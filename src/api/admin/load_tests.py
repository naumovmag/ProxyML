import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import select, delete, desc, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_async_session
from src.api.deps import get_current_admin
from src.models.admin_user import AdminUser
from src.models.service import Service
from src.models.load_test import LoadTestTask, LoadTestResult
from src.services.load_test_payloads import get_default_payload
from src.services.load_test_scheduler import scheduler
from src.services.service_access import check_service_access

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Schemas ───


class LoadTestTaskCreate(BaseModel):
    service_id: str
    name: str = ""
    interval_seconds: int = 60
    test_path: str | None = None
    test_method: str = "POST"
    test_body: dict | None = None
    test_headers: dict | None = None
    max_runs: int | None = None

    @field_validator("interval_seconds")
    @classmethod
    def interval_min(cls, v):
        if v < 5:
            raise ValueError("interval_seconds must be >= 5")
        return v


class LoadTestTaskUpdate(BaseModel):
    name: str | None = None
    interval_seconds: int | None = None
    test_path: str | None = None
    test_method: str | None = None
    test_body: dict | None = None
    test_headers: dict | None = None
    max_runs: int | None = None

    @field_validator("interval_seconds")
    @classmethod
    def interval_min(cls, v):
        if v is not None and v < 5:
            raise ValueError("interval_seconds must be >= 5")
        return v


class LoadTestTaskRead(BaseModel):
    id: str
    service_id: str
    name: str
    interval_seconds: int
    service_type: str
    test_path: str
    test_method: str
    test_body: dict | None
    test_headers: dict | None
    status: str
    max_runs: int | None
    total_runs: int
    last_run_at: str | None
    created_at: str
    updated_at: str


class LoadTestResultRead(BaseModel):
    id: str
    task_id: str
    status_code: int
    duration_ms: float
    request_size: int
    response_size: int
    error: str | None
    response_body: str | None
    created_at: str


class LoadTestStatsRead(BaseModel):
    total: int
    avg_duration_ms: float | None
    min_duration_ms: float | None
    max_duration_ms: float | None
    p95_duration_ms: float | None
    error_count: int
    error_rate: float | None


# ─── Helpers ───


def _task_to_read(t: LoadTestTask) -> LoadTestTaskRead:
    return LoadTestTaskRead(
        id=str(t.id),
        service_id=str(t.service_id),
        name=t.name,
        interval_seconds=t.interval_seconds,
        service_type=t.service_type,
        test_path=t.test_path,
        test_method=t.test_method,
        test_body=t.test_body,
        test_headers=t.test_headers,
        status=t.status,
        max_runs=t.max_runs,
        total_runs=t.total_runs,
        last_run_at=t.last_run_at.isoformat() if t.last_run_at else None,
        created_at=t.created_at.isoformat(),
        updated_at=t.updated_at.isoformat(),
    )


def _result_to_read(r: LoadTestResult) -> LoadTestResultRead:
    return LoadTestResultRead(
        id=str(r.id),
        task_id=str(r.task_id),
        status_code=r.status_code,
        duration_ms=r.duration_ms,
        request_size=r.request_size,
        response_size=r.response_size,
        error=r.error,
        response_body=r.response_body,
        created_at=r.created_at.isoformat(),
    )


# ─── Endpoints ───


@router.get("/load-tests")
async def list_load_tests(
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(LoadTestTask)
        .where(LoadTestTask.owner_id == admin.id)
        .order_by(desc(LoadTestTask.created_at))
    )
    tasks = result.scalars().all()
    return [_task_to_read(t) for t in tasks]


@router.post("/load-tests")
async def create_load_test(
    data: LoadTestTaskCreate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    service, role = await check_service_access(session, uuid.UUID(data.service_id), admin.id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    default = get_default_payload(service.service_type)
    test_path = data.test_path if data.test_path is not None else default["path"]

    task = LoadTestTask(
        owner_id=admin.id,
        service_id=service.id,
        name=data.name or service.name,
        interval_seconds=data.interval_seconds,
        service_type=service.service_type,
        test_path=test_path,
        test_method=data.test_method,
        test_body=data.test_body,
        test_headers=data.test_headers,
        max_runs=data.max_runs,
        status="stopped",
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return _task_to_read(task)


@router.get("/load-tests/{task_id}")
async def get_load_test(
    task_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(LoadTestTask).where(LoadTestTask.id == task_id, LoadTestTask.owner_id == admin.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Load test task not found")
    return _task_to_read(task)


@router.put("/load-tests/{task_id}")
async def update_load_test(
    task_id: uuid.UUID,
    data: LoadTestTaskUpdate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(LoadTestTask).where(LoadTestTask.id == task_id, LoadTestTask.owner_id == admin.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Load test task not found")
    if task.status == "running":
        raise HTTPException(status_code=400, detail="Cannot update a running task. Stop it first.")

    if data.name is not None:
        task.name = data.name
    if data.interval_seconds is not None:
        task.interval_seconds = data.interval_seconds
    if data.test_path is not None:
        task.test_path = data.test_path
    if data.test_method is not None:
        task.test_method = data.test_method
    if data.test_body is not None:
        task.test_body = data.test_body
    if data.test_headers is not None:
        task.test_headers = data.test_headers
    if data.max_runs is not None:
        task.max_runs = data.max_runs

    await session.commit()
    await session.refresh(task)
    return _task_to_read(task)


@router.delete("/load-tests/{task_id}")
async def delete_load_test(
    task_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(LoadTestTask).where(LoadTestTask.id == task_id, LoadTestTask.owner_id == admin.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Load test task not found")

    scheduler.stop_task(task_id)
    await session.delete(task)
    await session.commit()
    return {"ok": True}


@router.post("/load-tests/{task_id}/start")
async def start_load_test(
    task_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(LoadTestTask).where(LoadTestTask.id == task_id, LoadTestTask.owner_id == admin.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Load test task not found")
    if task.status == "running":
        raise HTTPException(status_code=400, detail="Task is already running")

    result = await session.execute(select(Service).where(Service.id == task.service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=400, detail="Associated service not found")
    if not service.is_active:
        raise HTTPException(status_code=400, detail="Cannot start: service is inactive")

    task.status = "running"
    await session.commit()

    scheduler.start_task(task_id, task.interval_seconds)
    return {"ok": True, "status": "running"}


@router.post("/load-tests/{task_id}/stop")
async def stop_load_test(
    task_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(LoadTestTask).where(LoadTestTask.id == task_id, LoadTestTask.owner_id == admin.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Load test task not found")

    scheduler.stop_task(task_id)
    task.status = "stopped"
    await session.commit()
    return {"ok": True, "status": "stopped"}


@router.get("/load-tests/{task_id}/results")
async def list_load_test_results(
    task_id: uuid.UUID,
    limit: int = Query(50, le=500),
    offset: int = Query(0),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    # Verify ownership
    result = await session.execute(
        select(LoadTestTask.id).where(LoadTestTask.id == task_id, LoadTestTask.owner_id == admin.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Load test task not found")

    result = await session.execute(
        select(LoadTestResult)
        .where(LoadTestResult.task_id == task_id)
        .order_by(desc(LoadTestResult.created_at))
        .offset(offset)
        .limit(limit)
    )
    results = result.scalars().all()
    return [_result_to_read(r) for r in results]


@router.get("/load-tests/{task_id}/stats")
async def load_test_stats(
    task_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    # Verify ownership
    result = await session.execute(
        select(LoadTestTask.id).where(LoadTestTask.id == task_id, LoadTestTask.owner_id == admin.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Load test task not found")

    result = await session.execute(
        select(
            sa_func.count(LoadTestResult.id).label("total"),
            sa_func.avg(LoadTestResult.duration_ms).label("avg_duration_ms"),
            sa_func.min(LoadTestResult.duration_ms).label("min_duration_ms"),
            sa_func.max(LoadTestResult.duration_ms).label("max_duration_ms"),
            sa_func.count(LoadTestResult.id).filter(LoadTestResult.error.isnot(None)).label("error_count"),
        ).where(LoadTestResult.task_id == task_id)
    )
    row = result.one()
    total = row.total or 0
    error_count = row.error_count or 0

    # p95
    p95 = None
    if total > 0:
        p95_result = await session.execute(
            select(LoadTestResult.duration_ms)
            .where(LoadTestResult.task_id == task_id)
            .order_by(LoadTestResult.duration_ms)
            .offset(int(total * 0.95))
            .limit(1)
        )
        p95_row = p95_result.scalar_one_or_none()
        p95 = round(p95_row, 1) if p95_row is not None else None

    return LoadTestStatsRead(
        total=total,
        avg_duration_ms=round(row.avg_duration_ms, 1) if row.avg_duration_ms is not None else None,
        min_duration_ms=round(row.min_duration_ms, 1) if row.min_duration_ms is not None else None,
        max_duration_ms=round(row.max_duration_ms, 1) if row.max_duration_ms is not None else None,
        p95_duration_ms=p95,
        error_count=error_count,
        error_rate=round(error_count / total * 100, 1) if total > 0 else None,
    )


@router.delete("/load-tests/{task_id}/results")
async def clear_load_test_results(
    task_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    # Verify ownership
    result = await session.execute(
        select(LoadTestTask).where(LoadTestTask.id == task_id, LoadTestTask.owner_id == admin.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Load test task not found")

    await session.execute(
        delete(LoadTestResult).where(LoadTestResult.task_id == task_id)
    )
    task.total_runs = 0
    task.last_run_at = None
    await session.commit()
    return {"ok": True}
