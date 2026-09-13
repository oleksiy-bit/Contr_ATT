import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message

logging.basicConfig(level=logging.INFO)

API_TOKEN = '8634099013:AAHAQMFw8rRb6blIG2QbBLmi4ueNjMQ608M'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Дані та активні дати в пам'яті
user_data = {}
active_dates = {}

@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    active_dates.pop(message.from_user.id, None)
    await message.answer(
        "Привіт! Я бот для підрахунку середнього.\n\n"
        "📅 **Крок 1:** Надішли мені дату (наприклад, `11.09` або `сьогодні`), за якою будемо вести облік:"
    )

@dp.message()
async def handle_message(message: Message):
    user_id = message.from_user.id
    text = message.text.strip().replace(',', '.')

    if user_id not in active_dates:
        active_dates[user_id] = text
        await message.answer(
            f"✅ Дата встановлена: **{text}**.\n\n"
            "🔢 Тепер просто надсилай числа одне за одним, а я рахуватиму середнє!"
        )
        return

    try:
        new_value = float(text)
    except ValueError:
        await message.answer("⚠️ Це не число. Введи цифру або напиши /start для зміни дати.")
        return

    date_str = active_dates[user_id]
    user_data.setdefault(user_id, {}).setdefault(date_str, [])
    numbers_list = user_data[user_id][date_str]

    old_avg = sum(numbers_list) / len(numbers_list) if numbers_list else None
    numbers_list.append(new_value)
    new_avg = sum(numbers_list) / len(numbers_list)

    reaction = ""
    if old_avg is not None:
        if new_avg < old_avg:
            reaction = "\n\n🔥 Шикарно! Показник пішов униз, так тримати!"
        elif new_avg > old_avg:
            reaction = "\n\n😡 Серйозно? Знову зросло?! Я розчарований таким результатом..."
        else:
            reaction = "\n\n⚖️ На одному рівні. Жодних змін."

    await message.answer(
        f"📅 Дата: **{date_str}**\n"
        f"Числа: {numbers_list}\n"
        f"📊 **Середнє:** `{new_avg:.2f}`{reaction}\n\n"
        f"*(Можеш надсилати наступне число або написати /start для зміни дати)*"
    )

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
