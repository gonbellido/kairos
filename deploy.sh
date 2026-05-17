#!/bin/bash
# KAIROS — Deploy script for Ubuntu 22.04+
# Usage: chmod +x deploy.sh && ./deploy.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   KAIROS — Production Deploy        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"

# ── Check prerequisites ──
echo -e "\n${YELLOW}[1/7]${NC} Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker not found. Installing...${NC}"
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo -e "${YELLOW}Please log out and back in, then re-run this script.${NC}"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}Docker Compose not found. Installing...${NC}"
    sudo apt-get update && sudo apt-get install -y docker-compose-plugin
fi

echo -e "${GREEN}✓ Docker $(docker --version | cut -d' ' -f3 | cut -d',' -f1)${NC}"

# ── Environment file ──
echo -e "\n${YELLOW}[2/7]${NC} Checking .env.production..."
if [ ! -f .env.production ]; then
    echo -e "${RED}.env.production not found!${NC}"
    echo "Copy .env.production.example and fill in your secrets:"
    echo "  cp .env.production.example .env.production"
    echo "  nano .env.production"
    exit 1
fi

# Check for placeholder values
if grep -q "REPLACE_WITH" .env.production; then
    echo -e "${RED}⚠ Found placeholder values in .env.production!${NC}"
    echo "Please replace all REPLACE_WITH_* values before deploying."
    echo "  nano .env.production"
    exit 1
fi

echo -e "${GREEN}✓ .env.production OK${NC}"

# ── SSL Certificates ──
echo -e "\n${YELLOW}[3/7]${NC} SSL certificates..."
if [ ! -f nginx/ssl/fullchain.pem ]; then
    echo "No SSL certs found. You have two options:"
    echo "  1. Use Let's Encrypt (recommended): run certbot after first deploy"
    echo "  2. Generate self-signed for testing: run ./scripts/gen_selfsign_ssl.sh"
    echo ""
    echo "For now, using HTTP only. Run certbot after DNS is configured."
fi

# ── Pull images ──
echo -e "\n${YELLOW}[4/7]${NC} Pulling Docker images..."
docker compose --env-file .env.production -f docker-compose.prod.yml pull

# ── Build app ──
echo -e "\n${YELLOW}[5/7]${NC} Building KAIROS app..."
docker compose --env-file .env.production -f docker-compose.prod.yml build app --no-cache

# ── Start services ──
echo -e "\n${YELLOW}[6/7]${NC} Starting services..."
docker compose --env-file .env.production -f docker-compose.prod.yml up -d

# ── Run migrations ──
echo -e "\n${YELLOW}[7/7]${NC} Running database migrations..."
sleep 10  # wait for postgres
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T app alembic -c /app/kairos/db/alembic.ini upgrade head || {
    echo -e "${YELLOW}⚠ Migration failed (may need to retry). Run:${NC}"
    echo "  docker compose --env-file .env.production -f docker-compose.prod.yml exec app alembic -c /app/kairos/db/alembic.ini upgrade head"
}

# ── Done ──
echo -e "\n${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Deploy Complete!                   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo "Subdomains needed (point to server IP):"
echo "  • coach.YOUR_DOMAIN  → Backoffice"
echo "  • api.YOUR_DOMAIN    → API REST"
echo "  • storage.YOUR_DOMAIN → MinIO Console"
echo "  • s3.YOUR_DOMAIN     → MinIO API"
echo ""
echo "After DNS is configured, get SSL with:"
echo "  sudo certbot --nginx -d coach.YOUR_DOMAIN -d api.YOUR_DOMAIN -d storage.YOUR_DOMAIN -d s3.YOUR_DOMAIN"
echo ""
echo "Check status:"
echo "  docker compose --env-file .env.production -f docker-compose.prod.yml ps"
echo "  curl http://localhost:8000/health"
