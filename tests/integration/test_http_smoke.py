"""Loopback-only tests of real HTTP connections; no lab VMs required."""

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


@pytest.mark.parametrize('served_build,expected_exit', [('42', 0), ('41', 1)])
def test_real_http_cli(tmp_path, served_build, expected_exit):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write((served_build + '\n').encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        inventory = {'nginx': {'hosts': ['loopback']}, '_meta': {'hostvars': {
            'loopback': {'ansible_host': '127.0.0.1', 'nginx_http_port': server.server_port},
        }}}
        inventory_file = tmp_path / 'inventory.json'
        inventory_file.write_text(json.dumps(inventory), encoding='utf-8')
        report = tmp_path / 'report.json'
        script = Path(__file__).resolve().parents[2] / 'scripts/smoke_test.py'
        result = subprocess.run([
            sys.executable, str(script), '--inventory', str(inventory_file),
            '--expected-build', '42', '--attempts', '1', '--report', str(report),
        ], capture_output=True, text=True, timeout=10)
        assert result.returncode == expected_exit, result.stdout + result.stderr
        assert report.is_file()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
