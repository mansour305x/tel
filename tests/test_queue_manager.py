import asyncio

from bot.queue.manager import QueueJob, QueueManager


def test_can_enqueue_within_limit():
    manager = QueueManager(workers_count=1, rate_limit=2)
    assert manager.can_enqueue(123)
    assert manager.can_enqueue(123)


def test_blocks_after_rate_limit():
    manager = QueueManager(workers_count=1, rate_limit=1)
    assert manager.can_enqueue(1)
    assert not manager.can_enqueue(1)


def test_enqueue_and_cancel_job():
    manager = QueueManager(workers_count=1, rate_limit=10)
    job = QueueJob(job_id="abc123", user_id=42, payload={})

    async def worker(_: QueueJob) -> None:
        return None

    async def run_queue() -> None:
        await manager.start_workers(worker)
        await manager.enqueue(job)
        await asyncio.sleep(0.1)
        manager.cancel_job(job.job_id, job.user_id)
        await manager.stop_workers()

    asyncio.run(run_queue())
    assert job.job_id not in manager.active_jobs
