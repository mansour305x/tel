from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def quality_selection_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="أفضل جودة 🎥", callback_data=f"download:{job_id}:best")],
        [InlineKeyboardButton(text="جودة متوسطة 📱", callback_data=f"download:{job_id}:medium")],
        [InlineKeyboardButton(text="تحميل MP3 🎧", callback_data=f"download:{job_id}:mp3")],
        [InlineKeyboardButton(text="إلغاء العملية ❌", callback_data=f"cancel:{job_id}")],
    ])


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="زيادة عدد العمال ➕", callback_data="settings:workers:+1")],
        [InlineKeyboardButton(text="تقليل عدد العمال ➖", callback_data="settings:workers:-1")],
        [InlineKeyboardButton(text="زيادة الحد الأقصى للحجم ➕", callback_data="settings:max_size:+1")],
        [InlineKeyboardButton(text="تقليل الحد الأقصى للحجم ➖", callback_data="settings:max_size:-1")],
        [InlineKeyboardButton(text="زيادة حد الطلبات ➕", callback_data="settings:rate_limit:+1")],
        [InlineKeyboardButton(text="تقليل حد الطلبات ➖", callback_data="settings:rate_limit:-1")],
    ])


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="إحصائيات المستخدمين 📊", callback_data="admin:stats")],
        [InlineKeyboardButton(text="البث الجماعي 📨", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="قائمة الانتظار ⏳", callback_data="admin:queue")],
    ])
