import logging
import os
import asyncio
import yt_dlp
import glob
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from check_join import is_user_member, send_join_message

# ---------------- CONFIG ----------------
TOKEN = "8489847079:AAG2Eey-1ebdBWfB6LJRMaVlfs7RmuaRzRk"

# Added 144p as requested
RESOLUTIONS = ["144", "240", "360", "480", "720", "1080"]
AUDIO_BITRATES = ["128", "256"]

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
download_lock = asyncio.Lock()

# ---------------- yt-dlp CORE ----------------

def run_yt_dlp_sync(url: str, quality: str):
    output_tpl = os.path.join(DOWNLOAD_DIR, "%(id)s_" + quality + ".%(ext)s")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": output_tpl,
        "retries": 10,
        "fragment_retries": 10,
    }

    if quality in AUDIO_BITRATES:
        # --- Robust MP3 Settings ---
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": quality,
            }],
        })
    else:
        # --- High Quality Video (1080p Support) ---
        # This format string forces a merge of best video and best audio
        ydl_opts["format"] = f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}][ext=mp4]/best"
        ydl_opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Post-processing extension fix
            if quality in AUDIO_BITRATES:
                filename = os.path.splitext(filename)[0] + ".mp3"
            elif not filename.endswith(".mp4"):
                filename = os.path.splitext(filename)[0] + ".mp4"

            return filename, None
    except Exception as e:
        return None, str(e)

# ---------------- HANDLERS ----------------

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    # 1. Handle Membership Button FIRST
    if query.data == "verify_membership":
        if await is_user_member(context.bot, user_id):
            await query.edit_message_text(
                "✅ عضویت شما تایید شد! حالا شما میتوانید از ربات استفاده کنید."
            )
        else:
            await query.answer("❌ شما هنوز عضو کانال نشده‌اید.", show_alert=True)
        return

    # 2. Handle Download Buttons (they contain "|")
    if "|" in query.data:
        quality, url = query.data.split("|")
        asyncio.create_task(send_download_process(url, quality, query, context))

async def send_download_process(url, quality, query, context):
    async with download_lock:
        chat_id = query.message.chat_id
        status_msg = await context.bot.send_message(chat_id, f"⏳ در حال پردازش {quality}...")

        filename, error = await asyncio.to_thread(run_yt_dlp_sync, url, quality)

        if error:
            await status_msg.edit_text(f"❌ خطا:\n{error}")
            return

        if filename and os.path.exists(filename):
            await status_msg.edit_text("📤 در حال ارسال فایل...")
            with open(filename, "rb") as f:
                if quality in AUDIO_BITRATES:
                    await context.bot.send_video(chat_id=chat_id, video=f, write_timeout=600, read_timeout=600)
                else:
                    await context.bot.send_video(chat_id=chat_id, video=f, write_timeout=600, read_timeout=600)
            
            os.remove(filename)
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ متاسفانه فایل دریافت نشد.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    url = update.message.text.strip()

    if "youtube.com" not in url and "youtu.be" not in url:
        return

    # Check membership before allowing interaction
    if not await is_user_member(context.bot, user_id):
        await send_join_message(context.bot, update.message.chat_id)
        return

    try:
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "Video")
            
        keyboard = [
            [InlineKeyboardButton(f"{r}p", callback_data=f"{r}|{url}") for r in RESOLUTIONS[:3]],
            [InlineKeyboardButton(f"{r}p", callback_data=f"{r}|{url}") for r in RESOLUTIONS[3:]],
            [InlineKeyboardButton(f"🎵 MP3 {b}", callback_data=f"{b}|{url}") for b in AUDIO_BITRATES],
        ]

        await update.message.reply_text(
            f"📹 {title}\nکیفیت مورد نظر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception:
        await update.message.reply_text("❌ خطا در دریافت اطلاعات ویدیو. لینک را بررسی کنید.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 سلام! لینک یوتیوب را بفرست تا برات دانلود کنم.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ Bot is online with full 1080p/MP3 support")
    app.run_polling()
