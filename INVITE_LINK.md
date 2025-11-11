# Complete Discord Bot Invite Link

## Your Bot Invite Link

**Application ID:** `1437602027063738548`

### Complete Invite URL (Guild Install):

```
https://discord.com/oauth2/authorize?client_id=1437602027063738548&permissions=2147832064&scope=bot%20applications.commands&integration_type=0
```

### What Each Parameter Does:

- `client_id=1437602027063738548` - Your Application ID
- `permissions=2147832064` - All required bot permissions
- `scope=bot%20applications.commands` - Bot scope + slash commands
- `integration_type=0` - **Guild Install** (server install, not DM install)

### Alternative: Without integration_type

If the above doesn't work, try this simpler version:

```
https://discord.com/oauth2/authorize?client_id=1437602027063738548&permissions=2147832064&scope=bot%20applications.commands
```

## How to Use

1. Copy one of the URLs above
2. Paste in your browser
3. Select your Discord server
4. Click "Authorize"
5. Bot will join your server!

## Permissions Included

- Send Messages
- Embed Links  
- Attach Files
- Read Message History
- Use Slash Commands
- Mention Everyone
- Use External Emojis

## Troubleshooting

If the scope won't change:
1. Make sure you're using the **complete URL** with all parameters
2. Try the version with `integration_type=0` first
3. If that doesn't work, try without `integration_type=0`
4. Clear your browser cache and try again
5. Try in an incognito/private window

