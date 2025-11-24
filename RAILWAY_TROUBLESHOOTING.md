# Railway Deployment Troubleshooting Guide

## ❌ Error: `ConnectionRefusedError: [Errno 111] Connection refused`

This error means your FastAPI app cannot connect to the PostgreSQL database. Follow these steps to fix it:

---

## 🔍 Step 1: Verify PostgreSQL Service Exists

1. Go to your **Railway Dashboard**: https://railway.app/dashboard
2. Click on your project
3. You should see **TWO services**:
   - **Web Service** (your FastAPI app) - usually named after your repo
   - **PostgreSQL** service

**If you only see ONE service:**
- Click **"+ New"** → **"Database"** → **"Add PostgreSQL"**
- Wait for it to provision (~1-2 minutes)

---

## 🔗 Step 2: Link Database to Web Service

Railway needs to know that your web service should have access to the database.

### Option A: Use Railway's Internal Network (Recommended)

1. In Railway Dashboard → Your **PostgreSQL** service → **Variables** tab
2. You'll see several variables including:
   - `PGHOST` (or `DATABASE_HOST`)
   - `PGUSER` (or `DATABASE_USER`)
   - `PGPASSWORD` (or `DATABASE_PASSWORD`)
   - `PGDATABASE` (or `DATABASE_NAME`)
   - `PGPORT` (or `DATABASE_PORT`)
   - `DATABASE_URL`

3. Copy the **full `DATABASE_URL`** value. It looks like:
   ```
   postgresql://postgres:password@postgres.railway.internal:5432/railway
   ```
   OR
   ```
   postgres://postgres:password@containers-us-west-123.railway.app:1234/railway
   ```

4. Go to your **Web Service** (FastAPI app) → **Variables** tab

5. Add a new variable:
   - **Name**: `DATABASE_URL`
   - **Value**: Paste the URL you copied
   
   **✅ The app will automatically convert `postgres://` or `postgresql://` to `postgresql+asyncpg://`**

### Option B: Use Railway Reference Variables

1. In your **Web Service** → **Variables** tab
2. Click **"+ New Variable"**
3. **Reference variable**:
   ```
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   ```
   (Replace `Postgres` with your actual PostgreSQL service name if different)

---

## 🔐 Step 3: Set Other Required Environment Variables

While you're in the **Web Service** → **Variables** tab, make sure these are set:

1. **`TELEGRAM_API_ID`**
   - Value: Your API ID from https://my.telegram.org
   - Example: `12345678`

2. **`TELEGRAM_API_HASH`**
   - Value: Your API hash from https://my.telegram.org
   - Example: `abcdef1234567890abcdef1234567890`

3. **`PORT`** (Usually auto-set by Railway)
   - If not set, add it with value: `8000`

---

## 🚀 Step 4: Redeploy

After setting the variables:

1. Railway should **automatically redeploy** your service
2. If not, click **"Deploy"** or **"Redeploy"** button
3. Watch the **Deployment Logs**:
   - Click on your **Web Service**
   - Go to **"Deployments"** tab
   - Click on the latest deployment
   - Watch for these success messages:
     ```
     📡 DATABASE_URL found: postgresql://...
     🔌 Attempting to connect to: ...
     🗄️  Initializing database...
     ✅ Database tables created/verified successfully!
     ✓ Telegram client started.
     🚀 Starting Telegram Scraper API...
     ```

---

## 🔍 Still Having Issues? Check These:

### Issue 1: "DATABASE_URL environment variable not set"

**Solution:**
- You didn't set the `DATABASE_URL` variable in Railway
- Go back to **Step 2** above

### Issue 2: "Connection refused" even with DATABASE_URL set

**Possible causes:**

1. **Wrong DATABASE_URL format**
   - ✅ Should be: `postgresql://...` or `postgres://...`
   - ❌ Should NOT be: `localhost`, `127.0.0.1`, or empty

2. **PostgreSQL service not running**
   - In Railway Dashboard → PostgreSQL service
   - Check if it shows as "Active" (green)
   - If not, it may still be provisioning

3. **Services in different projects**
   - Both services must be in the **same Railway project**
   - Check the project name at the top of the dashboard

4. **Network isolation**
   - Railway services in the same project can talk to each other by default
   - If you've modified networking settings, reset them

### Issue 3: "peer authentication failed" or "password authentication failed"

**Solution:**
- Your `DATABASE_URL` has the wrong credentials
- Get a fresh `DATABASE_URL` from PostgreSQL service variables
- Make sure you're using the internal URL (ends with `.railway.internal`) not the public one

---

## 🧪 Testing the Connection Locally

To ensure everything works before deploying:

1. Copy your Railway `DATABASE_URL` 
2. In your local `.env` file, set:
   ```env
   DATABASE_URL=postgresql+asyncpg://postgres:password@host:port/railway
   ```
3. Run locally:
   ```bash
   uvicorn main:app --reload
   ```
4. Visit http://localhost:8000/health
5. Should return: `{"status": "ok", "database": "connected"}`

---

## 📞 Need More Help?

If you're still stuck:

1. **Check Railway Logs:**
   - Dashboard → Web Service → Deployments → Latest → Build Logs & Deploy Logs
   - Look for error messages with ❌ or red text

2. **Check PostgreSQL Logs:**
   - Dashboard → PostgreSQL service → Logs
   - Look for connection attempts from your web service

3. **Verify DATABASE_URL format:**
   - In your Web Service logs, look for:
     ```
     📡 DATABASE_URL found: ...
     🔌 Attempting to connect to: ...
     ```
   - The host should be something like:
     - `postgres.railway.internal:5432` (internal - best)
     - `containers-us-west-xxx.railway.app:xxxx` (public)
   - Should NOT be:
     - `localhost`
     - `127.0.0.1`

4. **Railway Community:**
   - https://help.railway.app/
   - Discord: https://discord.gg/railway

---

## ✅ Success Checklist

- [ ] PostgreSQL service exists and is running (green status)
- [ ] Web service exists and has `DATABASE_URL` variable set
- [ ] `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` are set
- [ ] Deployment logs show "✅ Database tables created/verified successfully!"
- [ ] Visit your Railway app URL → should see: `{"message": "Telegram Scraper API is running!"}`
- [ ] Visit `https://your-app.railway.app/health` → should return database connected

---

## 🎯 Quick Fix Summary

**Most common solution:**

1. Railway Dashboard → **PostgreSQL service** → **Variables** → Copy `DATABASE_URL`
2. Railway Dashboard → **Web Service** → **Variables** → **+ New Variable**:
   - Name: `DATABASE_URL`
   - Value: [paste the URL you copied]
3. Save and wait for automatic redeployment
4. Check deployment logs for ✅ success messages

That's it! 🎉





