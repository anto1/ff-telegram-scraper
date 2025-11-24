# Telegram Scraper - Railway Deployment Guide

## Overview

This is a FastAPI-based Telegram channel scraper service with PostgreSQL database, ready for deployment on Railway.

## Features

- 🔌 **REST API** for managing Telegram channels (CRUD operations)
- 📊 **Statistics endpoints** for channel analytics
- 🗄️ **PostgreSQL database** for storing channels and scraped messages
- 📡 **Telegram scraper** that reads active channels from database
- 🚀 **Railway-ready** with environment variable configuration

## Project Structure

```
.
├── main.py              # FastAPI application (API endpoints)
├── db.py                # Database configuration and session management
├── models.py            # SQLAlchemy ORM models
├── schemas.py           # Pydantic request/response schemas
├── scraper.py           # Telegram scraper with DB integration
├── parser.py            # Original scraper (kept for reference)
├── requirements.txt     # Python dependencies
├── Procfile             # Railway process configuration
├── railway.json         # Railway deployment configuration
└── env.example          # Environment variables template
```

## Database Schema

### `telegram_channels` table
- `id` - Primary key
- `title` - Channel name
- `username` - Telegram @username (optional)
- `channel_id` - Telegram channel ID (unique, required)
- `is_active` - Whether to scrape this channel
- `created_at`, `updated_at` - Timestamps
- `last_scraped_at` - Last successful scrape
- `notes` - Optional notes

### `telegram_messages` table
- `id` - Primary key
- `channel_id` - Foreign key to telegram_channels
- `message_id` - Telegram message ID
- `date` - Message post date
- `text` - Message content
- `views`, `forwards`, `replies` - Engagement metrics
- `total_reactions` - Free reactions count (excludes paid)
- `engagement_count`, `engagement_rate` - Calculated metrics
- `post_length` - Character count
- `raw_json` - Optional full message data
- `created_at` - When we saved it

Indexes on: `channel_id`, `message_id`, `date`, `engagement_rate`, `engagement_count`

## API Endpoints

### Health Check
- `GET /` - Basic health check
- `GET /health` - Health check with DB connectivity test

### Channels Management
- `GET /channels` - List all channels (with pagination)
- `GET /channels/with-stats` - List channels with statistics
- `GET /channels/{id}` - Get specific channel
- `POST /channels` - Create new channel
- `PATCH /channels/{id}` - Update channel
- `DELETE /channels/{id}` - Soft delete (set is_active=false)
- `DELETE /channels/{id}/hard` - Hard delete (remove from DB)

### Messages
- `GET /channels/{id}/messages` - Get messages for a channel (with sorting/pagination)

### Statistics
- `GET /stats/global` - Global statistics
- `GET /stats/channels` - Detailed stats for all channels

### Scraper
- `POST /scrape` - Trigger scraping (see note below)

**Note**: The `/scrape` endpoint is currently a placeholder. For production, you should run `scraper.py` as a separate scheduled job (cron job, Railway scheduled task, or background worker).

## Local Development

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Copy `env.example` to `.env` and fill in your credentials:

```bash
cp env.example .env
```

Required variables:
- `API_ID` - Get from https://my.telegram.org/apps
- `API_HASH` - Get from https://my.telegram.org/apps
- `DATABASE_URL` - PostgreSQL connection string

### 3. Set Up Local Database

For local development, you can use PostgreSQL in Docker:

```bash
docker run -d \
  --name telegram-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=telegram_scraper \
  -p 5432:5432 \
  postgres:15
```

Update `.env`:
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/telegram_scraper
```

### 4. Run the API Server

```bash
python main.py
```

Or with uvicorn directly:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API documentation will be available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 5. Add Channels via API

Use the API to add channels:

```bash
curl -X POST http://localhost:8000/channels \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Poker News",
    "channel_id": -1001213573012,
    "username": "pokerok",
    "is_active": true,
    "notes": "Main poker news channel"
  }'
```

### 6. Run the Scraper

First, authenticate with Telegram (one-time):

```bash
python scraper.py
```

This will prompt for your phone number and verification code. After authentication, it will create a `telegram_session.session` file.

Subsequent runs will use the saved session:

```bash
python scraper.py
```

## Railway Deployment

### 1. Create Railway Project

1. Go to [Railway.app](https://railway.app/)
2. Create a new project
3. Choose "Deploy from GitHub repo" and select your repository

### 2. Add PostgreSQL Database

1. In your Railway project, click "New"
2. Select "Database" → "PostgreSQL"
3. Railway will automatically set the `DATABASE_URL` environment variable

### 3. Configure Environment Variables

In Railway project settings, add these variables:

```
API_ID=your_api_id
API_HASH=your_api_hash
```

Railway automatically provides:
- `DATABASE_URL` (from Postgres addon)
- `PORT` (for the web service)

### 4. Deploy

Railway will automatically:
1. Detect Python project
2. Install dependencies from `requirements.txt`
3. Run the command from `Procfile`: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Create database tables on first startup

### 5. Telegram Session Authentication

**Important**: The Telegram session requires interactive authentication (phone + code). You have two options:

**Option A: Authenticate Locally First**
1. Run `python scraper.py` locally
2. Complete authentication (phone + verification code)
3. This creates `telegram_session.session` file
4. Add this file to your repository (or upload to Railway)
5. Redeploy

**Option B: Use Telegram Bot Token** (Alternative)
If you want to avoid session files, you can use a Telegram Bot instead:
1. Create a bot via @BotFather
2. Add bot to your channels as admin
3. Modify scraper to use bot token instead of user session

### 6. Set Up Scheduled Scraping

Railway doesn't have built-in cron jobs. Options:

**Option A: External Cron Service**
Use a service like [cron-job.org](https://cron-job.org/) or [EasyCron](https://www.easycron.com/) to call:
```
POST https://your-app.railway.app/scrape
```

**Option B: Railway Scheduled Job** (if available in your plan)
Create a separate service that runs `python scraper.py` on a schedule.

**Option C: GitHub Actions**
Use GitHub Actions to trigger scraping:

```yaml
# .github/workflows/scrape.yml
name: Scrape Telegram Channels
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:  # Manual trigger

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python scraper.py
        env:
          API_ID: ${{ secrets.API_ID }}
          API_HASH: ${{ secrets.API_HASH }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

## Database Migrations (Optional)

For production, consider using Alembic for database migrations:

```bash
pip install alembic
alembic init alembic
```

Then configure `alembic/env.py` to use your async engine and models.

## Testing the API

Once deployed, your API will be available at: `https://your-app.railway.app`

Test endpoints:
```bash
# Health check
curl https://your-app.railway.app/health

# List channels
curl https://your-app.railway.app/channels

# Get stats
curl https://your-app.railway.app/stats/global

# View API docs
https://your-app.railway.app/docs
```

## Monitoring

Railway provides:
- **Logs**: View application logs in Railway dashboard
- **Metrics**: CPU, memory, and network usage
- **Deployments**: Track deployment history

For database monitoring:
```sql
-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check message count by channel
SELECT 
    c.title,
    COUNT(m.id) as message_count,
    MAX(m.date) as latest_message
FROM telegram_channels c
LEFT JOIN telegram_messages m ON c.id = m.channel_id
GROUP BY c.id, c.title
ORDER BY message_count DESC;
```

## Troubleshooting

### Database Connection Issues
- Verify `DATABASE_URL` is set correctly
- Check if it uses `postgresql+asyncpg://` scheme (not `postgres://`)
- Ensure Railway Postgres addon is running

### Telegram Authentication Issues
- Ensure `telegram_session.session` file exists
- Check `API_ID` and `API_HASH` are correct
- Try re-authenticating locally and uploading new session file

### Memory Issues on Railway
- Reduce scraping `limit` (default 200 messages per channel)
- Process channels in smaller batches
- Consider upgrading Railway plan

### Rate Limiting
- Telegram has rate limits for API calls
- Add delays between channel scraping if needed
- Consider reducing scraping frequency

## Security Considerations

1. **Environment Variables**: Never commit `.env` file or credentials
2. **Session Files**: Keep `telegram_session.session` secure (it gives full account access)
3. **API Authentication**: Consider adding API authentication for production
4. **CORS**: Update CORS origins in `main.py` for production
5. **Admin Endpoints**: Protect `/scrape` endpoint if exposed publicly

## Next Steps

1. Add API authentication (JWT, API keys)
2. Implement background job queue (Celery, RQ)
3. Add more advanced analytics endpoints
4. Set up automated testing
5. Add monitoring and alerting
6. Implement rate limiting
7. Add data export features (CSV, JSON)

## Support

For issues or questions:
- Check Railway documentation: https://docs.railway.app/
- Review FastAPI docs: https://fastapi.tiangolo.com/
- Telethon documentation: https://docs.telethon.dev/

## License

[Your License Here]

