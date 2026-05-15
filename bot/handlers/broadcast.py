from aiogram import Router
from aiogram.filters import Text
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.config import BotConfig
from bot.database import add_log, get_all_user_ids
from bot.keyboards.menus import owner_menu

router = Router()


class BroadcastStates(StatesGroup):
    message = State()


def _owner_required(user_id: int) -> bool:
    return BotConfig().is_owner(user_id)


async def _owner_guard(callback: CallbackQuery) -> bool:
    if not _owner_required(callback.from_user.id):
        await callback.answer("❌ هذه الخاصية للمالك فقط.", show_alert=True)
        return False
    return True


@router.callback_query(Text("owner_broadcast"))
async def owner_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _owner_guard(callback):
        return
    await state.set_state(BroadcastStates.message)
    await callback.answer("✅ اكتب رسالة للبث الجماعي")
    await callback.message.answer("اكتب النص الذي تريد إرساله لجميع المستخدمين:")


@router.message(BroadcastStates.message)
async def broadcast_message(message: Message, state: FSMContext) -> None:
    recipients = await get_all_user_ids()
    count = 0
    for user_id in recipients:
        try:
            await message.bot.send_message(user_id, message.text or "")
            count += 1
        except Exception:
            continue
    await add_log("INFO", f"تم البث إلى {count} مستخدمين")
    await message.answer(f"✅ تم إرسال الرسالة إلى {count} مستخدمًا.", reply_markup=owner_menu())
    await state.clear()
