"""Ops Knowledge MCP Server.

Provides tools for ops knowledge base management:
semantic search, document upload, and knowledge browsing.
"""

from fastmcp import FastMCP

mcp = FastMCP(
    "ops-knowledge",
    instructions="运维知识库工具集：提供知识文档入库、语义检索和文档浏览能力。",
)

from tools.knowledge_search import register as register_knowledge_search
from tools.knowledge_upload import register as register_knowledge_upload
from tools.knowledge_list import register as register_knowledge_list

register_knowledge_search(mcp)
register_knowledge_upload(mcp)
register_knowledge_list(mcp)

if __name__ == "__main__":
    mcp.run()
