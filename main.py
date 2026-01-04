import os
import asyncio
import sqlite3
import time
from datetime import datetime

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# ================= DATABASE =================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    text TEXT,
    remind_ts INTEGER,
    sent INTEGER DEFAULT 0
)
""")
conn.commit()

# ================= STATE =================
class Register(StatesGroup):
    phone = State()
    fullname = State()

class Reminder(StatesGroup):
    time = State()
    text = State()

# ================= START =================
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("📱 Telefon raqam yuborish", request_contact=True))

    await message.answer(
        "📱 Botdan foydalanish uchun telefon raqamingni yubor",
        reply_markup=kb
    )
    await Register.phone.set()

# ================= PHONE =================
@dp.message_handler(content_types=types.ContentType.CONTACT, state=Register.phone)
async def get_phone(message: types.Message, state: FSMContext):
    await message.answer(
        "👤 Ism familiyangni yoz\nMasalan: Jahongir Isoqulov",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await Register.fullname.set()

# ================= FULL NAME =================
@dp.message_handler(state=Register.fullname)
async def get_name(message: types.Message, state: FSMContext):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔔 Eslatma")

    await message.answer(
        "✅ Ro‘yxatdan o‘tding!\nEndi eslatma qo‘shishing mumkin.",
        reply_markup=kb
    )
    await state.finish()

# ================= REMINDER START =================
@dp.message_handler(lambda m: m.text == "🔔 Eslatma")
async def reminder_start(message: types.Message):
    await message.answer(
        "⏰ Eslatma vaqtini yoz\n\n"
        "Format:\n"
        "2026-01-05 18:30"
    )
    await Reminder.time.set()

# ================= REMINDER TIME =================
@dp.message_handler(state=Reminder.time)
async def reminder_time(message: types.Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
        ts = int(dt.timestamp())

        if ts <= int(time.time()):
            await message.answer("❌ O‘tmish vaqt bo‘lishi mumkin emas")
            return

        await state.update_data(remind_ts=ts)
        await message.answer("✍️ Eslatma matnini yoz")
        await Reminder.text.set()
    except:
        await message.answer("❌ Format xato\nMasalan: 2026-01-05 18:30")

# ================= REMINDER TEXT =================
@dp.message_handler(state=Reminder.text)
async def reminder_text(message: types.Message, state: FSMContext):
    data = await state.get_data()

    cursor.execute(
        "INSERT INTO reminders (user_id, text, remind_ts) VALUES (?, ?, ?)",
        (message.from_user.id, message.text, data["remind_ts"])
    )
    conn.commit()

    await message.answer("✅ Eslatma saqlandi. Belgilangan vaqtda xabar beraman.")
    await state.finish()

# ================= CHECK REMINDERS =================
async def reminder_checker():
    print("REMINDER CHECKER STARTED")  # 👈 LOG
    while True:
        now = int(time.time())

        cursor.execute(
            "SELECT id, user_id, text FROM reminders WHERE sent = 0 AND remind_ts <= ?",
            (now,)
        )
        rows = cursor.fetchall()

        for r in rows:
            await bot.send_message(r[1], f"🔔 ESLATMA:\n\n{r[2]}")
            cursor.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (r[0],))
            conn.commit()

        await asyncio.sleep(10)

# ================= RUN =================
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(reminder_checker())  # 👈 MAJBURIY ISHGA TUSHADI
    executor.start_polling(dp, skip_updates=True)
