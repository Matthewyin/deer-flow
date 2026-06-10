import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastmcp import FastMCP

from config import get_config


def _build_payload(content: str, msgtype: str) -> dict[str, Any]:
    if msgtype == "text":
        return {"msgtype": "text", "text": {"content": content}}
    if msgtype == "markdown":
        return {"msgtype": "markdown", "markdown": {"content": content}}
    raise ValueError("msgtype only supports 'markdown' or 'text'")


def _post_json(url: str, payload: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        return {
            "ok": False,
            "status": exc.code,
            "error": exc.reason,
        }
    except URLError as exc:
        return {
            "ok": False,
            "error": str(exc.reason),
        }

    try:
        data = json.loads(response_body)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": "response is not JSON",
        }

    errcode = data.get("errcode")
    return {
        "ok": errcode == 0,
        "errcode": errcode,
        "errmsg": data.get("errmsg", ""),
    }


def send_wecom_group_message(content: str, msgtype: str = "markdown") -> dict:
    content = content.strip()
    msgtype = msgtype.strip().lower()
    if not content:
        return {
            "ok": False,
            "error": "content is required",
        }

    cfg = get_config().wecom_group_bot
    if not cfg.webhook_urls:
        return {
            "ok": False,
            "error": "WECOM_GROUP_BOT_WEBHOOK_URLS is not configured",
        }

    try:
        payload = _build_payload(content, msgtype)
    except ValueError as exc:
        return {
            "ok": False,
            "error": str(exc),
        }

    results = []
    for index, url in enumerate(cfg.webhook_urls, start=1):
        result = _post_json(url, payload, cfg.timeout_seconds)
        results.append(
            {
                "index": index,
                **result,
            }
        )

    failed = [item for item in results if not item.get("ok")]
    return {
        "ok": not failed,
        "total": len(results),
        "succeeded": len(results) - len(failed),
        "failed": len(failed),
        "results": results,
    }


def register(mcp: FastMCP):
    @mcp.tool()
    def wecom_group_bot_send(content: str, msgtype: str = "markdown") -> dict:
        """向已配置的企业微信群聊机器人发送相同消息。

        Args:
            content: 要发送的消息正文。
            msgtype: 消息类型，支持 markdown 或 text，默认 markdown。

        Returns:
            dict: 每个 webhook 的发送结果；不会返回 webhook 原始 URL。
        """
        return send_wecom_group_message(content, msgtype)
