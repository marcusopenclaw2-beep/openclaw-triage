# OpenClaw Triage — Self-Hosted Deployment

## Quick Start (5 minutes)

### 1. Clone and Configure

```bash
git clone https://github.com/marcusopenclaw2-beep/openclaw-triage.git
cd openclaw-triage

# Create environment file
cp .env.example .env
```

Edit `.env`:
```bash
GITHUB_TOKEN=ghp_your_token_here
ANTHROPIC_API_KEY=sk-ant-your_key_here  # Optional, for AI features
POST_COMMENTS=false
LOG_LEVEL=INFO
```

### 2. Deploy

```bash
./deploy.sh
```

Or manually:
```bash
docker-compose up -d
```

### 3. Verify

```bash
curl http://localhost:8080/health
```

## Usage

### Analyze a PR
```bash
curl -X POST http://localhost:8080/analyze/pr \
  -H 'Content-Type: application/json' \
  -d '{"repo":"openclaw/openclaw","pr_number":18546}'
```

### Batch Analysis (run once)
```bash
docker-compose run --rm worker python -m openclaw_triage.worker batch openclaw/openclaw 50
```

### Scheduled Batch Analysis (hourly)
```bash
docker-compose --profile scheduler up -d
```

## Production Deployment

### With Domain + HTTPS (using Caddy)

Create `docker-compose.prod.yml`:
```yaml
version: '3.8'

services:
  api:
    build: .
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./data:/app/data
    restart: unless-stopped

  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy-data:/data
      - caddy-config:/config
    restart: unless-stopped

volumes:
  caddy-data:
  caddy-config:
```

Create `Caddyfile`:
```
triage.yourdomain.com {
    reverse_proxy api:8080
}
```

### With GitHub Webhook

1. Go to your GitHub repo → Settings → Webhooks
2. Add webhook:
   - Payload URL: `https://triage.yourdomain.com/webhook/github`
   - Content type: `application/json`
   - Secret: (set in .env as WEBHOOK_SECRET)
   - Events: Pull requests, Issues

## Monitoring

### View logs
```bash
docker-compose logs -f api
```

### Update
```bash
git pull
docker-compose up -d --build
```

### Backup data
```bash
tar czf backup-$(date +%Y%m%d).tar.gz data/
```

## Requirements

- Docker + Docker Compose
- 2GB RAM minimum (4GB recommended for ML features)
- GitHub token with `repo` scope

## Cost

Self-hosted on any VPS:
- **Hetzner CX21**: €5.35/mo (2 vCPU, 4GB RAM) — sufficient
- **DigitalOcean Basic**: $12/mo (1 vCPU, 2GB RAM) — minimal
- **AWS t3.small**: ~$15/mo (2 vCPU, 2GB RAM)

## Troubleshooting

### API not starting
```bash
docker-compose logs api
```

### Out of memory
Add swap or upgrade VPS. PyTorch needs ~2GB for embeddings.

### Rate limiting
GitHub API: 5000 requests/hour for authenticated users.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   GitHub    │────▶│  API (FastAPI)│────▶│  Analysis   │
│  Webhooks   │     │   (Docker)    │     │   Engine    │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    Redis    │
                    │   (Cache)   │
                    └─────────────┘
```
