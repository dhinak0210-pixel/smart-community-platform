# 🏘️ Smart Community Platform

> An intelligent civic-tech platform connecting citizens with
> local authorities to report, track, and resolve community issues.

[![Tests](https://github.com/username/smart-community/actions/workflows/deploy.yml/badge.svg)](https://github.com/username/smart-community/actions)
[![Coverage](https://codecov.io/gh/username/smart-community/badge.svg)](https://codecov.io/gh/username/smart-community)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🌟 Live Demo

| | URL |
|---|---|
| **Frontend** | https://smartcommunity.vercel.app |
| **API** | https://smartcommunity-api.railway.app |
| **API Docs** | https://smartcommunity-api.railway.app/docs |

Demo accounts:
- Citizen: `citizen1@demo.com` / `DemoPass123!`
- Authority: `roads@municipality.demo` / `DemoPass123!`
- Admin: `admin@demo.com` / `DemoPass123!`

---

## ✨ Features

### For Citizens
- 📍 Report community issues with location pin on map
- 📸 Upload photos for visual evidence
- 🗺️ See all community issues on interactive map
- 👍 Vote on issues you care about
- 💬 Comment and follow issue progress
- 📧 Get email updates when your issue status changes
- ✅ Confirm when your issue is actually fixed

### For Authorities
- 📊 Analytics dashboard with charts and heatmaps
- 🔔 Notifications for new high-priority issues
- 📋 Manage and update issue status
- 📨 Send official updates to reporters
- 📈 Department performance tracking
- 📅 Weekly automated analytics reports

### AI Features
- 🤖 Auto-categorization from description text
- 🖼️ Image analysis to detect issue type (YOLO)
- 🔍 Automatic duplicate detection
- ⚡ Smart priority assignment
- 📍 Hotspot prediction for proactive planning
- 💬 24/7 AI community assistant (RAG)

### Autonomous Agents
- 🔵 **Reporter Agent**: Processes every new issue within 5 minutes
- 🟡 **Resolver Agent**: Escalates overdue issues every 6 hours
- 🟣 **Analyst Agent**: Sends weekly reports every Sunday 2am
- 🟢 **Volunteer Agent**: Matches volunteers to issues hourly
- 💬 **Community Agent**: Answers citizen questions 24/7

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11/3.12, FastAPI, Uvicorn |
| **Database** | PostgreSQL (Neon.tech) / SQLite |
| **ORM** | SQLAlchemy 2.0 + Alembic |
| **Auth** | JWT (python-jose) + bcrypt |
| **Storage** | Cloudinary (images) |
| **Email** | Gmail SMTP |
| **Maps** | Leaflet.js + OpenStreetMap |
| **Frontend** | HTML5, CSS3, Vanilla JS, Bootstrap 5 |
| **ML Text** | DistilBERT (Hugging Face) |
| **ML Vision** | YOLOv8n (Ultralytics) |
| **ML Similarity** | MiniLM (sentence-transformers) |
| **ML Priority** | Random Forest (scikit-learn) |
| **LLM** | Groq API (llama3-8b) |
| **Vector DB** | ChromaDB |
| **Scheduling** | APScheduler |
| **Hosting** | Railway (backend) + Vercel (frontend) |

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- Git

### Setup

```bash
# Clone
git clone https://github.com/username/smart-community.git
cd smart-community

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your values

# Download ML models (once, takes 5-10 minutes)
python scripts/download_models.py

# Run database migrations
alembic upgrade head

# Seed demo data (optional)
python scripts/seed_data.py

# Start backend
uvicorn backend.main:app --reload --port 8000

# Open frontend
# Just open frontend/index.html in your browser
```

### Running Tests

```bash
# All tests (sub-20s execution)
make test

# With coverage
make test-coverage

# Only unit tests (fastest)
make test-unit

# Only integration tests
make test-integration
```

---

## 📁 Project Structure

```
smart-community/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Settings
│   ├── database.py          # DB connection
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── routes/              # API endpoints (57 endpoints)
│   ├── utils/               # Helpers
│   ├── ml/                  # AI/ML models
│   ├── agents/              # Autonomous agents
│   ├── tasks/               # Background tasks
│   └── migrations/          # Alembic migrations
├── frontend/
│   ├── index.html           # Main map page
│   ├── issue.html           # Issue detail
│   ├── dashboard.html       # Authority dashboard
│   ├── auth.html            # Login/Register
│   ├── profile.html         # User profile
│   ├── css/                 # Stylesheets
│   └── js/                  # JavaScript
├── tests/                   # Pytest unit, integration, agent & e2e tests
├── scripts/
│   ├── download_models.py   # Download ML models
│   ├── migrate.py           # Run migrations
│   ├── create_admin.py      # Create admin user
│   ├── seed_data.py         # Demo data
│   └── health_check.py      # Verify deployment
├── .github/
│   └── workflows/
│       └── deploy.yml       # CI/CD pipeline
├── Procfile                 # Railway start command
├── railway.json             # Railway config
├── vercel.json              # Vercel config
├── nixpacks.toml            # Build config
├── requirements.txt         # Python dependencies
├── alembic.ini              # Migrations config
├── pytest.ini               # Test config
├── Makefile                 # Convenient commands
└── .env.example             # Environment template
```

---

## 📊 API Documentation

Full interactive docs at: `/docs`

| Group | Endpoints | Count |
|-------|-----------|-------|
| Authentication | Register, Login, Logout, Reset Password... | 12 |
| Issues | Create, List, Detail, Vote, Comment, Status... | 20 |
| Users | Profile, List, Ban, Role, Leaderboard... | 6 |
| Upload | Image upload, Avatar, Delete... | 6 |
| AI | Classify, Analyze, Duplicate check, Ask... | 7 |
| Agents | Status, Trigger, Logs, Community Chat... | 6 |
| **Total** | | **57** |

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Write tests for your changes
4. Make sure all tests pass: `make test`
5. Commit: `git commit -m 'Add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.
