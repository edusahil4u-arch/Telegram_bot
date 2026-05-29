"""
Telegram Affiliate Marketing Bot.
==================================
"""

import logging
import asyncio
import os
import time
import sqlite3
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
BOT_TOKEN   = os.getenv("BOT_TOKEN")
CHANNEL_ID  = int(os.getenv("CHANNEL_ID", 0))
ADMIN_ID    = int(os.getenv("ADMIN_ID", 0))
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

# ════════════════════════════════════════════
# SQLITE DATABASE
# ════════════════════════════════════════════

conn = sqlite3.connect("bot_data.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS subscribers (
    user_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_name TEXT,
    amount TEXT,
    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()

# ── In-memory storage ──
affiliate_products = [
    {
        "name": "🛍️ Product 1",
        "description": "Amazing product you must try!",
        "link": "https://your-affiliate-link.com/product1",
        "emoji": "🔥",
        "category": "general"
    },
    {
        "name": "💻 Product 2",
        "description": "Best deal of the week!",
        "link": "https://your-affiliate-link.com/product2",
        "emoji": "⭐",
        "category": "electronics"
    },
]

sale_products = []
subscribers = set()
wishlists = {}
user_ids = set()

faq_answers = {
    "how to buy":  "👉 Click the product link and follow the steps on the website!",
    "is it safe":  "✅ Yes! All links are verified and safe to use.",
    "discount":    "💰 Use our links to get the best prices automatically!",
    "shipping":    "🚚 Shipping info is available on each product page.",
    "refund":      "💳 Each store has its own refund policy, check the product page.",
    "contact":     "📩 Send a message to our admin for help.",
}

categories = {
    "electronics": "📱 Electronics",
    "fashion":     "👗 Fashion",
    "health":      "💊 Health & Beauty",
    "home":        "🏠 Home & Kitchen",
    "general":     "🛍️ General",
}

post_index = 0


# ════════════════════════════════════════════
# DATABASE FUNCTIONS
# ════════════════════════════════════════════

def save_user(user):
    try:
        cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
        """, (
            user.id,
            user.username,
            user.first_name
        ))
        conn.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")


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
# BASIC COMMANDS
# ════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_ids.add(update.effective_user.id)
    save_user(update.effective_user)

    await update.message.reply_text(
        "👋 Welcome to *Affiliate Deals Bot!*\n\n"
        "🔥 Get the best deals every day!\n\n"
        "📋 *Commands:*\n"
        "/deals — Today's best products\n"
        "/new — Newly added products\n"
        "/sale — Flash sales & hot deals\n"
        "/categories — Browse by category\n"
        "/search — Search products\n"
        "/wishlist — Your saved products\n"
        "/subscribe — Get daily deal alerts\n"
        "/faq — Common questions\n"
        "/help — Show this menu",
        parse_mode="Markdown"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Available Commands:*\n\n"
        "🛍️ *Shopping*\n"
        "/deals — Browse all products\n"
        "/new — Newly added products\n"
        "/sale — Flash sales\n"
        "/categories — Browse by category\n"
        "/search — Search products by name\n\n"
        "❤️ *Personal*\n"
        "/wishlist — Your saved products\n"
        "/subscribe — Daily deal alerts ON\n"
        "/unsubscribe — Daily deal alerts OFF\n\n"
        "❓ *Help*\n"
        "/faq — Frequently asked questions\n"
        "/help — Show this menu",
        parse_mode="Markdown"
    )


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    user_ids.add(user_id)
    save_user(update.effective_user)

    subscribers.add(user_id)

    cursor.execute(
        "INSERT OR IGNORE INTO subscribers (user_id) VALUES (?)",
        (user_id,)
    )

    conn.commit()

    await update.message.reply_text(
        "🔔 *Subscribed!*\n\n"
        "You'll now receive daily deal alerts!\n"
        "Type /unsubscribe to stop anytime.",
        parse_mode="Markdown"
    )


async def cmd_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    subscribers.discard(user_id)

    cursor.execute(
        "DELETE FROM subscribers WHERE user_id=?",
        (user_id,)
    )

    conn.commit()

    await update.message.reply_text(
        "🔕 *Unsubscribed!*\n\n"
        "You won't receive daily alerts anymore.",
        parse_mode="Markdown"
    )


async def cmd_deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_ids.add(update.effective_user.id)
    save_user(update.effective_user)

    if not affiliate_products:
        await update.message.reply_text("No products available yet.")
        return

    await update.message.reply_text(
        "🔥 *Today's Best Deals:*",
        parse_mode="Markdown"
    )

    for product in affiliate_products:
        msg = (
            f"{product['emoji']} *{product['name']}*\n\n"
            f"📝 {product['description']}\n\n"
            f"🔗 [Click here to get it!]({product['link']})"
        )

        await update.message.reply_text(
            msg,
            parse_mode="Markdown"
        )


async def cmd_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    faq_text = "❓ *Frequently Asked Questions:*\n\n"

    for question, answer in faq_answers.items():
        faq_text += f"*Q: {question.title()}*\n{answer}\n\n"

    await update.message.reply_text(
        faq_text,
        parse_mode="Markdown"
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only command.")
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM subscribers")
    total_subscribers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM purchases")
    total_purchases = cursor.fetchone()[0]

    await update.message.reply_text(
        f"📊 *Bot Statistics:*\n\n"
        f"👥 Total Users: {total_users}\n"
        f"🔔 Subscribers: {total_subscribers}\n"
        f"🛒 Purchases: {total_purchases}\n"
        f"🛍️ Total Products: {len(affiliate_products)}",
        parse_mode="Markdown"
    )


# ════════════════════════════════════════════
# PURCHASE COMMAND
# ════════════════════════════════════════════

async def cmd_addpurchase(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only command.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n/addpurchase user_id | product | amount"
        )
        return

    text = " ".join(context.args)
    parts = [p.strip() for p in text.split("|")]

    if len(parts) < 3:
        await update.message.reply_text(
            "❌ Format:\n/addpurchase user_id | product | amount"
        )
        return

    user_id = int(parts[0])
    product = parts[1]
    amount = parts[2]

    cursor.execute("""
    INSERT INTO purchases (user_id, product_name, amount)
    VALUES (?, ?, ?)
    """, (user_id, product, amount))

    conn.commit()

    await update.message.reply_text(
        f"✅ Purchase saved for user {user_id}"
    )


# ════════════════════════════════════════════
# SMART FAQ REPLY
# ════════════════════════════════════════════

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message or not update.message.text:
        return

    user_ids.add(update.effective_user.id)
    save_user(update.effective_user)

    user_text = update.message.text.lower()

    for keyword, answer in faq_answers.items():
        if keyword in user_text:
            await update.message.reply_text(answer)
            return

    await update.message.reply_text(
        "🤖 I didn't understand that.\n"
        "Try /deals or /faq"
    )


# ════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════

def main():

    app = Application.builder().token(BOT_TOKEN).build()

    # User commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("deals", cmd_deals))
    app.add_handler(CommandHandler("faq", cmd_faq))
    app.add_handler(CommandHandler("subscribe", cmd_subscribe))
    app.add_handler(CommandHandler("unsubscribe", cmd_unsubscribe))

    # Admin commands
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("addpurchase", cmd_addpurchase))

    # Welcome handler
    app.add_handler(
        ChatMemberHandler(
            welcome_new_member,
            ChatMemberHandler.CHAT_MEMBER
        )
    )

    # Message handler
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("🤖 Bot is running...")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":

    while True:
        try:
            main()

        except Exception as e:
            logger.error(f"Bot crashed: {e}, restarting in 5s...")
            time.sleep(5)