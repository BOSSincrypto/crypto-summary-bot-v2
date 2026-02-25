import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, CommandHandler, filters,
)

logger = logging.getLogger(__name__)

# Conversation states for developer flows
(
    DEV_WAITING_PASSWORD,
    DEV_ADD_COIN_SYMBOL,
    DEV_ADD_COIN_NAME,
    DEV_ADD_COIN_DEX_QUERY,
    DEV_ADD_COIN_CHAIN,
    DEV_ADD_COIN_ADDRESS,
    DEV_ADD_COIN_TWITTER,
    DEV_EDIT_TEMPLATE_SELECT,
    DEV_EDIT_TEMPLATE_CONTENT,
    DEV_ADD_MEMORY_KEY,
    DEV_ADD_MEMORY_VALUE,
    DEV_TEACH_AI,
) = range(12)


async def dev_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /dev command."""
    db = context.bot_data["db"]
    user = update.effective_user
    await db.upsert_user(user.id, user.username, user.first_name)

    user_data = await db.get_user(user.id)
    if user_data and (user_data.get("is_developer") or user_data.get("is_admin")):
        await show_dev_panel(update, context)
        return ConversationHandler.END

    await update.message.reply_text(
        "🔧 *Developer Panel*\n\nPlease enter the admin password to access developer tools:",
        parse_mode="Markdown",
    )
    return DEV_WAITING_PASSWORD


async def dev_check_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify password for developer access."""
    config = context.bot_data["config"]
    db = context.bot_data["db"]
    password = update.message.text.strip()

    try:
        await update.message.delete()
    except Exception:
        pass

    if password == config.admin_password:
        await db.set_developer(update.effective_user.id, True)
        await db.set_admin(update.effective_user.id, True)
        await db.log_action(update.effective_user.id, "dev_login_success")
        await show_dev_panel(update, context)
    else:
        await db.log_action(update.effective_user.id, "dev_login_failed")
        await update.message.reply_text("❌ Wrong password. Access denied.")

    return ConversationHandler.END


async def show_dev_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the developer panel."""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add New Coin", callback_data="dev_add_coin")],
        [InlineKeyboardButton("📋 Manage Coins", callback_data="dev_manage_coins")],
        [InlineKeyboardButton("📝 Edit AI Templates", callback_data="dev_edit_templates")],
        [InlineKeyboardButton("🧠 Manage AI Memory", callback_data="dev_manage_memory")],
        [InlineKeyboardButton("🎓 Teach AI", callback_data="dev_teach_ai")],
        [InlineKeyboardButton("📊 System Stats", callback_data="dev_system_stats")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_main")],
    ])

    text = (
        "🔧 *Developer Panel*\n\n"
        "Advanced tools for managing the bot.\n"
        "Add coins, edit AI behavior, and more."
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=keyboard,
        )
    else:
        msg = update.message or update.effective_message
        if msg:
            await msg.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def dev_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle developer panel callbacks."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    user_data = await db.get_user(update.effective_user.id)
    if not user_data or not (user_data.get("is_developer") or user_data.get("is_admin")):
        await query.edit_message_text("❌ Unauthorized. Use /dev to log in.")
        return

    action = query.data

    if action == "dev_add_coin":
        await query.edit_message_text(
            "➕ *Add New Coin*\n\n"
            "Enter the coin *symbol* (e.g., BTC, ETH, DOGE):",
            parse_mode="Markdown",
        )
        context.user_data["dev_state"] = "add_coin_symbol"

    elif action == "dev_manage_coins":
        await show_manage_coins(update, context)

    elif action == "dev_edit_templates":
        await show_edit_templates(update, context)

    elif action == "dev_manage_memory":
        await show_manage_memory(update, context)

    elif action == "dev_teach_ai":
        await query.edit_message_text(
            "🎓 *Teach AI*\n\n"
            "Send a message to teach the AI something new.\n"
            "Format: `key: value`\n\n"
            "Examples:\n"
            "• `owb_info: OWB is a gaming token on BSC`\n"
            "• `analysis_focus: Pay attention to whale transactions`\n"
            "• `report_style: Use bullet points and keep it concise`\n\n"
            "Send your teaching now:",
            parse_mode="Markdown",
        )
        context.user_data["dev_state"] = "teach_ai"

    elif action == "dev_system_stats":
        await show_system_stats(update, context)

    elif action == "dev_panel":
        await show_dev_panel(update, context)


async def show_manage_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show coin management with toggle/remove options."""
    query = update.callback_query
    db = context.bot_data["db"]

    coins = await db.get_all_coins()
    keyboard = []
    for c in coins:
        status = "🟢" if c["active"] else "🔴"
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {c['name']} ({c['symbol']})",
                callback_data=f"dev_toggle_{c['symbol']}",
            ),
            InlineKeyboardButton("🗑", callback_data=f"dev_remove_{c['symbol']}"),
        ])
    keyboard.append([InlineKeyboardButton("➕ Add New", callback_data="dev_add_coin")])
    keyboard.append([InlineKeyboardButton("🔙 Dev Panel", callback_data="dev_panel")])

    await query.edit_message_text(
        "📋 *Manage Coins*\n\n"
        "Tap a coin to toggle active/inactive. Tap 🗑 to remove.\n"
        "🟢 = Active | 🔴 = Inactive",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def toggle_coin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle a coin's active status."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    symbol = query.data.replace("dev_toggle_", "")

    new_state = await db.toggle_coin(symbol)
    if new_state is None:
        await query.answer("Coin not found!", show_alert=True)
    else:
        state_text = "activated" if new_state else "deactivated"
        await query.answer(f"{symbol} {state_text}!")

    # Refresh the coin list
    await show_manage_coins(update, context)


async def remove_coin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a coin."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    symbol = query.data.replace("dev_remove_", "")

    removed = await db.remove_coin(symbol)
    if removed:
        await query.answer(f"{symbol} removed!", show_alert=True)
    else:
        await query.answer("Coin not found!", show_alert=True)

    await show_manage_coins(update, context)


async def show_edit_templates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show template selection."""
    query = update.callback_query
    db = context.bot_data["db"]

    templates = await db.get_all_templates()
    keyboard = []
    for tpl in templates:
        keyboard.append([
            InlineKeyboardButton(
                f"📝 {tpl['name']}",
                callback_data=f"dev_tpl_{tpl['name']}",
            )
        ])
    keyboard.append([InlineKeyboardButton("🔙 Dev Panel", callback_data="dev_panel")])

    await query.edit_message_text(
        "📝 *Edit AI Templates*\n\nSelect a template to view/edit:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def view_template_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View a specific template."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    tpl_name = query.data.replace("dev_tpl_", "")

    template = await db.get_template(tpl_name)
    if template:
        # Truncate for display
        display = template if len(template) <= 3000 else template[:3000] + "\n..."
        text = (
            f"📝 *Template: {tpl_name}*\n\n"
            f"`{display}`\n\n"
            "To edit, send the new template text now.\n"
            "Or press Back to cancel."
        )
        context.user_data["dev_state"] = f"edit_template_{tpl_name}"
    else:
        text = f"Template '{tpl_name}' not found."

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Templates", callback_data="dev_edit_templates")],
            [InlineKeyboardButton("🔙 Dev Panel", callback_data="dev_panel")],
        ]),
    )


async def show_manage_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show AI memory management."""
    query = update.callback_query
    db = context.bot_data["db"]

    memories = await db.get_all_memory()
    keyboard = []
    for mem in memories:
        keyboard.append([
            InlineKeyboardButton(
                f"🧠 {mem['key']}",
                callback_data=f"dev_mem_view_{mem['key']}",
            ),
            InlineKeyboardButton("🗑", callback_data=f"dev_mem_del_{mem['key']}"),
        ])
    keyboard.append([InlineKeyboardButton("➕ Add Memory", callback_data="dev_add_memory")])
    keyboard.append([InlineKeyboardButton("🔙 Dev Panel", callback_data="dev_panel")])

    text = "🧠 *AI Memory*\n\nThe AI uses these memories for context:\n\n"
    for mem in memories:
        text += f"• *{mem['key']}:* {mem['value'][:50]}...\n" if len(mem['value']) > 50 else f"• *{mem['key']}:* {mem['value']}\n"

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def delete_memory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete an AI memory entry."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["db"]
    key = query.data.replace("dev_mem_del_", "")

    deleted = await db.delete_memory(key)
    if deleted:
        await query.answer(f"Memory '{key}' deleted!", show_alert=True)
    else:
        await query.answer("Memory not found!", show_alert=True)

    await show_manage_memory(update, context)


async def show_system_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show system statistics."""
    query = update.callback_query
    db = context.bot_data["db"]
    config = context.bot_data["config"]

    analytics = await db.get_analytics()
    coins = await db.get_all_coins()
    active_coins = [c for c in coins if c["active"]]
    templates = await db.get_all_templates()
    memories = await db.get_all_memory()

    text = (
        "📊 *System Statistics*\n\n"
        f"👥 Total Users: {analytics['total_users']}\n"
        f"🟢 Active (24h): {analytics['active_24h']}\n"
        f"📅 Active (7d): {analytics['active_7d']}\n\n"
        f"🪙 Coins: {len(active_coins)} active / {len(coins)} total\n"
        f"📝 Summaries generated: {analytics['total_summaries']}\n"
        f"📄 AI Templates: {len(templates)}\n"
        f"🧠 AI Memory entries: {len(memories)}\n\n"
        f"🤖 AI Model: `{config.ai_model}`\n"
        f"📡 CMC API: {'✅' if config.coinmarketcap_api_key else '❌'}\n"
        f"🐦 Apify: {'✅' if config.apify_api_key else '❌'}\n"
        f"🧠 OpenRouter: {'✅' if config.openrouter_api_key else '❌'}\n"
    )

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="dev_system_stats")],
            [InlineKeyboardButton("🔙 Dev Panel", callback_data="dev_panel")],
        ]),
    )


async def handle_dev_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input for developer operations."""
    db = context.bot_data["db"]
    ai = context.bot_data["ai"]
    state = context.user_data.get("dev_state", "")
    text = update.message.text.strip()

    if state == "add_coin_symbol":
        context.user_data["new_coin_symbol"] = text.upper()
        context.user_data["dev_state"] = "add_coin_name"
        await update.message.reply_text(
            f"Symbol: *{text.upper()}*\n\nNow enter the coin *name* (e.g., Bitcoin, Ethereum):",
            parse_mode="Markdown",
        )

    elif state == "add_coin_name":
        context.user_data["new_coin_name"] = text
        context.user_data["dev_state"] = "add_coin_dex_query"
        await update.message.reply_text(
            f"Name: *{text}*\n\nEnter the *DexScreener search query* (or 'skip'):",
            parse_mode="Markdown",
        )

    elif state == "add_coin_dex_query":
        dex_q = text if text.lower() != "skip" else None
        context.user_data["new_coin_dex_query"] = dex_q
        context.user_data["dev_state"] = "add_coin_chain"
        await update.message.reply_text(
            "Enter the *chain ID* (e.g., ethereum, bsc, solana) or 'skip':",
            parse_mode="Markdown",
        )

    elif state == "add_coin_chain":
        chain = text if text.lower() != "skip" else None
        context.user_data["new_coin_chain"] = chain
        context.user_data["dev_state"] = "add_coin_address"
        await update.message.reply_text(
            "Enter the *token contract address* or 'skip':",
            parse_mode="Markdown",
        )

    elif state == "add_coin_address":
        addr = text if text.lower() != "skip" else None
        context.user_data["new_coin_address"] = addr
        context.user_data["dev_state"] = "add_coin_twitter"
        await update.message.reply_text(
            "Enter *Twitter search queries* (comma-separated) or 'skip':\n"
            "Example: `#BTC, $BTC, bitcoin`",
            parse_mode="Markdown",
        )

    elif state == "add_coin_twitter":
        if text.lower() == "skip":
            tw_queries = None
        else:
            tw_queries = [q.strip() for q in text.split(",") if q.strip()]

        symbol = context.user_data.get("new_coin_symbol", "")
        name = context.user_data.get("new_coin_name", "")
        dex_q = context.user_data.get("new_coin_dex_query")
        chain = context.user_data.get("new_coin_chain")
        addr = context.user_data.get("new_coin_address")

        success = await db.add_coin(
            symbol=symbol, name=name, dex_search_query=dex_q,
            chain_id=chain, token_address=addr, twitter_queries=tw_queries,
        )

        if success:
            await update.message.reply_text(
                f"✅ Coin *{name}* ({symbol}) added successfully!",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Manage Coins", callback_data="dev_manage_coins")],
                    [InlineKeyboardButton("🔙 Dev Panel", callback_data="dev_panel")],
                ]),
            )
        else:
            await update.message.reply_text(
                f"❌ Failed to add coin (symbol may already exist).",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Dev Panel", callback_data="dev_panel")],
                ]),
            )

        context.user_data["dev_state"] = ""

    elif state.startswith("edit_template_"):
        tpl_name = state.replace("edit_template_", "")
        await db.update_template(tpl_name, text)
        context.user_data["dev_state"] = ""
        await update.message.reply_text(
            f"✅ Template *{tpl_name}* updated successfully!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 Templates", callback_data="dev_edit_templates")],
                [InlineKeyboardButton("🔙 Dev Panel", callback_data="dev_panel")],
            ]),
        )

    elif state == "teach_ai":
        # Parse key: value format
        if ":" in text:
            key, value = text.split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            value = value.strip()
            result = await ai.learn(db, key, value)
            await update.message.reply_text(
                f"🎓 {result}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎓 Teach More", callback_data="dev_teach_ai")],
                    [InlineKeyboardButton("🔙 Dev Panel", callback_data="dev_panel")],
                ]),
            )
        else:
            await update.message.reply_text(
                "❌ Invalid format. Use `key: value`\n"
                "Example: `owb_info: OWB is a gaming token`",
                parse_mode="Markdown",
            )
        context.user_data["dev_state"] = ""

    elif state == "add_memory":
        if ":" in text:
            key, value = text.split(":", 1)
            await db.set_memory(key.strip(), value.strip())
            await update.message.reply_text(
                f"✅ Memory entry added!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🧠 Memory", callback_data="dev_manage_memory")],
                    [InlineKeyboardButton("🔙 Dev Panel", callback_data="dev_panel")],
                ]),
            )
        else:
            await update.message.reply_text("❌ Use format: `key: value`", parse_mode="Markdown")
        context.user_data["dev_state"] = ""

    else:
        # Not in a dev flow, ignore
        return


async def add_memory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the add memory flow."""
    query = update.callback_query
    await query.answer()

    context.user_data["dev_state"] = "add_memory"
    await query.edit_message_text(
        "➕ *Add AI Memory*\n\n"
        "Send in format: `key: value`\n\n"
        "Example: `owb_chain: BSC (BNB Smart Chain)`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Cancel", callback_data="dev_manage_memory")],
        ]),
    )
