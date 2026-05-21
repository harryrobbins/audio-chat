# Makefile for Kokoro-82M Podcast Generator

.PHONY: help install build dev dev-backend dev-frontend phoenix clean test

# Default target
help:
	@echo "Available commands:"
	@echo "  make install        - Install all system and local dependencies (backend & frontend)"
	@echo "  make build          - Build both frontend assets and backend environment"
	@echo "  make dev            - Run both backend and frontend development servers in parallel"
	@echo "  make dev-backend    - Run backend FastAPI server with optimized auto-reload"
	@echo "  make dev-frontend   - Run frontend Vue 3 / Vite development server"
	@echo "  make phoenix        - Start Arize Phoenix container for LLM observability and tracing"
	@echo "  make test           - Run backend integration tests"
	@echo "  make clean          - Clean temporary caches, audio outputs, and build files"

# Install dependencies
install:
	@echo "Installing backend dependencies with uv..."
	uv sync
	@echo "Installing Node.js and frontend dependencies with pnpm..."
	pnpm env use --global lts
	cd frontend && pnpm install

# Build the project
build:
	@echo "Syncing backend environment..."
	uv sync
	@echo "Building frontend static assets..."
	cd frontend && pnpm run build

# Start Arize Phoenix in Docker for tracing
phoenix:
	@echo "Starting Arize Phoenix container..."
	docker compose up -d phoenix
	@echo "Arize Phoenix is running:"
	@echo "  - Web UI: http://localhost:3000"
	@echo "  - Collector: http://localhost:6006"

# Run backend dev server with optimized auto-reload settings
# Note: We explicitly exclude the virtual environments (.ubuntu-venv, .venv), frontend folder, 
# audio outputs, databases, and git files to prevent massive resource usage from file watching.
dev-backend:
	@echo "Starting FastAPI backend development server..."
	uv run uvicorn main:app \
		--reload \
		--host 127.0.0.1 \
		--port 8000 \
		--reload-exclude ".ubuntu-venv/*" \
		--reload-exclude ".venv/*" \
		--reload-exclude "frontend/*" \
		--reload-exclude "audio_outputs/*" \
		--reload-exclude "*.wav" \
		--reload-exclude "*.db" \
		--reload-exclude ".git/*"

# Run Vue 3 / Vite dev server
dev-frontend:
	@echo "Starting Vue 3 frontend development server..."
	cd frontend && pnpm run dev

# Run both frontend and backend dev servers in parallel
dev:
	@make -j2 dev-backend dev-frontend

# Run integration tests
test:
	@echo "Running local audio TTS micro-test..."
	uv run python test_client.py
	@echo "Running local podcast flow test..."
	uv run python test_podcast.py

# Clean temporary files
clean:
	@echo "Cleaning up generated audio files and caches..."
	rm -rf audio_outputs/ *.wav *.db .pytest_cache .uv cache/
	find . -type d -name "__pycache__" -exec rm -r {} +
	@echo "Clean completed."
