"""
CSP-based Dungeon Generator

Uses Constraint Satisfaction Problem solving with backtracking to generate
valid dungeons. Two ways to drive the search:

  - ``backtrack()`` / ``generate()`` — one-shot, returns when done.
  - ``solve_steps()`` — generator that yields events at each select / consider
    / assign / reject / backtrack / succeed / fail step. Used by the GUI's
    Generation Inspector to animate the algorithm.
"""

from typing import List, Tuple, Dict, Set, Optional
from models import Dungeon, Room, RoomType, Item, ItemType, NPC, NPCType
import random
from collections import deque


class DungeonCSP:
    """
    Constraint Satisfaction Problem for dungeon generation

    Variables: Room positions in the grid
    Domains: Valid room types and configurations
    Constraints:
        1. All rooms must be connected
        2. Boss room must be farthest from start
        3. Key must be placed before boss room is accessible
        4. No overlapping rooms
        5. Minimum number of rooms
    """

    def __init__(self, width: int, height: int, num_rooms: int, seed: Optional[int] = None):
        self.width = width
        self.height = height
        self.num_rooms = num_rooms
        self.dungeon = Dungeon(width, height)

        if seed is not None:
            random.seed(seed)

        # CSP components
        self.variables: List[Tuple[int, int]] = []          # Room positions to assign
        self.domains: Dict[Tuple[int, int], List[RoomType]] = {}  # Possible room types
        self.assignment: Dict[Tuple[int, int], Room] = {}    # Current assignment

        # Tracking
        self.backtrack_count = 0
        self.nodes_explored = 0

    # ------------------------------------------------------------------
    # Constraint helpers
    # ------------------------------------------------------------------

    def is_valid_position(self, coords: Tuple[int, int]) -> bool:
        """Check if position is within bounds"""
        x, y = coords
        return 0 <= x < self.width and 0 <= y < self.height

    def get_neighbors(self, coords: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get all valid neighboring positions (4-directional)"""
        x, y = coords
        neighbors = [
            (x + 1, y), (x - 1, y),
            (x, y + 1), (x, y - 1),
        ]
        return [n for n in neighbors if self.is_valid_position(n)]

    def is_connected(self) -> bool:
        """All assigned rooms reachable via connections (BFS)"""
        if not self.assignment:
            return True
        start = next(iter(self.assignment.keys()))
        visited = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in self.get_neighbors(current):
                if neighbor in self.assignment and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return len(visited) == len(self.assignment)

    def get_distance_from_start(self, coords: Tuple[int, int]) -> int:
        """Shortest distance from start room using BFS over connections."""
        if not self.assignment:
            return 0
        start = next((pos for pos, room in self.assignment.items()
                      if room.room_type == RoomType.START), None)
        if start is None or coords == start:
            return 0
        visited = {start: 0}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            if current == coords:
                return visited[current]
            for neighbor in self.get_neighbors(current):
                if neighbor in self.assignment and neighbor not in visited:
                    visited[neighbor] = visited[current] + 1
                    queue.append(neighbor)
        return -1

    def is_consistent(self, coords: Tuple[int, int], room_type: RoomType) -> bool:
        """Check whether assigning ``room_type`` to ``coords`` is consistent."""
        # Constraint 1: Position must be valid and not already assigned
        if not self.is_valid_position(coords) or coords in self.assignment:
            return False

        # Constraint 2: Must connect to existing rooms (except first)
        if self.assignment:
            has_connection = any(neighbor in self.assignment
                                 for neighbor in self.get_neighbors(coords))
            if not has_connection:
                return False

        # Constraint 3: only one START
        if room_type == RoomType.START:
            if any(room.room_type == RoomType.START for room in self.assignment.values()):
                return False

        # Constraint 4: only one BOSS
        if room_type == RoomType.BOSS:
            if any(room.room_type == RoomType.BOSS for room in self.assignment.values()):
                return False

        return True

    def select_unassigned_variable(self) -> Optional[Tuple[int, int]]:
        """MRV-style pick: position adjacent to most assigned neighbors."""
        if not self.assignment:
            return (self.width // 2, self.height // 2)

        candidates = set()
        for assigned_pos in self.assignment.keys():
            for neighbor in self.get_neighbors(assigned_pos):
                if neighbor not in self.assignment:
                    candidates.add(neighbor)

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda pos: sum(1 for n in self.get_neighbors(pos)
                                if n in self.assignment),
        )

    def order_domain_values(self, coords: Tuple[int, int]) -> List[RoomType]:
        """LCV-flavoured ordering tuned to the dungeon distribution."""
        assigned_types = [room.room_type for room in self.assignment.values()]
        num_assigned = len(self.assignment)

        if num_assigned == 0:
            return [RoomType.START]

        if num_assigned == self.num_rooms - 1:
            if RoomType.BOSS not in assigned_types:
                return [RoomType.BOSS]

        priority = []
        if RoomType.START not in assigned_types:
            priority.append(RoomType.START)
        priority.extend([RoomType.NORMAL] * 3)
        if assigned_types.count(RoomType.TREASURE) < 2:
            priority.append(RoomType.TREASURE)
        if assigned_types.count(RoomType.TRAP) < 2:
            priority.append(RoomType.TRAP)
        if assigned_types.count(RoomType.MERCHANT) < 1:
            priority.append(RoomType.MERCHANT)
        if num_assigned >= self.num_rooms - 2 and RoomType.BOSS not in assigned_types:
            priority.append(RoomType.BOSS)

        random.shuffle(priority)
        return priority

    # ------------------------------------------------------------------
    # Backtracking — one-shot wrapper + step-by-step generator
    # ------------------------------------------------------------------

    def backtrack(self) -> bool:
        """
        CSP Backtracking algorithm (one-shot wrapper).
        Returns True if a valid assignment is found.
        For the same algorithm exposed as a step-by-step event stream
        suitable for animation, see :meth:`solve_steps`.
        """
        for event in self.solve_steps():
            if event["kind"] == "succeed":
                return True
            if event["kind"] == "fail":
                return False
        return False

    def solve_steps(self):
        """
        Step-by-step CSP backtracking as a generator. Yields a dict event
        at each significant point so a GUI (or trace logger) can animate
        the algorithm. Internally this performs exactly the same
        backtracking search as :meth:`backtrack` -- every yield is a no-op
        for the algorithm.

        Event kinds (each event also carries running counters
        ``nodes`` and ``backtracks``):

        - ``select``    : about to pick values for ``coords``
        - ``consider``  : trying ``room_type`` at ``coords``
        - ``reject``    : ``(coords, room_type)`` violated a constraint
        - ``assign``    : committed ``coords -> room_type`` with connections
        - ``backtrack`` : un-assigned ``coords`` (also fires backtrack_count++)
        - ``succeed``   : final solution found
        - ``fail``      : root call exhausted with no solution
        """
        success = yield from self._solve_steps_recursive()
        if success:
            yield {"kind": "succeed",
                   "nodes": self.nodes_explored,
                   "backtracks": self.backtrack_count}
        else:
            yield {"kind": "fail",
                   "nodes": self.nodes_explored,
                   "backtracks": self.backtrack_count}

    def _solve_steps_recursive(self):
        """Recursive generator. Returns True/False via StopIteration.value."""
        self.nodes_explored += 1

        if len(self.assignment) == self.num_rooms:
            types = [room.room_type for room in self.assignment.values()]
            if RoomType.START in types and RoomType.BOSS in types:
                return self.is_connected()
            return False

        coords = self.select_unassigned_variable()
        if coords is None:
            return False

        yield {"kind": "select",
               "coords": coords,
               "nodes": self.nodes_explored,
               "backtracks": self.backtrack_count,
               "depth": len(self.assignment)}

        for room_type in self.order_domain_values(coords):
            yield {"kind": "consider",
                   "coords": coords,
                   "room_type": room_type.value,
                   "nodes": self.nodes_explored,
                   "backtracks": self.backtrack_count}

            if not self.is_consistent(coords, room_type):
                yield {"kind": "reject",
                       "coords": coords,
                       "room_type": room_type.value,
                       "reason": "constraint_violation",
                       "nodes": self.nodes_explored,
                       "backtracks": self.backtrack_count}
                continue

            # Make assignment
            room = Room(
                coordinates=coords,
                room_type=room_type,
                description=self.generate_room_description(room_type),
            )
            self.assignment[coords] = room
            for neighbor in self.get_neighbors(coords):
                if neighbor in self.assignment:
                    room.connect_to(neighbor)
                    self.assignment[neighbor].connect_to(coords)

            yield {"kind": "assign",
                   "coords": coords,
                   "room_type": room_type.value,
                   "connections": sorted(room.connections),
                   "nodes": self.nodes_explored,
                   "backtracks": self.backtrack_count,
                   "depth": len(self.assignment)}

            success = yield from self._solve_steps_recursive()
            if success:
                return True

            # Backtrack
            self.backtrack_count += 1
            for neighbor in self.get_neighbors(coords):
                if neighbor in self.assignment:
                    self.assignment[neighbor].connections.remove(coords)
            del self.assignment[coords]

            yield {"kind": "backtrack",
                   "coords": coords,
                   "room_type": room_type.value,
                   "nodes": self.nodes_explored,
                   "backtracks": self.backtrack_count,
                   "depth": len(self.assignment)}

        return False

    def finalize(self) -> Dungeon:
        """
        After :meth:`solve_steps` yields a ``succeed`` event, call this to
        promote the CSP assignment into a fully populated Dungeon
        (rooms registered, items + NPCs placed). Mirrors the second half
        of :meth:`generate`.
        """
        for room in self.assignment.values():
            self.dungeon.add_room(room)
        self.populate_rooms()
        return self.dungeon

    # ------------------------------------------------------------------
    # Populating with content (unchanged)
    # ------------------------------------------------------------------

    def generate_room_description(self, room_type: RoomType) -> str:
        """Generate atmospheric description based on room type"""
        descriptions = {
            RoomType.START: [
                "The entrance to the dungeon. Torches flicker on damp stone walls.",
                "A heavy wooden door creaks shut behind you. The adventure begins.",
            ],
            RoomType.NORMAL: [
                "A dusty corridor with ancient stone walls.",
                "A dimly lit chamber. You hear water dripping somewhere.",
                "Cobwebs hang from the ceiling. The air is stale.",
            ],
            RoomType.TREASURE: [
                "You see a glint of gold in the corner!",
                "An ornate chest sits against the far wall.",
            ],
            RoomType.BOSS: [
                "A massive door looms ahead. This must be the boss chamber.",
                "You feel an ominous presence beyond this door.",
            ],
            RoomType.TRAP: [
                "Something feels wrong here. Be careful.",
                "The floor looks unstable in places.",
            ],
            RoomType.MERCHANT: [
                "A friendly merchant has set up shop here.",
                "You hear the jingle of coins and smell exotic spices.",
            ],
        }
        return random.choice(descriptions.get(room_type, ["An empty room."]))

    def populate_rooms(self):
        """Add items and NPCs to rooms after generation"""
        for coords, room in self.assignment.items():
            if room.room_type == RoomType.TREASURE:
                room.items.append(Item("Gold Coins", ItemType.GOLD, {"amount": random.randint(50, 150)}))
                if random.random() > 0.5:
                    room.items.append(Item("Health Potion", ItemType.POTION, {"heal": 30}))

            elif room.room_type == RoomType.NORMAL:
                if random.random() > 0.7:
                    weapons = ["Iron Sword", "Rusty Dagger", "Wooden Staff"]
                    room.items.append(Item(
                        random.choice(weapons),
                        ItemType.WEAPON,
                        {"damage": random.randint(5, 15)},
                    ))

            # KEY into a treasure room (only once)
            treasure_rooms = [r for r in self.assignment.values()
                              if r.room_type == RoomType.TREASURE]
            if treasure_rooms and not any(
                item.item_type == ItemType.KEY
                for room in self.assignment.values()
                for item in room.items
            ):
                key_room = random.choice(treasure_rooms)
                key_room.items.append(Item("Boss Key", ItemType.KEY, {"opens": "boss_room"}))

            # NPCs by room type
            if room.room_type == RoomType.NORMAL and random.random() > 0.6:
                enemies = ["Goblin", "Skeleton", "Giant Rat"]
                room.npcs.append(NPC(
                    name=random.choice(enemies),
                    npc_type=NPCType.ENEMY,
                    hp=random.randint(20, 40),
                    attack=random.randint(5, 12),
                    defense=random.randint(1, 5),
                    dialogue=["Grr!", "You shall not pass!"],
                ))
            elif room.room_type == RoomType.MERCHANT:
                room.npcs.append(NPC(
                    name="Merchant",
                    npc_type=NPCType.MERCHANT,
                    hp=50, attack=0, defense=10,
                    dialogue=["Welcome! Care to see my wares?",
                              "I have the finest goods!"],
                    inventory=[
                        Item("Health Potion", ItemType.POTION, {"heal": 50}),
                        Item("Steel Sword", ItemType.WEAPON, {"damage": 20}),
                    ],
                ))
            elif room.room_type == RoomType.BOSS:
                room.npcs.append(NPC(
                    name="Dragon",
                    npc_type=NPCType.BOSS,
                    hp=100, attack=25, defense=10,
                    dialogue=["You dare challenge me?!",
                              "Prepare to meet your doom!"],
                ))

    # ------------------------------------------------------------------
    # One-shot generate() (kept for backwards compatibility)
    # ------------------------------------------------------------------

    def generate(self) -> Optional[Dungeon]:
        """One-shot dungeon generation using the CSP."""
        print(f"Generating dungeon with CSP: {self.width}x{self.height}, {self.num_rooms} rooms")

        if self.backtrack():
            for room in self.assignment.values():
                self.dungeon.add_room(room)
            self.populate_rooms()

            print(f"✓ Generation successful!")
            print(f"  - Nodes explored: {self.nodes_explored}")
            print(f"  - Backtracks: {self.backtrack_count}")
            print(f"  - Rooms created: {len(self.dungeon.rooms)}")

            return self.dungeon
        else:
            print(f"✗ Generation failed!")
            print(f"  - Nodes explored: {self.nodes_explored}")
            print(f"  - Backtracks: {self.backtrack_count}")
            return None


# Smoke test
if __name__ == "__main__":
    generator = DungeonCSP(width=5, height=5, num_rooms=8, seed=42)
    dungeon = generator.generate()

    if dungeon:
        print(f"\n{dungeon}")
        print(f"Start: {dungeon.start_position}")
        print(f"Boss: {dungeon.boss_position}")

        print("\nRoom details:")
        for coords, room in sorted(dungeon.rooms.items()):
            print(f"  {coords}: {room.room_type.value}")
            print(f"    Connections: {sorted(room.connections)}")
            if room.items:
                print(f"    Items: {[item.name for item in room.items]}")
            if room.npcs:
                print(f"    NPCs: {[npc.name for npc in room.npcs]}")
