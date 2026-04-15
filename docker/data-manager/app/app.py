import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request

from app.routers import everybusiness, emergency, probe

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("data-manager")

PROBE_SCHEDULER_ENABLED = os.environ.get(
    "PROBE_SCHEDULER_ENABLED", "false"
).lower() in ("true", "1", "yes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Data Manager starting up")
    if PROBE_SCHEDULER_ENABLED:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from app.services.probe_service import (
                collect_probe_data,
                save_collection_log,
            )
            from datetime import datetime

            def scheduled_collect():
                logger.info("Scheduled probe collection started")
                try:
                    result = collect_probe_data()
                    total_new = sum(
                        v.get("tgz_new", 0) + v.get("json_new", 0)
                        for v in result.values()
                        if isinstance(v, dict) and "error" not in v
                    )
                    errors = [
                        k
                        for k, v in result.items()
                        if isinstance(v, dict) and "error" in v
                    ]
                    log_entry = {
                        "time": datetime.now().isoformat(),
                        "status": "success"
                        if not errors
                        else "partial"
                        if total_new > 0
                        else "failed",
                        "new_files": total_new,
                        "errors": errors,
                        "details": result,
                    }
                    save_collection_log(log_entry)
                    logger.info(
                        f"Scheduled probe collection done: {total_new} new files"
                    )
                except Exception as e:
                    logger.error(f"Scheduled probe collection failed: {e}")

            scheduler = BackgroundScheduler()
            scheduler.add_job(scheduled_collect, "cron", hour="11,17", minute=0)
            scheduler.start()
            logger.info("Probe scheduler started (11:00, 17:00)")
            yield
            scheduler.shutdown()
        except Exception as e:
            logger.error(f"Failed to start probe scheduler: {e}")
            yield
    else:
        yield
    logger.info("Data Manager shutting down")


app = FastAPI(title="DeerFlow Data Manager", lifespan=lifespan)

app.include_router(everybusiness.router)
app.include_router(emergency.router)
app.include_router(probe.router)

templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
