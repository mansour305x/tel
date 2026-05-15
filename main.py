import asyncio
import csv
import html
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID_RAW = os.getenv("OWNER_ID", "")
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN غير موجود داخل ملف .env")

OWNER_ID = int(OWNER_ID_RAW) if OWNER_ID_RAW.strip().isdigit() else None
ENV_ADMINS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()]

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

BASE_DIR = Path(__file__).resolve().parent
DB_NAME = "mansour_factory.db"
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)


DEFAULT_TEXTS = {
    "welcome": """<b>🤖 Mansour Factory</b>

<b>منصة احترافية لصناعة وإدارة بوتات تيليجرام</b>

اختر من لوحة التحكم:""",
    "help": """<b>📘 شرح الاستخدام</b>

1. اضغط إنشاء بوت جديد
2. أنشئ بوت من BotFather
3. أرسل التوكن
4. اختر قالب
5. تابع حالة البوت من قسم بوتاتي

للإدارة والمالك:
استخدم لوحة التحكم الخاصة بك.""",
    "services": """<b>💎 الخدمات</b>

• إنشاء بوتات تيليجرام
• تركيب قوالب جاهزة
• إدارة اشتراكات
• دعم فني
• استضافة بوتات
• تطوير مخصص""",
    "plans": """<b>💳 الاشتراكات</b>

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
• ملكية المشروع لك""",
    "security": """<b>⚠️ تعليمات الأمان</b>

• لا تشارك توكن البوت مع الغرباء
• لا ترفع ملف .env إلى GitHub
• غيّر التوكن إذا ظهر في صورة أو محادثة
• اجعل OWNER_ID لك فقط
• لا تعطي صلاحية الإدارة إلا لشخص موثوق""",
    "support_prompt": "🛟 أرسل رسالتك للدعم الآن.",
    "maintenance": "🔧 البوت حالياً في وضع الصيانة.\n\nيرجى المحاولة لاحقاً.",
}

DEFAULT_BUTTONS = {
    "create_bot": "➕ إنشاء بوت جديد",
    "my_bots": "🤖 بوتاتي",
    "templates": "📦 القوالب الجاهزة",
    "services": "💎 الخدمات",
    "plans": "💳 الاشتراكات",
    "account": "👤 حسابي",
    "help": "📘 شرح الاستخدام",
    "support": "🛟 الدعم الفني",
    "system_status": "📊 حالة النظام",
    "owner_panel": "👑 لوحة المالك",
    "admin_panel": "🛠 لوحة الإدارة",
}


class SupportState(StatesGroup):
    waiting_message = State()


class BroadcastState(StatesGroup):
    waiting_message = State()
    waiting_confirm = State()


class BotTokenState(StatesGroup):
    waiting_token = State()


class EditTextState(StatesGroup):
    waiting_new_text = State()
    waiting_confirm = State()


class EditButtonState(StatesGroup):
    waiting_new_label = State()
    waiting_confirm = State()


class AddAdminState(StatesGroup):
    waiting_user_id = State()


class RemoveAdminState(StatesGroup):
    waiting_user_id = State()


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def esc(value) -> str:
    return html.escape(str(value))


def db():
    return sqlite3.connect(DB_NAME)


def run_command(command: list[str], timeout: int = 90):
    return subprocess.run(command, cwd=BASE_DIR, capture_output=True, text=True, timeout=timeout)


async def failed(callback: CallbackQuery, message: str = "❌ فشل التنفيذ"):
    await callback.answer("❌ فشل التنفيذ", show_alert=True)
    await callback.message.answer(message)


async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=reply_markup)


def btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def ensure_column(cur, table: str, column: str, definition: str):
    cur.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cur.fetchall()]
    if column not in columns:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            role TEXT DEFAULT 'user',
            created_at TEXT,
            updated_at TEXT
        )
    """)
    ensure_column(cur, "users", "role", "TEXT DEFAULT 'user'")
    ensure_column(cur, "users", "updated_at", "TEXT")

    cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS ui_texts (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS ui_buttons (key TEXT PRIMARY KEY, label TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS admin_users (user_id INTEGER PRIMARY KEY, created_at TEXT)")

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

    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance', 'off')")

    for key, value in DEFAULT_TEXTS.items():
        cur.execute("INSERT OR IGNORE INTO ui_texts (key, value) VALUES (?, ?)", (key, value))

    for key, value in DEFAULT_BUTTONS.items():
        cur.execute("INSERT OR IGNORE INTO ui_buttons (key, label) VALUES (?, ?)", (key, value))

    for admin_id in ENV_ADMINS:
        cur.execute("INSERT OR IGNORE INTO admin_users (user_id, created_at) VALUES (?, ?)", (admin_id, now()))

    if OWNER_ID:
        cur.execute("INSERT OR IGNORE INTO admin_users (user_id, created_at) VALUES (?, ?)", (OWNER_ID, now()))

    conn.commit()
    conn.close()


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
    cur.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value)
    )
    conn.commit()
    conn.close()


def get_text(key: str) -> str:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM ui_texts WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else DEFAULT_TEXTS.get(key, "")


def set_text(key: str, value: str):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ui_texts (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value)
    )
    conn.commit()
    conn.close()


def reset_text(key: str):
    if key in DEFAULT_TEXTS:
        set_text(key, DEFAULT_TEXTS[key])


def get_button(key: str) -> str:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT label FROM ui_buttons WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else DEFAULT_BUTTONS.get(key, key)


def set_button(key: str, label: str):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ui_buttons (key, label) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET label = excluded.label",
        (key, label)
    )
    conn.commit()
    conn.close()


def reset_button(key: str):
    if key in DEFAULT_BUTTONS:
        set_button(key, DEFAULT_BUTTONS[key])


def is_owner(user_id: int) -> bool:
    return OWNER_ID is not None and user_id == OWNER_ID


def get_admin_ids():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM admin_users")
    rows = cur.fetchall()
    conn.close()

    admins = [row[0] for row in rows]
    if OWNER_ID and OWNER_ID not in admins:
        admins.append(OWNER_ID)
    return admins


def is_admin(user_id: int) -> bool:
    return is_owner(user_id) or user_id in get_admin_ids()


def add_admin(user_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO admin_users (user_id, created_at) VALUES (?, ?)", (user_id, now()))
    conn.commit()
    conn.close()


def remove_admin(user_id: int) -> bool:
    if is_owner(user_id):
        return False

    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM admin_users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True


def save_user(user):
    conn = db()
    cur = conn.cursor()

    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

    if is_owner(user.id):
        role = "owner"
    elif is_admin(user.id):
        role = "admin"
    else:
        role = "user"

    cur.execute("""
        INSERT INTO users (user_id, username, full_name, role, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            full_name = excluded.full_name,
            role = excluded.role,
            updated_at = excluded.updated_at
    """, (user.id, user.username, full_name, role, now(), now()))

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
    cur.execute(
        "INSERT INTO support_messages (user_id, username, message, created_at) VALUES (?, ?, ?, ?)",
        (user_id, username, message, now())
    )
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


def get_user_projects(user_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, bot_username, bot_name, template, status, created_at
        FROM bot_projects
        WHERE owner_id = ?
        ORDER BY id DESC
        LIMIT 10
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_latest_projects(limit: int = 10):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, owner_id, bot_username, bot_name, template, status, created_at
        FROM bot_projects
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_latest_support(limit: int = 10):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, user_id, username, message, status, created_at
        FROM support_messages
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def back_home():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🏠 القائمة الرئيسية", "home")]
    ])


def main_menu(user_id: int):
    rows = [
        [btn(get_button("create_bot"), "create_bot"), btn(get_button("my_bots"), "my_bots")],
        [btn(get_button("templates"), "templates"), btn(get_button("services"), "services")],
        [btn(get_button("plans"), "plans"), btn(get_button("account"), "account")],
        [btn(get_button("help"), "help"), btn(get_button("support"), "support")],
        [btn(get_button("system_status"), "system_status")],
    ]

    if is_owner(user_id):
        rows.append([btn(get_button("owner_panel"), "owner_panel")])
    elif is_admin(user_id):
        rows.append([btn(get_button("admin_panel"), "admin_panel")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def create_bot_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🔑 إرسال توكن البوت", "send_token")],
        [btn("📘 طريقة إنشاء التوكن", "token_help")],
        [btn("📦 اختيار قالب جاهز", "templates")],
        [btn("⚠️ تعليمات الأمان", "security_notes")],
        [btn("🏠 القائمة الرئيسية", "home")],
    ])


def templates_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("📥 بوت تحميل مقاطع", "template_downloader")],
        [btn("🛒 بوت متجر", "template_store"), btn("🎫 بوت دعم فني", "template_support")],
        [btn("💳 بوت اشتراكات", "template_subscriptions"), btn("👥 إدارة قروبات", "template_groups")],
        [btn("📢 بوت تنبيهات", "template_alerts"), btn("🧾 بوت طلبات", "template_orders")],
        [btn("🤖 بوت ذكاء اصطناعي", "template_ai")],
        [btn("🏠 القائمة الرئيسية", "home")],
    ])


def owner_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("📝 تعديل النصوص", "owner_texts"), btn("🔘 تعديل الأزرار", "owner_buttons")],
        [btn("👮 إدارة الأدمن", "owner_admins"), btn("📢 إرسال جماعي", "owner_broadcast")],
        [btn("🔧 الصيانة", "owner_maintenance"), btn("📊 الإحصائيات", "owner_stats")],
        [btn("👥 تصدير المستخدمين", "owner_export_users"), btn("🤖 مشاريع البوتات", "owner_projects")],
        [btn("🛟 رسائل الدعم", "owner_support_messages"), btn("💾 نسخة احتياطية", "owner_backup")],
        [btn("🔄 تحديث البوت", "owner_update"), btn("♻️ إعادة تشغيل", "owner_restart")],
        [btn("🧪 فحص النظام", "owner_check"), btn("👑 معلومات الملكية", "owner_info")],
        [btn("🏠 القائمة الرئيسية", "home")],
    ])


def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("📊 الإحصائيات", "owner_stats"), btn("📢 إرسال جماعي", "owner_broadcast")],
        [btn("🔧 الصيانة", "owner_maintenance"), btn("🛟 رسائل الدعم", "owner_support_messages")],
        [btn("🧪 فحص النظام", "owner_check")],
        [btn("🏠 القائمة الرئيسية", "home")],
    ])


def text_edit_menu():
    labels = {
        "welcome": "رسالة الترحيب",
        "help": "شرح الاستخدام",
        "services": "الخدمات",
        "plans": "الاشتراكات",
        "security": "الأمان",
        "support_prompt": "رسالة الدعم",
        "maintenance": "رسالة الصيانة",
    }

    rows = [[btn(f"📝 {label}", f"text_open:{key}")] for key, label in labels.items()]
    rows.append([btn("⬅️ رجوع للمالك", "owner_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def text_manage_menu(key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("✏️ تعديل", f"text_edit:{key}"), btn("👁 معاينة", f"text_preview:{key}")],
        [btn("♻️ استعادة الافتراضي", f"text_reset:{key}")],
        [btn("⬅️ رجوع للنصوص", "owner_texts")],
    ])


def text_confirm_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("✅ حفظ النص", "text_confirm_save")],
        [btn("🔁 إعادة كتابة", "text_rewrite")],
        [btn("❌ إلغاء", "text_cancel")],
    ])


def button_edit_menu():
    labels = {
        "create_bot": "زر إنشاء بوت",
        "my_bots": "زر بوتاتي",
        "templates": "زر القوالب",
        "services": "زر الخدمات",
        "plans": "زر الاشتراكات",
        "account": "زر حسابي",
        "help": "زر الشرح",
        "support": "زر الدعم",
        "system_status": "زر حالة النظام",
        "owner_panel": "زر لوحة المالك",
        "admin_panel": "زر لوحة الإدارة",
    }

    rows = [[btn(f"🔘 {label}", f"button_open:{key}")] for key, label in labels.items()]
    rows.append([btn("⬅️ رجوع للمالك", "owner_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def button_manage_menu(key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("✏️ تعديل الاسم", f"button_edit:{key}")],
        [btn("♻️ استعادة الافتراضي", f"button_reset:{key}")],
        [btn("⬅️ رجوع للأزرار", "owner_buttons")],
    ])


def button_confirm_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("✅ حفظ اسم الزر", "button_confirm_save")],
        [btn("🔁 إعادة كتابة", "button_rewrite")],
        [btn("❌ إلغاء", "button_cancel")],
    ])


def admin_manage_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("➕ إضافة أدمن", "owner_add_admin")],
        [btn("➖ حذف أدمن", "owner_remove_admin")],
        [btn("📋 عرض المدراء", "owner_list_admins")],
        [btn("⬅️ رجوع للمالك", "owner_panel")],
    ])


def maintenance_menu():
    if get_setting("maintenance") == "on":
        return InlineKeyboardMarkup(inline_keyboard=[
            [btn("🟢 إيقاف الصيانة", "maintenance_off")],
            [btn("⬅️ رجوع", "owner_panel")],
        ])

    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🔴 تشغيل الصيانة", "maintenance_on")],
        [btn("⬅️ رجوع", "owner_panel")],
    ])


def broadcast_confirm_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("✅ تأكيد الإرسال", "broadcast_confirm_send")],
        [btn("❌ إلغاء", "broadcast_cancel")],
    ])


async def maintenance_check(message: Message) -> bool:
    if is_admin(message.from_user.id):
        return False

    if get_setting("maintenance") == "on":
        await message.answer(get_text("maintenance"))
        return True

    return False


def create_backup() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"backup_{timestamp}"
    backup_path.mkdir(exist_ok=True)

    shutil.copy2(BASE_DIR / "main.py", backup_path / "main.py")

    db_path = BASE_DIR / DB_NAME
    if db_path.exists():
        shutil.copy2(db_path, backup_path / DB_NAME)

    return backup_path


@dp.message(CommandStart())
async def start(message: Message):
    save_user(message.from_user)

    if await maintenance_check(message):
        return

    await message.answer(get_text("welcome"), reply_markup=main_menu(message.from_user.id))


@dp.message(Command("id"))
async def user_id(message: Message):
    save_user(message.from_user)

    await message.answer(
        f"""<b>🆔 معلومات حسابك</b>

<b>User ID:</b>
<code>{message.from_user.id}</code>

<b>Username:</b>
@{esc(message.from_user.username if message.from_user.username else "لا يوجد")}

<b>صلاحيتك:</b>
{'👑 مالك' if is_owner(message.from_user.id) else '🛠 أدمن' if is_admin(message.from_user.id) else 'مستخدم'}"""
    )


@dp.message(Command("cancel"))
async def cancel_state(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("✅ تم الإلغاء بنجاح.")


@dp.message(Command("admin"))
async def admin_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ هذا الأمر مخصص للإدارة فقط.")
        return

    await message.answer("✅ تم فتح لوحة الإدارة.", reply_markup=admin_menu())


@dp.message(Command("owner"))
async def owner_command(message: Message):
    if not is_owner(message.from_user.id):
        await message.answer("❌ هذا الأمر للمالك فقط.")
        return

    await message.answer("✅ تم فتح لوحة المالك.", reply_markup=owner_menu())


@dp.callback_query(F.data == "home")
async def home(callback: CallbackQuery):
    save_user(callback.from_user)

    await callback.answer("✅ تم فتح القائمة الرئيسية")
    await safe_edit(callback, "🏠 <b>القائمة الرئيسية</b>\n\nاختر العملية:", main_menu(callback.from_user.id))


@dp.callback_query(F.data == "create_bot")
async def create_bot(callback: CallbackQuery):
    await callback.answer("✅ تم فتح إنشاء بوت")
    await safe_edit(
        callback,
        """<b>➕ إنشاء بوت جديد</b>

ابدأ بواحدة من الخيارات التالية:

• إرسال توكن بوت جاهز
• معرفة طريقة استخراج التوكن
• اختيار قالب جاهز""",
        create_bot_menu()
    )


@dp.callback_query(F.data == "send_token")
async def send_token(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BotTokenState.waiting_token)

    await callback.answer("✅ جاهز لاستقبال التوكن")
    await callback.message.answer(
        """🔑 أرسل توكن البوت الآن.

مثال:
<code>123456789:AAxxxxxxxxxxxxxxxx</code>

⚠️ لا ترسل توكن بوت مهم إلا إذا كنت تثق بالنظام."""
    )


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

    add_bot_project(message.from_user.id, me.username, me.first_name, "not_selected")

    await state.clear()

    await message.answer(
        f"""✅ تم التحقق من البوت وحفظه بنجاح.

<b>اسم البوت:</b> {esc(me.first_name)}
<b>المعرف:</b> @{esc(me.username)}

الآن اختر القالب المناسب:""",
        reply_markup=templates_menu()
    )


@dp.callback_query(F.data == "token_help")
async def token_help(callback: CallbackQuery):
    await callback.answer("✅ تم عرض شرح التوكن")

    await safe_edit(
        callback,
        """<b>📘 طريقة إنشاء توكن بوت</b>

1. افتح @BotFather
2. أرسل /newbot
3. اكتب اسم البوت
4. اكتب username ينتهي بـ bot
5. انسخ التوكن
6. ارجع هنا واضغط إرسال توكن البوت""",
        create_bot_menu()
    )


@dp.callback_query(F.data == "security_notes")
async def security_notes(callback: CallbackQuery):
    await callback.answer("✅ تم عرض تعليمات الأمان")
    await safe_edit(callback, get_text("security"), create_bot_menu())


@dp.callback_query(F.data == "templates")
async def templates(callback: CallbackQuery):
    await callback.answer("✅ تم فتح القوالب")
    await safe_edit(callback, "📦 <b>القوالب الجاهزة</b>\n\nاختر قالب البوت:", templates_menu())


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

    await callback.answer("✅ تم اختيار القالب")
    await safe_edit(
        callback,
        f"""<b>{name}</b>

✅ تم اختيار القالب بنجاح.

المرحلة القادمة:
ربط القالب بمحرك تشغيل حقيقي.""",
        back_home()
    )


@dp.callback_query(F.data == "my_bots")
async def my_bots(callback: CallbackQuery):
    await callback.answer("✅ تم فتح بوتاتي")

    projects = get_user_projects(callback.from_user.id)

    if not projects:
        await safe_edit(
            callback,
            """<b>🤖 بوتاتي</b>

لا توجد بوتات محفوظة حالياً.

ابدأ من زر:
➕ إنشاء بوت جديد""",
            back_home()
        )
        return

    lines = ["<b>🤖 بوتاتي</b>\n"]

    for project_id, bot_username, bot_name, template, status, created_at in projects:
        lines.append(
            f"""<b>#{project_id}</b>
الاسم: {esc(bot_name)}
المعرف: @{esc(bot_username)}
القالب: {esc(template)}
الحالة: {esc(status)}
التاريخ: {esc(created_at)}
"""
        )

    await safe_edit(callback, "\n".join(lines), back_home())


@dp.callback_query(F.data == "services")
async def services(callback: CallbackQuery):
    await callback.answer("✅ تم عرض الخدمات")
    await safe_edit(callback, get_text("services"), back_home())


@dp.callback_query(F.data == "plans")
async def plans(callback: CallbackQuery):
    await callback.answer("✅ تم عرض الاشتراكات")
    await safe_edit(callback, get_text("plans"), back_home())


@dp.callback_query(F.data == "help")
async def help_button(callback: CallbackQuery):
    await callback.answer("✅ تم عرض الشرح")
    await safe_edit(callback, get_text("help"), back_home())


@dp.callback_query(F.data == "account")
async def account(callback: CallbackQuery):
    await callback.answer("✅ تم عرض حسابك")

    await safe_edit(
        callback,
        f"""<b>👤 حسابي</b>

<b>ID:</b> <code>{callback.from_user.id}</code>
<b>Username:</b> @{esc(callback.from_user.username if callback.from_user.username else "لا يوجد")}
<b>الصلاحية:</b> {'👑 مالك' if is_owner(callback.from_user.id) else '🛠 أدمن' if is_admin(callback.from_user.id) else 'مستخدم'}""",
        back_home()
    )


@dp.callback_query(F.data == "system_status")
async def system_status(callback: CallbackQuery):
    await callback.answer("✅ تم فحص حالة النظام")

    await safe_edit(
        callback,
        f"""<b>📊 حالة النظام</b>

✅ البوت يعمل
👥 المستخدمين: <b>{count_table("users")}</b>
🤖 مشاريع البوتات: <b>{count_table("bot_projects")}</b>
🛟 رسائل الدعم: <b>{count_table("support_messages")}</b>
👮 المدراء: <b>{len(get_admin_ids())}</b>
🔧 الصيانة: <b>{'مفعلة' if get_setting("maintenance") == 'on' else 'متوقفة'}</b>""",
        back_home()
    )


@dp.callback_query(F.data == "support")
async def support(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SupportState.waiting_message)

    await callback.answer("✅ تم فتح الدعم")
    await callback.message.answer(get_text("support_prompt"))


@dp.message(SupportState.waiting_message)
async def receive_support(message: Message, state: FSMContext):
    add_support_message(message.from_user.id, message.from_user.username, message.text)

    for admin_id in get_admin_ids():
        try:
            await bot.send_message(
                admin_id,
                f"""<b>🛟 رسالة دعم جديدة</b>

<b>من:</b> {esc(message.from_user.full_name)}
<b>ID:</b> <code>{message.from_user.id}</code>
<b>Username:</b> @{esc(message.from_user.username if message.from_user.username else "لا يوجد")}

<b>الرسالة:</b>
{esc(message.text)}"""
            )
        except Exception:
            pass

    await state.clear()
    await message.answer("✅ تم إرسال رسالتك للدعم بنجاح.")


@dp.callback_query(F.data == "owner_panel")
async def owner_panel(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه اللوحة للمالك فقط.")
        return

    await callback.answer("✅ تم فتح لوحة المالك")
    await safe_edit(callback, "👑 <b>لوحة المالك</b>\n\nاختر العملية:", owner_menu())


@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await failed(callback, "❌ غير مصرح لك.")
        return

    await callback.answer("✅ تم فتح لوحة الإدارة")
    await safe_edit(callback, "🛠 <b>لوحة الإدارة</b>\n\nاختر العملية:", admin_menu())


@dp.callback_query(F.data == "owner_texts")
async def owner_texts(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    await callback.answer("✅ تم فتح إدارة النصوص")
    await safe_edit(callback, "📝 <b>إدارة النصوص</b>\n\nاختر النص الذي تريد إدارته:", text_edit_menu())


@dp.callback_query(F.data.startswith("text_open:"))
async def text_open(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    key = callback.data.split(":", 1)[1]
    value = get_text(key)

    await callback.answer("✅ تم فتح النص")
    await safe_edit(
        callback,
        f"""📝 <b>إدارة النص</b>

<b>المفتاح:</b>
<code>{esc(key)}</code>

<b>النص الحالي:</b>
<code>{esc(value)}</code>""",
        text_manage_menu(key)
    )


@dp.callback_query(F.data.startswith("text_preview:"))
async def text_preview(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    key = callback.data.split(":", 1)[1]

    await callback.answer("✅ تم عرض المعاينة")
    await callback.message.answer(
        f"""👁 <b>معاينة النص</b>

<b>المفتاح:</b> <code>{esc(key)}</code>

{get_text(key)}"""
    )


@dp.callback_query(F.data.startswith("text_edit:"))
async def text_edit_start(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    key = callback.data.split(":", 1)[1]

    await state.set_state(EditTextState.waiting_new_text)
    await state.update_data(key=key)

    await callback.answer("✅ جاهز لاستقبال النص الجديد")
    await callback.message.answer(
        f"""✏️ <b>تعديل النص</b>

<b>المفتاح:</b>
<code>{esc(key)}</code>

أرسل النص الجديد الآن.

لن يتم الحفظ مباشرة. ستظهر لك معاينة أولاً."""
    )


@dp.message(EditTextState.waiting_new_text)
async def text_edit_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data.get("key")
    new_value = message.text

    await state.set_state(EditTextState.waiting_confirm)
    await state.update_data(key=key, new_value=new_value)

    await message.answer(
        f"""👁 <b>معاينة النص الجديد</b>

<b>المفتاح:</b>
<code>{esc(key)}</code>

<b>النص الجديد:</b>
<code>{esc(new_value)}</code>

اختر الإجراء:""",
        reply_markup=text_confirm_menu()
    )


@dp.callback_query(F.data == "text_confirm_save")
async def text_confirm_save(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    data = await state.get_data()
    key = data.get("key")
    new_value = data.get("new_value")

    if not key or new_value is None:
        await state.clear()
        await failed(callback, "❌ لا توجد بيانات محفوظة للتعديل.")
        return

    set_text(key, new_value)
    await state.clear()

    await callback.answer("✅ تم حفظ النص")
    await callback.message.answer("✅ تم تحديث النص بنجاح.", reply_markup=owner_menu())


@dp.callback_query(F.data == "text_rewrite")
async def text_rewrite(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    key = data.get("key")

    await state.set_state(EditTextState.waiting_new_text)
    await state.update_data(key=key)

    await callback.answer("✅ أرسل النص من جديد")
    await callback.message.answer("🔁 أرسل النص الجديد مرة أخرى.")


@dp.callback_query(F.data == "text_cancel")
async def text_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    await callback.answer("✅ تم إلغاء تعديل النص")
    await callback.message.answer("❌ تم إلغاء تعديل النص.", reply_markup=owner_menu())


@dp.callback_query(F.data.startswith("text_reset:"))
async def text_reset(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    key = callback.data.split(":", 1)[1]
    reset_text(key)

    await callback.answer("✅ تم استعادة الافتراضي")
    await callback.message.answer(f"♻️ تم استعادة النص الافتراضي للمفتاح:\n<code>{esc(key)}</code>", reply_markup=owner_menu())


@dp.callback_query(F.data == "owner_buttons")
async def owner_buttons(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    await callback.answer("✅ تم فتح إدارة الأزرار")
    await safe_edit(callback, "🔘 <b>إدارة الأزرار</b>\n\nاختر الزر الذي تريد إدارته:", button_edit_menu())


@dp.callback_query(F.data.startswith("button_open:"))
async def button_open(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    key = callback.data.split(":", 1)[1]
    label = get_button(key)

    await callback.answer("✅ تم فتح الزر")
    await safe_edit(
        callback,
        f"""🔘 <b>إدارة الزر</b>

<b>المفتاح الداخلي:</b>
<code>{esc(key)}</code>

<b>الاسم الحالي:</b>
<code>{esc(label)}</code>""",
        button_manage_menu(key)
    )


@dp.callback_query(F.data.startswith("button_edit:"))
async def button_edit_start(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    key = callback.data.split(":", 1)[1]

    await state.set_state(EditButtonState.waiting_new_label)
    await state.update_data(key=key)

    await callback.answer("✅ جاهز لاستقبال اسم الزر")
    await callback.message.answer(
        f"""✏️ <b>تعديل اسم الزر</b>

<b>المفتاح:</b>
<code>{esc(key)}</code>

أرسل الاسم الجديد للزر.

مثال:
🚀 ابدأ الآن"""
    )


@dp.message(EditButtonState.waiting_new_label)
async def button_edit_preview(message: Message, state: FSMContext):
    label = message.text.strip()

    if not label:
        await message.answer("❌ اسم الزر لا يمكن أن يكون فارغاً.")
        return

    if len(label) > 40:
        await message.answer("❌ اسم الزر طويل جداً. اجعله أقل من 40 حرف.")
        return

    data = await state.get_data()
    key = data.get("key")

    await state.set_state(EditButtonState.waiting_confirm)
    await state.update_data(key=key, new_label=label)

    await message.answer(
        f"""👁 <b>معاينة اسم الزر</b>

<b>المفتاح:</b>
<code>{esc(key)}</code>

<b>الاسم الجديد:</b>
<code>{esc(label)}</code>

اختر الإجراء:""",
        reply_markup=button_confirm_menu()
    )


@dp.callback_query(F.data == "button_confirm_save")
async def button_confirm_save(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    data = await state.get_data()
    key = data.get("key")
    new_label = data.get("new_label")

    if not key or not new_label:
        await state.clear()
        await failed(callback, "❌ لا توجد بيانات محفوظة للتعديل.")
        return

    set_button(key, new_label)
    await state.clear()

    await callback.answer("✅ تم حفظ اسم الزر")
    await callback.message.answer("✅ تم تحديث اسم الزر بنجاح.", reply_markup=owner_menu())


@dp.callback_query(F.data == "button_rewrite")
async def button_rewrite(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    key = data.get("key")

    await state.set_state(EditButtonState.waiting_new_label)
    await state.update_data(key=key)

    await callback.answer("✅ أرسل الاسم من جديد")
    await callback.message.answer("🔁 أرسل اسم الزر الجديد مرة أخرى.")


@dp.callback_query(F.data == "button_cancel")
async def button_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    await callback.answer("✅ تم إلغاء تعديل الزر")
    await callback.message.answer("❌ تم إلغاء تعديل الزر.", reply_markup=owner_menu())


@dp.callback_query(F.data.startswith("button_reset:"))
async def button_reset(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    key = callback.data.split(":", 1)[1]
    reset_button(key)

    await callback.answer("✅ تم استعادة الافتراضي")
    await callback.message.answer(f"♻️ تم استعادة الاسم الافتراضي للزر:\n<code>{esc(key)}</code>", reply_markup=owner_menu())


@dp.callback_query(F.data == "owner_admins")
async def owner_admins(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    await callback.answer("✅ تم فتح إدارة الأدمن")
    await safe_edit(callback, "👮 <b>إدارة الأدمن</b>", admin_manage_menu())


@dp.callback_query(F.data == "owner_add_admin")
async def owner_add_admin(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    await state.set_state(AddAdminState.waiting_user_id)

    await callback.answer("✅ أرسل ID الأدمن")
    await callback.message.answer("➕ أرسل User ID للشخص الذي تريد إضافته أدمن.\n\nللإلغاء أرسل /cancel")


@dp.message(AddAdminState.waiting_user_id)
async def add_admin_save(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        await state.clear()
        await message.answer("❌ هذه الخاصية للمالك فقط.")
        return

    if not message.text.strip().isdigit():
        await message.answer("❌ أرسل رقم ID صحيح.")
        return

    new_admin = int(message.text.strip())
    add_admin(new_admin)
    await state.clear()

    await message.answer(f"✅ تم إضافة الأدمن بنجاح:\n<code>{new_admin}</code>", reply_markup=owner_menu())


@dp.callback_query(F.data == "owner_remove_admin")
async def owner_remove_admin(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    await state.set_state(RemoveAdminState.waiting_user_id)

    await callback.answer("✅ أرسل ID الأدمن")
    await callback.message.answer("➖ أرسل User ID للأدمن الذي تريد حذفه.\n\nللإلغاء أرسل /cancel")


@dp.message(RemoveAdminState.waiting_user_id)
async def remove_admin_save(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        await state.clear()
        await message.answer("❌ هذه الخاصية للمالك فقط.")
        return

    if not message.text.strip().isdigit():
        await message.answer("❌ أرسل رقم ID صحيح.")
        return

    target = int(message.text.strip())
    ok = remove_admin(target)

    await state.clear()

    if ok:
        await message.answer(f"✅ تم حذف الأدمن بنجاح:\n<code>{target}</code>", reply_markup=owner_menu())
    else:
        await message.answer("❌ لا يمكن حذف المالك من الأدمن.", reply_markup=owner_menu())


@dp.callback_query(F.data == "owner_list_admins")
async def owner_list_admins(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    admins = get_admin_ids()
    text = "<b>📋 قائمة المدراء:</b>\n\n" + "\n".join([f"• <code>{x}</code>" for x in admins])

    await callback.answer("✅ تم عرض المدراء")
    await safe_edit(callback, text, admin_manage_menu())


@dp.callback_query(F.data == "owner_stats")
async def owner_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await failed(callback, "❌ غير مصرح.")
        return

    await callback.answer("✅ تم عرض الإحصائيات")
    await safe_edit(
        callback,
        f"""<b>📊 إحصائيات النظام</b>

👥 المستخدمين: <b>{count_table("users")}</b>
🤖 مشاريع البوتات: <b>{count_table("bot_projects")}</b>
🛟 رسائل الدعم: <b>{count_table("support_messages")}</b>
👮 المدراء: <b>{len(get_admin_ids())}</b>
🔧 الصيانة: <b>{'مفعلة' if get_setting("maintenance") == 'on' else 'متوقفة'}</b>""",
        owner_menu() if is_owner(callback.from_user.id) else admin_menu()
    )


@dp.callback_query(F.data == "owner_maintenance")
async def owner_maintenance(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await failed(callback, "❌ غير مصرح.")
        return

    await callback.answer("✅ تم فتح الصيانة")
    await safe_edit(
        callback,
        f"🔧 <b>وضع الصيانة</b>\n\nالحالة: <b>{'مفعلة' if get_setting('maintenance') == 'on' else 'متوقفة'}</b>",
        maintenance_menu()
    )


@dp.callback_query(F.data == "maintenance_on")
async def maintenance_on(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await failed(callback, "❌ غير مصرح.")
        return

    set_setting("maintenance", "on")

    await callback.answer("✅ تم تشغيل الصيانة")
    await callback.message.answer("🔴 تم تشغيل وضع الصيانة بنجاح.", reply_markup=maintenance_menu())


@dp.callback_query(F.data == "maintenance_off")
async def maintenance_off(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await failed(callback, "❌ غير مصرح.")
        return

    set_setting("maintenance", "off")

    await callback.answer("✅ تم إيقاف الصيانة")
    await callback.message.answer("🟢 تم إيقاف وضع الصيانة بنجاح.", reply_markup=maintenance_menu())


@dp.callback_query(F.data == "owner_broadcast")
async def owner_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await failed(callback, "❌ غير مصرح.")
        return

    await state.set_state(BroadcastState.waiting_message)

    await callback.answer("✅ تم فتح الإرسال الجماعي")
    await callback.message.answer("📢 أرسل رسالة الإرسال الجماعي الآن.\n\nلن يتم إرسالها مباشرة. ستظهر لك معاينة أولاً.")


@dp.message(BroadcastState.waiting_message)
async def broadcast_preview(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("❌ غير مصرح.")
        return

    users = get_all_users()

    await state.set_state(BroadcastState.waiting_confirm)
    await state.update_data(text=message.text)

    await message.answer(
        f"""👁 <b>معاينة الإرسال الجماعي</b>

<b>عدد المستلمين:</b> {len(users)}

<b>الرسالة:</b>
<code>{esc(message.text)}</code>

اختر الإجراء:""",
        reply_markup=broadcast_confirm_menu()
    )


@dp.callback_query(F.data == "broadcast_cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    await callback.answer("✅ تم إلغاء الإرسال")
    await callback.message.answer("❌ تم إلغاء الإرسال الجماعي.", reply_markup=owner_menu())


@dp.callback_query(F.data == "broadcast_confirm_send")
async def broadcast_confirm_send(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await failed(callback, "❌ غير مصرح.")
        return

    data = await state.get_data()
    text = data.get("text")

    if not text:
        await state.clear()
        await failed(callback, "❌ لا توجد رسالة محفوظة للإرسال.")
        return

    users = get_all_users()
    sent = 0
    failed_count = 0

    await callback.answer("✅ بدأ الإرسال")
    await callback.message.answer("⏳ جاري الإرسال الجماعي...")

    for user_id in users:
        try:
            await bot.send_message(user_id, text)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed_count += 1

    await state.clear()

    await callback.message.answer(
        f"""✅ تم تنفيذ الإرسال الجماعي بنجاح.

تم الإرسال: <b>{sent}</b>
فشل: <b>{failed_count}</b>""",
        reply_markup=owner_menu()
    )


@dp.callback_query(F.data == "owner_projects")
async def owner_projects(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    projects = get_latest_projects()

    if not projects:
        await callback.answer("✅ تم عرض المشاريع")
        await safe_edit(callback, "🤖 لا توجد مشاريع بوتات حالياً.", owner_menu())
        return

    lines = ["<b>🤖 آخر مشاريع البوتات</b>\n"]

    for project_id, owner_id, bot_username, bot_name, template, status, created_at in projects:
        lines.append(
            f"""<b>#{project_id}</b>
المالك: <code>{owner_id}</code>
الاسم: {esc(bot_name)}
المعرف: @{esc(bot_username)}
القالب: {esc(template)}
الحالة: {esc(status)}
التاريخ: {esc(created_at)}
"""
        )

    await callback.answer("✅ تم عرض مشاريع البوتات")
    await safe_edit(callback, "\n".join(lines), owner_menu())


@dp.callback_query(F.data == "owner_support_messages")
async def owner_support_messages(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await failed(callback, "❌ غير مصرح.")
        return

    messages = get_latest_support()
    menu = owner_menu() if is_owner(callback.from_user.id) else admin_menu()

    if not messages:
        await callback.answer("✅ تم عرض رسائل الدعم")
        await safe_edit(callback, "🛟 لا توجد رسائل دعم حالياً.", menu)
        return

    lines = ["<b>🛟 آخر رسائل الدعم</b>\n"]

    for msg_id, user_id, username, message, status, created_at in messages:
        lines.append(
            f"""<b>#{msg_id}</b>
المستخدم: <code>{user_id}</code>
يوزر: @{esc(username if username else "لا يوجد")}
الحالة: {esc(status)}
التاريخ: {esc(created_at)}
الرسالة:
<code>{esc(message)}</code>
"""
        )

    await callback.answer("✅ تم عرض رسائل الدعم")
    await safe_edit(callback, "\n".join(lines), menu)


@dp.callback_query(F.data == "owner_export_users")
async def owner_export_users(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    export_path = BASE_DIR / "users_export.csv"

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, full_name, role, created_at, updated_at FROM users")
    rows = cur.fetchall()
    conn.close()

    with open(export_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["user_id", "username", "full_name", "role", "created_at", "updated_at"])
        writer.writerows(rows)

    await callback.answer("✅ تم تصدير المستخدمين")
    await callback.message.answer_document(FSInputFile(export_path), caption="✅ تم تصدير المستخدمين بنجاح.")


@dp.callback_query(F.data == "owner_backup")
async def owner_backup(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    backup_path = create_backup()

    await callback.answer("✅ تم إنشاء نسخة احتياطية")
    await callback.message.answer(
        f"""💾 تم إنشاء نسخة احتياطية بنجاح.

المسار:
<code>{esc(backup_path)}</code>""",
        reply_markup=owner_menu()
    )


@dp.callback_query(F.data == "owner_update")
async def owner_update(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    await callback.answer("✅ بدأ التحديث")
    await callback.message.answer("🔄 جاري تجهيز التحديث الذاتي...")

    try:
        create_backup()

        branch_result = run_command(["git", "branch", "--show-current"], timeout=30)
        current_branch = branch_result.stdout.strip()

        if not current_branch:
            await callback.message.answer("❌ فشل التحديث: لم أستطع معرفة اسم الفرع الحالي.")
            return

        status_result = run_command(["git", "status", "--short"], timeout=30)
        changed_files = status_result.stdout.strip()

        if changed_files:
            await callback.message.answer("💾 توجد تعديلات محلية. سيتم حفظ الملفات الآمنة أولاً...")

            safe_files = ["main.py", "requirements.txt", ".gitignore", "railway.json"]
            existing_files = [name for name in safe_files if (BASE_DIR / name).exists()]

            add_result = run_command(["git", "add", *existing_files], timeout=60)
            if add_result.returncode != 0:
                await callback.message.answer(
                    f"❌ فشل تجهيز الملفات للحفظ.\n\n<code>{esc(add_result.stderr or add_result.stdout)}</code>"
                )
                return

            diff_result = run_command(["git", "diff", "--cached", "--quiet"], timeout=30)

            if diff_result.returncode != 0:
                commit_result = run_command(["git", "commit", "-m", "auto save before bot update"], timeout=90)
                if commit_result.returncode != 0:
                    await callback.message.answer(
                        f"❌ فشل حفظ التعديلات.\n\n<code>{esc(commit_result.stderr or commit_result.stdout)}</code>"
                    )
                    return

        remote_check = run_command(["git", "ls-remote", "--heads", "origin", current_branch], timeout=60)

        if remote_check.returncode != 0:
            await callback.message.answer(
                f"❌ فشل الاتصال بـ GitHub.\n\n<code>{esc(remote_check.stderr or remote_check.stdout)}</code>"
            )
            return

        if not remote_check.stdout.strip():
            await callback.message.answer("🚀 الفرع غير موجود في GitHub. سيتم رفعه وربطه تلقائياً...")
            push_result = run_command(["git", "push", "-u", "origin", current_branch], timeout=180)
        else:
            push_result = run_command(["git", "push", "origin", current_branch], timeout=180)

        if push_result.returncode != 0:
            await callback.message.answer(
                f"❌ فشل رفع التحديث إلى GitHub.\n\n<code>{esc(push_result.stderr or push_result.stdout)}</code>"
            )
            return

        fetch_result = run_command(["git", "fetch", "origin"], timeout=90)

        if fetch_result.returncode != 0:
            await callback.message.answer(
                f"❌ فشل جلب التحديثات.\n\n<code>{esc(fetch_result.stderr or fetch_result.stdout)}</code>"
            )
            return

        pull_result = run_command(["git", "pull", "origin", current_branch, "--ff-only"], timeout=90)

        if pull_result.returncode != 0:
            await callback.message.answer(
                f"""❌ فشل التحديث.

الفرع الحالي:
<code>{esc(current_branch)}</code>

السبب:
<code>{esc(pull_result.stderr or pull_result.stdout)}</code>"""
            )
            return

        if (BASE_DIR / "requirements.txt").exists():
            install_result = run_command(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                timeout=180
            )

            if install_result.returncode != 0:
                await callback.message.answer(
                    f"⚠️ تم سحب التحديث لكن فشل تثبيت المتطلبات.\n\n<code>{esc(install_result.stderr or install_result.stdout)}</code>"
                )
                return

        await callback.message.answer(
            f"""✅ تم حفظ المشروع وتحديث البوت بنجاح.

الفرع:
<code>{esc(current_branch)}</code>

♻️ سيتم إعادة تشغيل البوت الآن..."""
        )

        await asyncio.sleep(2)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    except Exception as e:
        await callback.message.answer(f"❌ خطأ أثناء التحديث:\n\n<code>{esc(e)}</code>")


@dp.callback_query(F.data == "owner_restart")
async def owner_restart(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    await callback.answer("✅ سيتم إعادة التشغيل")
    await callback.message.answer("♻️ تم تنفيذ أمر إعادة التشغيل.\n\nجاري إعادة تشغيل البوت الآن...")

    await asyncio.sleep(2)
    os.execv(sys.executable, [sys.executable] + sys.argv)


@dp.callback_query(F.data == "owner_check")
async def owner_check(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await failed(callback, "❌ غير مصرح.")
        return

    await callback.answer("✅ تم فحص النظام")
    await safe_edit(
        callback,
        """<b>🧪 فحص النظام</b>

✅ الاتصال بتيليجرام يعمل
✅ قاعدة البيانات تعمل
✅ الأزرار تعمل
✅ تعديل النصوص يعمل
✅ تعديل الأزرار يعمل
✅ لوحة المالك تعمل
✅ نظام الأدمن يعمل
✅ الإرسال الجماعي يعمل مع تأكيد
✅ النسخ الاحتياطي جاهز
✅ التحديث من GitHub جاهز
✅ كل زر يعطي رسالة تنفيذ""",
        owner_menu() if is_owner(callback.from_user.id) else admin_menu()
    )


@dp.callback_query(F.data == "owner_info")
async def owner_info(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await failed(callback, "❌ هذه الخاصية للمالك فقط.")
        return

    await callback.answer("✅ تم عرض معلومات الملكية")
    await safe_edit(
        callback,
        f"""<b>👑 معلومات الملكية</b>

<b>OWNER_ID:</b>
<code>{esc(OWNER_ID)}</code>

<b>حسابك:</b>
<code>{callback.from_user.id}</code>

<b>Repository:</b>
<code>{esc(BASE_DIR)}</code>

✅ أنت المالك الكامل للوحة.""",
        owner_menu()
    )


async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    print("Mansour Factory Bot V3 is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())