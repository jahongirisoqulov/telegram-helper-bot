import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from config import BOT_TOKEN, CHANNEL_USERNAME
from db import *
from keyboards import *

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

temp = {}

class ReminderState(StatesGroup):
    time = State()
    text = State()

async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False

@dp.message(CommandStart())
async def start(message: Message):
    if not await is_subscribed(message.from_user.id):
        await message.answer(
            "Botdan foydalanish uchun kanalga obuna bo‘ling",
            reply_markup=subscribe_keyboard(CHANNEL_USERNAME)
        )
        return

    user = await get_user(message.from_user.id)
    if user:
        await message.answer("Xush kelibsiz 👋", reply_markup=main_menu())
    else:
        await message.answer(
            "Telefon raqamingni yubor",
            reply_markup=phone_keyboard()
        )

@dp.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery):
    if await is_subscribed(call.from_user.id):
        await call.message.delete()
        await start(call.message)
    else:
        await call.answer("Hali obuna bo‘lmading", show_alert=True)

@dp.message(F.contact)
async def contact(message: Message):
    temp[message.from_user.id] = message.contact.phone_number
    await message.answer("Ism Familiyangni yoz")

@dp.message(F.text)
async def fullname(message: Message):
    if message.from_user.id in temp:
        await add_user(
            message.from_user.id,
            message.text,
            temp[message.from_user.id]
        )
        temp.pop(message.from_user.id)
        await message.answer("Ro‘yxatdan o‘tding ✅", reply_markup=main_menu())
        return

    if message.text == "🔔 Eslatma":
        await message.answer("Vaqtni yoz:\n2026-01-03 18:30")
        await dp.fsm.set_state(message.from_user.id, ReminderState.time)

    elif message.text == "💰 Pul":
        await add_transaction(message.from_user.id, 10000, "in")
        await message.answer("10 000 so‘m kirim qo‘shildi")

    elif message.text == "💼 Balans":
        bal = await get_balance(message.from_user.id)
        await message.answer(f"Balans: {bal} so‘m")

@dp.message(ReminderState.time)
async def rem_time(message: Message, state: FSMContext):
    try:
        t = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
        await state.update_data(time=t)
        await state.set_state(ReminderState.text)
        await message.answer("Eslatma matnini yoz")
    except:
        await message.answer("Format xato")

@dp.message(ReminderState.text)
async def rem_text(message: Message, state: FSMContext):
    data = await state.get_data()
    await add_reminder(
        message.from_user.id,
        message.text,
        data["time"].strftime("%Y-%m-%d %H:%M")
    )
    await state.clear()
    await message.answer("Eslatma saqlandi ✅")

async def reminder_worker():
    while True:
        reminders = await get_pending_reminders()
        for r in reminders:
            await bot.send_message(r[1], f"🔔 Eslatma:\n{r[2]}")
            await mark_sent(r[0])
        await asyncio.sleep(30)

async def main():
    await init_db()
    asyncio.create_task(reminder_worker())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
