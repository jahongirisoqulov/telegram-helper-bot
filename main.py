import os
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# ================= TIME =================
def uz_now():
    return datetime.utcnow() + timedelta(hours=5)

# ================= DATABASE =================
db = sqlite3.connect("bot.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    full_name TEXT,
    phone TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS money (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    type TEXT,
    created_at TEXT
)
""")
db.commit()

# ================= STATES =================
class Register(StatesGroup):
    phone = State()
    fullname = State()

class MoneyState(StatesGroup):
    amount = State()

# ================= HELPERS =================
async def is_subscribed(user_id):
    try:
        m = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return m.status in ("member", "administrator", "creator")
    except:
        return False

def is_registered(user_id):
    cur.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    return cur.fetchone() is not None

def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Kirim", "➖ Chiqim")
    kb.add("💼 Balans", "📊 Statistika")
    kb.add("❌ Pulni o‘chirish")
    return kb

# ================= START =================
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(
            "📢 Kanalga obuna bo‘lish",
            url=f"https://t.me/{CHANNEL_USERNAME.replace('@','')}"
        ))
        await message.answer(
            "❗ Botdan foydalanish uchun kanalga obuna bo‘ling",
            reply_markup=kb
        )
        return

    if is_registered(message.from_user.id):
        await message.answer("👋 Xush kelibsan!", reply_markup=main_menu())
        return

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("📱 Telefon raqam yuborish", request_contact=True))
    await message.answer("📱 Telefon raqamingni yubor", reply_markup=kb)
    await Register.phone.set()

# ================= REGISTER =================
@dp.message_handler(content_types=types.ContentType.CONTACT, state=Register.phone)
async def phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    await message.answer("👤 Ism familiyangni yoz", reply_markup=types.ReplyKeyboardRemove())
    await Register.fullname.set()

@dp.message_handler(state=Register.fullname)
async def fullname(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cur.execute(
        "INSERT OR REPLACE INTO users VALUES (?, ?, ?)",
        (message.from_user.id, message.text, data["phone"])
    )
    db.commit()
    await message.answer("✅ Tayyor!", reply_markup=main_menu())
    await state.finish()

# ================= MONEY ADD =================
@dp.message_handler(lambda m: m.text == "➕ Kirim")
async def income(message: types.Message, state: FSMContext):
    await state.update_data(type="in")
    await message.answer("💰 Summani yoz")
    await MoneyState.amount.set()

@dp.message_handler(lambda m: m.text == "➖ Chiqim")
async def expense(message: types.Message, state: FSMContext):
    await state.update_data(type="out")
    await message.answer("💸 Summani yoz")
    await MoneyState.amount.set()

@dp.message_handler(state=MoneyState.amount)
async def save_money(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Faqat raqam")
        return
    data = await state.get_data()
    cur.execute(
        "INSERT INTO money (user_id, amount, type, created_at) VALUES (?, ?, ?, ?)",
        (message.from_user.id, int(message.text), data["type"], uz_now().isoformat())
    )
    db.commit()
    await message.answer("✅ Saqlandi", reply_markup=main_menu())
    await state.finish()

# ================= BALANCE =================
@dp.message_handler(lambda m: m.text == "💼 Balans")
async def balance(message: types.Message):
    cur.execute("""
    SELECT SUM(CASE WHEN type='in' THEN amount ELSE -amount END)
    FROM money WHERE user_id=?
    """, (message.from_user.id,))
    bal = cur.fetchone()[0] or 0
    await message.answer(f"💼 Balans: {bal} so‘m")

# ================= STATISTICS =================
@dp.message_handler(lambda m: m.text == "📊 Statistika")
async def stats(message: types.Message):
    today = uz_now().date().isoformat()
    month = uz_now().strftime("%Y-%m")

    cur.execute("""
    SELECT
    SUM(CASE WHEN type='in' THEN amount ELSE 0 END),
    SUM(CASE WHEN type='out' THEN amount ELSE 0 END)
    FROM money WHERE user_id=? AND DATE(created_at)=?
    """, (message.from_user.id, today))
    d_in, d_out = cur.fetchone()

    cur.execute("""
    SELECT
    SUM(CASE WHEN type='in' THEN amount ELSE 0 END),
    SUM(CASE WHEN type='out' THEN amount ELSE 0 END)
    FROM money WHERE user_id=? AND strftime('%Y-%m', created_at)=?
    """, (message.from_user.id, month))
    m_in, m_out = cur.fetchone()

    await message.answer(
        "📊 STATISTIKA\n\n"
        f"📅 Bugun:\n➕ {d_in or 0} so‘m\n➖ {d_out or 0} so‘m\n\n"
        f"🗓 Oy:\n➕ {m_in or 0} so‘m\n➖ {m_out or 0} so‘m"
    )

# ================= DELETE MONEY =================
@dp.message_handler(lambda m: m.text == "❌ Pulni o‘chirish")
async def delete_money(message: types.Message):
    cur.execute(
        "SELECT id, amount, type FROM money WHERE user_id=? ORDER BY id DESC LIMIT 5",
        (message.from_user.id,)
    )
    rows = cur.fetchall()
    if not rows:
        await message.answer("❌ Pul yozuvi yo‘q")
        return

    kb = types.InlineKeyboardMarkup()
    for r in rows:
        kb.add(types.InlineKeyboardButton(
            f"{r[1]} ({r[2]}) ❌", callback_data=f"delmoney_{r[0]}"
        ))
    await message.answer("Qaysini o‘chirasan?", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("delmoney_"))
async def del_money(call: types.CallbackQuery):
    mid = int(call.data.split("_")[1])
    cur.execute("DELETE FROM money WHERE id=?", (mid,))
    db.commit()
    await call.message.answer("❌ O‘chirildi")
    await call.answer()

# ================= RUN =================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
