# Discord Bot Invite Link - Step by Step

## Quick Method: Manual URL Construction

If you can't find the "URL Generator" in OAuth2, you can manually create the invite URL.

### Step 1: Get Your Application ID

1. Go to https://discord.com/developers/applications
2. Click on your application ("OSRS Sniper")
3. In the left sidebar, click **"General Information"**
4. Copy your **Application ID** (it's a long number, like `123456789012345678`)

### Step 2: Calculate Permissions

The permissions you need are:
- Send Messages (512)
- Embed Links (16384)
- Attach Files (32768)
- Read Message History (65536)
- Use Slash Commands (2147483648)
- Mention Everyone (131072)
- Use External Emojis (262144)

**Total Permission Value:** `512 + 16384 + 32768 + 65536 + 2147483648 + 131072 + 262144 = 2147832064`

### Step 3: Construct the Invite URL

Replace `YOUR_APPLICATION_ID` with your actual Application ID:

```
https://discord.com/api/oauth2/authorize?client_id=YOUR_APPLICATION_ID&permissions=2147832064&scope=bot%20applications.commands
```

### Step 4: Use the URL

1. Copy the complete URL (with your Application ID)
2. Paste it in your browser
3. Select your Discord server
4. Click "Authorize"

---

## Alternative: Finding URL Generator in Discord UI

The URL Generator location may vary. Try these locations:

1. **OAuth2 → URL Generator** (if visible in sidebar)
2. **OAuth2 → General** (scroll down, might be at bottom)
3. **OAuth2 → Redirects** (sometimes the generator is here)
4. Look for a button/tab that says "URL Generator" or "Invite Link"

If you still can't find it, use the manual method above - it works exactly the same!

---

## About Webhooks

**Webhooks are OPTIONAL** and can be set up AFTER the bot is invited. You don't need them to invite the bot. You can:
1. Invite the bot first (using the URL above)
2. Then create webhooks later if you want backend notifications

