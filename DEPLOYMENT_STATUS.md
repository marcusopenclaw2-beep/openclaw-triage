# OpenClaw Triage — Deployment Status

## Deployed Services

### 1. Landing Page ✅
- **URL:** https://openclaw-triage.vercel.app
- **Status:** Live
- **Platform:** Vercel (Static)

### 2. API Server 🔄 (Building)
- **URL:** https://openclaw-triage-cwfg2wrmn-marcus-openclaws-projects.vercel.app
- **Status:** Building (installing dependencies)
- **Platform:** Vercel (Python serverless)

## What's Deployed

### Landing Page
- Dark theme with orange gradient
- Terminal mockup
- Feature cards
- Responsive design

### API (when build completes)
- Health check: `GET /` and `GET /health`
- Analyze PR: `POST /analyze/pr`
- Analyze Issue: `POST /analyze/issue`
- GitHub Webhook: `POST /webhook/github`

## Next Steps

### 1. Configure Environment Variables
Go to Vercel dashboard → Project Settings → Environment Variables:

```
GITHUB_TOKEN=ghp_your_token
ANTHROPIC_API_KEY=sk-ant-your_key  # Optional
WEBHOOK_SECRET=your_webhook_secret  # Optional
POST_COMMENTS=false
```

### 2. Set Up GitHub App (Optional)
For automatic PR analysis:
1. Create GitHub App at https://github.com/settings/apps
2. Set webhook URL to: `https://openclaw-triage-cwfg2wrmn-marcus-openclaws-projects.vercel.app/webhook/github`
3. Install on openclaw/openclaw repository

### 3. Test the API
```bash
curl https://openclaw-triage-cwfg2wrmn-marcus-openclaws-projects.vercel.app/health
```

### 4. Alternative Deployments
For production use with background workers:
- **Railway/Render:** Better for long-running tasks
- **Google Cloud Run:** Scale-to-zero, pay-per-use
- **Self-hosted:** Full control with Docker

See DEPLOYMENT.md for details.

## Files Created

- `src/openclaw_triage/api.py` — FastAPI server
- `src/openclaw_triage/worker.py` — Background worker
- `Dockerfile` — Container image
- `docker-compose.yml` — Local development
- `vercel.json` — Vercel config
- `Procfile` — Heroku/Railway
- `app.yaml` — Google App Engine
- `DEPLOYMENT.md` — Full deployment guide

## Cost

Current setup (Vercel free tier):
- Landing page: Free
- API: Free (with 10s function timeout limit)

For OpenClaw's scale (600+ PRs/day), consider:
- Vercel Pro ($20/mo) for longer timeouts
- Or Railway/Render ($5-20/mo) for no timeout limits
