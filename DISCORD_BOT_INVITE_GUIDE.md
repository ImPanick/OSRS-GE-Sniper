# Discord Bot Invite Link - Step by Step

**Note:** Discord has removed the OAuth2 URL Generator from their interface. You must now manually construct the invite URL using the method below.

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
https://discord.com/oauth2/authorize?client_id=YOUR_APPLICATION_ID&permissions=2147832064&scope=bot%20applications.commands
```

**Example:** If your Application ID is `123456789012345678`, your URL would be:
```
https://discord.com/oauth2/authorize?client_id=123456789012345678&permissions=2147832064&scope=bot%20applications.commands
```

### Step 4: Use the URL

1. Copy the complete URL (with your Application ID)
2. Paste it in your browser
3. Select your Discord server
4. Click "Authorize"

---

## Alternative: Use Online Permission Calculator

If you want a visual tool to help generate the URL:

1. Go to https://discordapi.com/permissions.html
2. Select the permissions you need (or use the preset)
3. Enter your Application ID
4. Copy the generated URL

This is helpful if you want to customize permissions or see what each permission does.

---

## About Webhooks

**Webhooks are OPTIONAL** and can be set up AFTER the bot is invited. You don't need them to invite the bot. You can:
1. Invite the bot first (using the URL above)
2. Then create webhooks later if you want backend notifications

