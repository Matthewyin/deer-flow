from collections.abc import Iterable


def clean_name(value: str) -> str:
    return value.strip().strip('"').strip("'")


def split_blocks(text: str, delimiter: str = "#") -> list[str]:
    blocks: list[str] = []
    current: list[str] = []

    for line in text.splitlines():
        if line.strip() == delimiter:
            if current:
                blocks.append("\n".join(current).strip())
                current = []
            continue
        current.append(line.rstrip())

    if current:
        blocks.append("\n".join(current).strip())

    return [block for block in blocks if block]


def bool_from_text(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in {"enable", "enabled", "yes", "true", "on"}:
        return True
    if normalized in {"disable", "disabled", "no", "false", "off"}:
        return False
    return None


def normalize_list(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    else:
        values = list(value)
    return [clean_name(item) for item in values if clean_name(item)]
