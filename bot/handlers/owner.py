import csv
import os
import sys
import asyncio
from pathlib import Path
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import BotConfig
from bot.database import (
    add_log,
    all_buttons,
    all_templates,
    create_button,
    create_template,
    delete_button,
    delete_template,
    get_all_user_ids,
    get_button,
    get_setting,
    get_template,
    list_buttons,
    list_templates,
    set_setting,
    update_button,
    update_template,
)
from bot.keyboards.menus import back_home, builder_menu, confirm_menu, main_menu, owner_menu
from bot.security import validate_action_type, validate_action_value, validate_category, validate_label, validate_location, validate_template_key, validate_description
from bot.services.updater import publish_update
from bot.validator import VALID_ACTION_TYPES, VALID_CATEGORIES, VALID_LOCATIONS

router = Router()


class TemplateStates(StatesGroup):
    key = State()
    label = State()
    description = State()
    category = State()
    visible = State()
    requires_subbot = State()
    preview = State()


class ButtonStates(StatesGroup):
    name = State()
    location = State()
    action_type = State()
    action_value = State()
    position = State()
    preview = State()


def _owner_required(user_id: int) -> bool:
    config = BotConfig()
    return config.is_owner(user_id)


async def _owner_guard(callback: CallbackQuery) -> bool:
    if not _owner_required(callback.from_user.id):
        await callback.answer("❌ هذه الخاصية للمالك فقط.", show_alert=True)
        return False
    return True


@router.callback_query()
async def owner_panel(callback: CallbackQuery) -> None:
    if callback.data != "owner_panel":
        return
    if not await _owner_guard(callback):
        return
    await callback.answer("✅ تم فتح لوحة المالك")
    await callback.message.edit_text("👑 <b>لوحة المالك</b>\n\nاختر العملية:", parse_mode="HTML", reply_markup=owner_menu())


@router.callback_query()
async def builder_panel(callback: CallbackQuery) -> None:
    if callback.data != "builder_panel":
        return
    if not await _owner_guard(callback):
        return
    await callback.answer("✅ تم فتح صانع القوالب والأزرار")
    await callback.message.edit_text("🧩 <b>صانع القوالب والأزرار</b>\n\nاختر العملية:", parse_mode="HTML", reply_markup=builder_menu())


@router.callback_query()
async def builder_add_template(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data != "builder_add_template":
        return
    if not await _owner_guard(callback):
        return
    await state.set_state(TemplateStates.key)
    await callback.answer("✅ أرسل مفتاح القالب")
    await callback.message.answer("اكتب مفتاح القالب (حروف صغيرة وأرقام و_ فقط):")


@router.message(TemplateStates.key)
async def template_key(message: Message, state: FSMContext) -> None:
    try:
        key = validate_template_key(message.text or "")
        await state.update_data(key=key)
        await state.set_state(TemplateStates.label)
        await message.answer("✅ تم حفظ المفتاح. الآن اكتب اسم القالب:")
    except ValueError as exc:
        await message.answer(f"❌ {exc}")


@router.message(TemplateStates.label)
async def template_label(message: Message, state: FSMContext) -> None:
    try:
        label = validate_label(message.text or "")
        await state.update_data(label=label)
        await state.set_state(TemplateStates.description)
        await message.answer("✅ جيد. اكتب وصفًا للقالب:")
    except ValueError as exc:
        await message.answer(f"❌ {exc}")


@router.message(TemplateStates.description)
async def template_description(message: Message, state: FSMContext) -> None:
    try:
        description = validate_description(message.text or "")
        await state.update_data(description=description)
        await state.set_state(TemplateStates.category)
        await message.answer(
            "✅ الآن اختر نوع القالب من القائمة التالية:\n" + "\n".join(f"- {name}" for name in VALID_CATEGORIES)
        )
    except ValueError as exc:
        await message.answer(f"❌ {exc}")


@router.message(TemplateStates.category)
async def template_category(message: Message, state: FSMContext) -> None:
    try:
        category = validate_category(message.text or "")
        await state.update_data(category=category)
        await state.set_state(TemplateStates.visible)
        await message.answer("✅ ممتاز. هل يظهر القالب للمستخدمين؟ (نعم / لا)")
    except ValueError as exc:
        await message.answer(f"❌ {exc}")


@router.message(TemplateStates.visible)
async def template_visible(message: Message, state: FSMContext) -> None:
    answer = (message.text or "").strip().lower()
    if answer not in {"نعم", "لا"}:
        await message.answer("❌ اكتب نعم أو لا.")
        return
    visible = answer == "نعم"
    await state.update_data(visible=visible)
    await state.set_state(TemplateStates.requires_subbot)
    await message.answer("✅ هل يحتاج القالب لتوكن بوت فرعي؟ (نعم / لا)")


@router.message(TemplateStates.requires_subbot)
async def template_requires_subbot(message: Message, state: FSMContext) -> None:
    answer = (message.text or "").strip().lower()
    if answer not in {"نعم", "لا"}:
        await message.answer("❌ اكتب نعم أو لا.")
        return
    requires_subbot = answer == "نعم"
    await state.update_data(requires_subbot=requires_subbot)
    data = await state.get_data()
    preview = (
        f"<b>معاينة القالب</b>\n\n"
        f"<b>المفتاح:</b> {data['key']}\n"
        f"<b>الاسم:</b> {data['label']}\n"
        f"<b>الوصف:</b> {data['description']}\n"
        f"<b>النوع:</b> {data['category']}\n"
        f"<b>يظهر للمستخدمين:</b> {'نعم' if data['visible'] else 'لا'}\n"
        f"<b>يحتاج بوت فرعي:</b> {'نعم' if data['requires_subbot'] else 'لا'}\n"
    )
    await state.set_state(TemplateStates.preview)
    await message.answer(preview, reply_markup=confirm_menu(), parse_mode="HTML")


@router.callback_query(StateFilter(TemplateStates.preview))
async def template_confirm_save(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data != "confirm_save":
        return
    data = await state.get_data()
    try:
        await create_template(
            key=data["key"],
            label=data["label"],
            description=data["description"],
            category=data["category"],
            visible=data["visible"],
            requires_subbot=data["requires_subbot"],
        )
        await add_log("INFO", f"تم إضافة قالب {data['key']}")
        await callback.answer("✅ تم حفظ القالب بنجاح")
        await callback.message.answer("✅ تم إضافة القالب بنجاح وجاهز للنشر.", reply_markup=owner_menu())
    except Exception as exc:
        await callback.answer("❌ فشل الحفظ")
        await callback.message.answer(f"❌ فشل حفظ القالب: {exc}")
    finally:
        await state.clear()


@router.callback_query(StateFilter(TemplateStates.preview))
async def template_confirm_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data != "confirm_cancel":
        return
    await callback.answer("❌ تم إلغاء العملية")
    await callback.message.edit_text("⚠️ تم إلغاء إضافة القالب.", reply_markup=owner_menu())
    await state.clear()


@router.callback_query()
async def builder_list_templates(callback: CallbackQuery) -> None:
    if callback.data != "builder_list_templates":
        return
    if not await _owner_guard(callback):
        return
    templates = await list_templates(active_only=False)
    if not templates:
        await callback.answer("⚠️ لا توجد قوالب")
        await callback.message.answer("لا يوجد قوالب بعد.", reply_markup=builder_menu())
        return
    lines = ["<b>📦 القوالب الموجودة</b>\n"]
    buttons = []
    for item in templates:
        status = "✅" if item["active"] else "❌"
        lines.append(f"{status} <b>{item['label']}</b> — {item['key']}\n")
        buttons.append([InlineKeyboardButton(text=f"⚙️ إدارة {item['label']}", callback_data=f"template_manage:{item['id']}")])
    buttons.append([InlineKeyboardButton(text="🏠 القائمة الرئيسية", callback_data="owner_panel")])
    await callback.answer("✅ تم عرض القوالب")
    await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query()
async def template_manage(callback: CallbackQuery) -> None:
    if not (callback.data and callback.data.startswith("template_manage:")):
        return
    template_id = int(callback.data.split(":", 1)[1])
    item = await get_template(template_id)
    if not item:
        await callback.answer("❌ القالب غير موجود")
        return
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ تعديل", callback_data=f"template_edit:{item['id']}")],
        [InlineKeyboardButton(text="🗑 حذف", callback_data=f"template_delete:{item['id']}")],
        [InlineKeyboardButton(text="🔄 تبديل الحالة", callback_data=f"template_toggle:{item['id']}")],
        [InlineKeyboardButton(text="🏠 القائمة الرئيسية", callback_data="owner_panel")],
    ])
    await callback.answer("✅ اختر إجراء للقالب")
    await callback.message.edit_text(
        f"<b>{item['label']}</b> — {item['key']}\n\n{item['description']}",
        parse_mode="HTML",
        reply_markup=buttons,
    )


@router.callback_query()
async def template_delete(callback: CallbackQuery) -> None:
    if not (callback.data and callback.data.startswith("template_delete:")):
        return
    template_id = int(callback.data.split(":", 1)[1])
    await delete_template(template_id)
    await add_log("INFO", f"تم حذف قالب {template_id}")
    await callback.answer("✅ تم حذف القالب")
    await callback.message.answer("✅ تم حذف القالب بنجاح.", reply_markup=owner_menu())


@router.callback_query()
async def template_toggle(callback: CallbackQuery) -> None:
    if not (callback.data and callback.data.startswith("template_toggle:")):
        return
    template_id = int(callback.data.split(":", 1)[1])
    item = await get_template(template_id)
    if not item:
        await callback.answer("❌ القالب غير موجود")
        return
    await update_template(template_id, active=0 if item["active"] else 1)
    await add_log("INFO", f"تم تغيير حالة القالب {item['key']}")
    await callback.answer("✅ تم تحديث حالة القالب")
    await callback.message.answer("✅ تم تحديث حالة القالب بنجاح.", reply_markup=owner_menu())


@router.callback_query()
async def builder_add_button(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data != "builder_add_button":
        return
    if not await _owner_guard(callback):
        return
    await state.set_state(ButtonStates.name)
    await callback.answer("✅ اكتب اسم الزر")
    await callback.message.answer("اكتب اسم الزر مثل: 📞 تواصل معنا")


@router.message(ButtonStates.name)
async def button_name(message: Message, state: FSMContext) -> None:
    try:
        name = validate_label(message.text or "")
        await state.update_data(name=name)
        await state.set_state(ButtonStates.location)
        await message.answer("✅ جيد. اكتب مكان الزر من أحد الخيارات التالية:\n" + "\n".join(f"- {item}" for item in VALID_LOCATIONS))
    except ValueError as exc:
        await message.answer(f"❌ {exc}")


@router.message(ButtonStates.location)
async def button_location(message: Message, state: FSMContext) -> None:
    try:
        location = validate_location(message.text or "")
        await state.update_data(location=location)
        await state.set_state(ButtonStates.action_type)
        await message.answer("✅ الآن اختر نوع الوظيفة من:\n" + "\n".join(f"- {item}" for item in VALID_ACTION_TYPES))
    except ValueError as exc:
        await message.answer(f"❌ {exc}")


@router.message(ButtonStates.action_type)
async def button_action_type(message: Message, state: FSMContext) -> None:
    try:
        action_type = validate_action_type(message.text or "")
        await state.update_data(action_type=action_type)
        await state.set_state(ButtonStates.action_value)
        await message.answer("✅ اكتب محتوى الوظيفة أو الرابط، مثال: https://example.com أو نص الرسالة")
    except ValueError as exc:
        await message.answer(f"❌ {exc}")


@router.message(ButtonStates.action_value)
async def button_action_value(message: Message, state: FSMContext) -> None:
    try:
        data = await state.get_data()
        action_value = validate_action_value(data["action_type"], message.text or "")
        await state.update_data(action_value=action_value)
        await state.set_state(ButtonStates.position)
        await message.answer("✅ ما ترتيب الزر؟ اكتب رقمًا مثل 1 أو 2.")
    except ValueError as exc:
        await message.answer(f"❌ {exc}")


@router.message(ButtonStates.position)
async def button_position(message: Message, state: FSMContext) -> None:
    try:
        position = int((message.text or "").strip())
        if position < 0:
            raise ValueError("الرقم يجب أن يكون موجبًا.")
        await state.update_data(position=position)
        data = await state.get_data()
        preview = (
            f"<b>معاينة الزر</b>\n\n"
            f"<b>الاسم:</b> {data['name']}\n"
            f"<b>المكان:</b> {data['location']}\n"
            f"<b>نوع الوظيفة:</b> {data['action_type']}\n"
            f"<b>المحتوى:</b> {data['action_value']}\n"
            f"<b>الترتيب:</b> {data['position']}\n"
        )
        await state.set_state(ButtonStates.preview)
        await message.answer(preview, reply_markup=confirm_menu(), parse_mode="HTML")
    except ValueError as exc:
        await message.answer(f"❌ {exc}")


@router.callback_query(StateFilter(ButtonStates.preview))
async def button_confirm_save(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data != "confirm_save":
        return
    data = await state.get_data()
    try:
        await create_button(
            name=data["name"],
            location=data["location"],
            action_type=data["action_type"],
            action_value=data["action_value"],
            position=int(data["position"]),
        )
        await add_log("INFO", f"تم إضافة زر {data['name']}")
        await callback.answer("✅ تم حفظ الزر")
        await callback.message.answer("✅ تمت إضافة الزر الجديد وعُد إلى لوحة المالك.", reply_markup=owner_menu())
    except Exception as exc:
        await callback.answer("❌ فشل حفظ الزر")
        await callback.message.answer(f"❌ فشل حفظ الزر: {exc}")
    finally:
        await state.clear()


@router.callback_query()
async def builder_list_buttons(callback: CallbackQuery) -> None:
    if callback.data != "builder_list_buttons":
        return
    if not await _owner_guard(callback):
        return
    buttons_list = await list_buttons(active_only=False)
    if not buttons_list:
        await callback.answer("⚠️ لا توجد أزرار")
        await callback.message.answer("لا توجد أزرار بعد.", reply_markup=builder_menu())
        return
    lines = ["<b>🔘 الأزرار الموجودة</b>\n"]
    buttons = []
    for item in buttons_list:
        status = "✅" if item["active"] else "❌"
        lines.append(f"{status} <b>{item['name']}</b> — {item['location']}\n")
        buttons.append([InlineKeyboardButton(text=f"⚙️ إدارة {item['name']}", callback_data=f"button_manage:{item['id']}")])
    buttons.append([InlineKeyboardButton(text="🏠 القائمة الرئيسية", callback_data="owner_panel")])
    await callback.answer("✅ تم عرض الأزرار")
    await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query()
async def button_manage(callback: CallbackQuery) -> None:
    if not (callback.data and callback.data.startswith("button_manage:")):
        return
    button_id = int(callback.data.split(":", 1)[1])
    item = await get_button(button_id)
    if not item:
        await callback.answer("❌ الزر غير موجود")
        return
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ تعديل", callback_data=f"button_edit:{item['id']}")],
        [InlineKeyboardButton(text="🗑 حذف", callback_data=f"button_delete:{item['id']}")],
        [InlineKeyboardButton(text="🔄 تبديل الحالة", callback_data=f"button_toggle:{item['id']}")],
        [InlineKeyboardButton(text="🏠 القائمة الرئيسية", callback_data="owner_panel")],
    ])
    await callback.answer("✅ اختر إجراء للزر")
    await callback.message.edit_text(
        f"<b>{item['name']}</b> — {item['location']}\n\n{item['action_type']} : {item['action_value']}",
        parse_mode="HTML",
        reply_markup=buttons,
    )


@router.callback_query()
async def button_delete(callback: CallbackQuery) -> None:
    if not (callback.data and callback.data.startswith("button_delete:")):
        return
    button_id = int(callback.data.split(":", 1)[1])
    await delete_button(button_id)
    await add_log("INFO", f"تم حذف زر {button_id}")
    await callback.answer("✅ تم حذف الزر")
    await callback.message.answer("✅ تم حذف الزر بنجاح.", reply_markup=owner_menu())


@router.callback_query()
async def button_toggle(callback: CallbackQuery) -> None:
    if not (callback.data and callback.data.startswith("button_toggle:")):
        return
    button_id = int(callback.data.split(":", 1)[1])
    item = await get_button(button_id)
    if not item:
        await callback.answer("❌ الزر غير موجود")
        return
    await update_button(button_id, active=0 if item["active"] else 1)
    await add_log("INFO", f"تم تغيير حالة الزر {item['name']}")
    await callback.answer("✅ تم تحديث حالة الزر")
    await callback.message.answer("✅ تم تحديث حالة الزر بنجاح.", reply_markup=owner_menu())


@router.callback_query()
async def owner_info(callback: CallbackQuery) -> None:
    if callback.data != "owner_info":
        return
    if not await _owner_guard(callback):
        return
    config = BotConfig()
    await callback.answer("✅ معلومات الملكية")
    await callback.message.edit_text(
        f"<b>👑 معلومات الملكية</b>\n\n" \
        f"<b>OWNER_ID:</b> <code>{config.owner_id}</code>\n" \
        f"<b>Bot Token:</b> <code>مخفي لأمانك</code>\n" \
        f"<b>قاعدة البيانات:</b> <code>{config.database_path}</code>",
        parse_mode="HTML",
        reply_markup=owner_menu(),
    )


@router.callback_query()
async def owner_check(callback: CallbackQuery) -> None:
    if callback.data != "owner_check":
        return
    if not await _owner_guard(callback):
        return
    maintenance = await get_setting("maintenance") or "off"
    await callback.answer("✅ فحص النظام")
    await callback.message.answer(
        f"🧪 فحص النظام:\n- صيانة: {maintenance}\n- إصدار البوت: V6 Builder\n- الذاكرة مؤمنة\n",
        reply_markup=owner_menu(),
    )


@router.callback_query()
async def owner_backup(callback: CallbackQuery) -> None:
    if callback.data != "owner_backup":
        return
    if not await _owner_guard(callback):
        return
    from bot.services.backup import create_backup
    config = BotConfig()
    backup = create_backup(Path(__file__).resolve().parent.parent / "main.py", config.database_path, config.backup_dir)
    await add_log("INFO", f"تم إنشاء نسخة احتياطية {backup}")
    await callback.answer("✅ تم إنشاء نسخة احتياطية")
    await callback.message.answer(f"💾 تم حفظ النسخة الاحتياطية في:\n<code>{backup}</code>", parse_mode="HTML", reply_markup=owner_menu())


@router.callback_query()
async def owner_publish(callback: CallbackQuery) -> None:
    if callback.data != "owner_publish":
        return
    if not await _owner_guard(callback):
        return
    config = BotConfig()
    await callback.answer("🔄 جاري نشر التحديث")
    result = await publish_update(config, ["main.py", "requirements.txt", ".gitignore", "bot/main.py"])
    if not result.get("success"):
        await callback.message.answer(f"❌ فشل نشر التحديث:\n{result.get('error')}", reply_markup=owner_menu())
        return
    await add_log("INFO", "تم نشر التحديث إلى GitHub")
    await callback.message.answer(
        f"✅ تم نشر التحديث بنجاح\n- الفرع: {result.get('branch')}\n- GitHub: تم الرفع\n",
        reply_markup=owner_menu(),
    )


@router.callback_query()
async def owner_restart(callback: CallbackQuery) -> None:
    if callback.data != "owner_restart":
        return
    if not await _owner_guard(callback):
        return
    await callback.answer("♻️ جاري إعادة تشغيل البوت")
    await callback.message.answer("♻️ سيتم إعادة تشغيل البوت الآن.", reply_markup=owner_menu())
    os.execv(sys.executable, [sys.executable] + sys.argv)


@router.callback_query()
async def owner_maintenance(callback: CallbackQuery) -> None:
    if callback.data != "owner_maintenance":
        return
    if not await _owner_guard(callback):
        return
    current = await get_setting("maintenance") or "off"
    new_value = "on" if current == "off" else "off"
    await set_setting("maintenance", new_value)
    await add_log("INFO", f"تم ضبط وضع الصيانة إلى {new_value}")
    await callback.answer("✅ تم تحديث وضع الصيانة")
    await callback.message.answer(f"🔧 تم تغيير وضع الصيانة إلى: {new_value}", reply_markup=owner_menu())


@router.callback_query()
async def owner_stats(callback: CallbackQuery) -> None:
    if callback.data != "owner_stats":
        return
    if not await _owner_guard(callback):
        return
    total_templates = len(await list_templates(active_only=False))
    total_buttons = len(await list_buttons(active_only=False))
    total_users = len(await get_all_user_ids())
    await callback.answer("✅ تم عرض الإحصائيات")
    await callback.message.answer(
        f"📊 إحصائيات النظام:\n- القوالب: {total_templates}\n- الأزرار: {total_buttons}\n- المستخدمين: {total_users}",
        reply_markup=owner_menu(),
    )


@router.callback_query()
async def owner_users(callback: CallbackQuery) -> None:
    if callback.data != "owner_users":
        return
    if not await _owner_guard(callback):
        return
    await callback.answer("✅ تم عرض إدارة المستخدمين")
    await callback.message.answer("👥 إدارة المستخدمين متاحة من خلال قاعدة البيانات واللوحة المستقبلية.", reply_markup=owner_menu())


@router.callback_query()
async def owner_admins(callback: CallbackQuery) -> None:
    if callback.data != "owner_admins":
        return
    if not await _owner_guard(callback):
        return
    await callback.answer("✅ تم فتح إدارة الأدمن")
    await callback.message.answer("👮 إدارة الأدمنات تحت التطوير وتعمل من خلال الإعدادات الداخلية.", reply_markup=owner_menu())


@router.callback_query()
async def owner_subscriptions(callback: CallbackQuery) -> None:
    if callback.data != "owner_subscriptions":
        return
    if not await _owner_guard(callback):
        return
    await callback.answer("✅ تم فتح إدارة الاشتراكات")
    await callback.message.answer("💳 إدارة الاشتراكات في البناء. يمكنك إضافة إعدادات الاشتراك المخصصة لاحقًا.", reply_markup=owner_menu())
