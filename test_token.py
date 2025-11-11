#!/usr/bin/env python3
"""
Quick script to test if a Discord bot token is valid
Run this OUTSIDE Docker to verify your token works
"""
import requests
import sys

if len(sys.argv) < 2:
    print("Usage: python test_token.py YOUR_BOT_TOKEN")
    print("Example: python test_token.py MTQzNzYwMjAyNzA2MzczODU0OA.GiUyRH.Bxt8_Q6sd9IWo7mvQVvKxb0_wJtCBsllnYW8R4")
    sys.exit(1)

token = sys.argv[1].strip()

print(f"Testing token: {token[:10]}...{token[-10:]}")
print(f"Token length: {len(token)}")

headers = {
    "Authorization": f"Bot {token}"
}

try:
    response = requests.get("https://discord.com/api/v10/users/@me", headers=headers, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        print("✅ TOKEN IS VALID!")
        print(f"Bot username: {data.get('username')}")
        print(f"Bot ID: {data.get('id')}")
        print("\nThis token should work in your bot. If it doesn't, check:")
        print("1. Bot intents are enabled in Discord Developer Portal")
        print("2. config.json is being read correctly by Docker")
        print("3. No encoding/whitespace issues")
    elif response.status_code == 401:
        print("❌ TOKEN IS INVALID (401 Unauthorized)")
        print("\nThis means:")
        print("- Token was reset in Discord Developer Portal")
        print("- Token was exposed and Discord invalidated it")
        print("- Wrong token type (using Client Secret instead of Bot Token)")
        print("- Token copied incorrectly")
        print("\nFix:")
        print("1. Go to https://discord.com/developers/applications")
        print("2. Select your application → Bot section")
        print("3. Click 'Reset Token'")
        print("4. Copy the NEW token")
        print("5. Update config.json")
    else:
        print(f"❌ Unexpected error: {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"❌ Error testing token: {e}")

