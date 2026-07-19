# Multi-stage build for a single-container Agentic RAG deployment.
# Both stages use the pure Debian Trixie slim OS image.

# Stage 1: Build Next.js frontend.
FROM debian:trixie-slim AS frontend-builder

WORKDIR /app/frontend

# Install Node.js 22 LTS via NodeSource plus build essentials.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

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

# Create a Python virtual environment for the backend to avoid conflicts
# with Debian's pre-installed system packages.
RUN python3.13 -m venv /app/.venv

# Install Python dependencies into the virtual environment.
COPY backend/requirements.txt ./backend/requirements.txt
RUN /app/.venv/bin/pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code.
COPY backend/ ./backend

# Copy built Next.js standalone frontend server.
COPY --from=frontend-builder /app/frontend/.next/standalone ./frontend
COPY --from=frontend-builder /app/frontend/.next/static ./frontend/.next/static
COPY --from=frontend-builder /app/frontend/public ./frontend/public

# Copy startup and process manager configs.
COPY scripts/start.sh ./scripts/start.sh
COPY scripts/start-frontend.sh ./scripts/start-frontend.sh
COPY config/supervisord.conf ./config/supervisord.conf
RUN chmod +x ./scripts/start.sh ./scripts/start-frontend.sh

# The container listens on the port provided by the PaaS via $PORT.
# Default is 3000, but Render/Railway override this. EXPOSE is informational.
EXPOSE 3000

ENV BACKEND_PORT=8000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

CMD ["./scripts/start.sh"]
