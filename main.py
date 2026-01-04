import os
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


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
    await state.update_data(phone=message.contact.phone_number)

    await message.answer(
        "👤 Ism familiyangni yoz\nMasalan: Jahongir Isoqulov",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await Register.fullname.set()


# ================= FULL NAME =================
@dp.message_handler(state=Register.fullname)
async def get_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    phone = data["phone"]
    fullname = message.text

    print("USER:", fullname, phone)

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔔 Eslatma")

    await message.answer(
        "✅ Ro‘yxatdan o‘tding!\nPastdagi menyudan foydalan.",
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
        remind_time = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
        await state.update_data(remind_time=remind_time)

        await message.answer("✍️ Eslatma matnini yoz")
        await Reminder.text.set()
    except:
        await message.answer(
            "❌ Format xato\n"
            "Masalan: 2026-01-05 18:30"
        )


# ================= REMINDER TEXT =================
@dp.message_handler(state=Reminder.text)
async def reminder_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    remind_time = data["remind_time"]
    text = message.text

    asyncio.create_task(send_reminder(message.chat.id, remind_time, text))

    await message.answer("✅ Eslatma saqlandi. Belgilangan vaqtda xabar beraman.")
    await state.finish()


# ================= SEND REMINDER =================
async def send_reminder(chat_id, remind_time, text):
    seconds = (remind_time - datetime.now()).total_seconds()
    if seconds > 0:
        await asyncio.sleep(seconds)
        await bot.send_message(chat_id, f"🔔 ESLATMA:\n\n{text}")


# ================= RUN =================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
