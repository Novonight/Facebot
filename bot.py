import asyncio
import base64
import html
import random
import time
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from openai import AsyncOpenAI

BOT_TOKEN = "9296393327:AAHD9TXAjCkBXRhaN4Oj1R63J3jqUd5aIgQ"
OPENAI_API_KEY = "sk-9WGnK2UaxvuNIoCOvBVaoZ8IkpD91KWA"
BASE_URL = "https://proxyapi.ru"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=BASE_URL)

SYSTEM_PROMPT = (
    "Ты — дерзкий стендап-комик и эксперт по стилю и дейтингу. "
    "Сделай прожарку фото для анкеты знакомств. Пиши смешно, с сарказмом, "
    "бей по вайбу, позе, свету, фону и одежде, без жестких оскорблений внешности. "
    "Не используй markdown-разметку, звездочки или решетки. "
    "Раздели ответ СТРОГО на две части строкой SPLIT_HERE\n\n"
    "ЧАСТЬ 1 (Бесплатная прожарка, до 600 символов):\n"
    "1. Текущий рейтинг (от 3.5 до 6.8 из 10) и Скрытый потенциал (на 3 балла выше).\n"
    "2. 2-3 колких замечания по фото.\n"
    "3. Заинтригуй: напиши, что нашел ГЛАВНУЮ ошибку, но раскроешь её в полном отчете.\n\n"
    "SPLIT_HERE\n\n"
    "ЧАСТЬ 2 (Полный разбор):\n"
    "1. Раскрой главную ошибку.\n"
    "2. Дай 4 совета по апгрейду (прическа, одежда, свет, ракурс).\n"
    "3. Напиши 3 цепляющих био для анкеты."
)

VIBE_LIST = (
    "🔮 <b>Вердикт ИИ:</b> Твой вайб кричит «я отвечу на сообщение через 3 рабочих дня». Срочно меняй свет!",
    "🔮 <b>Вердикт ИИ:</b> Потенциал на 9.5/10, но выражение лица такое, будто у тебя только что украли последний ролл.",
    "🔮 <b>Вердикт ИИ:</b> С этим кадром тебя свайпают вправо только те, кто случайно уронил телефон.",
    "🔮 <b>Вердикт ИИ:</b> Вайб главного героя сериала, который забыл прочитать сценарий. Кидай фото — исправим!",
)
# ----------------------------------------


async def init_bot():
    commands = list((
        BotCommand(command="start", description="🔥 Запустить ИИ-Рентген"),
        BotCommand(command="roast", description="📸 Сделать прожарку фото"),
        BotCommand(command="pay", description="💳️ Открыть полный разбор и 3 био"),
        BotCommand(command="vibe", description="🎲 Случайный вердикт от нейросети"),
        BotCommand(command="help", description="❓️ Как работает разбор и скидка"),
    ))
    await bot.set_my_commands(commands)
    async with aiosqlite.connect("users.db") as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS requests ("
            "user_id INTEGER PRIMARY KEY, file_id TEXT, paid_report TEXT, created_at INTEGER)"
        )
        await db.commit()
# ----------------------------------------


def get_keyboard(created_at: int):
    is_discount = (int(time.time()) - created_at) <= 900
    text = "🔥 Полный разбор за 149 ₽ (скидка 15 мин)" if is_discount else "🔒️ Полный разбор за 299 ₽"
    btn = InlineKeyboardButton(text=text, callback_data="buy_full")
    return InlineKeyboardMarkup(inline_keyboard=list((list((btn,)),)))
# ----------------------------------------


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 <b>Привет! Это ИИ-Рентген внешности и анкет.</b>\n\n"
        "Кидай своё фото — я оценю твой вайб от 1 до 10, прожарю ошибки и покажу потенциал.\n\n"
        "📸 <i>Отправь одно фото прямо сейчас:</i>",
        parse_mode="HTML",
    )
# ----------------------------------------


@dp.message(Command("roast"))
async def cmd_roast(message: types.Message):
    await message.answer("📸 <b>Отправь одно фото в чат</b> — через 5 секунд получишь разбор!", parse_mode="HTML")
# ----------------------------------------


@dp.message(Command("vibe"))
async def cmd_vibe(message: types.Message):
    await message.answer(f"{random.choice(VIBE_LIST)}\n\n📸 <i>Кидай фото для реального разбора!</i>", parse_mode="HTML")
# ----------------------------------------@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "❓️ <b>Как это работает:</b>\n"
        "1. Кидаешь фото — получаешь бесплатный рейтинг и прожарку.\n"
        "2. В первые <b>15 минут</b> полный разбор и 3 био стоят <b>149 ₽</b> (потом 299 ₽).",
        parse_mode="HTML",
    )
# ----------------------------------------


@dp.message(Command("pay"))
async def cmd_pay(message: types.Message):
    if not message.from_user:
        return
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT created_at FROM requests WHERE user_id = ?", (message.from_user.id,))
        row = await cursor.fetchone()
    if not row:
        await message.answer("🔒️ Сначала <b>отправь фото</b> в чат для анализа!", parse_mode="HTML")
        return
    created_at = next(iter(row))
    await message.answer("💳️ <b>Твой полный разбор готов!</b>", reply_markup=get_keyboard(created_at), parse_mode="HTML")
# ----------------------------------------


@dp.message()
async def handle_photo(message: types.Message):
    if not message.from_user:
        return
    file_id = None
    if message.photo:
        file_id = next(reversed(message.photo)).file_id
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id

    if file_id is None:
        await message.answer("📸 Отправь именно <b>фотографию</b>!", parse_mode="HTML")
        return

    status = await message.answer("🔍️ <i>Загружаю фото в нейросеть...</i>", parse_mode="HTML")
    try:
        file_info = await bot.get_file(file_id)
        if not file_info.file_path:
            await status.edit_text("❌ Ошибка загрузки фото.")
            return
        file_bytes = await bot.download_file(file_info.file_path)
        if not file_bytes:
            await status.edit_text("❌ Не удалось скачать фото.")
            return
        b64_img = base64.b64encode(file_bytes.read()).decode("utf-8")
        await status.edit_text("📊 <i>Сканирую вайб и считаю рейтинг...</i>", parse_mode="HTML")

        user_msg = list((
            {"type": "text", "text": "Разбери это фото по инструкции."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}},
        ))
        msgs = list(({"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_msg}))

        response = await client.chat.completions.create(model="gpt-4o-mini", messages=msgs, max_tokens=1000)
        full_text = next(iter(response.choices)).message.content or ""

        free_part, sep, paid_part = full_text.partition("SPLIT_HERE")
        free_safe = html.escape(free_part.strip())
        paid_safe = html.escape(paid_part.strip() or "Детальный план апгрейда готов.")

        now = int(time.time())
        async with aiosqlite.connect("users.db") as db:
            await db.execute(
                "INSERT OR REPLACE INTO requests (user_id, file_id, paid_report, created_at) VALUES (?, ?, ?, ?)",
                (message.from_user.id, file_id, paid_safe, now),
            )
            await db.commit()

        await status.delete()
        offer = (
            f"{free_safe}\n\n━━━━━━━━━━━━━━━━━━━━\n"
            "🔒️ <b>Полный разбор + главная ошибка + 3 био готовы!</b>\n"
            "⏳️ Спеццена <b>149 ₽</b> действует <b>15 минут</b>, затем <b>299 ₽</b>."
        )
        await message.answer(offer, reply_markup=get_keyboard(now), parse_mode="HTML")
    except Exception as err:
        await status.edit_text(f"❌ Ошибка:\n<code>{html.escape(str(err))}</code>", parse_mode="HTML")
# ----------------------------------------@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    if callback.data != "buy_full":
        await callback.answer()
        return
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT paid_report, created_at FROM requests WHERE user_id = ?", (callback.from_user.id,))
        row = await cursor.fetchone()
    if not row:
        await callback.answer("Сначала отправь фото!", show_alert=True)
        return
    paid_report, created_at = row
    price = 149 if (int(time.time()) - created_at <= 900) else 299
    if isinstance(callback.message, types.Message):
        await callback.message.answer(
            f"💳️ <b>Счет: {price} ₽</b>\n\n<i>(Тестовый режим)</i>\n\n{paid_report}",
            parse_mode="HTML",
        )
    await callback.answer()
# ----------------------------------------


async def main():
    await init_bot()
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот запущен!")
    await dp.start_polling(bot)
# ----------------------------------------


asyncio.run(main())