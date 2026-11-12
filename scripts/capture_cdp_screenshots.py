"""Capture full-fidelity VoxNeuro website screenshots via Edge and CDP."""

from __future__ import annotations

import asyncio
import base64
import json
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

import websockets

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT_DIR = ROOT / "docs" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


async def send_cmd(ws, method: str, params: dict | None = None, msg_id: int = 1) -> dict:
    payload = {"id": msg_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(payload))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == msg_id:
            return resp


async def eval_js(ws, expr: str, msg_id: int = 1) -> Any:
    res = await send_cmd(
        ws,
        "Runtime.evaluate",
        {"expression": expr, "returnByValue": True, "awaitPromise": True},
        msg_id=msg_id,
    )
    return res.get("result", {}).get("result", {}).get("value")


async def take_screenshot(ws, filename: str, msg_id: int = 1) -> Path:
    res = await send_cmd(
        ws,
        "Page.captureScreenshot",
        {"format": "png", "captureBeyondViewport": False},
        msg_id=msg_id,
    )
    data = res.get("result", {}).get("data")
    if not data:
        raise RuntimeError(f"No screenshot data returned for {filename}")
    out_file = SCREENSHOT_DIR / filename
    out_file.write_bytes(base64.b64decode(data))
    size = out_file.stat().st_size
    print(f"Captured {filename} ({size:,} bytes)")
    return out_file


async def run_capture() -> None:
    # 1. Fetch CDP target
    print("Connecting to Edge CDP at http://127.0.0.1:9222...")
    for _ in range(15):
        try:
            with urllib.request.urlopen("http://127.0.0.1:9222/json") as response:
                targets = json.loads(response.read().decode("utf-8"))
                page_target = next((t for t in targets if t.get("type") == "page"), None)
                if page_target and "webSocketDebuggerUrl" in page_target:
                    ws_url = page_target["webSocketDebuggerUrl"]
                    break
        except Exception:
            time.sleep(0.5)
    else:
        raise RuntimeError("Could not find Edge page target on 9222")

    print(f"Connected to debugger: {ws_url}")
    async with websockets.connect(ws_url, max_size=25_000_000) as ws:
        mid = 1
        await send_cmd(ws, "Page.enable", msg_id=mid)
        mid += 1
        await send_cmd(ws, "Runtime.enable", msg_id=mid)
        mid += 1
        await send_cmd(
            ws,
            "Emulation.setDeviceMetricsOverride",
            {"width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False},
            msg_id=mid,
        )
        mid += 1

        # Navigate to app
        await send_cmd(ws, "Page.navigate", {"url": "http://127.0.0.1:8501"}, msg_id=mid)
        mid += 1

        # Wait for Streamlit to render
        print("Waiting for Streamlit app to load...")
        for _ in range(30):
            ready = await eval_js(
                ws,
                "Boolean(document.querySelector('.vox-hero-headline') || "
                "document.querySelector('.vox-wordmark'))",
                msg_id=mid,
            )
            mid += 1
            if ready:
                break
            await asyncio.sleep(1)

        await asyncio.sleep(2)
        # 01 Landing page
        await take_screenshot(ws, "01_landing_hero.png", msg_id=mid)
        mid += 1

        # Click "How It Works" pill
        await eval_js(
            ws,
            """(() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const btn = buttons.find(b => b.textContent.includes('How It Works'));
                if (btn) btn.click();
            })()""",
            msg_id=mid,
        )
        mid += 1
        await asyncio.sleep(2)
        await take_screenshot(ws, "02_how_it_works.png", msg_id=mid)
        mid += 1

        # Click "Voice Assessment" pill
        await eval_js(
            ws,
            """(() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const btn = buttons.find(
                    b => b.textContent.includes('Voice Assessment') ||
                         b.textContent.includes('Voice Check')
                );
                if (btn) btn.click();
            })()""",
            msg_id=mid,
        )
        mid += 1
        await asyncio.sleep(2)
        await take_screenshot(ws, "03_voice_assessment_intro.png", msg_id=mid)
        mid += 1

        # Click "My Results" pill
        await eval_js(
            ws,
            """(() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const btn = buttons.find(
                    b => b.textContent.includes('My Results') ||
                         b.textContent.includes('Results')
                );
                if (btn) btn.click();
            })()""",
            msg_id=mid,
        )
        mid += 1
        await asyncio.sleep(2)
        await take_screenshot(ws, "04_results_page.png", msg_id=mid)
        mid += 1

        # Click "About VoxNeuro" pill
        await eval_js(
            ws,
            """(() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const btn = buttons.find(
                    b => b.textContent.includes('About VoxNeuro') ||
                         b.textContent.includes('About')
                );
                if (btn) btn.click();
            })()""",
            msg_id=mid,
        )
        mid += 1
        await asyncio.sleep(2)
        await take_screenshot(ws, "05_about_page.png", msg_id=mid)
        mid += 1

        # Click "My Account" pill
        await eval_js(
            ws,
            """(() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const btn = buttons.find(
                    b => b.textContent.includes('My Account') ||
                         b.textContent.includes('Account')
                );
                if (btn) btn.click();
            })()""",
            msg_id=mid,
        )
        mid += 1
        await asyncio.sleep(2)
        await take_screenshot(ws, "06_account_portal.png", msg_id=mid)
        mid += 1

        # Switch to Research model via sidebar radio
        await eval_js(
            ws,
            """(() => {
                const labels = Array.from(document.querySelectorAll('label'));
                const target = labels.find(l => l.textContent.includes('Research model'));
                if (target) target.click();
            })()""",
            msg_id=mid,
        )
        mid += 1
        await asyncio.sleep(2)
        await take_screenshot(ws, "07_researcher_model_portal.png", msg_id=mid)
        mid += 1

        # Switch to Signal analysis
        await eval_js(
            ws,
            """(() => {
                const labels = Array.from(document.querySelectorAll('label'));
                const target = labels.find(l => l.textContent.includes('Signal analysis'));
                if (target) target.click();
            })()""",
            msg_id=mid,
        )
        mid += 1
        await asyncio.sleep(2)
        await take_screenshot(ws, "08_signal_analysis.png", msg_id=mid)
        mid += 1

        # Switch to Reports
        await eval_js(
            ws,
            """(() => {
                const labels = Array.from(document.querySelectorAll('label'));
                const target = labels.find(l => l.textContent.includes('Reports'));
                if (target) target.click();
            })()""",
            msg_id=mid,
        )
        mid += 1
        await asyncio.sleep(2)
        await take_screenshot(ws, "09_reports_portal.png", msg_id=mid)
        mid += 1

    print("All screenshots successfully captured!")


def main() -> int:
    edge_proc = subprocess.Popen(
        [
            str(EDGE_EXE),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--remote-debugging-port=9222",
            "--user-data-dir=" + str(ROOT / ".temp_edge_profile"),
            "about:blank",
        ]
    )
    time.sleep(2)
    try:
        asyncio.run(run_capture())
    finally:
        edge_proc.terminate()
        try:
            edge_proc.wait(timeout=3)
        except Exception:
            edge_proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
