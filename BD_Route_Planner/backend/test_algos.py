"""
test_algos.py
-------------
Quick sanity-check for all 6 routing algorithms.

Picks a source node, then finds a destination that is reachable and
within ~10-15 hops (small enough for IDS to finish in < 2 s).
"""

import random
import time
from collections import deque

from graph_builder import load_graph
from algorithms import astar, best_first, bfs, dfs, ids, ucs

# ── Load graph ────────────────────────────────────────────────────────────────
G = load_graph()
print(f"Graph: {len(G.nodes)} nodes, {len(G.edges)} edges\n")

# ── Pick src + dst that are 8-14 hops apart (BFS hop distance) ────────────────
random.seed(42)
nodes = list(G.nodes)

def find_nearby_pair(G, seed_node, min_hops=8, max_hops=14):
    """BFS from seed_node; return a node that is min_hops..max_hops away."""
    visited = {seed_node: 0}
    q = deque([seed_node])
    candidates = []
    while q:
        n = q.popleft()
        d = visited[n]
        if min_hops <= d <= max_hops:
            candidates.append(n)
        if d >= max_hops:
            continue
        for nb in G.successors(n):
            if nb not in visited:
                visited[nb] = d + 1
                q.append(nb)
    return random.choice(candidates) if candidates else None

src = random.choice(nodes)
dst = find_nearby_pair(G, src)
if dst is None:
    # Fallback: pick any reachable node
    src = nodes[0]
    dst = find_nearby_pair(G, src, min_hops=4, max_hops=20)

print(f"Source : {src}")
print(f"Target : {dst}")
print()

# ── Run all algorithms ────────────────────────────────────────────────────────
weights = {"distance": 1.0, "traffic": 1.0, "condition": 1.0, "safety": 1.0}

algos = [
    ("BFS",        bfs),
    ("DFS",        dfs),
    ("UCS",        ucs),
    ("IDS",        ids),
    ("Best-First", best_first),
    ("A*",         astar),
]

print(f"{'Algorithm':<12} | {'Found':<5} | {'Dist (km)':<10} | {'Cost':<10} | {'Nodes exp':<10} | {'Time (ms)'}")
print("-" * 72)
for name, fn in algos:
    t0 = time.time()
    r  = fn(G, src, dst, weights)
    ms = round((time.time() - t0) * 1000, 1)
    s  = r["stats"]
    found = r["found"]
    dist  = f"{s['distance_km']:.3f}" if found else "N/A"
    cost  = f"{s['total_cost']:.4f}"  if found else "N/A"
    # Use reported ms from stat (more precise) but also show wall-clock
    print(f"{name:<12} | {str(found):<5} | {dist:<10} | {cost:<10} | {s['nodes_expanded']:<10} | {s['runtime_ms']} ms")
