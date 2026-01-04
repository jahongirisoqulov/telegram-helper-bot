import os
import asyncio
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# ================= ENV =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

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
    phone TEXT,
    joined_at TEXT
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

# ================= TEMP STORAGE =================
reminders = {}  # RAM (server o‘chsa yo‘qoladi)

# ================= STATES =================
class Register(StatesGroup):
    phone = State()
    fullname = State()

class ReminderState(StatesGroup):
    time = State()
    text = State()

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

def subscribe_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton(
            "📢 Kanalga obuna bo‘lish",
            url=f"https://t.me/{CHANNEL_USERNAME.replace('@','')}"
        )
    )
    kb.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub"))
    return kb

def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔔 Eslatma qo‘shish", "📋 Eslatmalarim")
    kb.add("➕ Kirim", "➖ Chiqim")
    kb.add("💼 Balans", "📊 Statistika")
    kb.add("❌ Pul yozuvini o‘chirish")
    return kb

# ================= START =================
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        await message.answer(
            "❗ Botdan foydalanish uchun avval kanalga obuna bo‘lishingiz kerak.",
            reply_markup=subscribe_keyboard()
        )
        return

    if is_registered(message.from_user.id):
        await message.answer(
            "👋 Xush kelibsiz! Quyidagi menyudan foydalanishingiz mumkin.",
            reply_markup=main_menu()
        )
        return

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("📱 Telefon raqam yuborish", request_contact=True))
    await message.answer(
        "📱 Iltimos, telefon raqamingizni yuboring.",
        reply_markup=kb
    )
    await Register.phone.set()

# ================= CHECK SUB =================
@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_sub(call: types.CallbackQuery):
    if await is_subscribed(call.from_user.id):
        await call.message.answer(
            "✅ Rahmat! Endi /start ni bosib botdan foydalanishingiz mumkin."
        )
    else:
        await call.answer(
            "❌ Siz hali kanalga obuna bo‘lmagansiz.",
            show_alert=True
        )

# ================= REGISTER =================
@dp.message_handler(content_types=types.ContentType.CONTACT, state=Register.phone)
async def phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    await message.answer(
        "👤 Iltimos, ism va familiyangizni yozing.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await Register.fullname.set()

@dp.message_handler(state=Register.fullname)
async def fullname(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cur.execute(
        "INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?)",
        (message.from_user.id, message.text, data["phone"], uz_now().isoformat())
    )
    db.commit()

    await message.answer(
        "✅ Ma’lumotlaringiz saqlandi. Botdan foydalanishingiz mumkin.",
        reply_markup=main_menu()
    )
    await state.finish()

# ================= REMINDER =================
@dp.message_handler(lambda m: m.text == "🔔 Eslatma qo‘shish")
async def reminder_start(message: types.Message):
    await message.answer(
        "⏰ Iltimos, eslatma vaqtini yozing.\nMasalan: 2026-01-05 18:30"
    )
    await ReminderState.time.set()

@dp.message_handler(state=ReminderState.time)
async def reminder_time(message: types.Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
        seconds = (dt - uz_now()).total_seconds()
        if seconds <= 0:
            await message.answer("❌ Kiritilgan vaqt o‘tib ketgan.")
            return
        await state.update_data(seconds=seconds, time=dt)
        await message.answer("✍️ Iltimos, eslatma matnini yozing.")
        await ReminderState.text.set()
    except:
        await message.answer("❌ Vaqt formati noto‘g‘ri.")

@dp.message_handler(state=ReminderState.text)
async def reminder_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    task = asyncio.create_task(send_reminder(message.chat.id, data["seconds"], message.text))
    reminders.setdefault(message.from_user.id, []).append(
        {"time": data["time"], "text": message.text, "task": task}
    )
    await message.answer(
        "✅ Eslatma saqlandi.",
        reply_markup=main_menu()
    )
    await state.finish()

async def send_reminder(chat_id, seconds, text):
    await asyncio.sleep(seconds)
    await bot.send_message(chat_id, f"🔔 ESLATMA:\n\n{text}")

@dp.message_handler(lambda m: m.text == "📋 Eslatmalarim")
async def list_reminders(message: types.Message):
    lst = reminders.get(message.from_user.id, [])
    if not lst:
        await message.answer("📭 Hozircha eslatmalar mavjud emas.")
        return
    text = "📋 Sizning eslatmalaringiz:\n\n"
    for r in lst:
        text += f"🕒 {r['time'].strftime('%Y-%m-%d %H:%M')} — {r['text']}\n"
    await message.answer(text)

# ================= MONEY =================
@dp.message_handler(lambda m: m.text == "➕ Kirim")
async def income(message: types.Message, state: FSMContext):
    await state.update_data(type="in")
    await message.answer("💰 Iltimos, kirim summasini yozing.")
    await MoneyState.amount.set()

@dp.message_handler(lambda m: m.text == "➖ Chiqim")
async def expense(message: types.Message, state: FSMContext):
    await state.update_data(type="out")
    await message.answer("💸 Iltimos, chiqim summasini yozing.")
    await MoneyState.amount.set()

@dp.message_handler(state=MoneyState.amount)
async def save_money(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Faqat raqam kiriting.")
        return
    data = await state.get_data()
    cur.execute(
        "INSERT INTO money (user_id, amount, type, created_at) VALUES (?, ?, ?, ?)",
        (message.from_user.id, int(message.text), data["type"], uz_now().isoformat())
    )
    db.commit()
    await message.answer("✅ Ma’lumot saqlandi.", reply_markup=main_menu())
    await state.finish()

@dp.message_handler(lambda m: m.text == "💼 Balans")
async def balance(message: types.Message):
    cur.execute("""
    SELECT SUM(CASE WHEN type='in' THEN amount ELSE -amount END)
    FROM money WHERE user_id=?
    """, (message.from_user.id,))
    bal = cur.fetchone()[0] or 0
    await message.answer(f"💼 Joriy balansingiz: {bal} so‘m")

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
        f"🗓 Joriy oy:\n➕ {m_in or 0} so‘m\n➖ {m_out or 0} so‘m"
    )

@dp.message_handler(lambda m: m.text == "❌ Pul yozuvini o‘chirish")
async def delete_money(message: types.Message):
    cur.execute(
        "SELECT id, amount, type FROM money WHERE user_id=? ORDER BY id DESC LIMIT 5",
        (message.from_user.id,)
    )
    rows = cur.fetchall()
    if not rows:
        await message.answer("❌ O‘chirish uchun pul yozuvlari mavjud emas.")
        return

    kb = types.InlineKeyboardMarkup()
    for r in rows:
        kb.add(types.InlineKeyboardButton(
            f"{r[1]} so‘m ({r[2]}) ❌",
            callback_data=f"delmoney_{r[0]}"
        ))
    await message.answer("Qaysi yozuvni o‘chirmoqchisiz?", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("delmoney_"))
async def del_money(call: types.CallbackQuery):
    mid = int(call.data.split("_")[1])
    cur.execute("DELETE FROM money WHERE id=?", (mid,))
    db.commit()
    await call.message.answer("❌ Pul yozuvi o‘chirildi.")
    await call.answer()

# ================= ADMIN =================
@dp.message_handler(commands=['users'])
async def users_list(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    cur.execute("SELECT full_name, phone FROM users")
    rows = cur.fetchall()

    text = f"👥 Foydalanuvchilar soni: {len(rows)}\n\n"
    for i, r in enumerate(rows, 1):
        text += f"{i}. {r[0]} — {r[1]}\n"

    await message.answer(text)

# ================= RUN =================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
