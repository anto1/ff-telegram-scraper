# Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment

Copy the example environment file:

```bash
cp env.example .env
```

Edit `.env` and add your credentials:
- Get `API_ID` and `API_HASH` from https://my.telegram.org/apps
- Set `DATABASE_URL` to your PostgreSQL connection string

### 3. Start PostgreSQL (Local Development)

**Option A: Using Docker**
```bash
docker run -d --name telegram-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=telegram_scraper \
  -p 5432:5432 \
  postgres:15
```

**Option B: Use existing PostgreSQL**
Just update `DATABASE_URL` in `.env`

### 4. Run the API Server

```bash
python main.py
```

The API will start on http://localhost:8000

- **Swagger Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 5. Add Your First Channel

Using curl:
```bash
curl -X POST http://localhost:8000/channels \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Poker News",
    "channel_id": -1001213573012,
    "username": "pokerok",
    "is_active": true
  }'
```

Or use the Swagger UI at http://localhost:8000/docs

### 6. Authenticate with Telegram

First run requires authentication:

```bash
python scraper.py
```

Enter your phone number and verification code when prompted.
This creates `telegram_session.session` for future runs.

### 7. Scrape Channels

After authentication:

```bash
python scraper.py
```

This will:
1. Read all active channels from database
2. Scrape latest 200 messages per channel
3. Save messages to database
4. Update `last_scraped_at` timestamp

## 📊 View Your Data

### API Endpoints

**List channels:**
```bash
curl http://localhost:8000/channels
```

**Get channel stats:**
```bash
curl http://localhost:8000/stats/channels
```

**View messages for a channel:**
```bash
curl http://localhost:8000/channels/1/messages
```

### Direct Database Access

```bash
# Connect to database
psql postgresql://postgres:postgres@localhost:5432/telegram_scraper

# View channels
SELECT id, title, is_active, last_scraped_at FROM telegram_channels;

# View message counts
SELECT c.title, COUNT(m.id) as messages 
FROM telegram_channels c 
LEFT JOIN telegram_messages m ON c.id = m.channel_id 
GROUP BY c.id, c.title;
```

## 🚂 Deploy to Railway

### Step 1: Push to GitHub

```bash
git add .
git commit -m "Add Telegram scraper service"
git push
```

### Step 2: Create Railway Project

1. Go to https://railway.app/
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your repository

### Step 3: Add PostgreSQL

1. In Railway project, click "New"
2. Select "Database" → "PostgreSQL"
3. Wait for database to provision

### Step 4: Set Environment Variables

In Railway project settings, add:
```
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
```

Railway automatically sets `DATABASE_URL` and `PORT`.

### Step 5: Deploy

Railway will automatically:
- Install dependencies
- Start the API server
- Create database tables

Your API will be live at: `https://your-app.railway.app`

### Step 6: Upload Telegram Session

**Important**: You need to authenticate with Telegram first.

**Option 1: Local Authentication**
1. Run `python scraper.py` locally
2. Complete authentication
3. Copy `telegram_session.session` to your repository
4. Commit and push
5. Railway will redeploy with the session file

**Option 2: Railway Shell** (if available)
1. Open Railway shell
2. Run `python scraper.py`
3. Complete authentication in the shell

### Step 7: Schedule Scraping

Use one of these approaches:

**GitHub Actions** (Recommended):

Create `.github/workflows/scrape.yml`:
```yaml
name: Scrape Channels
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:

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

**External Cron Service**:
- Use cron-job.org or similar
- Call `POST https://your-app.railway.app/scrape`

## 🛠️ Common Tasks

### Add Multiple Channels

```python
import requests

channels = [
    {"title": "Channel 1", "channel_id": -1001234567890, "is_active": True},
    {"title": "Channel 2", "channel_id": -1009876543210, "is_active": True},
]

for channel in channels:
    response = requests.post("http://localhost:8000/channels", json=channel)
    print(f"Added: {response.json()['title']}")
```

### Deactivate a Channel

```bash
curl -X PATCH http://localhost:8000/channels/1 \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

### Get Top Posts by Engagement

```bash
curl "http://localhost:8000/channels/1/messages?order_by=engagement_rate&limit=10"
```

### Check Database Size

```sql
SELECT 
    COUNT(*) as total_messages,
    MIN(date) as oldest,
    MAX(date) as newest,
    pg_size_pretty(pg_total_relation_size('telegram_messages')) as table_size
FROM telegram_messages;
```

## 🐛 Troubleshooting

**"Connection refused" error**
- Check if PostgreSQL is running: `docker ps`
- Verify `DATABASE_URL` in `.env`

**"No active channels found"**
- Add channels via API: `POST /channels`
- Verify `is_active=true` in database

**"Invalid phone number"**
- Use international format: `+1234567890`
- Include country code

**"Session file expired"**
- Delete `telegram_session.session`
- Run `python scraper.py` again
- Re-authenticate

## 📚 Next Steps

1. **Set up monitoring**: Add logging, error tracking (Sentry)
2. **Add authentication**: Protect API with JWT or API keys
3. **Schedule regular scraping**: Use cron or background jobs
4. **Build frontend**: Create a dashboard to view stats
5. **Add more analytics**: Implement trending posts, sentiment analysis
6. **Export data**: Add CSV/Excel export features

## 🆘 Need Help?

- Check `README_DEPLOYMENT.md` for detailed documentation
- Review API docs at http://localhost:8000/docs
- Check Railway logs for errors
- Verify environment variables are set correctly

Happy scraping! 🎉



