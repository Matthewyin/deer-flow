import os
from dataclasses import dataclass, field


@dataclass
class SQLiteConfig:
    db_path: str = ".deer-flow/db/remote_probe.db"


@dataclass
class ProbeConfig:
    ssh_user: str = "root"
    ssh_port: int = 22
    remote_base: str = "/root/tools/probing/network-diagnosis/output/probe_lottery"
    local_raw_dir: str = ".deer-flow/probe/raw"
    local_report_dir: str = ".deer-flow/probe/reports"
    nodes: dict = field(
        default_factory=lambda: {
            "hhht": {"ip": "39.104.209.139", "city": "呼和浩特"},
            "wh": {"ip": "47.122.115.139", "city": "武汉"},
            "hz": {"ip": "116.62.131.213", "city": "杭州"},
            "wlcb": {"ip": "8.130.82.52", "city": "乌兰察布"},
            "qd": {"ip": "120.27.112.200", "city": "青岛"},
            "cd": {"ip": "47.108.239.135", "city": "成都"},
        }
    )


@dataclass
class SchedulerConfig:
    enabled: bool = True
    schedule_times: list = field(default_factory=lambda: ["11:00", "17:00"])
    report_hours: int = 6
    update_window_size: int = 30
    update_weight_recent: float = 0.7


@dataclass
class ServerConfig:
    sqlite: SQLiteConfig = None
    probe: ProbeConfig = None
    scheduler: SchedulerConfig = None

    def __post_init__(self):
        if self.sqlite is None:
            self.sqlite = SQLiteConfig(
                db_path=os.getenv(
                    "REMOTE_PROBE_DB_PATH", ".deer-flow/db/remote_probe.db"
                ),
            )
        if self.probe is None:
            self.probe = ProbeConfig(
                ssh_user=os.getenv("PROBE_SSH_USER", "root"),
                ssh_port=int(os.getenv("PROBE_SSH_PORT", "22")),
                remote_base=os.getenv(
                    "PROBE_REMOTE_BASE",
                    "/root/tools/probing/network-diagnosis/output/probe_lottery",
                ),
                local_raw_dir=os.getenv("PROBE_RAW_DIR", ".deer-flow/probe/raw"),
                local_report_dir=os.getenv(
                    "PROBE_REPORT_DIR", ".deer-flow/probe/reports"
                ),
            )
        if self.scheduler is None:
            times_str = os.getenv("PROBE_SCHEDULE_TIMES", "11:00,17:00")
            self.scheduler = SchedulerConfig(
                enabled=os.getenv("PROBE_SCHEDULER_ENABLED", "true").lower() == "true",
                schedule_times=[t.strip() for t in times_str.split(",") if t.strip()],
                report_hours=int(os.getenv("PROBE_REPORT_HOURS", "6")),
                update_window_size=int(os.getenv("PROBE_UPDATE_WINDOW", "30")),
                update_weight_recent=float(os.getenv("PROBE_UPDATE_WEIGHT", "0.7")),
            )


def get_config() -> ServerConfig:
    return ServerConfig()
