"""
Telegram Affiliate Marketing Bot.
==================================
"""


import logging
import asyncio
import os
from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)

# Load environment variables from .env file
load_dotenv()

# ─────────────────────────────────────────────
# ✅ CREDENTIALS FROM ENVIRONMENT VARIABLES
# ─────────────────────────────────────────────
BOT_TOKEN   = os.getenv("BOT_TOKEN")      # From @BotFather
CHANNEL_ID  = int(os.getenv("CHANNEL_ID", 0))   # Your channel ID
ADMIN_ID    = int(os.getenv("ADMIN_ID", 0))     # Your Telegram user ID
# ─────────────────────────────────────────────

# Validate credentials
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN is not set in environment variables")
if CHANNEL_ID == 0:
    raise ValueError("❌ CHANNEL_ID is not set in environment variables")
if ADMIN_ID == 0:
    raise ValueError("❌ ADMIN_ID is not set in environment variables")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── In-memory storage (simple, no database needed) ──
affiliate_products = [
    {
        "name": "🛍️ Product 1",
        "description": "Amazing product you must try!",
        "link": "https://your-affiliate-link.com/product1",
        "emoji": "🔥"
    },
    {
        "name": "💻 Product 2",
        "description": "Best deal of the week!",
        "link": "https://your-affiliate-link.com/product2",
        "emoji": "⭐"
    },
]

faq_answers = {
    "how to buy":     "👉 Click the product link and follow the steps on the website!",
    "is it safe":     "✅ Yes! All links are verified and safe to use.",
    "discount":       "💰 Use our links to get the best prices automatically!",
    "shipping":       "🚚 Shipping info is available on each product page.",
    "refund":         "💳 Each store has its own refund policy, check the product page.",
    "contact":        "📩 Send a message to our admin for help.",
}

post_index = 0  # tracks which product to post next


# ════════════════════════════════════════════
# WELCOME NEW MEMBERS
# ════════════════════════════════════════════
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if result.new_chat_member.status == "member":
        new_user = result.new_chat_member.user
        name = new_user.first_name or "Friend"
        welcome_msg = (
            f"🎉 Welcome, *{name}*!\n\n"
            f"You've joined our Affiliate Deals channel!\n\n"
            f"Here you'll find:\n"
            f"✅ Exclusive deals & discounts\n"
            f"✅ Top product recommendations\n"
            f"✅ Daily offers\n\n"
            f"Type /deals to see today's best products!\n"
            f"Type /help to see all commands."
        )
        await context.bot.send_message(
            chat_id=result.chat.id,
            text=welcome_msg,
            parse_mode="Markdown"
        )


# ════════════════════════════════════════════
# COMMANDS
# ════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! I'm your Affiliate Bot!\n\n"
        "Commands:\n"
        "/deals  — See today's best products\n"
        "/faq    — Common questions & answers\n"
        "/help   — Show this menu\n\n"
        "Join our channel for daily deals! 🔥"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Available Commands:*\n\n"
        "/deals  — Browse affiliate products\n"
        "/faq    — Frequently asked questions\n"
        "/help   — Show this menu\n\n"
        "💬 You can also ask me questions like:\n"
        "• 'how to buy'\n"
        "• 'is it safe'\n"
        "• 'discount'\n"
        "• 'shipping'\n"
        "• 'refund'",
        parse_mode="Markdown"
    )


async def cmd_deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not affiliate_products:
        await update.message.reply_text("No products available yet. Check back soon!")
        return

    for product in affiliate_products:
        msg = (
            f"{product['emoji']} *{product['name']}*\n\n"
            f"📝 {product['description']}\n\n"
            f"🔗 [Click here to get it!]({product['link']})"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    faq_text = "❓ *Frequently Asked Questions:*\n\n"
    for question, answer in faq_answers.items():
        faq_text += f"*Q: {question.title()}*\n{answer}\n\n"
    await update.message.reply_text(faq_text, parse_mode="Markdown")


# ════════════════════════════════════════════
# ADMIN COMMANDS
# ════════════════════════════════════════════
async def cmd_addproduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /addproduct Name | Description | https://link"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only command.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n/addproduct Name | Description | https://yourlink.com"
        )
        return

    text = " ".join(context.args)
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 3:
        await update.message.reply_text(
            "❌ Format: /addproduct Name | Description | https://link"
        )
        return

    affiliate_products.append({
        "name": parts[0],
        "description": parts[1],
        "link": parts[2],
        "emoji": "🛍️"
    })
    await update.message.reply_text(f"✅ Product added: *{parts[0]}*", parse_mode="Markdown")


async def cmd_postall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: post all products to channel now"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only command.")
        return

    await post_to_channel(context.bot)
    await update.message.reply_text("✅ Posted to channel!")


# ════════════════════════════════════════════
# AUTO-POST TO CHANNEL (SCHEDULED)
# ════════════════════════════════════════════
async def post_to_channel(bot: Bot):
    """Posts one product at a time to the channel, cycling through the list."""
    global post_index
    if not affiliate_products:
        return

    try:
        product = affiliate_products[post_index % len(affiliate_products)]
        post_index += 1

        msg = (
            f"{product['emoji']} *{product['name']}*\n\n"
            f"📝 {product['description']}\n\n"
            f"🔗 [Get it here!]({product['link']})\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🔔 Subscribe for more daily deals!"
        )
        await bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error posting to channel: {e}")


async def scheduled_post(context: ContextTypes.DEFAULT_TYPE):
    """Called by the job queue every scheduled interval."""
    await post_to_channel(context.bot)


# ════════════════════════════════════════════
# SMART FAQ REPLY (keyword detection)
# ════════════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_text = update.message.text.lower()

    # Check if message matches any FAQ keyword
    for keyword, answer in faq_answers.items():
        if keyword in user_text:
            await update.message.reply_text(answer)
            return

    # Default reply
    await update.message.reply_text(
        "🤖 I didn't understand that.\n"
        "Try /deals to see products or /faq for common questions!"
    )


# ════════════════════════════════════════════
# MAIN — BUILD & RUN BOT
# ════════════════════════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # ── Register command handlers ──
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(CommandHandler("deals",      cmd_deals))
    app.add_handler(CommandHandler("faq",        cmd_faq))
    app.add_handler(CommandHandler("addproduct", cmd_addproduct))
    app.add_handler(CommandHandler("postall",    cmd_postall))

    # ── Welcome new channel/group members ──
    app.add_handler(ChatMemberHandler(welcome_new_member, ChatMemberHandler.CHAT_MEMBER))

    # ── Handle regular messages (FAQ keywords) ──
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    

    print("🤖 Bot is running... Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    import time
    while True:
        try:
            main()
        except Exception as e:
            logger.error(f"Bot crashed: {e}, restarting in 5s...")
            time.sleep(5)

    
