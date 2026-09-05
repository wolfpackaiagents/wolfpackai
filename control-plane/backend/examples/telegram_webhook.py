"""Configure Telegram with AMP after setting the TELEGRAM_* environment variables."""

import os
import urllib.parse
import urllib.request


amp_url = os.environ.get("AMP_URL", "http://127.0.0.1:8000").rstrip("/")
secret = os.environ["TELEGRAM_WEBHOOK_SECRET"]
token = os.environ["TELEGRAM_BOT_TOKEN"]
webhook_url = f"{amp_url}/api/public/channels/telegram/webhook"
payload = urllib.parse.urlencode({"url": webhook_url, "secret_token": secret}).encode()
request = urllib.request.Request(f"https://api.telegram.org/bot{token}/setWebhook", data=payload, method="POST")
with urllib.request.urlopen(request, timeout=10) as response:
    print(response.read().decode())
