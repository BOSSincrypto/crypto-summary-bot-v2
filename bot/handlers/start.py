import logging
from telegram import (
    BotCommand,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Persistent reply-keyboard shown at the bottom of every chat
PERSISTENT_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("💰 Price"), KeyboardButton("📊 Summary")],
        [KeyboardButton("📰 News"), KeyboardButton("ℹ️ Help")],
        [KeyboardButton("💎 Support Project")],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

# Commands to register with BotFather (shown in the / menu)
BOT_COMMANDS = [
    BotCommand("start", "Main menu"),
    BotCommand("price", "Quick price check"),
    BotCommand("summary", "AI-powered summary"),
    BotCommand("help", "Help & tips"),
    BotCommand("support", "Support the project"),
    BotCommand("admin", "Admin panel"),
    BotCommand("dev", "Developer panel"),
]


async def set_bot_commands(application):
    """Register slash-commands with Telegram so they appear in the / menu."""
    await application.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Bot commands registered with Telegram")


def get_main_menu_keyboard():
    """Build the main menu inline keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Get Summary", callback_data="menu_summary")],
        [InlineKeyboardButton("📰 Latest News", callback_data="menu_news")],
        [
            InlineKeyboardButton("💰 Support Project", callback_data="menu_support"),
            InlineKeyboardButton("ℹ️ Help & Tips", callback_data="menu_help"),
        ],
        [InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings")],
    ])


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    db = context.bot_data["db"]
    user = update.effective_user

    # Register / update user
    await db.upsert_user(user.id, user.username, user.first_name)
    await db.log_action(user.id, "start")

    welcome_text = (
        f"👋 Welcome, {user.first_name}!\n\n"
        "🤖 *Crypto Summary Bot v2*\n\n"
        "I provide AI-powered daily summaries for cryptocurrencies, "
        "analyzing market data, DEX activity, and social media sentiment.\n\n"
        "📅 *Scheduled Reports:*\n"
        "• 🌅 Morning summary — 8:00 AM MSK\n"
        "• 🌙 Evening summary — 11:00 PM MSK\n\n"
        "📈 *Currently tracking:* OWB, Rainbow (RNBW) on Base chain\n"
        "💱 All prices in USD/USDC from largest DEX pools\n\n"
        "Choose an option below to get started:"
    )

    # Send with both the persistent bottom keyboard and inline menu
    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=PERSISTENT_KEYBOARD,
    )
    # Follow up with inline menu buttons
    await update.message.reply_text(
        "Choose an option:",
        reply_markup=get_main_menu_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    db = context.bot_data["db"]
    await db.log_action(update.effective_user.id, "help")

    help_text = (
        "ℹ️ *Help & Tips*\n\n"
        "📌 *Commands:*\n"
        "/start — Main menu\n"
        "/summary — Get current summary for all coins\n"
        "/price — Quick price check\n"
        "/help — This help message\n"
        "/support — Support the project\n"
        "/admin — Admin panel (password required)\n"
        "/dev — Developer panel\n\n"
        "📌 *How it works:*\n"
        "1️⃣ The bot collects data from CoinMarketCap, DexScreener, and Twitter\n"
        "2️⃣ An AI agent analyzes all the data\n"
        "3️⃣ You receive a comprehensive summary\n\n"
        "📌 *Tips:*\n"
        "• Summaries are sent automatically at 8 AM and 11 PM MSK\n"
        "• Use /summary anytime for an on-demand report\n"
        "• The AI learns and improves over time\n"
        "• Admins can run test summaries from the admin panel\n\n"
        "📌 *Data Sources:*\n"
        "• 💹 CoinMarketCap — Market prices & volume\n"
        "• 📊 DexScreener — DEX pools on Base chain (USD/USDC)\n"
        "• 🔗 BaseScan — On-chain token data\n"
        "• 🐦 Twitter/X — Social sentiment & news\n"
        "• 🤖 AI — Google Gemma via OpenRouter\n\n"
        "💡 *Tip:* The bot tracks buy/sell pressure, volume changes, "
        "and significant price movements to give you actionable insights!"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            help_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")]
            ]),
        )
    else:
        await update.message.reply_text(
            help_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")]
            ]),
        )


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle settings menu."""
    query = update.callback_query
    await query.answer()

    settings_text = (
        "⚙️ *Settings*\n\n"
        "🔔 *Notifications:* Enabled\n"
        "📅 *Morning Report:* 8:00 AM MSK\n"
        "🌙 *Evening Report:* 11:00 PM MSK\n\n"
        "Currently, summaries are sent automatically to all subscribers.\n"
        "More customization options coming soon!"
    )

    await query.edit_message_text(
        settings_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")]
        ]),
    )


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to main menu."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    text = (
        f"👋 Welcome back, {user.first_name}!\n\n"
        "🤖 *Crypto Summary Bot v2*\n\n"
        "Choose an option:"
    )

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(),
    )


async def keyboard_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route persistent-keyboard button presses to the correct handler.

    The bottom keyboard sends plain text messages like "💰 Price".
    This handler maps them to the same logic as the slash commands.
    """
    from bot.handlers.summary import price_command, summary_command, news_command_text
    from bot.handlers.support import support_command as _support_command

    text = update.message.text.strip()

    if text == "💰 Price":
        await price_command(update, context)
    elif text == "📊 Summary":
        await summary_command(update, context)
    elif text == "📰 News":
        await news_command_text(update, context)
    elif text == "ℹ️ Help":
        await help_command(update, context)
    elif text == "💎 Support Project":
        await _support_command(update, context)
    else:
        await update.message.reply_text("Use the buttons below or type a /command.")
