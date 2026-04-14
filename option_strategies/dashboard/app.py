"""
Wheel Strategy Dashboard — FastAPI Backend
============================================

API:
    GET  /              Dashboard UI
    GET  /api/scan      Run a fresh live scan, return JSON
    GET  /api/latest    Return cached last scan
    GET  /api/history   List past scan files
    GET  /api/playbook  Decision rules as JSON

Run:
    uvicorn dashboard.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.daily_scanner import run_scan, save_report

app = FastAPI(title="Wheel Strategy Dashboard", version="1.0.0")

BASE_DIR = Path(__file__).resolve().parent
SCAN_DIR = Path(__file__).resolve().parent.parent / "results" / "daily_scans"

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_latest_scan: dict | None = None


# ── API ──────────────────────────────────────────────────────────

@app.get("/api/scan")
async def api_scan():
    """Run a fresh live scan and return results."""
    global _latest_scan
    results = run_scan()
    path = save_report(results, str(SCAN_DIR))
    _latest_scan = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "tickers": results,
    }
    return JSONResponse(_latest_scan)


@app.get("/api/latest")
async def api_latest():
    """Return the most recent cached scan."""
    global _latest_scan
    if _latest_scan:
        return JSONResponse(_latest_scan)
    latest = _load_latest_from_disk()
    if latest:
        _latest_scan = latest
        return JSONResponse(latest)
    return JSONResponse({"error": "No scans yet. Hit /api/scan first."}, status_code=404)


@app.get("/api/history")
async def api_history():
    """List past scan files."""
    SCAN_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(SCAN_DIR.glob("scan_*.json"), reverse=True)
    return JSONResponse([
        {"file": f.name, "timestamp": f.stem.replace("scan_", "")}
        for f in files[:50]
    ])


@app.get("/api/playbook")
async def api_playbook():
    """Return the full decision playbook as structured JSON."""
    return JSONResponse({
        "entry": {
            "SELL_PUT": "IVR >= 30, above 200 SMA, no earnings. IVR 30-50 = 0.25 delta, IVR 50+ = 0.20 delta.",
            "BUY_STOCK": "IVR < 20 (premium too thin), or strong breakout, or ex-div capture.",
            "STAND_ASIDE": "Earnings in DTE, or >10% below 200 SMA, or below 200 SMA + IVR > 80.",
        },
        "put_management": {
            "50% profit": "Close, re-sell 30-45 DTE.",
            "OTM > 21 DTE": "Hold.",
            "OTM <= 21 DTE": "Close if >30% profit, else roll same strike +30d.",
            "ITM < 3%": "Roll same strike +30d for credit.",
            "ITM 3-8%": "Roll down 1-2 strikes +45d. Must be for credit.",
            "ITM > 8%": "Accept assignment, sell covered calls.",
            "golden_rule": "NEVER roll for a debit.",
        },
        "covered_call": {
            "> 5% above basis": "Sell 0.30-0.40 delta CC — get called away.",
            "Near basis (+/- 2%)": "Sell 0.25 delta CC — standard income.",
            "2-10% below basis": "Sell 0.15-0.20 delta CC — patient recovery.",
            "> 10% below basis": "Sell 0.10-0.15 delta CC — wait for recovery.",
            "rule": "Never sell a call below adjusted cost basis.",
        },
        "call_management": {
            "50% profit": "Close, re-sell.",
            "ITM <= 7 DTE, above basis": "Let it get called away. Cycle complete.",
            "ITM <= 7 DTE, below basis": "Roll up and out.",
            "Stock fell > 8%": "Roll call down closer to money. Never below cost basis.",
        },
        "concentration": {
            "max_per_ticker": "20%", "max_per_sector": "35%", "cash_buffer": "25%",
        },
    })


# ── Dashboard ────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request, "index.html")


def _load_latest_from_disk() -> dict | None:
    SCAN_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(SCAN_DIR.glob("scan_*.json"), reverse=True)
    if not files:
        return None
    with open(files[0]) as f:
        return json.load(f)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard.app:app", host="0.0.0.0", port=8080, reload=True)
