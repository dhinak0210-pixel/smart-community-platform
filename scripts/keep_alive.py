#!/usr/bin/env python3
"""
Keep-alive strategy for Render free tier web service.

Render free tier web services spin down after 15 minutes of inactivity.
This file documents the 3 zero-cost keep-alive methods to ensure zero cold-start delays.

Method 1 (RECOMMENDED): UptimeRobot (100% Free, External)
  1. Register a free account at https://uptimerobot.com
  2. Click "Add New Monitor"
  3. Set Monitor Type: HTTP(S)
  4. Friendly Name: Smart Community Backend
  5. URL: https://smart-community-api.onrender.com/health
  6. Monitoring Interval: 5 minutes
  7. Save monitor. UptimeRobot pings the health check every 5 minutes forever.

Method 2: GitHub Actions Scheduled Cron (Backup)
  Included in `.github/workflows/deploy_free.yml` or `.github/workflows/keep_alive.yml`.
  Runs every 14 minutes using free GitHub Actions minutes.

Method 3: Self-Ping Task (Internal Fallback)
"""

import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPTIMEROBOT_GUIDE = """
===================================================================
100% FREE UPTIMEROBOT KEEP-ALIVE SETUP INSTRUCTIONS:
===================================================================
1. Navigate to: https://uptimerobot.com
2. Create a free account (No credit card required).
3. Select "Add New Monitor":
   - Monitor Type: HTTP(S)
   - Friendly Name: Smart Community API
   - URL: https://your-render-app.onrender.com/health
   - Interval: 5 minutes
4. Click "Create Monitor".
5. Done! Your Render free app will stay awake 24/7 without cost.
===================================================================
"""

if __name__ == "__main__":
    print(UPTIMEROBOT_GUIDE)
