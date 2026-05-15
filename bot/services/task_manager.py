from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aiogram import Bot
from aiogram.types import InputFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import BotConfig
from bot.database.session import create_async_session
from bot.downloader.yt_downloader import YoutubeDownloader
from bot.exceptions.errors import DownloadError, ValidationError
from bot.models.job import DownloadJob, JobStatus
from bot.models.setting import Setting
from bot.models.user import User
from bot.queue.manager import QueueJob, QueueManager
from bot.utils.files import cleanup_files, ensure_directories
from bot.utils.formatters import format_size
from bot.validators.url_validator import detect_platform, format_platform, validate_url
from loguru import logger

if TYPE_CHECKING:
    from bot.services.settings_service import SettingsService


class TaskManager:
    def __init__(self, config: BotConfig, settings_service: "SettingsService") -> None:
        self.config = config
        self.settings_service = settings_service
        self.queue_manager = QueueManager(config.workers_count, config.rate_limit)
        self.download_dir = config.download_dir
        self.temp_dir = config.temp_dir
        self.downloader = YoutubeDownloader(config)
        self.session_maker = create_async_session(config.database_url)

    async def start(self) -> None:
        ensure_directories(self.download_dir, self.temp_dir)
        await self.queue_manager.start_workers(self.process_job)

    async def shutdown(self) -> None:
        await self.queue_manager.stop_workers()

    async def register_user(self, user_id: int, username: str | None, first_name: str | None, last_name: str | None) -> User:
        async with self.session_maker() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                return user
            user = User(id=user_id, username=username, first_name=first_name, last_name=last_name)
            session.add(user)
            await session.commit()
            return user

    async def prepare_job(self, user_id: int, url: str, platform: str, info: dict[str, Any]) -> DownloadJob:
        title = info.get("title", "Video")[:250]
        job_id = uuid.uuid4().hex
        async with self.session_maker() as session:
            job = DownloadJob(
                job_id=job_id,
                user_id=user_id,
                url=url,
                platform=platform,
                title=title,
                status=JobStatus.PENDING,
                quality="pending",
            )
            session.add(job)
            await session.commit()
            return job

    async def update_job_quality(self, job_id: str, quality: str) -> DownloadJob:
        async with self.session_maker() as session:
            result = await session.execute(select(DownloadJob).where(DownloadJob.job_id == job_id))
            job = result.scalar_one_or_none()
            if not job:
                raise ValidationError("الطلب غير موجود.")
            if quality not in {"best", "medium", "mp3"}:
                raise ValidationError("الخيار غير صالح.")
            job.quality = quality
            await session.commit()
            return job

    async def enqueue_job(self, job: DownloadJob) -> None:
        if not self.queue_manager.can_enqueue(job.user_id):
            raise ValidationError("وصلت إلى الحد الأقصى للطلبات المؤقتة. حاول لاحقًا.")
        await self.queue_manager.enqueue(QueueJob(job_id=job.job_id, user_id=job.user_id, payload={"job_id": job.job_id}))

    async def process_job(self, queue_job: QueueJob) -> None:
        async with self.session_maker() as session:
            result = await session.execute(select(DownloadJob).where(DownloadJob.job_id == queue_job.job_id))
            job = result.scalar_one_or_none()
            if not job:
                return
            if job.quality == "pending":
                job.status = JobStatus.FAILED
                job.error_message = "لم يتم اختيار جودة التحميل."
                await session.commit()
                return
            job.status = JobStatus.PROCESSING
            await session.commit()
            job_path = self.download_dir / job.job_id
            ensure_directories(job_path)
            try:
                downloaded_file = await self.downloader.download(job.url, job.quality, job_path)
                if downloaded_file.stat().st_size > self.config.max_file_size_mb * 1024 * 1024:
                    raise DownloadError("حجم الملف النهائي أكبر من الحد المسموح به.")
                job.file_path = str(downloaded_file)
                job.status = JobStatus.COMPLETED
                await session.commit()
                await self._send_result(job, downloaded_file)
            except Exception as exc:
                logger.exception("Failed to process job %s", job.job_id)
                job.status = JobStatus.FAILED
                job.error_message = str(exc)
                await session.commit()
                await self._notify_failure(job)
            finally:
                cleanup_files([job_path])

    async def _send_result(self, job: DownloadJob, file_path: Path) -> None:
        bot = Bot(token=self.config.bot_token)
        try:
            input_file = InputFile(file_path)
            caption = f"✅ تمت العملية بنجاح\n📌 العنوان: {job.title}\n🎬 المنصة: {format_platform(job.platform)}"
            if job.quality == "mp3":
                await bot.send_audio(job.user_id, audio=input_file, caption=caption)
            else:
                await bot.send_video(job.user_id, video=input_file, caption=caption)
        except Exception as exc:
            logger.error("Telegram upload failed for job %s: %s", job.job_id, exc)
        finally:
            await bot.session.close()

    async def _notify_failure(self, job: DownloadJob) -> None:
        bot = Bot(token=self.config.bot_token)
        try:
            await bot.send_message(job.user_id, f"⚠️ فشل تنزيل الفيديو: {job.error_message}")
        except Exception:
            logger.error("Unable to send failure notification for job %s", job.job_id)
        finally:
            await bot.session.close()

    async def get_job_status(self, job_id: str) -> str:
        async with self.session_maker() as session:
            result = await session.execute(select(DownloadJob).where(DownloadJob.job_id == job_id))
            job = result.scalar_one_or_none()
            return job.status.value if job else "غير موجود"

    async def cancel_user_jobs(self, user_id: int) -> bool:
        cancelled = False
        for job_id, queue_job in list(self.queue_manager.active_jobs.items()):
            if queue_job.user_id == user_id:
                self.queue_manager.active_jobs.pop(job_id, None)
                cancelled = True
        return cancelled

    def cancel_user_job(self, job_id: str, user_id: int) -> None:
        self.queue_manager.cancel_job(job_id, user_id)

    async def broadcast_message(self, message_text: str) -> int:
        async with self.session_maker() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()
        bot = Bot(token=self.config.bot_token)
        count = 0
        for user in users:
            try:
                await bot.send_message(user.id, message_text)
                count += 1
            except Exception:
                continue
        await bot.session.close()
        return count

    async def get_admin_stats(self) -> dict[str, int]:
        async with self.session_maker() as session:
            users_count = await session.scalar(select(func.count()).select_from(User))
            completed_jobs = await session.scalar(select(func.count()).select_from(DownloadJob).where(DownloadJob.status == JobStatus.COMPLETED))
        return {
            "users": int(users_count or 0),
            "active_jobs": len(self.queue_manager.active_jobs),
            "completed_jobs": int(completed_jobs or 0),
        }

    async def get_user_summary(self) -> list[User]:
        async with self.session_maker() as session:
            result = await session.execute(select(User))
            return result.scalars().all()

    async def cleanup_old_jobs(self) -> None:
        expiration = datetime.utcnow().timestamp() - self.config.retention_seconds
        async with self.session_maker() as session:
            result = await session.execute(select(DownloadJob).where(DownloadJob.created_at < datetime.utcfromtimestamp(expiration)))
            for job in result.scalars().all():
                if job.file_path:
                    Path(job.file_path).unlink(missing_ok=True)
                session.delete(job)
            await session.commit()
