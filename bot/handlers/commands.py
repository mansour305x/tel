from __future__ import annotations

from aiogram import Router
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import Command, Text
from aiogram.types import CallbackQuery, Message
from bot.exceptions.errors import UnsupportedPlatformError, ValidationError
from bot.keyboards.menus import admin_keyboard, quality_selection_keyboard, settings_keyboard
from bot.services.task_manager import TaskManager
from bot.services.settings_service import SettingsService
from bot.validators.url_validator import detect_platform, format_platform, validate_url
from bot.utils.formatters import format_duration, format_size

router = Router()


def register_handlers(task_manager: TaskManager, settings_service: SettingsService) -> Router:
    @router.message(Command("start"))
    async def start_handler(message: Message) -> None:
        if not message.from_user:
            return
        await task_manager.register_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        await message.answer(
            "مرحبًا! أرسل رابط فيديو من YouTube أو TikTok أو Instagram أو Snapchat للحصول على الخيارات المتاحة.",
            parse_mode=ParseMode.HTML,
        )

    @router.message(Command("help"))
    async def help_handler(message: Message) -> None:
        await message.answer(
            "استخدم هذا البوت لتحميل الفيديوهات أو تحويلها إلى MP3.\n\n" \
            "أرسل رابط فيديو لتبدأ.\n" \
            "/status - حالة الطلب\n" \
            "/cancel - إلغاء الطلب الحالي\n" \
            "/settings - عرض إعدادات النظام\n" \
            "للمسؤولين: /admin_stats /admin_users /admin_broadcast /admin_queue",
            parse_mode=ParseMode.HTML,
        )

    @router.message(Command("status"))
    async def status_handler(message: Message) -> None:
        await message.answer("جاري التحقق من حالة الطلبات...")
        active_jobs = len(task_manager.queue_manager.active_jobs)
        await message.answer(
            f"📌 عدد الطلبات النشطة: {active_jobs}\n" \
            f"⏳ عدد طلبات الانتظار: {task_manager.queue_manager.queue.qsize()}",
        )

    @router.message(Command("cancel"))
    async def cancel_handler(message: Message) -> None:
        user_id = message.from_user.id
        cancelled = task_manager.cancel_user_jobs(user_id)
        if cancelled:
            await message.answer("✅ تم إلغاء الطلبات النشطة الخاصة بك.")
        else:
            await message.answer("لم يتم العثور على طلبات نشطة للإلغاء.")

    @router.message(Command("settings"))
    async def settings_handler(message: Message) -> None:
        if message.from_user.id not in task_manager.config.admin_ids:
            await message.answer("⚠️ هذا الأمر مخصص للمسؤولين فقط.")
            return
        current = await settings_service.all()
        await message.answer(
            "⚙️ إعدادات النظام الحالية:\n"
            f"- الحد الأقصى للحجم: {current.get('max_file_size_mb')} MB\n"
            f"- الجودة الافتراضية: {current.get('default_quality')}\n"
            f"- عدد العمال: {current.get('workers_count')}\n"
            f"- حد الطلبات لكل دقيقة: {current.get('rate_limit')}\n"
            f"- مدة الاحتفاظ: {current.get('retention_seconds')} ثانية",
            reply_markup=settings_keyboard(),
        )

    @router.message(Command("admin_stats"))
    async def admin_stats_handler(message: Message) -> None:
        if message.from_user.id not in task_manager.config.admin_ids:
            await message.answer("⚠️ غير مصرح.")
            return
        stats = await task_manager.get_admin_stats()
        await message.answer(
            "📊 إحصائيات الإدارة:\n"
            f"المستخدمون المسجلون: {stats['users']}\n"
            f"الطلبات الحالية: {stats['active_jobs']}\n"
            f"الطلبات المكتملة: {stats['completed_jobs']}\n"
        )

    @router.message(Command("admin_users"))
    async def admin_users_handler(message: Message) -> None:
        if message.from_user.id not in task_manager.config.admin_ids:
            await message.answer("⚠️ غير مصرح.")
            return
        users = await task_manager.get_user_summary()
        if not users:
            await message.answer("لا يوجد مستخدمون مسجلون حتى الآن.")
            return
        lines = [f"{user.id} - @{user.username or 'غير معروف'}" for user in users]
        await message.answer("👥 المستخدمون المسجلون:\n" + "\n".join(lines))

    @router.message(Command("admin_broadcast"))
    async def admin_broadcast_handler(message: Message) -> None:
        if message.from_user.id not in task_manager.config.admin_ids:
            await message.answer("⚠️ غير مصرح.")
            return
        payload = message.text.removeprefix("/admin_broadcast").strip()
        if not payload:
            await message.answer("استخدم /admin_broadcast <النص> لإرسال رسالة لجميع المستخدمين.")
            return
        count = await task_manager.broadcast_message(payload)
        await message.answer(f"✅ تم إرسال الرسالة إلى {count} مستخدمًا.")

    @router.message(Command("admin_queue"))
    async def admin_queue_handler(message: Message) -> None:
        if message.from_user.id not in task_manager.config.admin_ids:
            await message.answer("⚠️ غير مصرح.")
            return
        await message.answer(
            f"قائمة الانتظار: {task_manager.queue_manager.queue.qsize()} طلبات\n" \
            f"الطلبات النشطة: {len(task_manager.queue_manager.active_jobs)}",
            reply_markup=admin_keyboard(),
        )

    @router.message()
    async def receive_url_handler(message: Message) -> None:
        user_id = message.from_user.id
        text = message.text or ""
        try:
            validated_url = validate_url(text)
            platform = detect_platform(validated_url)
            info = await task_manager.downloader.extract_info(validated_url)
            if info.get("is_private"):
                raise ValidationError("الفيديو خاص ولا يمكن الوصول إليه.")
            job = await task_manager.prepare_job(user_id, validated_url, platform, info)
            duration = format_duration(int(info.get("duration", 0)))
            size = format_size(int(info.get("filesize", 0)))
            await message.answer(
                f"📌 العنوان: {info.get('title', 'غير معروف')}\n"
                f"⏱️ المدة: {duration}\n"
                f"📦 الحجم المتوقع: {size}\n"
                f"🌐 المنصة: {format_platform(platform)}\n"
                "اختر نوع العملية:",
                reply_markup=quality_selection_keyboard(job.job_id),
            )
        except ValidationError as exc:
            await message.answer(f"⚠️ {exc}")
        except UnsupportedPlatformError as exc:
            await message.answer(f"⚠️ {exc}")
        except Exception:
            await message.answer("⚠️ حدث خطأ أثناء تحليل الرابط. تأكد من أن الرابط صالح ومدعوم.")

    @router.callback_query(Text(startswith="download:"))
    async def download_callback(callback: CallbackQuery) -> None:
        await callback.answer()
        _, job_id, quality = callback.data.split(":")
        try:
            job = await task_manager.update_job_quality(job_id, quality)
            await task_manager.enqueue_job(job)
            await callback.message.edit_text(f"✅ تم تسجيل الطلب {job.title}. سيتم تحميل المحتوى قريبًا.")
        except ValidationError as exc:
            await callback.message.edit_text(f"⚠️ {exc}")
        except Exception:
            await callback.message.edit_text("⚠️ تعذر معالجة الطلب. حاول مرة أخرى لاحقًا.")

    @router.callback_query(Text(startswith="cancel:"))
    async def cancel_callback(callback: CallbackQuery) -> None:
        await callback.answer()
        _, job_id = callback.data.split(":")
        try:
            task_manager.cancel_user_job(job_id, callback.from_user.id)
            await callback.message.edit_text("✅ تم إلغاء الطلب.")
        except Exception:
            await callback.message.edit_text("⚠️ تعذر إلغاء الطلب أو لقد اكتمل بالفعل.")

    @router.callback_query(Text(startswith="settings:"))
    async def settings_callback(callback: CallbackQuery) -> None:
        await callback.answer()
        if callback.from_user.id not in task_manager.config.admin_ids:
            await callback.message.answer("⚠️ هذا الأمر للمسؤولين فقط.")
            return
        _, key, action = callback.data.split(":")
        current = await settings_service.get(key)
        if current is None:
            await callback.message.answer("⚠️ إعداد غير معروف.")
            return
        value = int(current) + (1 if action == "+1" else -1)
        if value < 1:
            value = 1
        await settings_service.set(key, str(value))
        await callback.message.answer(f"✅ تم تحديث {key} إلى {value}.")

    return router
