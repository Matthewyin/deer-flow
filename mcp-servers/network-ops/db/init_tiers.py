import re
import os


def parse_tiers_from_md(md_path: str = "docs/bandwidth.md") -> list[tuple]:
    tiers = []
    if not os.path.exists(md_path):
        md_path = os.path.join("..", "..", "..", md_path)

    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        if "当前单线带宽" in line or not line.strip():
            continue

        parts = [p.strip() for p in line.split("\t") if p.strip()]
        if len(parts) < 6:
            continue

        try:
            current_bw = int(parts[0].split()[0])
            scale_up_threshold = float(re.search(r"[\d.]+", parts[1]).group())
            scale_up_target = int(parts[2].split()[0])

            scale_down_threshold = None
            if parts[3] != "-":
                scale_down_threshold = float(re.search(r"[\d.]+", parts[3]).group())

            scale_down_target = None
            if parts[4] != "-":
                scale_down_target = int(parts[4].split()[0])

            description = parts[5]

            tiers.append(
                (
                    current_bw,
                    scale_up_threshold,
                    scale_up_target,
                    scale_down_threshold,
                    scale_down_target,
                    description,
                )
            )
        except (ValueError, AttributeError, IndexError):
            continue

    return tiers


if __name__ == "__main__":
    try:
        tiers = parse_tiers_from_md()
        for t in tiers:
            print(t)
    except Exception as e:
        print(f"Test failed: {e}")
