import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

logging.basicConfig(level=logging.INFO)

API_TOKEN = '8634099013:AAEM4fW8rRb6b1IG2QbBLmi4ueNjMQ608M'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Сховище даних: {user_id: {date_str: [numbers]}}
user_data = {}
# Активна дата для кожного користувача: {user_id: date_str}
active_dates = {}

class CalcState(StatesGroup):
    waiting_for_number = State()

@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    active_dates.pop(message.from_user.id, None)
    await message.answer(
        "Привіт! Я бот для підрахунку середнього.\n\n"
        "Спочатку надішли мені **дату** (наприклад, `11.09` або `сьогодні`), за якою будемо вести облік:"
    )

@dp.message(CalcState.waiting_for_number)
async def process_number(message: Message, state: FSMContext):
    user_id = message.from_user.id
    date_str = active_dates.get(user_id)
    text = message.text.replace(',', '.').strip()

    # Спроба перетворити повідомлення на число
    try:
        new_value = float(text)
    except ValueError:
        await message.answer("⚠️ Це не схоже на число. Введи цифру або число:")
        return

    # Зберігаємо число
    user_data.setdefault(user_id, {}).setdefault(date_str, [])
    numbers_list = user_data[user_id][date_str]

    # Вираховуємо попереднє середнє (якщо вже були числа)
    old_avg = sum(numbers_list) / len(numbers_list) if numbers_list else None

    # Додаємо нове число
    numbers_list.append(new_value)
    
    # Нове середнє
    new_avg = sum(numbers_list) / len(numbers_list)

    # Формуємо реакцію
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
        f"*(Можеш надсилати наступне число або написати /start, щоб змінити дату)*"
    )

@dp.message()
async def set_date_or_handle(message: Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip()

    # Якщо дата ще не вибрана — вважаємо це повідомлення датою
    if user_id not in active_dates:
        active_dates[user_id] = text
        await state.set_state(CalcState.waiting_for_number)
        await message.answer(
            f"✅ Дата встановлена: **{text}**.\n\n"
            "Тепер просто надсилай мені числа по одному, а я буду рахувати середнє!"
        )
        return

    # Якщо дата вже є, але користувач чомусь написав щось не те замість числа
    await message.answer("⚠️ Надішли число або напиши /start для зміни дати.")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
