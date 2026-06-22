"""종합엔진: 종목/섹터 페이지를 신규 원자로 차분병합. 설계 §4.2/4.2b.

⚠️ claude -p 경로(_call_sonnet)는 신뢰불가로 폐기 — 에이전트가 stdout에 잡담/요약을
섞거나 페이지 대신 변경요약문만 반환해 골드 페이지를 파괴한 사례 발생(2026-06-22 삼성전자).
종합은 서브에이전트가 파일을 직접 쓰는 방식으로 전환(설계 §4.2 개정). _build_prompt는 유지.
어떤 경로든 결과를 쓰기 전 validate_synthesis() 가드를 통과해야 한다.
"""
from pathlib import Path

_MODEL = "sonnet"

# 변경요약문/잡담 오염 신호 (페이지가 아니라 설명을 반환한 경우)
_POLLUTION = ("변경 사항 요약", "변경사항 요약", "갱신 완료", "다음과 같이 갱신", "## 변경")


def validate_synthesis(old_md: str, new_md: str, *, min_ratio: float = 0.6) -> None:
    """종합 결과를 페이지에 쓰기 전 안전 검증. 위반 시 예외(쓰기 금지).

    - 길이가 원본의 min_ratio 미만 → 페이지 파괴 의심.
    - 변경요약문/잡담 마커 포함 → 결과물이 아니라 설명 반환 의심.
    """
    if len(new_md) < len(old_md) * min_ratio:
        raise ValueError(
            f"종합 결과가 원본의 {min_ratio*100:.0f}% 미만 "
            f"({len(new_md)} < {len(old_md)}) — 페이지 파괴 의심, 쓰기 거부"
        )
    head = new_md[:400]
    for mark in _POLLUTION:
        if mark in head:
            raise ValueError(f"종합 결과 상단에 잡담/요약 마커 '{mark}' — 쓰기 거부")

_RULES = """너는 주식 위키 종합 편집자다. 아래 [현재 페이지]에 [신규 원자]를 녹여 갱신본을 출력하라.
철칙:
1. 출처는 신규 원자의 sources에 있는 **실존 파일명만** 인용. 두 파일을 합치거나 새 파일명을 지어내지 마라.
2. 원자에 없는 사실을 만들지 마라. 모르면 적지 마라. (할루시네이션 금지)
3. 검증등급에 따라: '검증완료'면 확인된 사실이니 태그 없이 쓴다(증권사 리포트 등). '미검증'이면 `⚠️미검증`, '설'이면 `(설)`을 붙여라. 절대 검증완료에 미검증 태그를 붙이지 마라.
4. 섹션 규칙: 최신 이벤트=7일 롤링 표 상단 추가 / 증권사 컨센서스=증권사당 1행 덮어쓰기 / 리포트 논거=30일 롤링 WHY보존 / 종합 스토리=최신 단락 상단 추가.
5. 기존 골드 내용은 보존하고 신규만 추가/갱신하라.
출력은 갱신된 마크다운 전체. 설명 문장 없이 마크다운만."""


def _build_prompt(page_md: str, atoms: list[dict]) -> str:
    lines = ["[신규 원자]"]
    for a in atoms:
        srcs = " · ".join(a.get("sources") or [a.get("raw_file", "?")])
        grade = (a.get("verdict") or {}).get("grade", a.get("certainty", "불명"))
        lines.append(f"- [{a.get('date','?')}] (검증={grade}) {a['content']}  ← {srcs}")
    atoms_block = "\n".join(lines)
    return f"{_RULES}\n\n[현재 페이지]\n{page_md}\n\n{atoms_block}"


def _call_sonnet(prompt: str) -> str:
    """Claude Code 헤드리스로 종합 (Max 구독, 추가 API 과금 없음).
    프롬프트는 stdin으로 전달(Windows argv 길이 한도 회피). anthropic SDK 금지."""
    import subprocess
    r = subprocess.run(
        ["claude", "-p", "--model", _MODEL],
        input=prompt, capture_output=True, text=True, encoding="utf-8",
        timeout=300,
    )
    if r.returncode != 0:
        raise RuntimeError(f"claude -p 실패: {r.stderr[:300]}")
    return r.stdout.strip()


def synth_stock(page_path: Path, atoms: list[dict], *, dry_run: bool = False) -> str:
    page_md = page_path.read_text(encoding="utf-8")
    prompt = _build_prompt(page_md, atoms)
    if dry_run:
        return prompt
    updated = _call_sonnet(prompt)
    validate_synthesis(page_md, updated)   # 파괴 방지 가드
    page_path.write_text(updated, encoding="utf-8")
    return updated


_SECTOR_RULES = """너는 섹터 위키 편집자다. [현재 섹터페이지]의 "시장 국면·테마 코멘트" 섹션에 [신규 원자]를 녹여라.
철칙은 종목과 동일(실존출처만·할루시네이션금지). 검증등급 '검증완료'는 태그 없이, '미검증'은 ⚠️미검증, '설'은 (설)을 붙여라. 개별 종목 깊이가 아니라 섹터 전체 국면·수급·테마 흐름을 종합하라.
출력은 갱신된 마크다운 전체."""


def _build_sector_prompt(page_md: str, atoms: list[dict]) -> str:
    lines = ["[신규 원자]"]
    for a in atoms:
        srcs = " · ".join(a.get("sources") or [a.get("raw_file", "?")])
        grade = (a.get("verdict") or {}).get("grade", a.get("certainty", "불명"))
        lines.append(f"- [{a.get('date','?')}] (검증={grade}) {a['content']}  ← {srcs}")
    return f"{_SECTOR_RULES}\n\n[현재 섹터페이지]\n{page_md}\n\n" + "\n".join(lines)


def synth_sector(sector_page: Path, atoms: list[dict], *, dry_run: bool = False) -> str:
    page_md = sector_page.read_text(encoding="utf-8")
    prompt = _build_sector_prompt(page_md, atoms)
    if dry_run:
        return prompt
    updated = _call_sonnet(prompt)
    validate_synthesis(page_md, updated)   # 파괴 방지 가드
    sector_page.write_text(updated, encoding="utf-8")
    return updated
