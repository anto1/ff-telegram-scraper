# Fix SESSION_REVOKED Error on Railway

## Problem
You're getting `SESSION_REVOKED` errors because the Telegram session file on Railway is invalid or expired.

## Solution

I've added a new `/auth/reset` endpoint to fix this. Here's how to use it:

### Step 1: Reset the Session

Call the reset endpoint to delete the invalid session file:

```bash
curl -X POST https://ff-telegram-scraper-production.up.railway.app/auth/reset
```

Or use the Swagger UI:
1. Go to: https://ff-telegram-scraper-production.up.railway.app/docs
2. Find `POST /auth/reset` in the Authentication section
3. Click "Try it out" → "Execute"

### Step 2: Start Fresh Authentication

Now start the authentication process:

```bash
curl -X POST https://ff-telegram-scraper-production.up.railway.app/auth/start \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+447915940176"}'
```

**Response:**
```json
{
  "success": true,
  "message": "Verification code sent to +447915940176",
  "phone_code_hash": "abc123..."
}
```

**Save the `phone_code_hash`!**

### Step 3: Verify the Code

Check your Telegram for the verification code, then:

```bash
curl -X POST https://ff-telegram-scraper-production.up.railway.app/auth/verify \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+447915940176",
    "code": "12345",
    "phone_code_hash": "paste_hash_from_step_2"
  }'
```

### Step 4: Verify Success

Check that authentication worked:

```bash
curl https://ff-telegram-scraper-production.up.railway.app/auth/status
```

You should see `"authenticated": true` ✅

## Using Swagger UI (Easier)

1. **Reset:** https://ff-telegram-scraper-production.up.railway.app/docs → `POST /auth/reset`
2. **Start:** `POST /auth/start` with your phone number
3. **Verify:** `POST /auth/verify` with code from Telegram
4. **Check:** `GET /auth/status` to confirm

## What Changed

I've updated the code to:
- ✅ Add `/auth/reset` endpoint to delete invalid sessions
- ✅ Auto-detect and handle `SESSION_REVOKED` errors
- ✅ Better error messages in `/auth/status`
- ✅ Improved error handling in `/auth/start`

## After Authentication

Once authenticated, the session file will be saved on Railway and persist between deployments. You can now:
- Use `/scrape` to scrape channels
- Use `/channels/import-subscriptions` to import your channels
- The scraper will automatically use the authenticated session

