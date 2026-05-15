from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import BotConfig
from bot.database import get_project, list_user_projects, update_project
from bot.keyboards.menus import owner_menu
from bot.services.child_bots import restart_child_bot, start_child_bot, stop_child_bot

router = Router()


def _owner_required(user_id: int) -> bool:
    return BotConfig().is_owner(user_id)


async def _owner_guard(callback: CallbackQuery) -> bool:
    if not _owner_required(callback.from_user.id):
        await callback.answer("❌ هذه الخاصية للمالك فقط.", show_alert=True)
        return False
    return True


@router.callback_query()
async def owner_projects(callback: CallbackQuery) -> None:
    if callback.data != "owner_projects":
        return
    if not await _owner_guard(callback):
        return
    projects = await list_user_projects(callback.from_user.id)
    if not projects:
        await callback.answer("⚠️ لم يتم تسجيل أي بوتات")
        await callback.message.edit_text("🤖 لا توجد بوتات مسجلة لديك.", reply_markup=owner_menu())
        return
    lines = ["<b>🤖 بوتاتي</b>\n"]
    buttons = []
    for project in projects:
        lines.append(
            f"<b>{project['bot_name']}</b> (@{project['bot_username']})\n" \
            f"القالب: {project['template']}\n" \
            f"الحالة: {project['status']}\n"
        )
        buttons.append([InlineKeyboardButton(text=f"▶️ إدارة {project['bot_name']}", callback_data=f"project_manage:{project['id']}")])
    buttons.append([InlineKeyboardButton(text="🏠 القائمة الرئيسية", callback_data="owner_panel")])
    await callback.answer("✅ تم عرض بوتاتك")
    await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query()
async def project_manage(callback: CallbackQuery) -> None:
    if not (callback.data and callback.data.startswith("project_manage:")):
        return
    project_id = int(callback.data.split(":", 1)[1])
    project = await get_project(project_id)
    if not project:
        await callback.answer("❌ المشروع غير موجود")
        return
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ تشغيل البوت", callback_data=f"project_action:{project_id}:start")],
        [InlineKeyboardButton(text="⏸ إيقاف البوت", callback_data=f"project_action:{project_id}:stop")],
        [InlineKeyboardButton(text="🔄 إعادة تشغيل", callback_data=f"project_action:{project_id}:restart")],
        [InlineKeyboardButton(text="📊 الإحصائيات", callback_data=f"project_action:{project_id}:stats")],
        [InlineKeyboardButton(text="🗑 حذف البوت", callback_data=f"project_action:{project_id}:delete")],
        [InlineKeyboardButton(text="🏠 القائمة الرئيسية", callback_data="owner_panel")],
    ])
    await callback.answer("✅ اختر إجراء للمشروع")
    await callback.message.edit_text(
        f"<b>{project['bot_name']}</b> (@{project['bot_username']})\n" \
        f"القالب: {project['template']}\n" \
        f"الحالة: {project['status']}",
        parse_mode="HTML",
        reply_markup=buttons,
    )


@router.callback_query()
async def project_action(callback: CallbackQuery) -> None:
    if not (callback.data and callback.data.startswith("project_action:")):
        return
    parts = callback.data.split(":")
    project_id = int(parts[1])
    action = parts[2]
    project = await get_project(project_id)
    if not project:
        await callback.answer("❌ المشروع غير موجود")
        return
    if action == "start":
        result = await start_child_bot(project_id, project["bot_token"], project["bot_username"])
    elif action == "stop":
        result = await stop_child_bot(project_id)
    elif action == "restart":
        result = await restart_child_bot(project_id, project["bot_token"], project["bot_username"])
    elif action == "delete":
        await update_project(project_id, status="deleted")
        result = "✅ تم حذف المشروع من القائمة."
    elif action == "stats":
        result = f"📊 حالة البوت الحالية: {project['status']}"
    else:
        result = "❌ إجراء غير معرّف."
    await callback.answer(result)
    await callback.message.answer(result, reply_markup=owner_menu())
