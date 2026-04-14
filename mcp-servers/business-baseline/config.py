import os
from dataclasses import dataclass


@dataclass
class SQLiteConfig:
    db_path: str = ".deer-flow/db/business_baseline.db"


@dataclass
class FileConfig:
    everybusiness_path: str = "/app/docs/businessInfo/everybusiness"
    report_separator: str = os.getenv("REPORT_SEPARATOR", "XXX技术服务台")


@dataclass
class ServerConfig:
    sqlite: SQLiteConfig = None
    file: FileConfig = None

    def __post_init__(self):
        if self.sqlite is None:
            self.sqlite = SQLiteConfig(
                db_path=os.getenv(
                    "BUSINESS_DB_PATH", ".deer-flow/db/business_baseline.db"
                ),
            )
        if self.file is None:
            self.file = FileConfig(
                everybusiness_path=os.getenv(
                    "EVERYBUSINESS_FILE_PATH", "/app/docs/businessInfo/everybusiness"
                ),
                report_separator=os.getenv("REPORT_SEPARATOR", "XXX技术服务台"),
            )


def get_config() -> ServerConfig:
    return ServerConfig()
