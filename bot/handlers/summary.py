import json
import logging
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def collect_coin_data(context: ContextTypes.DEFAULT_TYPE, coin: dict) -> dict:
    """Collect all data for a coin from all sources."""
    cmc = context.bot_data["cmc"]
    dex = context.bot_data["dex"]
    twitter = context.bot_data["twitter"]

    symbol = coin["symbol"]

    # Fetch data from all sources in parallel-ish manner
    cmc_data = await cmc.get_quote(symbol)
    dex_pairs = await dex.get_token_data(coin)

    # Twitter queries
    tw_queries = []
    if coin.get("twitter_queries"):
        try:
            tw_queries = json.loads(coin["twitter_queries"])
        except (json.JSONDecodeError, TypeError):
            tw_queries = [f"#{symbol}", f"${symbol}"]

    tweets = await twitter.search_tweets(tw_queries, max_tweets=15)

    return {
        "cmc_data": cmc_data,
        "dex_pairs": dex_pairs,
        "tweets": tweets,
        "cmc_formatted": cmc.format_quote(cmc_data),
        "dex_formatted": dex.format_pair_data(dex_pairs),
        "twitter_formatted": twitter.format_tweets(tweets),
    }


async def generate_coin_summary(
    context: ContextTypes.DEFAULT_TYPE,
    coin: dict,
    report_type: str = "on-demand",
) -> str:
    """Generate AI-powered summary for a single coin."""
    ai = context.bot_data["ai"]
    db = context.bot_data["db"]

    # Collect data
    data = await collect_coin_data(context, coin)

    # Generate AI summary
    summary = await ai.analyze_with_context(
        db=db,
        coin_symbol=coin["symbol"],
        coin_name=coin["name"],
        report_type=report_type,
        market_data=data["cmc_formatted"],
        dex_data=data["dex_formatted"],
        twitter_data=data["twitter_formatted"],
    )

    # Save summary to database
    raw_data = json.dumps({
        "cmc": data["cmc_formatted"],
        "dex": data["dex_formatted"],
        "twitter": data["twitter_formatted"],
    }, default=str)
    await db.save_summary(coin["symbol"], report_type, summary, raw_data)

    return summary


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /summary command - generate summaries for all active coins."""
    db = context.bot_data["db"]
    user = update.effective_user

    await db.upsert_user(user.id, user.username, user.first_name)
    await db.log_action(user.id, "summary_request")

    coins = await db.get_active_coins()
    if not coins:
        await update.message.reply_text("❌ No active coins configured.")
        return

    # Show coin selection
    keyboard = []
    for coin in coins:
        keyboard.append([
            InlineKeyboardButton(
                f"📊 {coin['name']} ({coin['symbol']})",
                callback_data=f"summary_{coin['symbol']}",
            )
        ])
    keyboard.append([
        InlineKeyboardButton("📊 All Coins", callback_data="summary_ALL")
    ])
    keyboard.append([
        InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")
    ])

    await update.message.reply_text(
        "📊 *Select a coin for summary:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def summary_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle summary menu button from main menu."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    coins = await db.get_active_coins()

    if not coins:
        await query.edit_message_text("❌ No active coins configured.")
        return

    keyboard = []
    for coin in coins:
        keyboard.append([
            InlineKeyboardButton(
                f"📊 {coin['name']} ({coin['symbol']})",
                callback_data=f"summary_{coin['symbol']}",
            )
        ])
    keyboard.append([
        InlineKeyboardButton("📊 All Coins", callback_data="summary_ALL")
    ])
    keyboard.append([
        InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")
    ])

    await query.edit_message_text(
        "📊 *Select a coin for summary:*\n\n"
        "💡 _Tip: Summary includes price, volume, buy/sell activity, news, and AI analysis_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def summary_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle summary generation for a specific coin or all coins."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    symbol = query.data.replace("summary_", "")

    await db.log_action(update.effective_user.id, "summary_generate", symbol)

    if symbol == "ALL":
        coins = await db.get_active_coins()
    else:
        coins = await db.get_active_coins()
        coins = [c for c in coins if c["symbol"] == symbol]

    if not coins:
        await query.edit_message_text("❌ Coin not found.")
        return

    await query.edit_message_text(
        "⏳ *Generating summary...*\n"
        "Collecting data from CoinMarketCap, DexScreener, and Twitter...\n"
        "🤖 AI is analyzing the data...",
        parse_mode="Markdown",
    )

    for coin in coins:
        try:
            summary = await generate_coin_summary(context, coin, "on-demand")
            # Send as a new message (summaries can be long)
            header = f"📊 *{coin['name']} ({coin['symbol']}) Summary*\n{'━' * 30}\n\n"

            # Split long messages (Telegram limit is 4096 chars)
            full_msg = header + summary
            if len(full_msg) > 4000:
                # Send in parts
                parts = [full_msg[i:i+4000] for i in range(0, len(full_msg), 4000)]
                for part in parts:
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=part,
                        parse_mode="Markdown",
                    )
            else:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=full_msg,
                    parse_mode="Markdown",
                )
        except Exception as e:
            logger.error(f"Summary generation failed for {coin['symbol']}: {e}")
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"❌ Failed to generate summary for {coin['symbol']}: {str(e)[:200]}",
            )

    # Final message with back button
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="✅ Summary generation complete!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Another Summary", callback_data="menu_summary")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
        ]),
    )


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /price command - quick price check."""
    db = context.bot_data["db"]
    cmc = context.bot_data["cmc"]
    dex = context.bot_data["dex"]

    await db.log_action(update.effective_user.id, "price_check")

    coins = await db.get_active_coins()
    if not coins:
        await update.message.reply_text("❌ No active coins configured.")
        return

    await update.message.reply_text("⏳ Fetching prices...")

    lines = ["💰 *Current Prices (Base chain, USD/USDC pools)*\n"]

    for coin in coins:
        symbol = coin["symbol"]
        token_addr = coin.get("token_address", "")
        # Try DexScreener first (exact contract address on Base)
        dex_pairs = await dex.get_token_data(coin)
        if dex_pairs:
            pair = dex_pairs[0]  # Largest liquidity pool
            price = pair.get("priceUsd", "N/A")
            change_24h = pair.get("priceChange", {}).get("h24", "N/A")
            change_1h = pair.get("priceChange", {}).get("h1", "N/A")
            volume = pair.get("volume", {}).get("h24", 0)
            liquidity = pair.get("liquidity", {}).get("usd", 0)
            txns = pair.get("txns", {}).get("h24", {})
            buys = txns.get("buys", 0)
            sells = txns.get("sells", 0)
            total_txns = buys + sells
            buy_pct = (buys / total_txns * 100) if total_txns > 0 else 0
            market_cap = pair.get("marketCap", 0)
            quote_sym = pair.get("quoteToken", {}).get("symbol", "USD")
            dex_name = pair.get("dexId", "DEX")
            labels = pair.get("labels", [])
            version = f" {', '.join(labels)}" if labels else ""

            arrow = "🟢" if str(change_24h).replace("-", "").replace("+", "") != "N/A" and float(str(change_24h).replace(",", "") or 0) >= 0 else "🔴"

            basescan_link = f"https://basescan.org/token/{token_addr}" if token_addr else ""

            mcap_line = f"   🏦 MCap: ${float(market_cap):,.0f}\n" if market_cap else ""
            coin_text = (
                f"{arrow} *{coin['name']}* ({symbol})\n"
                f"   💲 Price: ${price} (vs {quote_sym})\n"
                f"   📈 1h: {change_1h}% | 24h: {change_24h}%\n"
                f"   📊 Vol 24h: ${float(volume):,.0f}\n"
                f"   💧 Liquidity: ${float(liquidity):,.0f}\n"
                f"{mcap_line}"
                f"   🔄 Txns 24h: {buys} buys / {sells} sells ({buy_pct:.0f}% buys)\n"
                f"   🔗 Pool: {dex_name}{version} (Base)\n"
            )
            lines.append(coin_text)
            if basescan_link:
                lines.append(f"   🔍 [BaseScan]({basescan_link})\n")
        else:
            # Try CoinMarketCap
            cmc_data = await cmc.get_quote(symbol)
            if cmc_data:
                usd = cmc_data.get("quote", {}).get("USD", {})
                price = usd.get("price", 0)
                change = usd.get("percent_change_24h", 0)
                arrow = "🟢" if change >= 0 else "🔴"
                lines.append(
                    f"{arrow} *{coin['name']}* ({symbol})\n"
                    f"   💲 Price: ${price:,.8f}\n"
                    f"   📈 24h: {change:+.2f}%\n"
                )
            else:
                lines.append(f"❓ *{coin['name']}* ({symbol}) — No data available\n")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Full Summary", callback_data="menu_summary")],
            [InlineKeyboardButton("🔙 Menu", callback_data="menu_main")],
        ]),
    )


async def _fetch_news_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Shared helper: build the news text from Twitter + available sources."""
    db = context.bot_data["db"]
    twitter = context.bot_data["twitter"]

    coins = await db.get_active_coins()
    all_tweets_text: list[str] = []

    if twitter.apify_api_key:
        for coin in coins:
            tw_queries: list[str] = []
            if coin.get("twitter_queries"):
                try:
                    tw_queries = json.loads(coin["twitter_queries"])
                except (json.JSONDecodeError, TypeError):
                    tw_queries = [f"#{coin['symbol']}"]

            tweets = await twitter.search_tweets(tw_queries, max_tweets=5)
            if tweets:
                all_tweets_text.append(f"\n🪙 *{coin['name']}* ({coin['symbol']}):")
                for t in tweets[:5]:
                    text = t.get("full_text") or t.get("text") or t.get("content") or "N/A"
                    author = (t.get("user", {}).get("screen_name")
                             or t.get("author", {}).get("userName") or "Unknown")
                    if len(text) > 150:
                        text = text[:150] + "..."
                    all_tweets_text.append(f"  • @{author}: {text}")

    if all_tweets_text:
        msg = "📰 Latest News from Twitter/X\n" + "\n".join(all_tweets_text)
    else:
        msg = (
            "📰 Latest News\n\n"
            "ℹ️ No Twitter data available at the moment.\n"
            "Use the Summary button for a full AI-powered report including "
            "market data, DEX activity, and news analysis."
        )

    if len(msg) > 4000:
        msg = msg[:4000] + "\n..."
    return msg


async def news_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle news inline-menu button (callback query)."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    await db.log_action(update.effective_user.id, "news_request")

    await query.edit_message_text("⏳ Fetching latest news...")

    msg = await _fetch_news_text(context)

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=msg,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Full Summary", callback_data="menu_summary")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
        ]),
    )


async def news_command_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the 📰 News keyboard button (plain text message)."""
    db = context.bot_data["db"]
    await db.log_action(update.effective_user.id, "news_request")

    await update.message.reply_text("⏳ Fetching latest news...")

    msg = await _fetch_news_text(context)

    await update.message.reply_text(
        msg,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Full Summary", callback_data="menu_summary")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
        ]),
    )
