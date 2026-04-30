"""
CSP-based Dungeon Generator
Uses Constraint Satisfaction Problem solving with backtracking to generate valid dungeons.
Refactored for Step-Generation (Generator Pattern) and Circular Growth Heuristic.
"""

import random
import math
from collections import deque
from typing import List, Tuple, Dict, Set, Optional, Generator
from models import Dungeon, Room, RoomType, Item, ItemType, NPC, NPCType


class DungeonCSP:
    """
    Constraint Satisfaction Problem for dungeon generation.
    
    Variables: Room positions in the grid.
    Heuristics: Circular growth via Euclidean distance to center.
    """
    
    def __init__(self, width: int, height: int, min_rooms: int, max_rooms: int, seed: Optional[int] = None):
        self.width = width
        self.height = height
        self.start_pos = (width // 2, height // 2)
        
        if seed is not None:
            random.seed(seed)
            
        self.num_rooms = random.randint(min_rooms, max_rooms)
        self.dungeon = Dungeon(width, height)
        self.assignment: Dict[Tuple[int, int], Room] = {}
        
        # Performance tracking
        self.backtrack_count = 0
        self.nodes_explored = 0
        
    def is_valid_position(self, coords: Tuple[int, int]) -> bool:
        """Check if position is within bounds."""
        x, y = coords
        return 0 <= x < self.width and 0 <= y < self.height
    
    def get_neighbors(self, coords: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get all valid neighboring positions (4-directional)."""
        x, y = coords
        neighbors = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [n for n in neighbors if self.is_valid_position(n)]
    
    def is_connected(self) -> bool:
        """Check if all assigned rooms are connected (BFS)."""
        if not self.assignment:
            return True
        
        start = self.start_pos
        if start not in self.assignment:
            return False
            
        visited = {start}
        queue = deque([start])
        
        while queue:
            current = queue.popleft()
            for neighbor in self.get_neighbors(current):
                if neighbor in self.assignment and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        
        return len(visited) == len(self.assignment)
    
    def select_unassigned_variable(self) -> Optional[Tuple[int, int]]:
        """
        Heuristic: Circular Growth.
        Prioritizes candidate positions closest to the center to prevent long "snake" corridors.
        """
        if not self.assignment:
            return self.start_pos
        
        candidates = set()
        for assigned_pos in self.assignment.keys():
            for neighbor in self.get_neighbors(assigned_pos):
                if neighbor not in self.assignment:
                    candidates.add(neighbor)
        
        if not candidates:
            return None
        
        # Sort by distance to center + small random noise to keep it organic
        sorted_candidates = sorted(
            list(candidates),
            key=lambda c: math.dist(c, self.start_pos) + (random.random() * 1.8)
        )
        
        # Pick from the best candidates
        return random.choice(sorted_candidates[:3])
    
    def order_domain_values(self, coords: Tuple[int, int]) -> List[RoomType]:
        """Order room types based on dungeon progression."""
        assigned_types = [room.room_type for room in self.assignment.values()]
        num_assigned = len(self.assignment)
        
        if num_assigned == 0:
            return [RoomType.START]
        
        # Priority logic for specific stages of generation
        priority = []
        
        # If it's the very last room, force a Boss room if one doesn't exist
        if num_assigned == self.num_rooms - 1:
            if RoomType.BOSS not in assigned_types:
                return [RoomType.BOSS]
        
        # Standard weights
        priority.extend([RoomType.NORMAL] * 6)
        if assigned_types.count(RoomType.TREASURE) < 2:
            priority.append(RoomType.TREASURE)
        if assigned_types.count(RoomType.TRAP) < 2:
            priority.append(RoomType.TRAP)
        if assigned_types.count(RoomType.MERCHANT) < 1:
            priority.append(RoomType.MERCHANT)
        
        # Only allow Boss rooms if we are past the halfway point
        if num_assigned > self.num_rooms // 2 and RoomType.BOSS not in assigned_types:
            priority.append(RoomType.BOSS)
            
        random.shuffle(priority)
        return priority

    def backtrack_step(self) -> Generator[Dict[Tuple[int, int], Room], None, bool]:
        """
        CSP Backtracking as a Generator.
        Yields the current assignment dict at every step for GUI visualization.
        Returns True/False as the generator's final return value.
        """
        self.nodes_explored += 1
        
        # Base case
        if len(self.assignment) == self.num_rooms:
            types = [room.room_type for room in self.assignment.values()]
            if RoomType.START in types and RoomType.BOSS in types:
                return self.is_connected()
            return False
        
        coords = self.select_unassigned_variable()
        if coords is None:
            return False
            
        for room_type in self.order_domain_values(coords):
            # Check consistency (Simplified: must be adjacent to existing or be the first)
            has_connection = any(n in self.assignment for n in self.get_neighbors(coords))
            if not self.assignment or has_connection:
                
                room = Room(
                    coordinates=coords,
                    room_type=room_type,
                    description=self.generate_room_description(room_type)
                )
                self.assignment[coords] = room
                
                # Link doors
                for neighbor in self.get_neighbors(coords):
                    if neighbor in self.assignment:
                        room.connect_to(neighbor)
                        self.assignment[neighbor].connect_to(coords)
                
                # Update GUI
                yield self.assignment
                
                # Recurse using 'yield from' to maintain the generator chain
                result = yield from self.backtrack_step()
                if result:
                    return True
                
                # Backtrack
                self.backtrack_count += 1
                for neighbor in self.get_neighbors(coords):
                    if neighbor in self.assignment:
                        if coords in self.assignment[neighbor].connections:
                            self.assignment[neighbor].connections.remove(coords)
                
                del self.assignment[coords]
                yield self.assignment # Yield the removal for visual feedback
                
        return False

    def generate_room_description(self, room_type: RoomType) -> str:
        descriptions = {
            RoomType.START: ["A dusty entrance with a faint breeze."],
            RoomType.NORMAL: ["A damp stone chamber.", "A corridor filled with echoes."],
            RoomType.TREASURE: ["Glinting piles of gold await."],
            RoomType.BOSS: ["A massive, ominous throne room."],
            RoomType.TRAP: ["The air feels heavy with hidden danger."],
            RoomType.MERCHANT: ["A cozy nook with a small campfire."]
        }
        return random.choice(descriptions.get(room_type, ["An empty room."]))

    def populate_rooms(self):
        """Finalize room contents with diverse enemy groups, merchants, and treasures."""
        for coords, room in self.assignment.items():
            
            # --- 1. Treasure Room Logic ---
            if room.room_type == RoomType.TREASURE:
                room.items.append(Item("Gold Coins", ItemType.GOLD, {"amount": random.randint(50, 150)}))
                if random.random() > 0.5:
                    room.items.append(Item("Health Potion", ItemType.POTION, {"heal": 30}))
            
            # --- 2. Merchant Room Logic (The Fix) ---
            elif room.room_type == RoomType.MERCHANT:
                merchant = NPC(
                    name="Traveling Merchant",
                    npc_type=NPCType.MERCHANT,
                    hp=50,
                    attack=5,
                    defense=10,
                    dialogue=["Greetings! I have supplies if you have the gold.", "A dangerous journey requires the right gear."]
                )
                room.npcs.append(merchant)
                # Merchants also carry a local potion stock
                room.items.append(Item("Shop Potion", ItemType.POTION, {"heal": 25}))

            # --- 3. Boss Room Logic ---
            elif room.room_type == RoomType.BOSS:
                room.npcs.append(NPC("Dragon King", NPCType.BOSS, 120, 22, 12, ["Burn!"]))
            
            # --- 4. Normal Room Logic (Diverse Enemies) ---
            elif room.room_type == RoomType.NORMAL:
                spawn_roll = random.random()
                if spawn_roll > 0.6:  # 40% chance of encounter
                    num_enemies = random.randint(1, 3)
                    for _ in range(num_enemies):
                        room.npcs.append(self._create_random_enemy())

        # --- 5. Key Insurance Logic ---
        # Ensure the Boss Key exists somewhere in the dungeon
        all_rooms = list(self.assignment.values())
        has_key = any(any(i.item_type == ItemType.KEY for i in r.items) for r in all_rooms)
        
        if not has_key:
            treasure_rooms = [r for r in all_rooms if r.room_type == RoomType.TREASURE]
            if treasure_rooms:
                target_room = random.choice(treasure_rooms)
            else:
                # If no treasure rooms spawned, put it in a normal room
                target_room = random.choice([r for r in all_rooms if r.room_type != RoomType.START])
            
            target_room.items.append(Item("Boss Key", ItemType.KEY, {"opens": "boss_room"}))

    def _create_random_enemy(self) -> NPC:
        """Factory for generating diverse enemies."""
        types = [
            # Name, HP, ATK, DEF
            ("Goblin", 25, 8, 2, ["Hehehe!"]),
            ("Kobold", 15, 10, 1, ["Yip yip!"]),
            ("Wolf", 20, 12, 3, ["Grrr..."]),
            ("Goblin Leader", 45, 14, 5, ["To arms!"])
        ]
        
        # Weighted choice: Kobolds and Goblins are common, Leaders are rare
        weights = [40, 30, 20, 10]
        name, hp, atk, df, lines = random.choices(types, weights=weights, k=1)[0]
        
        return NPC(name, NPCType.ENEMY, hp, atk, df, lines)

    def generate(self) -> Optional[Dungeon]:
        """Standard wrapper to run the generator to completion."""
        gen = self.backtrack_step()
        try:
            while True:
                next(gen)
        except StopIteration as e:
            if e.value: # Success
                for room in self.assignment.values():
                    self.dungeon.add_room(room)
                self.populate_rooms()
                return self.dungeon
        return None


if __name__ == "__main__":
    # Test circular generation
    gen = DungeonCSP(10, 10, 12, 12)
    dungeon = gen.generate()
    if dungeon:
        print("Dungeon Generated Successfully!")
        for pos in sorted(dungeon.rooms.keys()):
            print(f"{pos}: {dungeon.rooms[pos].room_type.name}")