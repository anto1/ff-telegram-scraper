#!/bin/bash
# Telegram Authentication Script for Railway
# App URL: https://ff-telegram-scraper-production.up.railway.app

APP_URL="https://ff-telegram-scraper-production.up.railway.app"

echo "🔐 Telegram Authentication for Railway"
echo "========================================"
echo ""

# Step 1: Check current status
echo "Step 1: Checking authentication status..."
STATUS=$(curl -s "${APP_URL}/auth/status")
echo "$STATUS" | jq '.'
echo ""

# Check if already authenticated
if echo "$STATUS" | jq -e '.authenticated == true' > /dev/null 2>&1; then
    echo "✅ Already authenticated!"
    echo "$STATUS" | jq '.user'
    exit 0
fi

echo "❌ Not authenticated. Starting authentication process..."
echo ""

# Step 2: Start authentication
read -p "Enter your phone number (with country code, e.g., +1234567890): " PHONE_NUMBER

echo ""
echo "Step 2: Sending verification code to ${PHONE_NUMBER}..."
RESPONSE=$(curl -s -X POST "${APP_URL}/auth/start" \
  -H "Content-Type: application/json" \
  -d "{\"phone_number\": \"${PHONE_NUMBER}\"}")

echo "$RESPONSE" | jq '.'

# Extract phone_code_hash
PHONE_CODE_HASH=$(echo "$RESPONSE" | jq -r '.phone_code_hash // empty')

if [ -z "$PHONE_CODE_HASH" ] || [ "$PHONE_CODE_HASH" == "null" ]; then
    echo "❌ Failed to get phone_code_hash. Check the error above."
    exit 1
fi

echo ""
echo "✅ Verification code sent! Check your Telegram app."
echo ""

# Step 3: Verify code
read -p "Enter the verification code from Telegram: " CODE

echo ""
echo "Step 3: Verifying code..."
VERIFY_RESPONSE=$(curl -s -X POST "${APP_URL}/auth/verify" \
  -H "Content-Type: application/json" \
  -d "{
    \"phone_number\": \"${PHONE_NUMBER}\",
    \"code\": \"${CODE}\",
    \"phone_code_hash\": \"${PHONE_CODE_HASH}\"
  }")

echo "$VERIFY_RESPONSE" | jq '.'

# Check if successful
if echo "$VERIFY_RESPONSE" | jq -e '.success == true' > /dev/null 2>&1; then
    echo ""
    echo "✅ Authentication successful!"
    echo ""
    echo "User info:"
    echo "$VERIFY_RESPONSE" | jq '.user_info'
    
    # Final status check
    echo ""
    echo "Final status check:"
    curl -s "${APP_URL}/auth/status" | jq '.'
else
    echo ""
    echo "❌ Authentication failed. Check the error above."
    exit 1
fi

