import inspect
from tools.calcopy.hybrid import runner_ops as R


def test_speechmatics_is_not_required():
    assert '"id": "speechmatics"' not in inspect.getsource(R)
