#!/bin/bash
# Quick deploy script for OpenClaw Triage

set -e

echo "🦞 OpenClaw Triage Deployment"
echo "=============================="

# Check for required env vars
if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ GITHUB_TOKEN not set"
    echo "Get one at: https://github.com/settings/tokens"
    exit 1
fi

# Create data directory
mkdir -p data

# Pull and build
echo "📦 Building containers..."
docker-compose pull
docker-compose build

# Start services
echo "🚀 Starting services..."
docker-compose up -d

# Wait for health check
echo "⏳ Waiting for API to be ready..."
sleep 5

# Check health
if curl -s http://localhost:8080/health | grep -q "healthy"; then
    echo "✅ API is healthy!"
    echo ""
    echo "📊 Dashboard: http://localhost:8080"
    echo ""
    echo "To analyze a PR:"
    echo "  curl -X POST http://localhost:8080/analyze/pr \\"
    echo "    -H 'Content-Type: application/json' \\"
    echo "    -d '{\"repo\":\"openclaw/openclaw\",\"pr_number\":1234}'"
    echo ""
    echo "To view logs:"
    echo "  docker-compose logs -f api"
    echo ""
    echo "To stop:"
    echo "  docker-compose down"
else
    echo "⚠️  API may not be ready yet. Check logs with:"
    echo "  docker-compose logs -f api"
fi
