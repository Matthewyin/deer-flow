import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.database import get_connection, init_db  # noqa: E402
from db.models import get_metrics_for_key, insert_daily_report, insert_metric  # noqa: E402


def test_get_metrics_for_key_limits_by_report_dates(tmp_path):
    db_path = tmp_path / "business_baseline.db"
    init_db(str(db_path))
    conn = get_connection(str(db_path))

    try:
        for day in ["2026-05-28", "2026-05-29", "2026-05-30", "2026-05-31"]:
            insert_daily_report(conn, day, "00:00", day, day, "raw")
            for sub_name in [None, "传统终端", "安卓终端"]:
                insert_metric(
                    conn,
                    {
                        "report_date": day,
                        "category": "terminal",
                        "metric_key": "online_terminals",
                        "metric_name": "在线终端数",
                        "sub_name": sub_name,
                        "extra_value": 1,
                        "unit": "台",
                    },
                )

        rows = get_metrics_for_key(conn, "online_terminals", limit=3)
    finally:
        conn.close()

    assert len(rows) == 9
    assert sorted({r["report_date"] for r in rows}) == [
        "2026-05-29",
        "2026-05-30",
        "2026-05-31",
    ]
