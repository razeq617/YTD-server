from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest

CHANNEL_ID = "@zinonestore" 

async def is_user_member(bot: Bot, user_id: int) -> bool:
    """Checks if the user is a member, creator, or admin."""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        valid_statuses = ['member', 'creator', 'administrator']
        return member.status in valid_statuses
    except Exception:
        return False

async def send_join_message(bot: Bot, chat_id: int, original_query=None):
    """Sends the join request message with the 'Check Membership' button."""
    keyboard = [
        [InlineKeyboardButton("🔗 عضویت در کانال", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")],
        [InlineKeyboardButton("بررسی عضویت", callback_data="verify_membership")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = (
        "⚠️ **اجباری: عضویت در کانال**\n\n"
        "برای استفاده از ربات لطفا ابتدا عضو کانال ما شوید.\n"
        "پس از عضویت، روی دکمه «بررسی عضویت» کلیک کنید."
    )
    
    if original_query:
        try:
            await original_query.edit_message_text(text=message_text, reply_markup=reply_markup, parse_mode="Markdown")
        except:
            pass 
    else:
        await bot.send_message(chat_id=chat_id, text=message_text, reply_markup=reply_markup, parse_mode="Markdown")
