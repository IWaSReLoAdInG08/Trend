import requests

# Your bot token
BOT_TOKEN = "8517691339:AAGlGQaf3QmxTthT6ghwLkz0Beo09n3e9hE"

# Get updates to find your chat ID
url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
response = requests.get(url)
data = response.json()

if data.get("result"):
    for update in data["result"]:
        if "message" in update:
            chat_id = update["message"]["chat"]["id"]
            print(f"Your Chat ID is: {chat_id}")
            print(f"\nSet it with: $env:TELEGRAM_CHAT_ID=\"{chat_id}\"")
            break
else:
    print("No messages found yet!")
    print("\n⚠️ IMPORTANT: First send ANY message to your bot at https://t.me/trend_08_bot")
    print("Then run this script again to get your Chat ID.")
