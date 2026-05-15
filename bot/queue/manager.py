from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from bot.exceptions.errors import JobCancellationError, RetryLimitExceededError


@dataclass
class QueueJob:
    job_id: str
    user_id: int
    payload: dict[str, Any]
    created_at: datetime = datetime.utcnow()


class QueueManager:
    def __init__(self, workers_count: int, rate_limit: int) -> None:
        self.queue: asyncio.Queue[QueueJob] = asyncio.Queue()
        self.active_jobs: dict[str, QueueJob] = {}
        self._workers_count = workers_count
        self._rate_limit = rate_limit
        self._user_requests: dict[int, list[datetime]] = defaultdict(list)
        self._stop_event = asyncio.Event()
        self._workers: list[asyncio.Task[None]] = []

    def can_enqueue(self, user_id: int) -> bool:
        now = datetime.utcnow()
        window = now - timedelta(minutes=1)
        self._user_requests[user_id] = [ts for ts in self._user_requests[user_id] if ts > window]
        if len(self._user_requests[user_id]) >= self._rate_limit:
            return False
        self._user_requests[user_id].append(now)
        return True

    async def enqueue(self, job: QueueJob) -> None:
        self.active_jobs[job.job_id] = job
        await self.queue.put(job)

    async def start_workers(self, worker_fn: Callable[[QueueJob], Any]) -> None:
        if self._workers:
            return
        for _ in range(self._workers_count):
            task = asyncio.create_task(self._worker_loop(worker_fn))
            self._workers.append(task)

    async def stop_workers(self) -> None:
        self._stop_event.set()
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def _worker_loop(self, worker_fn: Callable[[QueueJob], Any]) -> None:
        while not self._stop_event.is_set():
            job = await self.queue.get()
            if job.job_id not in self.active_jobs:
                self.queue.task_done()
                continue
            try:
                await worker_fn(job)
            except JobCancellationError:
                pass
            finally:
                self.active_jobs.pop(job.job_id, None)
                self.queue.task_done()

    def cancel_job(self, job_id: str, user_id: int) -> None:
        job = self.active_jobs.get(job_id)
        if not job or job.user_id != user_id:
            raise JobCancellationError("لا يوجد طلب لإلغائه.")
        self.active_jobs.pop(job_id, None)

    def validate_retry(self, retry_count: int) -> None:
        if retry_count > 3:
            raise RetryLimitExceededError("تم تجاوز عدد مرات المحاولة المسموح بها.")
