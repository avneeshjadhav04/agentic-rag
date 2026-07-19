# Multi-stage build for a single-container Agentic RAG deployment.
# Stage 1: Build Next.js frontend.
FROM node:22-slim-trixie AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
ENV NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
RUN npm run build

# Stage 2: Pure Debian Trixie runtime with Python 3.13 + Node.js 22 LTS.
FROM debian:trixie-slim

WORKDIR /app

# Install system dependencies for document processing, runtime, and build tools.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libssl-dev \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    poppler-utils \
    supervisor \
    python3.13 \
    python3-pip \
    python3.13-venv \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 22 LTS via NodeSource.
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r backend/requirements.txt

# Copy backend code.
COPY backend/ ./backend

# Copy built frontend and install production runtime.
COPY --from=frontend-builder /app/frontend/.next ./frontend/.next
COPY --from=frontend-builder /app/frontend/public ./frontend/public
COPY frontend/package.json frontend/package-lock.json* ./frontend/
RUN cd frontend && npm install --omit=dev

# Copy startup and process manager configs.
COPY scripts/start.sh ./scripts/start.sh
COPY config/supervisord.conf ./config/supervisord.conf
RUN chmod +x ./scripts/start.sh

# Expose the single external port (PaaS usually provides $PORT).
EXPOSE 3000

ENV BACKEND_PORT=8000
ENV NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV PORT=3000

CMD ["./scripts/start.sh"]
