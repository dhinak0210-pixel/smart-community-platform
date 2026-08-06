#!/usr/bin/env bash
set -e

echo "=========================================="
echo "Initializing Smart Community Platform..."
echo "=========================================="

# 1. Create Directory Structure
echo "[1/5] Creating directory structure..."
mkdir -p backend/models
mkdir -p backend/schemas
mkdir -p backend/routes
mkdir -p backend/utils
mkdir -p backend/agents
mkdir -p backend/ml
mkdir -p backend/migrations/versions
mkdir -p frontend/css
mkdir -p frontend/js
mkdir -p tests
mkdir -p uploads

# 2. Create Python Init & Placeholder Files
echo "[2/5] Creating Python package initializers and placeholders..."
cat << 'EOF' > backend/models/__init__.py
"""Database models package for Smart Community Platform."""
EOF

cat << 'EOF' > backend/models/volunteer.py
"""Volunteer and community coordination models (Phase 3)."""
# TODO: Implement Volunteer, Task, and Skill models in Phase 3
EOF

cat << 'EOF' > backend/models/notification.py
"""System notification models (Phase 3)."""
# TODO: Implement Notification model and delivery preference schemas in Phase 3
EOF

cat << 'EOF' > backend/schemas/__init__.py
"""Pydantic schemas package for data validation."""
EOF

cat << 'EOF' > backend/schemas/common.py
"""Shared Pydantic schemas across modules."""
from typing import Generic, TypeVar, List, Optional
from pydantic import BaseModel, Field

T = TypeVar("T")

class ResponseModel(BaseModel, Generic[T]):
    """Generic API response wrapper."""
    success: bool = True
    message: str = "Operation completed successfully"
    data: Optional[T] = None

class PaginationParams(BaseModel):
    """Pagination query parameters."""
    page: int = Field(default=1, ge=1, description="Page number")
    limit: int = Field(default=10, ge=1, le=100, description="Items per page")
EOF

cat << 'EOF' > backend/routes/__init__.py
"""API route handlers package."""
EOF

cat << 'EOF' > backend/utils/__init__.py
"""Backend utilities and helper modules."""
EOF

cat << 'EOF' > backend/agents/__init__.py
"""AI Agent workflows package (Phase 3)."""
EOF

cat << 'EOF' > backend/agents/reporter_agent.py
"""Reporter Agent for automated issue ingestion (Phase 3)."""
# TODO: Implement ReporterAgent using CrewAI / LangChain in Phase 3
EOF

cat << 'EOF' > backend/agents/resolver_agent.py
"""Resolver Agent for automated dispatch and tracking (Phase 3)."""
# TODO: Implement ResolverAgent for authority workflows in Phase 3
EOF

cat << 'EOF' > backend/agents/analyst_agent.py
"""Analyst Agent for trend analysis and reporting (Phase 3)."""
# TODO: Implement AnalystAgent for community insights in Phase 3
EOF

cat << 'EOF' > backend/agents/community_agent.py
"""Community Engagement Agent (Phase 3)."""
# TODO: Implement CommunityAgent for volunteer assignment in Phase 3
EOF

cat << 'EOF' > backend/ml/__init__.py
"""Machine Learning models package (Phase 2)."""
EOF

cat << 'EOF' > backend/ml/categorizer.py
"""NLP Issue Categorizer using Transformers (Phase 2)."""
# TODO: Fine-tune BERT model for auto-categorization of issues in Phase 2
EOF

cat << 'EOF' > backend/ml/image_analyzer.py
"""Computer Vision Image Analyzer using YOLOv8 (Phase 2)."""
# TODO: Integrate YOLOv8 for detecting road damage and hazards in Phase 2
EOF

cat << 'EOF' > tests/__init__.py
"""Test suite package."""
EOF

touch tests/conftest.py
touch tests/test_auth.py
touch tests/test_issues.py

touch frontend/index.html
touch frontend/dashboard.html
touch frontend/issue.html
touch frontend/profile.html

touch frontend/css/style.css
touch frontend/css/dashboard.css
touch frontend/css/components.css

touch frontend/js/config.js
touch frontend/js/auth.js
touch frontend/js/map.js
touch frontend/js/issues.js
touch frontend/js/dashboard.js

touch alembic.ini
touch Procfile

# 3. Create Virtual Environment
echo "[3/5] Setting up Virtual Environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created."
fi

source venv/bin/activate

# 4. Install Dependencies
echo "[4/5] Installing Python packages from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Initialize Git Repository if not present
echo "[5/5] Checking Git repository..."
if [ ! -d ".git" ]; then
    git init
    echo "Git repository initialized."
fi

echo "=========================================="
echo "Smart Community Platform project setup complete!"
echo "Next steps:"
echo " 1. Copy .env.example to .env and configure your secrets"
echo " 2. Activate virtual environment: source venv/bin/activate"
echo " 3. Start development server: uvicorn backend.main:app --reload"
echo "=========================================="
