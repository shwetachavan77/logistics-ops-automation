# Inbound Carrier Sales - AI Voice Agent

An AI-powered voice agent that automates inbound carrier sales calls for freight brokerages. Built on the HappyRobot platform with a custom FastAPI backend.

## Live Deployments

| Service | URL |
|---------|-----|
| **Dashboard** | [logistics-ops-automation-production.up.railway.app](https://logistics-ops-automation-production.up.railway.app/) |
| **API Docs** | [logistics-ops-automation-production.up.railway.app/docs](https://logistics-ops-automation-production.up.railway.app/docs) |
| **Health Check** | [logistics-ops-automation-production.up.railway.app/api/health](https://logistics-ops-automation-production.up.railway.app/api/health) |

## Architecture

```
Carrier calls in (web call / phone)
       |
       v
  HappyRobot Platform
  - Inbound Voice Agent (Sarah)
  - 4 Tools call external API mid-conversation
  - Real-time sentiment classification
  - Contact intelligence (carrier memory)
  - Post-call: Classify + Extract + Webhook
  - Conditional: if booked -> SMS confirmation
       |
       v
  FastAPI Backend (Railway)
  - FMCSA carrier verification (real API)
  - Load database search (PostgreSQL, fuzzy matching)
  - Negotiation engine (3-round, server-side pricing)
  - Rate limiting (SlowAPI)
  - Null/type handling for voice agent payloads
  - Call logging + metrics aggregation
       |
       v
  Metrics Dashboard (React 18 + Recharts)
  - 4 tabs: Overview, Call Log, Lanes, Performance
  - 6 KPI cards, area charts, donut charts, bar charts
  - Click-to-expand call detail drawer
  - AI vs Human performance comparison
  - Hidden demo mode toggle (triple-click logo)
```

## Features

### Voice Agent
- FMCSA carrier verification with company name confirmation (fraud prevention)
- 2 MC attempt limit per call, 4+ failed calls from same number -> immediate transfer
- Fuzzy load search with "anywhere" handling
- 3-round negotiation with server-side pricing isolation
- Real-time sentiment classification during calls
- Contact intelligence - remembers carriers across calls
- Off-topic guardrails (won't answer unrelated questions)
- Number pronunciation rules for clarity
- Post-booking SMS confirmation via Twilio

### Backend API
- **Rate limiting** - 30/min verify, 60/min search, 30/min negotiate
- **Null handling** - cleans "null", "", None from voice agent payloads
- **Flexible schemas** - accepts int/string/float for MC numbers, rates
- **Load availability** - marks loads unavailable after booking
- **Demo data** - 15 seed loads, 50 seed calls for dashboard

### Dashboard
- **Overview** - Total calls, booking rate, revenue, rate preservation, avg rounds, answer rate
- **Call Log** - Clickable table with slide-out detail drawer
- **Lanes** - Top origin-destination pairs with conversion rates
- **Performance** - Rate preservation, cost per booking, AI vs Human comparison

## API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/verify-carrier` | POST | API Key | FMCSA carrier verification |
| `/api/search-loads` | POST | API Key | Search available loads |
| `/api/negotiate` | POST | API Key | Evaluate carrier price offer |
| `/api/transfer` | POST | API Key | Mock call transfer |
| `/api/calls/log` | POST | API Key | Log completed call data |
| `/api/metrics` | GET | None | Dashboard metrics |
| `/api/calls/recent` | GET | None | Recent call log |
| `/api/loads` | GET | None | List all loads |
| `/api/health` | GET | None | Health check |
| `/` | GET | None | Dashboard UI |

## Quick Start

### Docker Compose (local)

```bash
git clone <repo-url>
cd happyrobot-carrier-sales
docker compose up --build
```

- API: http://localhost:8000/docs
- Dashboard: http://localhost:8000

### Railway (cloud)

1. Push to GitHub
2. Create project at railway.app
3. Add PostgreSQL plugin
4. Add service from GitHub repo
5. Set environment variables:
   - `API_KEY` - API authentication key
   - `DEMO_MODE=true` - Seeds demo data
   - `FMCSA_API_KEY` - FMCSA SAFER API web key

### Manual

```bash
export DATABASE_URL=postgresql://user:pass@host:5432/carrier_sales
export API_KEY=your-key
export DEMO_MODE=true
export FMCSA_API_KEY=your-fmcsa-key

cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Local dev default |
| `API_KEY` | API key for endpoint auth | `carrier-sales-dev-key-2026` |
| `FMCSA_API_KEY` | FMCSA SAFER Web Services key | Empty (uses mock) |
| `DEMO_MODE` | Seed demo data on startup | `true` |

## Negotiation Strategy

Server-side only. Pricing logic never exposed to the voice agent or caller.

| Round | Accept if carrier offers <= | Counter at |
|-------|----------------------------|------------|
| 1 | 100% of loadboard rate | Full rate |
| 2 | 105% of loadboard rate | 105% |
| 3 (final) | 110% of loadboard rate | Reject if above |

## Security Features

- **Server-side pricing isolation** - Floor rates never sent to the LLM
- **MC verification with name confirmation** - Carrier must say the company name
- **Per-call attempt limits** - 2 MC failures = forced transfer
- **Cross-call pattern detection** - 4+ failed calls = immediate transfer
- **API key authentication** - All POST endpoints protected
- **Rate limiting** - Prevents abuse
- **Off-topic guardrails** - Agent stays on freight topics only

## HappyRobot Platform Setup

See `happyrobot-config/` for all platform configuration:
- `agent-prompt-final.md` - Complete voice agent prompt with all rules
- `tools-config.json` - 4 tool definitions with webhook configs
- `workflow-config.json` - Full workflow structure with post-call automation
- `knowledge-base-loads.md` - Load inventory reference data

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12, FastAPI, asyncpg, httpx, SlowAPI |
| Database | PostgreSQL 16 |
| Dashboard | React 18, Recharts (CDN) |
| Voice Agent | HappyRobot Platform, GPT-4.1 |
| FMCSA API | SAFER Web Services (QCMobile) |
| Deployment | Railway (backend + dashboard), Docker |
| Infrastructure | Docker Compose (local dev) |
