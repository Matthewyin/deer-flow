import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from config import get_config
from db.database import get_connection, init_db
from db.models import (
    get_uningested_file_count,
    mark_raw_files_ingested,
    get_latest_metric_timestamp,
    get_all_region_domains,
    get_current_baseline,
)
from tools.parse_probe_results import parse_probe_results_impl
from tools.init_baseline import init_baseline_impl
from tools.update_baseline import update_baseline_impl

logger = logging.getLogger(__name__)

FRESHNESS_HOURS = 4
COLLECT_POLL_INTERVAL = 5
COLLECT_POLL_TIMEOUT = 120


def _is_fresh(latest_ts: Optional[str], hours: int) -> bool:
    if not latest_ts:
        return False
    try:
        latest_dt = datetime.fromisoformat(latest_ts.replace("Z", "+00:00").replace("+08:00", "+08:00"))
        if latest_dt.tzinfo:
            latest_dt = latest_dt.replace(tzinfo=None)
        return (datetime.now() - latest_dt) < timedelta(hours=hours)
    except (ValueError, TypeError):
        return False


def _trigger_data_manager_collect(base_url: str, regions: Optional[list[str]] = None) -> dict:
    url = f"{base_url}/api/probe/collect"
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, json={"regions": regions} if regions else {})
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error(f"Failed to trigger data-manager collect: {e}")
        return {"error": str(e)}


def _poll_collect_result(base_url: str, task_id: str) -> dict:
    url = f"{base_url}/api/probe/collect-result"
    import time
    elapsed = 0
    with httpx.Client(timeout=30) as client:
        while elapsed < COLLECT_POLL_TIMEOUT:
            try:
                resp = client.get(url, params={"task_id": task_id})
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status")
                    if status in ("completed", "done", "success"):
                        return data
                    if status in ("failed", "error"):
                        return {"error": f"collect failed: {data}"}
            except httpx.HTTPError:
                pass
            time.sleep(COLLECT_POLL_INTERVAL)
            elapsed += COLLECT_POLL_INTERVAL
    return {"error": "collect poll timed out"}


def _trigger_and_wait_collect(base_url: str, regions: list[str]) -> dict:
    trigger = _trigger_data_manager_collect(base_url, regions)
    if "error" in trigger:
        return trigger
    task_id = trigger.get("task_id")
    if not task_id:
        return trigger
    return _poll_collect_result(base_url, task_id)


def _update_baselines_for_regions(conn, regions: list[str]) -> list[dict]:
    baseline_results = []
    all_pairs = get_all_region_domains(conn)
    for region, domain in all_pairs:
        if region not in regions:
            continue
        existing = get_current_baseline(conn, region, domain)
        try:
            if existing:
                result = update_baseline_impl(region, domain)
            else:
                result = init_baseline_impl(region, domain)
            baseline_results.append({"region": region, "domain": domain, **result})
        except Exception as e:
            logger.error(f"baseline update failed for {region}/{domain}: {e}")
            baseline_results.append({"region": region, "domain": domain, "error": str(e)})
    return baseline_results


def ensure_probe_data_impl(regions: Optional[list[str]] = None) -> dict:
    cfg = get_config()
    init_db(cfg.sqlite.db_path)
    conn = get_connection(cfg.sqlite.db_path)

    if not regions:
        regions = list(cfg.probe.nodes.keys())

    base_url = cfg.data_manager_url
    result = {"regions": {}}

    for region in regions:
        steps = []

        # Step 1: Check freshness
        latest_ts = get_latest_metric_timestamp(conn, region)
        if _is_fresh(latest_ts, FRESHNESS_HOURS):
            result["regions"][region] = {
                "status": "fresh",
                "latest_metric": latest_ts,
                "steps": ["freshness_check_passed"],
            }
            continue
        steps.append(f"stale_data(last={latest_ts})")

        # Step 2: Check for uningested files
        uningested = get_uningested_file_count(conn, region)
        steps.append(f"uningested={uningested}")

        if uningested == 0:
            # No uningested files → trigger data-manager to collect
            steps.append("trigger_collect")
            collect_result = _trigger_and_wait_collect(base_url, [region])
            if "error" in collect_result:
                result["regions"][region] = {
                    "status": "error",
                    "steps": steps,
                    "error": collect_result["error"],
                }
                continue
            steps.append("collect_done")

            # Re-check uningested after collection
            uningested = get_uningested_file_count(conn, region)
            steps.append(f"after_collect_uningested={uningested}")
            if uningested == 0:
                result["regions"][region] = {
                    "status": "no_data",
                    "steps": steps,
                }
                continue

        # Step 3: Ingest uningested files
        steps.append("ingest")
        parse_result = parse_probe_results_impl([region])
        steps.append(f"parsed={parse_result.get('json', {}).get(region, {})}")

        # Step 4: Mark as ingested
        marked = mark_raw_files_ingested(conn, region)
        steps.append(f"marked_ingested={marked}")

        # Step 5: Update baselines
        steps.append("update_baselines")
        baseline_results = _update_baselines_for_regions(conn, [region])

        result["regions"][region] = {
            "status": "updated",
            "steps": steps,
            "baselines": baseline_results,
        }

    conn.close()
    return result


def register(mcp):
    @mcp.tool()
    def ensure_probe_data(regions: Optional[list[str]] = None) -> dict:
        """智能探测数据保障工具：检查数据新鲜度，必要时触发采集→入库→基线更新。
        当数据过期时自动执行完整pipeline：(1)检查待入库文件 (2)若无则触发data-manager采集
        (3)解析入库 (4)标记已入库 (5)更新基线。

        Args:
            regions: 要保障的region列表，为空则检查全部6个节点

        Returns:
            dict: 每个region的状态和执行步骤详情
        """
        return ensure_probe_data_impl(regions)
