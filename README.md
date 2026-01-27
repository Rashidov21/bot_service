# Bot Service (Telegram)

This service runs separately from Django and sends posts to your site via API.

## Setup

1. Create a virtualenv and install deps:

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Set environment variables (export or .env with python-dotenv):

```
TELEGRAM_BOT_TOKEN=123456:ABCDEF
BOT_API_TOKEN=your_api_token
API_BASE=https://pyblog.uz
TELEGRAM_CHANNEL_ID=@pybloguz
```

3. Run the bot:

```
python bot.py
```

## Commands

- `/new` start new post flow
- `/cancel` cancel current flow

## Notes

- Bot uses polling, so no webhook needed.
- The bot publishes to channel only if `TELEGRAM_CHANNEL_ID` is set.
