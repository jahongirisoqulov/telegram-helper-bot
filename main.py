import os
import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# 🇺🇿 O‘zbekiston vaqti (UTC+5)
def uz_now():
    return datetime.utcnow() + timedelta(hours=5)

# ================= STORAGE =================
# oddiy xotira (keyin bazaga o‘tkazamiz)
reminders = {}  # user_id: [ {id, time, text, task} ]

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
    await message.answer("📱 Telefon raqamingni yubor", reply_markup=kb)
    await Register.phone.set()

# ================= PHONE =================
@dp.message_handler(content_types=types.ContentType.CONTACT, state=Register.phone)
async def phone(message: types.Message, state: FSMContext):
    await message.answer(
        "👤 Ism familiyangni yoz\nMasalan: Jahongir Isoqulov",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await Register.fullname.set()

# ================= FULL NAME =================
@dp.message_handler(state=Register.fullname)
async def fullname(message: types.Message, state: FSMContext):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔔 Eslatma qo‘shish")
    kb.add("📋 Eslatmalarim")
    await message.answer("✅ Tayyor! Menyudan tanla.", reply_markup=kb)
    await state.finish()

# ================= ADD REMINDER =================
@dp.message_handler(lambda m: m.text == "🔔 Eslatma qo‘shish")
async def add_reminder(message: types.Message):
    await message.answer(
        "⏰ Vaqtni yoz\n\n"
        "Masalan:\n"
        "2026-01-05 18:30"
    )
    await Reminder.time.set()

@dp.message_handler(state=Reminder.time)
async def reminder_time(message: types.Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
        seconds = (dt - uz_now()).total_seconds()
        if seconds <= 0:
            await message.answer("❌ Bu vaqt o‘tib ketgan")
            return
        await state.update_data(seconds=seconds, remind_time=dt)
        await message.answer("✍️ Eslatma matnini yoz")
        await Reminder.text.set()
    except:
        await message.answer("❌ Format xato\nMasalan: 2026-01-05 18:30")

@dp.message_handler(state=Reminder.text)
async def reminder_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    seconds = data["seconds"]
    remind_time = data["remind_time"]
    text = message.text

    task = asyncio.create_task(send_reminder(message.chat.id, seconds, text))

    user_list = reminders.setdefault(message.from_user.id, [])
    reminder_id = len(user_list) + 1
    user_list.append({
        "id": reminder_id,
        "time": remind_time,
        "text": text,
        "task": task
    })

    await message.answer("✅ Eslatma saqlandi")
    await state.finish()

async def send_reminder(chat_id, seconds, text):
    await asyncio.sleep(seconds)
    await bot.send_message(chat_id, f"🔔 ESLATMA:\n\n{text}")

# ================= LIST REMINDERS =================
@dp.message_handler(lambda m: m.text == "📋 Eslatmalarim")
async def list_reminders(message: types.Message):
    user_list = reminders.get(message.from_user.id, [])

    if not user_list:
        await message.answer("📭 Hozircha eslatma yo‘q")
        return

    text = "📋 Eslatmalar:\n\n"
    kb = types.InlineKeyboardMarkup()

    for r in user_list:
        text += f"🕒 {r['time'].strftime('%Y-%m-%d %H:%M')}\n{r['text']}\n\n"
        kb.add(
            types.InlineKeyboardButton(
                text=f"❌ O‘chirish #{r['id']}",
                callback_data=f"del_{r['id']}"
            )
        )

    await message.answer(text, reply_markup=kb)

# ================= DELETE REMINDER =================
@dp.callback_query_handler(lambda c: c.data.startswith("del_"))
async def delete_reminder(call: types.CallbackQuery):
    rid = int(call.data.split("_")[1])
    user_list = reminders.get(call.from_user.id, [])

    for r in user_list:
        if r["id"] == rid:
            r["task"].cancel()
            user_list.remove(r)
            await call.message.answer("❌ Eslatma o‘chirildi")
            break

    await call.answer()

# ================= RUN =================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
