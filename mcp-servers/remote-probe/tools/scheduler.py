import json
import logging
import threading
import uuid
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from config import get_config
from db.database import get_connection, init_db
from db.models import get_all_region_domains, get_current_baseline
from tools.collect_probe_data import collect_probe_data_impl
from tools.parse_probe_results import parse_probe_results_impl
from tools.compare_with_baseline import compare_with_baseline_impl
from tools.generate_probe_report import generate_probe_report_impl
from tools.update_baseline import update_baseline_impl

logger = logging.getLogger("remote_probe.scheduler")

_scheduler: BackgroundScheduler | None = None

_pipeline_tasks: dict[str, dict] = {}
_pipeline_lock = threading.Lock()


def _execute_pipeline_background(
    task_id: str, hours: int, window_size: int, weight_recent: float
) -> None:
    """Run the full pipeline in a background thread, updating _pipeline_tasks as it progresses."""
    started = datetime.now()
    logger.info(f"[pipeline:{task_id}] started at {started.isoformat()}")

    task_state = {
        "task_id": task_id,
        "status": "running",
        "started_at": started.isoformat(),
        "current_step": "init",
        "steps": {},
        "error": None,
    }

    def _update(state: dict) -> None:
        with _pipeline_lock:
            _pipeline_tasks[task_id] = state

    _update(task_state)

    try:
        # Step 1: Collect
        task_state["current_step"] = "collect"
        _update(task_state)
        collect_result = collect_probe_data_impl()
        task_state["steps"]["collect"] = collect_result
        _update(task_state)
        logger.info(
            f"[pipeline:{task_id}] collect done: {json.dumps(collect_result, default=str)}"
        )

        # Step 2: Parse
        task_state["current_step"] = "parse"
        _update(task_state)
        parse_result = parse_probe_results_impl()
        task_state["steps"]["parse"] = parse_result
        _update(task_state)
        logger.info(
            f"[pipeline:{task_id}] parse done: {json.dumps(parse_result, default=str)}"
        )

        # Step 3: Compare
        task_state["current_step"] = "compare"
        _update(task_state)
        compare_result = compare_with_baseline_impl(hours=hours)
        task_state["steps"]["compare"] = compare_result
        _update(task_state)
        logger.info(
            f"[pipeline:{task_id}] compare done for {len(compare_result)} pairs"
        )

        # Step 4: Generate report
        task_state["current_step"] = "report"
        _update(task_state)
        report = generate_probe_report_impl(report_type="daily", hours=hours)
        task_state["steps"]["report"] = {"length": len(report), "saved": True}
        _update(task_state)
        logger.info(f"[pipeline:{task_id}] report generated ({len(report)} chars)")

        # Step 5: Update baseline for each region×domain pair
        task_state["current_step"] = "update_baseline"
        _update(task_state)
        cfg = get_config()
        init_db(cfg.sqlite.db_path)
        conn = get_connection(cfg.sqlite.db_path)
        pairs = get_all_region_domains(conn)

        update_results = {}
        for region, domain in pairs:
            bl = get_current_baseline(conn, region, domain)
            if bl:
                upd = update_baseline_impl(region, domain, window_size, weight_recent)
                update_results[f"{region}/{domain}"] = upd
                logger.info(
                    f"[pipeline:{task_id}] baseline updated for {region}/{domain}: {upd.get('changed_fields')}"
                )

        conn.close()
        task_state["steps"]["update_baseline"] = update_results

        finished = datetime.now()
        duration = (finished - started).total_seconds()
        task_state["status"] = "completed"
        task_state["current_step"] = "done"
        task_state["finished_at"] = finished.isoformat()
        task_state["duration_seconds"] = round(duration, 2)
        _update(task_state)
        logger.info(f"[pipeline:{task_id}] finished in {duration:.1f}s")

    except Exception as e:
        logger.error(f"[pipeline:{task_id}] failed: {e}", exc_info=True)
        task_state["status"] = "failed"
        task_state["error"] = str(e)
        task_state["finished_at"] = datetime.now().isoformat()
        _update(task_state)


def run_probe_pipeline(
    hours: int = 6,
    window_size: int = 30,
    weight_recent: float = 0.7,
) -> dict:
    """Execute the full probe pipeline synchronously (used by scheduler cron jobs)."""
    started = datetime.now()
    logger.info(f"[pipeline] started at {started.isoformat()}")

    result = {"started_at": started.isoformat(), "steps": {}}

    # Step 1: Collect
    collect_result = collect_probe_data_impl()
    result["steps"]["collect"] = collect_result
    logger.info(f"[pipeline] collect done: {json.dumps(collect_result, default=str)}")

    # Step 2: Parse
    parse_result = parse_probe_results_impl()
    result["steps"]["parse"] = parse_result
    logger.info(f"[pipeline] parse done: {json.dumps(parse_result, default=str)}")

    # Step 3: Compare
    compare_result = compare_with_baseline_impl(hours=hours)
    result["steps"]["compare"] = compare_result
    logger.info(f"[pipeline] compare done for {len(compare_result)} pairs")

    # Step 4: Generate report
    report = generate_probe_report_impl(report_type="daily", hours=hours)
    result["steps"]["report"] = {"length": len(report), "saved": True}
    logger.info(f"[pipeline] report generated ({len(report)} chars)")

    # Step 5: Update baseline for each region×domain pair
    cfg = get_config()
    init_db(cfg.sqlite.db_path)
    conn = get_connection(cfg.sqlite.db_path)
    pairs = get_all_region_domains(conn)

    update_results = {}
    for region, domain in pairs:
        bl = get_current_baseline(conn, region, domain)
        if bl:
            upd = update_baseline_impl(region, domain, window_size, weight_recent)
            update_results[f"{region}/{domain}"] = upd
            logger.info(
                f"[pipeline] baseline updated for {region}/{domain}: {upd.get('changed_fields')}"
            )

    conn.close()
    result["steps"]["update_baseline"] = update_results

    finished = datetime.now()
    duration = (finished - started).total_seconds()
    result["finished_at"] = finished.isoformat()
    result["duration_seconds"] = round(duration, 2)
    logger.info(f"[pipeline] finished in {duration:.1f}s")

    return result


def start_scheduler() -> BackgroundScheduler:
    """Start the background scheduler with cron jobs from config.

    Only starts if scheduler.enabled is True in config.
    Safe to call multiple times — returns existing scheduler if already running.
    """
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    cfg = get_config()
    sched_cfg = cfg.scheduler

    if not sched_cfg.enabled:
        logger.info("[scheduler] disabled by config")
        return None

    _scheduler = BackgroundScheduler(
        timezone="Asia/Shanghai",
        job_defaults={"max_instances": 1, "coalesce": True},
    )

    for time_str in sched_cfg.schedule_times:
        parts = time_str.strip().split(":")
        hour, minute = int(parts[0]), int(parts[1])
        _scheduler.add_job(
            run_probe_pipeline,
            "cron",
            hour=hour,
            minute=minute,
            id=f"probe_pipeline_{hour:02d}{minute:02d}",
            kwargs={
                "hours": sched_cfg.report_hours,
                "window_size": sched_cfg.update_window_size,
                "weight_recent": sched_cfg.update_weight_recent,
            },
        )
        logger.info(f"[scheduler] scheduled daily pipeline at {hour:02d}:{minute:02d}")

    _scheduler.start()
    logger.info("[scheduler] started")
    return _scheduler


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] stopped")
        _scheduler = None


def register(mcp):
    @mcp.tool()
    def run_scheduled_task(
        hours: int = 6,
        window_size: int = 30,
        weight_recent: float = 0.7,
    ) -> dict:
        """异步触发完整的探测流水线：采集→解析→对比→报告→更新基线。
        立即返回任务ID，流水线在后台执行。使用 get_pipeline_status 查询执行进度和结果。

        Args:
            hours: 回溯小时数，默认6小时
            window_size: 基线更新滑动窗口大小，默认30个样本
            weight_recent: 近期数据权重，默认0.7

        Returns:
            dict: 包含 task_id 和状态信息，通过 get_pipeline_status 查询完整结果
        """
        task_id = f"pipeline_{uuid.uuid4().hex[:8]}"

        with _pipeline_lock:
            _pipeline_tasks[task_id] = {
                "task_id": task_id,
                "status": "queued",
                "started_at": datetime.now().isoformat(),
                "current_step": "pending",
                "steps": {},
                "error": None,
            }

        thread = threading.Thread(
            target=_execute_pipeline_background,
            args=(task_id, hours, window_size, weight_recent),
            name=f"pipeline-{task_id}",
            daemon=True,
        )
        thread.start()

        return {
            "task_id": task_id,
            "status": "queued",
            "message": "流水线已在后台启动，使用 get_pipeline_status 查询进度",
        }

    @mcp.tool()
    def get_pipeline_status(task_id: str = "") -> dict:
        """查询探测流水线的执行状态和结果。

        Args:
            task_id: 任务ID（由 run_scheduled_task 返回）。为空则返回所有任务列表。

        Returns:
            dict: 任务状态信息，包含各步骤执行进度或完整结果
        """
        with _pipeline_lock:
            if not task_id:
                return {
                    "tasks": [
                        {
                            "task_id": tid,
                            "status": t.get("status"),
                            "current_step": t.get("current_step"),
                            "started_at": t.get("started_at"),
                            "duration_seconds": t.get("duration_seconds"),
                        }
                        for tid, t in _pipeline_tasks.items()
                    ]
                }

            task = _pipeline_tasks.get(task_id)
            if not task:
                return {"error": f"任务 {task_id} 不存在"}

            if task["status"] == "running":
                return {
                    "task_id": task["task_id"],
                    "status": task["status"],
                    "current_step": task["current_step"],
                    "started_at": task["started_at"],
                    "steps_completed": list(task["steps"].keys()),
                    "message": f"正在执行: {task['current_step']}",
                }

            result = {
                "task_id": task["task_id"],
                "status": task["status"],
                "started_at": task["started_at"],
                "finished_at": task.get("finished_at"),
                "duration_seconds": task.get("duration_seconds"),
            }
            if task["status"] == "failed":
                result["error"] = task.get("error")
            else:
                result["steps_summary"] = {
                    name: _summarize_step(name, data)
                    for name, data in task.get("steps", {}).items()
                }
            return result

    @mcp.tool()
    def get_scheduler_status() -> dict:
        """查看定时调度器状态，包括已配置的调度时间和下次执行时间。

        Returns:
            dict: 调度器运行状态、调度时间列表和下次执行时间
        """
        cfg = get_config()
        sched_cfg = cfg.scheduler

        if not sched_cfg.enabled:
            return {"running": False, "enabled": False}

        if _scheduler is None or not _scheduler.running:
            return {
                "running": False,
                "enabled": True,
                "schedule_times": sched_cfg.schedule_times,
            }

        jobs = []
        for job in _scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "next_run": str(job.next_run_time) if job.next_run_time else None,
                }
            )

        return {
            "running": True,
            "enabled": True,
            "schedule_times": sched_cfg.schedule_times,
            "jobs": jobs,
        }


def _summarize_step(name: str, data: any) -> dict:
    """Create a compact summary of a pipeline step result to keep MCP responses small."""
    if not isinstance(data, dict):
        return {"type": type(data).__name__}

    summary = {}
    if name == "collect":
        summary["regions"] = list(data.keys())
        summary["total_files"] = sum(
            v.get("files_downloaded", 0) if isinstance(v, dict) else 0
            for v in data.values()
        )
    elif name == "parse":
        summary["inserted"] = data.get("inserted")
        summary["skipped"] = data.get("skipped")
        summary["errors"] = data.get("errors")
    elif name == "compare":
        summary["pairs_compared"] = len(data)
        summary["alerts"] = {
            k: v.get("alerts", [])
            for k, v in data.items()
            if isinstance(v, dict)
            and v.get("alerts")
            and any("CRITICAL" in a or "WARNING" in a for a in v.get("alerts", []))
        }
    elif name == "report":
        summary["length"] = data.get("length")
        summary["saved"] = data.get("saved")
    elif name == "update_baseline":
        summary["regions_updated"] = list(data.keys())
        summary["changed_fields"] = {
            k: v.get("changed_fields") for k, v in data.items() if isinstance(v, dict)
        }
    else:
        summary["keys"] = list(data.keys())[:10]

    return summary
