# Smart Community Platform 🏙️

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon.tech-4169E1?style=flat-square&logo=postgresql)](https://neon.tech)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

A civic-tech platform connecting citizens with local authorities to report, track, and resolve community issues intelligently.

---

## 🚀 Project Overview

The **Smart Community Platform** empowers residents to report infrastructure and safety issues (e.g., potholes, broken streetlights, illegal dumping) with precise geolocation and photos. Local authorities gain a centralized dashboard to track, assign, and resolve reported issues efficiently.

### Key Features
- 📍 **Interactive Issue Mapping**: Real-time Leaflet map visualization of community reports.
- 📸 **Photo & Media Support**: File uploads with Cloudinary cloud storage integration.
- 👤 **Role-Based Access Control**: Separate workflows for Citizens, Volunteers, and Authorities.
- 📊 **Analytics Dashboard**: Chart.js data visualizations for resolution metrics.
- 🤖 **AI-Powered Workflows (Phase 2 & 3)**: Auto-categorization using Transformers & YOLOv8 image analysis.

---

## 🛠️ Tech Stack

| Domain | Technologies |
| :--- | :--- |
| **Backend Framework** | FastAPI (Python 3.11+), Uvicorn |
| **Database & ORM** | PostgreSQL (Neon.tech), SQLAlchemy 2.0, Alembic |
| **Security & Auth** | Passlib (bcrypt), PyJWT (python-jose), OAuth2 Password Bearer |
| **Frontend** | HTML5, CSS3, JavaScript (ES6+), Bootstrap 5.3 |
| **Mapping & Charts** | Leaflet.js 1.9.4, Chart.js |
| **AI / ML (Planned)** | Hugging Face Transformers, Ultralytics YOLOv8, CrewAI, Groq API |
| **Hosting & DevOps** | Git, GitHub, Railway.app, Cloudinary |

---

## 📂 Project Structure

```text
smart-community/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── database.py              # DB connection engine and session pool
│   ├── config.py                # Pydantic environment configuration
│   ├── models/                  # SQLAlchemy ORM models (User, Issue, Vote, Comment)
│   ├── schemas/                 # Pydantic data validation schemas
│   ├── routes/                  # API routers (auth, issues, users, dashboard)
│   ├── utils/                   # Utilities (auth helpers, Cloudinary uploads, mailers)
│   ├── agents/                  # AI CrewAI Agent workflows (Phase 3)
│   └── ml/                      # Machine Learning models & categorizers (Phase 2)
├── frontend/
│   ├── index.html               # Main map & issue reporting page
│   ├── dashboard.html           # Authority analytics dashboard
│   ├── issue.html               # Single issue detailed view
│   ├── profile.html             # User profile management
│   ├── css/                     # Application styling & component themes
│   └── js/                      # Leaflet map, Auth, API, & Chart modules
├── tests/                       # Pytest test suite (auth, issues endpoints)
├── uploads/                     # Local fallback media storage
├── .env.example                 # Environment configuration template
├── .gitignore                   # Version control ignore rules
├── setup.sh                     # Automated environment setup script
├── requirements.txt             # Python dependencies with version pins
└── README.md                    # Project documentation
```

---

## ⚡ Quick Start Guide

### Prerequisites
- **Python 3.11+**
- **Git**
- **PostgreSQL** (Local instance or free [Neon.tech](https://neon.tech) database)

### 1. Clone & Initialize Environment
Run the automated setup script to set up virtual environment and dependencies:

```bash
git clone https://github.com/your-username/smart-community.git
cd smart-community
bash setup.sh
```

### 2. Configure Environment Secrets
Copy the environment template and update your credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```ini
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/smart_community"
SECRET_KEY="your_custom_secret_key_here"
```

### 3. Run Development Server
Activate your virtual environment and launch Uvicorn:

```bash
source venv/bin/activate
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Access the interactive API documentation at `http://localhost:8000/docs`.

---

## 🔑 Environment Variables

| Variable | Description | Default / Required |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL connection URL | **Required** |
| `SECRET_KEY` | JWT signing secret key | **Required** |
| `ALGORITHM` | JWT hashing algorithm (`HS256`) | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT expiration time | `60` |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary storage cloud name | Optional |
| `CLOUDINARY_API_KEY` | Cloudinary API Key | Optional |
| `CLOUDINARY_API_SECRET` | Cloudinary API Secret | Optional |
| `GROQ_API_KEY` | Groq API Key for LLM services | Optional |

---

## 🌐 Key API Endpoints Overview

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :---: |
| `POST` | `/api/v1/auth/register` | Register a new user | ❌ |
| `POST` | `/api/v1/auth/login` | Login and obtain JWT access token | ❌ |
| `GET` | `/api/v1/users/me` | Fetch authenticated user profile | ✅ |
| `GET` | `/api/v1/issues/` | List all reported issues with filters | ❌ |
| `POST` | `/api/v1/issues/` | Create a new community issue report | ✅ |
| `GET` | `/api/v1/issues/{id}` | Retrieve issue details | ❌ |
| `PUT` | `/api/v1/issues/{id}` | Update issue status (Authorities) | ✅ |
| `GET` | `/api/v1/dashboard/stats` | Fetch community statistics & chart metrics | ✅ |

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:
1. Fork the project repository.
2. Create a feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for details.
