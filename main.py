import os
import asyncio
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

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
db.commit()

# ================= STATES =================
class Register(StatesGroup):
    phone = State()
    fullname = State()

# ================= HELPERS =================
async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ("member", "administrator", "creator")
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
    kb.add(
        types.InlineKeyboardButton(
            "✅ Tekshirish",
            callback_data="check_sub"
        )
    )
    return kb

def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔔 Eslatma qo‘shish")
    kb.add("➕ Kirim", "➖ Chiqim")
    kb.add("💼 Balans")
    return kb

# ================= START =================
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        await message.answer(
            "❗ Botdan foydalanish uchun avval kanalga obuna bo‘ling.",
            reply_markup=subscribe_keyboard()
        )
        return

    if is_registered(message.from_user.id):
        await message.answer(
            "👋 Xush kelibsiz! Botdan foydalanishingiz mumkin.",
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

# ================= CHECK SUB BUTTON =================
@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_sub(call: types.CallbackQuery):
    if await is_subscribed(call.from_user.id):
        await call.message.answer(
            "✅ Rahmat! Endi botdan foydalanishingiz mumkin.\n/start ni bosing."
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

# ================= ADMIN: USERS LIST =================
@dp.message_handler(commands=['users'])
async def users_list(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    cur.execute("SELECT full_name, phone FROM users")
    rows = cur.fetchall()

    if not rows:
        await message.answer("Hozircha foydalanuvchilar yo‘q.")
        return

    text = f"👥 Foydalanuvchilar soni: {len(rows)}\n\n"
    for i, r in enumerate(rows, 1):
        text += f"{i}. {r[0]} — {r[1]}\n"

    await message.answer(text)

# ================= RUN =================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
