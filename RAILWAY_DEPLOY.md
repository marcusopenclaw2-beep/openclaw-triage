# Deploy to Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/openclaw-triage)

## Manual Deploy

1. Go to [Railway](https://railway.app)
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose `marcusopenclaw2-beep/openclaw-triage`
5. Add environment variables:
   - `GITHUB_TOKEN` (required)
   - `ANTHROPIC_API_KEY` (optional)
   - `OPENAI_API_KEY` (optional)
6. Deploy!

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes | GitHub personal access token |
| `ANTHROPIC_API_KEY` | No | For Claude AI features |
| `OPENAI_API_KEY` | No | For GPT AI features |
| `POST_COMMENTS` | No | Auto-post comments (true/false) |
| `LOG_LEVEL` | No | DEBUG, INFO, WARNING, ERROR |

## Health Check

Once deployed, check:
```
GET https://your-app.railway.app/health
```
