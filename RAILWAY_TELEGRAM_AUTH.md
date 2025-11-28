# Authenticating Telegram on Railway

This guide shows you how to authenticate your Telegram account on Railway using the API endpoints.

## Prerequisites

1. Your Railway app must be deployed and running
2. You need your Railway app URL (e.g., `https://your-app.railway.app`)
3. Environment variables must be set in Railway:
   - `API_ID` - Your Telegram API ID
   - `API_HASH` - Your Telegram API Hash

## Step-by-Step Authentication

### Step 1: Check Current Authentication Status

First, check if you're already authenticated:

```bash
curl https://your-app.railway.app/auth/status
```

If you see `"authenticated": true`, you're already authenticated! ✅

### Step 2: Start Authentication

Send a request to start authentication. This will send a verification code to your Telegram:

```bash
curl -X POST https://your-app.railway.app/auth/start \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+1234567890"
  }'
```

**Important:** Use international format with country code (e.g., `+1234567890`)

**Response:**
```json
{
  "success": true,
  "message": "Verification code sent to +1234567890",
  "phone_code_hash": "abc123def456..."
}
```

**Save the `phone_code_hash`** - you'll need it in the next step!

### Step 3: Verify the Code

Check your Telegram app for the verification code, then verify it:

```bash
curl -X POST https://your-app.railway.app/auth/verify \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+1234567890",
    "code": "12345",
    "phone_code_hash": "abc123def456..."
  }'
```

Replace:
- `+1234567890` with your phone number
- `12345` with the code you received
- `abc123def456...` with the `phone_code_hash` from Step 2

**Response:**
```json
{
  "success": true,
  "message": "Successfully authenticated as Your Name",
  "user_info": {
    "id": 123456789,
    "first_name": "Your",
    "last_name": "Name",
    "username": "yourusername",
    "phone": "+1234567890"
  }
}
```

### Step 4: Verify Authentication

Check that authentication was successful:

```bash
curl https://your-app.railway.app/auth/status
```

You should see:
```json
{
  "authenticated": true,
  "user": {
    "id": 123456789,
    "first_name": "Your",
    "last_name": "Name",
    "username": "yourusername",
    "phone": "+1234567890"
  }
}
```

## Using the Swagger UI (Easier Method)

1. Open your Railway app's Swagger UI:
   ```
   https://your-app.railway.app/docs
   ```

2. Find the **"Authentication"** section

3. Click on `POST /auth/start` → **"Try it out"**
   - Enter your phone number (e.g., `+1234567890`)
   - Click **"Execute"**
   - Copy the `phone_code_hash` from the response

4. Check your Telegram for the verification code

5. Click on `POST /auth/verify` → **"Try it out"**
   - Enter your phone number
   - Enter the code from Telegram
   - Paste the `phone_code_hash` from Step 3
   - Click **"Execute"**

6. Verify with `GET /auth/status` → **"Try it out"** → **"Execute"**

## Troubleshooting

### "Failed to send verification code"
- Check that `API_ID` and `API_HASH` are set correctly in Railway
- Verify your phone number format (must include country code)
- Check Railway logs for detailed error messages

### "Failed to verify code"
- Make sure you're using the correct `phone_code_hash` from Step 2
- Codes expire after a few minutes - request a new one if needed
- Check that the code you entered is correct

### "Session invalid or expired"
- The session file may have been lost or corrupted
- Re-authenticate using the steps above
- Check Railway logs to see if the session file is being created

### Session File Location on Railway

The session file (`telegram_session.session`) is stored in the Railway service's filesystem. It persists between deployments as long as the service isn't deleted.

**Important:** If you delete and recreate the Railway service, you'll need to re-authenticate.

## Alternative: Authenticate Locally and Upload Session

If the API method doesn't work, you can authenticate locally and upload the session file:

### 1. Authenticate Locally

```bash
# Make sure you have .env file with API_ID and API_HASH
python scraper.py
```

Enter your phone number and verification code when prompted. This creates `telegram_session.session`.

### 2. Upload to Railway

**Option A: Using Railway CLI**
```bash
# Install Railway CLI if you haven't
npm i -g @railway/cli

# Login to Railway
railway login

# Link to your project
railway link

# Upload the session file
railway run --service your-service-name -- cat telegram_session.session > telegram_session.session
```

**Option B: Add to Git (Not Recommended for Production)**
```bash
# Add session file to git
git add telegram_session.session
git commit -m "Add Telegram session"
git push

# Railway will redeploy with the session file
```

⚠️ **Warning:** Adding session files to Git is a security risk. Only do this if you're okay with the session being in your repository.

## After Authentication

Once authenticated, the session file is saved on Railway and will persist. You can now:

- Use the `/scrape` endpoint to scrape channels
- Use `/channels/import-subscriptions` to import your subscribed channels
- The scraper will automatically use the authenticated session

## Security Notes

- The session file gives full access to your Telegram account
- Keep your Railway project secure
- Don't share your session file
- If compromised, revoke all sessions in Telegram settings

