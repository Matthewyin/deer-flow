import logging
import os
from typing import Optional

import paramiko

from config import get_config
from db.database import get_connection, init_db
from db.models import insert_raw_file, get_collected_files

logger = logging.getLogger(__name__)

MAX_JSON_PER_RUN = 200


def _ssh_list_tgz(ssh_client: paramiko.SSHClient, remote_path: str) -> list[str]:
    _, stdout, _ = ssh_client.exec_command(f"ls {remote_path}/prob_*.tgz 2>/dev/null")
    return [os.path.basename(line.strip()) for line in stdout if line.strip()]


def collect_probe_data_impl(regions: Optional[list[str]] = None) -> dict:
    """Core logic for incremental probe data collection from ECS nodes."""
    cfg = get_config()
    init_db(cfg.sqlite.db_path)
    conn = get_connection(cfg.sqlite.db_path)

    if not regions:
        regions = list(cfg.probe.nodes.keys())

    results = {}
    for region in regions:
        node = cfg.probe.nodes.get(region)
        if not node:
            results[region] = {"error": f"unknown region: {region}"}
            continue

        local_dir = os.path.join(cfg.probe.local_raw_dir, region)
        os.makedirs(local_dir, exist_ok=True)

        remote_base = cfg.probe.remote_base
        summary = {"tgz_new": 0, "tgz_total": 0, "json_new": 0, "json_skipped": 0}

        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                node["ip"],
                port=cfg.probe.ssh_port,
                username=cfg.probe.ssh_user,
                timeout=30,
                look_for_keys=True,
            )
            sftp = ssh.open_sftp()

            # --- Phase 1: Collect tgz archives ---
            existing_tgz = set(get_collected_files(conn, region, "tgz"))
            remote_tgz = _ssh_list_tgz(ssh, remote_base)
            summary["tgz_total"] = len(remote_tgz)

            for fname in remote_tgz:
                if fname in existing_tgz:
                    continue
                local_path = os.path.join(local_dir, fname)
                if not os.path.exists(local_path):
                    remote_file = f"{remote_base}/{fname}"
                    sftp.get(remote_file, local_path)
                fsize = os.path.getsize(local_path)
                insert_raw_file(conn, region, fname, "tgz", fsize, "")
                summary["tgz_new"] += 1

            # --- Phase 2: Collect latest JSON files ---
            json_dir = os.path.join(local_dir, "domain_based")
            os.makedirs(json_dir, exist_ok=True)

            existing_json = set(get_collected_files(conn, region, "json"))

            cmd = (
                f"find {remote_base}/domain_based/ -name '*.json' "
                f"-mtime -1 -exec basename {{}} \\; "
                f"| sort -r | head -{MAX_JSON_PER_RUN}"
            )
            _, stdout, _ = ssh.exec_command(cmd)
            new_json = [line.strip() for line in stdout if line.strip()]

            for fname in new_json:
                if fname in existing_json:
                    summary["json_skipped"] += 1
                    continue
                local_path = os.path.join(json_dir, fname)
                if not os.path.exists(local_path):
                    remote_file = f"{remote_base}/domain_based/{fname}"
                    sftp.get(remote_file, local_path)
                fsize = os.path.getsize(local_path)
                insert_raw_file(conn, region, fname, "json", fsize, "")
                summary["json_new"] += 1

            conn.commit()

            sftp.close()
            ssh.close()
            results[region] = summary

        except Exception as e:
            logger.error(f"collect_probe_data error for {region}: {e}")
            results[region] = {"error": str(e)}

    conn.close()
    return results


def register(mcp):
    @mcp.tool()
    def collect_probe_data(regions: Optional[list[str]] = None) -> dict:
        """从ECS节点增量采集探测数据（tgz归档+最新JSON）。通过SSH免密连接，
        对比本地已采集文件列表，仅下载缺失的文件。

        Args:
            regions: 要采集的region列表，为空则采集全部6个节点

        Returns:
            dict: 每个region的采集统计 {region: {tgz_new, tgz_total, json_new}}
        """
        return collect_probe_data_impl(regions)
