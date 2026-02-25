import logging
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

logger = logging.getLogger(__name__)

# Conversation states
WAITING_PASSWORD = 1


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin command - check if user is already admin or ask for password."""
    db = context.bot_data["db"]
    user = update.effective_user
    await db.upsert_user(user.id, user.username, user.first_name)

    user_data = await db.get_user(user.id)
    if user_data and user_data.get("is_admin"):
        await show_admin_panel(update, context)
        return ConversationHandler.END

    await update.message.reply_text(
        "🔐 *Admin Panel*\n\nPlease enter the admin password:",
        parse_mode="Markdown",
    )
    return WAITING_PASSWORD


async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify admin password."""
    config = context.bot_data["config"]
    db = context.bot_data["db"]
    password = update.message.text.strip()

    # Delete the password message for security
    try:
        await update.message.delete()
    except Exception:
        pass

    if password == config.admin_password:
        await db.set_admin(update.effective_user.id, True)
        await db.log_action(update.effective_user.id, "admin_login_success")
        await show_admin_panel(update, context)
    else:
        await db.log_action(update.effective_user.id, "admin_login_failed")
        await update.message.reply_text("❌ Wrong password. Access denied.")

    return ConversationHandler.END


async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the admin panel."""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Run Summary Now", callback_data="admin_run_summary")],
        [InlineKeyboardButton("📊 User Analytics", callback_data="admin_analytics")],
        [InlineKeyboardButton("🪙 Manage Coins", callback_data="admin_coins")],
        [InlineKeyboardButton("🤖 AI Templates", callback_data="admin_templates")],
        [InlineKeyboardButton("🧠 AI Memory", callback_data="admin_memory")],
        [InlineKeyboardButton("⚙️ Bot Settings", callback_data="admin_settings")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
    ])

    text = (
        "🔐 *Admin Panel*\n\n"
        "Welcome to the admin dashboard. Choose an action:"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=keyboard,
        )
    else:
        msg = update.message or update.effective_message
        if msg:
            await msg.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin panel button clicks."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    user_data = await db.get_user(update.effective_user.id)
    if not user_data or not user_data.get("is_admin"):
        await query.edit_message_text("❌ Unauthorized. Use /admin to log in.")
        return

    action = query.data

    if action == "admin_run_summary":
        await run_summary_admin(update, context)
    elif action == "admin_analytics":
        await show_analytics(update, context)
    elif action == "admin_coins":
        await show_coins_admin(update, context)
    elif action == "admin_templates":
        await show_templates_admin(update, context)
    elif action == "admin_memory":
        await show_memory_admin(update, context)
    elif action == "admin_settings":
        await show_settings_admin(update, context)
    elif action == "admin_panel":
        await show_admin_panel(update, context)


async def run_summary_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Run summary for all coins immediately."""
    query = update.callback_query
    db = context.bot_data["db"]

    await db.log_action(update.effective_user.id, "admin_run_summary")

    coins = await db.get_active_coins()
    if not coins:
        await query.edit_message_text("❌ No active coins to summarize.")
        return

    await query.edit_message_text(
        "⏳ *Running summary for all coins...*\n"
        "This may take a minute...",
        parse_mode="Markdown",
    )

    from bot.handlers.summary import generate_coin_summary

    for coin in coins:
        try:
            summary = await generate_coin_summary(context, coin, "admin-test")
            header = f"📊 *{coin['name']} ({coin['symbol']}) — Admin Test*\n{'━' * 30}\n\n"
            full_msg = header + summary

            if len(full_msg) > 4000:
                parts = [full_msg[i:i+4000] for i in range(0, len(full_msg), 4000)]
                for part in parts:
                    await context.bot.send_message(
                        chat_id=query.message.chat_id, text=part, parse_mode="Markdown",
                    )
            else:
                await context.bot.send_message(
                    chat_id=query.message.chat_id, text=full_msg, parse_mode="Markdown",
                )
        except Exception as e:
            logger.error(f"Admin summary failed for {coin['symbol']}: {e}")
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"❌ Error for {coin['symbol']}: {str(e)[:200]}",
            )

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="✅ Admin summary test complete!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")],
        ]),
    )


async def show_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user analytics."""
    query = update.callback_query
    db = context.bot_data["db"]

    analytics = await db.get_analytics()

    top_actions_text = ""
    for act in analytics["top_actions_24h"]:
        top_actions_text += f"  • {act['action']}: {act['cnt']}x\n"
    if not top_actions_text:
        top_actions_text = "  No actions in the last 24h\n"

    text = (
        "📊 *User Analytics*\n\n"
        f"👥 *Total Users:* {analytics['total_users']}\n"
        f"🟢 *Active (24h):* {analytics['active_24h']}\n"
        f"📅 *Active (7d):* {analytics['active_7d']}\n"
        f"📝 *Total Summaries:* {analytics['total_summaries']}\n\n"
        f"🔝 *Top Actions (24h):*\n{top_actions_text}"
    )

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_analytics")],
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")],
        ]),
    )


async def show_coins_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show coin management panel."""
    query = update.callback_query
    db = context.bot_data["db"]

    coins = await db.get_all_coins()
    coin_lines = []
    for c in coins:
        status = "🟢" if c["active"] else "🔴"
        coin_lines.append(f"{status} {c['name']} ({c['symbol']})")

    text = (
        "🪙 *Coin Management*\n\n"
        + "\n".join(coin_lines) + "\n\n"
        "Use /dev panel to add/remove/toggle coins."
    )

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")],
        ]),
    )


async def show_templates_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show AI templates."""
    query = update.callback_query
    db = context.bot_data["db"]

    templates = await db.get_all_templates()
    text = "🤖 *AI Templates*\n\n"
    for tpl in templates:
        preview = tpl["template"][:100] + "..." if len(tpl["template"]) > 100 else tpl["template"]
        status = "🟢" if tpl["active"] else "🔴"
        text += f"{status} *{tpl['name']}*\n`{preview}`\n\n"

    text += "\nUse /dev panel to edit templates."

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")],
        ]),
    )


async def show_memory_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show AI memory entries."""
    query = update.callback_query
    db = context.bot_data["db"]

    memories = await db.get_all_memory()
    text = "🧠 *AI Memory*\n\n"
    for mem in memories:
        text += f"• *{mem['key']}:* {mem['value']}\n"

    if not memories:
        text += "No memory entries yet."

    text += "\n\nUse /dev panel to manage AI memory."

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")],
        ]),
    )


async def show_settings_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot settings."""
    query = update.callback_query
    config = context.bot_data["config"]

    text = (
        "⚙️ *Bot Settings*\n\n"
        f"🤖 AI Model: `{config.ai_model}`\n"
        f"🌅 Morning Report: 8:00 AM MSK (UTC+3)\n"
        f"🌙 Evening Report: 11:00 PM MSK (UTC+3)\n"
        f"💰 Support Address: `{config.support_address}`\n\n"
        f"📡 CoinMarketCap: {'✅' if config.coinmarketcap_api_key else '❌'}\n"
        f"🐦 Twitter/Apify: {'✅' if config.apify_api_key else '❌'}\n"
        f"🤖 OpenRouter AI: {'✅' if config.openrouter_api_key else '❌'}\n"
    )

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")],
        ]),
    )
