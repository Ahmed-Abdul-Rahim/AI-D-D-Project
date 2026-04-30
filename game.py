"""
Game-state controller.
Wires together the AI components: DungeonCSP, Bayesian Combat, and NPC Decision Trees.
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from bayesian_combat import BayesianCombatSystem, BayesianSkillCheck, CombatOutcome
from csp_generator import DungeonCSP
from models import Dungeon, Item, ItemType, NPC, NPCType, Player, RoomType
from npc_decision_tree import NPCAction, NPCBehaviorManager

# ---------------------------------------------------------------------------
# Player Factory
# ---------------------------------------------------------------------------

def make_player(name: str = "Hero", player_class: str = "Warrior") -> Player:
    def roll_stat() -> int:
        rolls = sorted(random.randint(1, 6) for _ in range(4))[1:]
        return sum(rolls)

    str_, dex, con, int_, wis, cha = (roll_stat() for _ in range(6))

    if player_class == "Warrior": 
        str_ += 2
        con += 1
    elif player_class == "Rogue": 
        dex += 3
        cha += 1
    elif player_class == "Cleric": 
        wis += 3
        con += 1
    elif player_class == "Mage": 
        int_ += 3
        wis += 1

    base_hp = 80 + (con - 10) * 4
    base_atk = 8 + (str_ - 10) // 2
    base_def = 4 + (dex - 10) // 2

    if player_class == "Warrior": 
        base_hp += 20
        base_atk += 3
    elif player_class == "Rogue": 
        base_atk += 4
        base_def += 1
    elif player_class == "Cleric": 
        base_hp += 10
        base_def += 3
    elif player_class == "Mage": 
        base_atk += 5

    return Player(
        name=name, hp=base_hp, max_hp=base_hp,
        attack=max(1, base_atk), defense=max(0, base_def),
        position=(0, 0), gold=20, inventory=[],
        strength=str_, dexterity=dex, constitution=con,
        intelligence=int_, wisdom=wis, charisma=cha,
    )

# ---------------------------------------------------------------------------
# Game State Structures
# ---------------------------------------------------------------------------

@dataclass
class GameStatus:
    in_combat: bool = False
    combat_enemies: List[NPC] = field(default_factory=list) 
    target_idx: int = 0 
    boss_unlocked: bool = False
    game_over: bool = False
    victory: bool = False

class GameState:
    MAX_LOG_LINES = 200

    def __init__(self, grid_size: int = 8, num_rooms: int = 12, 
                 player_name: str = "Hero", player_class: str = "Warrior", 
                 seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)

        self.grid_params = (grid_size, num_rooms)
        self.csp_solver = DungeonCSP(grid_size, grid_size, min_rooms=10, max_rooms=num_rooms, seed=seed)
        self.gen_iterator = None 
        
        # Initial generation
        self.dungeon = self.csp_solver.generate()
        if self.dungeon is None:
            raise RuntimeError("CSP failed initial generation.")

        self.player = make_player(player_name, player_class)
        self.player.position = self.dungeon.start_position
        self.dungeon.rooms[self.player.position].visited = True

        self.combat_system = BayesianCombatSystem()
        self.skill_check = BayesianSkillCheck()
        self.npc_brain = NPCBehaviorManager()

        self.event_log: List[str] = []
        self.status = GameStatus()
        self.turn = 0

        self.log(f"{self.player.name} the {player_class} enters the dungeon.")
        self._announce_room_entry()

    def log(self, msg: str) -> None:
        self.event_log.append(msg)
        if len(self.event_log) > self.MAX_LOG_LINES:
            del self.event_log[:-self.MAX_LOG_LINES]

    def current_room(self):
        return self.dungeon.rooms[self.player.position]

    # -- Step Generation Logic --

    def start_step_gen(self):
        self.dungeon.rooms = {} 
        self.gen_iterator = self.csp_solver.backtrack_step()
        self.status.game_over = True 
        self.log("--- Starting Step-by-Step CSP Generation ---")

    def step_gen(self) -> bool:
        if self.gen_iterator is None:
            self.start_step_gen()
        try:
            current_assignment = next(self.gen_iterator)
            self.dungeon.rooms = current_assignment.copy()
            return True
        except StopIteration as e:
            if e.value:
                self.csp_solver.populate_rooms()
                self.dungeon.rooms = self.csp_solver.assignment
                self.log("CSP: Valid dungeon found.")
            else:
                self.log("CSP: Failed to find valid layout.")
            self.gen_iterator = None
            self.status.game_over = False
            return False

    # -- Standard Actions --

    def move(self, coords: Tuple[int, int]) -> bool:
        if self.status.game_over or self.status.in_combat: 
            return False
        if coords not in self.current_room().connections: 
            return False

        dest = self.dungeon.rooms[coords]
        if dest.room_type == RoomType.BOSS and not self.status.boss_unlocked:
            if any(i.item_type == ItemType.KEY for i in self.player.inventory):
                self.status.boss_unlocked = True
                self.log("The Boss Key unlocks the heavy door!")
            else:
                self.log("The door is locked.")
                return False

        self.player.position = coords
        self.turn += 1
        dest.visited = True
        self._announce_room_entry()
        return True

    def _announce_room_entry(self) -> None:
        room = self.current_room()
        self.log(f"Entered {room.room_type.value} at {room.coordinates}")
        
        # Collect ALL hostile NPCs in the room
        hostiles = [n for n in room.npcs if n.npc_type in (NPCType.ENEMY, NPCType.BOSS) and n.hp > 0]
        
        if hostiles:
            self.status.in_combat = True
            self.status.combat_enemies = hostiles
            self.status.target_idx = 0
            names = ", ".join([n.name for n in hostiles])
            self.log(f" Foes appear: {names}!")

    def attack(self, target_idx: Optional[int] = None) -> None:
        if not self.status.in_combat or not self.status.combat_enemies:
            return
        
        if target_idx is not None:
            self.status.target_idx = target_idx
        
        # Ensure target is valid
        idx = min(self.status.target_idx, len(self.status.combat_enemies) - 1)
        enemy = self.status.combat_enemies[idx]

        # 1. Player Attacks
        outcome, dmg = self.combat_system.resolve_attack(self.player, enemy)
        enemy.hp = max(0, enemy.hp - dmg)
        self.log(f"You hit {enemy.name} for {dmg} damage ({outcome.value}).")
        
        # 2. Check for Enemy Death
        if enemy.hp <= 0:
            self.log(f"✨ {enemy.name} defeated!")
            if enemy in self.current_room().npcs:
                self.current_room().npcs.remove(enemy)
            self.status.combat_enemies.remove(enemy)
            self.status.target_idx = 0 # Reset target
            
            if enemy.npc_type == NPCType.BOSS:
                self.status.victory = True
                self.status.game_over = True
                self.status.in_combat = False
                return

        # 3. If enemies remain, they ALL get a turn
        if not self.status.combat_enemies:
            self.status.in_combat = False
            self.log("Combat cleared!")
        else:
            self._resolve_npc_turns()

    def _resolve_npc_turns(self) -> None:
        """All active enemies in the room attack the player."""
        for enemy in list(self.status.combat_enemies):
            if enemy.hp <= 0: 
                continue
            
            action = self.npc_brain.get_npc_action(enemy, self.player, {"turn": self.turn})
            if action == NPCAction.ATTACK:
                outcome, dmg = self.combat_system.resolve_attack(enemy, self.player)
                self.player.hp = max(0, self.player.hp - dmg)
                self.log(f" {enemy.name} strikes you for {dmg} damage!")
        
        if self.player.hp <= 0:
            self.log(" You have been slain...")
            self.status.game_over = True

    def flee(self) -> None:
        if not self.status.in_combat: 
            return
        
        # Use Dexterity vs Difficulty 12
        success, _ = self.skill_check.perform_check(self.player.dexterity, 12)
        
        if "success" in success.value.lower():
            self.status.in_combat = False
            self.status.combat_enemies = []
            self.log(" You successfully escaped combat!")
        else:
            self.log(" Escape failed! The enemies surround you!")
            self._resolve_npc_turns()

    def talk(self) -> None:
        if self.status.in_combat:
            self.log("You can't talk right now, you are in combat!")
            return
        
        room = self.current_room()
        # Filter for living NPCs
        living_npcs = [n for n in room.npcs if n.hp > 0]
        
        if not living_npcs:
            self.log("There is no one here to talk to.")
            return

        for npc in living_npcs:
            # Ask the decision tree what this NPC wants to do
            game_state_context = {
                "turn_count": self.turn,
                "npc_met": getattr(npc, "met", False), 
                "player_attacked": False
            }
            
            action = self.npc_brain.get_npc_action(npc, self.player, game_state_context)
            dialogue = self.npc_brain.get_npc_dialogue(npc, action)
            
            self.log(f"{npc.name}: '{dialogue}'")
            
            # Handle the specific outcome of the interaction
            if action == NPCAction.TRADE:
                if self.player.gold >= 10:
                    self.player.gold -= 10
                    heal_amount = 25
                    self.player.hp = min(self.player.max_hp, self.player.hp + heal_amount)
                    self.log(f"Traded 10 gold for a healing draught! Recovered {heal_amount} HP.")
                else:
                    self.log(f"{npc.name} points to a sign: 'Healing Draughts: 10 Gold'. You can't afford it.")
                    
            elif action == NPCAction.HELP:
                heal_amount = 15
                self.player.hp = min(self.player.max_hp, self.player.hp + heal_amount)
                self.log(f"{npc.name} tends to your wounds. Recovered {heal_amount} HP.")
            
            # Mark the NPC as met so the decision tree can alter future dialogue
            npc.met = True

    def pick_up(self, idx: int) -> None:
        room_items = self.current_room().items
        if 0 <= idx < len(room_items):
            item = room_items.pop(idx)
            self.player.inventory.append(item)
            self.log(f"Picked up {item.name}.") # The GUI will call refresh() after this, 
                                                 # and because the item was popped, the button will disappear.

    def use_item(self, idx: int) -> None:
        if 0 <= idx < len(self.player.inventory):
            item = self.player.inventory.pop(idx)
            if item.item_type == ItemType.POTION:
                self.player.hp = min(self.player.max_hp, self.player.hp + 25)
                self.log(f"Used {item.name}. Feeling better!")
            elif item.item_type == ItemType.KEY:
                # Key logic is usually handled in move(), but we'll put it back in the list
                self.player.inventory.insert(idx, item)
                self.log("You should save this key for the Boss door.")