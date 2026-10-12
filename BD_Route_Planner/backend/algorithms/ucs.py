"""
algorithms/ucs.py  —  Uniform Cost Search
------------------------------------------
Strategy  : Priority queue ordered by cumulative path cost g(n).
Optimality: Optimal — always finds the lowest-cost path (assuming non-negative
            edge costs, which our cost function guarantees).
Completeness: Complete.
Equivalence: Equivalent to Dijkstra's algorithm.
"""

import heapq
import time

from .common import build_result, get_best_edge, not_found_result


def ucs(G, source, target, weights: dict) -> dict:
    t0 = time.time()

    # heap item: (g_cost, counter, node, path)
    # counter breaks ties deterministically (avoids comparing node IDs)
    counter = 0
    heap    = [(0.0, counter, source, [source])]
    visited = {}            # node → best g_cost seen so far
    nodes_expanded = 0
    explored_seq   = []

    while heap:
        g, _, node, path = heapq.heappop(heap)

        if node in visited:
            continue
        visited[node]  = g
        nodes_expanded += 1
        explored_seq.append(node)

        if node == target:
            return build_result(G, path, explored_seq, nodes_expanded, weights, t0)

        for neighbor in G.successors(node):
            if neighbor in visited:
                continue
            edge_data, edge_cost = get_best_edge(G, node, neighbor, weights)
            if edge_cost == float("inf"):
                continue
            new_g = g + edge_cost
            if neighbor not in visited:
                counter += 1
                heapq.heappush(heap, (new_g, counter, neighbor, path + [neighbor]))

    return not_found_result(explored_seq, nodes_expanded, t0)
