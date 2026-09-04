"""미리보기는 '도착했다'로 판정한다 — '도착하라고 시켰다'가 아니다 (2026-09-02).

사장님 제보: "전체재생에서 훅 뒤에 꼬다리가 나온다. 오렌지박스보다 1초 정도 앞 화면이다."
칸별 재생에는 없고 **전체 재생에만** 났다.

원인: step()의 '바로 보여줘도 되나' 판정이 currentTime만 봤다.
  if (Math.abs(v.currentTime - c.start) < 0.05 && v.readyState >= 2) show();
HTML 명세상 `v.currentTime = X`는 **요청 즉시** X를 돌려주고 seeking만 true가 된다.
실제 프레임은 나중에 온다. 그래서 이 조건은 도착을 못 본다.

전체 재생에서만 난 이유: runAllFrom이 다음 칸 첫 컷을 seat()으로 미리 앉히는데,
seat은 currentTime만 꽂고 기다리지 않는다(주석엔 "완료까지 기다린다"고 적혀 있었다).
앞 칸과 같은 소스를 쓰면 readyState는 이미 높고 seeking만 true라 조건이 통과 →
가림막(썸네일) 없이 바로 화면에 올려, 아직 도착 못 한 앞부분이 노출됐다.
칸별 재생은 미리 앉히기가 없어 늘 else(썸네일로 가리고 대기)로 갔다.

이 테스트가 막는 것: 판정에서 seeking이 빠지는 되돌림.
"""
import pathlib
import re

_JS = pathlib.Path(__file__).resolve().parents[1] / "static" / "scene_play.js"


def _src():
    return _JS.read_text(encoding="utf-8")


def test_바로보여주기_판정이_seeking을_본다():
    src = _src()
    m = re.search(r"if \(Math\.abs\(v\.currentTime - c\.start\)[^\n]*\) show\(\);", src)
    assert m, "step()의 '바로 보여줌' 판정을 못 찾았다 — 이 테스트를 코드에 맞춰 고쳐라"
    line = m.group(0)
    assert "!v.seeking" in line, (
        "판정에서 seeking이 빠졌다 — currentTime만 보면 '도착하라고 시켰다'를 도착으로 읽어\n"
        "전체 재생의 칸 넘김에서 앞부분이 노출된다(2026-09-02 '훅 뒤 꼬다리').\n"
        f"  지금: {line}"
    )


def test_진행중인_시크를_다시_꽂지_않는다():
    """같은 값을 재대입하면 브라우저가 seeked를 안 쏘아 진행 중이던 완료 신호까지 놓친다.
    그러면 컷 시작이 cutWaitMs만큼 늦어진다 — 미리 앉힌 컷이 정확히 이 경우다."""
    src = _src()
    assert "if (!(v.seeking && Math.abs(v.currentTime - c.start) < 0.05)) v.currentTime = c.start;" in src, \
        "진행 중인 시크에 currentTime을 재대입하지 않는 가드가 사라졌다"


def test_도착_전에는_가림막을_걷지_않는다():
    """대기 타이머(cutWaitMs)는 시크가 안 끝나도 show()로 온다. 그때 썸네일을 걷으면
    도착 못 한 앞부분이 그대로 보인다 — 실측(job 8b5aed8af66b): 훅 마지막 컷이
    s4@10.06인데 그 앞 9초대가 노출됐고, 다음 칸도 같은 s4(0.75~)를 써서 미리 앉히기와
    시크가 겹쳐 느려진 상황이었다. readyState는 '열려 있다'일 뿐 '그 자리에 왔다'가 아니다."""
    src = _src()
    assert "if (v.readyState >= 2 && !v.seeking) holdShot(null, false);" in src, (
        "가림막(썸네일)을 걷는 판정에서 seeking이 빠졌다 — 도착 전에 걷으면 꼬다리가 다시 난다"
    )
