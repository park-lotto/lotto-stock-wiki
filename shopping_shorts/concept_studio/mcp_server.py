# -*- coding: utf-8 -*-
"""숏템 컨셉 스튜디오 MCP — 고객 Claude 데스크톱이 부르는 도구(Claude형, 관제 213).

도구는 core 를 부르기만 한다(판단은 core 한 곳). 무거운 일은 core 가 따로 띄운 작업 프로세스가 한다.
실행: python -m shopping_shorts.concept_studio.mcp_server   (stdio)
"""
from mcp.server.mcpserver import MCPServer

from shopping_shorts.concept_studio import core

mcp = MCPServer(
    "shottem-studio",
    instructions=(
        "숏템 컨셉 스튜디오. 고객이 '스튜디오 설정대로 OO 만들어줘'라고 하면: "
        "⓪ 처음이거나 고객이 웹에서 설정을 바꿨다고 하면 studio_sync 로 받아 온다. "
        "① studio_concepts 로 컨셉을 보고 ② studio_start(concept, seed) 로 시작한다. "
        "③ studio_status 가 need_script 면 prompt 의 지시를 그대로 따라 **요청한 형식(JSON)만** 써서 "
        "studio_submit_script 로 넣는다(사실은 prompt 안 자료에 있는 것만). 반려가 오면 다시 쓴다. "
        "④ confirm_script 면 대본을 고객에게 보여 주고 확인을 받아 studio_confirm 을 부른다. "
        "⑤ running 이면 잠시 뒤 다시 status. done 이면 final 경로를 알려 준다. failed 면 이유를 그대로 전한다."),
)


@mcp.tool()
def studio_sync() -> dict:
    """웹 컨셉 스튜디오에 저장한 컨셉·내 설정·팩(글꼴·효과음·배경음)을 이 PC로 받는다. 처음 한 번, 설정을 바꾼 뒤마다."""
    return core.sync()


@mcp.tool()
def studio_concepts() -> list:
    """쓸 수 있는 컨셉 목록(이름·필요한 소재 형식)."""
    return core.list_concepts()


@mcp.tool()
def studio_start(concept: str, seed: str) -> dict:
    """컨셉으로 새 작업을 시작한다. seed 는 컨셉의 source_hint 형식(예: '안세영 | 배드민턴 세계 1위가 되기까지')."""
    jid = core.start_job(concept, seed)
    return {"job_id": jid, "next": "studio_status 로 상태 확인"}


@mcp.tool()
def studio_status(job_id: str) -> dict:
    """작업 상태. state: queued|running|need_script|confirm_script|failed|done."""
    return core.status(job_id)


@mcp.tool()
def studio_submit_script(job_id: str, text: str) -> dict:
    """need_script 일 때 prompt 에 맞춰 쓴 대본(요청한 JSON)을 넣는다."""
    core.submit_script(job_id, text)
    return {"ok": True, "next": "studio_status"}


@mcp.tool()
def studio_confirm(job_id: str, ok: bool = True, note: str = "") -> dict:
    """대본 확인. ok=False 면 note(고칠 점)를 붙여 다시 쓰게 한다."""
    core.confirm_script(job_id, ok, note)
    return {"ok": True, "next": "studio_status"}


@mcp.tool()
def studio_resume(job_id: str) -> dict:
    """멈춘 작업(queued·running 인데 진행이 없을 때)을 이어서 돌린다."""
    core.resume(job_id)
    return {"ok": True, "next": "studio_status"}


if __name__ == "__main__":
    mcp.run()
