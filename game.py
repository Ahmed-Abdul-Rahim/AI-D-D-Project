"""
Game-state controller.

Wires together the four AI components:
  - DungeonCSP                 -> generates the dungeon
  - BayesianCombatSystem       -> resolves attack rolls / damage
  - NPCBehaviorManager         -> picks NPC actions via decision tree
  - DiceRoller / SkillCheck    -> for misc randomness

The GUI calls into the methods on this class — no Tk imports here, so the
game logic stays testable headlessly.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

from bayesian_combat import (
    BayesianCombatSystem,
    BayesianSkillCheck,
    CombatOutcome,
)
from csp_generator import DungeonCSP
from models import (
    Dungeon, Item, ItemType, NPC, NPCType, Player, RoomType,
)
from npc_decision_tree import NPCAction, NPCBehaviorManager


# ---------------------------------------------------------------------------
# Player factory
# ---------------------------------------------------------------------------

def make_player(name: str = "Hero",
                player_class: str = "Warrior") -> Player:
    """
    Roll a starting character. Class affects starting stats.
    Ability scores use a 4d6 drop-lowest convention (3..18, mean ~12.2).
    """
    def roll_stat() -> int:
        rolls = sorted(random.randint(1, 6) for _ in range(4))[1:]
        return sum(rolls)  # 3..18

    # Roll the six classic abilities.
    str_, dex, con, int_, wis, cha = (roll_stat() for _ in range(6))

    # Class bonuses to abilities (D&D-flavoured, light-touch)
    if player_class == "Warrior":
        str_ += 2; con += 1
    elif player_class == "Rogue":
        dex += 3; cha += 1
    elif player_class == "Cleric":
        wis += 3; con += 1
    elif player_class == "Mage":
        int_ += 3; wis += 1

    # Derive HP/ATK/DEF from abilities + class
    base_hp = 80 + (con - 10) * 4
    base_atk = 8 + (str_ - 10) // 2
    base_def = 4 + (dex - 10) // 2

    if player_class == "Warrior":
        base_hp += 20; base_atk += 3
    elif player_class == "Rogue":
        base_atk += 4; base_def += 1
    elif player_class == "Cleric":
        base_hp += 10; base_def += 3
    elif player_class == "Mage":
        base_atk += 5  # arcane bolt

    return Player(
        name=name,
        hp=base_hp, max_hp=base_hp,
        attack=max(1, base_atk),
        defense=max(0, base_def),
        position=(0, 0),
        gold=20,
        inventory=[],
        strength=str_, dexterity=dex, constitution=con,
        intelligence=int_, wisdom=wis, charisma=cha,
    )


# ---------------------------------------------------------------------------
# GameState
# ---------------------------------------------------------------------------

@dataclass
class GameStatus:
    in_combat: bool = False
    combat_enemy: Optional[NPC] = None
    boss_unlocked: bool = False
    game_over: bool = False
    victory: bool = False


class GameState:
    """All mutable game state + actions. The GUI is a thin shell over this."""

    MAX_LOG_LINES = 200

    def __init__(self,
                 grid_size: int = 8,
                 num_rooms: int = 12,
                 player_name: str = "Hero",
                 player_class: str = "Warrior",
                 seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)

        # Generate the dungeon (CSP — guaranteed solvable)
        gen = DungeonCSP(grid_size, grid_size, num_rooms, seed=seed)
        dungeon = gen.generate()
        if dungeon is None:
            raise RuntimeError(
                f"CSP failed to generate a {grid_size}x{grid_size} dungeon "
                f"with {num_rooms} rooms — try smaller num_rooms.")

        self.dungeon: Dungeon = dungeon
        self.player: Player = make_player(player_name, player_class)
        self.player.position = self.dungeon.start_position
        self.dungeon.rooms[self.player.position].visited = True

        self.combat_system = BayesianCombatSystem()
        self.skill_check = BayesianSkillCheck()
        self.npc_brain = NPCBehaviorManager()

        self.event_log: List[str] = []
        self.status = GameStatus()
        self.turn = 0

        self.log(f"{self.player.name} the {player_class} enters the dungeon.")
        self.log(f"HP {self.player.hp}/{self.player.max_hp} · "
                 f"ATK {self.player.attack} · DEF {self.player.defense}")
        self._announce_room_entry()

    # -- helpers -----------------------------------------------------------

    def log(self, msg: str) -> None:
        self.event_log.append(msg)
        if len(self.event_log) > self.MAX_LOG_LINES:
            del self.event_log[: -self.MAX_LOG_LINES]

    def current_room(self):
        return self.dungeon.rooms[self.player.position]

    def has_key(self) -> bool:
        return any(it.item_type == ItemType.KEY for it in self.player.inventory)

    def available_moves(self) -> List[Tuple[int, int]]:
        if self.status.in_combat or self.status.game_over:
            return []
        return sorted(self.current_room().connections)

    def _announce_room_entry(self) -> None:
        room = self.current_room()
        self.log(f"-- Room {room.coordinates} ({room.room_type.value}) --")
        if room.description:
            self.log(room.description)
        if room.items:
            self.log("Items here: " + ", ".join(it.name for it in room.items))
        for npc in room.npcs:
            self.log(f"You see a {npc.name} ({npc.npc_type.value}).")

        # Auto-engage hostile NPCs that are present
        enemy = next((n for n in room.npcs
                      if n.npc_type in (NPCType.ENEMY, NPCType.BOSS)
                      and n.hp > 0), None)
        if enemy is not None:
            self.status.in_combat = True
            self.status.combat_enemy = enemy
            self.log(f"⚔  {enemy.name} attacks! Combat begins.")

    # -- actions: movement -------------------------------------------------

    def move(self, coords: Tuple[int, int]) -> bool:
        if self.status.game_over:
            return False
        if self.status.in_combat:
            self.log("Cannot move while in combat — defeat or flee the enemy first.")
            return False
        if coords not in self.current_room().connections:
            self.log("That direction is blocked.")
            return False

        dest = self.dungeon.rooms[coords]
        if dest.room_type == RoomType.BOSS and not self.status.boss_unlocked:
            if self.has_key():
                self.status.boss_unlocked = True
                self.log("You use the Boss Key — the great door grinds open!")
            else:
                self.log("The boss door is locked. You need the Boss Key.")
                return False

        self.player.position = coords
        self.turn += 1
        dest.visited = True

        # Trap rooms: DEX save to avoid damage
        if dest.room_type == RoomType.TRAP:
            result, roll = self.skill_check.perform_check(
                skill_level=self.player.dexterity, difficulty=13)
            if result.value.endswith("success"):
                self.log(f"⚠  Trap! DEX save (rolled {roll}, "
                         f"DEX {self.player.dexterity}) → "
                         f"{result.value} — you nimbly avoid it.")
            else:
                dmg = random.randint(5, 15)
                if result.value == "critical_failure":
                    dmg = int(dmg * 1.5)
                self.player.hp = max(0, self.player.hp - dmg)
                self.log(f"⚠  Trap! DEX save (rolled {roll}) → "
                         f"{result.value} — you take {dmg} damage.")
            self._check_death()

        self._announce_room_entry()
        return True

    # -- actions: combat ---------------------------------------------------

    def attack(self) -> None:
        if not self.status.in_combat:
            self.log("Nothing to attack.")
            return
        enemy = self.status.combat_enemy
        if enemy is None:
            self.status.in_combat = False
            return

        # Player swings first
        outcome, dmg = self.combat_system.resolve_attack(self.player, enemy)
        if outcome == CombatOutcome.CRITICAL_HIT:
            self.log(f"💥 CRIT! You hit {enemy.name} for {dmg}.")
        elif outcome == CombatOutcome.HIT:
            self.log(f"You hit {enemy.name} for {dmg}.")
        elif outcome == CombatOutcome.CRITICAL_MISS:
            self.log("Critical miss! You stumble.")
        else:
            self.log(f"You miss {enemy.name}.")
        enemy.hp = max(0, enemy.hp - dmg)
        if enemy.hp <= 0:
            self._defeat_enemy(enemy)
            return

        # NPC reacts via decision tree
        npc_action = self.npc_brain.get_npc_action(
            enemy, self.player,
            {"player_attacked": True, "npc_met": True, "turn_count": self.turn},
        )
        self._npc_reacts(enemy, npc_action)

    def flee(self) -> None:
        if not self.status.in_combat:
            return
        # Charisma-style skill check using Bayesian skill check
        result, roll = self.skill_check.perform_check(
            skill_level=self.player.defense + 5, difficulty=12,
        )
        self.log(f"You attempt to flee (rolled {roll} -> {result.value}).")
        if result.value.endswith("success"):
            # bounce back to a connected, non-current room
            options = [c for c in self.current_room().connections
                       if self.dungeon.rooms[c].room_type != RoomType.BOSS]
            if options:
                self.player.position = random.choice(options)
                self.dungeon.rooms[self.player.position].visited = True
                self.status.in_combat = False
                self.status.combat_enemy = None
                self.log("You break away and slip into the next room.")
                self._announce_room_entry()
                return
        self.log("Your escape fails — the enemy gets a free swing!")
        if self.status.combat_enemy is not None:
            self._enemy_attacks(self.status.combat_enemy)

    def _enemy_attacks(self, enemy: NPC) -> None:
        outcome, dmg = self.combat_system.resolve_attack(enemy, self.player)
        if outcome == CombatOutcome.CRITICAL_HIT:
            self.log(f"💥 {enemy.name} crits you for {dmg}!")
        elif outcome == CombatOutcome.HIT:
            self.log(f"{enemy.name} hits you for {dmg}.")
        else:
            self.log(f"{enemy.name} misses.")
        self.player.hp = max(0, self.player.hp - dmg)
        self._check_death()

    def _npc_reacts(self, npc: NPC, action: NPCAction) -> None:
        if action == NPCAction.ATTACK:
            self._enemy_attacks(npc)
        elif action == NPCAction.DEFEND:
            self.log(f"{npc.name} braces defensively.")
            # half damage on next hit — modeled as a buff to defense for one turn
            npc.defense += 5
        elif action == NPCAction.FLEE:
            self.log(f"{npc.name} flees!")
            self.current_room().npcs.remove(npc)
            self.status.in_combat = False
            self.status.combat_enemy = None
        elif action == NPCAction.SURRENDER:
            self.log(f"{npc.name} surrenders.")
            self.current_room().npcs.remove(npc)
            self.status.in_combat = False
            self.status.combat_enemy = None
        else:
            self.log(f"{npc.name} hesitates ({action.value}).")

    def _defeat_enemy(self, enemy: NPC) -> None:
        self.log(f"{enemy.name} falls!")
        gold_drop = random.randint(5, 25) if enemy.npc_type != NPCType.BOSS else 100
        self.player.gold += gold_drop
        self.log(f"You loot {gold_drop} gold.")
        if enemy in self.current_room().npcs:
            self.current_room().npcs.remove(enemy)
        self.status.in_combat = False
        self.status.combat_enemy = None
        if enemy.npc_type == NPCType.BOSS:
            self.status.victory = True
            self.status.game_over = True
            self.log("🏆 You have slain the boss! Victory!")

    # -- actions: items / NPCs --------------------------------------------

    def pick_up(self, item_index: int) -> None:
        room = self.current_room()
        if not (0 <= item_index < len(room.items)):
            return
        item = room.items.pop(item_index)
        self.player.inventory.append(item)
        self.log(f"Picked up {item.name}.")
        if item.item_type == ItemType.GOLD:
            amount = item.properties.get("amount", 0)
            self.player.gold += amount
            self.player.inventory.remove(item)
            self.log(f"  +{amount} gold (total {self.player.gold}).")

    def use_item(self, item_index: int) -> None:
        if not (0 <= item_index < len(self.player.inventory)):
            return
        item = self.player.inventory[item_index]
        if item.item_type == ItemType.POTION:
            heal = item.properties.get("heal", 20)
            healed = min(heal, self.player.max_hp - self.player.hp)
            self.player.hp += healed
            self.log(f"Drank {item.name} (+{healed} HP).")
            self.player.inventory.pop(item_index)
        elif item.item_type == ItemType.WEAPON:
            bonus = item.properties.get("damage", 5)
            self.player.attack += bonus
            self.log(f"Equipped {item.name} (+{bonus} ATK).")
            self.player.inventory.pop(item_index)
        else:
            self.log(f"You can't use {item.name} right now.")

    def talk(self) -> None:
        room = self.current_room()
        non_hostile = [n for n in room.npcs
                       if n.npc_type not in (NPCType.ENEMY, NPCType.BOSS)]
        if not non_hostile:
            self.log("There is no one to talk to.")
            return
        npc = non_hostile[0]
        action = self.npc_brain.get_npc_action(
            npc, self.player,
            {"player_attacked": False, "npc_met": True, "turn_count": self.turn},
        )
        line = self.npc_brain.get_npc_dialogue(npc, action)
        self.log(f"{npc.name}: \"{line}\"  [{action.value}]")
        if action == NPCAction.TRADE and npc.inventory:
            item = npc.inventory[0]
            cost = 30
            if self.player.gold >= cost:
                self.player.gold -= cost
                self.player.inventory.append(item)
                npc.inventory.remove(item)
                self.log(f"  You buy {item.name} for {cost} gold.")
            else:
                self.log(f"  ({npc.name} wants {cost} gold for {item.name}.)")
        elif action == NPCAction.HELP:
            healed = min(20, self.player.max_hp - self.player.hp)
            self.player.hp += healed
            self.log(f"  {npc.name} heals you for {healed} HP.")
        elif action == NPCAction.STEAL and self.player.inventory:
            stolen = self.player.inventory.pop()
            self.log(f"  {npc.name} swipes your {stolen.name} and vanishes!")
            room.npcs.remove(npc)

    # -- actions: skill checks --------------------------------------------

    def can_force_boss_door(self) -> bool:
        """True when adjacent to a locked boss room (STR check option)."""
        if self.status.in_combat or self.status.game_over:
            return False
        if self.status.boss_unlocked or self.has_key():
            return False
        for nb in self.current_room().connections:
            r = self.dungeon.rooms.get(nb)
            if r is not None and r.room_type == RoomType.BOSS:
                return True
        return False

    def insight_check(self) -> None:
        """WIS check. On success, log the NPC's currently-intended action.
        Useful for deciding whether to attack, flee, persuade, or trade."""
        room = self.current_room()
        targets = [n for n in room.npcs if n.hp > 0]
        if not targets:
            self.log("There is no one here to read.")
            return
        npc = targets[0]
        result, roll = self.skill_check.perform_check(
            skill_level=self.player.wisdom, difficulty=12)
        intent = self.npc_brain.get_npc_action(
            npc, self.player,
            {"player_attacked": self.status.in_combat,
             "npc_met": True, "turn_count": self.turn})
        rolldesc = f"WIS {self.player.wisdom}, rolled {roll}"
        if result.value.endswith("success"):
            self.log(f"🔍 Insight ({rolldesc}) → {result.value}: "
                     f"{npc.name} intends to **{intent.value}**.")
        elif result.value == "critical_failure":
            # Mislead the player on a crit fail — flip to a misleading guess.
            misread = {
                NPCAction.ATTACK: NPCAction.TALK,
                NPCAction.FLEE: NPCAction.ATTACK,
                NPCAction.STEAL: NPCAction.HELP,
                NPCAction.HELP: NPCAction.STEAL,
            }.get(intent, NPCAction.IDLE)
            self.log(f"🔍 Insight ({rolldesc}) → critical failure! "
                     f"You misread {npc.name} as planning to "
                     f"**{misread.value}**.")
        else:
            self.log(f"🔍 Insight ({rolldesc}) → {result.value}: "
                     f"you can't get a read on {npc.name}.")

    def persuade(self) -> None:
        """CHA check during combat. Success → enemy leaves peacefully.
        Failure → enemy gets a free hit. DC scales with enemy 'attack'."""
        if not self.status.in_combat or self.status.combat_enemy is None:
            self.log("Nothing to persuade right now.")
            return
        enemy = self.status.combat_enemy
        dc = 12 + max(0, enemy.attack // 5)  # tougher foes harder to talk down
        if enemy.npc_type == NPCType.BOSS:
            dc = 20  # the dragon is not interested in your sweet talk
        result, roll = self.skill_check.perform_check(
            skill_level=self.player.charisma, difficulty=dc)
        rolldesc = f"CHA {self.player.charisma}, rolled {roll}, DC {dc}"
        if result.value.endswith("success"):
            self.log(f"🗣 Persuasion ({rolldesc}) → {result.value}. "
                     f"{enemy.name} stands down.")
            # On crit success enemy even leaves a token of goodwill
            if result.value == "critical_success":
                bonus = random.randint(10, 30)
                self.player.gold += bonus
                self.log(f"  {enemy.name} drops {bonus} gold and walks away.")
            if enemy in self.current_room().npcs:
                self.current_room().npcs.remove(enemy)
            self.status.in_combat = False
            self.status.combat_enemy = None
        else:
            self.log(f"🗣 Persuasion ({rolldesc}) → {result.value}. "
                     f"{enemy.name} is unmoved and strikes!")
            self._enemy_attacks(enemy)

    def force_boss_door(self) -> None:
        """STR check to break the boss door open without a key. High DC,
        and a critical failure costs HP from straining."""
        if not self.can_force_boss_door():
            self.log("There's no boss door to force here.")
            return
        result, roll = self.skill_check.perform_check(
            skill_level=self.player.strength, difficulty=16)
        rolldesc = f"STR {self.player.strength}, rolled {roll}, DC 16"
        if result.value.endswith("success"):
            self.log(f"💪 Force door ({rolldesc}) → {result.value}. "
                     f"The boss door splinters!")
            self.status.boss_unlocked = True
        else:
            dmg = random.randint(3, 8)
            if result.value == "critical_failure":
                dmg *= 2
            self.player.hp = max(0, self.player.hp - dmg)
            self.log(f"💪 Force door ({rolldesc}) → {result.value}. "
                     f"You hurt yourself for {dmg}.")
            self._check_death()

    # -- death check -------------------------------------------------------

    def _check_death(self) -> None:
        if self.player.hp <= 0:
            self.player.hp = 0
            self.status.game_over = True
            self.status.victory = False
            self.status.in_combat = False
            self.log("💀 You have fallen. The dungeon claims another victim.")
