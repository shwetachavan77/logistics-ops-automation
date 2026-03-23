# Inbound Carrier Sales - AI Voice Agent

HappyRobot FDE Technical Challenge: An AI-powered voice agent that automates inbound carrier sales calls for freight brokerages.

## Architecture

```
Carrier calls in (web call)
       |
       v
  HappyRobot Platform
  - Inbound Voice Agent (Sarah)
  - Tools call external API mid-conversation
  - Post-call: Classify + Extract + Webhook
       |
       v
  FastAPI Backend (this repo)
  - FMCSA carrier verification
  - Load database search (PostgreSQL)
  - Negotiation engine (3-round max)
  - Call logging + metrics aggregation
       |
       v
  Metrics Dashboard (React)
  - Call outcomes, sentiment, negotiation stats
  - Lane analysis, call log
```

## API Endpoints

All endpoints require `x-api-key` header.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/verify-carrier` | POST | FMCSA carrier verification |
| `/api/search-loads` | POST | Search available loads |
| `/api/negotiate` | POST | Evaluate carrier price offer |
| `/api/transfer` | POST | Mock call transfer |
| `/api/calls/log` | POST | Log completed call data |
| `/api/metrics` | GET | Dashboard metrics |
| `/api/calls/recent` | GET | Recent call log |
| `/api/loads` | GET | List all loads |
| `/api/health` | GET | Health check (no auth) |

## Quick Start

### Docker Compose (local)

```bash
git clone <repo-url>
cd happyrobot-carrier-sales
docker compose up --build
```

- API: http://localhost:8000/docs
- Dashboard: http://localhost:3000

### Railway (cloud)

```bash
# 1. Push this repo to GitHub

# 2. Go to railway.app, create new project
# 3. Add PostgreSQL plugin
# 4. Add service from GitHub repo
# 5. Set environment variables:
#    API_KEY=your-secure-key
#    DEMO_MODE=true
# 6. Railway gives you a public URL
```

### Manual

```bash
export DATABASE_URL=postgresql://user:pass@host:5432/carrier_sales
export API_KEY=your-key
export DEMO_MODE=true

cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://carrier_user:carrier_pass@localhost:5432/carrier_sales` |
| `API_KEY` | API key for endpoint auth | `carrier-sales-dev-key-2026` |
| `DEMO_MODE` | Seed demo data on startup | `true` |

## Negotiation Strategy

| Round | Accept if offer >= | Counter at |
|-------|--------------------|------------|
| 1 | 100% of loadboard rate | Full rate |
| 2 | 95% of loadboard rate | 95% |
| 3 (final) | 85% floor | Reject if below |

## HappyRobot Platform Setup

See `happyrobot-config/` for all platform configuration files:
- `agent-prompt-final.md` - Voice agent prompt
- `tools-config.json` - Tool definitions
- `workflow-config.json` - Full workflow structure
- `knowledge-base-loads.md` - Load data

## Tech Stack

- Python 3.12, FastAPI, asyncpg, httpx
- PostgreSQL 16
- React 18, Recharts
- Docker + Docker Compose
- HappyRobot platform (voice agent)
