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


async def cmd_deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_ids.add(update.effective_user.id)
    if not affiliate_products:
        await update.message.reply_text("No products available yet. Check back soon!")
        return
    await update.message.reply_text("🔥 *Today's Best Deals:*", parse_mode="Markdown")
    for product in affiliate_products:
        msg = (
            f"{product['emoji']} *{product['name']}*\n\n"
            f"📝 {product['description']}\n\n"
            f"🔗 [Click here to get it!]({product['link']})"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_ids.add(update.effective_user.id)
    if not affiliate_products:
        await update.message.reply_text("No new products yet!")
        return
    # Show last 3 added products
    new_products = affiliate_products[-3:]
    await update.message.reply_text("🆕 *Newly Added Products:*", parse_mode="Markdown")
    for product in new_products:
        msg = (
            f"{product['emoji']} *{product['name']}*\n\n"
            f"📝 {product['description']}\n\n"
            f"🔗 [Get it here!]({product['link']})"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_ids.add(update.effective_user.id)
    if not sale_products:
        await update.message.reply_text(
            "⚡ No flash sales right now!\n"
            "Subscribe with /subscribe to get notified when sales start! 🔔"
        )
        return
    await update.message.reply_text("⚡ *Flash Sales & Hot Deals:*", parse_mode="Markdown")
    for product in sale_products:
        msg = (
            f"🔴 *SALE* — {product['emoji']} *{product['name']}*\n\n"
            f"📝 {product['description']}\n"
            f"💥 *{product.get('discount', 'Special Price')}*\n\n"
            f"🔗 [Grab this deal!]({product['link']})"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_ids.add(update.effective_user.id)
    cat_text = "📦 *Browse by Category:*\n\n"
    for key, name in categories.items():
        count = len([p for p in affiliate_products if p.get("category") == key])
        cat_text += f"{name} — {count} products\n"
    cat_text += "\n📌 Type `/category electronics` to see electronics\n"
    cat_text += "📌 Replace electronics with any category name"
    await update.message.reply_text(cat_text, parse_mode="Markdown")


async def cmd_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_ids.add(update.effective_user.id)
    if not context.args:
        await update.message.reply_text(
            "Usage: /category electronics\n"
            "Available: electronics, fashion, health, home, general"
        )
        return
    cat = context.args[0].lower()
    filtered = [p for p in affiliate_products if p.get("category") == cat]
    if not filtered:
        await update.message.reply_text(f"No products found in *{cat}* category!", parse_mode="Markdown")
        return
    await update.message.reply_text(f"📦 *{categories.get(cat, cat)} Products:*", parse_mode="Markdown")
    for product in filtered:
        msg = (
            f"{product['emoji']} *{product['name']}*\n\n"
            f"📝 {product['description']}\n\n"
            f"🔗 [Get it here!]({product['link']})"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_ids.add(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("Usage: /search laptop\nType a product name to search!")
        return
    query = " ".join(context.args).lower()
    results = [
        p for p in affiliate_products
        if query in p["name"].lower() or query in p["description"].lower()
    ]
    if not results:
        await update.message.reply_text(f"❌ No products found for *{query}*", parse_mode="Markdown")
        return
    await update.message.reply_text(f"🔍 *Search results for '{query}':*", parse_mode="Markdown")
    for product in results:
        msg = (
            f"{product['emoji']} *{product['name']}*\n\n"
            f"📝 {product['description']}\n\n"
            f"🔗 [Get it here!]({product['link']})"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_ids.add(user_id)
    wish = wishlists.get(user_id, [])
    if not wish:
        await update.message.reply_text(
            "❤️ Your wishlist is empty!\n\n"
            "Use /save ProductName to save a product.\n"
            "Example: /save Product 1"
        )
        return
    await update.message.reply_text("❤️ *Your Wishlist:*", parse_mode="Markdown")
    for item in wish:
        await update.message.reply_text(f"• {item}")


async def cmd_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_ids.add(user_id)
    if not context.args:
        await update.message.reply_text("Usage: /save ProductName")
        return
    product_name = " ".join(context.args)
    if user_id not in wishlists:
        wishlists[user_id] = []
    if product_name in wishlists[user_id]:
        await update.message.reply_text("Already in your wishlist! ❤️")
        return
    wishlists[user_id].append(product_name)
    await update.message.reply_text(f"✅ *{product_name}* saved to your wishlist!", parse_mode="Markdown")
async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_ids.add(user_id)
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
    await update.message.reply_text(
        "🔕 *Unsubscribed!*\n\n"
        "You won't receive daily alerts anymore.\n"
        "Type /subscribe to turn them back on.",
        parse_mode="Markdown"
    )


async def cmd_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    faq_text = "❓ *Frequently Asked Questions:*\n\n"
    for question, answer in faq_answers.items():
        faq_text += f"*Q: {question.title()}*\n{answer}\n\n"
    await update.message.reply_text(faq_text, parse_mode="Markdown")


# ════════════════════════════════════════════
# ADMIN COMMANDS
# ════════════════════════════════════════════
async def cmd_addproduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /addproduct Name | Description | https://link | category"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only command.")
        return
    if not context.args:
        await update.message.reply_text(
            "Usage:\n/addproduct Name | Description | https://link | category\n\n"
            "Categories: electronics, fashion, health, home, general"
        )
        return
    text = " ".join(context.args)
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 3:
        await update.message.reply_text("❌ Format: /addproduct Name | Description | https://link | category")
        return
    affiliate_products.append({
        "name": parts[0],
        "description": parts[1],
        "link": parts[2],
        "category": parts[3] if len(parts) > 3 else "general",
        "emoji": "🛍️"
    })
    await update.message.reply_text(f"✅ Product added: *{parts[0]}*", parse_mode="Markdown")


async def cmd_addsale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /addsale Name | Description | https://link | discount"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only command.")
        return
    if not context.args:
        await update.message.reply_text(
            "Usage:\n/addsale Name | Description | https://link | 50% OFF"
        )
        return
    text = " ".join(context.args)
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 3:
        await update.message.reply_text("❌ Format: /addsale Name | Description | https://link | discount")
        return
    sale_products.append({
        "name": parts[0],
        "description": parts[1],
        "link": parts[2],
        "discount": parts[3] if len(parts) > 3 else "Special Price",
        "emoji": "🔴"
    })
    await update.message.reply_text(f"✅ Sale product added: *{parts[0]}*", parse_mode="Markdown")


async def cmd_removeproduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /removeproduct ProductName"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only command.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /removeproduct ProductName")
        return
    name = " ".join(context.args)
    original_count = len(affiliate_products)
    affiliate_products[:] = [p for p in affiliate_products if p["name"] != name]
    if len(affiliate_products) < original_count:
        await update.message.reply_text(f"✅ Removed: *{name}*", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Product not found: *{name}*", parse_mode="Markdown")


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /broadcast Your message here"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only command.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast Your message here")
        return
    message = " ".join(context.args)
    success = 0
    for user_id in subscribers:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 *Announcement:*\n\n{message}",
                parse_mode="Markdown"
            )
            success += 1
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")
    await update.message.reply_text(f"✅ Broadcast sent to {success} subscribers!")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /stats"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only command.")
        return
    await update.message.reply_text(
        f"📊 *Bot Statistics:*\n\n"
        f"👥 Total Users: {len(user_ids)}\n"
        f"🔔 Subscribers: {len(subscribers)}\n"
        f"🛍️ Total Products: {len(affiliate_products)}\n"
        f"⚡ Sale Products: {len(sale_products)}\n"
        f"❤️ Users with Wishlists: {len(wishlists)}",
        parse_mode="Markdown"
    )


async def cmd_postall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only command.")
        return
    await post_to_channel(context.bot)
    await update.message.reply_text("✅ Posted to channel!")


# ════════════════════════════════════════════
# AUTO-POST TO CHANNEL
# ════════════════════════════════════════════
async def post_to_channel(bot: Bot):
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
    await post_to_channel(context.bot)


# ════════════════════════════════════════════
# SMART FAQ REPLY
# ════════════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user_ids.add(update.effective_user.id)
    user_text = update.message.text.lower()
    for keyword, answer in faq_answers.items():
        if keyword in user_text:
            await update.message.reply_text(answer)
            return
    await update.message.reply_text(
        "🤖 I didn't understand that.\n"
        "Try /deals to see products or /faq for common questions!"
    )


# ════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # User commands
    app.add_handler(CommandHandler("start",         cmd_start))
    app.add_handler(CommandHandler("help",          cmd_help))
    app.add_handler(CommandHandler("deals",         cmd_deals))
    app.add_handler(CommandHandler("new",           cmd_new))
    app.add_handler(CommandHandler("sale",          cmd_sale))
    app.add_handler(CommandHandler("categories",    cmd_categories))
    app.add_handler(CommandHandler("category",      cmd_category))
    app.add_handler(CommandHandler("search",        cmd_search))
    app.add_handler(CommandHandler("wishlist",      cmd_wishlist))
    app.add_handler(CommandHandler("save",          cmd_save))
    app.add_handler(CommandHandler("subscribe",     cmd_subscribe))
    app.add_handler(CommandHandler("unsubscribe",   cmd_unsubscribe))
    app.add_handler(CommandHandler("faq",           cmd_faq))

    # Admin commands
    app.add_handler(CommandHandler("addproduct",    cmd_addproduct))
    app.add_handler(CommandHandler("addsale",       cmd_addsale))
    app.add_handler(CommandHandler("removeproduct", cmd_removeproduct))
    app.add_handler(CommandHandler("broadcast",     cmd_broadcast))
    app.add_handler(CommandHandler("stats",         cmd_stats))
    app.add_handler(CommandHandler("postall",       cmd_postall))

    # Welcome new members
    app.add_handler(ChatMemberHandler(welcome_new_member, ChatMemberHandler.CHAT_MEMBER))

    # Handle messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot is running... Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            logger.error(f"Bot crashed: {e}, restarting in 5s...")
            time.sleep(5)