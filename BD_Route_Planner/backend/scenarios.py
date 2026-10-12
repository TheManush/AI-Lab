"""
scenarios.py
------------
Applies a named traffic / road-condition / safety scenario to the graph
by modifying the working attributes (traffic, condition, safety) on each edge.
The base_* attributes are always preserved so the graph can be reset.

Key fix: base_condition already has ~9% edges at condition>=3 from graph_builder.
We now reset condition to 1 (Good) for ALL edges before applying scenario, so
the scenario effects are clean and clearly visible.

Supported scenarios
~~~~~~~~~~~~~~~~~~~
  normal         -- all roads reset to good condition, base traffic/safety
  peak_hour      -- major roads become heavily congested (traffic=3)
  heavy_traffic  -- all roads at maximum traffic
  flooded        -- 50% of roads are flooded (condition=3)
  road_blocked   -- 40% of roads are blocked (impassable, condition=4)
  night          -- safety degrades on all roads
  storm          -- traffic + condition + safety all worsen severely
"""

import random

SCENARIO_SEED = 99   # fixed seed so scenarios are reproducible


def apply_scenario(G, scenario_name: str) -> None:
    """
    Modify G's edge attributes in-place to reflect `scenario_name`.
    Always resets from base_* first so scenarios are independent.
    """
    # ── 1. Full reset to base values ──────────────────────────────────────────
    for u, v, k, data in G.edges(data=True, keys=True):
        G[u][v][k]["traffic"]   = data.get("base_traffic",   1)
        G[u][v][k]["condition"] = data.get("base_condition", 1)
        G[u][v][k]["safety"]    = data.get("base_safety",    1)

    # ── 2. Apply scenario ─────────────────────────────────────────────────────
    rng = random.Random(SCENARIO_SEED)
    edge_list = list(G.edges(keys=True))

    if scenario_name == "normal":
        # Reset condition to 1 (Good) for all edges — clean baseline
        for u, v, k in edge_list:
            G[u][v][k]["condition"] = 1

    elif scenario_name == "peak_hour":
        # Major roads get heavy congestion
        HIGH_ROADS = {"trunk", "trunk_link", "primary", "primary_link",
                      "secondary", "secondary_link"}
        for u, v, k, data in G.edges(data=True, keys=True):
            hw = data.get("highway", "unclassified")
            if isinstance(hw, list):
                hw = hw[0]
            if hw in HIGH_ROADS:
                G[u][v][k]["traffic"] = 3
            else:
                G[u][v][k]["traffic"] = min(3, data.get("base_traffic", 1) + 1)

    elif scenario_name == "heavy_traffic":
        for u, v, k in edge_list:
            G[u][v][k]["traffic"] = 3

    elif scenario_name == "flooded":
        # Reset condition first (override base flooded edges)
        for u, v, k in edge_list:
            G[u][v][k]["condition"] = 1
        # Flood 50% of edges — clearly visible effect
        n_flood = max(1, int(len(edge_list) * 0.50))
        for u, v, k in rng.sample(edge_list, n_flood):
            G[u][v][k]["condition"] = 3   # flooded

    elif scenario_name == "road_blocked":
        # Reset condition first
        for u, v, k in edge_list:
            G[u][v][k]["condition"] = 1
        # Block 40% of edges — forces clearly different paths
        n_block = max(1, int(len(edge_list) * 0.40))
        for u, v, k in rng.sample(edge_list, n_block):
            G[u][v][k]["condition"] = 4   # blocked (cost = inf)

    elif scenario_name == "night":
        # All roads become risky at night
        for u, v, k in edge_list:
            G[u][v][k]["safety"] = 3   # high risk everywhere

    elif scenario_name == "storm":
        # Reset condition first
        for u, v, k in edge_list:
            G[u][v][k]["condition"] = 1
        # Flood 40% of roads
        n_flood = max(1, int(len(edge_list) * 0.40))
        for u, v, k in rng.sample(edge_list, n_flood):
            G[u][v][k]["condition"] = 3
        # Max traffic + safety risk everywhere
        for u, v, k in edge_list:
            G[u][v][k]["traffic"] = 3
            G[u][v][k]["safety"]  = 3

    else:
        raise ValueError(f"Unknown scenario: {scenario_name!r}")
