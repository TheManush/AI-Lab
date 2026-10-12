"""
algorithms/astar.py  —  A* Search
------------------------------------
Strategy  : Priority queue ordered by f(n) = g(n) + h(n).
              g(n) = actual cost from source to n
              h(n) = admissible heuristic (straight-line × w_distance)
Optimality: Optimal — guaranteed to find the minimum-cost path when h is
            admissible (never overestimates).
Completeness: Complete.

Why better than UCS?
  A* uses h(n) to focus the search toward the goal, typically expanding
  far fewer nodes than UCS while still returning the optimal path.

Why better than Best-First?
  A* accounts for the actual cost g(n) as well, preventing it from being
  misled by the heuristic into ignoring an expensive partial path.
"""

import heapq
import time

from cost_function import heuristic
from .common import build_result, get_best_edge, not_found_result


def astar(G, source, target, weights: dict) -> dict:
    t0 = time.time()

    h_src   = heuristic(source, target, G, weights)
    counter  = 0
    # heap item: (f, counter, g, node, path)
    heap     = [(h_src, counter, 0.0, source, [source])]
    g_costs  = {source: 0.0}     # best g(n) seen so far
    visited  = set()
    nodes_expanded = 0
    explored_seq   = []

    while heap:
        f, _, g, node, path = heapq.heappop(heap)

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
            edge_data, edge_cost = get_best_edge(G, node, neighbor, weights)
            if edge_cost == float("inf"):
                continue
            new_g = g + edge_cost
            if new_g < g_costs.get(neighbor, float("inf")):
                g_costs[neighbor] = new_g
                h_n = heuristic(neighbor, target, G, weights)
                counter += 1
                heapq.heappush(
                    heap, (new_g + h_n, counter, new_g, neighbor, path + [neighbor])
                )

    return not_found_result(explored_seq, nodes_expanded, t0)
