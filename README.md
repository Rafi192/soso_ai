# soso_ai — WhatsApp Restaurant Consultation AI

A WhatsApp-based AI consultation system for restaurant owners. The AI acts as a personal business advisor, collects a restaurant profile, diagnoses the owner's main business problem, and delivers tailored recommendations — all through a conversational interface.

Built with FastAPI, Redis, and OpenAI GPT-4o. Designed to plug into a Node.js/NestJS WhatsApp backend.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Local Development Setup](#local-development-setup)
- [Running the Application](#running-the-application)
- [API Reference](#api-reference)
- [Conversation Flow](#conversation-flow)
- [Architecture Overview](#architecture-overview)
- [Deployment (VPS)](#deployment-vps)
- [Useful Commands](#useful-commands)

---

## How It Works

The AI guides a restaurant owner through a structured conversation:

1. **Profile Collection** — collects restaurant name, location, owner name, cuisine type, number of locations, and delivery platform info
2. **Problem Detection** — presents a menu of 7 business problem categories and identifies which one applies
3. **Category Confirmation** — confirms the detected problem with the user
4. **Diagnostic Questions** — asks targeted questions based on the problem type (with axis branching for certain types)
5. **Scoring** — calculates a severity score based on signals detected in answers
6. **Recommendations** — delivers 3-4 specific, actionable recommendations with real partnership references (Hemblem, GFV/MrBeast Burger, TheFork, Zelty, etc.)
7. **Follow-up** — handles any follow-up questions the owner has about the recommendations

The system supports both **English and French** — it detects the user's language automatically and responds accordingly.

---

## Project Structure

```
soso_ai/
├── app/
│   ├── main.py                          startup/shutdown
│   ├── api/
│   │   └── chat.py                      # POST /api/v1/generate endpoint
│   ├── config/
│   │   └── settings.py                  # Environment config via pydantic BaseSettings
│   ├── llm/
│   │   ├── openai_client.py             # All OpenAI API calls (chat, classify, extract)
│   │   ├── prompt_builder.py            # System prompts for each conversation stage
│   │   └── response_formatter.py        # Strips markdown, truncates for WhatsApp
│   ├── memory/
│   │   ├── redis_client.py              # Redis async connection setup
│   │   └── session_manager.py           # Load/save sessions, append history
│   ├── orchestrator/
│   │   └── conversation_orchestrator.py # State machine — routes each message to correct handler
│   ├── recommendations/
│   │   └── recommendation_engine.py     # Deterministic recommendation selection
│   ├── schemas/
│   │   ├── chat_schema.py               # Request/response Pydantic models
│   │   └── session_schema.py            # UserSession model, stage constants
│   ├── scoring/
│   │   └── scoring_engine.py            # Signal evaluation, severity + confidence scoring
│   └── workflows/
│       ├── profile_workflow.py          # Profile collection with multi-field extraction
│       ├── problem_detection_workflow.py # Category menu, classification, confirmation
│       ├── diagnostic_workflow.py       # Per-category question banks with axis branching
│       └── recommendation_workflow.py   # Final recommendation formatting
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env                                 # Not committed — see Environment Variables below
```

---

## Prerequisites

- Python 3.11+
- Redis (via Docker or local install)
- OpenAI API key
- Docker + Docker Compose (for containerized deployment)

---

## Environment Variables

Create a `.env` file in the project root. Never commit this file.

```dotenv
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_MINI_MODEL=gpt-4o-mini

# Redis
REDIS_HOST=localhost        # Use 'redis' when running via Docker Compose
REDIS_PORT=6379
REDIS_DB=0
REDIS_TTL_SECONDS=86400    # Session lifetime in seconds (24 hours)

# MongoDB (optional — not yet wired into session persistence)
MONGODB_URI=mongodb+srv://...
MONGODB_DB=soso_DB
MONGODB_COLLECTION=conversations
```

**Important:** When running locally, use `REDIS_HOST=localhost`. When deploying via Docker Compose on a VPS, change to `REDIS_HOST=redis` (the container name).

---

## Local Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/Rafi192/soso_ai.git
cd soso_ai
```

### 2. Create and activate a virtual environment

```bash
python -m venv soso_env

# Windows
soso_env\Scripts\activate

# Mac/Linux
source soso_env/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create your `.env` file

Copy the example above and fill in your actual keys.

### 5. Start Redis

Make sure Docker Desktop is running, then:

```bash
docker start redis-server
```

If you don't have a Redis container yet, create one:

```bash
docker run -d --name redis-server -p 6379:6379 redis:latest
```

Verify Redis is running:

```bash
docker exec -it redis-server redis-cli ping
# Should return: PONG
```

---

## Running the Application

```bash
uvicorn app.main:app --reload
```

The API will be available at:
- **Swagger UI:** http://localhost:8000/docs
- **Health check:** http://localhost:8000/health
- **Chat endpoint:** http://localhost:8000/api/v1/generate

---

## API Reference

### `POST /api/v1/generate`

Receives a WhatsApp message and returns the AI response.

**Request body:**
```json
{
  "whatsappNumber": "+44123456789",
  "userMessage": "Hello!"
}
```

**Response:**
```json
{
  "responseText": "Hi, I'm your personal advisor...",
  "extractedData": {},
  "actionTriggered": null
}
```

**`actionTriggered` values:**

| Value | When it fires |
|---|---|
| `null` | Normal conversation turn |
| `ONBOARDING_COMPLETE` | Problem menu has been shown |
| `UPDATE_STAGE_HOT_LEAD` | Recommendations have been delivered |
| `SHOW_BOOKING_CTA` | User is in follow-up stage |

---

## Conversation Flow

```
User sends any message
        ↓
INTRO → PROFILE_COLLECTION (6 questions)
        ↓
PROBLEM_DETECTION (category menu + free text classification)
        ↓
CATEGORY_CONFIRMATION (confirm detected problem)
        ↓
DIAGNOSTIC_QUESTIONS (per-category question bank)
        │
        ├── TYPE_1 and TYPE_3: pivot question first (Axis A or B)
        │   then axis-specific questions
        │
        └── All others: direct questions
        ↓
SCORING (severity score calculated from signals)
        ↓
RECOMMENDATIONS (3-4 tailored recommendations delivered)
        ↓
FOLLOWUP (open-ended — user can ask anything about the recommendations)
```

### Problem Categories

| Number | Category | Internal Key |
|---|---|---|
| 1 | Not enough customers / lack of visibility | `TYPE_2_LOCAL_VISIBILITY` |
| 2 | Too dependent on delivery platforms | `TYPE_1_PLATFORM_DEPENDENCY` |
| 3 | I make revenue but don't earn enough | `TYPE_3_LOW_MARGIN` |
| 4 | Customers come but don't come back | `TYPE_4_RETENTION` |
| 5 | I have lots of tools but it's chaos | `TYPE_5_DIGITAL_CHAOS` |
| 6 | I'm launching / relaunching a location | `TYPE_6_LAUNCH` |
| 7 | Something else | `OTHER` |

### Axis Branching

Two categories split into sub-branches based on a pivot question:

**TYPE_1_PLATFORM_DEPENDENCY**
- Axis A: Delivery (revenue comes mainly from platforms)
- Axis B: On-site (revenue comes mainly from dine-in)

**TYPE_3_LOW_MARGIN**
- Axis A: Reduce costs (food cost, waste, staff optimization)
- Axis B: Increase revenue (virtual brand, delivery expansion)

---

## Architecture Overview

### State Machine

The orchestrator owns a strict state machine. The LLM generates text and tone — it never controls flow, scores, or selects recommendations. All routing decisions are deterministic Python code.

```
ConversationOrchestrator
    ├── _handle_intro()
    ├── _handle_profile()          → ProfileWorkflow
    ├── _handle_problem_detection() → ProblemDetectionWorkflow
    ├── _handle_category_confirmation()
    ├── _handle_diagnostics()      → DiagnosticWorkflow + ScoringEngine
    ├── _handle_scoring_passthrough()
    ├── _handle_recommendations()  → RecommendationWorkflow + RecommendationEngine
    └── _handle_followup()
```

### Multi-Field Extraction

Rather than strict one-question-one-answer sequencing, the system runs an LLM extraction pass on every user message to detect if multiple questions were answered at once. This makes the conversation feel natural — if a user says "I'm Rafi, I run Food Village in Bogura", both `owner_name` and `restaurant_name` are captured in one turn.

### Scoring

Each diagnostic question has an associated signal. When a signal fires (based on keyword/pattern matching of the answer), points are added to a severity score. When confidence (answers given / total questions) reaches 0.80 AND all critical questions are answered, diagnostics stop and recommendations are generated.

### Session Storage

Sessions are stored as JSON in Redis, keyed by WhatsApp number. TTL is configurable (default 24 hours). Each session contains the full conversation history, profile, answers, score, stage, and last recommendations.

---

## Deployment (VPS)

### 1. Update `.env` for production

```dotenv
REDIS_HOST=redis    # Docker Compose container name
```

### 2. Push your code to GitHub

```bash
git add .
git commit -m "ready for deployment"
git push origin main
```

### 3. SSH into your VPS

```bash
ssh root@your_vps_ip
```

### 4. Install Docker and Docker Compose

```bash
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
apt install docker-compose -y
```

### 5. Clone the repo on VPS

```bash
git clone https://github.com/Rafi192/soso_ai.git
cd soso_ai
```

### 6. Create `.env` on VPS

```bash
nano .env
# Paste your environment variables, save with Ctrl+X → Y → Enter
```

### 7. Build and start everything

```bash
docker-compose up --build -d
```

### 8. Open firewall port

```bash
ufw allow 8000
ufw allow 22
ufw enable
```

Your API is now live at `http://your_vps_ip:8000`.

---

## Useful Commands

### Local development

```bash
# Start Redis
docker start redis-server

# Run the app
uvicorn app.main:app --reload

# Flush Redis (reset all sessions)
docker exec -it redis-server redis-cli FLUSHALL

# Check Redis keys
docker exec -it redis-server redis-cli KEYS *
```

### VPS / Docker Compose

```bash
# Start everything
docker-compose up --build -d

# View live logs
docker-compose logs -f app

# Stop everything
docker-compose down

# Restart after code changes
git pull
docker-compose up --build -d

# Flush Redis on VPS
docker exec -it redis redis-cli FLUSHALL
```

### Health check

```bash
curl http://localhost:8000/health
# Expected: {"status": 200, "message": "Server is healthy"}
```

---

## Notes

- The `.env` file must never be committed to Git. It is listed in `.gitignore`.
- `REDIS_HOST` must be `localhost` for local development and `redis` for Docker Compose deployment.
- The system is designed to receive messages from a NestJS WhatsApp backend — the `whatsappNumber` field is used as the session key.
- All recommendation content (Hemblem, GFV/MrBeast Burger, TheFork, Zelty, Innovorder, Tiller) reflects real partnership programs defined in the MUFU Brain document. Do not alter recommendation texts without updating the MUFU Brain source.