import aiosqlite
import json
import time
from typing import Optional


class Database:
    """SQLite database for bot persistence."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None

    async def init(self):
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        await self._create_tables()
        await self._seed_defaults()

    async def close(self):
        if self.db:
            await self.db.close()

    async def _create_tables(self):
        await self.db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                is_admin INTEGER DEFAULT 0,
                is_developer INTEGER DEFAULT 0,
                subscribed INTEGER DEFAULT 1,
                first_seen REAL NOT NULL,
                last_active REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS coins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                cmc_slug TEXT,
                dex_search_query TEXT,
                chain_id TEXT,
                token_address TEXT,
                twitter_queries TEXT,
                active INTEGER DEFAULT 1,
                added_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin_symbol TEXT NOT NULL,
                summary_type TEXT NOT NULL,
                content TEXT NOT NULL,
                raw_data TEXT,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ai_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                template TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ai_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                coin_symbol TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                UNIQUE(telegram_id, coin_symbol)
            );
        """)
        await self.db.commit()

    async def _seed_defaults(self):
        """Seed default coins and AI templates if not present."""
        now = time.time()

        # Default coins
        default_coins = [
            ("OWB", "OpenWorld", None, "OWB", None, None,
             json.dumps(["owb", "#owb", "#OWB", "$OWB"])),
            ("RNBW", "Rainbow", None, "rainbow token", None, None,
             json.dumps(["rnbw", "rainbow", "#rnbw", "#rainbow", "#RNBW", "$RNBW"])),
        ]
        for symbol, name, cmc_slug, dex_q, chain, addr, tw_q in default_coins:
            await self.db.execute(
                """INSERT OR IGNORE INTO coins
                   (symbol, name, cmc_slug, dex_search_query, chain_id, token_address, twitter_queries, added_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (symbol, name, cmc_slug, dex_q, chain, addr, tw_q, now),
            )

        # Default AI system template
        default_system = (
            "You are a professional cryptocurrency analyst bot. "
            "You provide clear, concise, and actionable market summaries. "
            "Analyze the provided data and generate a comprehensive summary including:\n"
            "- Current price and price changes (daily)\n"
            "- Trading volume and liquidity analysis\n"
            "- Buy vs sell pressure analysis\n"
            "- Notable transactions or whale activity\n"
            "- Social media sentiment from Twitter mentions\n"
            "- Key news and developments\n"
            "- Brief outlook and important levels to watch\n\n"
            "Format your response with emojis for readability. "
            "Be factual and data-driven. If data is missing, note it clearly. "
            "Keep the summary under 2000 characters for Telegram readability."
        )
        await self.db.execute(
            """INSERT OR IGNORE INTO ai_templates (name, template, active, updated_at)
               VALUES (?, ?, 1, ?)""",
            ("system_prompt", default_system, now),
        )

        default_summary_tpl = (
            "Generate a {report_type} crypto market summary for {coin_name} ({coin_symbol}).\n\n"
            "=== MARKET DATA ===\n{market_data}\n\n"
            "=== DEX DATA ===\n{dex_data}\n\n"
            "=== SOCIAL MEDIA / NEWS ===\n{twitter_data}\n\n"
            "=== AI MEMORY (learned context) ===\n{ai_memory}\n\n"
            "Provide a well-structured summary with all available metrics. "
            "Use emojis for visual structure. Include buy/sell volumes, price change, "
            "and any significant observations."
        )
        await self.db.execute(
            """INSERT OR IGNORE INTO ai_templates (name, template, active, updated_at)
               VALUES (?, ?, 1, ?)""",
            ("summary_template", default_summary_tpl, now),
        )

        # Default AI memory entries
        defaults_memory = [
            ("analysis_style", "Professional, concise, data-driven with emoji formatting"),
            ("target_audience", "Crypto traders and investors interested in OWB and Rainbow tokens"),
            ("language", "English with crypto terminology"),
        ]
        for key, value in defaults_memory:
            await self.db.execute(
                "INSERT OR IGNORE INTO ai_memory (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, now),
            )

        await self.db.commit()

    # ---- User operations ----

    async def upsert_user(self, telegram_id: int, username: str = None,
                          first_name: str = None) -> dict:
        now = time.time()
        await self.db.execute(
            """INSERT INTO users (telegram_id, username, first_name, first_seen, last_active)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET
               username=excluded.username, first_name=excluded.first_name, last_active=?""",
            (telegram_id, username, first_name, now, now, now),
        )
        await self.db.commit()
        cursor = await self.db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else {}

    async def get_user(self, telegram_id: int) -> Optional[dict]:
        cursor = await self.db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def set_admin(self, telegram_id: int, is_admin: bool = True):
        await self.db.execute(
            "UPDATE users SET is_admin = ? WHERE telegram_id = ?",
            (1 if is_admin else 0, telegram_id),
        )
        await self.db.commit()

    async def set_developer(self, telegram_id: int, is_developer: bool = True):
        await self.db.execute(
            "UPDATE users SET is_developer = ? WHERE telegram_id = ?",
            (1 if is_developer else 0, telegram_id),
        )
        await self.db.commit()

    async def get_all_subscribed_users(self) -> list[dict]:
        cursor = await self.db.execute(
            "SELECT * FROM users WHERE subscribed = 1"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_user_count(self) -> int:
        cursor = await self.db.execute("SELECT COUNT(*) as cnt FROM users")
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def get_active_users_count(self, since_hours: int = 24) -> int:
        since = time.time() - (since_hours * 3600)
        cursor = await self.db.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE last_active > ?", (since,)
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    # ---- Coin operations ----

    async def get_active_coins(self) -> list[dict]:
        cursor = await self.db.execute("SELECT * FROM coins WHERE active = 1")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_all_coins(self) -> list[dict]:
        cursor = await self.db.execute("SELECT * FROM coins")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def add_coin(self, symbol: str, name: str, cmc_slug: str = None,
                       dex_search_query: str = None, chain_id: str = None,
                       token_address: str = None, twitter_queries: list[str] = None) -> bool:
        try:
            now = time.time()
            tw_json = json.dumps(twitter_queries or [f"#{symbol}", f"${symbol}"])
            await self.db.execute(
                """INSERT INTO coins
                   (symbol, name, cmc_slug, dex_search_query, chain_id, token_address, twitter_queries, added_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (symbol.upper(), name, cmc_slug, dex_search_query or symbol,
                 chain_id, token_address, tw_json, now),
            )
            await self.db.commit()
            return True
        except Exception:
            return False

    async def remove_coin(self, symbol: str) -> bool:
        cursor = await self.db.execute(
            "DELETE FROM coins WHERE symbol = ?", (symbol.upper(),)
        )
        await self.db.commit()
        return cursor.rowcount > 0

    async def toggle_coin(self, symbol: str) -> Optional[bool]:
        cursor = await self.db.execute(
            "SELECT active FROM coins WHERE symbol = ?", (symbol.upper(),)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        new_state = 0 if row["active"] else 1
        await self.db.execute(
            "UPDATE coins SET active = ? WHERE symbol = ?", (new_state, symbol.upper())
        )
        await self.db.commit()
        return bool(new_state)

    # ---- Summary operations ----

    async def save_summary(self, coin_symbol: str, summary_type: str,
                           content: str, raw_data: str = None):
        now = time.time()
        await self.db.execute(
            """INSERT INTO summaries (coin_symbol, summary_type, content, raw_data, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (coin_symbol, summary_type, content, raw_data, now),
        )
        await self.db.commit()

    async def get_latest_summary(self, coin_symbol: str) -> Optional[dict]:
        cursor = await self.db.execute(
            "SELECT * FROM summaries WHERE coin_symbol = ? ORDER BY created_at DESC LIMIT 1",
            (coin_symbol,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    # ---- Analytics operations ----

    async def log_action(self, telegram_id: int, action: str, details: str = None):
        now = time.time()
        await self.db.execute(
            "INSERT INTO user_actions (telegram_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (telegram_id, action, details, now),
        )
        await self.db.commit()

    async def get_analytics(self) -> dict:
        total_users = await self.get_user_count()
        active_24h = await self.get_active_users_count(24)
        active_7d = await self.get_active_users_count(168)

        cursor = await self.db.execute(
            """SELECT action, COUNT(*) as cnt FROM user_actions
               WHERE timestamp > ? GROUP BY action ORDER BY cnt DESC LIMIT 10""",
            (time.time() - 86400,),
        )
        top_actions = [dict(r) for r in await cursor.fetchall()]

        cursor = await self.db.execute(
            "SELECT COUNT(*) as cnt FROM summaries"
        )
        total_summaries = (await cursor.fetchone())["cnt"]

        return {
            "total_users": total_users,
            "active_24h": active_24h,
            "active_7d": active_7d,
            "total_summaries": total_summaries,
            "top_actions_24h": top_actions,
        }

    # ---- AI Template operations ----

    async def get_template(self, name: str) -> Optional[str]:
        cursor = await self.db.execute(
            "SELECT template FROM ai_templates WHERE name = ? AND active = 1", (name,)
        )
        row = await cursor.fetchone()
        return row["template"] if row else None

    async def update_template(self, name: str, template: str):
        now = time.time()
        await self.db.execute(
            """INSERT INTO ai_templates (name, template, active, updated_at)
               VALUES (?, ?, 1, ?)
               ON CONFLICT(name) DO UPDATE SET template=excluded.template, updated_at=?""",
            (name, template, now, now),
        )
        await self.db.commit()

    async def get_all_templates(self) -> list[dict]:
        cursor = await self.db.execute("SELECT * FROM ai_templates")
        return [dict(r) for r in await cursor.fetchall()]

    # ---- AI Memory operations ----

    async def get_memory(self, key: str) -> Optional[str]:
        cursor = await self.db.execute(
            "SELECT value FROM ai_memory WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else None

    async def set_memory(self, key: str, value: str):
        now = time.time()
        await self.db.execute(
            """INSERT INTO ai_memory (key, value, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=?""",
            (key, value, now, now),
        )
        await self.db.commit()

    async def get_all_memory(self) -> list[dict]:
        cursor = await self.db.execute("SELECT * FROM ai_memory")
        return [dict(r) for r in await cursor.fetchall()]

    async def delete_memory(self, key: str) -> bool:
        cursor = await self.db.execute("DELETE FROM ai_memory WHERE key = ?", (key,))
        await self.db.commit()
        return cursor.rowcount > 0

    # ---- Settings ----

    async def get_setting(self, key: str, default: str = None) -> Optional[str]:
        cursor = await self.db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str):
        await self.db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await self.db.commit()
