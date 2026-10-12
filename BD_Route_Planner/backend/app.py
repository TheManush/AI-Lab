"""
app.py  —  Flask backend for BD Route Planner
===============================================
Endpoints
─────────
  GET  /                      → serve frontend
  GET  /api/graph             → graph nodes + edges (current scenario)
  POST /api/nearest-node      → find nearest graph node to a lat/lon
  POST /api/run               → run one algorithm
  POST /api/run-all           → run all 6 algorithms for comparison
  POST /api/apply-scenario    → change active scenario, return updated edges
"""

import os
import sys
import threading
from math import atan2, cos, radians, sin, sqrt

from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_cors import CORS

# ── path setup so sibling modules import correctly ────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from graph_builder import graph_to_json, load_graph
from scenarios import apply_scenario
from algorithms import astar, best_first, bfs, dfs, ids, ucs

# ── Flask setup ────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR   = os.path.join(BASE_DIR, "static")

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
CORS(app)

# ── Graph (loaded once at startup) ────────────────────────────────────────────
print("[app] Loading road network …")
G = load_graph()
_graph_lock       = threading.Lock()
_current_scenario = "normal"
_manual_blocks    = set()   # set of (u, v, k) tuples blocked by user clicks

# ── Helpers ────────────────────────────────────────────────────────────────────

def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000
    f1, f2 = radians(lat1), radians(lat2)
    df = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    a  = sin(df / 2) ** 2 + cos(f1) * cos(f2) * sin(dl / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _nearest_node(lat, lon):
    best_id   = None
    best_dist = float("inf")
    for nid, data in G.nodes(data=True):
        d = _haversine_m(lat, lon, data["y"], data["x"])
        if d < best_dist:
            best_dist = d
            best_id   = nid
    return best_id, best_dist


def _run_algorithm(algo_name: str, source, target, weights: dict) -> dict:
    ALGOS = {
        "bfs":        bfs,
        "dfs":        dfs,
        "ucs":        ucs,
        "ids":        ids,
        "best_first": best_first,
        "astar":      astar,
    }
    fn = ALGOS.get(algo_name)
    if fn is None:
        return {"error": f"Unknown algorithm: {algo_name}"}
    return fn(G, source, target, weights)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)


@app.route("/api/graph")
def api_graph():
    # Read-only — no lock needed
    data = graph_to_json(G)
    data["current_scenario"] = _current_scenario
    return jsonify(data)


@app.route("/api/nearest-node", methods=["POST"])
def api_nearest_node():
    body = request.get_json(force=True)
    lat  = float(body["lat"])
    lon  = float(body["lon"])
    # Read-only — no lock needed
    nid, dist = _nearest_node(lat, lon)
    node_data = G.nodes[nid]
    return jsonify(
        {
            "node_id":  str(nid),
            "lat":      node_data["y"],
            "lon":      node_data["x"],
            "dist_m":   round(dist, 1),
        }
    )


@app.route("/api/apply-scenario", methods=["POST"])
def api_apply_scenario():
    global _current_scenario
    body     = request.get_json(force=True)
    scenario = body.get("scenario", "normal")
    with _graph_lock:
        apply_scenario(G, scenario)
        _current_scenario = scenario
        data = graph_to_json(G)

    # Count impact for UI feedback
    total   = len(list(G.edges()))
    blocked = sum(1 for _,_,_,d in G.edges(data=True, keys=True) if d.get("condition") == 4)
    flooded = sum(1 for _,_,_,d in G.edges(data=True, keys=True) if d.get("condition") == 3)
    hi_traf = sum(1 for _,_,_,d in G.edges(data=True, keys=True) if d.get("traffic") == 3)
    hi_risk = sum(1 for _,_,_,d in G.edges(data=True, keys=True) if d.get("safety") == 3)

    data["current_scenario"] = scenario
    data["impact"] = {
        "total":    total,
        "blocked":  blocked,
        "flooded":  flooded,
        "hi_traf":  hi_traf,
        "hi_risk":  hi_risk,
    }
    return jsonify(data)


@app.route("/api/run", methods=["POST"])
def api_run():
    body      = request.get_json(force=True)
    source_id = int(body["source"])
    target_id = int(body["target"])
    algo      = body.get("algorithm", "astar")
    weights   = {
        "distance":  float(body.get("w_distance",  1.0)),
        "traffic":   float(body.get("w_traffic",   1.0)),
        "condition": float(body.get("w_condition", 1.0)),
        "safety":    float(body.get("w_safety",    1.0)),
    }

    if source_id not in G.nodes or target_id not in G.nodes:
        return jsonify({"error": "Invalid node IDs"}), 400

    # Algorithms are read-only — no lock needed
    result = _run_algorithm(algo, source_id, target_id, weights)
    result["algorithm"] = algo
    return jsonify(result)


@app.route("/api/run-all", methods=["POST"])
def api_run_all():
    body      = request.get_json(force=True)
    source_id = int(body["source"])
    target_id = int(body["target"])
    weights   = {
        "distance":  float(body.get("w_distance",  1.0)),
        "traffic":   float(body.get("w_traffic",   1.0)),
        "condition": float(body.get("w_condition", 1.0)),
        "safety":    float(body.get("w_safety",    1.0)),
    }

    if source_id not in G.nodes or target_id not in G.nodes:
        return jsonify({"error": "Invalid node IDs"}), 400

    # Algorithms are read-only — run without lock so /api/graph can still be served
    results = {}
    for algo in ["bfs", "dfs", "ucs", "ids", "best_first", "astar"]:
        r = _run_algorithm(algo, source_id, target_id, weights)
        r["algorithm"] = algo
        results[algo]  = r

    return jsonify({"results": results})


# ── Manual road blocking ───────────────────────────────────────────────────────

@app.route("/api/block-edge", methods=["POST"])
def api_block_edge():
    """Toggle a specific edge blocked (condition=4) or unblock it."""
    global _manual_blocks
    body   = request.get_json(force=True)
    u      = int(body["source"])
    v      = int(body["target"])
    k      = int(body.get("key", 0))
    action = body.get("action", "block")   # "block" | "unblock"

    if u not in G.nodes or v not in G.nodes:
        return jsonify({"error": "Invalid node IDs"}), 400
    if v not in G[u] or k not in G[u][v]:
        return jsonify({"error": "Edge not found"}), 400

    with _graph_lock:
        edge_key = (u, v, k)
        if action == "block":
            G[u][v][k]["condition"] = 4
            _manual_blocks.add(edge_key)
        else:
            base = G[u][v][k].get("base_condition", 1)
            G[u][v][k]["condition"] = base
            _manual_blocks.discard(edge_key)

    return jsonify({
        "ok":            True,
        "action":        action,
        "source":        str(u),
        "target":        str(v),
        "key":           k,
        "manual_blocks": len(_manual_blocks),
    })


@app.route("/api/unblock-all-manual", methods=["POST"])
def api_unblock_all_manual():
    """Reset all manually blocked edges back to their base condition."""
    global _manual_blocks
    with _graph_lock:
        count = len(_manual_blocks)
        for (u, v, k) in list(_manual_blocks):
            try:
                G[u][v][k]["condition"] = G[u][v][k].get("base_condition", 1)
            except (KeyError, TypeError):
                pass
        _manual_blocks.clear()
    return jsonify({"ok": True, "cleared": count})


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("[app] Starting server at http://127.0.0.1:5000")
    app.run(debug=True, host="127.0.0.1", port=5000, use_reloader=False)
