import json
import logging
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


def run_probe_pipeline(
    hours: int = 6,
    window_size: int = 30,
    weight_recent: float = 0.7,
) -> dict:
    """Execute the full probe pipeline: collect → parse → compare → report → update baseline."""
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
    """Start the background scheduler with cron jobs from config."""
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
        """手动触发完整的探测流水线：采集→解析→对比→报告→更新基线。
        执行与定时调度相同的逻辑，用于按需执行或测试。

        Args:
            hours: 回溯小时数，默认6小时
            window_size: 基线更新滑动窗口大小，默认30个样本
            weight_recent: 近期数据权重，默认0.7

        Returns:
            dict: 各步骤执行结果和耗时
        """
        return run_probe_pipeline(
            hours=hours, window_size=window_size, weight_recent=weight_recent
        )

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
