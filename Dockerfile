# Multi-stage build for a single-container Agentic RAG deployment.
# Stage 1: Build Next.js frontend.
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
ENV NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
RUN npm run build

# Stage 2: Python backend runtime + frontend static bundle.
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for document processing and node runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libxml2-dev \
    libxslt1-dev \
    libssl-dev \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    poppler-utils \
    nodejs \
    npm \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code.
COPY backend/ ./backend

# Copy built frontend and install production runtime.
COPY --from=frontend-builder /app/frontend/.next ./frontend/.next
COPY --from=frontend-builder /app/frontend/public ./frontend/public
COPY frontend/package.json frontend/package-lock.json* ./frontend/
RUN cd frontend && npm install --omit=dev

# Copy startup and process manager configs.
COPY start.sh ./start.sh
COPY supervisord.conf ./supervisord.conf
RUN chmod +x ./start.sh

# Expose the single external port (PaaS usually provides $PORT).
EXPOSE 3000

ENV BACKEND_PORT=8000
ENV NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV PORT=3000

CMD ["./start.sh"]
