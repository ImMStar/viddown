import asyncio
import logging
import os
import re
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import yt_dlp
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO
)
log = logging.getLogger("videobot")

BOT_TOKEN = os.environ["BOT_TOKEN"]
# Telegram Bot API upload limit is 50 MB for bots using the cloud API.
MAX_BYTES = int(os.environ.get("MAX_MB", "50")) * 1024 * 1024
# Optional: comma-separated Telegram user IDs allowed to use the bot. Empty = everyone.
ALLOWED = {int(x) for x in os.environ.get("ALLOWED_USER_IDS", "").split(",") if x.strip()}
# Max simultaneous downloads, so a free Render instance is not overwhelmed.
SEM = asyncio.Semaphore(int(os.environ.get("MAX_PARALLEL", "2")))

URL_RE = re.compile(r"https?://\S+")

WELCOME = (
    "Send me a video link and I'll try to download it for you.\n\n"
    "Only download content you own or have permission to save. "
    "Some sites aren't supported, and files over "
    f"{MAX_BYTES // (1024 * 1024)} MB can't be sent through Telegram."
)


# ---------- tiny health server (keeps Render Web Service happy) ----------
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def run_health():
    port = int(os.environ.get("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), Health).serve_forever()


# ---------- bot logic ----------
def allowed(update: Update) -> bool:
    if not ALLOWED:
        return True
    user = update.effective_user
    return bool(user and user.id in ALLOWED)


def download(url: str, out_dir: str) -> Path:
    opts = {
        "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
        # Prefer a single mp4 under the size limit; fall back to the best small format.
        "format": f"best[ext=mp4][filesize<{MAX_BYTES}]/best[filesize<{MAX_BYTES}]/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_BYTES,
        "socket_timeout": 30,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = Path(ydl.prepare_filename(info))
    if not path.exists():
        # yt-dlp may have merged into a different extension
        matches = list(Path(out_dir).glob(f"{info['id']}.*"))
        if not matches:
            raise FileNotFoundError("Download finished but no file was found.")
        path = matches[0]
    return path


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    await update.message.reply_text(WELCOME)


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        await update.message.reply_text("Sorry, this bot is private.")
        return

    match = URL_RE.search(update.message.text or "")
    if not match:
        await update.message.reply_text("Please send a valid video link.")
        return
    url = match.group(0)

    status = await update.message.reply_text("Working on it...")
    async with SEM:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                await update.message.chat.send_action(ChatAction.UPLOAD_VIDEO)
                path = await asyncio.to_thread(download, url, tmp)

                size = path.stat().st_size
                if size > MAX_BYTES:
                    await status.edit_text(
                        "That video is larger than Telegram allows bots to send."
                    )
                    return

                with open(path, "rb") as f:
                    await update.message.reply_video(
                        video=f,
                        supports_streaming=True,
                        read_timeout=120,
                        write_timeout=120,
                    )
                await status.delete()
            except yt_dlp.utils.DownloadError as e:
                log.warning("Download failed for %s: %s", url, e)
                await status.edit_text(
                    "I couldn't download that link. It may be unsupported, private, "
                    "or too large."
                )
            except Exception:
                log.exception("Unexpected error")
                await status.edit_text("Something went wrong. Please try again later.")


def main():
    threading.Thread(target=run_health, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    log.info("Bot started (polling)")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
