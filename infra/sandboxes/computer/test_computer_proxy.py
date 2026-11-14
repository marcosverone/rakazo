"""Offline tests for the loopback proxy config built from the mounted upstream proxy file."""
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import importlib.util

spec = importlib.util.spec_from_file_location("computer_proxy", HERE / "computer-proxy.py")
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)


class TinyproxyConfigTests(unittest.TestCase):
    def upstream(self, raw):
        lines = proxy.tinyproxy_config(raw).splitlines()
        return next(line for line in lines if line.startswith("Upstream "))

    def test_socks5_with_credentials(self):
        self.assertEqual(
            self.upstream("socks5://user:pass@proxy.example.test:10000"),
            "Upstream socks5 user:pass@proxy.example.test:10000",
        )

    def test_http_without_credentials_defaults_the_port(self):
        self.assertEqual(self.upstream("http://proxy.example.test"), "Upstream http proxy.example.test:80")

    def test_percent_encoded_credentials_are_decoded(self):
        self.assertEqual(
            self.upstream("socks5://user:p%23ss@proxy.example.test:1080"),
            "Upstream socks5 user:p#ss@proxy.example.test:1080",
        )

    def test_listens_on_loopback_only(self):
        config = proxy.tinyproxy_config("socks5://proxy.example.test:1080")
        self.assertIn("Listen 127.0.0.1", config)
        self.assertIn("Allow 127.0.0.1", config)

    def test_rejects_unsupported_or_malformed_values_without_echoing_them(self):
        for raw in ["ftp://u:secretvalue@h:1", "not a url", "socks5://u:sec ret@h:1", "socks5://u:secretvalue@h:99999"]:
            with self.assertRaises(ValueError) as caught:
                proxy.tinyproxy_config(raw)
            self.assertNotIn("secretvalue", str(caught.exception))


class CommandTests(unittest.TestCase):
    def run_script(self, value):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tinyproxy.conf"
            source = Path(tmp) / "proxy"
            source.write_text(value + "\n")
            result = subprocess.run(
                [sys.executable, str(HERE / "computer-proxy.py"), str(source), str(path)],
                capture_output=True,
                text=True,
            )
            mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
            return result, mode

    def test_writes_a_private_config(self):
        result, mode = self.run_script("socks5://user:pass@proxy.example.test:1080")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mode, 0o600)

    def test_a_bad_value_fails_and_writes_nothing(self):
        result, mode = self.run_script("ftp://proxy.example.test")
        self.assertEqual(result.returncode, 1)
        self.assertIsNone(mode)


if __name__ == "__main__":
    unittest.main()
