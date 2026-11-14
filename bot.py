import asyncio
import base64
import datetime
import html
import random
import re
import sqlite3
import time
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand,
)

BOT_TOKEN = "9296393327:AAHD9TXAjCkBXRhaN4Oj1R63J3jqUd5aIgQ"
OPENAI_API_KEY = "sk-9WGnK2UaxvuNIoCOvBVaoZ8IkpD91KWA"
API_URL = "https://proxyapi.ru"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

BATTLE_WAIT = set()
BATTLE_FIRST = {}
DUEL_WAIT = {}
DUEL_QUEUE = {}
ACTIVE_CHATS = {}
STYLIST_MODE = set()

SYS_PROMPT = (
    "Ты дерзкий стендап-комик и эксперт по стилю и дейтингу. "
    "Сделай разбор фото для анкеты знакомств без markdown, звездочек и решеток. "
    "Первой строкой напиши ТОЛЬКО балл от 3.50 до 9.80 в формате: SCORE: 7.45\n"
    "Затем раздели ответ СТРОГО строкой SPLIT_HERE\n"
    "ЧАСТЬ 1 (Короткий бесплатный тизер до 240 символов, без советов):\n"
    "1. Текущий рейтинг (совпадающий с SCORE) и Потенциал (+2.5 балла).\n"
    "2. Вайб-двойник: смешное сравнение с киногероем или мемом в 1 строчку.\n"
    "3. Напиши: Я нашел 3 критические ошибки, которые убивают 80% совпадений, "
    "но они скрыты в полном отчете.\n"
    "SPLIT_HERE\n"
    "ЧАСТЬ 2 (Полный разбор):\n"
    "1. Подробно раскрой все 3 критические ошибки.\n"
    "2. Дай 4 совета по апгрейду (свет, ракурс, одежда, прическа/поза).\n"
    "3. Напиши 3 цепляющих био для анкеты."
)

BATTLE_PROMPT = (
    "Ты эксперт по визуалу. Сравни ДВА фото одного человека для аватарки. "
    "Без markdown, звездочек и решеток. Раздели ответ строкой SPLIT_HERE\n"
    "ЧАСТЬ 1 (до 220 символов): назови победителя (Фото №1 или №2), разницу "
    "в баллах, смешную причину и напиши, что полный разбор закрыт подпиской.\n"
    "SPLIT_HERE\n"
    "ЧАСТЬ 2: подробный разбор плюсов и минусов обоих кадров и главный совет."
)

DUEL_PROMPT = (
    "Ты судья батла внешности. Сравни Фото Игрока 1 и Фото Игрока 2. "
    "Без markdown и звездочек, до 420 символов: объяви победителя, счет "
    "(например 8.4 против 7.9), дай по 1 колкой шутке каждому и пожелай общения."
)

STYLIST_PROMPT = (
    "Ты элитный персональный ИИ-стилист и тренер харизмы для VIP-клиента LEGEND. "
    "Отвечай стильно, четко и по делу. Без markdown, звездочек и решеток."
)

FACTS = (
    "💡 <b>Факт дня:</b> Мозг оценивает привлекательность человека на фото "
    "всего за <b>0.1 секунды</b> — быстрее, чем ты успеваешь моргнуть.",
    "💡 <b>Факт дня:</b> Мягкий боковой свет от окна повышает привлекательность "
    "портрета на <b>42%</b> по сравнению со светом люстры сверху.",
    "💡 <b>Факт дня:</b> Камера ближе 40 см искажает пропорции и увеличивает нос "
    "на <b>30%</b>. Отодвинь телефон и включи 2x-зум.",
    "💡 <b>Факт дня:</b> Искренняя улыбка с прищуром глаз повышает доверие "
    "к профилю почти в <b>2 раза</b>.",
    "💡 <b>Факт дня:</b> Однотонный фон без лишних вещей за спиной удерживает "
    "взгляд собеседника строго на твоем лице.",
)


def init_db():
    conn = sqlite3.connect("users.db")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "user_id INTEGER PRIMARY KEY, name TEXT DEFAULT 'Игрок', "
        "best_score REAL DEFAULT 0.0, last_report TEXT DEFAULT '', "
        "sub_until INTEGER DEFAULT 0, is_legend INTEGER DEFAULT 0, "
        "invited_by INTEGER DEFAULT 0, ref_count INTEGER DEFAULT 0, "
        "ref_paid INTEGER DEFAULT 0, streak INTEGER DEFAULT 0, "
        "last_day INTEGER DEFAULT 0, disc_30 INTEGER DEFAULT 0, "
        "free_duels INTEGER DEFAULT 0, gender TEXT DEFAULT '')"
    )
    cols = (
        "ALTER TABLE users ADD COLUMN name TEXT DEFAULT 'Игрок'",
        "ALTER TABLE users ADD COLUMN best_score REAL DEFAULT 0.0",
        "ALTER TABLE users ADD COLUMN last_report TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN sub_until INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN is_legend INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN invited_by INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN ref_count INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN ref_paid INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN streak INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN last_day INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN disc_30 INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN free_duels INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN gender TEXT DEFAULT ''",
    )
    for sql in cols:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


def get_user(uid: int):
    conn = sqlite3.connect("users.db")
    cur = conn.execute(
        "SELECT sub_until, last_report, ref_count, best_score, is_legend, "
        "streak, disc_30, free_duels, gender, last_day FROM users WHERE user_id = ?",
        (uid,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return (0, "", 0, 0.0, 0, 0, 0, 0, "", 0)
    return row
def reg_user(uid: int, full_name: str, ref_id: int = 0):
    clean = html.escape((full_name or "Игрок").strip())
    conn = sqlite3.connect("users.db")
    cur = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
    if not cur.fetchone():
        v_ref = ref_id if (ref_id > 0 and ref_id != uid) else 0
        conn.execute(
            "INSERT INTO users (user_id, name, invited_by) VALUES (?, ?, ?)",
            (uid, clean, v_ref),
        )
    else:
        conn.execute("UPDATE users SET name = ? WHERE user_id = ?", (clean, uid))
    conn.commit()
    conn.close()


def add_streak(uid: int):
    today = datetime.date.today().toordinal()
    _, _, _, _, _, streak, disc, f_duels, _, last_day = get_user(uid)

    hit_5 = False
    if last_day == today:
        pass
    elif last_day == today - 1:
        streak += 1
        if streak == 5:
            disc = 1
            f_duels += 1
            hit_5 = True
    else:
        streak = 1

    conn = sqlite3.connect("users.db")
    conn.execute(
        "UPDATE users SET streak=?, last_day=?, disc_30=?, free_duels=? WHERE user_id=?",
        (streak, today, disc, f_duels, uid),
    )
    conn.commit()
    conn.close()
    return streak, hit_5


def save_score(uid: int, report: str, score: float):
    _, _, _, old_best, is_leg, _, _, _, _, _ = get_user(uid)
    boosted = min(9.99, score + 1.0) if (is_leg and score > 0) else score
    best = boosted if boosted > old_best else old_best
    conn = sqlite3.connect("users.db")
    conn.execute(
        "UPDATE users SET last_report=?, best_score=? WHERE user_id=?",
        (report, best, uid),
    )
    conn.commit()
    conn.close()
    return best


def activate_plan(uid: int, months: int, leg_flag: int):
    now = int(time.time())
    conn = sqlite3.connect("users.db")
    cur = conn.execute(
        "SELECT sub_until, last_report, best_score, is_legend, invited_by, ref_paid "
        "FROM users WHERE user_id=?",
        (uid,),
    )
    row = cur.fetchone()
    sub_u, rep, best, is_l, inv_by, r_paid = row if row else (0, "", 0.0, 0, 0, 0)
    base = sub_u if sub_u > now else now

    if leg_flag == 2:
        new_until = now + 100 * 365 * 86400
        new_leg = 1
    elif leg_flag == 1:
        new_until = base + 30 * 86400
        new_leg = 1
    else:
        new_until = base + months * 30 * 86400
        new_leg = is_l

    new_best = best
    if new_leg == 1 and is_l == 0:
        new_best = min(9.99, best + 1.0) if best > 0 else 8.50

    conn.execute(
        "UPDATE users SET sub_until=?, is_legend=?, best_score=?, disc_30=0 WHERE user_id=?",
        (new_until, new_leg, new_best, uid),
    )

    rewarded_uid = 0
    if inv_by > 0 and r_paid == 0:
        conn.execute("UPDATE users SET ref_paid=1 WHERE user_id=?", (uid,))
        c2 = conn.execute("SELECT sub_until FROM users WHERE user_id=?", (inv_by,))
        r2 = c2.fetchone()
        if r2:
            inv_u = next(iter(r2))
            inv_base = inv_u if inv_u > now else now
            conn.execute(
                "UPDATE users SET sub_until=?, ref_count=ref_count+1 WHERE user_id=?",
                (inv_base + 10 * 86400, inv_by),
            )
            rewarded_uid = inv_by

    conn.commit()
    conn.close()
    return rep or "", rewarded_uid


def get_top(uid: int):
    conn = sqlite3.connect("users.db")
    rows = conn.execute(
        "SELECT user_id, name, best_score, is_legend FROM users "
        "WHERE best_score > 0 ORDER BY best_score DESC LIMIT 20"
    ).fetchall()
    rk = conn.execute(
        "SELECT COUNT(*) FROM users WHERE best_score > "
        "(SELECT COALESCE(best_score, 0) FROM users WHERE user_id=?)",
        (uid,),
    ).fetchone()
    conn.close()
    return rows, (next(iter(rk)) + 1) if rk else 1


async def ask_ai(sys_p: str, content: list):
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    msgs = list(({"role": "system", "content": sys_p}, {"role": "user", "content": content}))
    payload = {"model": "gpt-4o-mini", "messages": msgs, "max_tokens": 1000}
    async with aiohttp.ClientSession() as s:
        async with s.post(API_URL, headers=headers, json=payload) as r:
            data = await r.json()
            if r.status != 200:
                raise RuntimeError(data.get("error", {}).get("message", str(data)))
            ch = next(iter(data.get("choices")))
            return ch.get("message", {}).get("content", "")


def main_kb():
    r1 = list((KeyboardButton(text="📸 Прожарить фото"), KeyboardButton(text="🥊 Дуэль 1 на 1")))
    r2 = list((KeyboardButton(text="🏆 Топ-100 красоты"), KeyboardButton(text="🧠 ИИ-Стилист (LEGEND)")))
    r3 = list((KeyboardButton(text="⚔️ Битва 2 фото"), KeyboardButton(text="💎 Подписка / LEGEND")))
    r4 = list((KeyboardButton(text="🎁 Бесплатный доступ"), KeyboardButton(text="💡 Факт дня")))
    return ReplyKeyboardMarkup(keyboard=list((r1, r2, r3, r4)), resize_keyboard=True)


def chat_kb():
    r1 = list((KeyboardButton(text="🚪 Завершить чат"), KeyboardButton(text="🥊 Следующий соперник")))
    return ReplyKeyboardMarkup(keyboard=list((r1,)), resize_keyboard=True)


def sub_kb(disc: int):
    if disc:
        btns = (
            ("🔥 1 мес — 104 ₽ (-30%)", "pay_1_0_104"),
            ("⚡ 3 мес — 265 ₽ (-30%)", "pay_3_0_265"),
            ("🚀 6 мес — 489 ₽ (-30%)", "pay_6_0_489"),
            ("👑 9 мес — 629 ₽ (-30%)", "pay_9_0_629"),
            ("💎 12 мес — 734 ₽ (-30%)", "pay_12_0_734"),
            ("🔱 LEGEND 1 мес — 1400 ₽ (-30%)", "pay_1_1_1400"),
            ("👑 LEGEND НАВСЕГДА — 3500 ₽ (-30%)", "pay_999_2_3500"),
        )
    else:
        btns = (
            ("🔥 1 месяц — 149 ₽", "pay_1_0_149"),
            ("⚡ 3 месяца — 379 ₽", "pay_3_0_379"),
            ("🚀 6 месяцев — 699 ₽", "pay_6_0_699"),
            ("👑 9 месяцев — 899 ₽", "pay_9_0_899"),
            ("💎 12 месяцев — 1049 ₽", "pay_12_0_1049"),
            ("🔱 LEGEND 1 мес + ИИ-Стилист — 2000 ₽", "pay_1_1_2000"),
            ("👑 LEGEND НАВСЕГДА + Корона — 5000 ₽", "pay_999_2_5000"),
        )
    rows = list((list((InlineKeyboardButton(text=t, callback_data=c),)) for t, c in btns))
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def end_chat(uid: int, notify: bool = True):
    pid = ACTIVE_CHATS.pop(uid, None)
    if pid:
        ACTIVE_CHATS.pop(pid, None)
        if notify:
            try:
                await bot.send_message(pid, "🚪 Собеседник завершил чат.", reply_markup=main_kb())
            except Exception:
                pass


def get_today_fact():
    idx = datetime.date.today().toordinal() % len(FACTS)
    it = iter(FACTS)
    for _ in range(idx):
        next(it)
    return next(it)
@dp.message(CommandStart())
async def h_start(m: types.Message):
    if not m.from_user:
        return
    uid = m.from_user.id
    await end_chat(uid)
    DUEL_WAIT.pop(uid, None)
    STYLIST_MODE.discard(uid)

    parts = (m.text or "").split()
    ref = 0
    if len(parts) > 1:
        it = iter(parts)
        next(it)
        arg = next(it)
        if arg.isdigit():
            ref = int(arg)
    reg_user(uid, m.from_user.full_name, ref)

    await m.answer(
        f"👋 <b>Привет! Это ИИ-Рентген внешности.</b>\n\n"
        f"Кидай фото — получишь рейтинг, место в <b>Топ-100</b> и Огонёк 🔥.\n\n{get_today_fact()}",
        reply_markup=main_kb(),
        parse_mode="HTML",
    )


@dp.message(F.text == "🚪 Завершить чат")
async def h_stop(m: types.Message):
    if not m.from_user:
        return
    uid = m.from_user.id
    DUEL_WAIT.pop(uid, None)
    DUEL_QUEUE.pop(uid, None)
    STYLIST_MODE.discard(uid)
    await end_chat(uid)
    await m.answer("✅ Главное меню:", reply_markup=main_kb())


@dp.message(Command("fact"))
@dp.message(F.text == "💡 Факт дня")
async def h_fact(m: types.Message):
    if m.from_user:
        STYLIST_MODE.discard(m.from_user.id)
    await m.answer(get_today_fact(), parse_mode="HTML")


@dp.message(Command("top"))
@dp.message(F.text == "🏆 Топ-100 красоты")
async def h_top(m: types.Message):
    if not m.from_user:
        return
    uid = m.from_user.id
    STYLIST_MODE.discard(uid)
    reg_user(uid, m.from_user.full_name)
    rows, rk = get_top(uid)
    _, _, _, best, _, _, _, _, _, _ = get_user(uid)
    lines = list(("🏆 <b>ТОП-100 КРАСОТЫ</b>\n",))
    for i, r in enumerate(rows, 1):
        r_uid, r_name, r_score, r_leg = r
        crown = " 👑[LEGEND]" if r_leg else ""
        me = " <b>(ТЫ)</b>" if r_uid == uid else ""
        lines.append(f"{i}. {r_name}{crown}{me} — <b>{r_score:.2f}</b>")
    lines.append(f"\n📍 Твой балл: <b>{best:.2f}</b> (Место: <b>#{rk}</b>)")
    await m.answer("\n".join(lines), parse_mode="HTML")


@dp.message(Command("free"))
@dp.message(F.text == "🎁 Бесплатный доступ")
async def h_free(m: types.Message):
    if not m.from_user:
        return
    uid = m.from_user.id
    STYLIST_MODE.discard(uid)
    me = await bot.get_me()
    _, _, ref_c, _, _, streak, _, _, _, _ = get_user(uid)
    link = f"https://t.me{me.username}?start={uid}"
    await m.answer(
        f"🎁 <b>+10 дней VIP за каждого оплатившего друга!</b>\n"
        f"Оплативших друзей: <b>{ref_c}</b> (Бонус: <b>{ref_c * 10} дн.</b>)\n"
        f"🔗 Ссылка:\n<code>{link}</code>\n\n"
        f"🔥 <b>Огонёк:</b> {streak} из 5 дней подряд (на 5-й день скидка 30% + 1 дуэль!)",
        parse_mode="HTML",
    )


@dp.message(Command("pay"))
@dp.message(F.text == "💎 Подписка / LEGEND")
async def h_pay(m: types.Message):
    if not m.from_user:
        return
    STYLIST_MODE.discard(m.from_user.id)
    _, _, _, _, _, _, disc, _, _, _ = get_user(m.from_user.id)
    await m.answer(
        "💎 <b>Выбери тариф VIP или статус LEGEND:</b>\n"
        "• <b>VIP:</b> полные разборы, 3 био и Дуэль 1 на 1 с чатом.\n"
        "• <b>LEGEND:</b> корона 👑 в Топ-100, буст +1.00 и личный 🧠 ИИ-Стилист!",
        reply_markup=sub_kb(disc),
        parse_mode="HTML",
    )


@dp.message(Command("stylist"))
@dp.message(F.text == "🧠 ИИ-Стилист (LEGEND)")
async def h_stylist(m: types.Message):
    if not m.from_user:
        return
    uid = m.from_user.id
    sub_u, _, _, _, is_leg, _, disc, _, _, _ = get_user(uid)
    if is_leg == 0 or sub_u <= int(time.time()):
        await m.answer(
            "🔱 <b>Личный ИИ-Стилист доступен только со статусом LEGEND!</b>",
            reply_markup=sub_kb(disc),
            parse_mode="HTML",
        )
        return
    STYLIST_MODE.add(uid)
    await m.answer("🔱 <b>ИИ-Стилист на связи!</b> Задай вопрос или кинь фото образа:", parse_mode="HTML")


@dp.message(Command("duel"))
@dp.message(F.text == "🥊 Дуэль 1 на 1")
@dp.message(F.text == "🥊 Следующий соперник")
async def h_duel(m: types.Message):
    if not m.from_user:
        return
    uid = m.from_user.id
    await end_chat(uid)
    STYLIST_MODE.discard(uid)
    sub_u, _, _, _, _, _, disc, f_duels, gen, _ = get_user(uid)
    if sub_u <= int(time.time()) and f_duels <= 0:
        await m.answer("🔒 <b>Дуэль 1 на 1 доступна по VIP-подписке!</b>", reply_markup=sub_kb(disc), parse_mode="HTML")
        return
    if not gen:
        kb = InlineKeyboardMarkup(inline_keyboard=list((list((
            InlineKeyboardButton(text="👨 Я парень", callback_data="gen_M"),
            InlineKeyboardButton(text="👩 Я девушка", callback_data="gen_F"),
        )),)))
        await m.answer("👤 <b>Укажи свой пол перед дуэлью:</b>", reply_markup=kb, parse_mode="HTML")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=list((
        list((InlineKeyboardButton(text="👩 Девушек", callback_data="trg_F"),
              InlineKeyboardButton(text="👨 Парней", callback_data="trg_M"))),
        list((InlineKeyboardButton(text="🎲 Любого соперника", callback_data="trg_ANY"),)),
    )))
    await m.answer("🥊 <b>Кого искать для дуэли?</b>", reply_markup=kb, parse_mode="HTML")


@dp.message(F.text == "📸 Прожарить фото")
async def h_roast_btn(m: types.Message):
    if m.from_user:
        uid = m.from_user.id
        BATTLE_WAIT.discard(uid)
        DUEL_WAIT.pop(uid, None)
        STYLIST_MODE.discard(uid)
    await m.answer("📸 <b>Отправь одно фото в чат!</b>", parse_mode="HTML")


@dp.message(F.text == "⚔️ Битва 2 фото")
async def h_battle_btn(m: types.Message):
    if m.from_user:
        uid = m.from_user.id
        STYLIST_MODE.discard(uid)
        DUEL_WAIT.pop(uid, None)
        BATTLE_WAIT.add(uid)
        BATTLE_FIRST.pop(uid, None)
    await m.answer("⚔️ <b>Отправь ПЕРВОЕ фото для сравнения:</b>", parse_mode="HTML")


async def get_b64(fid: str):
    fi = await bot.get_file(fid)
    if not fi.file_path:
        return None
    fb = await bot.download_file(fi.file_path)
    return base64.b64encode(fb.read()).decode("utf-8") if fb else None


@dp.message()
async def h_msg(m: types.Message):
    if not m.from_user:
        return
    uid = m.from_user.id
    reg_user(uid, m.from_user.full_name)

    if uid in ACTIVE_CHATS:
        try:
            await m.copy_to(ACTIVE_CHATS[uid])
        except Exception:
            await end_chat(uid, False)
            await m.answer("❌ Собеседник вышел.", reply_markup=main_kb())
        return

    fid = next(reversed(m.photo)).file_id if m.photo else None

    if uid in STYLIST_MODE:
        st = await m.answer("🔱 <i>Стилист думает...</i>", parse_mode="HTML")
        try:
            cnt = list(({"type": "text", "text": m.text or m.caption or "Оцени образ"},))
            if fid:
                b64 = await get_b64(fid)
                if b64:
                    cnt.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
            ans = html.escape(await ask_ai(STYLIST_PROMPT, cnt))
            await st.edit_text(f"🔱 <b>ИИ-Стилист:</b>\n\n{ans}", parse_mode="HTML")
        except Exception as e:
            await st.edit_text(f"❌ Ошибка: {html.escape(str(e))}")
        return

    if not fid:
        await m.answer("📸 Отправь <b>фото</b> или выбери кнопку в меню!", reply_markup=main_kb(), parse_mode="HTML")
        return

    if uid in DUEL_WAIT:
        trg = DUEL_WAIT.pop(uid)
        st = await m.answer("⏳ <i>Ищем соперника...</i>", parse_mode="HTML")
        b64 = await get_b64(fid)
        if not b64:
            await st.edit_text("❌ Ошибка фото.")
            return
        sub_u, _, _, _, _, _, _, f_duels, my_gen, _ = get_user(uid)
        if sub_u <= int(time.time()) and f_duels > 0:
            conn = sqlite3.connect("users.db")
            conn.execute("UPDATE users SET free_duels=MAX(0, free_duels-1) WHERE user_id=?", (uid,))
            conn.commit()
            conn.close()

        opp_id, opp_val = None, None
        for q_id, q_v in list(DUEL_QUEUE.items()):
            if q_id != uid:
                _, _, q_gen, q_trg = q_v
                ok1 = (trg == "ANY") or (trg == q_gen)
                ok2 = (q_trg == "ANY") or (q_trg == my_gen)
                if ok1 and ok2:
                    opp_id = q_id
                    opp_val = DUEL_QUEUE.pop(q_id)
                    break

        if not opp_id or not opp_val:
            DUEL_QUEUE[uid] = (fid, b64, my_gen, trg)
            await st.edit_text("🔍 <b>Ты в очереди на дуэль!</b> Ждем соперника...", parse_mode="HTML")
            return

        opp_fid, opp_b64, _, _ = opp_val
        await st.edit_text("⚔️ <i>Соперник найден! Идет батл...</i>", parse_mode="HTML")
        try:
            cnt = list((
                {"type": "text", "text": "Сравни Игрока 1 и Игрока 2"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{opp_b64}"}},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ))
            verd = html.escape(await ask_ai(DUEL_PROMPT, cnt))
            await st.delete()
            ACTIVE_CHATS[uid] = opp_id
            ACTIVE_CHATS[opp_id] = uid
            await bot.send_photo(opp_id, fid, caption=f"🥊 <b>ДУЭЛЬ!</b>\n\n{verd}\n\n💬 Чат открыт:", reply_markup=chat_kb(), parse_mode="HTML")
            await m.answer_photo(opp_fid, caption=f"🥊 <b>ДУЭЛЬ!</b>\n\n{verd}\n\n💬 Чат открыт:", reply_markup=chat_kb(), parse_mode="HTML")
        except Exception as e:
            await st.edit_text(f"❌ Ошибка: {html.escape(str(e))}")
        return

    if uid in BATTLE_WAIT:
        if uid not in BATTLE_FIRST:
            b1 = await get_b64(fid)
            if b1:
                BATTLE_FIRST[uid] = b1
                await m.answer("✅ Первое фото принято! Отправь <b>ВТОРОЕ фото</b>:", parse_mode="HTML")
            return
        BATTLE_WAIT.discard(uid)
        b1 = BATTLE_FIRST.pop(uid)
        st = await m.answer("⚔️ <i>Сравниваю два фото...</i>", parse_mode="HTML")
        try:
            b2 = await get_b64(fid)
            cnt = list((
                {"type": "text", "text": "Сравни два фото"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b1}"}},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b2}"}},
            ))
            res = await ask_ai(BATTLE_PROMPT, cnt)
            p1, _, p2 = res.partition("SPLIT_HERE")
            sub_u, _, _, _, _, _, disc, _, _, _ = get_user(uid)
            await st.delete()
            if sub_u > int(time.time()):
                await m.answer(f"⚔️ {html.escape(p1.strip())}\n\n{html.escape(p2.strip())}", parse_mode="HTML")
            else:
                await m.answer(f"⚔️ {html.escape(p1.strip())}\n\n🔒 Полный разбор по подписке:", reply_markup=sub_kb(disc), parse_mode="HTML")
        except Exception as e:
            await st.edit_text(f"❌ Ошибка: {html.escape(str(e))}")
        return

    st = await m.answer("🔍 <i>Анализирую фото...</i>", parse_mode="HTML")
    try:
        b64 = await get_b64(fid)
        if not b64:
            await st.edit_text("❌ Ошибка загрузки.")
            return
        cnt = list((
            {"type": "text", "text": "Разбери фото"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ))
        raw = await ask_ai(SYS_PROMPT, cnt)
        sc = round(random.uniform(5.2, 7.6), 2)
        mt = re.search(r"SCORE:\s*(\d+(?:\.\d+)?)", raw)
        if mt:
            sc = float(mt.group(1))
            raw = re.sub(r"SCORE:\s*\d+(?:\.\d+)?\s*", "", raw, count=1).strip()

        p1, _, p2 = raw.partition("SPLIT_HERE")
        f_txt = html.escape(p1.strip())
        p_txt = html.escape(p2.strip() or "План готов.")
        streak, hit5 = add_streak(uid)
        best = save_score(uid, p_txt, sc)
        _, rk = get_top(uid)
        sub_u, _, _, _, _, _, disc, _, _, _ = get_user(uid)
        await st.delete()

        bonus = "\n🎉 <b>5 дней подряд! Открыта СКИДКА 30% и 1 бесплатная дуэль!</b>" if hit5 else ""
        head = f"{f_txt}\n\n🏆 Топ-100: <b>#{rk}</b> ({best:.2f}) | 🔥 Огонёк: <b>{streak} дн.</b>{bonus}"
        if sub_u > int(time.time()):
            await m.answer(f"{head}\n━━━━━━━━━━━━━━━━━━━━\n💎 <b>ПОЛНЫЙ РАЗБОР:</b>\n\n{p_txt}", parse_mode="HTML")
        else:
            await m.answer(f"{head}\n━━━━━━━━━━━━━━━━━━━━\n🔒 <b>Полный разбор и Дуэль 1 на 1 закрыты!</b>", reply_markup=sub_kb(disc), parse_mode="HTML")
    except Exception as e:
        await st.edit_text(f"❌ Ошибка: {html.escape(str(e))}")
@dp.callback_query()
async def h_cb(cb: types.CallbackQuery):
    data = cb.data or ""
    uid = cb.from_user.id
    if data.startswith("gen_"):
        g = "F" if data == "gen_F" else "M"
        conn = sqlite3.connect("users.db")
        conn.execute("UPDATE users SET gender=? WHERE user_id=?", (g, uid))
        conn.commit()
        conn.close()
        if isinstance(cb.message, types.Message):
            kb = InlineKeyboardMarkup(inline_keyboard=list((
                list((InlineKeyboardButton(text="👩 Девушек", callback_data="trg_F"),
                      InlineKeyboardButton(text="👨 Парней", callback_data="trg_M"))),
                list((InlineKeyboardButton(text="🎲 Любого соперника", callback_data="trg_ANY"),)),
            )))
            await cb.message.edit_text("🥊 <b>Кого искать для дуэли?</b>", reply_markup=kb, parse_mode="HTML")
    elif data.startswith("trg_"):
        _, trg = data.split("_")
        DUEL_WAIT[uid] = trg
        if isinstance(cb.message, types.Message):
            await cb.message.answer("📸 <b>Отправь боевое фото для дуэли:</b>", reply_markup=chat_kb(), parse_mode="HTML")
    elif data.startswith("pay_"):
        _, m_str, l_str, p_str = data.split("_")
        months, leg_flag, price = int(m_str), int(l_str), int(p_str)
        rep, inv_uid = activate_plan(uid, months, leg_flag)
        if inv_uid > 0:
            try:
                await bot.send_message(inv_uid, "🎉 Друг оплатил подписку! Тебе начислено <b>+10 дней VIP</b>!", parse_mode="HTML")
            except Exception:
                pass
        if isinstance(cb.message, types.Message):
            extra = f"\n\n━━━━━━━━━━━━━━━━━━━━\n🔓 <b>Твой разбор:</b>\n\n{rep}" if rep.strip() else ""
            await cb.message.answer(f"✅ <b>Оплата {price} ₽ прошла! Доступ открыт.</b>{extra}", parse_mode="HTML")
    await cb.answer()


async def main():
    init_db()
    cmds = list((
        BotCommand(command="start", description="🔥 Запустить бота"),
        BotCommand(command="duel", description="🥊 Дуэль 1 на 1 + чат"),
        BotCommand(command="top", description="🏆 Топ-100 красоты"),
        BotCommand(command="stylist", description="🧠 ИИ-Стилист (LEGEND)"),
        BotCommand(command="pay", description="💎 Подписка / LEGEND"),
        BotCommand(command="free", description="🎁 +10 дней за друга"),
    ))
    await bot.set_my_commands(cmds)
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот запущен!")
    await dp.start_polling(bot)


asyncio.run(main())
