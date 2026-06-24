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

# Opis roli hosta (można nadpisać: NETDATA_HOST_ROLES=terminal3:Produkcja,terminal1:Standby)
DEFAULT_HOST_ROLES: dict[str, str] = {
    "terminal3": "produkcja",
    "terminal1": "standby / replika",
    "oczyszczalnia-aio": "monitoring",
}


def _parse_host_roles() -> dict[str, str]:
    roles = dict(DEFAULT_HOST_ROLES)
    raw = os.environ.get("NETDATA_HOST_ROLES", "")
    for part in raw.split(","):
        part = part.strip()
        if ":" not in part:
            continue
        host, role = part.split(":", 1)
        roles[host.strip()] = role.strip()
    return roles


HOST_ROLES = _parse_host_roles()


def _fetch_chart(host: str, chart: str, points: int = 1) -> dict[str, Any] | None:
    url = f"http://{host}:{NETDATA_PORT}/api/v1/data"
    try:
        response = requests.get(
            url,
            params={"chart": chart, "points": points, "format": "json"},
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


def _avg_dimensions(payload: dict[str, Any]) -> dict[str, float]:
    """Średnia wartości wymiarów z wielu punktów (stabilniejsze niż ostatnia sekunda)."""
    labels = payload.get("labels", [])
    rows = payload.get("data", [])
    if not labels or not rows:
        return {}

    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for row in rows:
        for index, label in enumerate(labels):
            if index == 0:
                continue
            if index < len(row) and row[index] is not None:
                key = str(label)
                sums[key] = sums.get(key, 0.0) + float(row[index])
                counts[key] = counts.get(key, 0) + 1

    return {key: sums[key] / counts[key] for key in sums if counts.get(key)}


def _dim_value(dims: dict[str, float], name: str) -> float:
    """Pobiera wymiar bez względu na wielkość liter (Netdata zwraca małe litery)."""
    if name in dims:
        return dims[name]
    lowered = name.lower()
    for key, value in dims.items():
        if key.lower() == lowered:
            return value
    return 0.0


# Netdata domyślnie nie zwraca wymiaru idle w /api/v1/data — busy liczymy z aktywnych.
_CPU_BUSY_DIMS = (
    "user",
    "nice",
    "system",
    "irq",
    "softirq",
    "steal",
    "guest",
    "guest_nice",
)



def _disk_summary(host: str) -> dict[str, Any]:
    payload = _fetch_chart(host, DISK_CHART)
    if not payload:
        return {
            "ok": False,
            "error": f"brak danych Netdata (wykres {DISK_CHART})",
        }

    dims = _last_row(payload)
    used_gib = dims.get("used", 0.0)
    avail_gib = dims.get("avail", 0.0)
    total_gib = used_gib + avail_gib
    if total_gib <= 0:
        return {"ok": False, "error": "brak danych o dysku"}

    used_pct = round(100.0 * used_gib / total_gib, 1)

    return {
        "ok": True,
        "used_gib": round(used_gib, 1),
        "avail_gib": round(avail_gib, 1),
        "used_pct": used_pct,
    }


def _cpu_summary(host: str) -> dict[str, Any]:
    payload = _fetch_chart(host, "system.cpu", points=5)
    if not payload:
        return {"ok": False, "error": "brak danych CPU"}

    dims = _avg_dimensions(payload)
    if not dims:
        return {"ok": False, "error": "brak danych CPU"}

    busy = sum(_dim_value(dims, name) for name in _CPU_BUSY_DIMS)
    iowait = _dim_value(dims, "iowait")
    idle = _dim_value(dims, "idle")
    if idle <= 0.0:
        # idle nie ma w domyślnej odpowiedzi Netdata — wylicz z pozostałych wymiarów
        idle = max(0.0, 100.0 - busy - iowait)

    busy = min(100.0, max(0.0, busy))
    idle = min(100.0, max(0.0, idle))

    return {
        "ok": True,
        "busy_pct": round(busy, 1),
        "idle_pct": round(idle, 1),
        "iowait_pct": round(iowait, 1),
    }


def _ram_summary(host: str) -> dict[str, Any]:
    payload = _fetch_chart(host, "system.ram")
    if not payload:
        return {"ok": False, "error": "brak danych RAM"}

    dims = _last_row(payload)
    # Netdata system.ram — wartości w MiB
    used_mib = dims.get("used", 0.0)
    free_mib = dims.get("free", 0.0)
    cached_mib = dims.get("cached", 0.0)
    buffers_mib = dims.get("buffers", 0.0)
    total_mib = used_mib + free_mib + cached_mib + buffers_mib
    if total_mib <= 0:
        return {"ok": False, "error": "brak danych RAM"}

    used_pct = round(100.0 * used_mib / total_mib, 1)
    total_gib = round(total_mib / 1024.0, 1)
    used_gib = round(used_mib / 1024.0, 1)
    avail_gib = round((free_mib + cached_mib + buffers_mib) / 1024.0, 1)

    return {
        "ok": True,
        "used_gib": used_gib,
        "avail_gib": avail_gib,
        "total_gib": total_gib,
        "used_pct": used_pct,
        "cached_gib": round(cached_mib / 1024.0, 1),
    }


def _host_metrics(host: str) -> dict[str, Any]:
    return {
        "host": host,
        "role": HOST_ROLES.get(host, "Host MES"),
        "netdata_url": f"http://{host}:{NETDATA_PORT}/v3",
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
