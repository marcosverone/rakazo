"""Writes the loopback tinyproxy config for the upstream proxy named in a file.

The file holds one URL, with or without credentials:
  http://user:pass@host:8080, socks5://user:pass@host:1080, socks4://host:1080

Chromium cannot send proxy credentials, so tinyproxy listens on 127.0.0.1 and forwards to the
upstream with them. The config is written with mode 0600. Errors never repeat the value.
"""

import os
import re
import sys
from urllib.parse import unquote, urlsplit

PORT = 18080
TYPES = {"http": "http", "socks5": "socks5", "socks5h": "socks5", "socks4": "socks4"}


def tinyproxy_config(raw: str) -> str:
    try:
        url = urlsplit(raw.strip())
        kind = TYPES.get(url.scheme)
        port = url.port or (80 if kind == "http" else 1080)
        host = url.hostname
    except ValueError:
        raise ValueError("the upstream proxy is not a valid URL") from None
    if kind is None:
        raise ValueError("the upstream proxy must start with http://, socks5:// or socks4://")
    if not host or not 1 <= port <= 65535:
        raise ValueError("the upstream proxy needs a host and a valid port")
    username = unquote(url.username or "")
    password = unquote(url.password or "")
    # tinyproxy reads "user:pass@host:port" without decoding, so these characters would split it.
    if re.search(r'[\s:@"]', username) or re.search(r'[\s@"]', password):
        raise ValueError(
            "upstream proxy: the username cannot contain spaces, ':', '@' or '\"', "
            "and the password cannot contain spaces, '@' or '\"'"
        )
    credentials = f"{username}{':' + password if password else ''}@" if username else ""
    target = f"[{host}]" if ":" in host else host
    return "\n".join(
        [
            f"Port {PORT}",
            "Listen 127.0.0.1",
            "Allow 127.0.0.1",
            "Timeout 600",
            "MaxClients 200",
            "DisableViaHeader Yes",
            "LogLevel Warning",
            'LogFile "/tmp/rakazo/tinyproxy.log"',
            'PidFile "/tmp/rakazo/tinyproxy.pid"',
            f"Upstream {kind} {credentials}{target}:{port}",
            "",
        ]
    )


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: computer-proxy.py <proxy-file> <config-path>", file=sys.stderr)
        return 2
    try:
        with open(sys.argv[1]) as source:
            config = tinyproxy_config(source.read())
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    fd = os.open(sys.argv[2], os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
