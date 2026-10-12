"""
graph_builder.py
----------------
Downloads (or loads from cache) a real road network for a portion of Dhaka city
using OSMnx, then assigns synthetic road attributes:
  - traffic   : 1=Low, 2=Medium, 3=High
  - condition : 1=Good, 2=Damaged, 3=Flooded, 4=Blocked
  - safety    : 1=Low Risk, 2=Medium Risk, 3=High Risk
"""

import os
import pickle
import random
from math import atan2, cos, radians, sin, sqrt

import osmnx as ox

# ── Constants ─────────────────────────────────────────────────────────────────

GRAPH_CACHE = os.path.join(os.path.dirname(__file__), "graph_cache.pkl")

# Dhanmondi / Mirpur Road area, Dhaka
CENTER_LAT = 23.7461
CENTER_LON = 90.3742
DIST_METERS = 1400          # radius → ~200-400 nodes, good for demo

ATTR_SEED = 42              # reproducible random attributes

# Per-highway-type base attributes ── (traffic, safety)
HIGHWAY_ATTRS = {
    "trunk":          (3, 3),
    "trunk_link":     (3, 3),
    "primary":        (3, 2),
    "primary_link":   (3, 2),
    "secondary":      (2, 2),
    "secondary_link": (2, 2),
    "tertiary":       (2, 1),
    "tertiary_link":  (2, 1),
    "residential":    (1, 1),
    "living_street":  (1, 1),
    "service":        (1, 1),
    "unclassified":   (1, 1),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def haversine_m(lat1, lon1, lat2, lon2):
    """Straight-line distance in metres between two lat/lon points."""
    R = 6_371_000
    f1, f2 = radians(lat1), radians(lat2)
    df = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    a = sin(df / 2) ** 2 + cos(f1) * cos(f2) * sin(dl / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


# ── Attribute assignment ───────────────────────────────────────────────────────

def _assign_attributes(G):
    """
    Assign base_traffic, base_condition, base_safety to every edge.
    These are the 'ground truth' attributes for the Normal scenario.
    The working copies (traffic / condition / safety) are always reset
    from the base values when a scenario is applied.
    """
    rng = random.Random(ATTR_SEED)

    for u, v, k, data in G.edges(data=True, keys=True):
        hw = data.get("highway", "unclassified")
        if isinstance(hw, list):
            hw = hw[0]

        base_t, base_s = HIGHWAY_ATTRS.get(hw, (1, 1))

        # Small random jitter so roads of the same type differ slightly
        traffic = max(1, min(3, base_t + rng.randint(-1, 0)))
        safety  = max(1, min(3, base_s + rng.randint(-1, 1)))

        # Condition: 60% good, 25% damaged, 10% flooded, 5% good (reset)
        r = rng.random()
        if r < 0.60:
            condition = 1
        elif r < 0.85:
            condition = 2
        elif r < 0.95:
            condition = 3
        else:
            condition = 1

        # Ensure length exists
        if "length" not in data or data["length"] is None:
            n_u = G.nodes[u]
            n_v = G.nodes[v]
            data["length"] = haversine_m(n_u["y"], n_u["x"], n_v["y"], n_v["x"])

        G[u][v][k].update(
            base_traffic=traffic,
            base_condition=condition,
            base_safety=safety,
            traffic=traffic,
            condition=condition,
            safety=safety,
        )


# ── Public API ─────────────────────────────────────────────────────────────────

def load_graph():
    """
    Return the NetworkX MultiDiGraph.
    Uses a pickle cache so the download only happens once.
    """
    if os.path.exists(GRAPH_CACHE):
        print("[graph_builder] Loading graph from cache …")
        with open(GRAPH_CACHE, "rb") as f:
            G = pickle.load(f)
        print(f"[graph_builder] Loaded: {len(G.nodes)} nodes, {len(G.edges)} edges")
        return G

    print("[graph_builder] Downloading road network from OpenStreetMap …")
    G = ox.graph_from_point(
        (CENTER_LAT, CENTER_LON),
        dist=DIST_METERS,
        network_type="drive",
        simplify=True,
    )
    # Convert to plain DiGraph for simpler edge access
    # (keeps only the minimum-length parallel edge between any two nodes)
    G = ox.convert.to_digraph(G, weight="length")
    # Re-wrap in a MultiDiGraph so algorithms work uniformly
    import networkx as nx
    G = nx.MultiDiGraph(G)

    print(f"[graph_builder] Downloaded: {len(G.nodes)} nodes, {len(G.edges)} edges")
    _assign_attributes(G)

    with open(GRAPH_CACHE, "wb") as f:
        pickle.dump(G, f)
    print("[graph_builder] Graph cached.")
    return G


def graph_to_json(G):
    """Serialise the graph to plain dicts for JSON responses."""
    nodes = []
    for nid, data in G.nodes(data=True):
        nodes.append(
            {
                "id": str(nid),
                "lat": data.get("y", 0),
                "lon": data.get("x", 0),
                "name": data.get("name", ""),
            }
        )

    edges = []
    seen = set()
    for u, v, k, data in G.edges(data=True, keys=True):
        key = (str(u), str(v), k)
        if key in seen:
            continue
        seen.add(key)
        edges.append(
            {
                "source": str(u),
                "target": str(v),
                "key": k,
                "length": round(data.get("length", 0), 2),
                "traffic": data.get("traffic", 1),
                "condition": data.get("condition", 1),
                "safety": data.get("safety", 1),
                "highway": (
                    data.get("highway", "unclassified")
                    if isinstance(data.get("highway"), str)
                    else data.get("highway", ["unclassified"])[0]
                ),
                "name": (
                    data.get("name", "")
                    if isinstance(data.get("name"), str)
                    else (data.get("name") or [""])[0]
                ),
            }
        )

    lats = [d.get("y", 0) for _, d in G.nodes(data=True)]
    lons = [d.get("x", 0) for _, d in G.nodes(data=True)]

    return {
        "nodes": nodes,
        "edges": edges,
        "bounds": {
            "min_lat": min(lats),
            "max_lat": max(lats),
            "min_lon": min(lons),
            "max_lon": max(lons),
            "center_lat": CENTER_LAT,
            "center_lon": CENTER_LON,
        },
        "stats": {
            "num_nodes": len(G.nodes),
            "num_edges": len(G.edges),
        },
    }
