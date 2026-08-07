# Smart Community Platform - Deployment Guide

## Prerequisites
- GitHub account (free)
- Railway account (free) - railway.app
- Vercel account (free) - vercel.com
- Neon.tech account (already set up) - neon.tech
- Cloudinary account (already set up) - cloudinary.com

---

## Step 1: Prepare GitHub Repository

```bash
# Initialize git if not done
git init

# Add all files
git add .

# Make sure .env is NOT included
git status | grep ".env"  # Should show nothing

# Commit
git commit -m "Initial commit: Smart Community Platform v1.0"

# Create repo on github.com then:
git remote add origin https://github.com/yourusername/smart-community.git
git push -u origin main
```

---

## Step 2: Set Up Railway (Backend)

### 2.1 Create Railway Project
1. Go to railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Select your smart-community repo
5. Railway auto-detects Python

### 2.2 Set Environment Variables
In Railway dashboard → Variables tab, add ALL variables from your `.env` file (see `.env.example` for complete list).

CRITICAL ones to add first:
```env
DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
GROQ_API_KEY=gsk_...
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
EMAIL_USER=your@gmail.com
EMAIL_PASSWORD=your_app_password
```

### 2.3 Deploy
- Railway auto-deploys when you push to `main`.
- First deploy takes 5-10 minutes (downloading ML models).
- Watch the build logs in Railway dashboard.

### 2.4 Get Your Backend URL
- After deploy: Railway → your service → Settings → Domain
- URL will be: `https://smart-community-api.railway.app`

### 2.5 Add FRONTEND_URL and CORS_ORIGINS
After getting Vercel URL (Step 3), come back and add:
```env
FRONTEND_URL=https://smart-community.vercel.app
CORS_ORIGINS=https://smart-community.vercel.app
```

---

## Step 3: Set Up Vercel (Frontend)

### 3.1 Update API URL in frontend
```javascript
// frontend/js/config.js
const CONFIG = {
  API_BASE_URL: "https://smart-community-api.railway.app",
  // ... rest of config
}
```

### 3.2 Deploy to Vercel
```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Deploy from frontend folder
vercel deploy frontend/ --prod

# Get your URL: https://smart-community.vercel.app
```

OR use Vercel dashboard:
1. Go to vercel.com
2. Import GitHub repo
3. Set Root Directory: `frontend`
4. Deploy

### 3.3 Update Backend with Frontend URL
- Go back to Railway → Variables
- Update: `FRONTEND_URL=https://smart-community.vercel.app`
- Update: `CORS_ORIGINS=https://smart-community.vercel.app`
- Railway auto-redeploys after env var change.

---

## Step 4: Run Database Migrations

```bash
# Option A: Run via Railway CLI
npm install -g @railway/cli
railway login
railway run python scripts/migrate.py

# Option B: SSH into Railway container
railway shell
python scripts/migrate.py

# Option C: Add to Railway start command (already in railway.json)
# Migrations run automatically before app starts
```

---

## Step 5: Create Admin User

```bash
# Run on Railway
railway run python scripts/create_admin.py \
  --name "City Administrator" \
  --email "admin@yourcity.gov"
# (will prompt for password)
```

---

## Step 6: Verify Deployment

```bash
# Run health check
python scripts/health_check.py https://smart-community-api.railway.app

# Expected output:
# ✅ API is reachable
# ✅ Health endpoint returns healthy
# ✅ Database is connected
# ✅ API docs are accessible
# ✅ Issues endpoint is working
# ✅ Auth endpoint is working
# ✅ Map markers endpoint is working
# ✅ Stats endpoint is working
# Results: 8 passed, 0 failed
# 🎉 ALL CHECKS PASSED!
```

---

## Step 7: Set Up GitHub Secrets for CI/CD

In your GitHub repo → Settings → Secrets → Actions:

```
RAILWAY_TOKEN=your_railway_token
RAILWAY_BACKEND_URL=https://smart-community-api.railway.app
VERCEL_TOKEN=your_vercel_token
VERCEL_ORG_ID=your_org_id
VERCEL_PROJECT_ID=your_project_id
```

Now every push to `main` auto-deploys! 🚀

---

## Step 8: Add Demo Data (Optional)

```bash
# ONLY for development/demo - not production!
railway run python scripts/seed_data.py
```

---

## Step 9: Set Up Monitoring

1. UptimeRobot: Add monitor for `/health` endpoint
2. Sentry: Add DSN to Railway environment variables
3. Set up email alerts

---

## Rollback Procedure

If something breaks after deployment:

```bash
# Option A: Railway dashboard
# Go to Deployments → click previous deploy → Redeploy

# Option B: Git revert
git revert HEAD
git push origin main
# Railway auto-deploys the revert

# Option C: Emergency database rollback
railway run alembic downgrade -1
```

---

## Cost Summary

| Service | Free Tier | Our Usage |
|---------|-----------|-----------|
| Railway | $5 credit/month | ~$3-4/month |
| Vercel | Unlimited static | $0 |
| Neon.tech | 0.5GB storage | $0 |
| Cloudinary | 25GB storage | $0 |
| Groq API | 100K tokens/day | $0 |
| Gmail SMTP | 2000/day | $0 |
| **TOTAL** | | **~$0** |

---

## Troubleshooting

### "Application failed to respond"
- Check Railway logs for startup errors
- Verify all required env vars are set
- Check `/health` endpoint response

### "ML models not loading"
- Check Railway disk space (1GB limit)
- Check build logs for download errors
- Models download during build phase

### "Database connection error"
- Verify `DATABASE_URL` includes `?sslmode=require`
- Check Neon.tech dashboard for connection limits
- Neon.tech pauses after inactivity; first request wakes it

### "CORS errors in browser"
- Verify `CORS_ORIGINS` includes your Vercel URL exactly
- Check no trailing slashes in URL
- Redeploy backend after updating CORS settings

### "Agents not running"
- Check startup logs for agent errors
- Verify system user exists: `python scripts/create_admin.py`
- Manually trigger: `POST /api/agents/reporter/run`
