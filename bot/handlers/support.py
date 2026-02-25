import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /support command."""
    db = context.bot_data["db"]
    config = context.bot_data["config"]

    await db.log_action(update.effective_user.id, "support_view")

    text = (
        "💰 *Support the Project*\n\n"
        "If you find this bot useful, consider supporting its development!\n\n"
        "🔗 *EVM Address (ETH/BSC/Polygon/etc.):*\n"
        f"`{config.support_address}`\n\n"
        "You can send ETH, BNB, MATIC, USDT, USDC, or any EVM-compatible token "
        "to this address.\n\n"
        "Thank you for your support! 🙏\n\n"
        "Every contribution helps maintain the bot, pay for API access, "
        "and develop new features."
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Copy Address", callback_data="support_copy")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
            ]),
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Copy Address", callback_data="support_copy")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
            ]),
        )


async def support_copy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle copy address button - resend just the address for easy copying."""
    query = update.callback_query
    await query.answer("Address shown below for copying!")

    config = context.bot_data["config"]
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"`{config.support_address}`",
        parse_mode="Markdown",
    )
