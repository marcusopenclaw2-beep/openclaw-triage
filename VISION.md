# OpenClaw Vision Document

## Mission

OpenClaw is a **personal AI assistant** that you run on your own devices. It answers you on the channels you already use (WhatsApp, Telegram, Slack, Discord, etc.).

## Core Principles

### 1. Personal First
- Single-user focus, not multi-tenant
- Your assistant, your data
- No user management, no RBAC complexity

### 2. Local-First
- Runs on your devices (laptop, Pi, VPS)
- Gateway is the control plane — the product is the assistant
- Cloud services are optional, not required

### 3. Privacy by Design
- Your messages, files, and data stay yours
- No telemetry without explicit opt-in
- Self-hostable end-to-end

### 4. Multi-Channel Native
- Works where you already communicate
- Unified inbox across all channels
- No forced app adoption

### 5. Extensible Skills
- Skills-based architecture
- Community and private skills
- Easy to create, share, install

## What We Build

### Core Platform
- Gateway WebSocket control plane
- Session management with isolation
- Multi-channel routing
- Tool platform (browser, canvas, nodes, cron)

### Channels
- WhatsApp, Telegram, Slack, Discord
- Google Chat, Signal, iMessage (BlueBubbles)
- Microsoft Teams, Matrix, Zalo
- WebChat for browser access

### Voice & Canvas
- Voice Wake + Talk Mode (macOS/iOS/Android)
- Live Canvas for visual workspace
- A2UI for agent-driven interfaces

### Skills Platform
- Bundled skills (weather, healthcheck, etc.)
- Managed skills from ClawHub
- Workspace skills for private development

## What We Avoid

### Not Building
- Multi-tenant SaaS features
- Complex enterprise RBAC
- Heavy cloud dependencies
- Breaking changes without migration
- AI slop (features for feature's sake)

### Anti-Patterns
- "Just add a config option" for everything
- Vendor lock-in (skills should be portable)
- Magic that hides what's happening
- Complexity that doesn't serve the personal use case

## Architecture Decisions

### Gateway as Control Plane
The Gateway is just the control plane — sessions, channels, tools, events. The product is the assistant experience.

### Main vs Isolated Sessions
- Main session: direct chat with your human
- Isolated sessions: group chats, shared contexts
- Security boundaries enforced

### Channel Routing
- Inbound messages route to appropriate session
- Reply tags for conversational context
- Per-channel chunking and formatting

## Contribution Guidelines

### PRs Should
- Solve a real personal use case
- Maintain or improve simplicity
- Include tests for new functionality
- Update documentation
- Respect security boundaries

### PRs Should Not
- Add enterprise complexity
- Break existing workflows
- Introduce heavy dependencies
- Stray from personal-first focus

## Success Metrics

- Works reliably for one person
- Easy to set up and maintain
- Fast response times
- Minimal resource usage
- Joy to use daily
