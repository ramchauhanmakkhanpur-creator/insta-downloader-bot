import logging
import requests
import asyncio
import os
import sqlite3
from datetime import datetime
from yt_dlp import YoutubeDL
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_BOT_TOKEN = '8645642370:AAFjiq8rkC0IfEhrd7je6vFurIwC7wBvweU'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====================== DATABASE ======================
def init_db():
    conn = sqlite3.connect('credits.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    credits INTEGER DEFAULT 0,
                    username TEXT,
                    welcome_bonus INTEGER DEFAULT 0,
                    last_updated TEXT)''')
    try: conn.execute("ALTER TABLE users ADD COLUMN welcome_bonus INTEGER DEFAULT 0")
    except: pass
    conn.commit()
    conn.close()

def get_credits(user_id): 
    conn = sqlite3.connect('credits.db')
    row = conn.execute("SELECT credits FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row[0] if row else 0

def has_received_welcome(user_id):
    conn = sqlite3.connect('credits.db')
    row = conn.execute("SELECT welcome_bonus FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row[0] == 1 if row else False

def add_credits(user_id, amount):
    conn = sqlite3.connect('credits.db')
    conn.execute("""INSERT INTO users (user_id, credits, welcome_bonus, last_updated) 
                    VALUES (?, ?, 1, ?) ON CONFLICT(user_id) DO UPDATE SET credits = credits + ?, last_updated = ?""",
                 (user_id, amount, datetime.now(), amount, datetime.now()))
    conn.commit()
    conn.close()

def deduct_credits(user_id):
    conn = sqlite3.connect('credits.db')
    conn.execute("UPDATE users SET credits = credits - 10 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# ====================== START & BUY ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not has_received_welcome(user_id):
        add_credits(user_id, 20)
        await update.message.reply_text("🚀 **20 FREE Credits** mil gaye!\nLink bhejo!")
    else:
        await update.message.reply_text(f"👋 Welcome back! Credits: {get_credits(user_id)}")

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    qr_path = os.path.join(script_dir, 'paytm_qr.jpg')
    if os.path.exists(qr_path):
        await update.message.reply_photo(photo=open(qr_path, 'rb'), caption="💳 ₹45 mein 1000 Credits\nScreenshot bhej do!")

async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    file = await update.message.photo[-1].get_file()
    os.makedirs("screenshots", exist_ok=True)
    await file.download_to_drive(f"screenshots/{user_id}_{int(datetime.now().timestamp())}.jpg")
    add_credits(user_id, 1000)
    await update.message.reply_text(f"✅ 1000 Credits add ho gaye!\nAb credits: {get_credits(user_id)}")

# ====================== IMPROVED DOWNLOAD (GIF + NO AUDIO FIX) ======================
async def download_zero_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id

    if 'instagram.com' not in url.lower():
        await update.message.reply_text("❌ Sirf Instagram link bhejo!")
        return

    if get_credits(user_id) < 10:
        await update.message.reply_text("⛔ Credits khatam!\n/buy type karo")
        return

    deduct_credits(user_id)
    status = await update.message.reply_text("⚡ TURANT DOWNLOAD SHURU...\nCredits left: " + str(get_credits(user_id)))

    success = False
    start_time = asyncio.get_event_loop().time()

    async def loading_loop():
        msgs = ["⚡ Fast server connect...", "⚡ Reel extract ho rahi hai...", "⚡ Almost ready 🔥", "⚡ Thoda aur wait 😊"]
        i = 0
        while asyncio.get_event_loop().time() - start_time < 75:
            if success: break
            try: await status.edit_text(msgs[i % len(msgs)])
            except: pass
            await asyncio.sleep(3)
            i += 1
    asyncio.create_task(loading_loop())

    # === PRIMARY APIs (sabse fast) ===
    try:
        r = requests.post("https://co.wuk.sh/api/json", json={"url": url}, timeout=12)
        if r.json().get("url"):
            await update.message.reply_video(video=r.json()["url"], caption="✅ TURANT HO GAYA! ⚡", supports_streaming=True)
            success = True
    except: pass

    if not success:
        try:
            r = requests.post("https://api.cobalt.tools/api/json", json={"url": url}, timeout=12)
            if r.json().get("url"):
                await update.message.reply_video(video=r.json()["url"], caption="✅ TURANT HO GAYA! ⚡", supports_streaming=True)
                success = True
        except: pass

    # === IMPROVED BACKUP (GIF + NO AUDIO PROBLEM SOLVED) ===
    if not success:
        try:
            ydl_opts = {
                'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
                'merge_output_format': 'mp4',
                'quiet': True,
                'socket_timeout': 35,
                'no_warnings': True
            }
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                video_url = info.get('url')
                if not video_url and info.get('formats'):
                    # Best mp4 with audio
                    suitable = [f for f in info['formats'] if f.get('ext') == 'mp4' and f.get('height', 0) <= 720 and f.get('acodec') != 'none']
                    if suitable:
                        best = max(suitable, key=lambda f: f.get('height', 0))
                        video_url = best.get('url')

                if video_url:
                    await update.message.reply_video(video=video_url, caption="✅ TURANT HO GAYA! ⚡ (Fixed Quality)", supports_streaming=True)
                    success = True
        except Exception as e:
            logger.error(f"Backup Error: {e}")

    if success:
        await status.delete()
    else:
        add_credits(user_id, 10)  # credit refund
        await status.edit_text("⏳ Instagram busy hai...\n15 sec baad try karo (credits wapas mil gaye)")

# ====================== START BOT ======================
if __name__ == '__main__':
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_screenshot))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_zero_error))

    print("✅ BOT STARTED WITH FIXED GIF & AUDIO ISSUE!")
    app.run_polling()
