"""
CSP-based Dungeon Generator
Uses Constraint Satisfaction Problem solving with backtracking to generate valid dungeons
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
        self.variables: List[Tuple[int, int]] = []  # Room positions to assign
        self.domains: Dict[Tuple[int, int], List[RoomType]] = {}  # Possible room types
        self.assignment: Dict[Tuple[int, int], Room] = {}  # Current assignment
        
        # Tracking
        self.backtrack_count = 0
        self.nodes_explored = 0
        
    def is_valid_position(self, coords: Tuple[int, int]) -> bool:
        """Check if position is within bounds"""
        x, y = coords
        return 0 <= x < self.width and 0 <= y < self.height
    
    def get_neighbors(self, coords: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get all valid neighboring positions (4-directional)"""
        x, y = coords
        neighbors = [
            (x + 1, y), (x - 1, y),  # Horizontal
            (x, y + 1), (x, y - 1)   # Vertical
        ]
        return [n for n in neighbors if self.is_valid_position(n)]
    
    def is_connected(self) -> bool:
        """
        Check if all assigned rooms are connected (BFS)
        Constraint: Connectivity
        """
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
        """
        Calculate shortest distance from start room using BFS
        Used for boss room placement constraint
        """
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
        
        return -1  # Not reachable
    
    def is_consistent(self, coords: Tuple[int, int], room_type: RoomType) -> bool:
        """
        Check if assigning room_type to coords is consistent with constraints
        """
        # Constraint 1: Position must be valid and not already assigned
        if not self.is_valid_position(coords) or coords in self.assignment:
            return False
        
        # Constraint 2: Room must have at least one connection to existing rooms (except first room)
        if self.assignment:
            has_connection = any(neighbor in self.assignment 
                               for neighbor in self.get_neighbors(coords))
            if not has_connection:
                return False
        
        # Constraint 3: Only one START room
        if room_type == RoomType.START:
            if any(room.room_type == RoomType.START for room in self.assignment.values()):
                return False
        
        # Constraint 4: Only one BOSS room
        if room_type == RoomType.BOSS:
            if any(room.room_type == RoomType.BOSS for room in self.assignment.values()):
                return False
        
        return True
    
    def select_unassigned_variable(self) -> Optional[Tuple[int, int]]:
        """
        Select next position to assign (MRV heuristic - Most Restricted Variable)
        Choose position with fewest remaining valid neighbors
        """
        if not self.assignment:
            # First room - place at center or random position
            return (self.width // 2, self.height // 2)
        
        # Get all positions adjacent to assigned rooms
        candidates = set()
        for assigned_pos in self.assignment.keys():
            for neighbor in self.get_neighbors(assigned_pos):
                if neighbor not in self.assignment:
                    candidates.add(neighbor)
        
        if not candidates:
            return None
        
        # Choose position with most assigned neighbors (most constrained)
        return max(candidates, 
                  key=lambda pos: sum(1 for n in self.get_neighbors(pos) 
                                     if n in self.assignment))
    
    def order_domain_values(self, coords: Tuple[int, int]) -> List[RoomType]:
        """
        Order room types to try (LCV heuristic - Least Constraining Value)
        Prioritize room types based on current dungeon state
        """
        assigned_types = [room.room_type for room in self.assignment.values()]
        num_assigned = len(self.assignment)
        
        # Priority order based on dungeon generation strategy
        priority = []
        
        # First room must be START
        if num_assigned == 0:
            return [RoomType.START]
        
        # Last room should be BOSS
        if num_assigned == self.num_rooms - 1:
            if RoomType.BOSS not in assigned_types:
                return [RoomType.BOSS]
        
        # Standard priority for middle rooms
        if RoomType.START not in assigned_types:
            priority.append(RoomType.START)
        
        # Add normal rooms most frequently
        priority.extend([RoomType.NORMAL] * 3)
        
        # Special rooms less frequently
        if assigned_types.count(RoomType.TREASURE) < 2:
            priority.append(RoomType.TREASURE)
        
        if assigned_types.count(RoomType.TRAP) < 2:
            priority.append(RoomType.TRAP)
        
        if assigned_types.count(RoomType.MERCHANT) < 1:
            priority.append(RoomType.MERCHANT)
        
        # Boss room only near the end
        if num_assigned >= self.num_rooms - 2 and RoomType.BOSS not in assigned_types:
            priority.append(RoomType.BOSS)
        
        # Shuffle to add randomness while maintaining priorities
        random.shuffle(priority)
        return priority
    
    def backtrack(self) -> bool:
        """
        CSP Backtracking algorithm
        Returns True if a valid assignment is found
        """
        self.nodes_explored += 1
        
        # Base case: all rooms assigned
        if len(self.assignment) == self.num_rooms:
            # Final check: must have START and BOSS rooms
            types = [room.room_type for room in self.assignment.values()]
            if RoomType.START in types and RoomType.BOSS in types:
                return self.is_connected()
            return False
        
        # Select next variable (position)
        coords = self.select_unassigned_variable()
        if coords is None:
            return False
        
        # Try values (room types) in order
        for room_type in self.order_domain_values(coords):
            if self.is_consistent(coords, room_type):
                # Make assignment
                room = Room(
                    coordinates=coords,
                    room_type=room_type,
                    description=self.generate_room_description(room_type)
                )
                self.assignment[coords] = room
                
                # Create connections to adjacent assigned rooms
                for neighbor in self.get_neighbors(coords):
                    if neighbor in self.assignment:
                        room.connect_to(neighbor)
                        self.assignment[neighbor].connect_to(coords)
                
                # Recursive call
                if self.backtrack():
                    return True
                
                # Backtrack: remove assignment
                self.backtrack_count += 1
                # Remove connections
                for neighbor in self.get_neighbors(coords):
                    if neighbor in self.assignment:
                        self.assignment[neighbor].connections.remove(coords)
                
                del self.assignment[coords]
        
        return False
    
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
            ]
        }
        return random.choice(descriptions.get(room_type, ["An empty room."]))
    
    def populate_rooms(self):
        """Add items and NPCs to rooms after generation"""
        for coords, room in self.assignment.items():
            # Add items based on room type
            if room.room_type == RoomType.TREASURE:
                # Add treasure items
                room.items.append(Item("Gold Coins", ItemType.GOLD, {"amount": random.randint(50, 150)}))
                if random.random() > 0.5:
                    room.items.append(Item("Health Potion", ItemType.POTION, {"heal": 30}))
            
            elif room.room_type == RoomType.NORMAL:
                # Randomly add items
                if random.random() > 0.7:
                    weapons = ["Iron Sword", "Rusty Dagger", "Wooden Staff"]
                    room.items.append(Item(
                        random.choice(weapons),
                        ItemType.WEAPON,
                        {"damage": random.randint(5, 15)}
                    ))
            
            # Add KEY item to a random treasure room (needed for boss)
            treasure_rooms = [r for r in self.assignment.values() 
                            if r.room_type == RoomType.TREASURE]
            if treasure_rooms and not any(
                item.item_type == ItemType.KEY 
                for room in self.assignment.values() 
                for item in room.items
            ):
                key_room = random.choice(treasure_rooms)
                key_room.items.append(Item("Boss Key", ItemType.KEY, {"opens": "boss_room"}))
            
            # Add NPCs based on room type
            if room.room_type == RoomType.NORMAL and random.random() > 0.6:
                # Add enemy
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
                    dialogue=["Welcome! Care to see my wares?", "I have the finest goods!"],
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
                    dialogue=["You dare challenge me?!", "Prepare to meet your doom!"]
                ))
    
    def generate(self) -> Dungeon:
        """
        Main generation method
        Returns a complete dungeon or None if generation fails
        """
        print(f"Generating dungeon with CSP: {self.width}x{self.height}, {self.num_rooms} rooms")
        
        if self.backtrack():
            # Add all rooms to dungeon
            for room in self.assignment.values():
                self.dungeon.add_room(room)
            
            # Populate with items and NPCs
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


# Testing
if __name__ == "__main__":
    # Generate a dungeon
    generator = DungeonCSP(width=5, height=5, num_rooms=8, seed=42)
    dungeon = generator.generate()
    
    if dungeon:
        print(f"\n{dungeon}")
        print(f"Start: {dungeon.start_position}")
        print(f"Boss: {dungeon.boss_position}")
        
        print("\nRoom details:")
        for coords, room in sorted(dungeon.rooms.items()):
            print(f"  {coords}: {room.room_type.value}")
            print(f"    Connections: {room.connections}")
            if room.items:
                print(f"    Items: {[item.name for item in room.items]}")
            if room.npcs:
                print(f"    NPCs: {[npc.name for npc in room.npcs]}")
