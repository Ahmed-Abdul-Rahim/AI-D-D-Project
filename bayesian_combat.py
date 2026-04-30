"""
Bayesian Models for Combat and Dice Rolls
Implements probabilistic reasoning for D&D-style randomness
"""

import random
from typing import Dict, Tuple, List
from models import Player, NPC
from enum import Enum


class CombatOutcome(Enum):
    """Possible combat outcomes"""
    CRITICAL_HIT = "critical_hit"
    HIT = "hit"
    MISS = "miss"
    CRITICAL_MISS = "critical_miss"


class SkillCheckResult(Enum):
    """Skill check results"""
    CRITICAL_SUCCESS = "critical_success"
    SUCCESS = "success"
    FAILURE = "failure"
    CRITICAL_FAILURE = "critical_failure"


class DiceRoller:
    """
    Simulates D&D dice rolls
    d20 = 20-sided die, d6 = 6-sided die, etc.
    """
    
    @staticmethod
    def roll(sides: int, num_dice: int = 1) -> List[int]:
        """
        Roll dice
        
        Args:
            sides: Number of sides on each die
            num_dice: Number of dice to roll
        
        Returns:
            List of individual rolls
        """
        return [random.randint(1, sides) for _ in range(num_dice)]
    
    @staticmethod
    def d20() -> int:
        """Roll a 20-sided die (standard D&D roll)"""
        return random.randint(1, 20)
    
    @staticmethod
    def d6(num_dice: int = 1) -> int:
        """Roll d6 dice (standard damage)"""
        return sum(DiceRoller.roll(6, num_dice))
    
    @staticmethod
    def d8(num_dice: int = 1) -> int:
        """Roll d8 dice"""
        return sum(DiceRoller.roll(8, num_dice))
    
    @staticmethod
    def d12(num_dice: int = 1) -> int:
        """Roll d12 dice"""
        return sum(DiceRoller.roll(12, num_dice))


class BayesianCombatSystem:
    """
    Combat system using Bayesian reasoning
    
    Uses prior probabilities and updates based on:
    - Attacker's skill (attack stat)
    - Defender's skill (defense stat)
    - Environmental factors
    - Equipment bonuses
    """
    
    def __init__(self):
        self.dice = DiceRoller()
        
        # Prior probabilities (base chances before any modifiers)
        self.BASE_HIT_CHANCE = 0.55  # 55% base hit chance
        self.CRITICAL_HIT_CHANCE = 0.05  # 5% critical hit (natural 20)
        self.CRITICAL_MISS_CHANCE = 0.05  # 5% critical miss (natural 1)
    
    def calculate_hit_probability(
        self,
        attacker_attack: int,
        defender_defense: int,
        modifiers: Dict[str, float] = None
    ) -> float:
        """
        Calculate probability of hit using Bayesian updating
        
        P(Hit | Evidence) ∝ P(Evidence | Hit) * P(Hit)
        
        Args:
            attacker_attack: Attacker's attack stat
            defender_defense: Defender's defense stat
            modifiers: Additional modifiers (terrain, equipment, etc.)
        
        Returns:
            Probability of successful hit (0.0 to 1.0)
        """
        if modifiers is None:
            modifiers = {}
        
        # Start with base probability
        hit_prob = self.BASE_HIT_CHANCE
        
        # Update based on attack vs defense difference
        stat_diff = attacker_attack - defender_defense
        stat_modifier = stat_diff * 0.03  # 3% per point difference
        hit_prob += stat_modifier
        
        # Apply environmental modifiers
        for modifier_name, modifier_value in modifiers.items():
            hit_prob += modifier_value
        
        # Clamp between 0.05 and 0.95 (always 5% chance to hit/miss)
        return max(0.05, min(0.95, hit_prob))
    
    def resolve_attack(
        self,
        attacker: Player | NPC,
        defender: Player | NPC,
        modifiers: Dict[str, float] = None
    ) -> Tuple[CombatOutcome, int]:
        """
        Resolve a single attack
        
        Returns:
            (outcome, damage_dealt)
        """
        # Roll d20 for attack
        attack_roll = self.dice.d20()
        
        # Check for critical hit/miss
        if attack_roll == 20:
            # Critical hit - double damage
            base_damage = attacker.attack
            damage = base_damage * 2 + self.dice.d6()
            return CombatOutcome.CRITICAL_HIT, damage
        
        if attack_roll == 1:
            # Critical miss - no damage
            return CombatOutcome.CRITICAL_MISS, 0
        
        # Calculate hit probability
        hit_prob = self.calculate_hit_probability(
            attacker.attack,
            defender.defense,
            modifiers
        )
        
        # Normalize roll to 0-1 probability (excluding criticals)
        # Rolls 2-19 map to probabilities
        roll_prob = (attack_roll - 1) / 19.0
        
        # Hit if roll_prob exceeds threshold based on hit_prob
        if roll_prob <= hit_prob:
            # Calculate damage
            damage = max(1, attacker.attack - defender.defense // 2 + self.dice.d6())
            return CombatOutcome.HIT, damage
        else:
            return CombatOutcome.MISS, 0
    
    def resolve_spell_attack(self, caster, defender, spell_stat):
        """
        Resolve a spell attack using the caster's spellcasting ability (WIS or INT).
        Damage formula is comparable to a physical attack, substituting spell_stat
        for the usual attack stat and rolling a d8 instead of a d6.
        """
        roll = self.dice.d20()

        # Natural 20 – critical hit
        if roll == 20:
            base_damage = spell_stat
            damage = base_damage * 2 + self.dice.d8()
            return CombatOutcome.CRITICAL_HIT, damage

        # Natural 1 – critical miss
        if roll == 1:
            return CombatOutcome.CRITICAL_MISS, 0

        # Hit probability – uses spell_stat vs defender defense (same logic as physical)
        stat_diff = spell_stat - defender.defense
        stat_mod = stat_diff * 0.03
        hit_prob = max(0.05, min(0.95, self.BASE_HIT_CHANCE + stat_mod))

        roll_prob = (roll - 1) / 19.0
        if roll_prob <= hit_prob:
            # Damage: spell_stat - half target's defense + 1d8 (similar to melee: attack - def/2 + d6)
            damage = max(1, spell_stat - defender.defense // 2 + self.dice.d8())
            return CombatOutcome.HIT, damage
        else:
            return CombatOutcome.MISS, 0

    def simulate_combat_round(
        self,
        player: Player,
        enemy: NPC,
        player_modifiers: Dict[str, float] = None,
        enemy_modifiers: Dict[str, float] = None
    ) -> Dict[str, any]:
        """
        Simulate a full combat round (both sides attack)
        
        Returns:
            Dictionary with combat results
        """
        results = {
            "player_attack": None,
            "player_damage": 0,
            "enemy_attack": None,
            "enemy_damage": 0,
            "player_hp_remaining": player.hp,
            "enemy_hp_remaining": enemy.hp
        }
        
        # Player attacks
        player_outcome, player_damage = self.resolve_attack(
            player, enemy, player_modifiers
        )
        results["player_attack"] = player_outcome
        results["player_damage"] = player_damage
        enemy.hp = max(0, enemy.hp - player_damage)
        results["enemy_hp_remaining"] = enemy.hp
        
        # Enemy attacks (if still alive)
        if enemy.hp > 0:
            enemy_outcome, enemy_damage = self.resolve_attack(
                enemy, player, enemy_modifiers
            )
            results["enemy_attack"] = enemy_outcome
            results["enemy_damage"] = enemy_damage
            player.hp = max(0, player.hp - enemy_damage)
            results["player_hp_remaining"] = player.hp
        
        return results


class BayesianSkillCheck:
    """
    Bayesian model for skill checks (non-combat actions)
    Examples: lockpicking, persuasion, stealth, etc.
    """
    
    def __init__(self):
        self.dice = DiceRoller()
    
    def calculate_success_probability(
        self,
        skill_level: int,
        difficulty: int,
        modifiers: Dict[str, float] = None
    ) -> float:
        """
        Calculate probability of skill check success
        
        Args:
            skill_level: Character's skill level (0-20)
            difficulty: Task difficulty (0-20)
            modifiers: Additional modifiers
        
        Returns:
            Success probability
        """
        if modifiers is None:
            modifiers = {}
        
        # Base probability based on skill vs difficulty
        base_prob = 0.5 + (skill_level - difficulty) * 0.05
        
        # Apply modifiers
        for modifier_value in modifiers.values():
            base_prob += modifier_value
        
        return max(0.05, min(0.95, base_prob))
    
    def perform_check(
        self,
        skill_level: int,
        difficulty: int,
        modifiers: Dict[str, float] = None
    ) -> Tuple[SkillCheckResult, int]:
        """
        Perform a skill check
        
        Returns:
            (result, roll_value)
        """
        roll = self.dice.d20()
        
        # Critical success/failure
        if roll == 20:
            return SkillCheckResult.CRITICAL_SUCCESS, roll
        if roll == 1:
            return SkillCheckResult.CRITICAL_FAILURE, roll
        
        # Calculate success probability
        success_prob = self.calculate_success_probability(
            skill_level, difficulty, modifiers
        )
        
        # Check if successful
        roll_prob = (roll - 1) / 19.0
        
        if roll_prob <= success_prob:
            return SkillCheckResult.SUCCESS, roll
        else:
            return SkillCheckResult.FAILURE, roll


# Testing
if __name__ == "__main__":
    from models import Player, NPC, NPCType
    
    print("Testing Bayesian Combat System")
    print("=" * 60)
    
    # Create combatants
    player = Player(
        name="Hero",
        hp=100,
        max_hp=100,
        attack=15,
        defense=10,
        position=(0, 0)
    )
    
    goblin = NPC(
        name="Goblin",
        npc_type=NPCType.ENEMY,
        hp=40,
        attack=10,
        defense=5,
        dialogue=["Die!"]
    )
    
    combat_system = BayesianCombatSystem()
    
    print(f"\n{player.name} (HP: {player.hp}, ATK: {player.attack}, DEF: {player.defense})")
    print(f"vs")
    print(f"{goblin.name} (HP: {goblin.hp}, ATK: {goblin.attack}, DEF: {goblin.defense})")
    print()
    
    # Calculate hit probabilities
    player_hit_prob = combat_system.calculate_hit_probability(
        player.attack, goblin.defense
    )
    goblin_hit_prob = combat_system.calculate_hit_probability(
        goblin.attack, player.defense
    )
    
    print(f"Player hit probability: {player_hit_prob:.2%}")
    print(f"Goblin hit probability: {goblin_hit_prob:.2%}")
    print()
    
    # Simulate combat rounds
    round_num = 1
    while player.hp > 0 and goblin.hp > 0:
        print(f"--- Round {round_num} ---")
        
        results = combat_system.simulate_combat_round(player, goblin)
        
        print(f"{player.name} attacks: {results['player_attack'].value}")
        if results['player_damage'] > 0:
            print(f"  Deals {results['player_damage']} damage!")
        
        if goblin.hp > 0:
            print(f"{goblin.name} attacks: {results['enemy_attack'].value}")
            if results['enemy_damage'] > 0:
                print(f"  Deals {results['enemy_damage']} damage!")
        
        print(f"{player.name} HP: {results['player_hp_remaining']}")
        print(f"{goblin.name} HP: {results['enemy_hp_remaining']}")
        print()
        
        round_num += 1
        
        if round_num > 20:  # Safety limit
            break
    
    # Combat conclusion
    if player.hp > 0:
        print(f"🎉 {player.name} wins!")
    else:
        print(f"💀 {player.name} has been defeated!")
    
    # Test skill checks
    print("\n" + "=" * 60)
    print("Testing Skill Checks")
    print("=" * 60)
    
    skill_checker = BayesianSkillCheck()
    
    tests = [
        ("Easy lockpick", 15, 8),
        ("Moderate persuasion", 12, 12),
        ("Hard stealth", 10, 16),
        ("Very hard perception", 8, 18)
    ]
    
    for test_name, skill, difficulty in tests:
        result, roll = skill_checker.perform_check(skill, difficulty)
        prob = skill_checker.calculate_success_probability(skill, difficulty)
        print(f"\n{test_name} (Skill: {skill}, Difficulty: {difficulty})")
        print(f"  Success probability: {prob:.2%}")
        print(f"  Rolled: {roll}")
        print(f"  Result: {result.value}")
