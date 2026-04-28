"""
Tkinter GUI for the AI Dungeon Master.
Updated to support Step-by-Step CSP Generation.
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

    def _build_layout(self) -> None:
        main = tk.Frame(self.root, bg=GRID_BG)
        main.pack(fill=tk.BOTH, expand=True, padx=PADDING, pady=PADDING)

        top = tk.Frame(main, bg=GRID_BG)
        top.pack(fill=tk.BOTH, expand=True)

        d = self.state.dungeon
        canvas_w = d.width * CELL_PX + 2 * PADDING
        canvas_h = d.height * CELL_PX + 2 * PADDING
        self.canvas = tk.Canvas(
            top, width=canvas_w, height=canvas_h,
            bg=GRID_BG, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, anchor=tk.N)

        right = tk.Frame(top, bg=GRID_BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(PADDING, 0))

        self._build_debug_panel(right)
        self._build_stats_panel(right)
        self._build_room_panel(right)
        self._build_inventory_panel(right)

        self._build_action_bar(main)
        self._build_event_log(main)

    def _build_debug_panel(self, parent: tk.Widget) -> None:
        body = self._section(parent, "Debug Controls")
        btn_frame = tk.Frame(body, bg="#1a1a1f")
        btn_frame.pack(fill=tk.X)

        tk.Button(btn_frame, text="Regenerate", bg="#c0392b", fg="white",
                  command=self._on_regenerate, width=12).pack(side=tk.LEFT, padx=2)
        
        tk.Button(btn_frame, text="Step Gen", bg="#2980b9", fg="white",
                  command=self._on_step_gen, width=12).pack(side=tk.LEFT, padx=2)

    # -- handlers ------------------------------------------------------

    def _on_regenerate(self) -> None:
        """Fully resets the dungeon and player position."""
        # Using the params stored in state to re-init
        self.state.__init__(
            grid_size=self.state.csp_solver.width,
            num_rooms=self.state.grid_params[1],
            player_name=self.state.player.name,
            seed=None 
        )
        self.state.event_log.append("--- Dungeon Regenerated ---")
        self.refresh()

    def _on_step_gen(self) -> None:
        """Advances the CSP solver by one step and refreshes the view."""
        is_running = self.state.step_gen()
        
        # Force all currently assigned rooms to be 'visited' so they 
        # show up on the canvas during the backtracking process.
        for room in self.state.dungeon.rooms.values():
            room.visited = True
            
        self.refresh()
        
        if not is_running:
            messagebox.showinfo("CSP", "Generation complete. Movement unlocked.")

    # -- layout helpers ----------------------------------------------------

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

    # -- Action Handlers ---------------------------------------------------

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
        if hasattr(self.state, 'talk'):
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
            self.refresh()
            if self.state.status.victory:
                messagebox.showinfo("Victory!", "You defeated the boss!")
            else:
                messagebox.showwarning("Defeated", "Your journey ends here.")

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

        # Connections
        for coords, room in d.rooms.items():
            if not room.visited: continue
            cx1, cy1 = self._cell_center(coords)
            for nb in room.connections:
                if nb not in d.rooms or not d.rooms[nb].visited: continue
                cx2, cy2 = self._cell_center(nb)
                self.canvas.create_line(cx1, cy1, cx2, cy2, fill=CONNECTION_COLOR, width=3)

        # Cells
        for coords, room in d.rooms.items():
            x, y = coords
            x0, y0 = PADDING + x * CELL_PX + 6, PADDING + y * CELL_PX + 6
            x1, y1 = x0 + CELL_PX - 12, y0 + CELL_PX - 12
            
            fill = ROOM_COLORS.get(room.room_type, UNVISITED_COLOR) if room.visited else FOG_COLOR
            outline = "#333" if room.visited else "#222"
            
            if room.room_type == RoomType.BOSS and not self.state.status.boss_unlocked and room.visited:
                outline = "#f39c12"

            self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=2)
            if room.visited:
                glyph = {
                    RoomType.START: "S", RoomType.BOSS: "B",
                    RoomType.TREASURE: "T", RoomType.MERCHANT: "M",
                    RoomType.TRAP: "X", RoomType.NORMAL: "·",
                }.get(room.room_type, "?")
                self.canvas.create_text((x0+x1)/2, (y0+y1)/2, text=glyph, fill="#0a0a0a", font=self.bold)

        # Player (only if game is not in 'generation mode')
        if not self.state.gen_iterator:
            cx, cy = self._cell_center(px)
            self.canvas.create_oval(cx-10, cy-10, cx+10, cy+10, fill=PLAYER_COLOR, outline="#000", width=2)

    def _cell_center(self, coords):
        x, y = coords
        return (PADDING + x * CELL_PX + CELL_PX / 2, PADDING + y * CELL_PX + CELL_PX / 2)

    def _draw_stats(self) -> None:
        p = self.state.player
        self.stat_name.config(text=f"{p.name}")
        pct = (p.hp / p.max_hp) * 100 if p.max_hp else 0
        self.hp_bar["value"] = pct
        self.hp_text.config(text=f"HP {p.hp}/{p.max_hp}")
        
        # Check if the has_key helper exists or use a backup check
        has_key = any(i.item_type == ItemType.KEY for i in p.inventory)
        keystr = "✓ Boss Key" if has_key else "no key"
        
        self.stat_text.config(
            text=(f"ATK {p.attack}    DEF {p.defense}\n"
                  f"Gold {p.gold}    Pos {p.position}\n"
                  f"Turn {self.state.turn}    {keystr}"))

    def _draw_room(self) -> None:
        room = self.state.current_room()
        lines = [f"Type: {room.room_type.value}"]
        if room.npcs:
            lines.append("NPCs:")
            for n in room.npcs:
                tag = "(hostile)" if n.npc_type in (NPCType.ENEMY, NPCType.BOSS) else ""
                lines.append(f"  - {n.name} HP {n.hp} {tag}")
        
        if self.state.status.in_combat and self.state.status.combat_enemy:
            e = self.state.status.combat_enemy
            lines.append(f"** IN COMBAT vs {e.name} **")
        self.room_text.config(text="\n".join(lines))

        for w in self.room_items_frame.winfo_children(): w.destroy()
        if room.items:
            tk.Label(self.room_items_frame, text="On the floor:", font=self.mono, bg="#1a1a1f", fg="#cfcfcf").pack(anchor="w")
            for i, item in enumerate(list(room.items)):
                tk.Button(self.room_items_frame, text=f"Pick up: {item.name}", command=lambda idx=i: self._on_pickup(idx)).pack(anchor="w", pady=1)

    def _draw_inventory(self) -> None:
        self.inv_listbox.delete(0, tk.END)
        for item in self.state.player.inventory:
            self.inv_listbox.insert(tk.END, f"{item.name} [{item.item_type.value}]")

    def _draw_log(self) -> None:
        self.log_box.config(state=tk.NORMAL)
        self.log_box.delete("1.0", tk.END)
        self.log_box.insert(tk.END, "\n".join(self.state.event_log))
        self.log_box.see(tk.END)
        self.log_box.config(state=tk.DISABLED)

    def _update_button_state(self) -> None:
        room = self.state.current_room()
        in_combat = self.state.status.in_combat
        game_over = self.state.status.game_over
        
        for label, btn in self.move_buttons.items():
            x, y = self.state.player.position
            target = {"North": (x, y-1), "South": (x, y+1), "East": (x+1, y), "West": (x-1, y)}[label]
            enabled = (target in room.connections and not in_combat and not game_over)
            btn.config(state=tk.NORMAL if enabled else tk.DISABLED)

        self.btn_attack.config(state=tk.NORMAL if in_combat and not game_over else tk.DISABLED)
        self.btn_flee.config(state=tk.NORMAL if in_combat and not game_over else tk.DISABLED)

if __name__ == "__main__":
    from game import GameState
    root = tk.Tk()
    state = GameState(grid_size=10, num_rooms=15)
    app = DungeonGUI(root, state)
    root.mainloop()