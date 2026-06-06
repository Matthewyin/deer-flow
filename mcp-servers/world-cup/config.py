import os
from dataclasses import dataclass


@dataclass
class WorldCupConfig:
    db_path: str = "/app/backend/.deer-flow/db/world_cup.db"
    data_dir: str = "/app/.deer-flow/world-cup"


def get_config() -> WorldCupConfig:
    return WorldCupConfig(
        db_path=os.getenv("WORLD_CUP_DB_PATH", "/app/backend/.deer-flow/db/world_cup.db"),
        data_dir=os.getenv("WORLD_CUP_DATA_DIR", "/app/.deer-flow/world-cup"),
    )
