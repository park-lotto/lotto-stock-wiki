"""#5245·#5298(11-04 김유선): VMake 뒤에서 지우기의 cut_piece ffmpeg 실패가 원문 없이 'CalledProcessError: Command [...]' 만 남아
원인을 가를 수 없었다(손·분리 프로세스로는 재현 안 됨). 실패하면 ffmpeg stderr 끝과 쓴 ffmpeg 경로를 예외 문구에 담는다."""
from pathlib import Path

import pytest

from tools.calcopy import vmake_clean as VC


def test_실패하면_ffmpeg_원문과_경로를_담는다(tmp_path):
    bad = tmp_path / "없는파일.mp4"
    with pytest.raises(RuntimeError) as e:
        VC.cut_piece(bad, 1.0, 2.0)
    msg = str(e.value)
    assert "ffmpeg" in msg and ("No such file" in msg or "없는파일" in msg or "Error" in msg)
