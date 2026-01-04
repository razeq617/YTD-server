import logging
import os
import asyncio
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import BadRequest
from check_join import is_user_member, send_join_message, CHANNEL_ID

# --- CONFIGURATION ---
TOKEN = '8489847079:AAG2Eey-1ebdBWfB6LJRMaVlfs7RmuaRzRk'

# Get Token from Environment Variable (Docker compatible)
TOKEN = os.environ.get("TOKEN")

# 2. Fallback for local testing (Optional)
if not TOKEN:
    print("WARNING: TOKEN environment variable not found. Using hardcoded fallback.")
    TOKEN = '8489847079:AAG2Eey-1ebdBWfB6LJRMaVlfs7RmuaRzRk' 

# 3. Configuration Lists (CRITICAL: This was missing)
RESOLUTIONS = ['240', '360', '480', '720', '1080']
AUDIO_BITRATES = ['128', '256']

# Resolutions
RESOLUTIONS = ['240', '360', '480', '720', '1080']

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- HELPER FUNCTIONS ---

def run_yt_dlp_sync(url, quality):
    """
    Downloads the video.
    Strategy: Strictly looks for a single file containing both audio and video
    to avoid needing FFmpeg for merging.
    """
    out_tmpl = f'%(title)s_{quality}p.%(ext)s'
    
    # IMPORTANT: 
    # 1. 'best[height<=quality]' selects the best video under that height.
    # 2. '[acodec!=none]' ensures the file HAS audio (no merging required).
    # 3. '[ext=mp4]' ensures MP4 format.
    format_string = f'best[height<={quality}][ext=mp4][acodec!=none]/best[height<={quality}][acodec!=none]'

    ydl_opts = {
        'format': format_string,
        'outtmpl': out_tmpl,
        'quiet': True,
        'overwrites': True,
        'noplaylist': True,
        'check_formats': True, # Helps verify availability
        'no_warnings': True,
    }

    filename = None
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first to validate
            info = ydl.extract_info(url, download=False)
            
            # Check if we actually found a format. 
            # If no format matches the strict 'acodec!=none' rule, yt-dlp might throw error or download empty.
            # We proceed to download.
            
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            return filename, None
            
    except Exception as e:
        return None, str(e)

async def send_download_process(url, quality, query, context):
    chat_id = query.message.chat_id
    
    try:
        # Update status
        await query.edit_message_text(text=f"🔄 در حال دانلود کیفیت {quality}p...")

        # Run download
        filename, error = await asyncio.to_thread(run_yt_dlp_sync, url, quality)

        if error:
            # Handle specific errors
            if "Requested format is not available" in error or "No video formats found" in error:
                 await context.bot.send_message(chat_id=chat_id, text=f"❌ این ویدیو در کیفیت {quality}p (فایل یک‌تکه) موجود نیست. لطفا کیفیت دیگری را امتحان کنید.")
            elif "ffmpeg" in error.lower() or "merging" in error.lower():
                 # Fallback message if merging somehow happened
                 await context.bot.send_message(chat_id=chat_id, text="❌ خطا در ادغام فایل. لطفا 360p یا 480p را امتحان کنید.")
            else:
                 await context.bot.send_message(chat_id=chat_id, text=f"❌ خطا: {error}")
            return

        if filename and os.path.exists(filename):
            # Check file size (Telegram limit is 50MB)
            file_size = os.path.getsize(filename)
            if file_size > 50 * 1024 * 1024: # 50MB
                await context.bot.send_message(chat_id=chat_id, text="❌ فایل برای تلگرام خیلی بزرگ است (بیش از 50 مگابایت).")
                os.remove(filename)
                return

            # Send Video
            with open(filename, 'rb') as video_file:
                await context.bot.send_video(
                    chat_id=chat_id, 
                    video=video_file, 
                    caption=f"✅ دانلود کیفیت {quality}p تکمیل شد."
                )
            
            # Cleanup
            try:
                os.remove(filename)
            except:
                pass
        else:
            await context.bot.send_message(chat_id=chat_id, text="❌ خطا: فایل دانلود نشد.")

    except Exception as e:
        logging.error(f"Critical error: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"❌ خطای سیستمی: {str(e)}")

# --- HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 سلام! به دانلودر یوتیوب خوش آمدید.\n\n"
        "نکته: بدون FFmpeg، کیفیت‌های 720p و 1080p ممکن است همیشه در دسترس نباشند. "
        "کیفیت‌های 360p و 480p معمولاً کار می‌کنند."
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Get User ID
    user_id = update.message.from_user.id
    url = update.message.text
    
    # 2. Basic URL Validation
    if not ("youtube.com" in url or "youtu.be" in url):
        await update.message.reply_text("⚠️ لطفا فقط لینک یوتیوب ارسال کنید.")
        return

    # 3. JOIN GATEKEEPER
    is_joined = await is_user_member(context.bot, user_id)
    
    if not is_joined:
        await send_join_message(context.bot, update.message.chat_id)
        return

    # 4. Normal Bot Logic
    try:
        # Add cookies or headers if needed, usually this is enough
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'extract_flat': False}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Video')
            
            keyboard = []
            row1 = [InlineKeyboardButton(f"{r}p", callback_data=f"{r}|{url}") for r in RESOLUTIONS[:3]]
            keyboard.append(row1)
            row2 = [InlineKeyboardButton(f"{r}p", callback_data=f"{r}|{url}") for r in RESOLUTIONS[3:]]
            keyboard.append(row2)
            row3 = [InlineKeyboardButton(f"🎵 MP3 {b}", callback_data=f"{b}|{url}") for b in AUDIO_BITRATES]
            keyboard.append(row3)
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"📹 **{title}**\nکیفیت را انتخاب کنید:", reply_markup=reply_markup)
            
    except Exception as e:
        # FIX: Show the exact error so you can see it
        error_text = str(e)
        logging.error(f"yt-dlp info error: {error_text}") # Prints to terminal
        await update.message.reply_text(f"❌ خطا در دریافت اطلاعات:\n\n{error_text}")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    # 1. ACKNOWLEDGE CLICK IMMEDIATELY (Important for visual feedback)
    try:
        await query.answer()
    except BadRequest:
        pass

    user_id = update.effective_user.id

    # 2. CHECK IF USER CLICKED "I JOINED" (CHECK_AGAIN)
    # We MUST check this BEFORE checking for quality buttons
    if query.data == "check_again":
        # Recheck membership
        if await is_user_member(context.bot, user_id):
            # Success: Edit the "Join" message to a success message
            await query.edit_message_text("✅ تایید شد! عضویت شما ثبت گردید. حالا می‌توانید لینک ویدیو را ارسال کنید.")
        else:
            # Failure: Show a red popup alert
            await query.answer("❌ شما هنوز عضو کانال نشده‌اید!", show_alert=True)
            return # IMPORTANT: Stop here, don't try to download!

    # 3. PROCEED WITH DOWNLOAD (Quality Buttons)
    try:
        data = query.data.split('|')
        quality = data[0]
        url = data[1]

        # Check membership again (Gatekeeper)
        if not await is_user_member(context.bot, user_id):
            await send_join_message(context.bot, query.message.chat_id, query)
            return

        # Start download
        asyncio.create_task(send_download_process(url, quality, query, context))
        
    except ValueError:
        # This handles the case where query.data is "check_again" 
        # (because it can't be split by '|')
        # Since we already handled "check_again" above, we can ignore this.
        pass

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("Bot is running...")
    application.run_polling()