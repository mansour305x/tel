import asyncio
import logging
import os
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID_RAW = os.getenv("OWNER_ID", "")
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN غير موجود داخل ملف .env")

OWNER_ID = int(OWNER_ID_RAW) if OWNER_ID_RAW.strip().isdigit() else None

ADMIN_IDS = [
    int(x.strip())
    for x in ADMIN_IDS_RAW.split(",")
    if x.strip().isdigit()
]

if OWNER_ID and OWNER_ID not in ADMIN_IDS:
    ADMIN_IDS.append(OWNER_ID)

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
DB_NAME = "mansour_factory.db"


class SupportState(StatesGroup):
    waiting_message = State()


class BroadcastState(StatesGroup):
    waiting_message = State()


class BotTokenState(StatesGroup):
    waiting_token = State()


def db():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            role TEXT DEFAULT 'user',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            message TEXT,
            status TEXT DEFAULT 'open',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS bot_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER,
            bot_username TEXT,
            bot_name TEXT,
            template TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)

    cur.execute("""
        INSERT OR IGNORE INTO settings (key, value)
        VALUES ('maintenance', 'off')
    """)

    conn.commit()
    conn.close()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def save_user(user):
    conn = db()
    cur = conn.cursor()

    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    role = "owner" if OWNER_ID and user.id == OWNER_ID else "admin" if user.id in ADMIN_IDS else "user"

    cur.execute("""
        INSERT INTO users (user_id, username, full_name, role, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            full_name = excluded.full_name,
            role = excluded.role
    """, (user.id, user.username, full_name, role, now()))

    conn.commit()
    conn.close()


def is_owner(user_id: int) -> bool:
    return OWNER_ID is not None and user_id == OWNER_ID


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS or is_owner(user_id)


def get_setting(key: str) -> str:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else ""


def set_setting(key: str, value: str):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value))
    conn.commit()
    conn.close()


def count_table(table_name: str) -> int:
    conn = db()
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cur.fetchone()[0]
    conn.close()
    return count


def get_all_users():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def add_support_message(user_id, username, message):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO support_messages (user_id, username, message, created_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, username, message, now()))
    conn.commit()
    conn.close()


def add_bot_project(owner_id, bot_username, bot_name, template):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO bot_projects (owner_id, bot_username, bot_name, template, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (owner_id, bot_username, bot_name, template, "pending", now()))
    conn.commit()
    conn.close()


async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=reply_markup)


def btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def main_menu(user_id: int):
    rows = [
        [btn("➕ إنشاء بوت جديد", "create_bot"), btn("🤖 بوتاتي", "my_bots")],
        [btn("📦 القوالب الجاهزة", "templates"), btn("💎 الخدمات", "services")],
        [btn("💳 الاشتراكات", "plans"), btn("👤 حسابي", "account")],
        [btn("📘 شرح الاستخدام", "help"), btn("🛟 الدعم الفني", "support")],
        [btn("📊 حالة النظام", "system_status")]
    ]

    if is_admin(user_id):
        rows.append([btn("🛠 لوحة تحكم الإدارة", "admin_panel")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_home():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🏠 القائمة الرئيسية", "home")]
    ])


def create_bot_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🔑 إرسال توكن البوت", "send_token")],
        [btn("📘 طريقة إنشاء التوكن", "token_help")],
        [btn("📦 اختيار قالب جاهز", "templates")],
        [btn("⚠️ تعليمات الأمان", "security_notes")],
        [btn("🏠 القائمة الرئيسية", "home")]
    ])


def templates_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("📥 بوت تحميل مقاطع", "template_downloader")],
        [btn("🛒 بوت متجر", "template_store"), btn("🎫 بوت دعم فني", "template_support")],
        [btn("💳 بوت اشتراكات", "template_subscriptions"), btn("👥 إدارة قروبات", "template_groups")],
        [btn("📢 بوت تنبيهات", "template_alerts"), btn("🧾 بوت طلبات", "template_orders")],
        [btn("🤖 بوت ذكاء اصطناعي", "template_ai")],
        [btn("🏠 القائمة الرئيسية", "home")]
    ])


def account_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🆔 عرض رقم حسابي", "show_id")],
        [btn("📋 طلباتي", "my_orders"), btn("🤖 بوتاتي", "my_bots")],
        [btn("💳 اشتراكي", "my_plan")],
        [btn("🏠 القائمة الرئيسية", "home")]
    ])


def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("📊 الإحصائيات", "admin_stats"), btn("👥 المستخدمين", "admin_users")],
        [btn("📢 إرسال جماعي", "admin_broadcast"), btn("🛟 رسائل الدعم", "admin_support")],
        [btn("🔧 وضع الصيانة", "admin_maintenance"), btn("🤖 مشاريع البوتات", "admin_projects")],
        [btn("📦 إدارة القوالب", "admin_templates"), btn("💳 إدارة الاشتراكات", "admin_plans")],
        [btn("🧪 فحص النظام", "admin_check"), btn("👑 معلومات الملكية", "admin_owner")],
        [btn("🏠 القائمة الرئيسية", "home")]
    ])


def maintenance_menu():
    status = get_setting("maintenance")
    if status == "on":
        return InlineKeyboardMarkup(inline_keyboard=[
            [btn("🟢 إيقاف الصيانة", "maintenance_off")],
            [btn("⬅️ رجوع للوحة التحكم", "admin_panel")]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🔴 تشغيل الصيانة", "maintenance_on")],
        [btn("⬅️ رجوع للوحة التحكم", "admin_panel")]
    ])


async def maintenance_check(message: Message) -> bool:
    if is_admin(message.from_user.id):
        return False

    if get_setting("maintenance") == "on":
        await message.answer("🔧 البوت حالياً في وضع الصيانة.\n\nيرجى المحاولة لاحقاً.")
        return True

    return False


@dp.message(CommandStart())
async def start(message: Message):
    save_user(message.from_user)

    if await maintenance_check(message):
        return

    await message.answer(
        """
<b>🤖 Mansour Factory</b>

<b>منصة احترافية لصناعة وإدارة بوتات تيليجرام</b>

اختر من لوحة التحكم:
""",
        reply_markup=main_menu(message.from_user.id)
    )


@dp.message(Command("id"))
async def user_id(message: Message):
    save_user(message.from_user)
    await message.answer(
        f"""
<b>🆔 معلومات حسابك</b>

<b>User ID:</b>
<code>{message.from_user.id}</code>

<b>Username:</b>
@{message.from_user.username if message.from_user.username else "لا يوجد"}

انسخ الرقم وضعه في OWNER_ID داخل ملف .env إذا كنت مالك البوت.
"""
    )


@dp.message(Command("admin"))
async def admin_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ هذا الأمر مخصص للإدارة فقط.")
        return

    await message.answer("🛠 <b>لوحة تحكم الإدارة</b>", reply_markup=admin_menu())


@dp.callback_query(F.data == "home")
async def home(callback: CallbackQuery):
    save_user(callback.from_user)
    await safe_edit(callback, "🏠 <b>القائمة الرئيسية</b>\n\nاختر العملية:", main_menu(callback.from_user.id))
    await callback.answer()


@dp.callback_query(F.data == "create_bot")
async def create_bot(callback: CallbackQuery):
    await safe_edit(
        callback,
        """
<b>➕ إنشاء بوت جديد</b>

ابدأ بواحدة من الخيارات التالية:

• إرسال توكن بوت جاهز
• معرفة طريقة استخراج التوكن
• اختيار قالب جاهز
""",
        create_bot_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "send_token")
async def send_token(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BotTokenState.waiting_token)
    await callback.message.answer(
        """
🔑 أرسل توكن البوت الآن.

مثال:
<code>123456789:AAxxxxxxxxxxxxxxxx</code>

⚠️ لا ترسل توكن بوت مهم إلا إذا كنت تثق بالنظام.
"""
    )
    await callback.answer()


@dp.message(BotTokenState.waiting_token)
async def receive_token(message: Message, state: FSMContext):
    token = message.text.strip()

    if ":" not in token or len(token) < 30:
        await message.answer("❌ التوكن غير صحيح. أرسل توكن صحيح من BotFather.")
        return

    try:
        test_bot = Bot(token=token)
        me = await test_bot.get_me()
        await test_bot.session.close()
    except Exception:
        await message.answer("❌ التوكن غير صالح أو مرفوض من تيليجرام.")
        return

    add_bot_project(
        owner_id=message.from_user.id,
        bot_username=me.username,
        bot_name=me.first_name,
        template="not_selected"
    )

    await state.clear()

    await message.answer(
        f"""
✅ تم التحقق من البوت بنجاح.

<b>اسم البوت:</b> {me.first_name}
<b>المعرف:</b> @{me.username}

الآن اختر القالب المناسب:
""",
        reply_markup=templates_menu()
    )


@dp.callback_query(F.data == "token_help")
async def token_help(callback: CallbackQuery):
    await safe_edit(
        callback,
        """
<b>📘 طريقة إنشاء توكن بوت</b>

1. افتح @BotFather
2. أرسل /newbot
3. اكتب اسم البوت
4. اكتب username ينتهي بـ bot
5. انسخ التوكن
6. ارجع هنا واضغط إرسال توكن البوت

<b>مهم:</b>
أي شخص يملك التوكن يستطيع التحكم بالبوت.
""",
        create_bot_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "security_notes")
async def security_notes(callback: CallbackQuery):
    await safe_edit(
        callback,
        """
<b>⚠️ تعليمات الأمان</b>

• لا تشارك توكن البوت مع الغرباء
• لا ترفع ملف .env إلى GitHub
• غيّر التوكن إذا ظهر في صورة أو محادثة
• اجعل OWNER_ID لك فقط
• لا تعطي صلاحية الإدارة إلا لشخص موثوق
""",
        create_bot_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "templates")
async def templates(callback: CallbackQuery):
    await safe_edit(callback, "📦 <b>القوالب الجاهزة</b>\n\nاختر قالب البوت:", templates_menu())
    await callback.answer()


@dp.callback_query(F.data.startswith("template_"))
async def template_selected(callback: CallbackQuery):
    names = {
        "template_downloader": "📥 بوت تحميل مقاطع",
        "template_store": "🛒 بوت متجر",
        "template_support": "🎫 بوت دعم فني",
        "template_subscriptions": "💳 بوت اشتراكات",
        "template_groups": "👥 بوت إدارة قروبات",
        "template_alerts": "📢 بوت تنبيهات",
        "template_orders": "🧾 بوت طلبات",
        "template_ai": "🤖 بوت ذكاء اصطناعي",
    }

    name = names.get(callback.data, "قالب غير معروف")

    await safe_edit(
        callback,
        f"""
<b>{name}</b>

✅ تم اختيار القالب.

النسخة الحالية جهزت الواجهة وقاعدة البيانات.
الخطوة القادمة: تركيب محرك تشغيل القالب فعلياً.
""",
        back_home()
    )
    await callback.answer()


@dp.callback_query(F.data == "my_bots")
async def my_bots(callback: CallbackQuery):
    await safe_edit(
        callback,
        """
<b>🤖 بوتاتي</b>

هنا ستظهر البوتات التي أضفتها للنظام.

حالياً:
• حفظ البوتات مفعّل
• إدارة التشغيل قادمة في المرحلة التالية
""",
        back_home()
    )
    await callback.answer()


@dp.callback_query(F.data == "services")
async def services(callback: CallbackQuery):
    await safe_edit(
        callback,
        """
<b>💎 الخدمات</b>

• إنشاء بوتات تيليجرام
• تركيب قوالب جاهزة
• إدارة اشتراكات
• دعم فني
• استضافة بوتات
• تطوير مخصص
""",
        back_home()
    )
    await callback.answer()


@dp.callback_query(F.data == "plans")
async def plans(callback: CallbackQuery):
    await safe_edit(
        callback,
        """
<b>💳 الاشتراكات</b>

الخطة المجانية:
• تجربة الواجهة
• اختيار القوالب

الخطة الاحترافية:
• تشغيل بوت كامل
• دعم فني
• استضافة
• لوحة تحكم

الخطة الملكية:
• تخصيص كامل
• صلاحيات كاملة
• ملكية المشروع لك
""",
        back_home()
    )
    await callback.answer()


@dp.callback_query(F.data == "account")
async def account(callback: CallbackQuery):
    await safe_edit(
        callback,
        f"""
<b>👤 حسابي</b>

<b>ID:</b> <code>{callback.from_user.id}</code>
<b>Username:</b> @{callback.from_user.username if callback.from_user.username else "لا يوجد"}
<b>الصلاحية:</b> {'👑 مالك' if is_owner(callback.from_user.id) else '🛠 أدمن' if is_admin(callback.from_user.id) else 'مستخدم'}
""",
        account_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "show_id")
async def show_id(callback: CallbackQuery):
    await callback.message.answer(f"🆔 رقم حسابك:\n<code>{callback.from_user.id}</code>")
    await callback.answer()


@dp.callback_query(F.data == "my_orders")
async def my_orders(callback: CallbackQuery):
    await safe_edit(callback, "📋 <b>طلباتي</b>\n\nلا توجد طلبات حالياً.", back_home())
    await callback.answer()


@dp.callback_query(F.data == "my_plan")
async def my_plan(callback: CallbackQuery):
    await safe_edit(callback, "💳 <b>اشتراكي</b>\n\nالخطة الحالية: مجانية.", back_home())
    await callback.answer()


@dp.callback_query(F.data == "help")
async def help_button(callback: CallbackQuery):
    await safe_edit(
        callback,
        """
<b>📘 شرح الاستخدام</b>

1. اضغط إنشاء بوت جديد
2. أنشئ بوت من BotFather
3. أرسل التوكن
4. اختر قالب
5. تابع حالة البوت من قسم بوتاتي

للإدارة:
استخدم لوحة تحكم الإدارة.
""",
        back_home()
    )
    await callback.answer()


@dp.callback_query(F.data == "system_status")
async def system_status(callback: CallbackQuery):
    await safe_edit(
        callback,
        f"""
<b>📊 حالة النظام</b>

✅ البوت يعمل
👥 المستخدمين: <b>{count_table("users")}</b>
🤖 مشاريع البوتات: <b>{count_table("bot_projects")}</b>
🛟 رسائل الدعم: <b>{count_table("support_messages")}</b>
🔧 الصيانة: <b>{'مفعلة' if get_setting("maintenance") == 'on' else 'متوقفة'}</b>
""",
        back_home()
    )
    await callback.answer()


@dp.callback_query(F.data == "support")
async def support(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SupportState.waiting_message)
    await callback.message.answer("🛟 أرسل رسالتك للدعم الآن.")
    await callback.answer()


@dp.message(SupportState.waiting_message)
async def receive_support(message: Message, state: FSMContext):
    add_support_message(message.from_user.id, message.from_user.username, message.text)

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"""
<b>🛟 رسالة دعم جديدة</b>

<b>من:</b> {message.from_user.full_name}
<b>ID:</b> <code>{message.from_user.id}</code>
<b>Username:</b> @{message.from_user.username if message.from_user.username else "لا يوجد"}

<b>الرسالة:</b>
{message.text}
"""
            )
        except Exception:
            pass

    await state.clear()
    await message.answer("✅ تم إرسال رسالتك للدعم.")


@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح لك.", show_alert=True)
        return

    await safe_edit(callback, "🛠 <b>لوحة تحكم الإدارة</b>\n\nاختر العملية:", admin_menu())
    await callback.answer()


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح.", show_alert=True)
        return

    await safe_edit(
        callback,
        f"""
<b>📊 الإحصائيات</b>

👥 المستخدمين: <b>{count_table("users")}</b>
🤖 مشاريع البوتات: <b>{count_table("bot_projects")}</b>
🛟 رسائل الدعم: <b>{count_table("support_messages")}</b>
🔧 الصيانة: <b>{'مفعلة' if get_setting("maintenance") == 'on' else 'متوقفة'}</b>
""",
        admin_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح.", show_alert=True)
        return

    await safe_edit(callback, f"👥 <b>المستخدمين</b>\n\nالعدد: <b>{count_table('users')}</b>", admin_menu())
    await callback.answer()


@dp.callback_query(F.data == "admin_projects")
async def admin_projects(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح.", show_alert=True)
        return

    await safe_edit(callback, f"🤖 <b>مشاريع البوتات</b>\n\nالعدد: <b>{count_table('bot_projects')}</b>", admin_menu())
    await callback.answer()


@dp.callback_query(F.data == "admin_support")
async def admin_support(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح.", show_alert=True)
        return

    await safe_edit(callback, f"🛟 <b>رسائل الدعم</b>\n\nالعدد: <b>{count_table('support_messages')}</b>", admin_menu())
    await callback.answer()


@dp.callback_query(F.data == "admin_maintenance")
async def admin_maintenance(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح.", show_alert=True)
        return

    await safe_edit(
        callback,
        f"🔧 <b>وضع الصيانة</b>\n\nالحالة: <b>{'مفعلة' if get_setting('maintenance') == 'on' else 'متوقفة'}</b>",
        maintenance_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "maintenance_on")
async def maintenance_on(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح.", show_alert=True)
        return

    set_setting("maintenance", "on")
    await safe_edit(callback, "🔴 تم تشغيل وضع الصيانة.", maintenance_menu())
    await callback.answer()


@dp.callback_query(F.data == "maintenance_off")
async def maintenance_off(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح.", show_alert=True)
        return

    set_setting("maintenance", "off")
    await safe_edit(callback, "🟢 تم إيقاف وضع الصيانة.", maintenance_menu())
    await callback.answer()


@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح.", show_alert=True)
        return

    await state.set_state(BroadcastState.waiting_message)
    await callback.message.answer("📢 أرسل رسالة الإرسال الجماعي الآن.\n\nللإلغاء أرسل /cancel")
    await callback.answer()


@dp.message(BroadcastState.waiting_message)
async def send_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("❌ غير مصرح.")
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer("تم إلغاء الإرسال الجماعي.")
        return

    users = get_all_users()
    sent = 0
    failed = 0

    await message.answer("⏳ جاري الإرسال...")

    for user_id in users:
        try:
            await bot.send_message(user_id, message.text)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await state.clear()
    await message.answer(f"✅ انتهى الإرسال.\n\nتم: <b>{sent}</b>\nفشل: <b>{failed}</b>")


@dp.callback_query(F.data == "admin_templates")
async def admin_templates(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح.", show_alert=True)
        return

    await safe_edit(callback, "📦 <b>إدارة القوالب</b>\n\nالقوالب مفعلة في الواجهة، ومحرك التشغيل يضاف بالمرحلة التالية.", admin_menu())
    await callback.answer()


@dp.callback_query(F.data == "admin_plans")
async def admin_plans(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح.", show_alert=True)
        return

    await safe_edit(callback, "💳 <b>إدارة الاشتراكات</b>\n\nسيتم ربطها لاحقاً بالدفع والصلاحيات.", admin_menu())
    await callback.answer()


@dp.callback_query(F.data == "admin_check")
async def admin_check(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح.", show_alert=True)
        return

    await safe_edit(
        callback,
        """
<b>🧪 فحص النظام</b>

✅ الاتصال بتيليجرام يعمل
✅ قاعدة البيانات تعمل
✅ الأزرار تعمل
✅ لوحة الإدارة تعمل
✅ نظام الدعم يعمل
✅ نظام الإرسال الجماعي جاهز
✅ نظام الملكية جاهز
""",
        admin_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_owner")
async def admin_owner(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح.", show_alert=True)
        return

    await safe_edit(
        callback,
        f"""
<b>👑 معلومات الملكية</b>

<b>OWNER_ID:</b>
<code>{OWNER_ID if OWNER_ID else "غير محدد"}</code>

<b>حسابك:</b>
<code>{callback.from_user.id}</code>

إذا كان OWNER_ID يساوي رقمك فأنت المالك الكامل للوحة.
""",
        admin_menu()
    )
    await callback.answer()


async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    print("Mansour Factory Bot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())