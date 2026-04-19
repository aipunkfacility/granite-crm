"""API endpoint: pipeline status, cities, and run (SSE).

Возвращает статус обработки по всем городам для фронтенда-дашборда.
POST /pipeline/run запускает пайплайн в фоне и стримит прогресс через SSE.
"""
import asyncio
import json
import queue
import threading
from typing import Optional

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import func

from granite.api.deps import get_db
from granite.api.schemas import (
    PipelineRunRequest, PipelineStatusResponse, PipelineCitiesResponse,
)
from granite.database import (
    RawCompanyRow, CompanyRow, EnrichedCompanyRow, CityRefRow,
)

router = APIRouter()

# Глобальное состояние запущенных пайплайнов (защита от двойного запуска)
_running_pipelines: dict[str, threading.Thread] = {}
_running_lock = threading.Lock()


@router.get("/pipeline/status", response_model=PipelineStatusResponse)
def pipeline_status(
    request: Request,
    limit: int = Query(50, ge=1, le=500, description="Максимум городов в ответе"),
    db=Depends(get_db),
):
    """Статус пайплайна по городам.

    Возвращает список городов с количеством записей на каждом этапе:
    raw (скрапинг), companies (дедупликация), enriched (обогащение).
    """
    # Считаем записи по городам через GROUP BY (3 запроса)
    raw_counts = dict(
        db.query(RawCompanyRow.city, func.count(RawCompanyRow.id))
        .group_by(RawCompanyRow.city).all()
    )
    comp_counts = dict(
        db.query(CompanyRow.city, func.count(CompanyRow.id))
        .group_by(CompanyRow.city).all()
    )
    enriched_counts = dict(
        db.query(EnrichedCompanyRow.city, func.count(EnrichedCompanyRow.id))
        .group_by(EnrichedCompanyRow.city).all()
    )

    # Сегментация для enriched городов
    seg_counts = {}
    seg_rows = db.query(
        EnrichedCompanyRow.city,
        EnrichedCompanyRow.segment,
        func.count(EnrichedCompanyRow.id),
    ).group_by(
        EnrichedCompanyRow.city,
        EnrichedCompanyRow.segment,
    ).all()
    for city_name, segment, cnt in seg_rows:
        if city_name not in seg_counts:
            seg_counts[city_name] = {}
        seg_counts[city_name][segment] = cnt

    # Собираем все уникальные города из всех таблиц
    all_cities = sorted(
        set(raw_counts) | set(comp_counts) | set(enriched_counts)
    )

    cities = []
    for city_name in all_cities[:limit]:
        enriched = enriched_counts.get(city_name, 0)
        comp = comp_counts.get(city_name, 0)
        raw = raw_counts.get(city_name, 0)

        # Определяем стадию
        if enriched > 0:
            stage = "enriched"
        elif comp > 0:
            stage = "deduped"
        elif raw > 0:
            stage = "scraped"
        else:
            stage = "start"

        # Прогресс обогащения
        progress = 0.0
        if comp > 0:
            progress = enriched / comp

        # Проверяем, запущен ли пайплайн для этого города
        is_running = False
        with _running_lock:
            thread = _running_pipelines.get(city_name)
            if thread and thread.is_alive():
                is_running = True

        entry = {
            "city": city_name,
            "stage": stage,
            "is_running": is_running,
            "raw_count": raw,
            "company_count": comp,
            "enriched_count": enriched,
            "enrichment_progress": round(progress, 3),
            "segments": seg_counts.get(city_name, {}),
        }
        cities.append(entry)

    return {
        "total_cities": len(all_cities),
        "returned": len(cities),
        "cities": cities,
    }


@router.get("/pipeline/cities", response_model=PipelineCitiesResponse)
def pipeline_cities(db=Depends(get_db)):
    """Список всех городов из справочника cities_ref."""
    cities = db.query(CityRefRow).order_by(CityRefRow.region, CityRefRow.name).all()
    return {
        "total": len(cities),
        "cities": [
            {
                "name": c.name,
                "region": c.region,
                "is_populated": c.is_populated,
                "is_doppelganger": c.is_doppelganger,
            }
            for c in cities
        ],
    }


@router.post("/pipeline/run")
async def pipeline_run(
    request: Request,
    body: PipelineRunRequest,
):
    """Запуск пайплайна для города с SSE-потоком прогресса.

    Пайплайн запускается в фоне (отдельный поток). SSE-стрим отправляет
    события: started, phase, done, error. Фронтенд подписывается на стрим
    для отслеживания прогресса в реальном времени.
    """
    city = body.city

    # Защита от двойного запуска
    with _running_lock:
        existing = _running_pipelines.get(city)
        if existing and existing.is_alive():
            return StreamingResponse(
                iter([f"data: {json.dumps({'type': 'error', 'message': 'Пайплайн уже запущен для этого города'})}\n\n"]),
                media_type="text/event-stream",
            )
        events: queue.Queue = queue.Queue()
        _running_pipelines[city] = threading.Thread(
            target=_run_pipeline_bg,
            args=(request, city, body.force, body.re_enrich, events),
            daemon=True,
        )
        _running_pipelines[city].start()

    async def event_stream():
        """Async generator для SSE — читает из queue и yield'ит события."""
        while True:
            try:
                event = events.get(timeout=30)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("type") in ("done", "error"):
                    break
            except queue.Empty:
                # Heartbeat для поддержания соединения
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _run_pipeline_bg(
    request: Request,
    city: str,
    force: bool,
    re_enrich: bool,
    events: queue.Queue,
) -> None:
    """Фоновый запуск пайплайна с эмиссией событий в queue."""
    try:
        events.put({"type": "started", "city": city})

        config = request.app.state.config
        db = request.app.state.db

        from granite.pipeline.manager import PipelineManager, PipelineCriticalError

        manager = PipelineManager(config, db)

        # Оборачиваем run_city для перехвата фаз
        events.put({"type": "phase", "phase": "scraping", "city": city})

        manager.run_city(
            city,
            force=force,
            run_scrapers=not re_enrich,
            re_enrich=re_enrich,
        )

        events.put({"type": "done", "city": city})

    except Exception as e:
        logger.exception(f"Pipeline run failed for {city}: {e}")
        events.put({"type": "error", "city": city, "message": str(e)})
