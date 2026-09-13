"""
Telegram-бот "Трекер середнього арифметичного" на aiogram 3.x.

Функціонал:
  * /start -> інлайн-календар для вибору активної дати.
  * Будь-яке текстове повідомлення з числом (кома або крапка) -> додається
    до списку значень обраної дати, рахується нове середнє арифметичне.
  * Бот порівнює нове середнє зі старим і відповідає випадковою фразою
    з одного з трьох масивів (по 50 унікальних варіантів кожен):
      - середнє зменшилось  -> PHRASES_DOWN (радість/схвалення)
      - середнє збільшилось -> PHRASES_UP   (розчарування/жарт)
      - середнє не змінилось -> PHRASES_SAME (нейтральна стабільність)
  * Дані зберігаються в пам'яті процесу (in-memory), окремо на кожен chat_id.
  * Для стабільної роботи на безкоштовному Render поруч із поллінгом
    піднімається мінімальний aiohttp-сервер, що слухає $PORT (health-check),
    а сам поллінг обгорнутий у цикл автоматичного перезапуску при збоях.

Змінні середовища:
  BOT_TOKEN  - обов'язково, токен бота від @BotFather.
  PORT       - опційно, порт для health-check сервера (Render підставляє сам).
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
from calendar import monthrange
from datetime import date, datetime

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiohttp import web

# --------------------------------------------------------------------------- #
#  Базове налаштування
# --------------------------------------------------------------------------- #

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("avg-tracker-bot")

BOT_TOKEN = "8634099013:AAHAQMFw8rRb6blIG2QbBLmi4ueNjMQ608M"
if not BOT_TOKEN:
    raise RuntimeError(
        "Не задано змінну середовища BOT_TOKEN. "
        "Додайте її в налаштуваннях Render (Environment -> BOT_TOKEN)."
    )

PORT = int(os.getenv("PORT", "10000"))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# In-memory сховище: {chat_id: {"date": "YYYY-MM-DD", "numbers": [float, ...]}}
user_data: dict[int, dict] = {}

MONTH_NAMES_UA = [
    "Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
    "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень",
]
WEEKDAYS_UA = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]


# --------------------------------------------------------------------------- #
#  Масиви реакцій — по 50 унікальних варіантів у кожному
# --------------------------------------------------------------------------- #

PHRASES_DOWN = [
    "Огонь! Середнє поповзло вниз 🔥",
    "Ти сьогодні в ударі, показник тільки покращується! 🚀",
    "Так тримати, прогрес наочний! 💪",
    "Це вже схоже на систему, а не на випадковість 👏",
    "Красиво! Тренд рухається в правильному напрямку 📉",
    "Маленький крок — велике досягнення! ✨",
    "От би так щодня — і результат не забариться 😎",
    "Дисципліна робить свою справу 🙌",
    "Ще трохи — і будеш задоволений результатом 😊",
    "Оце я розумію прогрес! 🎉",
    "Тенденція чудова, продовжуй у тому ж дусі 🌟",
    "Крок за кроком до кращого показника 👣",
    "Так, це саме те, що треба! ✅",
    "Показник каже тобі: «Дякую!» 😄",
    "Молодець, робота дає плоди 🍏",
    "Це вже привід для маленького святкування 🎈",
    "Прогрес не питає дозволу — він просто трапляється 😉",
    "Ти на правильному шляху, не зупиняйся 🛤️",
    "Кожне таке число — цеглинка в стіну успіху 🧱",
    "Ну хто тут молодець? Ти молодець! 🏆",
    "Це вже не випадковість, це результат 💯",
    "Все йде як по маслу 🧈",
    "Твоя старанність окупається 💵",
    "Гарний рух вниз, продовжуй в тому ж темпі 📊",
    "Оце справжня перемога над собою 🥇",
    "Такими темпами скоро поб'єш власний рекорд 🏅",
    "Приємно бачити, як старання конвертуються в результат 😌",
    "Ще одна маленька перемога у скарбничку 💰",
    "Ти сьогодні герой цієї статистики 🦸",
    "Число зменшилось — настрій піднявся 📉➡️😄",
    "Так і запишемо: сьогодні був продуктивний день 📝",
    "Тримай темп, результат вражає 🔥",
    "Оце так якісна робота над собою! 👍",
    "Гарна динаміка, продовжуй в тому ж дусі 🌈",
    "Скоро це стане приємною звичкою 🌱",
    "Ти вже майже профі в цій справі 🎯",
    "Впевнена хода до кращого результату 🚶➡️🏁",
    "Це той випадок, коли менше — це більше 😉",
    "Твої зусилля не залишились непоміченими 👀",
    "Наступного разу буде ще краще, повір! 🌤️",
    "Оце поворот подій — і дуже приємний 😍",
    "Показник тане, як сніг навесні ❄️🌸",
    "Дуже гідний результат, оплески! 👏👏👏",
    "Ти впевнено рухаєшся до мети 🎯",
    "Гарна новина для статистики дня 📰",
    "Ще один плюс у скарбничку досягнень ➕",
    "Це вже схоже на стабільний прогрес ✅",
    "Так тримати — і результат тебе здивує 😄",
    "Приємно бачити такий рух у правильному напрямку 🌟",
    "Оце заслужена похвала: молодець! 🎉",
]

PHRASES_UP = [
    "Ой-ой, середнє поповзло вгору 📈😬",
    "Ну ось, знову за старе... 🙄",
    "Здається, хтось трохи розслабився 😅",
    "Показник каже: «Ти забув про мене?» 😢",
    "От тобі і прогрес... у зворотному напрямку 🙃",
    "Це той момент, коли варто задуматись 🤔",
    "Ну що ж, буває і так, завтра краще 🤷",
    "Статистика трохи засмутилась сьогодні 😞",
    "Здається, дисципліна взяла вихідний 🏖️",
    "Ой, а могло бути й краще... 😬",
    "Число росте, а настрій падає 📉😅",
    "Ну хто ж так робить, га? 😏",
    "Це не той напрямок, який ми обирали 🚧",
    "Схоже, потрібна невелика перезарядка мотивації 🔋",
    "Ех, а так гарно все починалось... 😔",
    "Це тривожний дзвіночок, друже 🔔",
    "Ну от, знову доведеться надолужувати 😤",
    "Показник вирішив пожартувати не в твою користь 🎭",
    "Здається, статистика на тебе трохи ображена 🥲",
    "Ой, а куди поділась вчорашня рішучість? 🧐",
    "Це той випадок, коли краще було промовчати 🤐",
    "Число зростає швидше, ніж хотілося б 🚀😅",
    "Схоже, сьогодні не твій день 😕",
    "Ну от, знову довелось погіршити статистику 📊👎",
    "Це маленька невдача, але не кінець світу 🌥️",
    "Показник наче каже: «Я ж казав!» 😏",
    "Трохи прикро, але завтра новий шанс 🌅",
    "Ех, знову доведеться братись за старе 💪😅",
    "Це не той рекорд, яким варто пишатись 🏆❌",
    "Здається, комусь час взяти себе в руки 🧘",
    "Ой, а могло б бути і гірше... хоча куди вже 😅",
    "Число росте, а разом з ним і моє здивування 😲",
    "Ну от, знову тема для роздумів на вечір 🌙",
    "Це той сигнал, який не варто ігнорувати ⚠️",
    "Схоже, потрібно трохи більше зусиль 💦",
    "Ех, знову не туди пішло... 🙈",
    "Це маленький крок назад, але не привід здаватись 🚶",
    "Показник вирішив підняти планку... не в тому сенсі 😅",
    "Ой, а я так сподівався на інше... 😢",
    "Здається, це буде непроста розмова з собою 🗣️",
    "Ну що ж, статистика має право на поганий день 📉😐",
    "Це не той тренд, який хочеться бачити 📈🙅",
    "Ех, знову доведеться коригувати плани 📝",
    "Показник росте швидше за терпіння 😬",
    "Ой, здається, вихідний був занадто розслаблюючим 🛋️",
    "Це той момент, коли варто зробити висновки 🧠",
    "Ну от, знову маленька пляма на статистиці 🖋️",
    "Схоже, потрібна серйозна розмова з собою 🪞",
    "Ех, а могло бути і краще, чесно кажучи 😌",
    "Це не привід сумувати, а привід зібратись 💼",
]

PHRASES_SAME = [
    "Стабільність — це теж результат 🧘",
    "Все залишилось на своєму місці ⚖️",
    "Рівновага збережена 🎯",
    "Ні вгору, ні вниз — просто пауза ⏸️",
    "Показник вирішив трохи відпочити 😌",
    "Стабільно, як швейцарський годинник ⏱️",
    "Без змін, але й без погіршень — теж непогано 👌",
    "Плато — теж частина шляху 🏔️",
    "Все під контролем, без сюрпризів 🤖",
    "Число вирішило залишитись на місці 📍",
    "Стабільність — ознака майстерності 🎓",
    "Нічого не змінилось, і це нормально 🙂",
    "Рівний курс — теж курс 🧭",
    "Показник взяв паузу для роздумів 🤔",
    "Все як і вчора, спокійно і рівно 🌤️",
    "Статус-кво збережено 📋",
    "Ні перемога, ні поразка — просто рівновага ⚖️",
    "Число вирішило побути на нейтральній території 🏳️",
    "Стабільний результат — теж результат 📊",
    "Все тримається на рівному кілі ⛵",
    "Без різких рухів сьогодні 🧊",
    "Показник у режимі очікування ⏳",
    "Рівно, спокійно, без метушні 🍃",
    "Все стабільно, як і має бути 🔒",
    "Число не поспішає нікуди рухатись 🐢",
    "Це такий собі день перепочинку для статистики 🛌",
    "Стабільність — недооцінена перемога 🥈",
    "Все залишається без змін, і це теж непогано 🌿",
    "Показник вирішив трохи постояти на місці 🚦",
    "Рівновага у всій красі ⚗️",
    "Ні туди, ні сюди — просто стабільно 🔄",
    "Число тримає позицію впевнено 🛡️",
    "Все спокійно, як тиха гавань ⚓",
    "Стабільність — це теж маленька перемога 🏅",
    "Показник не поспішає з висновками 🧩",
    "Рівний темп — теж темп 🏃",
    "Все залишилось незмінним, і це факт 📌",
    "Число взяло вихідний від змін 🏖️",
    "Стабільно тримаємо курс 🧭",
    "Все на своїх місцях, без несподіванок 🗂️",
    "Показник вирішив побути консерватором сьогодні 🎩",
    "Рівновага — теж мистецтво ⚖️",
    "Число не поспішає нікуди, і це нормально 🐌",
    "Все стабільно, можна видихнути 😮",
    "Стабільність сьогодні в пріоритеті 🔐",
    "Показник тримається на рівні, як і личить 📏",
    "Все без змін, спокійно рухаємось далі ➡️",
    "Число вирішило зробити паузу перед наступним кроком ⏭️",
    "Стабільно, надійно, без сюрпризів 🛠️",
    "Все залишилось як є — і це теж результат 🎢",
]

# Захист від помилок у масивах — критично, щоб їх було рівно по 50.
assert len(PHRASES_DOWN) == 50, f"PHRASES_DOWN має {len(PHRASES_DOWN)} елементів"
assert len(PHRASES_UP) == 50, f"PHRASES_UP має {len(PHRASES_UP)} елементів"
assert len(PHRASES_SAME) == 50, f"PHRASES_SAME має {len(PHRASES_SAME)} елементів"
assert len(set(PHRASES_DOWN)) == 50, "У PHRASES_DOWN є дублікати"
assert len(set(PHRASES_UP)) == 50, "У PHRASES_UP є дублікати"
assert len(set(PHRASES_SAME)) == 50, "У PHRASES_SAME є дублікати"


# --------------------------------------------------------------------------- #
#  Побудова інлайн-календаря
# --------------------------------------------------------------------------- #

def build_calendar(year: int, month: int) -> InlineKeyboardMarkup:
    """Будує клавіатуру-календар для заданого місяця/року."""
    rows: list[list[InlineKeyboardButton]] = []

    # Шапка з навігацією між місяцями.
    rows.append(
        [
            InlineKeyboardButton(text="«", callback_data=f"cal_nav:{year}:{month}:prev"),
            InlineKeyboardButton(
                text=f"{MONTH_NAMES_UA[month - 1]} {year}", callback_data="cal_ignore"
            ),
            InlineKeyboardButton(text="»", callback_data=f"cal_nav:{year}:{month}:next"),
        ]
    )

    # Рядок днів тижня.
    rows.append(
        [InlineKeyboardButton(text=wd, callback_data="cal_ignore") for wd in WEEKDAYS_UA]
    )

    first_weekday, days_in_month = monthrange(year, month)  # Пн=0 ... Нд=6
    row: list[InlineKeyboardButton] = [
        InlineKeyboardButton(text=" ", callback_data="cal_ignore") for _ in range(first_weekday)
    ]

    for day in range(1, days_in_month + 1):
        row.append(
            InlineKeyboardButton(text=str(day), callback_data=f"cal_day:{year}:{month}:{day}")
        )
        if len(row) == 7:
            rows.append(row)
            row = []

    if row:
        row.extend(
            InlineKeyboardButton(text=" ", callback_data="cal_ignore")
            for _ in range(7 - len(row))
        )
        rows.append(row)

    rows.append([InlineKeyboardButton(text="📍 Сьогодні", callback_data="cal_today")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    """Зсуває (рік, місяць) на delta місяців (delta = -1 або +1)."""
    month += delta
    if month == 0:
        month = 12
        year -= 1
    elif month == 13:
        month = 1
        year += 1
    return year, month


def format_average_line(numbers: list[float]) -> str:
    if not numbers:
        return ""
    avg = sum(numbers) / len(numbers)
    return f"\n📊 Поточне середнє: <b>{avg:.3f}</b> (записів: {len(numbers)})"


# --------------------------------------------------------------------------- #
#  Хендлери команд і колбеків календаря
# --------------------------------------------------------------------------- #

@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    today = date.today()
    await message.answer(
        "🗓 Оберіть дату для ведення обліку:",
        reply_markup=build_calendar(today.year, today.month),
    )


@dp.callback_query(F.data == "cal_ignore")
async def cal_ignore(callback: CallbackQuery) -> None:
    await callback.answer()


@dp.callback_query(F.data.startswith("cal_nav:"))
async def cal_nav(callback: CallbackQuery) -> None:
    try:
        _, year_s, month_s, action = callback.data.split(":")
        year, month = int(year_s), int(month_s)
    except (ValueError, AttributeError):
        await callback.answer("Помилка навігації, спробуйте /start ще раз.", show_alert=True)
        return

    delta = -1 if action == "prev" else 1
    year, month = shift_month(year, month, delta)

    await callback.message.edit_reply_markup(reply_markup=build_calendar(year, month))
    await callback.answer()


@dp.callback_query(F.data == "cal_today")
async def cal_today(callback: CallbackQuery) -> None:
    today = date.today()
    await _select_date(callback, today.year, today.month, today.day)


@dp.callback_query(F.data.startswith("cal_day:"))
async def cal_day(callback: CallbackQuery) -> None:
    try:
        _, year_s, month_s, day_s = callback.data.split(":")
        year, month, day = int(year_s), int(month_s), int(day_s)
    except (ValueError, AttributeError):
        await callback.answer("Помилка вибору дати, спробуйте /start ще раз.", show_alert=True)
        return
    await _select_date(callback, year, month, day)


async def _select_date(callback: CallbackQuery, year: int, month: int, day: int) -> None:
    try:
        chosen = date(year, month, day)
    except ValueError:
        await callback.answer("Такої дати не існує 🙃", show_alert=True)
        return

    chat_id = callback.message.chat.id
    existing = user_data.get(chat_id)

    # Якщо для цієї ж дати вже є накопичені числа — не втрачаємо їх.
    if existing and existing.get("date") == chosen.isoformat():
        numbers = existing["numbers"]
    else:
        numbers = []

    user_data[chat_id] = {"date": chosen.isoformat(), "numbers": numbers}

    text = (
        f"✅ Обрано дату: <b>{chosen.strftime('%d.%m.%Y')}</b>"
        f"{format_average_line(numbers)}\n\n"
        f"Надсилайте числа для запису (можна з комою: 12,5).\n"
        f"Щоб змінити дату — /start"
    )

    try:
        await callback.message.edit_text(text)
    except Exception:
        # Наприклад, якщо текст не змінився — Telegram кине помилку "message is not modified".
        pass

    await callback.answer("Дату обрано ✅")


# --------------------------------------------------------------------------- #
#  Обробка чисел
# --------------------------------------------------------------------------- #

def try_parse_number(raw_text: str) -> float | None:
    """Парсить число з тексту, замінюючи кому на крапку. Повертає None, якщо не число."""
    cleaned = raw_text.strip().replace(",", ".").replace(" ", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


@dp.message(F.text)
async def handle_text(message: Message) -> None:
    text = (message.text or "").strip()

    # Невідомі команди (не /start) не намагаємось парсити як число.
    if text.startswith("/"):
        await message.answer("Невідома команда. Щоб почати — /start")
        return

    chat_id = message.chat.id
    entry = user_data.get(chat_id)

    if entry is None:
        await message.answer("Спочатку оберіть дату за допомогою команди /start 🗓")
        return

    value = try_parse_number(text)
    if value is None:
        await message.answer(
            "⚠️ Це не схоже на число. Надішліть, будь ласка, число "
            "(наприклад: 72 або 72,5)."
        )
        return

    numbers = entry["numbers"]
    old_avg = sum(numbers) / len(numbers) if numbers else None

    numbers.append(value)
    new_avg = sum(numbers) / len(numbers)

    if old_avg is None:
        phrase = "Записав перше значення для цієї дати. Продовжуй у тому ж дусі! 💪"
    elif new_avg < old_avg:
        phrase = random.choice(PHRASES_DOWN)
    elif new_avg > old_avg:
        phrase = random.choice(PHRASES_UP)
    else:
        phrase = random.choice(PHRASES_SAME)

    date_str = datetime.fromisoformat(entry["date"]).strftime("%d.%m.%Y")
    numbers_str = ", ".join(f"{n:g}" for n in numbers)

    reply = (
        f"{phrase}\n\n"
        f"📅 Дата: {date_str}\n"
        f"🔢 Значення ({len(numbers)}): {numbers_str}\n"
        f"📊 Середнє: <b>{new_avg:.3f}</b>"
    )
    await message.answer(reply)


# --------------------------------------------------------------------------- #
#  Міні веб-сервер для утримання сервісу на Render (health-check / keep-alive)
# --------------------------------------------------------------------------- #

async def health(request: web.Request) -> web.Response:
    return web.Response(text="OK: bot is running")


async def start_web_server() -> None:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("Health-check веб-сервер запущено на порту %s", PORT)


# --------------------------------------------------------------------------- #
#  Точка входу з автоматичним перезапуском поллінгу при збоях
# --------------------------------------------------------------------------- #

async def main() -> None:
    await start_web_server()

    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Бот запущений, починаю polling...")
            await dp.start_polling(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Polling впав з помилкою, перезапуск через 5 секунд...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
