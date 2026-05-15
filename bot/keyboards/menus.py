from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def quality_selection_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("أفضل جودة 🎥", f"download:{job_id}:best")],
        [btn("جودة متوسطة 📱", f"download:{job_id}:medium")],
        [btn("تحميل MP3 🎧", f"download:{job_id}:mp3")],
        [btn("إلغاء العملية ❌", f"cancel:{job_id}")],
    ])


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("زيادة عدد العمال ➕", "settings:workers:+1")],
        [btn("تقليل عدد العمال ➖", "settings:workers:-1")],
        [btn("زيادة الحد الأقصى للحجم ➕", "settings:max_size:+1")],
        [btn("تقليل الحد الأقصى للحجم ➖", "settings:max_size:-1")],
        [btn("زيادة حد الطلبات ➕", "settings:rate_limit:+1")],
        [btn("تقليل حد الطلبات ➖", "settings:rate_limit:-1")],
    ])


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("إحصائيات المستخدمين 📊", "admin:stats")],
        [btn("البث الجماعي 📨", "admin:broadcast")],
        [btn("قائمة الانتظار ⏳", "admin:queue")],
    ])


def main_menu(is_owner: bool, is_admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [btn("📦 القوالب الجاهزة", "templates")],
        [btn("📘 المساعدة", "help"), btn("🛟 الدعم", "support")],
        [btn("🔧 صانع القوالب والأزرار", "builder_panel")],
    ]
    if is_owner:
        rows.append([btn("👑 لوحة المالك", "owner_panel")])
    elif is_admin:
        rows.append([btn("🛠 لوحة الإدارة", "admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def owner_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🧩 صانع القوالب والأزرار", "builder_panel")],
        [btn("📦 إدارة القوالب", "manage_templates"), btn("🤖 بوتات العملاء", "owner_projects")],
        [btn("👥 إدارة المستخدمين", "owner_users"), btn("👮 إدارة الأدمن", "owner_admins")],
        [btn("💳 إدارة الاشتراكات", "owner_subscriptions"), btn("🛟 إدارة الدعم", "owner_support_messages")],
        [btn("📢 إرسال جماعي", "owner_broadcast"), btn("🔧 الصيانة", "owner_maintenance")],
        [btn("📊 الإحصائيات", "owner_stats"), btn("🧾 سجل العمليات", "owner_logs")],
        [btn("👥 تصدير المستخدمين", "owner_export_users")],
        [btn("💾 نسخة احتياطية", "owner_backup"), btn("🔄 تحديث البوت", "owner_update")],
        [btn("🚀 نشر التحديث", "owner_publish")],
        [btn("♻️ إعادة تشغيل", "owner_restart"), btn("🧪 فحص النظام", "owner_check")],
        [btn("👑 معلومات الملكية", "owner_info")],
        [btn("🏠 القائمة الرئيسية", "home")],
    ])


def builder_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("➕ إضافة قالب", "builder_add_template")],
        [btn("✏️ تعديل قالب", "builder_list_templates")],
        [btn("🗑 حذف قالب", "builder_list_templates")],
        [btn("➕ إضافة زر", "builder_add_button")],
        [btn("✏️ تعديل زر", "builder_list_buttons")],
        [btn("🗑 حذف زر", "builder_list_buttons")],
        [btn("👁 معاينة القوالب", "builder_list_templates")],
        [btn("👁 معاينة القائمة", "builder_list_buttons")],
        [btn("🏠 القائمة الرئيسية", "owner_panel")],
    ])


def confirm_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("✅ حفظ", "confirm_save")],
        [btn("🔁 تعديل", "confirm_edit")],
        [btn("❌ إلغاء", "confirm_cancel")],
    ])


def back_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[btn("🏠 القائمة الرئيسية", "owner_panel")]])
