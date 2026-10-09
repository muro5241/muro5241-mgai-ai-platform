"""Verify an actual public deployment with normal certificate validation."""

import argparse
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("origin", help="Actual HTTPS deployment origin")
    args = parser.parse_args()
    origin = args.origin.rstrip("/")
    parts = urllib.parse.urlsplit(origin)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username
        or parts.path
        or parts.query
        or parts.fragment
    ):
        parser.error("Actual HTTPS origin required")
    context = ssl.create_default_context()

    def get(path):
        with urllib.request.urlopen(
            origin + path, context=context, timeout=20
        ) as response:
            if urllib.parse.urlsplit(response.url).netloc != parts.netloc:
                raise RuntimeError("Unexpected origin redirect")
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise RuntimeError("Response exceeds verification limit")
            return raw, response.headers

    if json.loads(get("/health")[0]) != {"ok": True, "service": "mgai"}:
        raise RuntimeError("Unexpected health response")
    ready = json.loads(get("/ready")[0])
    if not all(
        ready.get(k) is True
        for k in ("ready", "database", "worker", "nvidia_configured")
    ):
        raise RuntimeError("Database/worker/NVIDIA configuration not ready")
    html, headers = get("/")
    if (
        b"MGAI AI Platform" not in html
        or not headers.get("Content-Security-Policy")
        or not headers.get("Strict-Transport-Security")
    ):
        raise RuntimeError("Frontend or security headers failed")
    print("Verified HTTPS certificate, frontend, health, PostgreSQL and worker: PASS")
    print(
        "A configured key alone does not prove live application generation. Complete authenticated studio verification separately."
    )


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        print("HTTPS verification failed; HTTP:", error.code)
        raise SystemExit(1) from None
    except (
        urllib.error.URLError,
        ValueError,
        RuntimeError,
        TimeoutError,
        OSError,
    ) as error:
        print("HTTPS verification failed; error type:", type(error).__name__)
        raise SystemExit(1) from None
