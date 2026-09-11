"""Local terminal handoff. Approval evidence is an operator attestation, not authentication.

Never infer user approval from a discussion. Submit only the exact approved payload.
This command persists a queue entry; it does not invoke models or send customer messages.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .app import ProjectCreate
from .catalog import COMPANY_IDS, TEAM_IDS
from .store import Store


class TerminalReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=120)
    session_ref: str = Field(min_length=1, max_length=500)
    approval_ref: str = Field(min_length=1, max_length=1000)
    approval_text: str = Field(min_length=1, max_length=4000)

    @field_validator('*', mode='before')
    @classmethod
    def strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class Handoff(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project: ProjectCreate
    receipt: TerminalReceipt


def submit(db: Path, payload: dict, *, confirmed: bool) -> dict:
    if not confirmed:
        raise ValueError("명시적인 대표 컨펌을 확인한 후에만 전달할 수 있습니다.")
    handoff = Handoff.model_validate(payload)
    if handoff.project.company_id not in COMPANY_IDS or handoff.project.team_id not in TEAM_IDS:
        raise ValueError("알 수 없는 회사 또는 팀입니다.")
    store = Store(db)
    store.initialize()
    return store.create_project(**handoff.project.model_dump(), terminal_receipt=handoff.receipt.model_dump())


def main():
    parser = argparse.ArgumentParser(description="대표가 터미널에서 컨펌한 지시를 운영실에 전달합니다.")
    parser.add_argument('--db', type=Path, required=True, help="운영실 서버와 동일한 로컬 DB 경로")
    parser.add_argument('--file', type=Path, required=True, help="컨펌된 지시와 승인 근거가 담긴 UTF-8 JSON")
    parser.add_argument('--confirmed-by-user', action='store_true', help="전달자가 명시적 사용자 컨펌을 확인했음")
    args = parser.parse_args()
    try:
        project = submit(args.db, json.loads(args.file.read_text(encoding='utf-8-sig')),
                         confirmed=args.confirmed_by_user)
    except Exception as exc:
        parser.exit(1, f"전달 실패: {exc}\n")
    print(json.dumps({'project_id':project['id'], 'status':'접수 저장',
                      'assignee':project['current_assignee'], 'ai_execution':'미연결'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
