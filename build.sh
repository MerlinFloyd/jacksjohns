#!/bin/bash

# Discord Bot + AI Agent Build Script
# This script builds and optionally runs the Docker containers

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found. Copying from .env.example...${NC}"
    cp .env.example .env
    echo -e "${RED}Please edit .env file with your actual values before running.${NC}"
    exit 1
fi

# Load environment variables
set -a
source .env
set +a

# Check required environment variables
if [ -z "$DISCORD_BOT_TOKEN" ] || [ "$DISCORD_BOT_TOKEN" = "your_discord_bot_token_here" ]; then
    echo -e "${RED}Error: DISCORD_BOT_TOKEN is not set in .env file${NC}"
    exit 1
fi

if [ ! -f credentials.json ]; then
    echo -e "${RED}Error: credentials.json not found. Please ensure GCP service account key exists.${NC}"
    exit 1
fi

# Parse command line arguments
ACTION=${1:-build}

case $ACTION in
    build)
        echo -e "${GREEN}Building Docker images...${NC}"
        docker compose build
        echo -e "${GREEN}Build complete!${NC}"
        ;;
    up)
        echo -e "${GREEN}Starting services...${NC}"
        docker compose up -d
        echo -e "${GREEN}Services started!${NC}"
        echo -e "Agent Service: http://localhost:8000"
        echo -e "View logs: docker compose logs -f"
        ;;
    down)
        echo -e "${YELLOW}Stopping services...${NC}"
        docker compose down
        echo -e "${GREEN}Services stopped.${NC}"
        ;;
    logs)
        docker compose logs -f
        ;;
    rebuild)
        echo -e "${YELLOW}Rebuilding and restarting services...${NC}"
        docker compose down
        docker compose build --no-cache
        docker compose up -d
        echo -e "${GREEN}Services rebuilt and started!${NC}"
        ;;
    *)
        echo "Usage: $0 {build|up|down|logs|rebuild}"
        echo "  build   - Build Docker images"
        echo "  up      - Start services in background"
        echo "  down    - Stop services"
        echo "  logs    - View service logs"
        echo "  rebuild - Rebuild images without cache and restart"
        exit 1
        ;;
esac
