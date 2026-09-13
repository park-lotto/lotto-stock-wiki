"""Exercise the actual stdio MCP protocol, not a direct socket replacement.

Run with the installed blender-mcp venv Python. Optional --script sends a
reviewed modeling script through the upstream safe-mode validation.
"""
import argparse
import asyncio
import os
from pathlib import Path
from datetime import timedelta
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

INSTALL = Path(os.environ['LOCALAPPDATA']) / 'Programs/MakersLab-Blender/blender-mcp'

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--script', type=Path)
    args = parser.parse_args()
    server = StdioServerParameters(
        command=str(INSTALL / '.venv/Scripts/blender-mcp.exe'),
        env={'DISABLE_TELEMETRY': 'true', 'BLENDER_MCP_SAFE_MODE': '1',
             'BLENDER_HOST': '127.0.0.1', 'BLENDER_PORT': '9876',
             'BLENDERMCP_ADDONS_DIR': str(INSTALL.parent / 'profile/scripts/addons'),
             'PYTHONIOENCODING': 'utf-8'},
    )
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=180)) as session:
            initialized = await session.initialize()
            print('MCP_INITIALIZED', initialized.serverInfo)
            tools = await session.list_tools()
            assert any(t.name == 'execute_blender_code' for t in tools.tools)
            print('TOOLS', len(tools.tools))
            calls = [('get_addon_status', {}), ('get_scene_info', {})]
            if args.script:
                output = Path(__file__).resolve().parents[1] / '.artifacts'
                calls.append(('execute_blender_code', {'code': 'OUTPUT_DIR = ' + repr(str(output)) + '\n' + args.script.read_text(encoding='utf-8')}))
            for name, params in calls:
                params['user_prompt'] = '설치 연결해서 진행해'
                result = await session.call_tool(name, params)
                body = '\n'.join(c.text for c in result.content if c.type == 'text')
                print(name, body)
                assert not result.isError, body
                assert not any(s in body for s in ['Error executing', 'Error getting', 'Rejected by safe mode', 'Could not determine']), body
                if name == 'get_addon_status':
                    assert '"telemetry_consent": false' in body, body

if __name__ == '__main__':
    asyncio.run(main())
