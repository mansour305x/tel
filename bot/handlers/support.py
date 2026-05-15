from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.config import BotConfig
from bot.database import add_log, add_support_message, get_support_messages
from bot.keyboards.menus import owner_menu

router = Router()


class SupportStates(StatesGroup):
    message = State()


def _owner_required(user_id: int) -> bool:
    return BotConfig().is_owner(user_id)


async def _owner_guard(callback: CallbackQuery) -> bool:
    if not _owner_required(callback.from_user.id):
        await callback.answer("❌ هذه الخاصية للمالك فقط.", show_alert=True)
        return False
    return True


@router.callback_query()
async def support_panel(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data != "support":
        return
    await state.set_state(SupportStates.message)
    await callback.answer("✅ تم فتح الدعم")
    await callback.message.answer("أرسل رسالة الدعم التي تريدها الآن.")
    await callback.message.answer("يمكنك كتابة استفسارك أو المشكلة وسأرسلها إلى الفريق.")


@router.message(SupportStates.message)
async def support_message(message: Message, state: FSMContext) -> None:
    await add_support_message(message.from_user.id, message.from_user.username or "", message.text or "")
    await add_log("INFO", f"رسالة دعم من {message.from_user.id}")
    await message.answer("✅ تم استلام رسالتك وسيتم الرد عليها قريبًا.")
    await state.clear()


@router.callback_query()
async def owner_support_messages(callback: CallbackQuery) -> None:
    if callback.data != "owner_support_messages":
        return
    if not await _owner_guard(callback):
        return
    rows = await get_support_messages()
    if not rows:
        await callback.answer("⚠️ لا توجد رسائل دعم")
        await callback.message.answer("لا توجد رسائل دعم جديدة.", reply_markup=owner_menu())
        return
    lines = ["<b>🛟 سجل دعم النظام</b>\n"]
    for row in rows[:10]:
        lines.append(f"<b>#{row['id']}</b> من <code>{row['username'] or row['user_id']}</code>\n{row['message']}\n{row['created_at']}\n")
    await callback.answer("✅ تم عرض سجل الدعم")
    await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=owner_menu())
