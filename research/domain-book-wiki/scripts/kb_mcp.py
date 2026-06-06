#!/usr/bin/env python3

"""
kb_mcp.py — 知识图谱 MCP 服务器（原生 JSON-RPC stdio 实现）

对外部工具（Hermes Agent / Claude Code）暴露 4 个工具：
  kb_query, kb_search, kb_trace, kb_validate

协议：JSON-RPC 2.0 over stdin/stdout
状态：✅ 协议实现正确，需手动注册到 MCP 系统

直接运行（测试）：
  python3 kb_mcp.py --wiki /path/to/wiki_root

使用 mcporter 注册到 Hermes Agent：
  mcporter serve python3 /path/to/kb_mcp.py --wiki /path/to/wiki_root --build

使用 native-mcp 注册（在 skill.yaml / config 中添加）：
  native_mcp_commands:
    - name: kb-mcp
      command: python3
      args: ["/path/to/kb_mcp.py", "--wiki", "/path/to/wiki_root", "--build"]

说明：
  - 本文件实现了标准 MCP 协议（tools/list + tools/call），通过 stdio 通信。
  - 未使用装饰器/@tool 模式，手动处理 JSON-RPC 请求，兼容性更广。
  - Hermes Agent 不自带 MCP 注册能力，需通过 mcporter 或 native-mcp 技能桥接。
"""

import argparse
import json
import os
import sys

# 启动时建图
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb_graph import KGraph

parser = argparse.ArgumentParser()
parser.add_argument("--wiki", required=True, help="知识库根目录")
parser.add_argument("--build", action="store_true", help="启动时自动建图")
args = parser.parse_args()

kg = KGraph(args.wiki)
if args.build or not os.path.exists(kg.db_path):
    kg.build()

TOOLS = [
    {
        "name": "kb_query",
        "description": "按名称查询知识库节点，返回节点信息 + 一级关联图（入边+出边）",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "节点名称，如：传导耦合"}},
            "required": ["name"],
        },
    },
    {
        "name": "kb_search",
        "description": "跨所有节点类型全文搜索",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "搜索关键词，如：辐射 耦合"}},
            "required": ["text"],
        },
    },
    {
        "name": "kb_trace",
        "description": "追踪一个节点的下游影响链（概念→KE→KP→SP→场景）",
        "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    },
    {
        "name": "kb_validate",
        "description": "知识图谱质量检查：孤立节点、断链、置信度异常",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def main():
    """MCP stdio server 主循环：从 stdin 读取 JSON-RPC 请求，处理并返回结果。"""
    for line in sys.stdin:
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        if method == "tools/list":
            resp = {"tools": TOOLS}
        elif method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments", {})
            try:
                if name == "kb_query":
                    result = kg.query(arguments.get("name", ""))
                elif name == "kb_search":
                    result = kg.search(arguments.get("text", ""))
                elif name == "kb_trace":
                    result = kg.trace(arguments.get("name", ""))
                elif name == "kb_validate":
                    result = kg.validate()
                else:
                    raise ValueError(f"Unknown tool: {name}")
                resp = {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}]}
            except Exception as e:
                resp = {"isError": True, "content": [{"type": "text", "text": str(e)}]}
        else:
            resp = {}

        sys.stdout.write(json.dumps({"id": req_id, "result": resp}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
