import logging
import json
from datetime import time as dt_time
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


async def _safe_send(bot, chat_id, text, reply_markup=None):
    """Send message with Markdown, falling back to plain text on parse error."""
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
        )
    except Exception as md_err:
        logger.warning(f"Markdown send failed ({md_err}), retrying as plain text")
        plain = text.replace('*', '').replace('_', '')
        try:
            return await bot.send_message(
                chat_id=chat_id,
                text=plain,
                reply_markup=reply_markup,
            )
        except Exception as plain_err:
            logger.error(f"Plain-text send also failed: {plain_err}")
            raise


async def send_scheduled_summary(context: ContextTypes.DEFAULT_TYPE):
    """Send scheduled summary to all subscribed users."""
    db = context.bot_data["db"]
    report_type = context.job.data or "scheduled"

    logger.info(f"Running scheduled summary: {report_type}")

    coins = await db.get_active_coins()
    if not coins:
        logger.warning("No active coins for scheduled summary")
        return

    # Generate summaries for all coins
    from bot.handlers.summary import generate_coin_summary

    summaries = {}
    for coin in coins:
        try:
            summary = await generate_coin_summary(context, coin, report_type)
            summaries[coin["symbol"]] = {
                "name": coin["name"],
                "summary": summary,
            }
        except Exception as e:
            logger.error(f"Scheduled summary failed for {coin['symbol']}: {e}")
            summaries[coin["symbol"]] = {
                "name": coin["name"],
                "summary": f"Summary unavailable: {str(e)[:100]}",
            }

    # Send to all subscribed users
    users = await db.get_all_subscribed_users()
    logger.info(f"Sending scheduled summary to {len(users)} users")

    success_count = 0
    fail_count = 0

    for user in users:
        try:
            for symbol, data in summaries.items():
                header = ""
                if report_type == "morning":
                    header = f"🌅 Morning Summary — {data['name']} ({symbol})\n{'━' * 30}\n\n"
                elif report_type == "evening":
                    header = f"🌙 Evening Summary — {data['name']} ({symbol})\n{'━' * 30}\n\n"
                else:
                    header = f"📊 {data['name']} ({symbol}) Summary\n{'━' * 30}\n\n"

                full_msg = header + data["summary"]

                if len(full_msg) > 4000:
                    parts = [full_msg[i:i+4000] for i in range(0, len(full_msg), 4000)]
                    for part in parts:
                        await _safe_send(context.bot, user["telegram_id"], part)
                else:
                    await _safe_send(context.bot, user["telegram_id"], full_msg)

            success_count += 1

        except Exception as e:
            fail_count += 1
            logger.warning(f"Failed to send summary to user {user['telegram_id']}: {e}")

    logger.info(
        f"Scheduled summary sent: {success_count} success, {fail_count} failed"
    )


def setup_schedules(job_queue):
    """Set up the morning and evening scheduled summaries."""
    # Morning summary: 8:00 AM MSK = 5:00 AM UTC
    morning_time = dt_time(hour=5, minute=0, second=0)
    job_queue.run_daily(
        send_scheduled_summary,
        time=morning_time,
        data="morning",
        name="morning_summary",
    )
    logger.info(f"Scheduled morning summary at {morning_time} UTC (8:00 AM MSK)")

    # Evening summary: 11:00 PM MSK = 8:00 PM UTC
    evening_time = dt_time(hour=20, minute=0, second=0)
    job_queue.run_daily(
        send_scheduled_summary,
        time=evening_time,
        data="evening",
        name="evening_summary",
    )
    logger.info(f"Scheduled evening summary at {evening_time} UTC (11:00 PM MSK)")
