import logging
import os

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Railway uchun

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


# ===== STATE =====
class Register(StatesGroup):
    phone = State()
    fullname = State()


# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("📞 Telefon raqamni yuborish", request_contact=True))

    await message.answer(
        "📞 Botdan foydalanish uchun telefon raqamingni yubor",
        reply_markup=kb
    )
    await Register.phone.set()


# ===== PHONE =====
@dp.message_handler(content_types=types.ContentType.CONTACT, state=Register.phone)
async def get_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)

    await message.answer(
        "👤 Ism familiyangni yoz\nMasalan: Jahongir Isoqulov",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await Register.fullname.set()


# ===== FULL NAME =====
@dp.message_handler(state=Register.fullname)
async def get_fullname(message: types.Message, state: FSMContext):
    data = await state.get_data()

    phone = data.get("phone")
    fullname = message.text

    # Hozircha faqat tekshirish uchun
    print("YANGI USER:", fullname, phone)

    await message.answer(
        "✅ Ro‘yxatdan muvaffaqiyatli o‘tding!\nBotdan foydalanishing mumkin 🎉"
    )

    await state.finish()  # 🔴 ENG MUHIM QATOR


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
