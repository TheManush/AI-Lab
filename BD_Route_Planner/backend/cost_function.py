"""
cost_function.py
----------------
Defines the combined edge cost and the admissible heuristic.

Cost formula
~~~~~~~~~~~~
For an edge with length L (km):

  cost(e) = L × (w_d  +  w_t × TF  +  w_c × CF  +  w_s × SF)

where:
  TF  = traffic factor     { Low:0.0, Medium:0.5, High:1.5 }
  CF  = condition factor   { Good:0.0, Damaged:0.8, Flooded:2.0, Blocked:∞ }
  SF  = safety factor      { Low-risk:0.0, Med-risk:0.4, High-risk:1.0 }
  w_d, w_t, w_c, w_s = user-supplied weights (default 1.0 each)

Admissibility of the heuristic
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  h(n) = haversine(n, goal) [km] × w_d

  Proof:  cost(path) ≥ road_length × w_d  ≥ haversine × w_d = h(n)
  (since TF,CF,SF ≥ 0 and road cannot be shorter than straight-line)
  ∴  h(n) ≤ true_cost  →  heuristic is admissible.
"""

from math import atan2, cos, radians, sin, sqrt

# ── Penalty lookup tables ──────────────────────────────────────────────────────

TRAFFIC_FACTOR = {
    1: 0.0,            # Low
    2: 0.5,            # Medium
    3: 1.5,            # High
}

CONDITION_FACTOR = {
    1: 0.0,            # Good
    2: 0.8,            # Damaged
    3: 2.0,            # Flooded
    4: float("inf"),   # Blocked
}

SAFETY_FACTOR = {
    1: 0.0,            # Low Risk
    2: 0.4,            # Medium Risk
    3: 1.0,            # High Risk
}


# ── Cost function ─────────────────────────────────────────────────────────────

def compute_edge_cost(edge_data: dict, weights: dict) -> float:
    """
    Return the combined cost of traversing `edge_data` given `weights`.
    Returns float('inf') if the edge is blocked (condition == 4).
    """
    condition = edge_data.get("condition", 1)
    if condition == 4:
        return float("inf")

    length_km = edge_data.get("length", 0) / 1000.0

    tf = TRAFFIC_FACTOR.get(edge_data.get("traffic", 1),   0.0)
    cf = CONDITION_FACTOR.get(condition,                    0.0)
    sf = SAFETY_FACTOR.get(edge_data.get("safety", 1),     0.0)

    w_d = weights.get("distance",  1.0)
    w_t = weights.get("traffic",   1.0)
    w_c = weights.get("condition", 1.0)
    w_s = weights.get("safety",    1.0)

    return length_km * (w_d + w_t * tf + w_c * cf + w_s * sf)


# ── Heuristic ─────────────────────────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Straight-line distance in kilometres."""
    R = 6_371.0
    f1, f2 = radians(lat1), radians(lat2)
    df = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    a = sin(df / 2) ** 2 + cos(f1) * cos(f2) * sin(dl / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def heuristic(node_id, target_id, G, weights: dict) -> float:
    """
    Admissible heuristic: straight-line distance × w_distance.
    Used by Best-First Search and A*.
    """
    n = G.nodes[node_id]
    t = G.nodes[target_id]
    dist_km = haversine_km(n["y"], n["x"], t["y"], t["x"])
    return dist_km * weights.get("distance", 1.0)
