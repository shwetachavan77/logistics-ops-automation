# Inbound Carrier Sales Automation

AI-powered voice agent that automates inbound carrier sales calls for freight brokerages. Built on HappyRobot.ai with a custom FastAPI backend and real-time analytics dashboard.

**Live Dashboard:** [https://logistics-ops-automation-production.up.railway.app](https://logistics-ops-automation-production.up.railway.app)  
**API Docs:** [https://logistics-ops-automation-production.up.railway.app/docs](https://logistics-ops-automation-production.up.railway.app/docs)

---

## What It Does

A carrier calls in looking for a load to haul. The AI agent (Sarah) handles the entire workflow:

1. **Verifies the carrier** via live FMCSA SAFER API (MC number + company name two-factor check)
2. **Searches available loads** by origin, destination, and equipment type
3. **Pitches the load** with full details (route, miles, weight, commodity, rate, pickup/delivery times)
4. **Negotiates the rate** through up to 3 rounds using a server-side pricing engine
5. **Transfers to a human rep** for final booking confirmation
6. **Logs everything** to a real-time analytics dashboard

## Architecture

```
Carrier Calls In
       │
       ▼
┌──────────────────────────┐
│   HappyRobot Platform    │
│   Voice Agent (Sarah)    │
│   GPT-4.1                │
│   4 Tools ──────────────────┐
│   Post-call: Classify +  │  │
│   Extract + Webhook      │  │
└──────────────────────────┘  │
                              ▼
                    ┌──────────────────┐
                    │  FastAPI Backend  │
                    │  (Railway)        │
                    ├──────────────────┤
                    │ FMCSA API        │
                    │ Load Search      │
                    │ Negotiation      │
                    │ Call Logging     │
                    │ Metrics          │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   PostgreSQL     │
                    │   (Railway)      │
                    │   loads, calls,  │
                    │   negotiations   │
                    └──────────────────┘
                             │
                    ┌────────▼─────────┐
                    │   Dashboard      │
                    │   React 18       │
                    │   4 tabs         │
                    └──────────────────┘
```

## Key Features

### Voice Agent
- FMCSA carrier verification with live federal API (no mocks)
- Two-factor identity check: MC number + company name confirmation
- Hard limit of 2 MC verification attempts per call
- Full load pitch with all shipment details
- 3-round negotiation with server-side pricing engine
- Agent never sees real loadboard rates or pricing strategy
- Conversational pausing after every piece of information
- Freight-industry number pronunciation (e.g., "twenty-eight fifty" not "two thousand eight hundred fifty")
- Guardrails for off-topic questions, spam, and AI identity queries

### Pricing Strategy
- Agent quotes 20% below loadboard rate to create negotiation room
- Carrier negotiates upward, engine manages acceptance caps (100% / 105% / 110%)
- Even after negotiation, brokerage typically pays at or under budget
- All pricing logic is server-side; agent has zero visibility into real rates

### Dashboard (4 Tabs)
- **Overview:** KPIs, conversion funnel, outcome/sentiment charts, negotiation depth, lane activity map, ROI calculator, alerts
- **Call Log:** Sortable/filterable table, click-to-open detail drawer with FMCSA status, shipment details, negotiation history, transcript, SMS, notes
- **Lanes:** Load board database, fill rate, top lanes, reseed button
- **Performance:** Rate preservation, cost per booking, AI vs Human comparison table

### Security
- API key authentication on all endpoints
- Server-side dashboard login (no credentials in frontend HTML)
- HTTPS via Railway automatic TLS
- Rate limiting via slowapi
- FMCSA API key stored as environment variable

## API Endpoints

All endpoints require `x-api-key` header except `/api/health` and `/api/auth/login`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/verify-carrier` | Verify MC via live FMCSA API |
| POST | `/api/search-loads` | Search loads (returns 20% discounted rate) |
| POST | `/api/negotiate` | Evaluate carrier offer (3-round engine) |
| POST | `/api/transfer` | Mock call transfer to human rep |
| POST | `/api/calls/log` | Log call with all extracted data |
| POST | `/api/calls/update-sms` | Patch SMS text onto existing call |
| POST | `/api/calls/backfill` | Normalize and fix existing records |
| POST | `/api/calls/cleanup` | Delete calls with no carrier data |
| POST | `/api/alerts/missed-opportunity` | Log near-miss with gap analysis |
| GET | `/api/metrics` | Aggregated dashboard metrics |
| GET | `/api/calls/recent` | Recent calls with load details (JOIN) |
| GET | `/api/calls/{id}/negotiations` | Round-by-round negotiation history |
| GET | `/api/loads/all` | All loads with availability status |
| POST | `/api/loads/refresh` | Reset dates, preserve booked loads |
| POST | `/api/loads/reseed` | Delete and repopulate all loads |
| POST | `/api/reset` | Nuclear reset (clears all data) |
| POST | `/api/auth/login` | Dashboard login |

## Quick Start

### Docker Compose (local)

```bash
git clone https://github.com/shwetachavan77/logistics-ops-automation.git
cd logistics-ops-automation
docker compose up --build
```

### Railway (production)

The app auto-deploys on git push to main. Environment variables:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (set by Railway) |
| `API_KEY` | API key for endpoint authentication |
| `FMCSA_API_KEY` | FMCSA SAFER System web key |
| `DASHBOARD_USERNAME` | Dashboard login username |
| `DASHBOARD_PASSWORD` | Dashboard login password |
| `DEMO_MODE` | Set to `false` in production |

## Test MC Numbers

| MC Number | Company | Result |
|-----------|---------|--------|
| 260913 | PAINTHORSE EXPRESS INC | PASS |
| 382806 | COOK HAULING LLC | PASS |
| 780050 | VIP EXPRESS LOGISTICS LLC | PASS |
| 100000 | C & C PRESTIGE LOGISTICS LLC | PASS |
| 150000 | (does not exist) | FAIL |
| 999999 | (does not exist) | FAIL |

## Tech Stack

- **Voice Agent:** HappyRobot.ai, GPT-4.1
- **Backend:** Python 3.12, FastAPI, asyncpg, httpx, slowapi
- **Database:** PostgreSQL (Railway managed)
- **Hosting:** Railway (Docker, auto-deploy)
- **FMCSA:** SAFER System live API
- **SMS:** Twilio via HappyRobot
- **Dashboard:** React 18, Recharts, single-file HTML

## HappyRobot Platform Config

See `happyrobot-config/` for platform configuration:
- `agent-prompt-final.md` - Voice agent prompt
- `tools-config.json` - Tool definitions
- `workflow-config.json` - Workflow structure
- `knowledge-base-loads.md` - Load data reference
- `negotiation-strategy.md` - Pricing strategy documentation

## Author

Shweta Chavan
