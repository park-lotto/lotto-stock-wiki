"""11-05 김미향 #7614: 윈도에서 쓰는 중인(열린) 파일은 scandir 항목 크기가 0 에 멈춰, 받기가 파일을 키워도 진행 감시가 멈춤으로 끊었다."""
from tools.calcopy.hybrid import runner_ops as RO


def test_dir_sig_sees_growing_open_file(tmp_path):
    f = open(tmp_path / "bench.mp4.part", "wb")
    try:
        f.write(b"0" * 100_000); f.flush()
        a = RO._dir_sig(tmp_path)
        f.write(b"0" * 100_000); f.flush()
        b = RO._dir_sig(tmp_path)
    finally:
        f.close()
    assert a != b, "쓰는 중인 파일이 자라도 진행 신호로 안 잡힌다"
