from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest

# --- تنظیمات ---
# نام کاربری کانال خود را اینجا وارد کنید (مثلا: @MyChannel)
# توجه: برای دکمه عضویت حتماً باید نام کاربری عمومی باشد، نه آیدی عددی.
CHANNEL_ID = "@zinonestore" 

async def is_user_member(bot: Bot, user_id: int) -> bool:
    """
    بررسی می‌کند که آیا کاربر عضو کانال است یا خیر.
    """
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        
        # وضعیت‌هایی که به معنای عضویت هستند
        valid_statuses = ['member', 'creator', 'administrator']
        
        return member.status in valid_statuses
        
    except BadRequest as e:
        # اگر کاربر عضو نباشد یا ربات ادمین نباشد خطا میدهد
        return False
    except Exception as e:
        return False

async def send_join_message(bot: Bot, chat_id: int, original_query=None):
    """
    پیام دسترسی ممنوع را به همراه دکمه عضویت ارسال می‌کند.
    """
    # ساخت دکمه‌ها
    keyboard = [
        [
            InlineKeyboardButton("🔗 عضویت در کانال", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}"),
            InlineKeyboardButton("✅ عضو شدم", callback_data="check_again")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # متن پیام فارسی
    message_text = (
        "⚠️ **اجباری: عضویت در کانال**\n\n"
        "برای استفاده از ربات لطفا ابتدا عضو کانال ما شوید.\n"
        "پس از عضویت، روی دکمه «عضو شدم» کلیک کنید."
    )
    
    if original_query:
        # اگر کاربر روی دکمه کلیک کرده باشد، پیام قبلی را ویرایش میکنیم
        try:
            await original_query.edit_message_text(text=message_text, reply_markup=reply_markup)
        except:
            pass 
    else:
        # اگر کاربر لینک فرستاده باشد، پیام جدید میفرستیم
        await bot.send_message(chat_id=chat_id, text=message_text, reply_markup=reply_markup)