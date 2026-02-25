import logging
import os
import sys
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    ConversationHandler,
    filters,
)

from bot.config import Config
from bot.database import Database
from bot.services.coinmarketcap import CoinMarketCapService
from bot.services.dexscreener import DexScreenerService
from bot.services.twitter import TwitterService
from bot.services.ai_agent import AIAgent
from bot.services.crypto_news import CryptoNewsService
from bot.handlers.start import (
    start_command,
    help_command,
    settings_callback,
    main_menu_callback,
    set_bot_commands,
    keyboard_button_handler,
)
from bot.handlers.summary import (
    summary_command,
    summary_menu_callback,
    summary_callback,
    price_command,
    news_callback,
)
from bot.handlers.admin import (
    admin_command,
    check_password,
    admin_callback,
    WAITING_PASSWORD,
)
from bot.handlers.developer import (
    dev_command,
    dev_check_password,
    dev_callback,
    toggle_coin_callback,
    remove_coin_callback,
    view_template_callback,
    add_memory_callback,
    delete_memory_callback,
    handle_dev_text_input,
    DEV_WAITING_PASSWORD,
)
from bot.handlers.support import (
    support_command,
    support_copy_callback,
)
from bot.scheduler import setup_schedules

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application: Application):
    """Initialize services after the application starts."""
    config = application.bot_data["config"]

    # Initialize database
    db = Database(config.db_path)
    await db.init()
    application.bot_data["db"] = db

    # Initialize services
    application.bot_data["cmc"] = CoinMarketCapService(config.coinmarketcap_api_key)
    application.bot_data["dex"] = DexScreenerService()
    application.bot_data["twitter"] = TwitterService(config.apify_api_key)
    application.bot_data["crypto_news"] = CryptoNewsService()
    application.bot_data["ai"] = AIAgent(config.openrouter_api_key, config.ai_model)

    # Register slash-commands with Telegram (shown in the / menu)
    await set_bot_commands(application)

    # Set up scheduled jobs
    setup_schedules(application.job_queue)

    logger.info("Bot initialized successfully!")
    logger.info(f"AI Model: {config.ai_model}")
    logger.info(f"CMC API: {'configured' if config.coinmarketcap_api_key else 'not set'}")
    logger.info(f"Apify API: {'configured' if config.apify_api_key else 'not set'}")
    logger.info(f"OpenRouter API: {'configured' if config.openrouter_api_key else 'not set'}")


async def post_shutdown(application: Application):
    """Clean up on shutdown."""
    db = application.bot_data.get("db")
    if db:
        await db.close()
    logger.info("Bot shut down gracefully.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again later."
            )
        except Exception:
            pass


def create_app(config: Config) -> Application:
    """Create and configure the Telegram bot application."""
    builder = Application.builder().token(config.telegram_token)
    builder.post_init(post_init)
    builder.post_shutdown(post_shutdown)

    application = builder.build()
    application.bot_data["config"] = config

    # --- Conversation handler for /admin ---
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_command)],
        states={
            WAITING_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, check_password)
            ],
        },
        fallbacks=[CommandHandler("admin", admin_command)],
        conversation_timeout=60,
    )

    # --- Conversation handler for /dev ---
    dev_conv = ConversationHandler(
        entry_points=[CommandHandler("dev", dev_command)],
        states={
            DEV_WAITING_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, dev_check_password)
            ],
        },
        fallbacks=[CommandHandler("dev", dev_command)],
        conversation_timeout=60,
    )

    # --- Register handlers ---

    # Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("summary", summary_command))
    application.add_handler(CommandHandler("price", price_command))
    application.add_handler(CommandHandler("support", support_command))
    application.add_handler(admin_conv)
    application.add_handler(dev_conv)

    # Callback queries - main menu
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^menu_main$"))
    application.add_handler(CallbackQueryHandler(help_command, pattern="^menu_help$"))
    application.add_handler(CallbackQueryHandler(settings_callback, pattern="^menu_settings$"))
    application.add_handler(CallbackQueryHandler(summary_menu_callback, pattern="^menu_summary$"))
    application.add_handler(CallbackQueryHandler(news_callback, pattern="^menu_news$"))
    application.add_handler(CallbackQueryHandler(support_command, pattern="^menu_support$"))

    # Callback queries - summary
    application.add_handler(CallbackQueryHandler(summary_callback, pattern="^summary_"))

    # Callback queries - admin
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))

    # Callback queries - developer
    application.add_handler(CallbackQueryHandler(dev_callback, pattern="^dev_(add_coin|manage_coins|edit_templates|manage_memory|teach_ai|system_stats|panel)$"))
    application.add_handler(CallbackQueryHandler(toggle_coin_callback, pattern="^dev_toggle_"))
    application.add_handler(CallbackQueryHandler(remove_coin_callback, pattern="^dev_remove_"))
    application.add_handler(CallbackQueryHandler(view_template_callback, pattern="^dev_tpl_"))
    application.add_handler(CallbackQueryHandler(add_memory_callback, pattern="^dev_add_memory$"))
    application.add_handler(CallbackQueryHandler(delete_memory_callback, pattern="^dev_mem_del_"))

    # Callback queries - support
    application.add_handler(CallbackQueryHandler(support_copy_callback, pattern="^support_copy$"))

    # Persistent keyboard button handler (matches emoji-prefixed button labels)
    application.add_handler(MessageHandler(
        filters.Regex(r'^(💰 Price|📊 Summary|📰 News|ℹ️ Help|💎 Support Project)$'),
        keyboard_button_handler,
    ))

    # Text input handler for developer flows (must be last)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_dev_text_input,
    ))

    # Error handler
    application.add_error_handler(error_handler)

    return application


def main():
    """Entry point."""
    load_dotenv()
    config = Config.from_env()

    if not config.telegram_token:
        logger.error("TELEGRAM_BOT_TOKEN is not set!")
        sys.exit(1)

    if not config.openrouter_api_key:
        logger.warning("OPENROUTER_API_KEY is not set - AI features will be limited")

    app = create_app(config)

    logger.info("Starting bot with polling...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
