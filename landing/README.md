# OpenClaw Triage Landing Page

A modern, dark-themed landing page for OpenClaw Triage.

## Design

- **Dark theme** with orange accent (#ff6b35)
- **Monospace terminal** aesthetic for the hero
- **Gradient text** effects
- **Subtle noise texture** overlay
- **Grid background** with radial mask
- **Animated elements** with fade-in effects

## Deploy to Vercel

```bash
cd landing
npx vercel
```

Or connect your GitHub repo to Vercel for auto-deploys.

## Deploy to Netlify

```bash
cd landing
npx netlify deploy --prod
```

Or drag and drop the `landing` folder to Netlify's deploy UI.

## Local Development

```bash
cd landing
npx serve .
```

Then open http://localhost:3000

## Structure

- `index.html` — Single-page landing site
- `package.json` — Dependencies and scripts
- `vercel.json` — Vercel configuration
- `netlify.toml` — Netlify configuration

No build step required — pure HTML/CSS/JS.
