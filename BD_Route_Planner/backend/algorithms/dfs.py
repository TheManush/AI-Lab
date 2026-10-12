"""
algorithms/dfs.py  —  Depth-First Search
-----------------------------------------
Strategy  : LIFO stack; dives as deep as possible before backtracking.
Optimality: NOT optimal — may return a very long/expensive path.
Completeness: NOT guaranteed in cyclic graphs (though we avoid cycles via
              path-set tracking).
Note      : DFS is useful as a baseline to show how poorly an uninformed
            depth-first traversal can perform on road networks.
"""

import time

from .common import build_result, get_best_edge, not_found_result


def dfs(G, source, target, weights: dict) -> dict:
    t0 = time.time()

    # stack holds (current_node, path_so_far)
    stack          = [(source, [source])]
    visited        = set()
    nodes_expanded = 0
    explored_seq   = []

    while stack:
        node, path = stack.pop()

        if node in visited:
            continue
        visited.add(node)
        nodes_expanded += 1
        explored_seq.append(node)

        if node == target:
            return build_result(G, path, explored_seq, nodes_expanded, weights, t0)

        # Push in reverse order so the first neighbour is explored first
        neighbors = list(G.successors(node))
        for neighbor in reversed(neighbors):
            if neighbor not in visited:
                _, cost = get_best_edge(G, node, neighbor, weights)
                if cost == float("inf"):      # blocked edge
                    continue
                stack.append((neighbor, path + [neighbor]))

    return not_found_result(explored_seq, nodes_expanded, t0)
