import aiosqlite

DB_NAME = "bot.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            phone TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            remind_at TEXT,
            is_sent INTEGER DEFAULT 0
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            type TEXT
        )
        """)
        await db.commit()

async def add_user(user_id, full_name, phone):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users VALUES (?, ?, ?)",
            (user_id, full_name, phone)
        )
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return await cur.fetchone()

async def add_reminder(user_id, text, remind_at):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO reminders (user_id, text, remind_at) VALUES (?, ?, ?)",
            (user_id, text, remind_at)
        )
        await db.commit()

async def get_pending_reminders():
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT id, user_id, text FROM reminders WHERE is_sent=0 AND remind_at<=datetime('now')"
        )
        return await cur.fetchall()

async def mark_sent(reminder_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE reminders SET is_sent=1 WHERE id=?",
            (reminder_id,)
        )
        await db.commit()

async def add_transaction(user_id, amount, t_type):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO transactions (user_id, amount, type) VALUES (?, ?, ?)",
            (user_id, amount, t_type)
        )
        await db.commit()

async def get_balance(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("""
        SELECT
        SUM(CASE WHEN type='in' THEN amount ELSE 0 END) -
        SUM(CASE WHEN type='out' THEN amount ELSE 0 END)
        FROM transactions WHERE user_id=?
        """, (user_id,))
        row = await cur.fetchone()
        return row[0] or 0
