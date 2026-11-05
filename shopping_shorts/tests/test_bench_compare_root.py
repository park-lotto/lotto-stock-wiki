import json
from tools.calcopy import bench_compare_script_scene as C


def test_bench_ids_reads_given_root(tmp_path):
    d = tmp_path / "myslug"; (d / "mp4").mkdir(parents=True); (d / "asr").mkdir()
    (d / "top.json").write_text(json.dumps([{"id": "AAA", "views": 9}, {"id": "BBB", "views": 5}]), encoding="utf-8")
    for i in ("AAA", "BBB"):
        (d / "mp4" / f"{i}.mp4").write_bytes(b"x"); (d / "asr" / f"{i}.json").write_text("{}", encoding="utf-8")
    assert C.bench_ids("myslug", 2, root=tmp_path) == ["AAA", "BBB"]
    assert C.bench_ids("myslug", 1, root=tmp_path) == ["AAA"]
