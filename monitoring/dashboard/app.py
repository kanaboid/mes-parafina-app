"""
Agregator metryk z lokalnego API Netdata (bez Cloud).
Uruchamiany na oczyszczalnia-aio — odpytuje hosty z listy NETDATA_HOSTS.
"""

from __future__ import annotations

import os
from typing import Any

import requests
from flask import Flask, jsonify, render_template

app = Flask(__name__)

NETDATA_PORT = int(os.environ.get("NETDATA_PORT", "19999"))
NETDATA_HOSTS = [
    h.strip()
    for h in os.environ.get(
        "NETDATA_HOSTS", "terminal3,terminal1,oczyszczalnia-aio"
    ).split(",")
    if h.strip()
]
DISK_CHART = os.environ.get("NETDATA_DISK_CHART", "disk_space./")
REQUEST_TIMEOUT = float(os.environ.get("NETDATA_REQUEST_TIMEOUT", "8"))


def _fetch_chart(host: str, chart: str, points: int = 1) -> dict[str, Any] | None:
    """Pobiera ostatnie punkty wykresu z Netdata API v1."""
    url = f"http://{host}:{NETDATA_PORT}/api/v1/data"
    try:
        response = requests.get(
            url,
            params={
                "chart": chart,
                "points": points,
                "format": "json",
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("data"):
            return None
        return payload
    except (requests.RequestException, ValueError):
        return None


def _last_row(payload: dict[str, Any]) -> dict[str, float]:
    """Zwraca słownik {nazwa_wymiaru: wartość} z ostatniego wiersza danych."""
    labels = payload.get("labels", [])
    rows = payload.get("data", [])
    if not labels or not rows:
        return {}

    row = rows[-1]
    result: dict[str, float] = {}
    for index, label in enumerate(labels):
        if index == 0:
            continue
        if index < len(row) and row[index] is not None:
            result[str(label)] = float(row[index])
    return result


def _disk_summary(host: str) -> dict[str, Any]:
    payload = _fetch_chart(host, DISK_CHART)
    if not payload:
        return {"ok": False, "error": f"brak wykresu {DISK_CHART}"}

    dims = _last_row(payload)
    used_gib = dims.get("used", 0.0)
    avail_gib = dims.get("avail", 0.0)
    total = used_gib + avail_gib
    if total <= 0:
        return {"ok": False, "error": "brak danych dysku"}

    return {
        "ok": True,
        "used_gib": round(used_gib, 1),
        "avail_gib": round(avail_gib, 1),
        "used_pct": round(100.0 * used_gib / total, 1),
    }


def _cpu_summary(host: str) -> dict[str, Any]:
    payload = _fetch_chart(host, "system.cpu")
    if not payload:
        return {"ok": False, "error": "brak system.cpu"}

    dims = _last_row(payload)
    idle = dims.get("idle", 0.0)
    iowait = dims.get("iowait", 0.0)
    busy = max(0.0, 100.0 - idle - iowait)
    return {"ok": True, "busy_pct": round(busy, 1)}


def _ram_summary(host: str) -> dict[str, Any]:
    payload = _fetch_chart(host, "system.ram")
    if not payload:
        return {"ok": False, "error": "brak system.ram"}

    dims = _last_row(payload)
    used = dims.get("used", 0.0)
    free = dims.get("free", 0.0)
    cached = dims.get("cached", 0.0)
    buffers = dims.get("buffers", 0.0)
    total = used + free + cached + buffers
    if total <= 0:
        return {"ok": False, "error": "brak danych RAM"}

    return {
        "ok": True,
        "used_gib": round(used / 1024.0, 1),
        "used_pct": round(100.0 * used / total, 1),
    }


def _host_metrics(host: str) -> dict[str, Any]:
    return {
        "host": host,
        "disk": _disk_summary(host),
        "cpu": _cpu_summary(host),
        "ram": _ram_summary(host),
    }


@app.route("/")
def index():
    return render_template(
        "index.html",
        hosts=NETDATA_HOSTS,
        refresh_seconds=int(os.environ.get("DASHBOARD_REFRESH_SECONDS", "30")),
    )


@app.route("/api/metrics")
def api_metrics():
    return jsonify({"hosts": [_host_metrics(host) for host in NETDATA_HOSTS]})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})

