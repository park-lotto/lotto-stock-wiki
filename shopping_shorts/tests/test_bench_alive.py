"""11-05 김미향 #7001: 8분22초 롱폼 소재를 받은 뒤 시트·받아쓰기가 180초 넘게 진행 신호 없이 돌아 감시가 3번 끊었다(하위 프로그램 0개).
소재 처리도 다른 단계와 같은 진행 신호 주인(runner_ops._Alive)으로 감싼다."""
import ast
import inspect

from tools.calcopy.hybrid import runner_ops as RO


def test_bench_heavy_part_inside_alive():
    src = inspect.getsource(RO.c_bench)
    tree = ast.parse(src)
    withs = [n for n in ast.walk(tree) if isinstance(n, ast.With) and any(isinstance(i.context_expr, ast.Call) and getattr(i.context_expr.func, "id", "") == "_Alive" for i in n.items)]
    assert withs, "소재 처리에 진행 신호(_Alive)가 없다"
    calls = {getattr(c.func, "id", "") for w in withs for c in ast.walk(w) if isinstance(c, ast.Call)}
    assert {"sheet", "asr"} <= calls, "시트·받아쓰기가 진행 신호 밖에 있다"
