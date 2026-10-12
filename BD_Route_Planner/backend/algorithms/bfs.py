"""
algorithms/bfs.py  —  Breadth-First Search
-------------------------------------------
Strategy  : FIFO queue; explores nodes level by level (hop-by-hop).
Optimality: Finds the path with the MINIMUM NUMBER OF HOPS (edges), NOT the
            minimum cost.  Does respect blocked edges (condition==4).
Completeness: Complete on finite graphs.
"""

import time
from collections import deque

from .common import build_result, get_best_edge, not_found_result


def bfs(G, source, target, weights: dict) -> dict:
    t0 = time.time()

    # queue holds (current_node, path_so_far)
    queue   = deque([(source, [source])])
    visited = {source}
    nodes_expanded = 0
    explored_seq   = []

    while queue:
        node, path = queue.popleft()
        nodes_expanded += 1
        explored_seq.append(node)

        if node == target:
            return build_result(G, path, explored_seq, nodes_expanded, weights, t0)

        for neighbor in G.successors(node):
            if neighbor in visited:
                continue
            _, cost = get_best_edge(G, node, neighbor, weights)
            if cost == float("inf"):          # blocked edge
                continue
            visited.add(neighbor)
            queue.append((neighbor, path + [neighbor]))

    return not_found_result(explored_seq, nodes_expanded, t0)
