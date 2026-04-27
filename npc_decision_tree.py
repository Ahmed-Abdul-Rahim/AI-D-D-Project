"""
Decision Tree for NPC Behavior
NPCs make decisions based on player state and game conditions
"""

from typing import Dict, Any, Callable, Optional
from models import NPC, Player, NPCType
from enum import Enum


class NPCAction(Enum):
    """Possible NPC actions"""
    ATTACK = "attack"
    FLEE = "flee"
    DEFEND = "defend"
    TALK = "talk"
    TRADE = "trade"
    HELP = "help"
    IDLE = "idle"
    STEAL = "steal"
    SURRENDER = "surrender"


class DecisionNode:
    """
    Node in the decision tree
    Can be either a decision (condition) or an action (leaf)
    """
    
    def __init__(self, condition: Optional[Callable] = None, action: Optional[NPCAction] = None):
        """
        Args:
            condition: Function that takes (npc, player, game_state) and returns bool
            action: Action to take (if leaf node)
        """
        self.condition = condition
        self.action = action
        self.true_branch: Optional[DecisionNode] = None
        self.false_branch: Optional[DecisionNode] = None
    
    def is_leaf(self) -> bool:
        """Check if this is a leaf node (action)"""
        return self.action is not None
    
    def evaluate(self, npc: NPC, player: Player, game_state: Dict[str, Any]) -> NPCAction:
        """
        Traverse the tree to get an action
        
        Args:
            npc: The NPC making the decision
            player: The player character
            game_state: Additional game state (turn count, environment, etc.)
        
        Returns:
            NPCAction to take
        """
        # Leaf node - return action
        if self.is_leaf():
            return self.action
        
        # Decision node - evaluate condition and recurse
        if self.condition(npc, player, game_state):
            if self.true_branch:
                return self.true_branch.evaluate(npc, player, game_state)
            return NPCAction.IDLE
        else:
            if self.false_branch:
                return self.false_branch.evaluate(npc, player, game_state)
            return NPCAction.IDLE


class NPCDecisionTree:
    """
    Decision tree builder for different NPC types
    """
    
    @staticmethod
    def build_enemy_tree() -> DecisionNode:
        """
        Decision tree for enemy NPCs
        
        Logic:
        - If NPC health < 20%, flee or surrender
        - Else if player health < 30%, attack aggressively
        - Else if NPC health < 50%, defend
        - Else attack normally
        """
        root = DecisionNode(
            condition=lambda npc, player, state: (npc.hp / (npc.hp + npc.defense * 10)) < 0.2
        )
        
        # Low health branch - flee or surrender
        low_health = DecisionNode(
            condition=lambda npc, player, state: player.hp > 50
        )
        low_health.true_branch = DecisionNode(action=NPCAction.FLEE)  # Player strong, flee
        low_health.false_branch = DecisionNode(action=NPCAction.ATTACK)  # Player weak, keep fighting
        
        root.true_branch = low_health
        
        # Normal health branch
        normal_health = DecisionNode(
            condition=lambda npc, player, state: player.hp < 30
        )
        
        # Player low health - attack aggressively
        normal_health.true_branch = DecisionNode(action=NPCAction.ATTACK)
        
        # Player healthy - check NPC health
        npc_health_check = DecisionNode(
            condition=lambda npc, player, state: (npc.hp / (npc.hp + npc.defense * 10)) < 0.5
        )
        npc_health_check.true_branch = DecisionNode(action=NPCAction.DEFEND)
        npc_health_check.false_branch = DecisionNode(action=NPCAction.ATTACK)
        
        normal_health.false_branch = npc_health_check
        root.false_branch = normal_health
        
        return root
    
    @staticmethod
    def build_merchant_tree() -> DecisionNode:
        """
        Decision tree for merchant NPCs
        
        Logic:
        - If player has gold, offer trade
        - Else if player has items, offer to buy
        - Else talk
        """
        root = DecisionNode(
            condition=lambda npc, player, state: player.gold > 50
        )
        
        root.true_branch = DecisionNode(action=NPCAction.TRADE)
        
        has_items = DecisionNode(
            condition=lambda npc, player, state: len(player.inventory) > 0
        )
        has_items.true_branch = DecisionNode(action=NPCAction.TRADE)
        has_items.false_branch = DecisionNode(action=NPCAction.TALK)
        
        root.false_branch = has_items
        
        return root
    
    @staticmethod
    def build_friendly_tree() -> DecisionNode:
        """
        Decision tree for friendly NPCs
        
        Logic:
        - If player health < 50%, offer help
        - Else if first encounter, talk
        - Else idle/talk
        """
        root = DecisionNode(
            condition=lambda npc, player, state: player.hp < 50
        )
        
        root.true_branch = DecisionNode(action=NPCAction.HELP)
        
        first_encounter = DecisionNode(
            condition=lambda npc, player, state: state.get("npc_met", False) == False
        )
        first_encounter.true_branch = DecisionNode(action=NPCAction.TALK)
        first_encounter.false_branch = DecisionNode(action=NPCAction.IDLE)
        
        root.false_branch = first_encounter
        
        return root
    
    @staticmethod
    def build_neutral_tree() -> DecisionNode:
        """
        Decision tree for neutral NPCs
        
        Logic:
        - If player attacks first, become hostile
        - Else if player has valuable items and NPC is thief-type, consider stealing
        - Else talk or idle
        """
        root = DecisionNode(
            condition=lambda npc, player, state: state.get("player_attacked", False)
        )
        
        root.true_branch = DecisionNode(action=NPCAction.ATTACK)
        
        # Thief behavior check
        is_thief = DecisionNode(
            condition=lambda npc, player, state: (
                "thief" in npc.name.lower() and 
                len(player.inventory) > 0
            )
        )
        is_thief.true_branch = DecisionNode(action=NPCAction.STEAL)
        is_thief.false_branch = DecisionNode(action=NPCAction.TALK)
        
        root.false_branch = is_thief
        
        return root
    
    @staticmethod
    def build_boss_tree() -> DecisionNode:
        """
        Decision tree for boss NPCs
        
        Logic:
        - If boss health < 30%, use special attack
        - Else if player health > 70%, defend and prepare
        - Else attack
        """
        root = DecisionNode(
            condition=lambda npc, player, state: (npc.hp / 100) < 0.3
        )
        
        root.true_branch = DecisionNode(action=NPCAction.ATTACK)  # Desperate attack
        
        player_strong = DecisionNode(
            condition=lambda npc, player, state: player.hp > 70
        )
        player_strong.true_branch = DecisionNode(action=NPCAction.DEFEND)
        player_strong.false_branch = DecisionNode(action=NPCAction.ATTACK)
        
        root.false_branch = player_strong
        
        return root
    
    @staticmethod
    def get_tree_for_npc(npc_type: NPCType) -> DecisionNode:
        """
        Get the appropriate decision tree for an NPC type
        
        Args:
            npc_type: Type of NPC
        
        Returns:
            Root node of decision tree
        """
        if npc_type == NPCType.ENEMY:
            return NPCDecisionTree.build_enemy_tree()
        elif npc_type == NPCType.MERCHANT:
            return NPCDecisionTree.build_merchant_tree()
        elif npc_type == NPCType.FRIENDLY:
            return NPCDecisionTree.build_friendly_tree()
        elif npc_type == NPCType.NEUTRAL:
            return NPCDecisionTree.build_neutral_tree()
        elif npc_type == NPCType.BOSS:
            return NPCDecisionTree.build_boss_tree()
        else:
            # Default to idle
            return DecisionNode(action=NPCAction.IDLE)


class NPCBehaviorManager:
    """
    Manages NPC behavior using decision trees
    """
    
    def __init__(self):
        self.decision_trees: Dict[NPCType, DecisionNode] = {}
        self._initialize_trees()
    
    def _initialize_trees(self):
        """Initialize decision trees for all NPC types"""
        for npc_type in NPCType:
            self.decision_trees[npc_type] = NPCDecisionTree.get_tree_for_npc(npc_type)
    
    def get_npc_action(self, npc: NPC, player: Player, game_state: Dict[str, Any]) -> NPCAction:
        """
        Get the action an NPC should take
        
        Args:
            npc: The NPC
            player: The player
            game_state: Current game state
        
        Returns:
            Action the NPC should take
        """
        tree = self.decision_trees.get(npc.npc_type)
        if tree:
            return tree.evaluate(npc, player, game_state)
        return NPCAction.IDLE
    
    def get_npc_dialogue(self, npc: NPC, action: NPCAction) -> str:
        """
        Get appropriate dialogue based on NPC action
        
        Args:
            npc: The NPC
            action: Action being taken
        
        Returns:
            Dialogue string
        """
        dialogue_map = {
            NPCAction.ATTACK: npc.dialogue[0] if npc.dialogue else "Prepare to fight!",
            NPCAction.FLEE: "I must retreat!",
            NPCAction.DEFEND: "I'll protect myself!",
            NPCAction.TALK: npc.dialogue[0] if npc.dialogue else "Greetings, traveler.",
            NPCAction.TRADE: "Would you like to trade?",
            NPCAction.HELP: "Let me help you.",
            NPCAction.STEAL: "What's this in your pocket?",
            NPCAction.SURRENDER: "I yield!",
            NPCAction.IDLE: "..."
        }
        return dialogue_map.get(action, "...")


# Testing
if __name__ == "__main__":
    from models import Player, NPC, NPCType, Item, ItemType
    
    print("Testing NPC Decision Trees")
    print("=" * 60)
    
    # Create test player
    player = Player(
        name="Hero",
        hp=80,
        max_hp=100,
        attack=15,
        defense=8,
        position=(0, 0),
        gold=100
    )
    
    # Create behavior manager
    behavior_mgr = NPCBehaviorManager()
    
    # Test different NPC types
    test_npcs = [
        NPC("Goblin", NPCType.ENEMY, hp=30, attack=10, defense=3, 
            dialogue=["I'll destroy you!"]),
        NPC("Merchant", NPCType.MERCHANT, hp=50, attack=0, defense=5,
            dialogue=["Welcome to my shop!"]),
        NPC("Village Elder", NPCType.FRIENDLY, hp=40, attack=5, defense=5,
            dialogue=["Hello, young adventurer."]),
        NPC("Mysterious Stranger", NPCType.NEUTRAL, hp=45, attack=12, defense=6,
            dialogue=["..."]),
        NPC("Dragon", NPCType.BOSS, hp=100, attack=25, defense=10,
            dialogue=["Face me, mortal!"])
    ]
    
    game_state = {
        "turn_count": 1,
        "npc_met": False,
        "player_attacked": False
    }
    
    print("\nScenario 1: Normal encounter")
    print("-" * 60)
    for npc in test_npcs:
        action = behavior_mgr.get_npc_action(npc, player, game_state)
        dialogue = behavior_mgr.get_npc_dialogue(npc, action)
        print(f"{npc.name} ({npc.npc_type.value}): {action.value}")
        print(f"  Says: '{dialogue}'")
    
    print("\n\nScenario 2: Player low health")
    print("-" * 60)
    player.hp = 25
    for npc in test_npcs:
        action = behavior_mgr.get_npc_action(npc, player, game_state)
        dialogue = behavior_mgr.get_npc_dialogue(npc, action)
        print(f"{npc.name} ({npc.npc_type.value}): {action.value}")
        print(f"  Says: '{dialogue}'")
    
    print("\n\nScenario 3: Enemy low health")
    print("-" * 60)
    player.hp = 80
    goblin = test_npcs[0]
    goblin.hp = 5
    action = behavior_mgr.get_npc_action(goblin, player, game_state)
    dialogue = behavior_mgr.get_npc_dialogue(goblin, action)
    print(f"{goblin.name}: {action.value}")
    print(f"  Says: '{dialogue}'")
