import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

logging.basicConfig(level=logging.INFO)

API_TOKEN = '8634099013:AAEM4zhg-Q5B4MAhcssuYiEvnIeJiOZ_Z3Q'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

user_data = {}

class AverageCalc(StatesGroup):
    waiting_for_date = State()
    waiting_for_numbers = State()

kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Додати числа за дату"), KeyboardButton(text="📋 Переглянути результати")]
    ],
    resize_keyboard=True
)

@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    await message.answer("Привіт! Обери дію на клавіатурі нижче:", reply_markup=kb)

@dp.message(F.text == "📊 Додати числа за дату")
async def start_date_input(message: Message, state: FSMContext):
    await message.answer("Введи дату (наприклад, **11 вересня** або **2026-09-11**):")
    await state.set_state(AverageCalc.waiting_for_date)

@dp.message(AverageCalc.waiting_for_date)
async def process_date(message: Message, state: FSMContext):
    date_str = message.text.strip()
    await state.update_data(current_date=date_str)
    await message.answer(f"Дата збережена: **{date_str}**.\n\nТепер введи числа через пробіл або кому:")
    await state.set_state(AverageCalc.waiting_for_numbers)

@dp.message(AverageCalc.waiting_for_numbers)
async def process_numbers(message: Message, state: FSMContext):
    tokens = message.text.replace(',', ' ').split()
    numbers = [float(t) for t in tokens if t.replace('.', '', 1).isdigit()]

    if not numbers:
        await message.answer("⚠️ Не знайдено чисел. Спробуй ще раз через пробіл:")
        return

    data = await state.get_data()
    date_str = data.get("current_date")
    user_id = message.from_user.id

    old_numbers = user_data.get(user_id, {}).get(date_str, [])
    old_avg = sum(old_numbers) / len(old_numbers) if old_numbers else None

    user_data.setdefault(user_id, {}).setdefault(date_str, []).extend(numbers)
    
    all_numbers = user_data[user_id][date_str]
    new_avg = sum(all_numbers) / len(all_numbers)

    reaction = ""
    if old_avg is not None:
        if new_avg < old_avg:
            reaction = "\n\n🔥 Шикарно! Показник пішов униз, так тримати!"
        elif new_avg > old_avg:
            reaction = "\n\n😡 Серйозно? Знову зросло?! Я розчарований таким результатом..."
        else:
            reaction = "\n\n⚖️ На одному рівні. Жодних змін."

    await message.answer(
        f"✅ Успішно додано до дати **{date_str}**!\n"
        f"Усі числа: {all_numbers}\n"
        f"📊 **Середнє:** `{new_avg:.2f}`{reaction}",
        reply_markup=kb
    )
    await state.clear()

@dp.message(F.text == "📋 Переглянути результати")
async def show_results(message: Message):
    user_data_dict = user_data.get(message.from_user.id, {})
    if not user_data_dict:
        await message.answer("У тебе ще немає збережених даних.", reply_markup=kb)
        return

    response = "📋 **Твої результати по датах:**\n\n"
    for date_str, numbers in user_data_dict.items():
        avg = sum(numbers) / len(numbers) if numbers else 0
        response += f"📅 **{date_str}**:\n  • Числа: {numbers}\n  • Середнє: `{avg:.2f}`\n\n"

    await message.answer(response, reply_markup=kb)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
