"""
Master evaluation runner.

Runs all three evaluation modules in sequence and writes results to results/.

Usage:
    python3 run_evaluation.py            # full sweep
    python3 run_evaluation.py --quick    # smaller sweep for fast feedback
"""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from evaluation import combat_eval, dungeon_eval, npc_eval


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="Run a smaller sweep (faster, useful for iteration).")
    args = ap.parse_args()

    if args.quick:
        dungeon_eval.NUM_SEEDS = 10
        dungeon_eval.CONFIGS = [(5, 6), (8, 12), (10, 25)]
        combat_eval.N_TRIALS_CALIBRATION = 1000

    started = time.time()

    print("=" * 60)
    print("STAGE 1/3: dungeon generation comparison")
    print("=" * 60)
    dungeon_eval.main()

    print("\n" + "=" * 60)
    print("STAGE 2/3: NPC decision-tree evaluation")
    print("=" * 60)
    npc_eval.main()

    print("\n" + "=" * 60)
    print("STAGE 3/3: Bayesian combat evaluation")
    print("=" * 60)
    combat_eval.main()

    elapsed = time.time() - started
    print(f"\nAll evaluations finished in {elapsed:.1f}s.")
    print(f"Outputs: {ROOT/'results'}")


if __name__ == "__main__":
    main()
