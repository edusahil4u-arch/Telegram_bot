"""
Telegram Affiliate Marketing Bot with Supabase
================================================
"""

import logging
import os
import time
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from telegram import Update
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
BOT_TOKEN     = os.getenv("BOT_TOKEN")
CHANNEL_ID    = int(os.getenv("CHANNEL_ID", 0))
ADMIN_ID      = int(os.getenv("ADMIN_ID", 0))
SUPABASE_URL  = os.getenv("SUPABASE_URL")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set")
if CHANNEL_ID == 0:
    raise ValueError("CHANNEL_ID not set")
if ADMIN_ID == 0:
    raise ValueError("ADMIN_ID not set")
if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL not set")
if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY not set")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase client
db: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# In-memory (for referrals only)
referrals  = {}
post_index = 0

faq_answers = {
    "how to buy":  "👉 Click the product link and follow steps on the website!",
    "is it safe":  "✅ Yes! All links are verified and safe to use.",
    "discount":    "💰 Use our links to get the best prices automatically!",
    "shipping":    "🚚 Shipping info is available on each product page.",
    "refund":      "💳 Each store has its own refund policy.",
    "contact":     "📩 Send a message to our admin for help.",
    "payment":     "💳 Pay directly on the website — we dont collect payments.",
    "cod":         "📦 COD availability depends on the website.",
    "return":      "🔄 Returns are handled by the store directly.",
    "cashback":    "💸 Click our links to get automatic cashback!",
}


# ─────────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────────

def db_save_user(user):
    try:
        db.table("users").upsert({
            "user_id":  user.id,
            "name":     user.first_name or "Friend",
            "username": user.username or "",
        }).execute()
    except Exception as e:
        logger.error(f"Save user error: {e}")

def db_get_products(sale=False):
    try:
        res = db.table("products").select("*").eq("is_sale", sale).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Get products error: {e}")
        return []

def db_add_product(product):
    try:
        db.table("products").insert(product).execute()
        return True
    except Exception as e:
        logger.error(f"Add product error: {e}")
        return False

def db_remove_last_product():
    try:
        res = db.table("products").select("id").eq("is_sale", False).order("id", desc=True).limit(1).execute()
        if res.data:
            pid = res.data[0]["id"]
            db.table("products").delete().eq("id", pid).execute()
            return True
        return False
    except Exception as e:
        logger.error(f"Remove product error: {e}")
        return False

def db_get_subscribers():
    try:
        res = db.table("subscribers").select("user_id").execute()
        return [r["user_id"] for r in (res.data or [])]
    except Exception as e:
        logger.error(f"Get subscribers error: {e}")
        return []

def db_add_subscriber(user_id):
    try:
        db.table("subscribers").upsert({"user_id": user_id}).execute()
    except Exception as e:
        logger.error(f"Add subscriber error: {e}")

def db_remove_subscriber(user_id):
    try:
        db.table("subscribers").delete().eq("user_id", user_id).execute()
    except Exception as e:
        logger.error(f"Remove subscriber error: {e}")

def db_get_wishlist(user_id):
    try:
        res = db.table("wishlists").select("item").eq("user_id", user_id).execute()
        return [r["item"] for r in (res.data or [])]
    except Exception as e:
        logger.error(f"Get wishlist error: {e}")
        return []

def db_add_wishlist(user_id, item):
    try:
        db.table("wishlists").insert({"user_id": user_id, "item": item}).execute()
        return True
    except Exception as e:
        logger.error(f"Add wishlist error: {e}")
        return False

def db_remove_wishlist(user_id, item):
    try:
        db.table("wishlists").delete().eq("user_id", user_id).eq("item", item).execute()
        return True
    except Exception as e:
        logger.error(f"Remove wishlist error: {e}")
        return False

def db_get_coupons():
    try:
        res = db.table("coupons").select("*").execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Get coupons error: {e}")
        return []

def db_add_coupon(code, discount):
    try:
        db.table("coupons").upsert({"code": code, "discount": discount}).execute()
        return True
    except Exception as e:
        logger.error(f"Add coupon error: {e}")
        return False

def db_remove_coupon(code):
    try:
        db.table("coupons").delete().eq("code", code).execute()
        return True
    except Exception as e:
        logger.error(f"Remove coupon error: {e}")
        return False

def db_get_stats():
    try:
        users_count = db.table("users").select("user_id", count="exact").execute().count
        subs_count  = db.table("subscribers").select("user_id", count="exact").execute().count
        prod_count  = db.table("products").select("id", count="exact").eq("is_sale", False).execute().count
        sale_count  = db.table("products").select("id", count="exact").eq("is_sale", True).execute().count
        coup_count  = db.table("coupons").select("code", count="exact").execute().count
        return users_count, subs_count, prod_count, sale_count, coup_count
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return 0, 0, 0, 0, 0

def get_referral_code(user_id):
    code = f"REF{user_id}"
    referrals[code] = user_id
    return code


# ════════════════════════════════════════════
# USER COMMANDS
# ════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_save_user(user)

    if context.args:
        ref_code = context.args[0]
        if ref_code in referrals and referrals[ref_code] != user.id:
            try:
                ref_id = referrals[ref_code]
                res = db.table("users").select("referrals").eq("user_id", ref_id).execute()
                if res.data:
                    current = res.data[0]["referrals"] or 0
                    db.table("users").update({"referrals": current + 1}).eq("user_id", ref_id).execute()
            except Exception:
                pass

    name = user.first_name or "Friend"
    await update.message.reply_text(
        f"👋 Welcome, *{name}!*\n\n"
        f"🛍️ *Ecomstore4u Deals Bot*\n\n"
        f"Best deals from Amazon, Flipkart & Meesho!\n\n"
        f"📋 *Commands:*\n"
        f"/deals — Todays best products\n"
        f"/new — Newly added products\n"
        f"/sale — Flash sales 🔥\n"
        f"/categories — Browse by category\n"
        f"/search — Search products\n"
        f"/wishlist — Your saved products\n"
        f"/coupon — Discount coupons\n"
        f"/refer — Get your referral link\n"
        f"/subscribe — Daily deal alerts\n"
        f"/faq — Common questions\n"
        f"/help — All commands",
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
        "/removewishlist — Remove from wishlist\n"
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
    db_save_user(update.effective_user)
    products = db_get_products(sale=False)

    if not products:
        await update.message.reply_text(
            "😔 No products yet! Check back soon.\n"
            "Subscribe with /subscribe to get alerts!"
        )
        return

    await update.message.reply_text("🔥 *Todays Best Deals:*", parse_mode="Markdown")
    for p in products[-10:]:
        msg = (
            f"{p.get('emoji','🛍️')} *{p['name']}*\n\n"
            f"📝 {p['description']}\n"
            f"🏷️ Category: {p.get('category','General')}\n\n"
            f"🔗 [Get it here!]({p['link']})"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_save_user(update.effective_user)
    try:
        res = db.table("products").select("*").eq("is_sale", False).order("id", desc=True).limit(5).execute()
        products = res.data or []
    except Exception:
        products = []

    if not products:
        await update.message.reply_text("😔 No new products yet!")
        return

    await update.message.reply_text("🆕 *Newly Added Products:*", parse_mode="Markdown")
    for p in products:
        msg = (
            f"{p.get('emoji','🛍️')} *{p['name']}*\n\n"
            f"📝 {p['description']}\n\n"
            f"🔗 [Get it here!]({p['link']})"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_save_user(update.effective_user)
    products = db_get_products(sale=True)

    if not products:
        await update.message.reply_text("😔 No flash sales right now!")
        return

    await update.message.reply_text("🔥 *Flash Sales & Hot Deals:*", parse_mode="Markdown")
    for p in products:
        msg = (
            f"⚡ *{p['name']}*\n\n"
            f"📝 {p['description']}\n"
            f"💰 *{p.get('discount','')}% OFF!*\n\n"
            f"🔗 [Grab the deal!]({p['link']})"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_save_user(update.effective_user)
    await update.message.reply_text(
        "📂 *Browse by Category:*\n\n"
        "📱 Electronics\n"
        "👗 Fashion\n"
        "💄 Beauty\n"
        "🏠 Home & Kitchen\n"
        "📚 Books\n"
        "🧸 Toys & Kids\n"
        "🏋️ Sports\n"
        "🛍️ General\n\n"
        "Type: `/search electronics` to filter!",
        parse_mode="Markdown"
    )


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_save_user(update.effective_user)
    if not context.args:
        await update.message.reply_text(
            "🔍 Usage: `/search keyword`\nExample: `/search earphones`",
            parse_mode="Markdown"
        )
        return

    keyword = " ".join(context.args).lower()
    try:
        res = db.table("products").select("*").execute()
        all_products = res.data or []
        results = [
            p for p in all_products
            if keyword in p["name"].lower()
            or keyword in p["description"].lower()
            or keyword in p.get("category", "").lower()
        ]
    except Exception:
        results = []

    if not results:
        await update.message.reply_text(f"😔 No products found for '{keyword}'!")
        return

    await update.message.reply_text(f"🔍 *Results for '{keyword}':*", parse_mode="Markdown")
    for p in results[:5]:
        msg = (
            f"{p.get('emoji','🛍️')} *{p['name']}*\n\n"
            f"📝 {p['description']}\n\n"
            f"🔗 [Get it here!]({p['link']})"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db_save_user(update.effective_user)
    wl = db_get_wishlist(user_id)

    if not wl:
        await update.message.reply_text(
            "❤️ Your wishlist is empty!\n"
            "Use /savewishlist ProductName to save."
        )
        return

    wl_text = "\n".join([f"• {item}" for item in wl])
    await update.message.reply_text(f"❤️ *Your Wishlist:*\n\n{wl_text}", parse_mode="Markdown")


async def cmd_savewishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db_save_user(update.effective_user)

    if not context.args:
        await update.message.reply_text("Usage: `/savewishlist Product Name`", parse_mode="Markdown")
        return

    item = " ".join(context.args)
    wl = db_get_wishlist(user_id)

    if len(wl) >= 10:
        await update.message.reply_text("❌ Wishlist full! Max 10 items.")
        return

    db_add_wishlist(user_id, item)
    await update.message.reply_text(f"✅ *{item}* saved to wishlist!", parse_mode="Markdown")


async def cmd_removewishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: `/removewishlist Product Name`", parse_mode="Markdown")
        return

    item = " ".join(context.args)
    db_remove_wishlist(user_id, item)
    await update.message.reply_text(f"✅ *{item}* removed from wishlist!", parse_mode="Markdown")


async def cmd_refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_save_user(user)
    code = get_referral_code(user.id)
    bot_info = await context.bot.get_me()

    try:
        res = db.table("users").select("referrals").eq("user_id", user.id).execute()
        ref_count = res.data[0]["referrals"] if res.data else 0
    except Exception:
        ref_count = 0

    await update.message.reply_text(
        f"🎯 *Your Referral Link:*\n\n"
        f"`https://t.me/{bot_info.username}?start={code}`\n\n"
        f"👥 Friends referred: *{ref_count}*\n\n"
        f"Share with friends to get great deals!",
        parse_mode="Markdown"
    )


async def cmd_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_save_user(update.effective_user)
    coupons = db_get_coupons()

    if not coupons:
        await update.message.reply_text("😔 No active coupons right now!")
        return

    coupon_text = ""
    for c in coupons:
        coupon_text += f"🎟️ Code: `{c['code']}` — *{c['discount']}% OFF*\n"

    await update.message.reply_text(
        f"🎟️ *Active Coupons:*\n\n{coupon_text}\nApply at checkout!",
        parse_mode="Markdown"
    )


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db_save_user(update.effective_user)
    db_add_subscriber(user_id)
    await update.message.reply_text(
        "🔔 *Subscribed!*\n\nYou will receive daily deal alerts!\nType /unsubscribe to stop.",
        parse_mode="Markdown"
    )


async def cmd_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db_remove_subscriber(user_id)
    await update.message.reply_text(
        "🔕 *Unsubscribed!*\n\nNo more alerts.\nType /subscribe to turn back on.",
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
            "Example:\n`/addproduct boAt Earphones | Best sound | https://link.com | electronics | 🎧`",
            parse_mode="Markdown"
        )
        return

    text = " ".join(context.args)
    parts = [p.strip() for p in text.split("|")]

    if len(parts) < 3:
        await update.message.reply_text("❌ Format: Name | Description | Link")
        return

    product = {
        "name":        parts[0],
        "description": parts[1],
        "link":        parts[2],
        "category":    parts[3] if len(parts) > 3 else "general",
        "emoji":       parts[4] if len(parts) > 4 else "🛍️",
        "is_sale":     False,
    }

    if db_add_product(product):
        subscribers = db_get_subscribers()
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
            f"✅ Product added: *{product['name']}*\n📢 Notified {len(subscribers)} subscribers!",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Error adding product!")


async def cmd_addsale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n`/addsale Name | Description | Link | Discount%`",
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
        "is_sale":     True,
        "category":    "sale",
    }

    if db_add_product(product):
        await update.message.reply_text(f"✅ Sale added: *{product['name']}*", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Error adding sale!")


async def cmd_addcoupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: `/addcoupon CODE DISCOUNT`", parse_mode="Markdown")
        return

    code     = context.args[0].upper()
    discount = context.args[1]

    if db_add_coupon(code, discount):
        await update.message.reply_text(f"✅ Coupon added!\nCode: `{code}` — {discount}% OFF", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Error adding coupon!")


async def cmd_removecoupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/removecoupon CODE`", parse_mode="Markdown")
        return

    code = context.args[0].upper()
    db_remove_coupon(code)
    await update.message.reply_text(f"✅ Coupon `{code}` removed!", parse_mode="Markdown")


async def cmd_removeproduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    if db_remove_last_product():
        await update.message.reply_text("✅ Last product removed!")
    else:
        await update.message.reply_text("❌ No products to remove!")


async def cmd_listproducts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    products = db_get_products(sale=False)
    if not products:
        await update.message.reply_text("No products added yet!")
        return

    text = "📋 *All Products:*\n\n"
    for i, p in enumerate(products, 1):
        text += f"{i}. {p.get('emoji','🛍️')} {p['name']} — {p.get('category','general')}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_postall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    products = db_get_products(sale=False)
    if not products:
        await update.message.reply_text("No products to post!")
        return

    global post_index
    product = products[post_index % len(products)]
    post_index += 1

    msg = (
        f"{product.get('emoji','🛍️')} *{product['name']}*\n\n"
        f"📝 {product['description']}\n\n"
        f"🔗 [Get it here!]({product['link']})\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🔔 Join for more daily deals!\n"
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
        await update.message.reply_text("Usage: `/broadcast Your message here`", parse_mode="Markdown")
        return

    message = " ".join(context.args)
    sent = 0
    failed = 0

    try:
        res = db.table("users").select("user_id").execute()
        all_users = [r["user_id"] for r in (res.data or [])]
    except Exception:
        all_users = []

    for user_id in all_users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 *Announcement:*\n\n{message}",
                parse_mode="Markdown"
            )
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(f"📢 Broadcast done!\n✅ Sent: {sent}\n❌ Failed: {failed}")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    users_c, subs_c, prod_c, sale_c, coup_c = db_get_stats()
    await update.message.reply_text(
        f"📊 *Bot Statistics:*\n\n"
        f"👥 Total Users: {users_c}\n"
        f"🔔 Subscribers: {subs_c}\n"
        f"🛍️ Total Products: {prod_c}\n"
        f"🔥 Sale Products: {sale_c}\n"
        f"🎟️ Active Coupons: {coup_c}",
        parse_mode="Markdown"
    )


async def cmd_clearproducts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only!")
        return

    try:
        db.table("products").delete().eq("is_sale", False).execute()
        await update.message.reply_text("✅ All products cleared!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


# ════════════════════════════════════════════
# WELCOME & MESSAGE HANDLER
# ════════════════════════════════════════════

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if result.new_chat_member.status == "member":
        name = result.new_chat_member.user.first_name or "Friend"
        await context.bot.send_message(
            chat_id=result.chat.id,
            text=(
                f"Welcome, *{name}*!\n\n"
                f"You have joined *Ecomstore4u*!\n\n"
                f"Daily deals from Amazon, Flipkart & Meesho!\n\n"
                f"Type /deals to see todays best products!"
            ),
            parse_mode="Markdown"
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    db_save_user(update.effective_user)
    user_text = update.message.text.lower()

    for keyword, answer in faq_answers.items():
        if keyword in user_text:
            await update.message.reply_text(answer)
            return

    await update.message.reply_text(
        "I did not understand that.\n\n"
        "Try:\n/deals - See products\n/faq - Common questions\n/help - All commands"
    )


# ════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()

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
    app.add_handler(ChatMemberHandler(welcome_new_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            logger.error(f"Bot crashed: {e}, restarting in 5s...")
            time.sleep(5)
