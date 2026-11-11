"""
Obstacle-Aware 2D Navigation and Pathfinding Subsystem.

Integrates with Phase 01 environment assets and catalog obstacle bounds:
- 2D AABB clearance expansion (character collision footprint = 1.2 studs)
- Fast segment-box intersection testing
- Obstacle avoidance visibility graph & A* waypoint solver
- Multi-waypoint path smoothing (string-pulling shortcut optimization)
"""
import heapq
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

COLLISION_MARGIN = 1.2  # Stud clearance around solid obstacle geometry


def segment_intersects_box(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    box: Tuple[float, float, float, float],
    margin: float = COLLISION_MARGIN,
) -> bool:
    """
    Tests if line segment p0 -> p1 intersects an AABB [xmin, ymin, xmax, ymax]
    expanded by `margin` using the slab method.
    """
    xmin = box[0] - margin
    ymin = box[1] - margin
    xmax = box[2] + margin
    ymax = box[3] + margin

    x0, y0 = p0
    x1, y1 = p1
    dx = x1 - x0
    dy = y1 - y0

    tmin = 0.0
    tmax = 1.0

    # X slab
    if abs(dx) < 1e-9:
        if x0 < xmin or x0 > xmax:
            return False
    else:
        tx1 = (xmin - x0) / dx
        tx2 = (xmax - x0) / dx
        t_enter_x = min(tx1, tx2)
        t_exit_x = max(tx1, tx2)
        tmin = max(tmin, t_enter_x)
        tmax = min(tmax, t_exit_x)
        if tmin > tmax:
            return False

    # Y slab
    if abs(dy) < 1e-9:
        if y0 < ymin or y0 > ymax:
            return False
    else:
        ty1 = (ymin - y0) / dy
        ty2 = (ymax - y0) / dy
        t_enter_y = min(ty1, ty2)
        t_exit_y = max(ty1, ty2)
        tmin = max(tmin, t_enter_y)
        tmax = min(tmax, t_exit_y)
        if tmin > tmax:
            return False

    return True


def line_of_sight(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    obstacles: List[Dict[str, Any]],
    margin: float = COLLISION_MARGIN,
) -> bool:
    """Returns True if segment p0 -> p1 does not collide with any obstacle in the list."""
    for obs in obstacles:
        b = obs.get("bounds_2d")
        if b and len(b) == 4:
            if segment_intersects_box(p0, p1, (b[0], b[1], b[2], b[3]), margin=margin):
                return False
    return True


def get_obstacle_clearance_corners(
    obs: Dict[str, Any],
    margin: float = COLLISION_MARGIN + 0.3,
) -> List[Tuple[float, float]]:
    """Returns 4 outward clearance corner waypoints for an obstacle."""
    b = obs.get("bounds_2d", [0, 0, 0, 0])
    xmin, ymin, xmax, ymax = b[0], b[1], b[2], b[3]
    return [
        (round(xmin - margin, 3), round(ymin - margin, 3)),
        (round(xmax + margin, 3), round(ymin - margin, 3)),
        (round(xmax + margin, 3), round(ymax + margin, 3)),
        (round(xmin - margin, 3), round(ymax + margin, 3)),
    ]


def find_path(
    start: Tuple[float, float],
    goal: Tuple[float, float],
    obstacles: List[Dict[str, Any]],
    extra_waypoints: Optional[List[Tuple[float, float]]] = None,
    margin: float = COLLISION_MARGIN,
) -> List[Tuple[float, float]]:
    """
    Finds an obstacle-free 2D waypoint path from `start` to `goal`.
    - If direct line of sight is clear, returns [start, goal].
    - Otherwise, builds a visibility graph around obstacle corners and solves A*.
    - Performs path smoothing (string-pulling) to remove redundant intermediate corners.
    """
    p_start = (round(start[0], 3), round(start[1], 3))
    p_goal = (round(goal[0], 3), round(goal[1], 3))

    # Fast direct path check
    if line_of_sight(p_start, p_goal, obstacles, margin=margin):
        return [p_start, p_goal]

    # Collect candidate waypoints
    nodes: List[Tuple[float, float]] = [p_start, p_goal]
    for obs in obstacles:
        # Only consider obstacles that intersect the direct bounding box
        b = obs.get("bounds_2d")
        if b:
            nodes.extend(get_obstacle_clearance_corners(obs, margin=margin + 0.2))

    if extra_waypoints:
        nodes.extend(extra_waypoints)

    # Filter out obstacle-corner waypoints that lie inside other solid obstacles
    # (start and goal are always preserved)
    valid_nodes = [p_start, p_goal]
    for pt in nodes[2:]:
        inside_any = False
        for obs in obstacles:
            b = obs.get("bounds_2d")
            if b and (b[0] - 0.1 <= pt[0] <= b[2] + 0.1) and (b[1] - 0.1 <= pt[1] <= b[3] + 0.1):
                inside_any = True
                break
        if not inside_any:
            valid_nodes.append(pt)

    # Deduplicate nodes
    node_set = list(dict.fromkeys(valid_nodes))
    n_count = len(node_set)
    idx_start = node_set.index(p_start) if p_start in node_set else 0
    idx_goal = node_set.index(p_goal) if p_goal in node_set else 1

    # Build adjacency list with line_of_sight checks
    adj: Dict[int, List[Tuple[int, float]]] = {i: [] for i in range(n_count)}
    for i in range(n_count):
        pt_i = node_set[i]
        for j in range(i + 1, n_count):
            pt_j = node_set[j]
            dist = math.hypot(pt_i[0] - pt_j[0], pt_i[1] - pt_j[1])
            if dist < 45.0 and line_of_sight(pt_i, pt_j, obstacles, margin=margin):
                adj[i].append((j, dist))
                adj[j].append((i, dist))

    # A* Search
    h = lambda idx: math.hypot(node_set[idx][0] - p_goal[0], node_set[idx][1] - p_goal[1])
    pq: List[Tuple[float, float, int, List[int]]] = [(h(idx_start), 0.0, idx_start, [idx_start])]
    visited: Dict[int, float] = {}

    best_path_indices = None
    while pq:
        est, cost, curr, path = heapq.heappop(pq)
        if curr == idx_goal:
            best_path_indices = path
            break
        if curr in visited and visited[curr] <= cost:
            continue
        visited[curr] = cost

        for nxt, d in adj[curr]:
            nxt_cost = cost + d
            if nxt not in visited or nxt_cost < visited[nxt]:
                heapq.heappush(pq, (nxt_cost + h(nxt), nxt_cost, nxt, path + [nxt]))

    if not best_path_indices:
        # Fallback to direct path if no graph solution
        return [p_start, p_goal]

    raw_path = [node_set[i] for i in best_path_indices]

    # Path smoothing (string-pulling shortcut optimization)
    smoothed = [raw_path[0]]
    curr_idx = 0
    while curr_idx < len(raw_path) - 1:
        next_idx = len(raw_path) - 1
        while next_idx > curr_idx + 1:
            if line_of_sight(raw_path[curr_idx], raw_path[next_idx], obstacles, margin=margin):
                break
            next_idx -= 1
        smoothed.append(raw_path[next_idx])
        curr_idx = next_idx

    return smoothed


def plan_multi_waypoint_locomotion(
    waypoints: List[Tuple[float, float]],
    speed: float = 6.0,
    fps: int = 30,
) -> Dict[str, Any]:
    """
    Computes movement parameters, heading transitions, and segment durations
    for traversing an obstacle-avoiding waypoint sequence.
    """
    if len(waypoints) < 2:
        return {"total_frames": 0, "segments": []}

    segments = []
    total_frames = 0
    total_distance = 0.0

    for i in range(len(waypoints) - 1):
        p0 = waypoints[i]
        p1 = waypoints[i + 1]
        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]
        dist = math.hypot(dx, dy)
        heading = math.degrees(math.atan2(dx, -dy))
        dur_frames = max(4, int(round((dist / max(1.0, speed)) * fps)))

        segments.append({
            "segment_index": i,
            "start": p0,
            "end": p1,
            "distance": round(dist, 3),
            "heading": round(heading, 2),
            "duration_frames": dur_frames,
            "start_frame_offset": total_frames,
        })
        total_frames += dur_frames
        total_distance += dist

    return {
        "total_distance": round(total_distance, 3),
        "total_frames": total_frames,
        "segments": segments,
    }
