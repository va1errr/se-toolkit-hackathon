#!/usr/bin/env python3
"""Compare outgoing requests from the proxy vs the real Qwen Code CLI.

Starts mitmdump, routes both through it, and diffs the captured requests.

Requirements:
  - mitmproxy (`pip install mitmproxy`)
  - qwen CLI (`pnpm add -g @qwen-code/qwen-code`)
  - Valid OAuth creds at ~/.qwen/oauth_creds.json

Usage:
  uv run python scripts/compare_requests.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

MITM_PORT = 19090
PROXY_PORT = 19085
PROMPT = "Reply with just: ok"

# ── mitmdump addon (written to a temp file) ──────────────────────────
ADDON_CODE = """
import json, os
DUMP = os.environ["MITM_DUMP_FILE"]
class DumpFlow:
    def request(self, flow):
        data = {
            "method": flow.request.method,
            "url": flow.request.pretty_url,
            "headers": dict(flow.request.headers),
        }
        if flow.request.content:
            try:
                data["body"] = json.loads(flow.request.content)
            except Exception:
                data["body"] = flow.request.content.decode("utf-8", errors="replace")
        with open(DUMP, "a") as f:
            f.write(json.dumps(data) + "\\n")
addons = [DumpFlow()]
"""

DYNAMIC_HEADERS = {
    "authorization",
    "content-length",
    "host",
    "accept",  # SDK sets this independently; proxy sets based on stream flag
}

DYNAMIC_BODY_KEYS = {
    "messages",  # content differs (system prompt, context)
    "tools",  # tool set differs (proxy forwards caller's tools)
    "metadata",  # session/prompt IDs are random
    "vl_high_resolution_images",  # vision param, no effect for text-only
}


class CapturedFlow(BaseModel):
    method: str = ""
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] = Field(default_factory=dict)


def start_mitmdump(dump_file: str, addon_file: str) -> subprocess.Popen[bytes]:
    env = {**os.environ, "MITM_DUMP_FILE": dump_file}
    proc: subprocess.Popen[bytes] = subprocess.Popen(
        [
            "mitmdump",
            "--listen-port",
            str(MITM_PORT),
            "-s",
            addon_file,
            "--set",
            "console_eventlog_verbosity=error",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    return proc


def start_proxy(mitmproxy_ca: str) -> subprocess.Popen[bytes]:
    env = {
        **os.environ,
        "HTTPS_PROXY": f"http://127.0.0.1:{MITM_PORT}",
        "HTTP_PROXY": f"http://127.0.0.1:{MITM_PORT}",
        "SSL_CERT_FILE": mitmproxy_ca,
        "REQUESTS_CA_BUNDLE": mitmproxy_ca,
        "PORT": str(PROXY_PORT),
        "ADDRESS": "0.0.0.0",
        "LOG_LEVEL": "error",
        "MAX_RETRIES": "1",
        "RETRY_DELAY_MS": "1000",
        "QWEN_CODE_AUTH_USE": "true",
        "QWEN_CODE_API_KEY": "test",
        "DEFAULT_MODEL": "coder-model",
        "LOG_REQUESTS": "false",
    }
    proc: subprocess.Popen[bytes] = subprocess.Popen(
        [sys.executable, "-m", "qwen_code_api.main"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    return proc


def send_proxy_request() -> None:
    import urllib.request

    body = json.dumps(
        {
            "model": "coder-model",
            "messages": [{"role": "user", "content": PROMPT}],
            "stream": True,
        }
    ).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{PROXY_PORT}/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer test",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except Exception as e:
        print(f"  Warning: proxy request error: {e}")


def send_qwen_request() -> None:
    env = {
        **os.environ,
        "HTTPS_PROXY": f"http://127.0.0.1:{MITM_PORT}",
        "NODE_TLS_REJECT_UNAUTHORIZED": "0",
    }
    try:
        subprocess.run(
            ["qwen", "-p", PROMPT],
            env=env,
            capture_output=True,
            timeout=30,
        )
    except FileNotFoundError:
        print(
            "  Error: 'qwen' CLI not found. Install with: pnpm add -g @qwen-code/qwen-code"
        )
        sys.exit(1)


def read_flows(dump_file: str) -> list[CapturedFlow]:
    flows: list[CapturedFlow] = []
    try:
        with open(dump_file) as f:
            for line in f:
                data = json.loads(line)
                if "chat/completions" in data.get("url", ""):
                    flows.append(CapturedFlow.model_validate(data))
    except FileNotFoundError:
        pass
    return flows


def normalize_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        k.lower(): v for k, v in headers.items() if k.lower() not in DYNAMIC_HEADERS
    }


def compare(proxy_flow: CapturedFlow, qwen_flow: CapturedFlow) -> list[str]:
    diffs: list[str] = []

    # Compare URL
    if proxy_flow.url != qwen_flow.url:
        diffs.append(f"URL: proxy={proxy_flow.url}  qwen={qwen_flow.url}")

    # Compare headers
    ph = normalize_headers(proxy_flow.headers)
    qh = normalize_headers(qwen_flow.headers)
    all_keys = sorted(set(ph) | set(qh))
    for k in all_keys:
        pv = ph.get(k)
        qv = qh.get(k)
        if pv != qv:
            diffs.append(f"Header [{k}]: proxy={pv!r}  qwen={qv!r}")

    # Compare body (top-level keys, excluding dynamic ones)
    pb = proxy_flow.body
    qb = qwen_flow.body

    all_body_keys = sorted(set(pb) | set(qb))
    for k in all_body_keys:
        if k in DYNAMIC_BODY_KEYS:
            # For tools, check cache_control on last tool when both present
            in_proxy = k in pb
            in_qwen = k in qb
            if k == "tools" and in_proxy and in_qwen:
                p_last_cc = "cache_control" in pb["tools"][-1] if pb["tools"] else None
                q_last_cc = "cache_control" in qb["tools"][-1] if qb["tools"] else None
                if p_last_cc != q_last_cc:
                    diffs.append(
                        f"Body [tools] last cache_control: proxy={p_last_cc}  qwen={q_last_cc}"
                    )
            continue

        pv = pb.get(k)
        qv = qb.get(k)
        if pv != qv:
            diffs.append(f"Body [{k}]: proxy={json.dumps(pv)}  qwen={json.dumps(qv)}")

    return diffs


def main() -> None:
    mitmproxy_ca = Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.pem"
    if not mitmproxy_ca.exists():
        print("Error: mitmproxy CA cert not found. Run mitmproxy once to generate it.")
        sys.exit(1)

    procs: list[subprocess.Popen[bytes]] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        addon_file = os.path.join(tmpdir, "addon.py")
        with open(addon_file, "w") as f:
            f.write(ADDON_CODE)

        try:
            # ── Step 1: Capture proxy request ──
            dump_proxy = os.path.join(tmpdir, "proxy.jsonl")
            os.environ["MITM_DUMP_FILE"] = dump_proxy

            print("Starting mitmdump...")
            mitm = start_mitmdump(dump_proxy, addon_file)
            procs.append(mitm)

            print("Starting proxy...")
            proxy = start_proxy(str(mitmproxy_ca))
            procs.append(proxy)

            print("Sending request through proxy...")
            send_proxy_request()
            time.sleep(1)

            proxy_flows = read_flows(dump_proxy)
            print(f"  Captured {len(proxy_flows)} proxy flow(s)")

            # Kill proxy
            proxy.terminate()
            proxy.wait(timeout=5)
            procs.remove(proxy)

            # ── Step 2: Capture real qwen request ──
            dump_qwen = os.path.join(tmpdir, "qwen.jsonl")
            # Update addon env
            mitm.terminate()
            mitm.wait(timeout=5)
            procs.remove(mitm)

            mitm = start_mitmdump(dump_qwen, addon_file)
            procs.append(mitm)

            print("Sending request through real qwen CLI...")
            send_qwen_request()
            time.sleep(1)

            qwen_flows = read_flows(dump_qwen)
            print(f"  Captured {len(qwen_flows)} qwen flow(s)")

            # ── Step 3: Compare ──
            if not proxy_flows:
                print("\nError: No proxy flows captured")
                sys.exit(1)
            if not qwen_flows:
                print("\nError: No qwen flows captured")
                sys.exit(1)

            print("\n=== Comparison ===")
            diffs = compare(proxy_flows[0], qwen_flows[0])

            if not diffs:
                print("  No differences found!")
            else:
                print(f"  {len(diffs)} difference(s):\n")
                for d in diffs:
                    print(f"  - {d}")

            sys.exit(0 if not diffs else 1)

        finally:
            for p in procs:
                try:
                    p.terminate()
                    p.wait(timeout=5)
                except Exception:
                    p.kill()


if __name__ == "__main__":
    main()
