import sqlite3
import aiosqlite
from config import Config

class Database:
    def __init__(self):
        self.db_name = Config.DB_NAME

    async def connect(self):
        """Devuelve una conexión asíncrona a la base de datos."""
        return await aiosqlite.connect(self.db_name)

    async def setup(self):
        """Inicializa y crea las tablas necesarias si no existen."""
        async with aiosqlite.connect(self.db_name) as db:
            # Tabla de usuarios (Economía y Niveles)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    bank INTEGER DEFAULT 0,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    last_daily TEXT,
                    last_rob TEXT,
                    last_message_time REAL DEFAULT 0
                )
            """)

            # Tabla de inventario para objetos competitivos (Escudos, Ganzúas, etc.)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    user_id INTEGER,
                    item_name TEXT,
                    quantity INTEGER DEFAULT 0,
                    expires_at TEXT,
                    PRIMARY KEY (user_id, item_name)
                )
            """)

            # Tabla para almacenar cuestionarios personalizados creados por modales
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

            await db.commit()

    # ==========================================
    # FUNCIONES DE USUARIO / ECONOMÍA / NIVELES
    # ==========================================
    async def get_user(self, user_id: int):
        """Obtiene o crea un usuario en la base de datos."""
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("SELECT balance, bank, xp, level, last_daily, last_rob, last_message_time FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
                    await db.commit()
                    return {"balance": 0, "bank": 0, "xp": 0, "level": 1, "last_daily": None, "last_rob": None, "last_message_time": 0}
                return {
                    "balance": row[0],
                    "bank": row[1],
                    "xp": row[2],
                    "level": row[3],
                    "last_daily": row[4],
                    "last_rob": row[5],
                    "last_message_time": row[6]
                }

    async def update_user_balance(self, user_id: int, amount: int):
        """Suma o resta dinero al balance del usuario."""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT INTO users (user_id, balance) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?", (user_id, amount, amount))
            await db.commit()

    async def update_user_xp_level(self, user_id: int, xp_add: int, new_level: int, last_msg_time: float):
        """Actualiza la experiencia, nivel y el tiempo del último mensaje para el cooldown."""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("""
                INSERT INTO users (user_id, xp, level, last_message_time) VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET 
                    xp = xp + ?, 
                    level = ?, 
                    last_message_time = ?
            """, (user_id, xp_add, new_level, last_msg_time, xp_add, new_level, last_msg_time))
            await db.commit()

    # ==========================================
    # FUNCIONES DE INVENTARIO
    # ==========================================
    async def get_item_count(self, user_id: int, item_name: str) -> int:
        """Devuelve la cantidad de un objeto específico que tiene el usuario."""
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def add_item(self, user_id: int, item_name: str, quantity: int = 1, expires_at: str = None):
        """Añade o incrementa un objeto en el inventario del usuario."""
        async with aiosqlite.connect(self.db_name) as db:
            current = await self.get_item_count(user_id, item_name)
            if current == 0:
                await db.execute("INSERT INTO inventory (user_id, item_name, quantity, expires_at) VALUES (?, ?, ?, ?)", (user_id, item_name, quantity, expires_at))
            else:
                await db.execute("UPDATE inventory SET quantity = quantity + ?, expires_at = COALESCE(?, expires_at) WHERE user_id = ? AND item_name = ?", (quantity, expires_at, user_id, item_name))
            await db.commit()