"""
Tkinter GUI for the AI Dungeon Master.

Layout:
    +-------------------------+--------------------+
    |                         |  Player stats      |
    |                         +--------------------+
    |    Dungeon canvas       |  Current room      |
    |    (map view)           +--------------------+
    |                         |  Inventory         |
    +-------------------------+--------------------+
    |  Action buttons                              |
    +----------------------------------------------+
    |  Event log                                   |
    +----------------------------------------------+

The GUI is a thin layer over GameState (game.py). All AI logic lives there.
"""

from __future__ import annotations

import argparse
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from typing import Optional

from game import GameState
from models import ItemType, NPCType, RoomType


# ---------------------------------------------------------------------------
# Visual constants
# ---------------------------------------------------------------------------

ROOM_COLORS = {
    RoomType.START:    "#5b8def",
    RoomType.NORMAL:   "#8b8b8b",
    RoomType.TREASURE: "#f1c40f",
    RoomType.BOSS:     "#c0392b",
    RoomType.TRAP:     "#9b59b6",
    RoomType.MERCHANT: "#27ae60",
}
UNVISITED_COLOR = "#2b2b2b"
FOG_COLOR = "#1a1a1a"
PLAYER_COLOR = "#ffffff"
CONNECTION_COLOR = "#666666"
GRID_BG = "#0e0e10"

CELL_PX = 60
PADDING = 12


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class DungeonGUI:
    def __init__(self, root: tk.Tk, state: GameState):
        self.root = root
        self.state = state

        root.title("AI Dungeon Master")
        root.configure(bg=GRID_BG)

        self.mono = tkfont.Font(family="Consolas", size=10)
        self.bold = tkfont.Font(family="Consolas", size=11, weight="bold")
        self.title_f = tkfont.Font(family="Segoe UI", size=14, weight="bold")

        self._build_layout()
        self.refresh()

    # -- layout ------------------------------------------------------------

    def _build_layout(self) -> None:
        main = tk.Frame(self.root, bg=GRID_BG)
        main.pack(fill=tk.BOTH, expand=True, padx=PADDING, pady=PADDING)

        # Top: map canvas (left) + side panels (right)
        top = tk.Frame(main, bg=GRID_BG)
        top.pack(fill=tk.BOTH, expand=True)

        # --- map canvas ---
        d = self.state.dungeon
        canvas_w = d.width * CELL_PX + 2 * PADDING
        canvas_h = d.height * CELL_PX + 2 * PADDING
        self.canvas = tk.Canvas(
            top, width=canvas_w, height=canvas_h,
            bg=GRID_BG, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, anchor=tk.N)

        # --- side panels ---
        right = tk.Frame(top, bg=GRID_BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(PADDING, 0))

        self._build_stats_panel(right)
        self._build_room_panel(right)
        self._build_inventory_panel(right)

        # Action bar
        self._build_action_bar(main)

        # Event log
        self._build_event_log(main)

    def _section(self, parent: tk.Widget, title: str) -> tk.Frame:
        wrapper = tk.Frame(parent, bg=GRID_BG, pady=4)
        wrapper.pack(fill=tk.X, pady=(0, 8))
        tk.Label(wrapper, text=title, font=self.title_f,
                 fg="#e6e6e6", bg=GRID_BG, anchor="w").pack(fill=tk.X)
        body = tk.Frame(wrapper, bg="#1a1a1f", padx=10, pady=8)
        body.pack(fill=tk.X)
        return body

    def _build_stats_panel(self, parent: tk.Widget) -> None:
        body = self._section(parent, "Player")
        self.stat_name = tk.Label(body, font=self.bold, bg="#1a1a1f", fg="#fafafa")
        self.stat_name.pack(anchor="w")

        self.hp_bar = ttk.Progressbar(body, length=240, maximum=100)
        self.hp_bar.pack(fill=tk.X, pady=(4, 2))
        self.hp_text = tk.Label(body, font=self.mono, bg="#1a1a1f", fg="#cfcfcf")
        self.hp_text.pack(anchor="w")
        self.stat_text = tk.Label(body, font=self.mono, bg="#1a1a1f",
                                  fg="#cfcfcf", justify="left")
        self.stat_text.pack(anchor="w")

    def _build_room_panel(self, parent: tk.Widget) -> None:
        body = self._section(parent, "Current room")
        self.room_text = tk.Label(body, font=self.mono, bg="#1a1a1f",
                                  fg="#cfcfcf", justify="left", wraplength=300,
                                  anchor="w")
        self.room_text.pack(fill=tk.X, anchor="w")

        # Buttons for picking up items
        self.room_items_frame = tk.Frame(body, bg="#1a1a1f")
        self.room_items_frame.pack(fill=tk.X, pady=(6, 0))

    def _build_inventory_panel(self, parent: tk.Widget) -> None:
        body = self._section(parent, "Inventory")
        self.inv_listbox = tk.Listbox(
            body, height=6, font=self.mono,
            bg="#0e0e10", fg="#e6e6e6",
            selectbackground="#5b8def", borderwidth=0,
            activestyle="none")
        self.inv_listbox.pack(fill=tk.X)

        btns = tk.Frame(body, bg="#1a1a1f")
        btns.pack(fill=tk.X, pady=(6, 0))
        tk.Button(btns, text="Use selected", command=self._on_use_item,
                  width=14).pack(side=tk.LEFT, padx=(0, 6))

    def _build_action_bar(self, parent: tk.Widget) -> None:
        bar = tk.Frame(parent, bg=GRID_BG, pady=8)
        bar.pack(fill=tk.X)

        self.move_buttons: dict = {}
        for label in ("North", "South", "East", "West"):
            b = tk.Button(bar, text=label, width=8,
                          command=lambda l=label: self._on_move(l))
            b.pack(side=tk.LEFT, padx=2)
            self.move_buttons[label] = b

        tk.Frame(bar, width=20, bg=GRID_BG).pack(side=tk.LEFT)

        self.btn_attack = tk.Button(bar, text="Attack", width=8,
                                    command=self._on_attack)
        self.btn_attack.pack(side=tk.LEFT, padx=2)
        self.btn_flee = tk.Button(bar, text="Flee", width=8,
                                  command=self._on_flee)
        self.btn_flee.pack(side=tk.LEFT, padx=2)
        self.btn_talk = tk.Button(bar, text="Talk / Trade", width=12,
                                  command=self._on_talk)
        self.btn_talk.pack(side=tk.LEFT, padx=2)

    def _build_event_log(self, parent: tk.Widget) -> None:
        body = self._section(parent, "Event log")
        self.log_box = tk.Text(body, height=10, font=self.mono,
                               bg="#0e0e10", fg="#cfcfcf",
                               borderwidth=0, wrap=tk.WORD)
        self.log_box.pack(fill=tk.BOTH, expand=True)
        self.log_box.config(state=tk.DISABLED)

    # -- handlers ----------------------------------------------------------

    def _on_move(self, direction: str) -> None:
        x, y = self.state.player.position
        target = {
            "North": (x, y - 1), "South": (x, y + 1),
            "East":  (x + 1, y), "West":  (x - 1, y),
        }[direction]
        self.state.move(target)
        self.refresh()
        self._maybe_endgame()

    def _on_attack(self) -> None:
        self.state.attack()
        self.refresh()
        self._maybe_endgame()

    def _on_flee(self) -> None:
        self.state.flee()
        self.refresh()
        self._maybe_endgame()

    def _on_talk(self) -> None:
        self.state.talk()
        self.refresh()

    def _on_pickup(self, idx: int) -> None:
        self.state.pick_up(idx)
        self.refresh()

    def _on_use_item(self) -> None:
        sel = self.inv_listbox.curselection()
        if sel:
            self.state.use_item(sel[0])
            self.refresh()
            self._maybe_endgame()

    def _maybe_endgame(self) -> None:
        if self.state.status.game_over:
            self.refresh()  # final repaint first
            if self.state.status.victory:
                messagebox.showinfo(
                    "Victory!",
                    f"You defeated the boss in {self.state.turn} turns.\n"
                    f"Final HP: {self.state.player.hp}/{self.state.player.max_hp}\n"
                    f"Gold: {self.state.player.gold}")
            else:
                messagebox.showwarning(
                    "Defeated",
                    f"You fell after {self.state.turn} turns.\n"
                    f"Gold collected: {self.state.player.gold}")

    # -- repaint -----------------------------------------------------------

    def refresh(self) -> None:
        self._draw_map()
        self._draw_stats()
        self._draw_room()
        self._draw_inventory()
        self._draw_log()
        self._update_button_state()

    def _draw_map(self) -> None:
        self.canvas.delete("all")
        d = self.state.dungeon
        px = self.state.player.position

        # Connections first (so cells overdraw)
        for coords, room in d.rooms.items():
            if not room.visited:
                continue
            cx1, cy1 = self._cell_center(coords)
            for nb in room.connections:
                if nb not in d.rooms:
                    continue
                if not d.rooms[nb].visited:
                    continue
                cx2, cy2 = self._cell_center(nb)
                self.canvas.create_line(
                    cx1, cy1, cx2, cy2,
                    fill=CONNECTION_COLOR, width=3)

        # Cells
        for coords, room in d.rooms.items():
            x, y = coords
            x0 = PADDING + x * CELL_PX + 6
            y0 = PADDING + y * CELL_PX + 6
            x1 = x0 + CELL_PX - 12
            y1 = y0 + CELL_PX - 12
            if not room.visited:
                fill = FOG_COLOR
                outline = "#222"
            else:
                fill = ROOM_COLORS.get(room.room_type, UNVISITED_COLOR)
                outline = "#333"
            # Boss room locked indicator
            if (room.room_type == RoomType.BOSS
                    and not self.state.status.boss_unlocked
                    and room.visited):
                outline = "#f39c12"
            self.canvas.create_rectangle(x0, y0, x1, y1,
                                         fill=fill, outline=outline, width=2)
            if room.visited:
                glyph = {
                    RoomType.START: "S", RoomType.BOSS: "B",
                    RoomType.TREASURE: "T", RoomType.MERCHANT: "M",
                    RoomType.TRAP: "X", RoomType.NORMAL: "·",
                }.get(room.room_type, "?")
                self.canvas.create_text(
                    (x0 + x1) / 2, (y0 + y1) / 2,
                    text=glyph, fill="#0a0a0a",
                    font=self.bold)

        # Player marker
        cx, cy = self._cell_center(px)
        r = 10
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                fill=PLAYER_COLOR, outline="#000",
                                width=2)

    def _cell_center(self, coords):
        x, y = coords
        return (PADDING + x * CELL_PX + CELL_PX / 2,
                PADDING + y * CELL_PX + CELL_PX / 2)

    def _draw_stats(self) -> None:
        p = self.state.player
        self.stat_name.config(text=f"{p.name}")
        pct = (p.hp / p.max_hp) * 100 if p.max_hp else 0
        self.hp_bar["value"] = pct
        self.hp_text.config(text=f"HP {p.hp}/{p.max_hp}")
        keystr = "✓ Boss Key" if self.state.has_key() else "no key"
        self.stat_text.config(
            text=(f"ATK {p.attack}    DEF {p.defense}\n"
                  f"Gold {p.gold}    Pos {p.position}\n"
                  f"Turn {self.state.turn}    {keystr}"))

    def _draw_room(self) -> None:
        room = self.state.current_room()
        lines = [f"Type: {room.room_type.value}",
                 f"Connections: {sorted(room.connections)}"]
        if room.npcs:
            lines.append("NPCs:")
            for n in room.npcs:
                tag = "(hostile)" if n.npc_type in (NPCType.ENEMY, NPCType.BOSS) else ""
                lines.append(f"  - {n.name} HP {n.hp} {tag}")
        else:
            lines.append("No NPCs.")
        if self.state.status.in_combat and self.state.status.combat_enemy:
            e = self.state.status.combat_enemy
            lines.append(f"** IN COMBAT vs {e.name} (HP {e.hp}) **")
        self.room_text.config(text="\n".join(lines))

        # Pickup buttons
        for w in self.room_items_frame.winfo_children():
            w.destroy()
        if room.items:
            tk.Label(self.room_items_frame, text="On the floor:",
                     font=self.mono, bg="#1a1a1f",
                     fg="#cfcfcf").pack(anchor="w")
            for i, item in enumerate(list(room.items)):
                tk.Button(self.room_items_frame,
                          text=f"Pick up: {item.name}",
                          command=lambda idx=i: self._on_pickup(idx)
                          ).pack(anchor="w", pady=1)

    def _draw_inventory(self) -> None:
        self.inv_listbox.delete(0, tk.END)
        for item in self.state.player.inventory:
            label = f"{item.name}  [{item.item_type.value}]"
            if item.item_type == ItemType.WEAPON:
                label += f"  +{item.properties.get('damage', 0)} ATK"
            elif item.item_type == ItemType.POTION:
                label += f"  heals {item.properties.get('heal', 0)}"
            self.inv_listbox.insert(tk.END, label)

    def _draw_log(self) -> None:
        self.log_box.config(state=tk.NORMAL)
        self.log_box.delete("1.0", tk.END)
        self.log_box.insert(tk.END, "\n".join(self.state.event_log))
        self.log_box.see(tk.END)
        self.log_box.config(state=tk.DISABLED)

    def _update_button_state(self) -> None:
        # Movement buttons
        x, y = self.state.player.position
        targets = {
            "North": (x, y - 1), "South": (x, y + 1),
            "East":  (x + 1, y), "West":  (x - 1, y),
        }
        room = self.state.current_room()
        in_combat = self.state.status.in_combat
        game_over = self.state.status.game_over
        for label, target in targets.items():
            enabled = (target in room.connections
                       and not in_combat and not game_over)
            self.move_buttons[label].config(
                state=tk.NORMAL if enabled else tk.DISABLED)

        self.btn_attack.config(state=tk.NORMAL if in_combat and not game_over else tk.DISABLED)
        self.btn_flee.config(state=tk.NORMAL if in_combat and not game_over else tk.DISABLED)
        has_friendly = any(n.npc_type not in (NPCType.ENEMY, NPCType.BOSS)
                           for n in room.npcs)
        self.btn_talk.config(
            state=tk.NORMAL if has_friendly and not in_combat and not game_over else tk.DISABLED)


# ---------------------------------------------------------------------------
# Launcher
# ---------------------------------------------------------------------------

def launch(grid: int = 8, rooms: int = 12, seed: Optional[int] = None,
           player_name: str = "Hero", player_class: str = "Warrior") -> None:
    state = GameState(grid_size=grid, num_rooms=rooms,
                      player_name=player_name, player_class=player_class,
                      seed=seed)
    root = tk.Tk()
    DungeonGUI(root, state)
    root.mainloop()


def main() -> None:
    ap = argparse.ArgumentParser(description="AI Dungeon Master GUI")
    ap.add_argument("--grid", type=int, default=8, help="Grid side length")
    ap.add_argument("--rooms", type=int, default=12, help="Number of rooms")
    ap.add_argument("--seed", type=int, default=None, help="Random seed")
    ap.add_argument("--name", type=str, default="Hero")
    ap.add_argument("--class", dest="player_class", type=str, default="Warrior",
                    choices=["Warrior", "Rogue", "Cleric", "Mage"])
    args = ap.parse_args()
    launch(grid=args.grid, rooms=args.rooms, seed=args.seed,
           player_name=args.name, player_class=args.player_class)


if __name__ == "__main__":
    main()
