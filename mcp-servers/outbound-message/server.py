from fastmcp import FastMCP

mcp = FastMCP(
    "outbound-message",
    instructions=(
        "外发消息工具集：负责将明确需要外发的文本消息发送到外部消息通道。"
        "当前支持企业微信群聊机器人 webhook。"
    ),
)

from tools.wecom_group_bot import register as register_wecom_group_bot

register_wecom_group_bot(mcp)


if __name__ == "__main__":
    mcp.run()
