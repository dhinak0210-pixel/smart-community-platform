# 100% Free Deployment Guide: Smart Community Platform
## Zero Dollars. Zero Credit Card. Free Forever.

This guide provides the complete step-by-step instructions to host the **Smart Community Platform** using 100% free tier cloud services with zero ongoing costs and zero credit card requirements.

---

## 🛠️ Architecture Stack & Services Map

| Service | Primary Provider | Backup Provider | Free Tier Limit | Cost |
| :--- | :--- | :--- | :--- | :--- |
| **Backend Web API** | **Render.com** | Railway.app / Koyeb | 750 hrs/mo, 512MB RAM | **$0.00** |
| **Static Frontend** | **Vercel** | Netlify / GitHub Pages | Unlimited bandwidth | **$0.00** |
| **PostgreSQL Database** | **Neon.tech** | Supabase / CockroachDB | 0.5GB Serverless Postgres | **$0.00** |
| **Image Hosting** | **Cloudinary** | ImageKit | 25GB Storage & Bandwidth | **$0.00** |
| **Email Delivery** | **Resend.com** | Gmail SMTP / Brevo | 3,000 emails/month | **$0.00** |
| **AI LLM API** | **Groq API** | Google Gemini API | 100,000 tokens/day | **$0.00** |
| **ML Inference API** | **Hugging Face API** | Keyword Heuristics | Free zero-shot model API | **$0.00** |
| **Health & Keep-Alive**| **UptimeRobot** | GitHub Actions Workflow | 50 HTTP monitors (5 min) | **$0.00** |

---

## 🚀 Step-by-Step 30-Minute Deployment

### Step 1: Create Free Accounts (No Credit Card Needed)
Create free accounts at:
1. [GitHub](https://github.com)
2. [Render](https://render.com)
3. [Vercel](https://vercel.com)
4. [Neon.tech](https://neon.tech)
5. [Cloudinary](https://cloudinary.com)
6. [Resend](https://resend.com)
7. [Groq Console](https://console.groq.com)
8. [UptimeRobot](https://uptimerobot.com)

---

### Step 2: Set Up Neon PostgreSQL Database
1. Log into **Neon.tech** and click **Create Project**.
2. Name the project `smart-community` and choose your preferred region.
3. Copy the pooled connection string:
   ```text
   postgresql://username:password@ep-xxx.neon.tech/neondb?sslmode=require
   ```
4. Keep this string ready for Render environment configuration.

---

### Step 3: Push Codebase to GitHub
```bash
git init
git add .
git commit -m "feat: complete free deployment infrastructure"
git remote add origin https://github.com/YOUR_USERNAME/smart-community-platform.git
git push -u origin main
```

---

### Step 4: Deploy Web Backend to Render.com
1. Log into **Render.com** and click **New +** -> **Web Service**.
2. Connect your GitHub repository `smart-community-platform`.
3. Configure settings:
   - **Name**: `smart-community-api`
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     pip install -r requirements-free.txt && python scripts/download_models_lite.py
     ```
   - **Start Command**:
     ```bash
     uvicorn backend.main:app --host 0.0.0.0 --port $PORT --workers 1
     ```
   - **Plan**: `Free`
4. Expand **Advanced** -> **Add Environment Variable**:
   - `DATABASE_URL`: *(from Step 2)*
   - `SECRET_KEY`: *(Generate using `python -c "import secrets; print(secrets.token_hex(32))"`)*
   - `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`: *(from Cloudinary console)*
   - `GROQ_API_KEY`: *(from Groq console)*
   - `RESEND_API_KEY`: *(from Resend dashboard)*
   - `ML_MODE`: `lightweight`
   - `FRONTEND_URL`: `https://smart-community.vercel.app`
5. Click **Create Web Service**. Note your active backend URL (e.g. `https://smart-community-api.onrender.com`).

---

### Step 5: Run Database Migrations & Provision Admin Account
Open the **Render Shell** tab on your deployed Web Service dashboard and execute:
```bash
# Apply database migrations
alembic upgrade head

# Provision the default Administrator account
python scripts/create_admin.py --name "City Administrator" --email "admin@yourcity.gov"
```

---

### Step 6: Deploy Frontend to Vercel
1. Update `frontend/js/config.js` to point to your new Render backend URL:
   ```javascript
   const CONFIG = {
     API_BASE_URL: "https://smart-community-api.onrender.com",
     // ...
   };
   ```
2. Commit and push:
   ```bash
   git add frontend/js/config.js
   git commit -m "config: set production Render backend URL"
   git push origin main
   ```
3. In **Vercel.com**, click **Add New Project**, select your GitHub repository, set **Root Directory** to `frontend`, and click **Deploy**.

---

### Step 7: Prevent Cold Starts with UptimeRobot
Render web services enter sleep mode after 15 minutes of inactivity. To keep your app responsive 24/7 for zero cost:
1. Log into **UptimeRobot.com**.
2. Click **Add New Monitor**.
3. Choose **HTTP(S)**, enter URL: `https://smart-community-api.onrender.com/health`.
4. Set monitoring interval to **5 minutes**.
5. Save monitor. UptimeRobot will ping the service every 5 minutes, preventing sleep mode.

---

### Step 8: Verify Deployment Health
Run the health check suite against your live instance:
```bash
python scripts/health_check_free.py https://smart-community-api.onrender.com
```

Expected output:
```text
✅ Root API reachable (180ms)
✅ Health Check endpoint (22ms)
✅ Database connected (35ms)
✅ Issues List API endpoint (92ms)
✅ Map Markers API endpoint (71ms)
✅ Auth security rejection check (140ms)
✅ Analytics Stats endpoint (45ms)

🎉 ALL CRITICAL CHECKS PASSED SUCCESSFULLY!
```

---

## 🔍 Troubleshooting & Edge Cases

| Symptom | Cause | Solution |
| :--- | :--- | :--- |
| **Slow initial response (30-50s)** | Render cold start after inactivity | Ensure UptimeRobot HTTP monitor is active (Step 7). |
| **Out of Memory (OOM) error** | Heavy PyTorch models loaded | Verify `requirements-free.txt` and `ML_MODE=lightweight` are active. |
| **CORS policy error in browser** | Mismatched origin URL | Ensure `CORS_ORIGINS` on Render includes your exact Vercel URL. |
| **Database Connection Error** | Missing SSL mode | Ensure `?sslmode=require` is appended to `DATABASE_URL`. |

---

## 📊 Free Tier Usage & Limits Tracker

| Component | Free Monthly Allowance | Target Platform Usage | Safe Margin |
| :--- | :--- | :--- | :--- |
| **Render Web** | 750 Hours | 720 Hours (1 instance 24/7) | ✅ 100% covered |
| **Vercel Hosting** | Unlimited Static Traffic | Standard static assets | ✅ 100% covered |
| **Neon Postgres** | 500 MB DB Storage | ~15-30 MB | ✅ 94% headroom |
| **Cloudinary** | 25 GB Images | ~1-2 GB | ✅ 92% headroom |
| **Resend Email** | 3,000 Emails/month | ~100-300 Emails | ✅ 90% headroom |
| **Groq AI** | 100,000 Tokens/day | ~5,000 Tokens/day | ✅ 95% headroom |
