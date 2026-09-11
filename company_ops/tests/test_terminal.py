import tempfile
import unittest
from pathlib import Path
from company_ops.terminal import submit
from company_ops.store import Store, ConflictError


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'test.sqlite3'
        self.payload = {
            'project': {'company_id':'makers','team_id':'improve','owner':'대표',
                        'title':'시험 지시','description':'외부 실행 없는 연결 검증'},
            'receipt': {'request_id':'test-1','session_ref':'시험 세션',
                        'approval_ref':'시험 승인 출처','approval_text':'시험 fixture, 실제 대표 승인 아님'}}

    def test_confirmation_required(self):
        with self.assertRaises(ValueError):
            submit(self.db, self.payload, confirmed=False)
        self.assertFalse(self.db.exists())

    def test_atomic_idempotent_handoff(self):
        first = submit(self.db, self.payload, confirmed=True)
        second = submit(self.db, self.payload, confirmed=True)
        self.assertEqual(first['id'], second['id'])
        state = Store(self.db).state()
        self.assertEqual(len(state['projects']), 1)
        self.assertEqual(len(state['terminal_receipts']), 1)
        self.assertEqual(len(state['assignments']), 1)
        self.assertEqual(len(state['events']), 3)
        self.assertEqual(first['current_assignee'], 'claude')

    def test_changed_payload_rejected(self):
        submit(self.db, self.payload, confirmed=True)
        self.payload['project']['title'] = '다른 내용'
        with self.assertRaises(ConflictError):
            submit(self.db, self.payload, confirmed=True)
        self.assertEqual(len(Store(self.db).state()['projects']), 1)

    def test_blank_evidence_rejected(self):
        self.payload['receipt']['approval_text'] = '   '
        with self.assertRaises(ValueError):
            submit(self.db, self.payload, confirmed=True)
        self.assertFalse(self.db.exists())
