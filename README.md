# OpenClaw Triage

An AI-powered system for managing the impossible volume of PRs and Issues hitting OpenClaw.

## Quick Start

```bash
# Install
pip install -e .

# Set environment variables
export GITHUB_TOKEN="your_github_token"
export ANTHROPIC_API_KEY="your_anthropic_key"  # Optional, for AI features

# Analyze a PR
openclaw-triage analyze-pr 1234 --repo openclaw/openclaw

# Analyze an Issue
openclaw-triage analyze-issue 18556 --repo openclaw/openclaw

# Batch analyze open PRs
openclaw-triage batch --repo openclaw/openclaw --limit 20
```

## Features

### 1. Deduplication
Detects similar/duplicate PRs and Issues using semantic similarity:
- Embeddings-based comparison
- Cross-references PRs solving the same problem
- Configurable similarity thresholds

### 2. Base PR Detection
Identifies foundational PRs that others build upon using signals:
- **Chronological**: First to address the issue
- **Quality**: Test coverage, code clarity, documentation
- **Engagement**: Discussion activity, reactions
- **Author**: Track record, past contributions
- **Completeness**: Scope of solution

### 3. Deep Review
AI-powered code review with:
- Security analysis
- Performance implications
- Breaking change detection
- Test coverage evaluation
- Actionable findings

### 4. Vision Alignment
Flags PRs that stray from project goals:
- Compares against vision document
- Identifies scope creep
- Suggests alternative approaches

## Installation

```bash
git clone https://github.com/openclaw/openclaw-triage.git
cd openclaw-triage
pip install -e .
```

## Configuration

Environment variables:
- `GITHUB_TOKEN` - GitHub API token (required)
- `ANTHROPIC_API_KEY` - For Claude-powered analysis (optional)
- `OPENAI_API_KEY` - For GPT-powered analysis (optional)
- `TRIAGE_REPO` - Default repository

Or use a config file:
```bash
openclaw-triage init-config
# Edit config.yaml
```

## Usage

### Single PR Analysis
```bash
openclaw-triage analyze-pr 1234 --repo openclaw/openclaw
```

### Batch Analysis
```bash
# Analyze all open PRs
openclaw-triage batch --repo openclaw/openclaw --limit 50

# Save results
openclaw-triage batch --repo openclaw/openclaw -o results.json
```

### JSON Output
```bash
openclaw-triage analyze-pr 1234 --json | jq '.priority'
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Webhook                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Triage Gateway                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │ Deduplicator│  │ Base Detector│  │Deep Reviewer│  │Vision   │ │
│  │             │  │             │  │             │  │Checker  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Output Layer                                │
│  • GitHub Labels/Comments  • Dashboard  • Maintainer Alerts      │
└─────────────────────────────────────────────────────────────────┘
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Format code
black src/
ruff check src/
```

## License

MIT
