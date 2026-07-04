from unittest.mock import patch, MagicMock
import pipeline.atoms.pdf_ingest as pdf_module


def test_pdf_to_atoms_rotates_on_daily_exhaustion(monkeypatch, tmp_path):
    pdf_path = tmp_path / "fake.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    meta = {"date": "2026-07-04", "broker": "테스트증권"}

    bad_client = MagicMock()
    bad_client.files.upload.return_value = MagicMock(name="file1")
    bad_client.models.generate_content.side_effect = Exception(
        "429 RESOURCE_EXHAUSTED PerDay limit: 500"
    )
    good_client = MagicMock()
    good_client.files.upload.return_value = MagicMock(name="file2")
    good_resp = MagicMock()
    good_resp.text = '[{"content": "삼성전자 목표가 상향, 근거는 메모리 업황 개선."}]'
    good_client.models.generate_content.return_value = good_resp

    clients = [bad_client, good_client]
    monkeypatch.setattr(pdf_module.key_vault, "get_client", lambda g: clients.pop(0))
    monkeypatch.setattr(pdf_module.key_vault, "rotate", lambda g: True)
    monkeypatch.setattr(pdf_module.key_vault, "is_daily_exhausted_error",
                         lambda e: "PerDay" in str(e))
    monkeypatch.setattr(pdf_module.key_vault, "is_quota_error", lambda e: "429" in str(e))

    atoms = pdf_module._pdf_to_atoms(pdf_path, meta)
    assert len(atoms) == 1
    assert "메모리 업황" in atoms[0]["content"]
