import tempfile
import unittest
from pathlib import Path


class RoloTest(unittest.TestCase):
    def test_report_reads_real_files_and_labels_uncertainty(self):
        from company_ops.rolo import build_report
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'handoff').mkdir()
            (root / 'handoff' / 'alpha.md').write_text('# 알파\n\n## 최근 기록\n- 검수 대기\n', encoding='utf-8')
            report = build_report(root)
            self.assertIn('검수 대기', report)
            self.assertIn('handoff/alpha.md', report)
            self.assertIn('현재 실행 상태 미확인', report)
            self.assertIn('AI 모델 미연결', report)

    def test_no_records_is_not_zero_work(self):
        from company_ops.rolo import build_report
        with tempfile.TemporaryDirectory() as folder:
            self.assertIn('기록을 찾지 못했습니다', build_report(Path(folder)))

    def test_symlink_outside_root_is_not_read(self):
        from company_ops.rolo import build_report
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'handoff').mkdir()
            (root/'secret.md').write_text('SECRET', encoding='utf-8')
            try:
                (root/'handoff'/'escape.md').symlink_to(root/'secret.md')
            except OSError:
                self.skipTest('symlink permission unavailable')
            self.assertNotIn('SECRET', build_report(root))
