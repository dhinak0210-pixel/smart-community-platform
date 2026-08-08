import os
import sys

# Ensure project root is in Python path for Vercel Serverless Functions
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set lightweight testing mode for Vercel Serverless environment
os.environ["APP_ENV"] = "testing"

from backend.main import app
