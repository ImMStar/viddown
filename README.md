# Telegram Video Downloader Bot

Send a video link to the bot and it replies with the video file (up to 50 MB).
Built with python-telegram-bot and yt-dlp. Only download content you own or have
permission to save, and respect each site's terms.

## 1. Create the bot
1. Open Telegram, chat with @BotFather, send `/newbot`, and copy the token.
2. (Optional) Get your numeric user ID from @userinfobot to restrict the bot to you.

## 2. Run locally
```bash
pip install -r requirements.txt
export BOT_TOKEN="123456:ABC..."
export ALLOWED_USER_IDS="your_user_id"   # optional, comma-separated
python bot.py
```

## 3. Deploy on Render
1. Push this folder to a GitHub repo.
2. On Render: New > Background Worker > connect the repo (or use `render.yaml`).
3. Build command: `pip install -r requirements.txt`
   Start command: `python bot.py`
4. Add environment variable `BOT_TOKEN` (and optionally `ALLOWED_USER_IDS`).
5. Deploy. Note: Render's free tier does not offer background workers, so you
   need a paid worker, or switch to a Web Service with a small health endpoint.

## Settings (environment variables)
| Name | Default | Meaning |
|---|---|---|
| BOT_TOKEN | required | Token from BotFather |
| ALLOWED_USER_IDS | empty (everyone) | Comma-separated Telegram user IDs |
| MAX_MB | 50 | Max file size to send |
| MAX_PARALLEL | 2 | Simultaneous downloads |

## Keep yt-dlp updated
Sites change often. If downloads start failing, redeploy so `pip` pulls the
latest yt-dlp.
