"""
Telegram Affiliate Marketing Bot
==================================
Features:
- User: deals, search, categories, wishlist, subscribe, referral, faq
- Admin: addproduct, removeproduct, postall, broadcast, stats, addcoupon, addsale
"""

import logging
import os
from datetime import datetime
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

load_dotenv()

# ─────────────────────────────────────────────
# CREDENTIALS
# ─────────────────────────────────────────────
BOT_TOKEN  = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
ADMIN_ID   = int(os.getenv("ADMIN_ID", 0))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set")
if CHANNEL_ID == 0:
    raise ValueError("CHANNEL_ID not set")
if ADMIN_ID == 0:
    raise ValueError("ADMIN_ID not set")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# IN-MEMORY STORAGE
# ─────────────────────────────────────────────
affiliate_products = []   # All products
sale_products      = []   # Sale/flash deals
new_products       = []   # Recently added
subscribers        = set()  # User IDs subscribed
wishlists          = {}   # user_id: [product names]
users              = {}   # user_id: {name, username, joined, referrals}
referrals          = {}   # referral_code: user_id
coupons            = {}   # code: discount%
post_index         = 0    # For cycling products

faq_answers = {
    "how to buy":  "👉 Click the product link and follow steps on the website!",
    "is it safe":  "✅ Yes! All links are verified and safe to use.",
    "discount":    "💰 Use our links to get the best prices automatically!",
    "shipping":    "🚚 Shipping info is available on each product page.",
    "refund":      "💳 Each store has its own refund policy.",
    "contact":     "📩 Send a message to our admin for help.",
    "payment":     "💳 Pay directly on the website — we don't collect payments.",
    "cod":         "📦 COD availability depends on the website. Check the product page!",
    "return":      "🔄 Returns are handled by the store directly.",
    "cashback":    "💸 Click our links to get automatic cashback & best prices!",
}

categories_list = {
    "📱 Electronics":     "electronics",
    "👗 Fashion":         "fashion",
    "💄 Beauty":          "beauty",
    "🏠 Home & Kitchen":  "home",
    "📚 Books":           "books",
    "🧸 Toys & Kids":     "toys",
    "🏋️ Sports":          "sports",
    "🛍️ General":         "general",
}


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def save_user(user):
    if user.id not in users:
        users[user.id] = {
            "name":     user.first_name or "Friend",
            "username": user.username or "",
            "joined":   datetime.now().strftime("%Y-%m-%d"),
            "referrals": 0,
        }

def get_referral_code(user_id):
    code = f"REF{user_id}"
    referrals[code] = user_id
    return code


# ════════════════════════════════════════════
# USER COMMANDS
# ════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)

    # Handle referral
    if context.args:
        ref_code = context.args[0]
        if ref_code in referrals and referrals[ref_code] != user.id:
            ref_user_id = referrals[ref_code]
            if ref_user_id in users:
                users[ref_user_id]["referrals"] += 1

    name = user.first_name or "Friend"
    await update.message.reply_text(
        f"👋 Welcome, *{name}!*\n\n"
        f"🛍️ *Ecomstore4u Deals Bot*\n\n"
        f"Get the best deals from Amazon, Flipkart & Meesho!\n\n"
        f"📋 *Commands:*\n"
        f"/deals — Today's best products\n"
        f"/new — Newly added products\n"
        f"/sale — Flash sales 🔥\n"
        f"/categories — Browse by category\n"
        f"/search — Search products\n"
        f"/wishlist — Your saved products ❤️\n"
        f"/coupon — Check discount coupons\n"
        f"/refer — Get your referral link\n"
        f"/subscribe — Daily deal alerts 🔔\n"
        f"/faq — Common questions\n"
        f"/help — Show all commands",
        parse_mode="Markdown"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *All Commands:*\n\n"
        "🛍️ *Shopping*\n"
        "/deals — All products\n"
        "/new — New arrivals\n"
        "/sale — Flash deals\n"
        "/categories — By category\n"
        "/search — Search product\n\n"
        "❤️ *Personal*\n"
        "/wishlist — Saved products\n"
        "/savewishlist — Save a product\n"
        "/refer — Your referral link\n"
        "/coupon — Discount coupons\n"
        "/subscribe — Daily alerts ON\n"
        "/unsubscribe — Daily alerts OFF\n\n"
        "❓ *Help*\n"
        "/faq — FAQ\n"
        "/help — This menu",
        parse_mode="Markdown"
    )


async def cmd_deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)
    if not affiliate_products:
        await update.message.reply_text(
            "😔 No products yet! Check back soon.\n"
            "Subscribe with /subscribe to get alerts!"
        )
        return

    await update.message.reply_text("🔥 *Today's Best Deals:*", parse_mode="Markdown")
    for product in affiliate_products[-10:]:  # Show last 10
        msg = (
            f"{product['emoji']} *{product['name']}*\n\n"
            f"📝 {product['description']}\n"
            f"🏷️ Category: {product.get('category', 'General')}\n\n"
            f"🔗 [Get it here!]({product['link']})"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)
    if not new_products:
        await update.message.reply_text("😔 No new products yet!")
        return

    await update.message.reply_text("🆕 *Newly Added Products:*", parse_mode="Markdown")
    for product in new_products[-5:]:
        msg = (
            f"{product['emoji']} *{product['name']}*\n\n"
            f"📝 {product['description']}\n\n"
            f"🔗 [Get it here!]({product['link']})"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)
    if not sale_products:
        await update.message.reply_text("😔 No flash sales right now! Check back soon.")
        return

    await update.message.reply_text("🔥 *Flash Sales & Hot Deals:*", parse_mode="Markdown")
    for product in sale_products:
        msg = (
            f"⚡ *{product['name']}*\n\n"
            f"📝 {product['description']}\n"
            f"💰 *{product.get('discount', '')}% OFF!*\n\n"
            f"🔗 [Grab the deal!]({product['link']})"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)
    cats = "\n".join([f"{cat}" for cat in categories_list.keys()])
    await update.message.reply_text(
        f"📂 *Browse by Category:*\n\n{cats}\n\n"
        f"Type: `/search electronics` or `/search fashion` to filter!",
        parse_mode="Markdown"
    )


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)
    if not context.args:
        await update.message.reply_text(
            "🔍 Usage: `/search keyword`\n"
            "Example: `/search earphones`",
            parse_mode="Markdown"
        )
        return

    keyword = " ".join(context.args).lower()
    results = [
        p for p in affiliate_products
        if keyword in p["name"].lower()
        or keyword in p["description"].lower()
        or keyword in p.get("category", "").lower()
    ]

    if not results:
        await update.message.reply_text(f"😔 No products found for '{keyword}'!")
        return

    await update.message.reply_text(
        f"🔍 *Results for '{keyword}':*",
        parse_mode="Markdown"
    )
    for product in results[:5]:
        msg = (
            f"{product['emoji']} *{product['name']}*\n\n"
            f"📝 {product['description']}\n\n"
            f"🔗 [Get it here!]({product['link']})"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(update.effective_user)

    wl = wishlists.get(user_id, [])
    if not wl:
        await update.message.reply_text(
            "❤️ Your wishlist is empty!\n"
            "Use /savewishlist ProductName to save a product."
        )
        return

    wl_text = "\n".join([f"• {item}" for item in wl])
    await update.message.reply_text(
        f"❤️ *Your Wishlist:*\n\n{wl_text}",
        parse_mode="Markdown"
    )


async def cmd_savewishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(update.effective_user)

    if not context.args:
        await update.message.reply_text(
            "Usage: `/savewishlist Product Name`",
            parse_mode="Markdown"
        )
        return

    item = " ".join(context.args)
    if user_id not in wishlists:
        wishlists[user_id] = []

    if len(wishlists[user_id]) >= 10:
        await update.message.reply_text("❌ Wishlist full! Max 10 items. Remove one first.")
        return

    wishlists[user_id].append(item)
    await update.message.reply_text(f"✅ *{item}* saved to your wishlist!", parse_mode="Markdown")


async def cmd_removewishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("Usage: `/removewishlist Product Name`", parse_mode="Markdown")
        return

    item = " ".join(context.args)
    if user_id in wishlists and item in wishlists[user_id]:
        wishlists[user_id].remove(item)
        await update.message.reply_text(f"✅ *{item}* removed from wishlist!", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Item not found in wishlist!")


async def cmd_refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)

    code = get_referral_code(user.id)
    ref_count = users[user.id]["referrals"]
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username

    await update.message.reply_text(
        f"🎯 *Your Referral Link:*\n\n"
        f"`https://t.me/{bot_username}?start={code}`\n\n"
        f"👥 Friends referred: *{ref_count}*\n\n"
        f"Share this link with friends — help them get great deals!",
        parse_mode="Markdown"
    )


async def cmd_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)

    if not coupons:
        await update.message.reply_text("😔 No active coupons right now! Check back soon.")
        return

    coupon_text = ""
    for code, discount in coupons.items():
        coupon_text += f"🎟️ Code: `{code}` — *{discount}% OFF*\n"

    await update.message.reply_text(
        f"🎟️ *Active Coupons:*\n\n{coupon_text}\n"
        f"Apply these codes on the website at checkout!",
        parse_mode="Markdown"
    )


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(update.effective_user)
    subscribers.add(user_id)

    await update.message.reply_text(
        "🔔 *Subscribed!*\n\n"
        "You'll receive daily deal alerts!\n"
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
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n`/addproduct Name | Description | Link | Category | Emoji`\n\n"
            "Categories: electronics, fashion, beauty, home, books, toys, sports, general\n\n"
            "Example:\n`/addproduct boAt Earphones | Best sound quality | https://link.com | electronics | 🎧`",
            parse_mode="Markdown"
        )
        return

    text = " ".join(context.args)
    parts = [p.strip() for p in text.split("|")]

    if len(parts) < 3:
        await update.message.reply_text("❌ Format: Name | Description | Link | Category | Emoji")
        return

    product = {
        "name":        parts[0],
        "description": parts[1],
        "link":        parts[2],
        "category":    parts[3] if len(parts) > 3 else "general",
        "emoji":       parts[4] if len(parts) > 4 else "🛍️",
        "added_at":    datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    affiliate_products.append(product)
    new_products.append(product)

    # Notify subscribers
    if subscribers:
        msg = (
            f"🔔 *New Deal Alert!*\n\n"
            f"{product['emoji']} *{product['name']}*\n\n"
            f"📝 {product['description']}\n\n"
            f"🔗 [Get it here!]({product['link']})"
        )
        for sub_id in subscribers:
            try:
                await context.bot.send_message(chat_id=sub_id, text=msg, parse_mode="Markdown")
            except Exception:
                pass

    await update.message.reply_text(
        f"✅ Product added: *{product['name']}*\n"
        f"📢 Notified {len(subscribers)} subscribers!",
        parse_mode="Markdown"
    )


async def cmd_addsale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n`/addsale Name | Description | Link | Discount%`\n\n"
            "Example:\n`/addsale Nike Shoes | Best sneakers | https://link.com | 50`",
            parse_mode="Markdown"
        )
        return

    text = " ".join(context.args)
    parts = [p.strip() for p in text.split("|")]

    if len(parts) < 4:
        await update.message.reply_text("❌ Format: Name | Description | Link | Discount%")
        return

    product = {
        "name":        parts[0],
        "description": parts[1],
        "link":        parts[2],
        "discount":    parts[3],
        "emoji":       "🔥",
    }

    sale_products.append(product)
    await update.message.reply_text(f"✅ Sale product added: *{product['name']}*", parse_mode="Markdown")


async def cmd_addcoupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Usage:\n`/addcoupon CODE DISCOUNT`\n\n"
            "Example:\n`/addcoupon SAVE20 20`",
            parse_mode="Markdown"
        )
        return

    code     = context.args[0].upper()
    discount = context.args[1]
    coupons[code] = discount

    await update.message.reply_text(
        f"✅ Coupon added!\n"
        f"Code: `{code}` — {discount}% OFF",
        parse_mode="Markdown"
    )


async def cmd_removecoupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/removecoupon CODE`", parse_mode="Markdown")
        return

    code = context.args[0].upper()
    if code in coupons:
        del coupons[code]
        await update.message.reply_text(f"✅ Coupon `{code}` removed!", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Coupon not found!")


async def cmd_removeproduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    if not affiliate_products:
        await update.message.reply_text("No products to remove!")
        return

    removed = affiliate_products.pop()
    if removed in new_products:
        new_products.remove(removed)

    await update.message.reply_text(f"✅ Removed: *{removed['name']}*", parse_mode="Markdown")


async def cmd_listproducts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    if not affiliate_products:
        await update.message.reply_text("No products added yet!")
        return

    text = "📋 *All Products:*\n\n"
    for i, p in enumerate(affiliate_products, 1):
        text += f"{i}. {p['emoji']} {p['name']} — {p.get('category', 'general')}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_postall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    if not affiliate_products:
        await update.message.reply_text("No products to post!")
        return

    global post_index
    product = affiliate_products[post_index % len(affiliate_products)]
    post_index += 1

    msg = (
        f"{product['emoji']} *{product['name']}*\n\n"
        f"📝 {product['description']}\n\n"
        f"🔗 [Get it here!]({product['link']})\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🔔 Subscribe for more daily deals!\n"
        f"👉 @ecomstore4u"
    )

    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode="Markdown")
        await update.message.reply_text("✅ Posted to channel!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n`/broadcast Your message here`",
            parse_mode="Markdown"
        )
        return

    message = " ".join(context.args)
    sent = 0
    failed = 0

    for user_id in list(users.keys()):
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 *Announcement:*\n\n{message}",
                parse_mode="Markdown"
            )
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"📢 Broadcast done!\n"
        f"✅ Sent: {sent}\n"
        f"❌ Failed: {failed}"
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    await update.message.reply_text(
        f"📊 *Bot Statistics:*\n\n"
        f"👥 Total Users: {len(users)}\n"
        f"🔔 Subscribers: {len(subscribers)}\n"
        f"🛍️ Total Products: {len(affiliate_products)}\n"
        f"🔥 Sale Products: {len(sale_products)}\n"
        f"🎟️ Active Coupons: {len(coupons)}\n"
        f"❤️ Users with Wishlist: {len(wishlists)}",
        parse_mode="Markdown"
    )


async def cmd_clearproducts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    affiliate_products.clear()
    new_products.clear()
    await update.message.reply_text("✅ All products cleared!")


# ════════════════════════════════════════════
# WELCOME NEW MEMBERS (Groups only)
# ════════════════════════════════════════════

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if result.new_chat_member.status == "member":
        new_user = result.new_chat_member.user
        name = new_user.first_name or "Friend"
        await context.bot.send_message(
            chat_id=result.chat.id,
            text=(
                f"🎉 Welcome, *{name}*!\n\n"
                f"You've joined *Ecomstore4u*!\n\n"
                f"✅ Daily deals & discounts\n"
                f"✅ Amazon | Flipkart | Meesho\n\n"
                f"Type /deals to see today's best products!"
            ),
            parse_mode="Markdown"
        )


# ════════════════════════════════════════════
# SMART FAQ KEYWORD HANDLER
# ════════════════════════════════════════════

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    save_user(update.effective_user)
    user_text = update.message.text.lower()

    for keyword, answer in faq_answers.items():
        if keyword in user_text:
            await update.message.reply_text(answer)
            return

    await update.message.reply_text(
        "🤖 I didn't understand that.\n\n"
        "Try these commands:\n"
        "/deals — See products\n"
        "/faq — Common questions\n"
        "/help — All commands"
    )


# ════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # User commands
    app.add_handler(CommandHandler("start",          cmd_start))
    app.add_handler(CommandHandler("help",           cmd_help))
    app.add_handler(CommandHandler("deals",          cmd_deals))
    app.add_handler(CommandHandler("new",            cmd_new))
    app.add_handler(CommandHandler("sale",           cmd_sale))
    app.add_handler(CommandHandler("categories",     cmd_categories))
    app.add_handler(CommandHandler("search",         cmd_search))
    app.add_handler(CommandHandler("wishlist",       cmd_wishlist))
    app.add_handler(CommandHandler("savewishlist",   cmd_savewishlist))
    app.add_handler(CommandHandler("removewishlist", cmd_removewishlist))
    app.add_handler(CommandHandler("refer",          cmd_refer))
    app.add_handler(CommandHandler("coupon",         cmd_coupon))
    app.add_handler(CommandHandler("subscribe",      cmd_subscribe))
    app.add_handler(CommandHandler("unsubscribe",    cmd_unsubscribe))
    app.add_handler(CommandHandler("faq",            cmd_faq))

    # Admin commands
    app.add_handler(CommandHandler("addproduct",     cmd_addproduct))
    app.add_handler(CommandHandler("addsale",        cmd_addsale))
    app.add_handler(CommandHandler("addcoupon",      cmd_addcoupon))
    app.add_handler(CommandHandler("removecoupon",   cmd_removecoupon))
    app.add_handler(CommandHandler("removeproduct",  cmd_removeproduct))
    app.add_handler(CommandHandler("listproducts",   cmd_listproducts))
    app.add_handler(CommandHandler("postall",        cmd_postall))
    app.add_handler(CommandHandler("broadcast",      cmd_broadcast))
    app.add_handler(CommandHandler("stats",          cmd_stats))
    app.add_handler(CommandHandler("clearproducts",  cmd_clearproducts))

    # Welcome handler
    app.add_handler(ChatMemberHandler(welcome_new_member, ChatMemberHandler.CHAT_MEMBER))

    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    import time
    while True:
        try:
            main()
        except Exception as e:
            logger.error(f"Bot crashed: {e}, restarting in 5s...")
            time.sleep(5)