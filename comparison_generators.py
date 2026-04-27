"""
Alternative Dungeon Generation Algorithms
For comparison with CSP approach: BFS, DFS, and Greedy
"""

from typing import List, Tuple, Optional, Set
from models import Dungeon, Room, RoomType, Item, ItemType, NPC, NPCType
from collections import deque
import random


class BaseDungeonGenerator:
    """Base class for dungeon generators"""
    
    def __init__(self, width: int, height: int, num_rooms: int, seed: Optional[int] = None):
        self.width = width
        self.height = height
        self.num_rooms = num_rooms
        self.dungeon = Dungeon(width, height)
        
        if seed is not None:
            random.seed(seed)
        
        self.nodes_explored = 0
        self.generation_time = 0
    
    def is_valid_position(self, coords: Tuple[int, int]) -> bool:
        """Check if position is within bounds"""
        x, y = coords
        return 0 <= x < self.width and 0 <= y < self.height
    
    def get_neighbors(self, coords: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get all valid neighboring positions"""
        x, y = coords
        neighbors = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [n for n in neighbors if self.is_valid_position(n)]
    
    def populate_rooms(self):
        """Add items and NPCs (same as CSP)"""
        for coords, room in self.dungeon.rooms.items():
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
                        {"damage": random.randint(5, 15)}
                    ))
        
        # Add KEY to random treasure room
        treasure_rooms = [r for r in self.dungeon.rooms.values() 
                         if r.room_type == RoomType.TREASURE]
        if treasure_rooms:
            key_room = random.choice(treasure_rooms)
            key_room.items.append(Item("Boss Key", ItemType.KEY, {"opens": "boss_room"}))
        
        # Add NPCs
        for room in self.dungeon.rooms.values():
            if room.room_type == RoomType.NORMAL and random.random() > 0.6:
                enemies = ["Goblin", "Skeleton", "Giant Rat"]
                room.npcs.append(NPC(
                    name=random.choice(enemies),
                    npc_type=NPCType.ENEMY,
                    hp=random.randint(20, 40),
                    attack=random.randint(5, 12),
                    defense=random.randint(1, 5),
                    dialogue=["Grr!", "You shall not pass!"]
                ))
            
            elif room.room_type == RoomType.MERCHANT:
                room.npcs.append(NPC(
                    name="Merchant",
                    npc_type=NPCType.MERCHANT,
                    hp=50,
                    attack=0,
                    defense=10,
                    dialogue=["Welcome! Care to see my wares?"],
                    inventory=[
                        Item("Health Potion", ItemType.POTION, {"heal": 50}),
                        Item("Steel Sword", ItemType.WEAPON, {"damage": 20})
                    ]
                ))
            
            elif room.room_type == RoomType.BOSS:
                room.npcs.append(NPC(
                    name="Dragon",
                    npc_type=NPCType.BOSS,
                    hp=100,
                    attack=25,
                    defense=10,
                    dialogue=["You dare challenge me?!"]
                ))


class BFSDungeonGenerator(BaseDungeonGenerator):
    """
    Breadth-First Search dungeon generation
    Expands dungeon layer by layer from starting position
    """
    
    def generate(self) -> Dungeon:
        """Generate dungeon using BFS approach"""
        print(f"Generating dungeon with BFS: {self.width}x{self.height}, {self.num_rooms} rooms")
        
        # Start position
        start_coords = (self.width // 2, self.height // 2)
        start_room = Room(
            coordinates=start_coords,
            room_type=RoomType.START,
            description="The entrance to the dungeon."
        )
        self.dungeon.add_room(start_room)
        
        # BFS queue: (coordinates, distance_from_start)
        queue = deque([(start_coords, 0)])
        visited = {start_coords}
        rooms_created = 1
        max_distance = 0
        farthest_room = start_coords
        
        while queue and rooms_created < self.num_rooms:
            current_coords, distance = queue.popleft()
            self.nodes_explored += 1
            
            # Get unvisited neighbors
            neighbors = self.get_neighbors(current_coords)
            random.shuffle(neighbors)  # Add randomness
            
            for neighbor in neighbors:
                if neighbor not in visited and rooms_created < self.num_rooms:
                    # Create new room
                    room_type = self._select_room_type(rooms_created)
                    new_room = Room(
                        coordinates=neighbor,
                        room_type=room_type,
                        description=f"A {room_type.value} room."
                    )
                    
                    # Connect to current room
                    current_room = self.dungeon.get_room(current_coords)
                    new_room.connect_to(current_coords)
                    current_room.connect_to(neighbor)
                    
                    self.dungeon.add_room(new_room)
                    visited.add(neighbor)
                    queue.append((neighbor, distance + 1))
                    rooms_created += 1
                    
                    # Track farthest room for boss placement
                    if distance + 1 > max_distance:
                        max_distance = distance + 1
                        farthest_room = neighbor
        
        # Ensure boss room is at farthest position
        if farthest_room != start_coords:
            boss_room = self.dungeon.get_room(farthest_room)
            boss_room.room_type = RoomType.BOSS
            boss_room.description = "The boss chamber."
        
        self.populate_rooms()
        
        print(f"✓ BFS Generation complete!")
        print(f"  - Nodes explored: {self.nodes_explored}")
        print(f"  - Rooms created: {len(self.dungeon.rooms)}")
        print(f"  - Max distance: {max_distance}")
        
        return self.dungeon
    
    def _select_room_type(self, room_count: int) -> RoomType:
        """Select room type based on generation progress"""
        if room_count == self.num_rooms - 1:
            return RoomType.BOSS
        
        # Random selection with weights
        types = [RoomType.NORMAL] * 5 + [RoomType.TREASURE] * 2 + [RoomType.TRAP, RoomType.MERCHANT]
        return random.choice(types)


class DFSDungeonGenerator(BaseDungeonGenerator):
    """
    Depth-First Search dungeon generation
    Creates long, winding paths before backtracking
    """
    
    def generate(self) -> Dungeon:
        """Generate dungeon using DFS approach"""
        print(f"Generating dungeon with DFS: {self.width}x{self.height}, {self.num_rooms} rooms")
        
        start_coords = (self.width // 2, self.height // 2)
        start_room = Room(
            coordinates=start_coords,
            room_type=RoomType.START,
            description="The entrance to the dungeon."
        )
        self.dungeon.add_room(start_room)
        
        visited = {start_coords}
        self._dfs_recursive(start_coords, visited, 1)
        
        # Place boss at a random leaf node (dead end)
        leaf_rooms = [coords for coords, room in self.dungeon.rooms.items()
                     if len(room.connections) == 1 and room.room_type != RoomType.START]
        if leaf_rooms:
            boss_coords = random.choice(leaf_rooms)
            self.dungeon.get_room(boss_coords).room_type = RoomType.BOSS
        
        self.populate_rooms()
        
        print(f"✓ DFS Generation complete!")
        print(f"  - Nodes explored: {self.nodes_explored}")
        print(f"  - Rooms created: {len(self.dungeon.rooms)}")
        
        return self.dungeon
    
    def _dfs_recursive(self, coords: Tuple[int, int], visited: Set[Tuple[int, int]], depth: int):
        """Recursive DFS helper"""
        if len(self.dungeon.rooms) >= self.num_rooms:
            return
        
        self.nodes_explored += 1
        neighbors = self.get_neighbors(coords)
        random.shuffle(neighbors)
        
        for neighbor in neighbors:
            if neighbor not in visited and len(self.dungeon.rooms) < self.num_rooms:
                room_type = self._select_room_type(len(self.dungeon.rooms))
                new_room = Room(
                    coordinates=neighbor,
                    room_type=room_type,
                    description=f"A {room_type.value} room."
                )
                
                current_room = self.dungeon.get_room(coords)
                new_room.connect_to(coords)
                current_room.connect_to(neighbor)
                
                self.dungeon.add_room(new_room)
                visited.add(neighbor)
                
                # Recurse deeper
                self._dfs_recursive(neighbor, visited, depth + 1)
    
    def _select_room_type(self, room_count: int) -> RoomType:
        """Select room type"""
        types = [RoomType.NORMAL] * 5 + [RoomType.TREASURE] * 2 + [RoomType.TRAP, RoomType.MERCHANT]
        return random.choice(types)


class GreedyDungeonGenerator(BaseDungeonGenerator):
    """
    Greedy dungeon generation
    Always expands to the position with the best heuristic score
    Heuristic: maximize distance from start + penalize clustering
    """
    
    def generate(self) -> Dungeon:
        """Generate dungeon using greedy approach"""
        print(f"Generating dungeon with Greedy: {self.width}x{self.height}, {self.num_rooms} rooms")
        
        start_coords = (self.width // 2, self.height // 2)
        start_room = Room(
            coordinates=start_coords,
            room_type=RoomType.START,
            description="The entrance to the dungeon."
        )
        self.dungeon.add_room(start_room)
        
        occupied = {start_coords}
        
        for i in range(1, self.num_rooms):
            # Find all possible expansion positions
            candidates = set()
            for coords in occupied:
                for neighbor in self.get_neighbors(coords):
                    if neighbor not in occupied:
                        candidates.add(neighbor)
            
            if not candidates:
                break
            
            # Score each candidate using heuristic
            best_coords = max(candidates, key=lambda c: self._heuristic(c, occupied))
            self.nodes_explored += len(candidates)
            
            # Create room at best position
            room_type = self._select_room_type(i)
            new_room = Room(
                coordinates=best_coords,
                room_type=room_type,
                description=f"A {room_type.value} room."
            )
            
            # Connect to adjacent rooms
            for neighbor in self.get_neighbors(best_coords):
                if neighbor in occupied:
                    new_room.connect_to(neighbor)
                    self.dungeon.get_room(neighbor).connect_to(best_coords)
            
            self.dungeon.add_room(new_room)
            occupied.add(best_coords)
        
        self.populate_rooms()
        
        print(f"✓ Greedy Generation complete!")
        print(f"  - Nodes explored: {self.nodes_explored}")
        print(f"  - Rooms created: {len(self.dungeon.rooms)}")
        
        return self.dungeon
    
    def _heuristic(self, coords: Tuple[int, int], occupied: Set[Tuple[int, int]]) -> float:
        """
        Heuristic score for position
        Higher is better
        """
        x, y = coords
        
        # Distance from center (prefer spreading out)
        center_x, center_y = self.width // 2, self.height // 2
        distance_from_center = abs(x - center_x) + abs(y - center_y)
        
        # Penalize clustering (prefer positions with fewer occupied neighbors)
        occupied_neighbors = sum(1 for n in self.get_neighbors(coords) if n in occupied)
        
        # Combined score
        score = distance_from_center - (occupied_neighbors * 2)
        
        # Add some randomness
        score += random.uniform(-1, 1)
        
        return score
    
    def _select_room_type(self, room_count: int) -> RoomType:
        """Select room type"""
        if room_count == self.num_rooms - 1:
            return RoomType.BOSS
        
        types = [RoomType.NORMAL] * 5 + [RoomType.TREASURE] * 2 + [RoomType.TRAP, RoomType.MERCHANT]
        return random.choice(types)


# Testing and comparison
if __name__ == "__main__":
    import time
    
    print("=" * 60)
    print("DUNGEON GENERATION ALGORITHM COMPARISON")
    print("=" * 60)
    
    params = {
        "width": 6,
        "height": 6,
        "num_rooms": 10,
        "seed": 42
    }
    
    generators = [
        ("BFS", BFSDungeonGenerator),
        ("DFS", DFSDungeonGenerator),
        ("Greedy", GreedyDungeonGenerator),
    ]
    
    results = []
    
    for name, GeneratorClass in generators:
        print(f"\n{'='*60}")
        generator = GeneratorClass(**params)
        
        start_time = time.time()
        dungeon = generator.generate()
        end_time = time.time()
        
        results.append({
            "name": name,
            "nodes_explored": generator.nodes_explored,
            "time": end_time - start_time,
            "rooms": len(dungeon.rooms) if dungeon else 0
        })
    
    # Summary
    print("\n" + "=" * 60)
    print("COMPARISON SUMMARY")
    print("=" * 60)
    print(f"{'Algorithm':<15} {'Nodes Explored':<20} {'Time (s)':<15} {'Rooms'}")
    print("-" * 60)
    for r in results:
        print(f"{r['name']:<15} {r['nodes_explored']:<20} {r['time']:<15.6f} {r['rooms']}")
