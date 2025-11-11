# Discord Bot Token Troubleshooting

## Current Status
- ✅ Token is being read correctly (72 characters)
- ✅ No whitespace issues
- ❌ Discord returns 401 Unauthorized (token is invalid)

## How to Fix

### Step 1: Verify Token in Discord Developer Portal

1. **Go to Discord Developer Portal**
   - Visit: https://discord.com/developers/applications
   - Log in with your Discord account

2. **Select Your Application**
   - Click on your bot application (e.g., "OSRS Sniper")

3. **Go to Bot Section**
   - Click "Bot" in the left sidebar

4. **Check the Token**
   - Look at the "Token" field
   - **DO NOT** click "Reset Token" yet (unless you need to)
   - Compare the token shown with what's in your `config.json`

### Step 2: Common Issues

#### Issue 1: Token Was Reset
If you clicked "Reset Token" in the Developer Portal, the old token is invalid. You need to:
- Copy the NEW token from the Developer Portal
- Update `config.json` with the new token
- Restart the bot: `docker compose restart bot`

#### Issue 2: Wrong Token Type
Make sure you're using the **Bot Token**, not:
- ❌ Client Secret (different section)
- ❌ Application ID (different number)
- ✅ Bot Token (from Bot section)

#### Issue 3: Token Exposed/Compromised
If your token was exposed publicly (e.g., committed to GitHub), Discord may have invalidated it. You need to:
- Click "Reset Token" in Developer Portal
- Copy the new token
- Update `config.json`
- Restart bot

#### Issue 4: Token Format Issues
The token should:
- Be exactly as shown in Developer Portal (no quotes, no spaces)
- Have 3 parts separated by dots: `XXXX.XXXX.XXXX`
- Be 50-72 characters total

### Step 3: Reset Token (If Needed)

If the token doesn't match or you're unsure:

1. **In Discord Developer Portal → Bot Section**
2. **Click "Reset Token"**
3. **Click "Yes, do it!" to confirm**
4. **Copy the NEW token immediately** (you can only see it once!)
5. **Update `config.json`**:
   ```json
   {
     "discord_token": "NEW_TOKEN_HERE",
     ...
   }
   ```
6. **Restart the bot**:
   ```bash
   docker compose restart bot
   docker compose logs bot -f
   ```

### Step 4: Verify Bot Settings

While in the Bot section, also verify:
- ✅ **MESSAGE CONTENT INTENT** is enabled
- ✅ **SERVER MEMBERS INTENT** is enabled
- ✅ Bot is not set to "Public Bot" (unless you want it public)

### Step 5: Test the Token

After updating the token, check the logs:
```bash
docker compose logs bot -f
```

You should see:
- `[BOT] Token found: MTQzNzYwM...XXXXX (length: XX)`
- `[BOT] Attempting to connect with token: ...`
- `YourBotName ONLINE` (if successful)

If you still get 401 errors, the token is definitely invalid and needs to be reset.

## Security Note

⚠️ **NEVER** share your bot token publicly or commit it to GitHub!
- If your token is in a public repository, reset it immediately
- Add `config.json` to `.gitignore` if not already there
- Use `config.json.example` for version control

