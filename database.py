import random
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone

import aiosqlite
from config import Config


class Database:
    def __init__(self, guild_id: int = 0):
        self.db_name = Config.DB_NAME
        self.guild_id = guild_id

    def for_guild(self, guild_id: int):
        scoped = Database(guild_id)
        scoped.db_name = self.db_name
        return scoped

    def connect(self):
        return aiosqlite.connect(self.db_name)

    async def setup(self):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA foreign_keys=ON")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER NOT NULL DEFAULT 0 CHECK(balance >= 0),
                    bank INTEGER NOT NULL DEFAULT 0 CHECK(bank >= 0),
                    xp INTEGER NOT NULL DEFAULT 0,
                    level INTEGER NOT NULL DEFAULT 1,
                    last_daily TEXT,
                    last_rob TEXT,
                    last_work TEXT,
                    daily_streak INTEGER NOT NULL DEFAULT 0,
                    next_daily_bonus INTEGER NOT NULL DEFAULT 0,
                    next_rob_insurance INTEGER NOT NULL DEFAULT 0,
                    last_message_time REAL NOT NULL DEFAULT 0
                )
            """)
            columns = {row[1] for row in await (await db.execute("PRAGMA table_info(users)")).fetchall()}
            for name, declaration in (
                ("last_work", "TEXT"),
                ("daily_streak", "INTEGER NOT NULL DEFAULT 0"),
                ("next_work_bonus", "INTEGER NOT NULL DEFAULT 0"),
                ("next_daily_bonus", "INTEGER NOT NULL DEFAULT 0"),
                ("next_rob_insurance", "INTEGER NOT NULL DEFAULT 0"),
            ):
                if name not in columns:
                    await db.execute(f"ALTER TABLE users ADD COLUMN {name} {declaration}")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    user_id INTEGER NOT NULL,
                    item_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
                    expires_at TEXT,
                    PRIMARY KEY (user_id, item_name)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS guild_users (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    balance INTEGER NOT NULL DEFAULT 0 CHECK(balance >= 0),
                    bank INTEGER NOT NULL DEFAULT 0 CHECK(bank >= 0),
                    xp INTEGER NOT NULL DEFAULT 0,
                    level INTEGER NOT NULL DEFAULT 1,
                    last_daily TEXT,
                    last_rob TEXT,
                    last_work TEXT,
                    daily_streak INTEGER NOT NULL DEFAULT 0,
                    next_daily_bonus INTEGER NOT NULL DEFAULT 0,
                    next_rob_insurance INTEGER NOT NULL DEFAULT 0,
                    next_work_bonus INTEGER NOT NULL DEFAULT 0,
                    last_message_time REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS guild_inventory (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    item_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
                    expires_at TEXT,
                    PRIMARY KEY (guild_id, user_id, item_name)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS guild_portfolio (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL REFERENCES market_assets(symbol),
                    quantity INTEGER NOT NULL CHECK(quantity > 0),
                    average_cost REAL NOT NULL CHECK(average_cost >= 0),
                    PRIMARY KEY (guild_id, user_id, symbol)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS guild_property_holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    property_key TEXT NOT NULL REFERENCES property_catalog(property_key),
                    purchased_at TEXT NOT NULL,
                    last_collected_at TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    name TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS questionnaires (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    creator_id INTEGER,
                    title TEXT,
                    question TEXT,
                    options TEXT,
                    config TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS market_assets (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    price INTEGER NOT NULL CHECK(price > 0),
                    buy_volume INTEGER NOT NULL DEFAULT 0,
                    sell_volume INTEGER NOT NULL DEFAULT 0,
                    last_change_pct REAL NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS market_state (
                    id INTEGER PRIMARY KEY CHECK(id = 1),
                    last_tick TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS market_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL DEFAULT 0,
                    user_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL REFERENCES market_assets(symbol),
                    action TEXT NOT NULL CHECK(action IN ('buy', 'sell')),
                    quantity INTEGER NOT NULL,
                    unit_price INTEGER NOT NULL,
                    total INTEGER NOT NULL,
                    realized_profit REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            trade_columns = {
                row[1] for row in await (await db.execute("PRAGMA table_info(market_trades)")).fetchall()
            }
            if "guild_id" not in trade_columns:
                await db.execute("ALTER TABLE market_trades ADD COLUMN guild_id INTEGER NOT NULL DEFAULT 0")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS portfolio (
                    user_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL REFERENCES market_assets(symbol),
                    quantity INTEGER NOT NULL CHECK(quantity > 0),
                    average_cost REAL NOT NULL CHECK(average_cost >= 0),
                    PRIMARY KEY (user_id, symbol)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS property_catalog (
                    property_key TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    price INTEGER NOT NULL CHECK(price > 0),
                    rent_per_hour INTEGER NOT NULL CHECK(rent_per_hour >= 0),
                    description TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS property_holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    property_key TEXT NOT NULL REFERENCES property_catalog(property_key),
                    purchased_at TEXT NOT NULL,
                    last_collected_at TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS economy_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    actor_id INTEGER NOT NULL,
                    target_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    action TEXT NOT NULL CHECK(action IN ('grant', 'remove')),
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    welcome_channel_id INTEGER,
                    log_channel_id INTEGER,
                    default_role_id INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS moderation_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    target_id INTEGER NOT NULL,
                    moderator_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    delivered INTEGER NOT NULL DEFAULT 0
                )
            """)
            questionnaire_columns = {
                row[1] for row in await (await db.execute("PRAGMA table_info(questionnaires)")).fetchall()
            }
            for name, declaration in (
                ("channel_id", "INTEGER"),
                ("message_id", "INTEGER"),
                ("created_at", "TEXT"),
                ("active", "INTEGER NOT NULL DEFAULT 1"),
            ):
                if name not in questionnaire_columns:
                    await db.execute(f"ALTER TABLE questionnaires ADD COLUMN {name} {declaration}")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS questionnaire_votes (
                    questionnaire_id INTEGER NOT NULL REFERENCES questionnaires(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL,
                    selected_options TEXT NOT NULL,
                    PRIMARY KEY (questionnaire_id, user_id)
                )
            """)
            await db.executemany(
                "INSERT OR IGNORE INTO market_assets (symbol, name, price, updated_at) VALUES (?, ?, ?, ?)",
                [
                    ("AUR", "Aurora Energy", 120, datetime.now(timezone.utc).isoformat()),
                    ("NEX", "Nexus Robotics", 250, datetime.now(timezone.utc).isoformat()),
                    ("VER", "Verde Biotech", 85, datetime.now(timezone.utc).isoformat()),
                    ("ORB", "Orbit Transport", 175, datetime.now(timezone.utc).isoformat()),
                    ("CRY", "Cryo Mining", 140, datetime.now(timezone.utc).isoformat()),
                    ("MED", "MedNova Health", 210, datetime.now(timezone.utc).isoformat()),
                    ("SOL", "Solstice Water", 95, datetime.now(timezone.utc).isoformat()),
                ],
            )
            await db.executemany(
                "INSERT OR IGNORE INTO property_catalog (property_key, name, price, rent_per_hour, description) VALUES (?, ?, ?, ?, ?)",
                [
                    ("casa", "Casa compacta", 2500, 12, "Entrada asequible al mercado inmobiliario."),
                    ("apartamento", "Apartamento", 12000, 75, "Vivienda urbana con renta estable."),
                    ("local", "Local comercial", 50000, 360, "Mayor inversión y mejor renta por hora."),
                    ("garaje", "Garaje de barrio", 8000, 42, "Propiedad pequeña de bajo coste y renta regular."),
                    ("edificio", "Edificio residencial", 125000, 950, "Cartera de viviendas con renta elevada."),
                    ("hotel", "Hotel costero", 300000, 2500, "Inversión premium con renta alta por hora."),
                ],
            )
            now = datetime.now(timezone.utc).isoformat()
            await db.execute("INSERT OR IGNORE INTO market_state (id, last_tick) VALUES (1, ?)", (now,))
            await db.commit()
        if Config.LEGACY_ECONOMY_GUILD_ID > 0:
            await self.migrate_legacy_economy(Config.LEGACY_ECONOMY_GUILD_ID)
        else:
            async with aiosqlite.connect(self.db_name) as db:
                legacy_rows = 0
                for table in ("users", "inventory", "portfolio", "property_holdings"):
                    legacy_rows += (await (await db.execute(f"SELECT COUNT(*) FROM {table}")).fetchone())[0]
                legacy_rows += (await (await db.execute(
                    "SELECT COUNT(*) FROM market_trades WHERE guild_id = 0"
                )).fetchone())[0]
            if legacy_rows:
                raise RuntimeError(
                    "Hay datos económicos globales antiguos. Define LEGACY_ECONOMY_GUILD_ID en .env para migrarlos al servidor correcto."
                )

    async def migrate_legacy_economy(self, guild_id: int):
        migration_name = "global-economy-to-guild-v1"
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            applied = await (await db.execute(
                "SELECT 1 FROM schema_migrations WHERE name = ?", (migration_name,)
            )).fetchone()
            if applied:
                await db.rollback()
                return False
            await db.execute(
                """
                INSERT OR IGNORE INTO guild_users (
                    guild_id, user_id, balance, bank, xp, level, last_daily, last_rob,
                    last_work, daily_streak, next_daily_bonus, next_rob_insurance,
                    next_work_bonus, last_message_time
                )
                SELECT ?, user_id, balance, bank, xp, level, last_daily, last_rob,
                    last_work, daily_streak, next_daily_bonus, next_rob_insurance,
                    next_work_bonus, last_message_time
                FROM users
                """,
                (guild_id,),
            )
            await db.execute(
                "INSERT OR IGNORE INTO guild_inventory (guild_id, user_id, item_name, quantity, expires_at) SELECT ?, user_id, item_name, quantity, expires_at FROM inventory",
                (guild_id,),
            )
            await db.execute(
                "INSERT OR IGNORE INTO guild_portfolio (guild_id, user_id, symbol, quantity, average_cost) SELECT ?, user_id, symbol, quantity, average_cost FROM portfolio",
                (guild_id,),
            )
            await db.execute(
                "INSERT INTO guild_property_holdings (guild_id, user_id, property_key, purchased_at, last_collected_at) SELECT ?, user_id, property_key, purchased_at, last_collected_at FROM property_holdings",
                (guild_id,),
            )
            await db.execute(
                "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
                (migration_name, datetime.now(timezone.utc).isoformat()),
            )
            await db.execute(
                "UPDATE market_trades SET guild_id = ? WHERE guild_id = 0",
                (guild_id,),
            )
            await db.commit()
            return True

    async def _ensure_user(self, db, user_id: int):
        await db.execute(
            "INSERT OR IGNORE INTO guild_users (guild_id, user_id) VALUES (?, ?)",
            (self.guild_id, user_id),
        )

    async def get_user(self, user_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await self._ensure_user(db, user_id)
            async with db.execute(
                "SELECT balance, bank, xp, level, last_daily, last_rob, last_message_time, last_work, daily_streak, next_daily_bonus, next_rob_insurance FROM guild_users WHERE guild_id = ? AND user_id = ?",
                (self.guild_id, user_id),
            ) as cursor:
                row = await cursor.fetchone()
            await db.commit()
        return {
            "balance": row[0], "bank": row[1], "xp": row[2], "level": row[3],
            "last_daily": row[4], "last_rob": row[5], "last_message_time": row[6],
            "last_work": row[7], "daily_streak": row[8],
            "next_daily_bonus": row[9], "next_rob_insurance": row[10],
        }

    async def update_user_balance(self, user_id: int, amount: int) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            await self._ensure_user(db, user_id)
            cursor = await db.execute(
                "UPDATE guild_users SET balance = balance + ? WHERE guild_id = ? AND user_id = ? AND balance + ? >= 0",
                (amount, self.guild_id, user_id, amount),
            )
            await db.commit()
            return cursor.rowcount == 1

    async def admin_adjust_balance(self, guild_id: int, actor_id: int, target_id: int,
                                   amount: int, action: str, reason: str, now: str) -> bool:
        if action not in {"grant", "remove"} or amount <= 0:
            raise ValueError("Invalid administrative balance adjustment")
        if self.guild_id != guild_id:
            raise ValueError("Database guild scope does not match audit guild")
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_user(db, target_id)
            delta = amount if action == "grant" else -amount
            cursor = await db.execute(
                "UPDATE guild_users SET balance = balance + ? WHERE guild_id = ? AND user_id = ? AND balance + ? >= 0",
                (delta, guild_id, target_id, delta),
            )
            if cursor.rowcount != 1:
                await db.rollback()
                return False
            await db.execute(
                "INSERT INTO economy_audit (guild_id, actor_id, target_id, amount, action, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (guild_id, actor_id, target_id, amount, action, reason, now),
            )
            await db.commit()
            return True

    async def get_economy_audit(self, guild_id: int, limit: int = 10):
        async with aiosqlite.connect(self.db_name) as db:
            return await (await db.execute(
                "SELECT actor_id, target_id, amount, action, reason, created_at FROM economy_audit WHERE guild_id = ? ORDER BY id DESC LIMIT ?",
                (guild_id, limit),
            )).fetchall()

    async def set_guild_setting(self, guild_id: int, setting: str, value: int):
        columns = {
            "welcome_channel_id": "welcome_channel_id",
            "log_channel_id": "log_channel_id",
            "default_role_id": "default_role_id",
        }
        column = columns.get(setting)
        if column is None:
            raise ValueError("Unsupported guild setting")
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                f"INSERT INTO guild_settings (guild_id, {column}) VALUES (?, ?) "
                f"ON CONFLICT(guild_id) DO UPDATE SET {column} = excluded.{column}",
                (guild_id, value),
            )
            await db.commit()

    async def get_guild_settings(self, guild_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            row = await (await db.execute(
                "SELECT welcome_channel_id, log_channel_id, default_role_id FROM guild_settings WHERE guild_id = ?",
                (guild_id,),
            )).fetchone()
            return row or (None, None, None)

    async def create_moderation_case(self, guild_id: int, target_id: int, moderator_id: int,
                                     action: str, reason: str, now: str):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute(
                "INSERT INTO moderation_cases (guild_id, target_id, moderator_id, action, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (guild_id, target_id, moderator_id, action, reason, now),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_moderation_cases(self, guild_id: int, target_id: int, limit: int = 10):
        async with aiosqlite.connect(self.db_name) as db:
            return await (await db.execute(
                "SELECT id, moderator_id, action, reason, created_at FROM moderation_cases WHERE guild_id = ? AND target_id = ? ORDER BY id DESC LIMIT ?",
                (guild_id, target_id, limit),
            )).fetchall()

    async def add_reminder(self, user_id: int, guild_id: int, channel_id: int, message: str, due_at: str):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute(
                "INSERT INTO reminders (user_id, guild_id, channel_id, message, due_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, guild_id, channel_id, message, due_at),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_due_reminders(self, now: str):
        async with aiosqlite.connect(self.db_name) as db:
            return await (await db.execute(
                "SELECT id, user_id, channel_id, message FROM reminders WHERE delivered = 0 AND due_at <= ? ORDER BY due_at",
                (now,),
            )).fetchall()

    async def mark_reminder_delivered(self, reminder_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE reminders SET delivered = 1 WHERE id = ?", (reminder_id,))
            await db.commit()

    async def create_questionnaire(self, guild_id: int, creator_id: int, channel_id: int,
                                  title: str, question: str, options: str, config: str, created_at: str):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute(
                "INSERT INTO questionnaires (guild_id, creator_id, title, question, options, config, channel_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (guild_id, creator_id, title, question, options, config, channel_id, created_at),
            )
            await db.commit()
            return cursor.lastrowid

    async def set_questionnaire_message(self, questionnaire_id: int, message_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE questionnaires SET message_id = ? WHERE id = ?", (message_id, questionnaire_id))
            await db.commit()

    async def deactivate_questionnaire(self, questionnaire_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("UPDATE questionnaires SET active = 0 WHERE id = ?", (questionnaire_id,))
            await db.commit()

    async def get_questionnaire_vote(self, questionnaire_id: int, user_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            row = await (await db.execute(
                "SELECT selected_options FROM questionnaire_votes WHERE questionnaire_id = ? AND user_id = ?",
                (questionnaire_id, user_id),
            )).fetchone()
            return row[0] if row else "[]"

    async def get_active_questionnaires(self):
        async with aiosqlite.connect(self.db_name) as db:
            return await (await db.execute(
                "SELECT id, message_id, options, config FROM questionnaires WHERE active = 1 AND message_id IS NOT NULL"
            )).fetchall()

    async def save_questionnaire_vote(self, questionnaire_id: int, user_id: int, selected_options: str):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT INTO questionnaire_votes (questionnaire_id, user_id, selected_options) VALUES (?, ?, ?) "
                "ON CONFLICT(questionnaire_id, user_id) DO UPDATE SET selected_options = excluded.selected_options",
                (questionnaire_id, user_id, selected_options),
            )
            await db.commit()

    async def backup(self, destination: str):
        source_path = self.db_name

        def create_backup():
            os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
            source = sqlite3.connect(source_path)
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
            finally:
                target.close()
                source.close()

        await __import__("asyncio").to_thread(create_backup)
        return Path(destination)

    async def transfer(self, sender_id: int, recipient_id: int, amount: int) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_user(db, sender_id)
            await self._ensure_user(db, recipient_id)
            cursor = await db.execute(
                "UPDATE guild_users SET balance = balance - ? WHERE guild_id = ? AND user_id = ? AND balance >= ?",
                (amount, self.guild_id, sender_id, amount),
            )
            if cursor.rowcount != 1:
                await db.rollback()
                return False
            await db.execute("UPDATE guild_users SET balance = balance + ? WHERE guild_id = ? AND user_id = ?", (amount, self.guild_id, recipient_id))
            await db.commit()
            return True

    async def claim_reward(self, user_id: int, column: str, cooldown_seconds: int, reward: int, now: str):
        if column not in {"last_daily", "last_work"}:
            raise ValueError("Invalid reward cooldown column")
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_user(db, user_id)
            row = await (await db.execute(
                f"SELECT {column}, daily_streak, next_work_bonus, next_daily_bonus FROM guild_users WHERE guild_id = ? AND user_id = ?", (self.guild_id, user_id)
            )).fetchone()
            last_claim, streak, work_bonus, daily_bonus = row
            if last_claim:
                from datetime import datetime
                current_time = datetime.fromisoformat(now)
                previous_time = datetime.fromisoformat(last_claim)
                if previous_time.tzinfo is None:
                    previous_time = previous_time.replace(tzinfo=current_time.tzinfo)
                elapsed = (current_time - previous_time).total_seconds()
                if elapsed < cooldown_seconds:
                    await db.rollback()
                    return False, int(cooldown_seconds - elapsed), streak
            if column == "last_daily":
                from datetime import datetime, timedelta
                previous_date = datetime.fromisoformat(last_claim).date() if last_claim else None
                today = datetime.fromisoformat(now).date()
                streak = streak + 1 if previous_date == today - timedelta(days=1) else 1
                await db.execute(
                    "UPDATE guild_users SET balance = balance + ?, last_daily = ?, daily_streak = ?, next_daily_bonus = 0 WHERE guild_id = ? AND user_id = ?",
                    (reward + reward * daily_bonus // 100, now, streak, self.guild_id, user_id),
                )
                reward += reward * daily_bonus // 100
            else:
                reward += reward * work_bonus // 100
                await db.execute(
                    "UPDATE guild_users SET balance = balance + ?, last_work = ?, next_work_bonus = 0 WHERE guild_id = ? AND user_id = ?",
                    (reward, now, self.guild_id, user_id),
                )
            await db.commit()
            return True, reward, streak

    async def bank_transfer(self, user_id: int, amount: int, deposit: bool) -> bool:
        source, destination = ("balance", "bank") if deposit else ("bank", "balance")
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_user(db, user_id)
            cursor = await db.execute(
                f"UPDATE guild_users SET {source} = {source} - ?, {destination} = {destination} + ? WHERE guild_id = ? AND user_id = ? AND {source} >= ?",
                (amount, amount, self.guild_id, user_id, amount),
            )
            if cursor.rowcount != 1:
                await db.rollback()
                return False
            await db.commit()
            return True

    async def purchase_item(self, user_id: int, item_name: str, price: int, expires_at: str = None) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_user(db, user_id)
            cursor = await db.execute(
                "UPDATE guild_users SET balance = balance - ? WHERE guild_id = ? AND user_id = ? AND balance >= ?",
                (price, self.guild_id, user_id, price),
            )
            if cursor.rowcount != 1:
                await db.rollback()
                return False
            if item_name != "loteria":
                await db.execute(
                    "INSERT INTO guild_inventory (guild_id, user_id, item_name, quantity, expires_at) VALUES (?, ?, ?, 1, ?) "
                    "ON CONFLICT(guild_id, user_id, item_name) DO UPDATE SET quantity = quantity + 1, expires_at = COALESCE(excluded.expires_at, guild_inventory.expires_at)",
                    (self.guild_id, user_id, item_name, expires_at),
                )
            await db.commit()
            return True

    async def settle_lottery(self, user_id: int, price: int, prize: int) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_user(db, user_id)
            cursor = await db.execute(
                "UPDATE guild_users SET balance = balance - ? + ? WHERE guild_id = ? AND user_id = ? AND balance >= ?",
                (price, prize, self.guild_id, user_id, price),
            )
            if cursor.rowcount != 1:
                await db.rollback()
                return False
            await db.commit()
            return True

    async def settle_wager(self, user_id: int, amount: int, won: bool) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            await self._ensure_user(db, user_id)
            if won:
                await db.execute("UPDATE guild_users SET balance = balance + ? WHERE guild_id = ? AND user_id = ?", (amount, self.guild_id, user_id))
                await db.commit()
                return True
            cursor = await db.execute(
                "UPDATE guild_users SET balance = balance - ? WHERE guild_id = ? AND user_id = ? AND balance >= ?",
                (amount, self.guild_id, user_id, amount),
            )
            await db.commit()
            return cursor.rowcount == 1

    async def rob(self, thief_id: int, victim_id: int, now: str, cooldown_seconds: int,
                  success_chance: int, fine_percentage: int, stolen_percentage: int):
        from datetime import datetime
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_user(db, thief_id)
            await self._ensure_user(db, victim_id)
            thief = await (await db.execute(
                "SELECT balance, last_rob, next_rob_insurance FROM guild_users WHERE guild_id = ? AND user_id = ?", (self.guild_id, thief_id)
            )).fetchone()
            victim_balance = (await (await db.execute("SELECT balance FROM guild_users WHERE guild_id = ? AND user_id = ?", (self.guild_id, victim_id))).fetchone())[0]
            if thief[1]:
                current_time = datetime.fromisoformat(now)
                previous_time = datetime.fromisoformat(thief[1])
                if previous_time.tzinfo is None:
                    previous_time = previous_time.replace(tzinfo=current_time.tzinfo)
                elapsed = (current_time - previous_time).total_seconds()
                if elapsed < cooldown_seconds:
                    await db.rollback()
                    return "cooldown", int(cooldown_seconds - elapsed), 0
            if victim_balance <= 50:
                await db.rollback()
                return "poor", 0, 0

            await db.execute("UPDATE guild_users SET last_rob = ? WHERE guild_id = ? AND user_id = ?", (now, self.guild_id, thief_id))
            shield = await (await db.execute(
                "SELECT quantity, expires_at FROM guild_inventory WHERE guild_id = ? AND user_id = ? AND item_name = 'escudo'", (self.guild_id, victim_id)
            )).fetchone()
            shield_expiry = datetime.fromisoformat(shield[1]) if shield and shield[1] else None
            if shield_expiry and shield_expiry.tzinfo is None:
                shield_expiry = shield_expiry.replace(tzinfo=datetime.fromisoformat(now).tzinfo)
            if shield and shield[0] > 0 and (shield_expiry is None or shield_expiry > datetime.fromisoformat(now)):
                if shield[0] == 1:
                    await db.execute("DELETE FROM guild_inventory WHERE guild_id = ? AND user_id = ? AND item_name = 'escudo'", (self.guild_id, victim_id))
                else:
                    await db.execute("UPDATE guild_inventory SET quantity = quantity - 1 WHERE guild_id = ? AND user_id = ? AND item_name = 'escudo'", (self.guild_id, victim_id))
                await db.commit()
                return "shield", 0, 0

            lockpick = await (await db.execute(
                "SELECT quantity FROM guild_inventory WHERE guild_id = ? AND user_id = ? AND item_name = 'ganzua'", (self.guild_id, thief_id)
            )).fetchone()
            if lockpick and lockpick[0] > 0:
                success_chance = min(95, success_chance + 20)
                if lockpick[0] == 1:
                    await db.execute("DELETE FROM guild_inventory WHERE guild_id = ? AND user_id = ? AND item_name = 'ganzua'", (self.guild_id, thief_id))
                else:
                    await db.execute("UPDATE guild_inventory SET quantity = quantity - 1 WHERE guild_id = ? AND user_id = ? AND item_name = 'ganzua'", (self.guild_id, thief_id))

            import random
            if random.randint(1, 100) <= success_chance:
                amount = max(1, int(victim_balance * stolen_percentage / 100))
                cursor = await db.execute(
                    "UPDATE guild_users SET balance = balance - ? WHERE guild_id = ? AND user_id = ? AND balance >= ?",
                    (amount, self.guild_id, victim_id, amount),
                )
                if cursor.rowcount != 1:
                    await db.rollback()
                    return "failed", 0, 0
                await db.execute("UPDATE guild_users SET balance = balance + ? WHERE guild_id = ? AND user_id = ?", (amount, self.guild_id, thief_id))
                await db.commit()
                return "success", amount, 0

            if thief[2]:
                await db.execute("UPDATE guild_users SET next_rob_insurance = 0 WHERE guild_id = ? AND user_id = ?", (self.guild_id, thief_id))
                await db.commit()
                return "insured", 0, 0
            fine = min(thief[0], max(10, int(thief[0] * fine_percentage / 100)))
            await db.execute("UPDATE guild_users SET balance = balance - ? WHERE guild_id = ? AND user_id = ?", (fine, self.guild_id, thief_id))
            await db.commit()
            return "caught", fine, 0

    async def get_item_count(self, user_id: int, item_name: str) -> int:
        async with aiosqlite.connect(self.db_name) as db:
            row = await (await db.execute(
                "SELECT quantity FROM guild_inventory WHERE guild_id = ? AND user_id = ? AND item_name = ?", (self.guild_id, user_id, item_name)
            )).fetchone()
            return row[0] if row else 0

    async def get_inventory(self, user_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            return await (await db.execute(
                "SELECT item_name, quantity, expires_at FROM guild_inventory WHERE guild_id = ? AND user_id = ? AND quantity > 0 ORDER BY item_name",
                (self.guild_id, user_id),
            )).fetchall()

    async def add_item(self, user_id: int, item_name: str, quantity: int = 1, expires_at: str = None):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT INTO guild_inventory (guild_id, user_id, item_name, quantity, expires_at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(guild_id, user_id, item_name) DO UPDATE SET quantity = quantity + excluded.quantity, expires_at = COALESCE(excluded.expires_at, guild_inventory.expires_at)",
                (self.guild_id, user_id, item_name, quantity, expires_at),
            )
            await db.commit()

    async def update_user_xp_level(self, user_id: int, xp_add: int, level_multiplier: int,
                                   last_msg_time: float, cooldown_seconds: int = 0):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_user(db, user_id)
            row = await (await db.execute(
                "SELECT xp, level, last_message_time FROM guild_users WHERE guild_id = ? AND user_id = ?", (self.guild_id, user_id)
            )).fetchone()
            if last_msg_time - row[2] < cooldown_seconds:
                await db.rollback()
                return -1
            starting_level = row[1]
            xp, level = row[0] + xp_add, row[1]
            while xp >= level * level_multiplier:
                xp -= level * level_multiplier
                level += 1
            await db.execute(
                "UPDATE guild_users SET xp = ?, level = ?, last_message_time = ? WHERE guild_id = ? AND user_id = ?",
                (xp, level, last_msg_time, self.guild_id, user_id),
            )
            await db.commit()
            return level - starting_level

    async def get_leaderboard(self, limit: int = 10):
        async with aiosqlite.connect(self.db_name) as db:
            return await (await db.execute(
                """
                SELECT user_id,
                    balance + bank
                        + COALESCE((SELECT SUM(p.quantity * a.price) FROM guild_portfolio p JOIN market_assets a ON a.symbol = p.symbol WHERE p.user_id = guild_users.user_id AND p.guild_id = guild_users.guild_id), 0)
                        + COALESCE((SELECT SUM(c.price) FROM guild_property_holdings h JOIN property_catalog c ON c.property_key = h.property_key WHERE h.user_id = guild_users.user_id AND h.guild_id = guild_users.guild_id), 0) AS wealth
                    FROM guild_users WHERE guild_id = ? ORDER BY wealth DESC LIMIT ?
                """,
                    (self.guild_id, limit),
            )).fetchall()

    async def get_user_wealth(self, user_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            row = await (await db.execute(
                """
                SELECT u.balance, u.bank,
                    COALESCE((SELECT SUM(p.quantity * a.price) FROM guild_portfolio p JOIN market_assets a ON a.symbol = p.symbol WHERE p.user_id = u.user_id AND p.guild_id = u.guild_id), 0),
                    COALESCE((SELECT SUM(c.price) FROM guild_property_holdings h JOIN property_catalog c ON c.property_key = h.property_key WHERE h.user_id = u.user_id AND h.guild_id = u.guild_id), 0)
                FROM guild_users u WHERE u.guild_id = ? AND u.user_id = ?
                """,
                 (self.guild_id, user_id),
            )).fetchone()
            return row or (0, 0, 0, 0)

    async def get_market_assets(self):
        async with aiosqlite.connect(self.db_name) as db:
            return await (await db.execute(
                "SELECT symbol, name, price, last_change_pct, buy_volume, sell_volume FROM market_assets ORDER BY symbol"
            )).fetchall()

    async def advance_market(self, now: datetime):
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            last_tick_text = (await (await db.execute(
                "SELECT last_tick FROM market_state WHERE id = 1"
            )).fetchone())[0]
            last_tick = datetime.fromisoformat(last_tick_text)
            if last_tick.tzinfo is None:
                last_tick = last_tick.replace(tzinfo=now.tzinfo)
            elapsed_hours = int((now - last_tick).total_seconds() // 3600)
            if elapsed_hours < 1:
                await db.rollback()
                return 0
            ticks = min(elapsed_hours, 168)
            assets = await (await db.execute(
                "SELECT symbol, price, buy_volume, sell_volume FROM market_assets"
            )).fetchall()
            for symbol, original_price, buy_volume, sell_volume in assets:
                price = original_price
                last_change = 0.0
                for hour in range(ticks):
                    pressure = 0.0
                    if hour == 0:
                        net_volume = buy_volume - sell_volume
                        pressure = max(-1.0, min(1.0, net_volume / max(price * 20, 1))) * Config.MARKET_FLOW_IMPACT_PERCENT
                    last_change = max(
                        -Config.MARKET_MAX_CHANGE_PERCENT,
                        min(
                            Config.MARKET_MAX_CHANGE_PERCENT,
                            random.uniform(Config.MARKET_BASE_CHANGE_MIN, Config.MARKET_BASE_CHANGE_MAX) + pressure,
                        ),
                    )
                    price = max(1, round(price * (1 + last_change / 100)))
                await db.execute(
                    "UPDATE market_assets SET price = ?, last_change_pct = ?, buy_volume = 0, sell_volume = 0, updated_at = ? WHERE symbol = ?",
                    (price, last_change, (last_tick + timedelta(hours=ticks)).isoformat(), symbol),
                )
            next_tick = last_tick + timedelta(hours=ticks)
            await db.execute("UPDATE market_state SET last_tick = ? WHERE id = 1", (next_tick.isoformat(),))
            await db.commit()
            return ticks

    async def trade_asset(self, user_id: int, symbol: str, quantity: int, buy: bool):
        if quantity <= 0:
            return False, 0, 0, 0.0
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_user(db, user_id)
            asset = await (await db.execute(
                "SELECT price FROM market_assets WHERE symbol = ?", (symbol.upper(),)
            )).fetchone()
            if not asset:
                await db.rollback()
                return False, 0, 0, 0.0
            price = asset[0]
            total = price * quantity
            if buy:
                holding = await (await db.execute(
                    "SELECT quantity, average_cost FROM guild_portfolio WHERE guild_id = ? AND user_id = ? AND symbol = ?",
                    (self.guild_id, user_id, symbol.upper()),
                )).fetchone()
                if holding and holding[0] + quantity > Config.MARKET_USER_HOLDING_MAX:
                    await db.rollback()
                    return False, price, total, 0.0
                cursor = await db.execute(
                    "UPDATE guild_users SET balance = balance - ? WHERE guild_id = ? AND user_id = ? AND balance >= ?",
                    (total, self.guild_id, user_id, total),
                )
                if cursor.rowcount != 1:
                    await db.rollback()
                    return False, price, total, 0.0
                if holding:
                    old_quantity, old_average = holding
                    average_cost = (old_quantity * old_average + total) / (old_quantity + quantity)
                    await db.execute(
                        "UPDATE guild_portfolio SET quantity = quantity + ?, average_cost = ? WHERE guild_id = ? AND user_id = ? AND symbol = ?",
                        (quantity, average_cost, self.guild_id, user_id, symbol.upper()),
                    )
                else:
                    await db.execute(
                        "INSERT INTO guild_portfolio (guild_id, user_id, symbol, quantity, average_cost) VALUES (?, ?, ?, ?, ?)",
                        (self.guild_id, user_id, symbol.upper(), quantity, price),
                    )
                await db.execute(
                    "UPDATE market_assets SET buy_volume = buy_volume + ? WHERE symbol = ?",
                    (total, symbol.upper()),
                )
                await db.execute(
                    "INSERT INTO market_trades (guild_id, user_id, symbol, action, quantity, unit_price, total, created_at) VALUES (?, ?, ?, 'buy', ?, ?, ?, ?)",
                    (self.guild_id, user_id, symbol.upper(), quantity, price, total, datetime.now(timezone.utc).isoformat()),
                )
                await db.commit()
                return True, price, total, 0.0

            holding = await (await db.execute(
                "SELECT quantity, average_cost FROM guild_portfolio WHERE guild_id = ? AND user_id = ? AND symbol = ?",
                (self.guild_id, user_id, symbol.upper()),
            )).fetchone()
            if not holding or holding[0] < quantity:
                await db.rollback()
                return False, price, total, 0.0
            owned, average_cost = holding
            profit = (price - average_cost) * quantity
            if owned == quantity:
                await db.execute("DELETE FROM guild_portfolio WHERE guild_id = ? AND user_id = ? AND symbol = ?", (self.guild_id, user_id, symbol.upper()))
            else:
                await db.execute(
                    "UPDATE guild_portfolio SET quantity = quantity - ? WHERE guild_id = ? AND user_id = ? AND symbol = ?",
                    (quantity, self.guild_id, user_id, symbol.upper()),
                )
            await db.execute("UPDATE guild_users SET balance = balance + ? WHERE guild_id = ? AND user_id = ?", (total, self.guild_id, user_id))
            await db.execute(
                "UPDATE market_assets SET sell_volume = sell_volume + ? WHERE symbol = ?",
                (total, symbol.upper()),
            )
            await db.execute(
                "INSERT INTO market_trades (guild_id, user_id, symbol, action, quantity, unit_price, total, realized_profit, created_at) VALUES (?, ?, ?, 'sell', ?, ?, ?, ?, ?)",
                (self.guild_id, user_id, symbol.upper(), quantity, price, total, profit, datetime.now(timezone.utc).isoformat()),
            )
            await db.commit()
            return True, price, total, profit

    async def get_market_trade_history(self, user_id: int, limit: int = 10):
        async with aiosqlite.connect(self.db_name) as db:
            return await (await db.execute(
                "SELECT symbol, action, quantity, unit_price, total, realized_profit, created_at FROM market_trades WHERE guild_id = ? AND user_id = ? ORDER BY id DESC LIMIT ?",
                (self.guild_id, user_id, limit),
            )).fetchall()

    async def get_portfolio(self, user_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            return await (await db.execute(
                """
                SELECT p.symbol, a.name, p.quantity, p.average_cost, a.price,
                    p.quantity * a.price AS value,
                    p.quantity * (a.price - p.average_cost) AS profit
                FROM guild_portfolio p JOIN market_assets a ON a.symbol = p.symbol
                WHERE p.guild_id = ? AND p.user_id = ? ORDER BY p.symbol
                """,
                (self.guild_id, user_id),
            )).fetchall()

    async def buy_property(self, user_id: int, property_key: str, now: str):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_user(db, user_id)
            property_row = await (await db.execute(
                "SELECT price FROM property_catalog WHERE property_key = ?", (property_key,)
            )).fetchone()
            if not property_row:
                await db.rollback()
                return False, 0
            price = property_row[0]
            cursor = await db.execute(
                "UPDATE guild_users SET balance = balance - ? WHERE guild_id = ? AND user_id = ? AND balance >= ?",
                (price, self.guild_id, user_id, price),
            )
            if cursor.rowcount != 1:
                await db.rollback()
                return False, price
            await db.execute(
                "INSERT INTO guild_property_holdings (guild_id, user_id, property_key, purchased_at, last_collected_at) VALUES (?, ?, ?, ?, ?)",
                (self.guild_id, user_id, property_key, now, now),
            )
            await db.commit()
            return True, price

    async def sell_property(self, user_id: int, property_key: str, resale_percent: int = 75):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            property_row = await (await db.execute(
                "SELECT price FROM property_catalog WHERE property_key = ?", (property_key,)
            )).fetchone()
            if not property_row:
                await db.rollback()
                return False, 0
            holding = await (await db.execute(
                "SELECT id FROM guild_property_holdings WHERE guild_id = ? AND user_id = ? AND property_key = ? ORDER BY purchased_at LIMIT 1",
                (self.guild_id, user_id, property_key),
            )).fetchone()
            if not holding:
                await db.rollback()
                return False, 0
            resale_value = property_row[0] * resale_percent // 100
            await db.execute("DELETE FROM guild_property_holdings WHERE guild_id = ? AND user_id = ? AND id = ?", (self.guild_id, user_id, holding[0]))
            await db.execute(
                "UPDATE guild_users SET balance = balance + ? WHERE guild_id = ? AND user_id = ?",
                (resale_value, self.guild_id, user_id),
            )
            await db.commit()
            return True, resale_value

    async def get_properties(self, user_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            return await (await db.execute(
                """
                SELECT c.property_key, c.name, c.price, c.rent_per_hour, COUNT(h.id)
                FROM property_catalog c LEFT JOIN guild_property_holdings h
                    ON h.property_key = c.property_key AND h.user_id = ? AND h.guild_id = ?
                GROUP BY c.property_key ORDER BY c.price
                """,
                (user_id, self.guild_id),
            )).fetchall()

    async def collect_rent(self, user_id: int, now: datetime):
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_user(db, user_id)
            holdings = await (await db.execute(
                """
                SELECT h.id, h.last_collected_at, c.rent_per_hour
                FROM guild_property_holdings h JOIN property_catalog c ON c.property_key = h.property_key
                WHERE h.guild_id = ? AND h.user_id = ?
                """,
                (self.guild_id, user_id),
            )).fetchall()
            payout = 0
            for holding_id, collected_text, rent_per_hour in holdings:
                collected_at = datetime.fromisoformat(collected_text)
                if collected_at.tzinfo is None:
                    collected_at = collected_at.replace(tzinfo=now.tzinfo)
                hours = min(
                    Config.PROPERTY_RENT_CAP_HOURS,
                    max(0, int((now - collected_at).total_seconds() // 3600)),
                )
                if hours:
                    payout += rent_per_hour * hours
                    await db.execute(
                        "UPDATE guild_property_holdings SET last_collected_at = ? WHERE guild_id = ? AND id = ?",
                        ((collected_at + timedelta(hours=hours)).isoformat(), self.guild_id, holding_id),
                    )
            if payout:
                await db.execute("UPDATE guild_users SET bank = bank + ? WHERE guild_id = ? AND user_id = ?", (payout, self.guild_id, user_id))
            await db.commit()
            return payout

    async def activate_work_boost(self, user_id: int, bonus_percent: int = 50):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_user(db, user_id)
            cursor = await db.execute(
                "UPDATE guild_inventory SET quantity = quantity - 1 WHERE guild_id = ? AND user_id = ? AND item_name = 'cafe' AND quantity > 0",
                (self.guild_id, user_id),
            )
            if cursor.rowcount != 1:
                await db.rollback()
                return False
            await db.execute("DELETE FROM guild_inventory WHERE guild_id = ? AND user_id = ? AND item_name = 'cafe' AND quantity = 0", (self.guild_id, user_id))
            await db.execute(
                "UPDATE guild_users SET next_work_bonus = MIN(next_work_bonus + ?, 100) WHERE guild_id = ? AND user_id = ?",
                (bonus_percent, self.guild_id, user_id),
            )
            await db.commit()
            return True

    async def activate_daily_coupon(self, user_id: int, bonus_percent: int = 100):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_user(db, user_id)
            cursor = await db.execute(
                "UPDATE guild_inventory SET quantity = quantity - 1 WHERE guild_id = ? AND user_id = ? AND item_name = 'cupon_diario' AND quantity > 0",
                (self.guild_id, user_id),
            )
            if cursor.rowcount != 1:
                await db.rollback()
                return False
            await db.execute(
                "DELETE FROM guild_inventory WHERE guild_id = ? AND user_id = ? AND item_name = 'cupon_diario' AND quantity = 0",
                (self.guild_id, user_id),
            )
            await db.execute(
                "UPDATE guild_users SET next_daily_bonus = MIN(next_daily_bonus + ?, 200) WHERE guild_id = ? AND user_id = ?",
                (bonus_percent, self.guild_id, user_id),
            )
            await db.commit()
            return True

    async def activate_robbery_insurance(self, user_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_user(db, user_id)
            cursor = await db.execute(
                "UPDATE guild_inventory SET quantity = quantity - 1 WHERE guild_id = ? AND user_id = ? AND item_name = 'seguro' AND quantity > 0",
                (self.guild_id, user_id),
            )
            if cursor.rowcount != 1:
                await db.rollback()
                return False
            await db.execute(
                "DELETE FROM guild_inventory WHERE guild_id = ? AND user_id = ? AND item_name = 'seguro' AND quantity = 0",
                (self.guild_id, user_id),
            )
            await db.execute("UPDATE guild_users SET next_rob_insurance = 1 WHERE guild_id = ? AND user_id = ?", (self.guild_id, user_id))
            await db.commit()
            return True

    async def open_crate(self, user_id: int, prize: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("BEGIN IMMEDIATE")
            await self._ensure_user(db, user_id)
            cursor = await db.execute(
                "UPDATE guild_inventory SET quantity = quantity - 1 WHERE guild_id = ? AND user_id = ? AND item_name = 'caja' AND quantity > 0",
                (self.guild_id, user_id),
            )
            if cursor.rowcount != 1:
                await db.rollback()
                return False
            await db.execute("DELETE FROM guild_inventory WHERE guild_id = ? AND user_id = ? AND item_name = 'caja' AND quantity = 0", (self.guild_id, user_id))
            await db.execute("UPDATE guild_users SET balance = balance + ? WHERE guild_id = ? AND user_id = ?", (prize, self.guild_id, user_id))
            await db.commit()
            return True