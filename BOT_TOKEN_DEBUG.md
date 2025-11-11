# Bot Token Debugging - Final Checklist

## The 401 Error Means ONE Thing: Invalid Token

If Discord returns `401 Unauthorized`, the token is **definitely wrong**. No exceptions.

## Final Verification Steps

### 1. Verify Token in Discord Developer Portal

**Go to:** https://discord.com/developers/applications

**Check:**
- ✅ Your application exists
- ✅ Bot section shows a bot user
- ✅ Token field shows a token (click "Reset Token" if you need to see it)
- ✅ **MESSAGE CONTENT INTENT** is enabled
- ✅ **SERVER MEMBERS INTENT** is enabled

### 2. Copy Token EXACTLY

**When copying the token:**
- Copy the ENTIRE token (all 3 parts separated by dots)
- NO spaces before or after
- NO quotes
- NO line breaks

**Token format:** `XXXX.XXXX.XXXX` (about 72 characters total)

### 3. Update config.json

**File location:** Root `config.json` (same folder as `docker/`, `backend/`, etc.)

**Format:**
```json
{
  "discord_token": "PASTE_TOKEN_HERE_WITH_NO_SPACES",
  ...
}
```

### 4. Verify Docker is Reading It

```bash
# Check what Docker sees
docker compose -f docker/docker-compose.yml exec bot cat /app/config.json

# Check bot logs
docker compose -f docker/docker-compose.yml logs bot | grep -i token
```

### 5. Common Mistakes

❌ **Wrong token type:**
- Using Client Secret instead of Bot Token
- Using Application ID instead of Bot Token
- Using OAuth2 token instead of Bot Token

❌ **Token was reset:**
- If you reset the token in Discord, the old one is invalid
- You MUST use the NEW token

❌ **Token exposed:**
- If token was in a public repo, Discord may have invalidated it
- Reset it in Discord Developer Portal

❌ **Bot not enabled:**
- Make sure the bot user exists in your application
- Click "Add Bot" if you haven't

### 6. Test Token Directly

You can test if a token is valid using Discord's API:

```bash
# Replace YOUR_TOKEN with your actual token
curl -H "Authorization: Bot YOUR_TOKEN" https://discord.com/api/v10/users/@me
```

If you get `{"id": "...", "username": "..."}`, the token is valid.
If you get `{"message": "401: Unauthorized"}`, the token is invalid.

## If Still Not Working

1. **Reset token in Discord Developer Portal** (even if you think it's correct)
2. **Copy the NEW token immediately**
3. **Update config.json** with the new token
4. **Rebuild bot container:**
   ```bash
   docker compose -f docker/docker-compose.yml build --no-cache bot
   docker compose -f docker/docker-compose.yml up -d bot
   ```
5. **Check logs:**
   ```bash
   docker compose -f docker/docker-compose.yml logs bot -f
   ```

## The Truth

If Discord returns 401, the token is wrong. Period. There's no other explanation. The bot code is correct, Docker is correct, the issue is 100% the token value.

