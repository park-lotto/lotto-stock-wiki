import json
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.request import urlopen

import pytest


pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows launcher')
SCRIPT = Path(__file__).parents[1] / 'tools' / 'open_static_result.ps1'


def launch(html, port):
    return subprocess.run(
        ['powershell.exe', '-NoProfile', '-File', str(SCRIPT),
         '-HtmlPath', str(html), '-Port', str(port), '-NoBrowser'],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=45,
    )


def test_detached_server_survives_launcher_and_reuses_exact_content(tmp_path):
    directory = tmp_path / 'space and 한글'
    directory.mkdir()
    html = directory / '비교 화면.html'
    body = '<!doctype html><meta charset="utf-8"><h1>유지 확인</h1>'.encode()
    html.write_bytes(body)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    started_pid = None
    try:
        first = launch(html, port)
        assert first.returncode == 0, first.stderr
        info = json.loads(first.stdout)
        started_pid = info['started_pid']
        assert started_pid and not info['reused'] and not info['browser_opened']
        # The launching PowerShell has exited. Its detached server must still respond.
        time.sleep(1)
        with urlopen(info['url'], timeout=3) as response:
            assert response.read() == body
        again = launch(html, port)
        assert again.returncode == 0, again.stderr
        assert json.loads(again.stdout)['reused'] is True
        other_dir = tmp_path / 'other'
        other_dir.mkdir()
        other = other_dir / html.name
        other.write_text('different result', encoding='utf-8')
        mismatch = launch(other, port)
        assert mismatch.returncode != 0
        assert 'already in use' in mismatch.stderr
        with urlopen(info['url'], timeout=3) as response:
            assert response.read() == body
    finally:
        if started_pid:
            # Only this test's exact, newly-created process is cleaned up.
            subprocess.run(['taskkill', '/PID', str(started_pid), '/F'], capture_output=True)


def test_rejects_non_html_without_starting_server(tmp_path):
    text_file = tmp_path / 'plain.txt'
    text_file.write_text('not html')
    result = launch(text_file, 8899)
    assert result.returncode != 0
    assert 'existing HTML file' in result.stderr
