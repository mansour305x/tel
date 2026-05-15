from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.database import all_templates, get_template, register_user
from bot.keyboards.menus import main_menu
from bot.config import BotConfig

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    config = BotConfig()
    await register_user(message.from_user.id, message.from_user.username or "", f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip(), "user")
    await message.answer(
        "<b>مرحبًا بك في Mansour Factory V6 Builder</b>\n\n" \
        "هذا النظام يتيح لك إدارة القوالب والأزرار من لوحة المالك مباشرة.",
        parse_mode="HTML",
        reply_markup=main_menu(config.is_owner(message.from_user.id), config.is_admin(message.from_user.id)),
    )


@router.callback_query()
async def home_callback(callback: CallbackQuery) -> None:
    if callback.data != "home":
        return
    config = BotConfig()
    await callback.answer("✅ تم العودة إلى القائمة الرئيسية")
    await callback.message.edit_text(
        "<b>القائمة الرئيسية</b>\n\nاختر الوظيفة المطلوبة:",
        parse_mode="HTML",
        reply_markup=main_menu(config.is_owner(callback.from_user.id), config.is_admin(callback.from_user.id)),
    )


@router.callback_query()
async def templates_callback(callback: CallbackQuery) -> None:
    if callback.data != "templates":
        return
    templates = await all_templates()
    if not templates:
        await callback.answer("⚠️ لا توجد قوالب متاحة");
        await callback.message.answer("لا توجد قوالب جاهزة حاليًا.", reply_markup=main_menu(True, False))
        return
    lines = ["<b>📦 القوالب الجاهزة</b>\n"]
    buttons = []
    for item in templates:
        lines.append(f"<b>{item['label']}</b> — {item['description']}\nنوع: {item['category']}\n")
        buttons.append([InlineKeyboardButton(text=item['label'], callback_data=f"template:{item['id']}")])
    buttons.append([InlineKeyboardButton(text="🏠 القائمة الرئيسية", callback_data="home")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.answer("✅ تم عرض القوالب")
    await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=keyboard)


@router.callback_query()
async def template_detail_callback(callback: CallbackQuery) -> None:
    if not (callback.data and callback.data.startswith("template:")):
        return
    template_id = int(callback.data.split(":", 1)[1])
    item = await get_template(template_id)
    if not item:
        await callback.answer("❌ القالب غير موجود")
        return
    text = (
        f"<b>{item['label']}</b>\n"
        f"<i>{item['description']}</i>\n\n"
        f"<b>نوع:</b> {item['category']}\n"
        f"<b>نشط:</b> {'نعم' if item['active'] else 'لا'}\n"
        f"<b>يظهر للمستخدمين:</b> {'نعم' if item['visible'] else 'لا'}\n"
        f"<b>يحتاج بوت فرعي:</b> {'نعم' if item['requires_subbot'] else 'لا'}"
    )
    await callback.answer("✅ تم عرض تفاصيل القالب")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu(False, False))
