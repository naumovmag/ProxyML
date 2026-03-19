import asyncio
import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from src.db.engine import async_session_factory
from src.models.load_test import LoadTestTask
from src.models.service import Service
from src.services.load_test_executor import execute_single_test

logger = logging.getLogger(__name__)


class LoadTestScheduler:
    def __init__(self):
        self._tasks: dict[uuid.UUID, asyncio.Task] = {}

    async def start(self):
        async with async_session_factory() as session:
            result = await session.execute(
                select(LoadTestTask).where(LoadTestTask.status == "running")
            )
            tasks = result.scalars().all()
            for task in tasks:
                self.start_task(task.id, task.interval_seconds)
            if tasks:
                logger.info(f"Load test scheduler: resumed {len(tasks)} running task(s)")

    async def stop(self):
        for task_id, atask in self._tasks.items():
            atask.cancel()
        self._tasks.clear()
        logger.info("Load test scheduler stopped")

    def start_task(self, task_id: uuid.UUID, interval_seconds: int):
        if task_id in self._tasks:
            self._tasks[task_id].cancel()
        self._tasks[task_id] = asyncio.create_task(self._run_loop(task_id, interval_seconds))
        logger.info(f"Load test task {task_id} started (interval={interval_seconds}s)")

    def stop_task(self, task_id: uuid.UUID):
        atask = self._tasks.pop(task_id, None)
        if atask:
            atask.cancel()
            logger.info(f"Load test task {task_id} stopped")

    async def _run_loop(self, task_id: uuid.UUID, interval_seconds: int):
        try:
            while True:
                await self._execute_one_run(task_id)
                await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Load test loop error for {task_id}: {e}")
            try:
                async with async_session_factory() as session:
                    result = await session.execute(
                        select(LoadTestTask).where(LoadTestTask.id == task_id)
                    )
                    task = result.scalar_one_or_none()
                    if task:
                        task.status = "stopped"
                        await session.commit()
            except Exception:
                pass
            self._tasks.pop(task_id, None)

    async def _execute_one_run(self, task_id: uuid.UUID):
        async with async_session_factory() as session:
            result = await session.execute(
                select(LoadTestTask).where(LoadTestTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if not task or task.status != "running":
                self.stop_task(task_id)
                return

            if task.max_runs and task.total_runs >= task.max_runs:
                task.status = "stopped"
                await session.commit()
                self.stop_task(task_id)
                return

            result = await session.execute(
                select(Service).where(Service.id == task.service_id)
            )
            service = result.scalar_one_or_none()
            if not service:
                logger.warning(f"Service {task.service_id} not found for load test {task_id}")
                task.status = "stopped"
                await session.commit()
                self.stop_task(task_id)
                return

            test_result = await execute_single_test(task, service)

            session.add(test_result)
            task.total_runs += 1
            task.last_run_at = datetime.now(timezone.utc)
            await session.commit()


scheduler = LoadTestScheduler()
