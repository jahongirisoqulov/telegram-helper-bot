import os
import asyncio
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

BOT_TOKEN = os.getenv("BOT_TOKEN")

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

# ================= STORAGE =================
reminders = {}  # vaqtinchalik (RAM)

# ================= STATES =================
class Register(StatesGroup):
    phone = State()
    fullname = State()

class Reminder(StatesGroup):
    time = State()
    text = State()

class MoneyState(StatesGroup):
    amount = State()

# ================= HELPERS =================
def is_registered(user_id):
    cur.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    return cur.fetchone() is not None

def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔔 Eslatma qo‘shish", "📋 Eslatmalarim")
    kb.add("➕ Kirim", "➖ Chiqim")
    kb.add("💼 Balans")
    return kb

# ================= START =================
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
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

# ================= REMINDER =================
@dp.message_handler(lambda m: m.text == "🔔 Eslatma qo‘shish")
async def add_reminder(message: types.Message):
    await message.answer("⏰ Vaqt yoz\nMasalan: 2026-01-05 18:30")
    await Reminder.time.set()

@dp.message_handler(state=Reminder.time)
async def reminder_time(message: types.Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
        seconds = (dt - uz_now()).total_seconds()
        if seconds <= 0:
            await message.answer("❌ O‘tib ketgan vaqt")
            return
        await state.update_data(seconds=seconds, time=dt)
        await message.answer("✍️ Matn yoz")
        await Reminder.text.set()
    except:
        await message.answer("❌ Format xato")

@dp.message_handler(state=Reminder.text)
async def reminder_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    task = asyncio.create_task(send_reminder(message.chat.id, data["seconds"], message.text))
    reminders.setdefault(message.from_user.id, []).append(
        {"time": data["time"], "text": message.text, "task": task}
    )
    await message.answer("✅ Eslatma saqlandi", reply_markup=main_menu())
    await state.finish()

async def send_reminder(chat_id, seconds, text):
    await asyncio.sleep(seconds)
    await bot.send_message(chat_id, f"🔔 ESLATMA:\n{text}")

@dp.message_handler(lambda m: m.text == "📋 Eslatmalarim")
async def list_reminders(message: types.Message):
    lst = reminders.get(message.from_user.id, [])
    if not lst:
        await message.answer("📭 Yo‘q")
        return
    text = "📋 Eslatmalar:\n\n"
    for r in lst:
        text += f"{r['time'].strftime('%Y-%m-%d %H:%M')} — {r['text']}\n"
    await message.answer(text)

# ================= MONEY =================
@dp.message_handler(lambda m: m.text == "➕ Kirim")
async def income(message: types.Message, state: FSMContext):
    await state.update_data(type="in")
    await message.answer("💰 Kirim summasini yoz")
    await MoneyState.amount.set()

@dp.message_handler(lambda m: m.text == "➖ Chiqim")
async def expense(message: types.Message, state: FSMContext):
    await state.update_data(type="out")
    await message.answer("💸 Chiqim summasini yoz")
    await MoneyState.amount.set()

@dp.message_handler(state=MoneyState.amount)
async def save_money(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Faqat raqam yoz")
        return
    data = await state.get_data()
    cur.execute(
        "INSERT INTO money (user_id, amount, type, created_at) VALUES (?, ?, ?, ?)",
        (message.from_user.id, int(message.text), data["type"], uz_now().isoformat())
    )
    db.commit()
    await message.answer("✅ Saqlandi", reply_markup=main_menu())
    await state.finish()

@dp.message_handler(lambda m: m.text == "💼 Balans")
async def balance(message: types.Message):
    cur.execute(
        "SELECT SUM(CASE WHEN type='in' THEN amount ELSE -amount END) FROM money WHERE user_id=?",
        (message.from_user.id,)
    )
    bal = cur.fetchone()[0] or 0
    await message.answer(f"💼 Balans: {bal} so‘m")

# ================= RUN =================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
