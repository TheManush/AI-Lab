"""
algorithms/common.py
--------------------
Shared helpers used by every algorithm module.
"""

import time
from cost_function import compute_edge_cost


# ── Edge accessor ─────────────────────────────────────────────────────────────

def get_best_edge(G, u, v, weights: dict):
    """
    Return (edge_data_dict, edge_cost) for the cheapest parallel edge u→v.
    If all parallel edges are blocked, returns (None, inf).
    """
    best_data = None
    best_cost = float("inf")
    for k, data in G[u][v].items():
        c = compute_edge_cost(data, weights)
        if c < best_cost:
            best_cost = c
            best_data = data
    return best_data, best_cost


# ── Result builders ───────────────────────────────────────────────────────────

def build_result(G, path, explored_seq, nodes_expanded, weights, t0):
    """Build the standard result dict for a found path."""
    from cost_function import compute_edge_cost

    total_dist_m = 0.0
    total_cost   = 0.0

    for i in range(len(path) - 1):
        edge_data, edge_cost = get_best_edge(G, path[i], path[i + 1], weights)
        if edge_data:
            total_dist_m += edge_data.get("length", 0)
            total_cost   += edge_cost

    path_coords     = [[G.nodes[n]["y"], G.nodes[n]["x"]] for n in path]
    explored_coords = [[G.nodes[n]["y"], G.nodes[n]["x"]] for n in explored_seq]

    return {
        "found": True,
        "path":             [str(n) for n in path],
        "path_coords":      path_coords,
        "explored_sequence":[str(n) for n in explored_seq],
        "explored_coords":  explored_coords,
        "stats": {
            "distance_km":    round(total_dist_m / 1000, 3),
            "total_cost":     round(total_cost, 4),
            "nodes_expanded": nodes_expanded,
            "runtime_ms":     round((time.time() - t0) * 1000, 2),
        },
    }


def not_found_result(explored_seq, nodes_expanded, t0):
    """Result dict when no path was found."""
    return {
        "found": False,
        "path":              [],
        "path_coords":       [],
        "explored_sequence": [str(n) for n in explored_seq],
        "explored_coords":   [],
        "stats": {
            "distance_km":    0,
            "total_cost":     0,
            "nodes_expanded": nodes_expanded,
            "runtime_ms":     round((time.time() - t0) * 1000, 2),
        },
    }
