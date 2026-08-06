# Smart Community Platform 🏙️

A modern, full-stack civic-tech platform connecting citizens with local authorities to report, track, and resolve community infrastructure issues intelligently.

---

## 🌟 Key Features

- 📍 **Interactive Live Map**: Real-time Leaflet.js dark map displaying reported community hazards with status badges.
- 🤖 **AI Issue Auto-Categorization**: Natural Language Processing (NLP) categorizer classifying issue reports (`Pothole`, `Street Light`, `Water Supply`, `Waste Management`, `Traffic Signal`, `Park Maintenance`).
- 🤖 **Multi-Agent Workflow Engine**:
  - `ReporterAgent`: Automated severity and urgency scoring.
  - `ResolverAgent`: Municipal action plan generation.
  - `AnalystAgent`: Executive civic health reporting.
  - `CommunityAgent`: Volunteer skill matching.
- 📊 **Civic Analytics Dashboard**: Chart.js visual insights on resolution rates, category distributions, and active dispatches.
- 📸 **Media Upload Handling**: Validated image uploads with Cloudinary integration and local filesystem fallback.
- 🔐 **JWT Authentication & RBAC**: Password hashing using bcrypt with Role-Based Access Control (`citizen`, `volunteer`, `authority`, `admin`).
- ⚡ **Production-Ready Stack**: FastAPI, SQLAlchemy 2.0, Alembic migrations, Pydantic V2 schemas, and 100% passing Pytest test suite.

---

## 🛠️ Technology Stack

| Component | Technology |
|---|---|
| **Backend Framework** | FastAPI (Python 3.12) |
| **ORM & Database** | SQLAlchemy 2.0 + PostgreSQL / SQLite |
| **Database Migrations** | Alembic |
| **Authentication** | Passlib (Bcrypt) + Python-Jose (JWT) |
| **Frontend UI** | Vanilla JS, Leaflet.js, Bootstrap 5.3, Chart.js |
| **Image Storage** | Cloudinary API + Pillow fallback |
| **Testing** | Pytest + Starlette TestClient |

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+
- Virtualenv

### 2. Environment Setup
```bash
# Clone repository and enter directory
cd dashbord

# Run automated setup script
bash setup.sh

# Activate virtual environment
source venv/bin/activate
```

### 3. Environment Variables (`.env`)
Create or edit `.env` in the project root:
```env
APP_NAME="Smart Community Platform"
SECRET_KEY="supersecretjwtkeychangeinproduction"
DATABASE_URL="sqlite:///./smart_community.db"
PORT=8001
CLOUDINARY_CLOUD_NAME=""
CLOUDINARY_API_KEY=""
CLOUDINARY_API_SECRET=""
```

### 4. Running Database Migrations
```bash
PYTHONPATH=. venv/bin/alembic upgrade head
```

### 5. Starting Development Server
```bash
venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload
```

Access application:
- 🌐 **Web UI**: [http://localhost:8001/static/index.html](http://localhost:8001/static/index.html)
- 📊 **Analytics Dashboard**: [http://localhost:8001/static/dashboard.html](http://localhost:8001/static/dashboard.html)
- 📚 **Swagger API Docs**: [http://localhost:8001/docs](http://localhost:8001/docs)

---

## 🧪 Running Automated Tests

```bash
PYTHONPATH=. venv/bin/pytest tests/
```

---

## 📁 Repository Structure

```
├── backend/
│   ├── main.py             # FastAPI App Entrypoint & Lifespan
│   ├── config.py           # Centralized Pydantic Settings
│   ├── database.py         # SQLAlchemy Engine & Session Provider
│   ├── models/             # ORM Models (User, Issue, Vote, Comment, VolunteerTask, Notification)
│   ├── schemas/            # Pydantic v2 Schemas (User, Issue, Common)
│   ├── routes/             # API Endpoints (auth, users, issues, dashboard)
│   ├── utils/              # Security, Image Upload & Email Helpers
│   ├── ml/                 # NLP Categorizer & Image Analyzer
│   └── agents/             # AI Multi-Agent Workflows
├── frontend/
│   ├── index.html          # Main Map UI & Reporting Modals
│   ├── dashboard.html      # Analytics & KPI Dashboard
│   ├── issue.html          # Issue Detail Page
│   ├── profile.html        # User Profile Page
│   ├── css/                # Glassmorphic Stylesheets
│   └── js/                 # Leaflet Map, Auth & Feed Modules
├── tests/                  # Pytest Unit & Integration Tests
├── alembic.ini             # Migration Configuration
├── requirements.txt        # Python Dependencies
└── setup.sh                # Setup Script
```

---

## 📄 License
Distributed under the MIT License. See `LICENSE` for details.
