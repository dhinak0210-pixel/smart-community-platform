# Smart Community Platform - Monitoring

## Free Monitoring Stack

### 1. Railway Built-in (Automatic)
- CPU and RAM usage graphs
- Request volume
- Response times
- Error rates
- Available at: railway.app → your service → Metrics

### 2. UptimeRobot (Free - uptime monitoring)
- Monitors `/health` endpoint every 5 minutes
- Alerts via email if down
- Free for 50 monitors
- Setup at: uptimerobot.com
- Add monitor: HTTP(S) → `https://your-api.railway.app/health`
- Alert contacts: your email

### 3. Sentry (Free - error tracking)
- Captures all Python exceptions
- Stack traces with context
- Groups similar errors
- Free 5,000 errors/month
- Setup:
  ```bash
  pip install sentry-sdk
  ```
  Add to `main.py`:
  ```python
  import sentry_sdk
  sentry_sdk.init(dsn="YOUR_DSN", environment=settings.ENVIRONMENT)
  ```

### 4. Grafana Cloud (Free - dashboards)
- Build custom dashboards
- 10,000 series free
- Connect to Railway metrics
- Setup at: grafana.com/products/cloud/

---

## Key Metrics to Monitor

### Application Health
- `/health` endpoint: must return status `healthy` or HTTP 200
- Response time: should be < 500ms
- Error rate: should be < 1%

### Database Health
- Connection pool usage
- Query response times
- Number of active connections

### Agent Health
- Last successful run time for each agent
- Number of issues processed per run
- Error count per agent

### ML Health
- Models loaded count
- Inference time per request
- Fallback usage rate

---

## Alert Rules

### Critical (immediate action needed)
- `/health` returns non-200 → Platform is down
- Database connection fails → All features broken
- Error rate > 10% → Major bug in production

### Warning (investigate soon)
- Response time > 2 seconds → Performance issue
- Agent not run in 2x its scheduled interval → Agent crashed
- ML models < 4/6 loaded → AI features degraded

---

## Log Monitoring

Railway logs are accessible at:
`railway.app → your service → Logs`

Search for these patterns:
- `"ERROR"` → something is broken
- `"SLOW REQUEST"` → performance issues
- `"Agent ... failed"` → agent problems
- `"Migration FAILED"` → database issues
