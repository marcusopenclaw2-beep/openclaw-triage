# OpenClaw Triage Deployment Guide

## Deployment Options

### 1. Vercel (Serverless Functions)

Best for: Webhook handling, API endpoints

```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Deploy
vercel --prod
```

**Environment Variables:**
- `GITHUB_TOKEN` - Required
- `ANTHROPIC_API_KEY` - Optional
- `WEBHOOK_SECRET` - For GitHub webhook verification

**Limitations:**
- 10s timeout on free tier (may need paid for large PRs)
- Cold start latency

---

### 2. Railway / Render (Container)

Best for: Always-on API, background workers

```bash
# Railway
railway login
railway init
railway up

# Or Render
# Connect GitHub repo to Render dashboard
```

**Advantages:**
- No timeout limits
- Background workers supported
- Persistent storage for vector DB

---

### 3. Google Cloud Run

Best for: Scale-to-zero, pay-per-use

```bash
# Build and deploy
gcloud builds submit --tag gcr.io/PROJECT/openclaw-triage
gcloud run deploy openclaw-triage \
  --image gcr.io/PROJECT/openclaw-triage \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="GITHUB_TOKEN=...,ANTHROPIC_API_KEY=..."
```

---

### 4. PythonAnywhere

Best for: Simple hosting, scheduled tasks

1. Upload code via Git
2. Create web app with FastAPI
3. Set environment variables in WSGI config
4. Use scheduled tasks for batch analysis

---

### 5. Self-Hosted (VPS/Dedicated)

Best for: Full control, no limits

```bash
# Clone and install
git clone https://github.com/openclaw/openclaw-triage.git
cd openclaw-triage
pip install -e "."

# Run with systemd or docker-compose
uvicorn openclaw_triage.api:app --host 0.0.0.0 --port 8080
```

---

## GitHub App Setup

For full integration:

1. Go to GitHub → Settings → Developer Settings → GitHub Apps
2. Create New App:
   - Name: "OpenClaw Triage"
   - Homepage URL: Your deployed URL
   - Webhook URL: `https://your-app.com/webhook/github`
   - Webhook secret: Generate random string
3. Permissions:
   - Pull requests: Read & Write
   - Issues: Read & Write
   - Contents: Read
4. Subscribe to events:
   - Pull request
   - Issues
5. Install on repository

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes | GitHub personal access token |
| `ANTHROPIC_API_KEY` | No | For Claude AI features |
| `OPENAI_API_KEY` | No | For GPT AI features |
| `WEBHOOK_SECRET` | No | GitHub webhook verification |
| `POST_COMMENTS` | No | Auto-post comments (true/false) |
| `LOG_LEVEL` | No | DEBUG, INFO, WARNING, ERROR |

---

## Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install -e "."

EXPOSE 8080
CMD ["uvicorn", "openclaw_triage.api:app", "--host", "0.0.0.0", "--port", "8080"]
```

```bash
docker build -t openclaw-triage .
docker run -p 8080:8080 \
  -e GITHUB_TOKEN=... \
  -e ANTHROPIC_API_KEY=... \
  openclaw-triage
```

---

## Recommended Architecture

For OpenClaw's scale (600+ PRs/day):

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   GitHub App    │────▶│  API (Vercel)    │────▶│  Queue (Redis)  │
│  (Webhook)      │     │  (Webhook recv)  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
                           ┌──────────────────┐          │
                           │  Worker (Railway)│◀─────────┘
                           │  (Heavy lifting) │
                           └──────────────────┘
```

1. **Vercel** for webhook reception (fast, always available)
2. **Redis queue** for job buffering
3. **Railway/Render worker** for actual analysis (no timeout)
4. **GitHub App** for seamless integration

---

## Cost Estimates

| Platform | Free Tier | Paid (typical) |
|----------|-----------|----------------|
| Vercel | 100GB bandwidth, 10s functions | $20/mo |
| Railway | $5/mo credit | $5-20/mo |
| Render | Web services free | $7/mo |
| GCloud Run | 2M requests free | ~$10-50/mo |
| PythonAnywhere | 1 web app limited | $10/mo |

For OpenClaw's volume, expect $20-50/mo for reliable service.
