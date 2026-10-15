# -*- coding: utf-8 -*-
"""컨셉 스튜디오 MCP 를 실제 stdio 로 띄워 도구 하나를 부른다(Claude 데스크톱과 같은 연결 방식 시험용).

  python tools/concept_studio/mcp_call.py <도구> '<json 인자>'
  예) python tools/concept_studio/mcp_call.py studio_start '{"concept":"인물형","seed":"안세영 | ..."}'
      인자 대신 @파일.json 을 주면 파일에서 읽는다.
"""
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


async def main(tool, args):
    params = StdioServerParameters(command=sys.executable, args=["-m", "shopping_shorts.concept_studio.mcp_server"],
                                   cwd=ROOT, env=dict(os.environ, PYTHONUTF8="1", PYTHONPATH=ROOT))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            if tool == "list":
                print([t.name for t in (await s.list_tools()).tools])
                return
            res = await s.call_tool(tool, args)
            for c in res.content:
                print(getattr(c, "text", c))


if __name__ == "__main__":
    a = sys.argv[2] if len(sys.argv) > 2 else "{}"
    if a.startswith("@"):
        a = open(a[1:], encoding="utf-8").read()
    asyncio.run(main(sys.argv[1], json.loads(a)))
