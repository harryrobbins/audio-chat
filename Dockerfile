# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Install system dependencies for Kokoro (espeak-ng) and build tools
RUN apt-get update && apt-get install -y \
    espeak-ng \
    curl \
    build-essential \
    python3-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory in the container
WORKDIR /app

# Copy the dependency files
COPY pyproject.toml uv.lock ./

# Install the dependencies (without dev dependencies)
RUN uv sync --frozen

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application with hot reloading
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
