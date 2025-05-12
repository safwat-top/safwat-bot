import logging
import random
from datetime import datetime, timedelta
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

ADMIN_ID = 7419187969
active_users = {}
pending_users = {}
user_state = {}
last_signal_time = {}
admin_session = {}

ASSETS = [
    "USD/EGP", "BRL/USD", "USD/TRY", "USD/PKR", "USD/PHP", "USD/INR",
    "USD/ARS", "USD/MXN", "NZD/JPY", "USD/DZD", "USD/BDT", "USD/COP",
    "USD/BRL", "USD/NGN", "USD/ZAR", "USD/CHF", "NZD/CAD"
]

SIGNAL_TYPES = ["CALL", "PUT"]

logging.basicConfig(level=logging.INFO)

def is_admin(user_id):
    return user_id == ADMIN_ID

def parse_duration(text):
    if text.endswith("h"):
        return timedelta(hours=int(text[:-1]))
    elif text.endswith("d"):
        return timedelta(days=int(text[:-1]))
    elif text.endswith("w"):
        return timedelta(weeks=int(text[:-1]))
    elif text == "perm":
        return "permanent"
    return None

def format_time(dt):
    return dt.strftime('%H:%M')

def generate_signal(asset):
    now = datetime.now(pytz.timezone("Africa/Cairo"))
    direction = random.choice(SIGNAL_TYPES)
    delay = random.randint(1, 2)
    signal_time = now + timedelta(minutes=delay)
    return f"📊 Signal: {asset} ➚ {format_time(signal_time)} {direction}"

def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔁 Start Again")]
    ], resize_keyboard=True)

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔄 Activate"), KeyboardButton("🔒 Block")],
        [KeyboardButton("📢 Broadcast"), KeyboardButton("👤 Users")]
    ], resize_keyboard=True)

def get_asset_keyboard():
    rows = [[KeyboardButton(asset)] for asset in ASSETS]
    return ReplyKeyboardMarkup(rows + [[KeyboardButton("✅ Confirm"), KeyboardButton("➕ Add Another")]], resize_keyboard=True)

def get_duration_keyboard(user_id):
    durations = [
        ["1h", "3h", "6h", "12h"],
        ["1d", "3d", "1w", "2w"],
        ["4w", "perm"]
    ]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(d, callback_data=f"duration_{user_id}_{d}") for d in row]
        for row in durations
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    full_name = update.effective_user.full_name
    now = datetime.now(pytz.timezone("Africa/Cairo"))

    if is_admin(user_id):
        await update.message.reply_text("👑 Welcome back, Safwat!", reply_markup=get_admin_keyboard())
        return

    info = active_users.get(user_id)
    if not info:
        pending_users[user_id] = full_name
        await update.message.reply_text(
            "👑 Welcome to Safwat's bot!\nWorks with martingale system.\nPlatform: Quotex (OTC)\nTime: Egypt\nContact: @T_Q4M",
            reply_markup=get_main_keyboard()
        )
        await update.message.reply_text("⛔ Please wait for activation by the owner 👑", reply_markup=get_main_keyboard())
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"New user: {full_name} | ID: {user_id}")
        return

    if info["until"] != "permanent" and now > info["until"]:
        await update.message.reply_text("⛔ Your subscription has expired.", reply_markup=get_main_keyboard())
        return

    if user_id in last_signal_time:
        if now - last_signal_time[user_id] < timedelta(minutes=2):
            await update.message.reply_text("⏱️ Wait 2 minutes before next signal.", reply_markup=get_main_keyboard())
            return

    user_state[user_id] = {"step": "choose", "assets": []}
    await update.message.reply_text("Choose asset(s):", reply_markup=get_asset_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    now = datetime.now(pytz.timezone("Africa/Cairo"))

    if is_admin(user_id):
        state = admin_session.get(user_id)
        if state:
            if state["action"] == "activate":
                try:
                    target_id = int(text)
                    admin_session[user_id] = {"action": "await_duration", "target_id": target_id}
                    await update.message.reply_text(
                        f"🕒 Choose duration for {target_id}:", reply_markup=get_duration_keyboard(target_id))
                except:
                    await update.message.reply_text("❗ Invalid ID.")
            elif state["action"] == "block":
                try:
                    target_id = int(text)
                    active_users.pop(target_id, None)
                    await update.message.reply_text(f"🚫 Blocked user {target_id}")
                except:
                    await update.message.reply_text("❗ Invalid ID.")
                admin_session.pop(user_id, None)
            elif state["action"] == "broadcast":
                for uid in active_users:
                    try: await context.bot.send_message(chat_id=uid, text=text)
                    except: pass
                await update.message.reply_text("✅ Broadcast sent.")
                admin_session.pop(user_id, None)
        else:
            if text.lower() == "safwat":
                await update.message.reply_text("📋 Admin Menu:", reply_markup=get_admin_keyboard())
            elif text == "🔄 Activate":
                admin_session[user_id] = {"action": "activate"}
                await update.message.reply_text("📥 Send user ID to activate.")
            elif text == "🔒 Block":
                admin_session[user_id] = {"action": "block"}
                await update.message.reply_text("📥 Send user ID to block.")
            elif text == "📢 Broadcast":
                admin_session[user_id] = {"action": "broadcast"}
                await update.message.reply_text("✏️ Send the message to broadcast.")
            elif text == "👤 Users":
                if not active_users:
                    await update.message.reply_text("❌ No users.")
                    return
                msg = "\n".join([f"{v.get('name','User')} (ID: {uid})" for uid, v in active_users.items()])
                await update.message.reply_text("✅ Active Users:\n" + msg)
    else:
        state = user_state.get(user_id)
        if text == "🔁 Start Again":
            return await start(update, context)
        if not state:
            return await update.message.reply_text("❗ Press '🔁 Start Again' to begin.", reply_markup=get_main_keyboard())

        if state["step"] == "choose":
            if text == "✅ Confirm":
                if not state["assets"]:
                    await update.message.reply_text("❗ Choose at least 1 asset.", reply_markup=get_asset_keyboard())
                    return
                signals = [generate_signal(asset) for asset in state["assets"]]
                tip = (
                    "\n\n⚠️ Avoid trading during news\n"
                    "- Don't enter against trend/momentum\n"
                    "- Avoid doji/reversal candles\n"
                    "- Stay away from round numbers like .00\n\n"
                    "📈 Bot helps you — but always manage risk!"
                )
                await update.message.reply_text("\n\n".join(signals) + tip, reply_markup=get_main_keyboard())
                last_signal_time[user_id] = now
                user_state.pop(user_id)
            elif text == "➕ Add Another":
                await update.message.reply_text("Choose more:", reply_markup=get_asset_keyboard())
            elif text in ASSETS:
                if text not in state["assets"]:
                    state["assets"].append(text)
                    await update.message.reply_text(f"✔️ Added: {text}", reply_markup=get_asset_keyboard())

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    if data.startswith("duration_"):
        _, uid, dur = data.split("_")
        uid = int(uid)
        duration = parse_duration(dur)
        until = "permanent" if duration == "permanent" else datetime.now(pytz.timezone("Africa/Cairo")) + duration
        active_users[uid] = {"until": until, "name": f"User {uid}"}
        await context.bot.send_message(chat_id=uid, text="✅ Your subscription is now active!")
        await query.edit_message_text(f"✅ Activated user {uid} for {dur}")
        admin_session.pop(query.from_user.id, None)

def main():
    app = ApplicationBuilder().token("7548370715:AAHaCndgq8ZhIGCVzGr3hbgHmq-6q61V-IM").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()

if __name__ == "__main__":
    main()















