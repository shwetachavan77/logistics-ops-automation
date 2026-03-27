# HappyRobot FDE Challenge - Kanban Board Items
# Copy these into Trello, Notion, or any kanban tool

========================================
COLUMN: DONE
========================================

Backend API (FastAPI + PostgreSQL)
- FastAPI app with async PostgreSQL via asyncpg
- Deployed to Railway with auto HTTPS
- Health check endpoint
- Server-side dashboard authentication (username + password via /api/auth/login)
- No credentials exposed in frontend HTML source code
- Logout button clears session

FMCSA Carrier Verification
- Real FMCSA SAFER API integration
- No mock fallbacks - real verification only, returns ineligible on any API failure
- Input sanitization on MC numbers
- Verified: MC 260913, 382806, 780050, 100000, 1234
- Two-factor identity check: MC number + carrier must state company name
- Agent never reveals company name from FMCSA records

MC Verification Security
- Hard limit of 2 MC attempts per call, no third attempt under any circumstances
- After 2 failures: auto-transfer to human rep for security
- Carriers with 4+ previous failed verifications: auto-transfer without attempting
- Failed carriers directed to safersys.org for self-service
- No loads, rates, or freight discussed until MC verified

Load Search Engine
- Fuzzy search on origin/destination/equipment
- Broad query guard: rejects "any/anywhere" for both origin + destination
- "Anything" equipment type handled: searches without filter instead of passing literal string
- Requires at least one of origin, destination, or equipment before searching
- 25 seeded loads across US corridors
- Loads auto-marked unavailable when booked (is_available = FALSE)
- Reseed endpoint with current dates
- Refresh endpoint resets availability and shifts dates to tomorrow
- Fetch New Loads: adds 5 random loads, caps unbooked at 100

3-Round Negotiation Engine
- 20% markdown pricing strategy: search_loads returns loadboard_rate x 0.80
- Agent quotes discounted rate, has no visibility into real loadboard rate
- Carrier negotiates upward, evaluate_offer uses real rate for caps
- Round 1: 100%, Round 2: 105%, Round 3: 110% caps
- Counter messages never reference real loadboard rate or internal pricing
- All amounts rounded to nearest whole dollar for voice clarity
- Each round logged to negotiations table with carrier_offer, our_counter, accepted status
- Negotiation history endpoint: GET /api/calls/{id}/negotiations
- Instant accept if carrier offers at or below loadboard rate

Missed Opportunity Analysis
- Auto-analyzes gap when negotiation fails
- Within 15%: "Near-miss deal. Worth manual follow-up."
- Over 15%: "Too far apart."
- Gap percentage, dollar amounts, and recommendation stored in notes field

Transfer Endpoint
- Accepts JSON body or query params
- Handles empty/missing call_id gracefully

Call Logging API
- POST /api/calls/log with flexible schema
- Auto-generates call_id if missing (uuid)
- Handles boolean sentiment, int MC numbers, empty strings
- Accepts transcript as string, list, or empty array
- Accepts both call_duration and call_duration_seconds field names
- model_validator cleans all voice agent payloads

SMS Update Endpoint
- POST /api/calls/update-sms patches SMS text and notes onto existing call record
- Separates SMS logging from main call logging to avoid data overwrites
- Works with HappyRobot Paths node (booked branch)

Data Maintenance Endpoints
- POST /api/reset: clears all calls and negotiations, resets loads
- POST /api/calls/cleanup: deletes calls with no carrier data
- POST /api/calls/backfill: normalizes sentiment case, backfills loadboard_rate from loads table, fixes negotiation_rounds from negotiations table, cleans empty strings to NULL
- POST /api/loads/refresh: resets availability, shifts dates to tomorrow using SQL arithmetic
- POST /api/loads/reseed: deletes and repopulates loads with current dates

API Security
- API key auth on ALL /api/* endpoints via middleware (JSONResponse, not HTTPException)
- Dashboard auth: server-side username + password validation, returns API key on success
- HTTPS via Railway auto TLS
- Rate limiting via SlowAPI (30/min verify, 60/min search/log, 10/min transfer, 5/min reset)
- Input sanitization (clean_str, clean_float, clean_int)
- No credentials in frontend code

HappyRobot Voice Agent
- Agent "Sarah" from carrier sales team
- GPT-4.1 model
- Professional female voice, office background
- Recording disclaimer enabled
- 19 freight key terms configured
- Numerals on for number formatting
- Never reveals company name, brokerage name, or internal systems
- Identifies as "Sarah, part of the carrier sales team" if asked about being AI
- Never mentions tools, webhooks, APIs, FMCSA, or databases

Agent Conversational Pausing
- Pauses after repeating MC number, waits for confirmation
- Pauses after stating rate or price, waits for response
- Pauses after describing load, asks "How does that sound?"
- Waits 3 seconds minimum after yes/no questions
- Never stacks multiple pieces of info in one turn
- Says "Are you still there?" after 3 seconds of silence
- Waits 5 seconds after goodbye before ending call

Agent Number Pronunciation
- Dollar amounts: "twenty-eight fifty" not "two thousand eight hundred fifty"
- MC numbers: digit-by-digit with pauses
- Miles: "nine twenty miles" not "nine hundred twenty miles"
- Weight: "forty-two thousand pounds" (thousand OK for weight)

Agent Guardrails
- Off-topic questions redirected: "I can only help with booking loads and freight questions"
- 2 off-topic redirects then call ended
- Never answers math, trivia, music, or general knowledge
- Reacts naturally to carrier emotions (friendly gets warmth, frustrated gets empathy)
- Never reveals internal systems, pricing strategy, or negotiation logic
- Never says "let me check my system" - says "let me check what we have available"

4 Voice Agent Tools
- verify_carrier: POST /api/verify-carrier with x-api-key header
- search_loads: POST /api/search-loads with x-api-key header
- evaluate_offer: POST /api/negotiate with x-api-key header
- transfer_call: POST /api/transfer with x-api-key header (JSON body)

Post-Call Workflow
- Classify Call Outcome (AI Classify node, 6 tags: booked, carrier_declined, no_match, negotiation_failed, verification_failed, general_inquiry)
- Classify Carrier Sentiment (separate AI Classify node, 4 tags: positive, neutral, negative, aggressive)
- Extract Call Data (AI Extract node: carrier_mc, carrier_name, load_id, agreed_rate, initial_offer, carrier_final_offer, agent_final_offer, negotiation_rounds, loadboard_rate, sentiment)
- Log Call to Dashboard (Webhook POST with retry: 3 attempts, 5s initial delay, 2x backoff, 30s max)
- Paths node for conditional routing
- SMS confirmation on booked calls (Twilio outbound text agent)
- SMS webhook: POST /api/calls/update-sms
- Missed opportunity webhook on negotiation_failed with gap analysis

Classify Call Outcome - FIXED
- "booked" tightened: requires carrier agreed on specific rate for specific load AND transfer to rep
- "general_inquiry" added for rep requests, questions, hangups
- 6 total tags covering all call outcomes

Sentiment Classification - FIXED
- Separate AI Classify node added (not the real-time boolean)
- 4 labels: positive, neutral, negative, aggressive
- Runs on transcript after call ends
- Dashboard handles case-insensitive matching (Positive/positive both work)

Agent Prompt - FIXED
- Agent never reveals company name (redirects to "our carrier sales line")
- Hard limit of 2 MC attempts enforced
- Immediate transfer when carrier requests rep
- "Anything" equipment handled without calling search with literal string
- Full load pitch with all fields (ID, route, times, miles, weight, commodity, pieces, dimensions, rate, notes)
- Pausing rules enforced
- Number pronunciation rules enforced

Contact Intelligence
- Enabled with 5-interaction memory window
- Auto context for repeat callers
- 4+ failed verifications triggers auto-transfer

Call Intent Classifier
- 5 classes: booking, rates, follow up, general inquiry, spam

Dashboard - Overview Tab
- 6 KPI cards (calls, booking rate, revenue, rate saved, avg rounds, answer rate)
- Conversion funnel (calls to deals closed with drop-off visualization)
- Outcomes donut chart with all 6 categories
- Call volume area chart (14 days)
- Sentiment bar chart (case-insensitive colors)
- Negotiation depth chart
- Lane activity SVG map with US outline, city labels, clickable routes, conversion colors
- Smart alerts panel (scam detection, rate anomalies, low inventory, high failure rates)
- ROI calculator with configurable inputs (dispatcher time, hourly cost, AI cost)

Dashboard - Call Log Tab
- Outcome filter buttons with counts (All, Booked, Declined, No Match, Neg. Failed, MC Failed, Inquiry)
- Lane filter from map clicks with clear button
- Clickable column headers for sorting (all columns)
- 12-column table including Transcript link column
- Empty state with refresh prompt
- Transcript "View" link opens drawer with transcript visible

Dashboard - Call Detail Drawer
- FMCSA verification status (pass/fail, company match)
- Call details (time, duration mm:ss, load ID)
- Full shipment details from loads table JOIN (route, equipment, miles, weight, commodity, pieces, dimensions, pickup, delivery, real loadboard rate, rate/mile, load notes)
- Real negotiation history from /api/calls/{id}/negotiations (round, carrier offer, our counter, accepted/countered badge)
- Outcome with rate delta and rate preservation
- Sentiment analysis with icon and contextual reasoning
- Notes section
- SMS Sent section with phone icon
- Full transcript in scrollable box

Dashboard - Lanes Tab
- 4 KPI cards (fill rate, available, booked, avg rate/mile)
- Top lanes table with progress bars
- Full Load Board database table (ID, origin, destination, equipment, rate, miles, weight, commodity, pieces, pickup, Available/Booked badge)
- Reseed Loads button (deletes and repopulates with current dates)
- Empty state

Dashboard - Performance Tab
- Row 1: Rate preservation, avg call duration, cost per booking
- Row 2: Round 1 close rate, floor rate hits, avg conceded, avg rounds
- Row 3: Failed vetting rate, sentiment breakdown, equipment demand, repeat carrier rate
- AI vs Human comparison table

Dashboard - Controls
- Server-side login (username + password, no creds in HTML)
- Logout button (red, clears session)
- Refresh button (no page jump)
- Fetch New Loads button (5 loads, 100 cap)
- Clear Data button with confirmation
- Reseed Loads button on Lanes tab
- Live call indicator (polls every 10s, pulsing cyan badge)
- Secret demo mode (triple-click CS logo, yellow Demo badge, preloaded mock data)

Dashboard - Auth
- Login screen with username and password fields
- Server-side validation via POST /api/auth/login
- API key returned on success, stored in sessionStorage
- All data fetches include API key header
- Data loads only after authentication (no premature mock data)
- Logout clears sessionStorage and returns to login

Call Duration
- Mapped from voice agent Duration output
- Accepted as call_duration or call_duration_seconds
- Cleaned via clean_int
- Displayed as mm:ss in dashboard

Docker Setup
- docker-compose.yml (PostgreSQL + API + Dashboard)
- Dockerfile for Railway (python:3.12-slim, uvicorn on 8080)
- .env.example with all variables documented
- DEMO_MODE=false in production

Documentation
- Build Description v3 (Word doc) with MC security, pausing, number formatting, pricing strategy, all dashboard features, all API endpoints, HappyRobot nodes, future improvements
- Negotiation Strategy document (assumptions + strategy)
- Agent prompt (agent-prompt-final.md)
- HappyRobot platform context doc
- README with live URLs

Git Repository
- GitHub: shwetachavan77/logistics-ops-automation
- All configs in happyrobot-config/ folder
- Agent prompt, workflow config, tools config, knowledge base

========================================
COLUMN: TO DO
========================================

Record Clean Demo Calls
- Reset data, refresh loads
- Call 1: Booked with negotiation (MC 260913, Chicago-Dallas, counter to ~$2,400)
- Call 2: No match (ask for lane not in database)
- Call 3: Verification failed (MC 150000)
- Run backfill after calls

Take Dashboard Screenshot
- Save as dashboard-screenshot.png in repo root
- Update README to display it

Record 5-Minute Demo Video
- Reset dashboard first
- Run full booking scenario with negotiation
- Show dashboard updating with real data
- Walk through all 4 tabs
- Show ROI calculator and lane map

Publish Workflow to Production
- Currently on Dev environment
- Switch to Production before final submission

========================================
COLUMN: V2 / PHASE 2
========================================

Transcript Reliability
- Add server-side transcript fetch via HappyRobot API as fallback when webhook transcript is empty
- Implement delayed re-fetch (30s after call ends) to catch late-resolving transcripts
- Store raw transcript JSON alongside formatted text for debugging

Negotiation Round Tracking v2
- Pass real call_id (room_name) to evaluate_offer tool so rounds are linked to the correct call
- Fallback: match negotiations by load_id + timestamp window when call_id is empty
- Show round-by-round visualization in dashboard with offer/counter timeline chart

Dynamic Lane Pricing
- Auto-adjust negotiation floors based on lane conversion rates
- Below 30% conversion: lower floor 5% to win more deals
- Above 70% conversion: raise floor to protect margin
- Alerts panel already detects patterns; automate the response
- Historical rate trends per lane to predict optimal pricing

Time-Decay Pricing
- Loads near pickup deadline get progressively aggressive pricing
- 48+ hours out: hold firm at 20% markdown
- 24 hours out: reduce markdown to 10%
- 4 hours out: drop to near-cost, accept almost any offer
- Prevents deadhead (empty truck return) which costs more than a low-margin load

Carrier Relationship Scoring
- Track booking reliability, on-time history, and negotiation patterns per carrier
- Build carrier rating (1-100) from call data and booking outcomes
- Preferred carriers get better initial rate quotes (15% markdown instead of 20%)
- Repeat callers flagged with green badge in dashboard
- Endpoint already exists: GET /api/carriers/{mc}/history

Predictive Load Matching
- ML model trained on historical booking data to predict which loads a carrier is likely to accept
- Factor in: carrier past lanes, equipment, avg accepted rate, time of day, day of week
- Pre-rank loads before pitching so agent leads with highest-probability match
- Reduce no-match rate and improve booking conversion

Outbound Carrier Campaigns
- Store carrier lane preferences on no-match calls
- Auto-notify carriers when matching loads become available
- Outbound calling workflow on HappyRobot
- "Hey, we got a load on your lane. Interested?" warm leads convert higher

Multi-Language Voice Support
- Spanish-speaking workforce is significant in freight
- HappyRobot supports 50+ languages
- Requires prompt translation + language setting
- Auto-detect language from first few seconds and switch dynamically

Real-Time WebSocket Dashboard
- Replace 10-second polling with WebSocket for instant updates
- Show call progress live as it happens (verified, searching, negotiating, transferred)
- Real-time notification toasts when calls complete

TMS Integration
- Pull live load data from Transportation Management Systems (McLeod, TMW, MercuryGate)
- Push booking confirmations directly into TMS
- Replace static load database with live sync
- Auto-update load availability in real-time

Fraud Detection v2
- Flag same MC from different phone numbers
- Detect carriers accepting far below market rate (possible double-brokering)
- Velocity check: same MC calling 10+ times in an hour
- Cross-reference MC with known fraud databases
- Auto-block after confirmed fraud pattern

Voice Sentiment Real-Time Escalation
- Use real-time sentiment (not just post-call) to detect frustration mid-call
- If sentiment drops to aggressive during the call, auto-offer transfer to human rep
- Track sentiment trajectory (started positive, turned negative) for coaching insights

Automated Rate Confirmation
- SendGrid integration for email
- Auto-send rate confirmation PDF to carrier email on booking
- Include: load details, agreed rate, pickup/delivery times, broker contact info
- Endpoint already exists: POST /api/confirmations/rate

Load Coverage Heatmap
- Dashboard view showing geographic areas with no available loads
- Overlay carrier demand (where carriers are asking for loads) vs supply (where loads exist)
- Help ops team prioritize shipper outreach to fill coverage gaps

Carrier Onboarding Flow
- If new carrier calls and passes FMCSA but has no history, trigger onboarding
- Collect: insurance certificate, W9, carrier packet via SMS/email
- Auto-populate carrier profile for future calls

Competitive Rate Intelligence
- Integrate DAT or Truckstop rate data for real-time market benchmarking
- Show how our rates compare to market average per lane
- Dashboard widget: "Your rate vs market" with recommendation to adjust

Call Recording Playback
- Store call recordings (HappyRobot provides these)
- Play recordings directly in the dashboard call drawer
- Useful for quality assurance and dispute resolution

Shift-Based Analytics
- Break down metrics by time of day and day of week
- Identify peak call hours for staffing human backup
- Show which shifts have highest conversion rates

Multi-Brokerage White Label
- Support multiple brokerage clients on one backend
- Each brokerage gets their own agent name, loads, dashboard, and pricing strategy
- Org-level isolation in database with tenant_id

Automated Follow-Up Sequences
- Carrier declined today? Auto-call back in 48 hours with new loads on their lane
- Negotiation failed? Send SMS with a revised offer 24 hours later
- No match? Text when a matching load appears within 7 days

Dashboard Mobile View
- Responsive layout for tablet and phone
- KPI cards stack vertically
- Swipeable tabs
- Call drawer becomes full-screen modal on mobile

Carrier Self-Service Portal
- Web portal where carriers can browse available loads without calling
- Filter by lane, equipment, rate range
- Click to book, triggers rate confirmation flow
- Reduces inbound call volume for straightforward bookings

A/B Test Negotiation Strategies
- Test different markdown percentages (15%, 20%, 25%)
- Test different counter offer phrasing
- Compare conversion rates and avg agreed rate across strategies
- Auto-select winning strategy per lane based on data

Voice Cloning for Brand Consistency
- Create a custom voice model for "Sarah" so she sounds identical across all calls
- Consistent brand experience regardless of underlying model updates

Compliance and Audit Trail
- Log every tool call, API request, and agent decision with timestamps
- Exportable audit trail for regulatory compliance
- Track who accessed what data on the dashboard (admin audit log)

Dashboard RBAC
- Role-based access: admin, manager, viewer
- Admin: reset data, reseed loads, manage settings
- Manager: view all data, export reports
- Viewer: read-only metrics, no sensitive data
