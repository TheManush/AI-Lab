"""
algorithms/best_first.py  —  Greedy Best-First Search
------------------------------------------------------
Strategy  : Priority queue ordered purely by heuristic h(n) — the estimated
            cost from n to goal (straight-line distance × w_distance).
Optimality: NOT optimal — ignores accumulated cost g(n).  Can be misled by
            the heuristic into choosing a costly actual path.
Completeness: Complete on finite graphs (with visited set).
Speed     : Usually very fast — strong heuristic guidance.

Heuristic (admissible, see cost_function.py):
  h(n) = haversine(n, goal) [km] × w_distance
"""

import heapq
import time

from cost_function import heuristic
from .common import build_result, get_best_edge, not_found_result


def best_first(G, source, target, weights: dict) -> dict:
    t0 = time.time()

    h_src  = heuristic(source, target, G, weights)
    counter = 0
    # heap item: (h, counter, node, path)
    heap   = [(h_src, counter, source, [source])]
    visited        = set()
    nodes_expanded = 0
    explored_seq   = []

    while heap:
        h, _, node, path = heapq.heappop(heap)

        if node in visited:
            continue
        visited.add(node)
        nodes_expanded += 1
        explored_seq.append(node)

        if node == target:
            return build_result(G, path, explored_seq, nodes_expanded, weights, t0)

        for neighbor in G.successors(node):
            if neighbor in visited:
                continue
            _, cost = get_best_edge(G, node, neighbor, weights)
            if cost == float("inf"):
                continue
            h_n = heuristic(neighbor, target, G, weights)
            counter += 1
            heapq.heappush(heap, (h_n, counter, neighbor, path + [neighbor]))

    return not_found_result(explored_seq, nodes_expanded, t0)
