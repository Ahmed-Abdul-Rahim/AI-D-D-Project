# AI Dungeon Master 

**An interactive showcase of AI algorithms powering a playable dungeon-crawler.**

Watch CSP, BFS, DFS, and Greedy search build dungeons step-by-step.  
Explore NPC decision trees, Bayesian combat math, and then play a D&D‑style adventure driven by the very same AI systems.

---

##  Features

- **Dungeon Generation Inspector** – visualises four search algorithms (CSP/backtracking, BFS, DFS, Greedy) constructing a dungeon in real time.
- **NPC Brain Tab** – interactive decision tree explorer; adjust player state and see how the NPC chooses actions.
- **Combat Math Tab** – Bayesian hit‑probability breakdown, roll‑by‑roll trace, and a live calibration scatter plot.
- **Algorithm Comparison Tab** – runs a configurable sweep across algorithms and renders solvability + structural metrics.
- **Play Tab** – full playable dungeon with move, attack, talk, skill checks, and a character creation popup. Warrior, Rogue, Cleric, and Mage classes fully supported; spellcasters use spell attacks.

All AI components (search, Bayesian reasoning, decision trees) are implemented in standalone modules and can be swapped or studied independently.

---

## Prerequisites

- **Python 3.14+** (the project uses modern type hints and `__future__` annotations)
- **Tkinter** – included with standard Python on Windows and macOS.  
  On Linux you may need to install it separately:  
  `sudo apt install python3-tk` (Debian/Ubuntu) or equivalent.
- **Matplotlib** *(optional)* – required for the calibration and comparison charts.  
  If not installed, those tabs degrade gracefully with a text notice.  
  Install with: `pip install matplotlib`

Other dependencies are pure Python (only the standard library and the project’s own modules).

---

##  Quick Start

```bash
git clone https://github.com/yourusername/AI-D-D-Project.git
cd AI-D-D-Project
python gui.py
```
---

## File Structure
```bash
AI-D-D-Project/
├── gui.py                  # Main application
├── game.py                 # Game state & actions
├── bayesian_combat.py      # Combat & skill checks
├── csp_generator.py        # CSP dungeon generator
├── comparison_generators.py# BFS/DFS/Greedy generators
├── npc_decision_tree.py    # NPC decision tree & manager
├── models.py               # Data classes (Player, NPC, Dungeon, etc.)
├── evaluation/             # Quality metrics & evaluation scripts
├── README.md
└── requirements.txt        # (optional, matplotlib only)
```
