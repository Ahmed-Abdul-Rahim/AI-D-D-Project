"""
Post-hoc quality metrics for a generated dungeon.
Used by the dungeon-generation evaluation harness — keeps metric definitions
in one place so every algorithm is judged identically.
"""

from collections import deque
from typing import Dict, List, Optional, Tuple

from models import Dungeon, ItemType, RoomType


def is_connected(dungeon: Dungeon) -> bool:
    """All rooms reachable from any starting room via room.connections."""
    if not dungeon.rooms:
        return False
    start = next(iter(dungeon.rooms))
    visited = {start}
    q = deque([start])
    while q:
        cur = q.popleft()
        for nb in dungeon.rooms[cur].connections:
            if nb in dungeon.rooms and nb not in visited:
                visited.add(nb)
                q.append(nb)
    return len(visited) == len(dungeon.rooms)


def shortest_path(dungeon: Dungeon,
                  src: Tuple[int, int],
                  dst: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
    """BFS over connections; None if no path."""
    if src not in dungeon.rooms or dst not in dungeon.rooms:
        return None
    if src == dst:
        return [src]
    parent = {src: None}
    q = deque([src])
    while q:
        cur = q.popleft()
        for nb in dungeon.rooms[cur].connections:
            if nb not in parent and nb in dungeon.rooms:
                parent[nb] = cur
                if nb == dst:
                    # reconstruct
                    path = [nb]
                    while parent[path[-1]] is not None:
                        path.append(parent[path[-1]])
                    return list(reversed(path))
                q.append(nb)
    return None


def has_key(dungeon: Dungeon) -> bool:
    return any(item.item_type == ItemType.KEY
               for room in dungeon.rooms.values()
               for item in room.items)


def key_position(dungeon: Dungeon) -> Optional[Tuple[int, int]]:
    for coords, room in dungeon.rooms.items():
        if any(i.item_type == ItemType.KEY for i in room.items):
            return coords
    return None


def is_solvable(dungeon: Dungeon) -> bool:
    """A dungeon is solvable iff: connected, has start+boss+key, and the
    player can reach the key first, then the boss, from the start."""
    start = dungeon.start_position
    boss = dungeon.boss_position
    key = key_position(dungeon)
    if start is None or boss is None or key is None:
        return False
    if not is_connected(dungeon):
        return False
    return (shortest_path(dungeon, start, key) is not None
            and shortest_path(dungeon, start, boss) is not None)


def start_to_boss_distance(dungeon: Dungeon) -> Optional[int]:
    s, b = dungeon.start_position, dungeon.boss_position
    if s is None or b is None:
        return None
    p = shortest_path(dungeon, s, b)
    return len(p) - 1 if p else None


def branching_factor(dungeon: Dungeon) -> float:
    if not dungeon.rooms:
        return 0.0
    return sum(len(r.connections) for r in dungeon.rooms.values()) / len(dungeon.rooms)


def dead_end_ratio(dungeon: Dungeon) -> float:
    if not dungeon.rooms:
        return 0.0
    dead = sum(1 for r in dungeon.rooms.values() if len(r.connections) == 1)
    return dead / len(dungeon.rooms)


def room_type_counts(dungeon: Dungeon) -> Dict[str, int]:
    counts = {rt.value: 0 for rt in RoomType}
    for r in dungeon.rooms.values():
        counts[r.room_type.value] += 1
    return counts


def metric_bundle(dungeon: Optional[Dungeon]) -> Dict[str, float]:
    """All quality metrics in one dict — ready for CSV output."""
    if dungeon is None or not dungeon.rooms:
        return {
            "rooms_built": 0,
            "connected": 0,
            "has_key": 0,
            "solvable": 0,
            "start_boss_dist": -1,
            "branching": 0.0,
            "dead_end_ratio": 0.0,
            **{f"n_{rt.value}": 0 for rt in RoomType},
        }
    counts = room_type_counts(dungeon)
    return {
        "rooms_built": len(dungeon.rooms),
        "connected": int(is_connected(dungeon)),
        "has_key": int(has_key(dungeon)),
        "solvable": int(is_solvable(dungeon)),
        "start_boss_dist": start_to_boss_distance(dungeon) or -1,
        "branching": branching_factor(dungeon),
        "dead_end_ratio": dead_end_ratio(dungeon),
        **{f"n_{k}": v for k, v in counts.items()},
    }
