#!/usr/bin/env python3
# editor.py – Neon Miami level editor
# Peut tourner seul (python editor.py) ou embarqué dans main.py (GS_EDITOR).

import sys
import os
import json
import copy
import math
import subprocess
import pygame

# ── Constantes layout ────────────────────────────────────────────────────────
PALETTE_W  = 140
STATUS_H   = 30
TILE       = 16
LEVELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "levels")

DEFAULT_MAP_W = 60
DEFAULT_MAP_H = 38

# Couleurs tiles dans l'éditeur (bien visibles)
TILE_TYPES = {
    0: ("floor",         ( 30,  30,  48)),
    1: ("wall_thin",     (  0, 140, 130)),
    2: ("wall_solid",    ( 90,  50, 120)),
    3: ("floor_parquet", ( 50,  42,  70)),
}

ENTITY_COLORS = {
    "player_spawn":  (  0, 220, 180),
    "enemy":         (255,  60, 100),
    "weapon_pickup": (255, 159,  28),
    "exit_trigger":  (100, 220,  80),
}

WEAPON_OPTIONS = ["pistol", "shotgun", "bat", "katana"]
PATROL_OPTIONS = ["static", "loop", "rand"]
VISION_OPTIONS = ["normal", "wide", "none"]

COL_BG        = ( 10,  10,  15)
COL_GRID      = ( 30,  30,  50)
COL_SELECT    = (  0, 255, 229)
COL_PANEL     = ( 20,  18,  30)
COL_TEXT      = (200, 200, 200)
COL_HIGHLIGHT = ( 50,  48,  70)
COL_STATUS_BG = ( 12,  12,  20)

UNDO_LIMIT = 50


# ── Palette ───────────────────────────────────────────────────────────────────
class PaletteItem:
    def __init__(self, label, key, value, category):
        self.label    = label
        self.key      = key
        self.value    = value
        self.category = category  # "tile" | "entity"

PALETTE_ITEMS = [
    PaletteItem("Floor",        "1", 0, "tile"),
    PaletteItem("Wall thin",    "2", 1, "tile"),
    PaletteItem("Wall solid",   "3", 2, "tile"),
    PaletteItem("Floor parq.",  "4", 3, "tile"),
    PaletteItem("Player spawn", "5", "player_spawn",  "entity"),
    PaletteItem("Enemy",        "6", "enemy",         "entity"),
    PaletteItem("Weapon",       "7", "weapon_pickup", "entity"),
    PaletteItem("Exit",         "8", "exit_trigger",  "entity"),
]

PALETTE_ITEM_Y0     = 36   # y du premier item dans le panel
PALETTE_ITEM_STRIDE = 34   # hauteur par item


# ── Popup dialog ──────────────────────────────────────────────────────────────
class Popup:
    def __init__(self, entity_type, font, sw, sh):
        self.entity_type = entity_type
        self.font        = font
        self.confirmed   = False
        self.result: dict = {}

        if entity_type == "enemy":
            self.fields = [
                {"label": "Weapon",  "options": WEAPON_OPTIONS, "idx": 0},
                {"label": "Patrol",  "options": PATROL_OPTIONS, "idx": 0},
                {"label": "Vision",  "options": VISION_OPTIONS, "idx": 0},
            ]
        elif entity_type == "weapon_pickup":
            self.fields = [{"label": "Weapon", "options": WEAPON_OPTIONS, "idx": 0}]
        else:
            self.fields = []

        self.cursor = 0
        self.w = 320
        self.h = max(160, 80 + len(self.fields) * 36)
        self.x = (sw - self.w) // 2
        self.y = (sh - self.h) // 2

    def handle(self, ev) -> bool:
        if ev.type != pygame.KEYDOWN: return True
        if ev.key == pygame.K_ESCAPE:  return False
        if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.result["type"] = self.entity_type
            for f in self.fields:
                self.result[f["label"].lower()] = f["options"][f["idx"]]
            self.confirmed = True; return False
        if ev.key == pygame.K_UP:
            self.cursor = (self.cursor - 1) % max(1, len(self.fields))
        if ev.key == pygame.K_DOWN:
            self.cursor = (self.cursor + 1) % max(1, len(self.fields))
        if ev.key == pygame.K_LEFT and self.fields:
            f = self.fields[self.cursor]; f["idx"] = (f["idx"] - 1) % len(f["options"])
        if ev.key == pygame.K_RIGHT and self.fields:
            f = self.fields[self.cursor]; f["idx"] = (f["idx"] + 1) % len(f["options"])
        return True

    def draw(self, surf):
        ov = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 140)); surf.blit(ov, (0, 0))
        box = pygame.Surface((self.w, self.h))
        box.fill((28, 24, 42))
        pygame.draw.rect(box, COL_SELECT, (0, 0, self.w, self.h), 2)
        box.blit(self.font.render(self.entity_type.replace("_"," ").upper(),
                                   True, COL_SELECT), (12, 10))
        y = 44
        for i, f in enumerate(self.fields):
            col = COL_SELECT if i == self.cursor else COL_TEXT
            box.blit(self.font.render(f["label"] + ":", True, COL_TEXT), (12, y))
            box.blit(self.font.render(f"< {f['options'][f['idx']]} >", True, col), (110, y))
            y += 30
        box.blit(self.font.render("↑↓ ← →   Enter OK   Esc cancel",
                                   True, (120,120,140)), (12, self.h - 26))
        surf.blit(box, (self.x, self.y))


# ── New level dialog ──────────────────────────────────────────────────────────
class NewLevelDialog:
    def __init__(self, font, sw, sh):
        self.font  = font
        self.w_str = str(DEFAULT_MAP_W)
        self.h_str = str(DEFAULT_MAP_H)
        self.focus = 0
        self.done  = False
        self.result = None
        self.w, self.h = 300, 160
        self.x = (sw - self.w) // 2
        self.y = (sh - self.h) // 2

    def handle(self, ev) -> bool:
        if ev.type != pygame.KEYDOWN: return True
        if ev.key == pygame.K_ESCAPE:  self.done = True; return False
        if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            try:
                w = max(10, min(200, int(self.w_str)))
                h = max(10, min(200, int(self.h_str)))
                self.result = (w, h)
            except ValueError: pass
            self.done = True; return False
        if ev.key == pygame.K_TAB: self.focus = 1 - self.focus; return True
        target = "w_str" if self.focus == 0 else "h_str"
        s = getattr(self, target)
        if ev.key == pygame.K_BACKSPACE: setattr(self, target, s[:-1])
        elif ev.unicode.isdigit():        setattr(self, target, s + ev.unicode)
        return True

    def draw(self, surf):
        ov = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        ov.fill((0,0,0,140)); surf.blit(ov, (0,0))
        box = pygame.Surface((self.w, self.h)); box.fill((28,24,42))
        pygame.draw.rect(box, COL_SELECT, (0,0,self.w,self.h), 2)
        box.blit(self.font.render("NEW LEVEL", True, COL_SELECT), (12,10))
        for i, (lbl, val) in enumerate([("Width  tiles:", self.w_str),
                                         ("Height tiles:", self.h_str)]):
            col = COL_SELECT if i == self.focus else COL_TEXT
            box.blit(self.font.render(lbl, True, COL_TEXT), (12, 50+i*34))
            box.blit(self.font.render(val+("_" if i==self.focus else ""),
                                       True, col), (155, 50+i*34))
        box.blit(self.font.render("Tab switch  Enter OK  Esc cancel",
                                   True, (120,120,140)), (12, self.h-26))
        surf.blit(box, (self.x, self.y))


# ── Open file dialog ──────────────────────────────────────────────────────────
class OpenDialog:
    def __init__(self, font, sw, sh):
        self.font   = font
        self.files  = sorted(f for f in os.listdir(LEVELS_DIR)
                             if f.endswith(".json")) if os.path.isdir(LEVELS_DIR) else []
        self.cursor = 0
        self.done   = False
        self.result = None
        self.w, self.h = 360, 260
        self.x = (sw - self.w) // 2
        self.y = (sh - self.h) // 2

    def handle(self, ev) -> bool:
        if ev.type != pygame.KEYDOWN: return True
        if ev.key == pygame.K_ESCAPE:  self.done = True; return False
        if not self.files: return True
        if ev.key == pygame.K_UP:   self.cursor = (self.cursor-1) % len(self.files)
        if ev.key == pygame.K_DOWN: self.cursor = (self.cursor+1) % len(self.files)
        if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.result = os.path.join(LEVELS_DIR, self.files[self.cursor])
            self.done = True; return False
        return True

    def draw(self, surf):
        ov = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        ov.fill((0,0,0,140)); surf.blit(ov, (0,0))
        box = pygame.Surface((self.w, self.h)); box.fill((28,24,42))
        pygame.draw.rect(box, COL_SELECT, (0,0,self.w,self.h), 2)
        box.blit(self.font.render("OPEN LEVEL", True, COL_SELECT), (12,10))
        if not self.files:
            box.blit(self.font.render("Aucun .json dans levels/",
                                       True, (180,80,80)), (12,50))
        else:
            start = max(0, self.cursor-4)
            for i, fname in enumerate(self.files[start:start+9]):
                col = COL_SELECT if start+i == self.cursor else COL_TEXT
                box.blit(self.font.render(fname, True, col), (12, 40+i*22))
        box.blit(self.font.render("↑↓ select  Enter open  Esc cancel",
                                   True, (120,120,140)), (12, self.h-26))
        surf.blit(box, (self.x, self.y))


# ── Utilitaires géométriques ──────────────────────────────────────────────────
def bresenham(x0, y0, x1, y1):
    pts, dx, dy = [], abs(x1-x0), abs(y1-y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        pts.append((x0, y0))
        if x0 == x1 and y0 == y1: break
        e2 = 2*err
        if e2 > -dy: err -= dy; x0 += sx
        if e2 <  dx: err += dx; y0 += sy
    return pts

def flood_fill(tiles, gx, gy, new_val):
    rows, cols = len(tiles), len(tiles[0]) if tiles else 0
    if not (0 <= gx < cols and 0 <= gy < rows): return
    old_val = tiles[gy][gx]
    if old_val == new_val: return
    stack, visited = [(gx, gy)], set()
    while stack:
        cx, cy = stack.pop()
        if (cx, cy) in visited: continue
        if not (0 <= cx < cols and 0 <= cy < rows): continue
        if tiles[cy][cx] != old_val: continue
        visited.add((cx, cy))
        tiles[cy][cx] = new_val
        stack.extend([(cx+1,cy),(cx-1,cy),(cx,cy+1),(cx,cy-1)])


# ── État du niveau édité ──────────────────────────────────────────────────────
class EditorState:
    def __init__(self, w, h):
        self.map_w    = w
        self.map_h    = h
        self.tiles    = [[0]*w for _ in range(h)]
        self.entities: list[dict] = []
        self.name     = "untitled"
        self.path     = None

    def to_json(self):
        return {"meta": {"name": self.name, "width": self.map_w,
                         "height": self.map_h, "tile_size": TILE, "version": 2},
                "tiles": self.tiles, "entities": self.entities}

    @classmethod
    def from_json(cls, data):
        meta = data["meta"]
        s = cls(meta["width"], meta["height"])
        s.name     = meta.get("name", "untitled")
        s.tiles    = [list(row) for row in data["tiles"]]
        s.entities = list(data.get("entities", []))
        return s

    def save(self, path):
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_json(), f, indent=2)
        self.path = path

    @classmethod
    def load(cls, path):
        with open(path) as f:
            data = json.load(f)
        s = cls.from_json(data)
        s.path = path
        return s


# ── Éditeur principal ─────────────────────────────────────────────────────────
class Editor:
    """
    Deux modes :
      standalone (embedded=False) : python editor.py → gère sa propre fenêtre
      embarqué   (embedded=True)  : main.py crée Editor() et appelle
                                    handle_event(ev) + draw(surface) chaque frame.
    """

    def __init__(self, open_path=None, embedded=False):
        self._embedded = embedded
        self._result: str | None = None   # 'quit' | 'test:<path>' | None

        if not embedded:
            pygame.init()
            self.screen = pygame.display.set_mode((1100, 600))
            pygame.display.set_caption("NEON MIAMI — Level Editor")
            self.clock  = pygame.time.Clock()

        self.font   = pygame.font.SysFont("consolas", 13)
        self.font_b = pygame.font.SysFont("consolas", 13, bold=True)

        # Canvas (re-créé si la surface change de taille)
        self._canvas: pygame.Surface | None = None
        self._canvas_size = (0, 0)

        self.ed = EditorState.load(open_path) if open_path else \
                  EditorState(DEFAULT_MAP_W, DEFAULT_MAP_H)

        self.zoom     = 2.0
        self.pan_x    = 0.0
        self.pan_y    = 0.0

        self.palette_idx  = 0
        self.tool         = "brush"
        self.show_grid    = True

        self._drag_start   = None
        self._drag_end     = None
        self._pan_dragging = False
        self._pan_last     = None

        self._undo: list = []
        self._redo: list = []
        self._sel_entity  = None
        self._dialog      = None
        self._status      = "Prêt — [H] aide"
        self._show_help   = False

        os.makedirs(LEVELS_DIR, exist_ok=True)

    # ── Accès dimensions dynamiques ───────────────────────────────────────────
    def _layout(self, sw, sh):
        """Retourne (canvas_w, canvas_h) en fonction de la surface cible."""
        return sw - PALETTE_W, sh - STATUS_H

    def _get_canvas(self, cw, ch):
        if self._canvas_size != (cw, ch):
            self._canvas       = pygame.Surface((cw, ch))
            self._canvas_size  = (cw, ch)
        return self._canvas

    # ── API embarquée ─────────────────────────────────────────────────────────
    def handle_event(self, ev) -> str | None:
        """
        Traite un événement Pygame.
        Retourne 'quit', 'test:<path>', ou None.
        Utilisé par main.py en mode embarqué.
        """
        self._result = None

        if self._dialog is not None:
            still_open = self._dialog.handle(ev)
            if not still_open:
                self._finish_dialog()
            return None

        self._handle(ev)
        return self._result

    def draw(self, surface: pygame.Surface):
        """Dessine l'éditeur sur la surface fournie."""
        sw, sh = surface.get_size()
        cw, ch = self._layout(sw, sh)
        canvas  = self._get_canvas(cw, ch)
        self._draw_all(surface, canvas, sw, sh, cw, ch)

    # ── Boucle standalone ─────────────────────────────────────────────────────
    def run(self):
        running = True
        while running:
            self.clock.tick(60)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False; break
                result = self.handle_event(ev)
                if result == 'quit':
                    running = False; break
                elif result and result.startswith('test:'):
                    path   = result[5:]
                    main_py = os.path.join(os.path.dirname(__file__), "main.py")
                    subprocess.Popen([sys.executable, main_py, "--level", path])
                    self._status = "Jeu lancé…"
            if running:
                self.draw(self.screen)
                pygame.display.flip()
        pygame.quit()

    # ── Helpers coordonnées ───────────────────────────────────────────────────
    def _screen_to_tile(self, sx, sy):
        return int((sx / self.zoom + self.pan_x) // TILE), \
               int((sy / self.zoom + self.pan_y) // TILE)

    def _tile_to_canvas(self, gx, gy):
        return int((gx * TILE - self.pan_x) * self.zoom), \
               int((gy * TILE - self.pan_y) * self.zoom)

    def _tile_px(self):
        return max(2, int(TILE * self.zoom))

    def _valid(self, gx, gy):
        return 0 <= gx < self.ed.map_w and 0 <= gy < self.ed.map_h

    # ── Undo/redo ─────────────────────────────────────────────────────────────
    def _push_undo(self):
        snap = (copy.deepcopy(self.ed.tiles), copy.deepcopy(self.ed.entities))
        self._undo.append(snap)
        if len(self._undo) > UNDO_LIMIT: self._undo.pop(0)
        self._redo.clear()

    def _undo_step(self):
        if not self._undo: return
        self._redo.append((copy.deepcopy(self.ed.tiles), copy.deepcopy(self.ed.entities)))
        t, e = self._undo.pop(); self.ed.tiles = t; self.ed.entities = e
        self._status = "Annulé"

    def _redo_step(self):
        if not self._redo: return
        self._undo.append((copy.deepcopy(self.ed.tiles), copy.deepcopy(self.ed.entities)))
        t, e = self._redo.pop(); self.ed.tiles = t; self.ed.entities = e
        self._status = "Rétabli"

    # ── Peinture ──────────────────────────────────────────────────────────────
    def _paint(self, gx, gy, val):
        if self._valid(gx, gy):
            self.ed.tiles[gy][gx] = val

    def _tile_val(self):
        item = PALETTE_ITEMS[self.palette_idx]
        return item.value if item.category == "tile" else 0

    def _entity_type(self):
        item = PALETTE_ITEMS[self.palette_idx]
        return item.value if item.category == "entity" else None

    def _entity_at(self, gx, gy):
        for e in self.ed.entities:
            if e["gx"] == gx and e["gy"] == gy: return e
        return None

    def _place_entity(self, gx, gy, etype, props=None):
        if not self._valid(gx, gy): return
        if etype in ("player_spawn", "exit_trigger"):
            self.ed.entities = [e for e in self.ed.entities if e["type"] != etype]
        ent = {"type": etype, "gx": gx, "gy": gy}
        if props: ent.update(props)
        self.ed.entities.append(ent)

    def _commit_drag(self, x0, y0, x1, y1):
        val = self._tile_val()
        if self.tool == "rect":
            for gy in range(min(y0,y1), max(y0,y1)+1):
                for gx in range(min(x0,x1), max(x0,x1)+1):
                    self._paint(gx, gy, val)
        elif self.tool == "line":
            for gx, gy in bresenham(x0, y0, x1, y1):
                self._paint(gx, gy, val)

    # ── Fichiers ──────────────────────────────────────────────────────────────
    def _save(self):
        path = self.ed.path or os.path.join(LEVELS_DIR, self.ed.name + ".json")
        self.ed.save(path)
        self._status = f"Sauvegardé → {os.path.basename(path)}"

    def _test_in_game(self):
        self._save()
        path = self.ed.path or os.path.join(LEVELS_DIR, "current.json")
        if self._embedded:
            self._result = f'test:{path}'
        else:
            main_py = os.path.join(os.path.dirname(__file__), "main.py")
            subprocess.Popen([sys.executable, main_py, "--level", path])
            self._status = "Jeu lancé…"

    # ── Gestion événements ────────────────────────────────────────────────────
    def _handle(self, ev):
        if ev.type == pygame.KEYDOWN:
            self._key(ev); return
        if ev.type == pygame.MOUSEWHEEL:
            self._wheel(ev); return
        if ev.type == pygame.MOUSEBUTTONDOWN: self._mdown(ev)
        elif ev.type == pygame.MOUSEBUTTONUP:   self._mup(ev)
        elif ev.type == pygame.MOUSEMOTION:     self._mmove(ev)

    def _key(self, ev):
        ctrl = ev.mod & pygame.KMOD_CTRL

        if ev.key == pygame.K_ESCAPE:
            self._result = 'quit'; return

        if ev.key == pygame.K_h:
            self._show_help = not self._show_help; return
        if ev.key == pygame.K_g:
            self.show_grid = not self.show_grid; return
        if ev.key == pygame.K_F5:
            self._test_in_game(); return

        if ctrl and ev.key == pygame.K_s: self._save(); return
        if ctrl and ev.key == pygame.K_z: self._undo_step(); return
        if ctrl and ev.key == pygame.K_y: self._redo_step(); return
        if ctrl and ev.key == pygame.K_o:
            self._dialog = OpenDialog(self.font, *self._cur_sw_sh()); return

        if ev.key == pygame.K_n and not ctrl:
            self._dialog = NewLevelDialog(self.font, *self._cur_sw_sh()); return

        if ev.key == pygame.K_DELETE:
            if self._sel_entity and self._sel_entity in self.ed.entities:
                self._push_undo()
                self.ed.entities.remove(self._sel_entity)
                self._sel_entity = None; return

        num = {pygame.K_1:0,pygame.K_2:1,pygame.K_3:2,pygame.K_4:3,
               pygame.K_5:4,pygame.K_6:5,pygame.K_7:6,pygame.K_8:7}
        if ev.key in num:
            self.palette_idx = min(num[ev.key], len(PALETTE_ITEMS)-1)
            item = PALETTE_ITEMS[self.palette_idx]
            self.tool = "entity" if item.category == "entity" else "brush"
            return

        tools = {pygame.K_b:"brush", pygame.K_f:"fill",
                 pygame.K_e:"erase", pygame.K_r:"rect", pygame.K_l:"line"}
        if ev.key in tools:
            self.tool = tools[ev.key]

    def _cur_sw_sh(self):
        """Taille de la surface courante (fallback pour les dialogues)."""
        if self._embedded and self._canvas:
            cw, ch = self._canvas_size
            return cw + PALETTE_W, ch + STATUS_H
        if not self._embedded and hasattr(self, 'screen'):
            return self.screen.get_size()
        return 960, 540

    def _wheel(self, ev):
        mx, my = pygame.mouse.get_pos()
        sw, sh = self._cur_sw_sh()
        cw = sw - PALETTE_W
        if mx >= cw: return
        old_z = self.zoom
        self.zoom = max(0.5, min(4.0, self.zoom + ev.y * 0.25))
        wx = mx / old_z + self.pan_x
        wy = my / old_z + self.pan_y
        self.pan_x = wx - mx / self.zoom
        self.pan_y = wy - my / self.zoom

    def _mdown(self, ev):
        mx, my = ev.pos
        sw, sh = self._cur_sw_sh()
        cw, ch = self._layout(sw, sh)

        if ev.button == 2:
            self._pan_dragging = True; self._pan_last = (mx, my); return

        if mx >= cw:
            self._palette_click(my); return
        if my >= ch: return

        gx, gy = self._screen_to_tile(mx, my)

        if ev.button == 3:
            self._push_undo(); self._paint(gx, gy, 0); return
        if ev.button != 1: return

        # Shift = pipette
        if ev.mod & pygame.KMOD_SHIFT:
            if self._valid(gx, gy):
                val = self.ed.tiles[gy][gx]
                for i, item in enumerate(PALETTE_ITEMS):
                    if item.category == "tile" and item.value == val:
                        self.palette_idx = i; self.tool = "brush"; break
            return

        item = PALETTE_ITEMS[self.palette_idx]

        if item.category == "entity" or self.tool == "entity":
            etype = item.value if item.category == "entity" else None
            if etype is None: return
            existing = self._entity_at(gx, gy)
            if existing:
                self._sel_entity = existing; return
            if etype in ("enemy", "weapon_pickup"):
                self._pending_entity = (gx, gy)
                self._dialog = Popup(etype, self.font, *self._cur_sw_sh())
            else:
                self._push_undo(); self._place_entity(gx, gy, etype)
            return

        if self.tool == "fill":
            self._push_undo(); flood_fill(self.ed.tiles, gx, gy, self._tile_val()); return

        if self.tool in ("rect", "line"):
            self._drag_start = (gx, gy); self._drag_end = (gx, gy); return

        if self.tool in ("brush", "erase"):
            self._push_undo()
            self._paint(gx, gy, 0 if self.tool == "erase" else self._tile_val())

    def _mup(self, ev):
        if ev.button == 2:
            self._pan_dragging = False; return
        if ev.button == 1 and self._drag_start and self._drag_end:
            self._push_undo()
            self._commit_drag(*self._drag_start, *self._drag_end)
            self._drag_start = self._drag_end = None

    def _mmove(self, ev):
        mx, my = ev.pos
        sw, sh = self._cur_sw_sh()
        cw, ch = self._layout(sw, sh)

        if self._pan_dragging and self._pan_last:
            dx = (mx - self._pan_last[0]) / self.zoom
            dy = (my - self._pan_last[1]) / self.zoom
            self.pan_x -= dx; self.pan_y -= dy
            self._pan_last = (mx, my)

        if 0 <= mx < cw and 0 <= my < ch:
            if pygame.mouse.get_pressed()[0]:
                gx, gy = self._screen_to_tile(mx, my)
                if self.tool in ("brush", "erase"):
                    self._paint(gx, gy, 0 if self.tool == "erase" else self._tile_val())
                elif self.tool in ("rect", "line") and self._drag_start:
                    self._drag_end = (gx, gy)
            gx, gy = self._screen_to_tile(mx, my)
            if self._valid(gx, gy):
                tid   = self.ed.tiles[gy][gx]
                tname = TILE_TYPES.get(tid, ("?",))[0]
                self._status = (f"tile({gx},{gy})={tname}  "
                                f"outil={self.tool}  zoom={self.zoom:.1f}×  "
                                f"actif={PALETTE_ITEMS[self.palette_idx].label}")

    def _palette_click(self, my):
        idx = (my - PALETTE_ITEM_Y0) // PALETTE_ITEM_STRIDE
        if 0 <= idx < len(PALETTE_ITEMS):
            self.palette_idx = idx
            self.tool = "entity" if PALETTE_ITEMS[idx].category == "entity" else "brush"

    def _finish_dialog(self):
        d = self._dialog; self._dialog = None
        if isinstance(d, NewLevelDialog) and d.result:
            self._push_undo()
            self.ed = EditorState(*d.result)
            self._status = f"Nouveau niveau {d.result[0]}×{d.result[1]}"
        elif isinstance(d, OpenDialog) and d.result:
            self.ed = EditorState.load(d.result)
            self._undo.clear(); self._redo.clear()
            self._status = f"Ouvert : {os.path.basename(d.result)}"
        elif isinstance(d, Popup) and d.confirmed:
            if hasattr(self, "_pending_entity"):
                gx, gy = self._pending_entity; del self._pending_entity
                self._push_undo()
                self._place_entity(gx, gy, d.entity_type, d.result)

    # ── Dessin ────────────────────────────────────────────────────────────────
    def _draw_all(self, surface, canvas, sw, sh, cw, ch):
        surface.fill(COL_BG)
        self._draw_canvas(canvas, cw, ch)
        surface.blit(canvas, (0, 0))
        self._draw_palette(surface, cw, sh)
        self._draw_status(surface, sw, sh)
        if self._dialog:
            self._dialog.draw(surface)
        if self._show_help:
            self._draw_help(surface, sw, sh)

    def _draw_canvas(self, c, cw, ch):
        c.fill(COL_BG)
        ts = self._tile_px()
        ed = self.ed

        for gy in range(ed.map_h):
            for gx in range(ed.map_w):
                sx, sy = self._tile_to_canvas(gx, gy)
                if sx + ts < 0 or sx > cw or sy + ts < 0 or sy > ch: continue
                col = TILE_TYPES.get(ed.tiles[gy][gx], (None,(30,30,48)))[1]
                pygame.draw.rect(c, col, (sx, sy, ts, ts))

        if self.show_grid and ts >= 4:
            for gy in range(ed.map_h + 1):
                sy = int((gy * TILE - self.pan_y) * self.zoom)
                if 0 <= sy <= ch:
                    pygame.draw.line(c, COL_GRID, (0, sy), (cw, sy))
            for gx in range(ed.map_w + 1):
                sx = int((gx * TILE - self.pan_x) * self.zoom)
                if 0 <= sx <= cw:
                    pygame.draw.line(c, COL_GRID, (sx, 0), (sx, ch))

        for ent in ed.entities:
            sx, sy = self._tile_to_canvas(ent["gx"], ent["gy"])
            if sx + ts < 0 or sx > cw or sy + ts < 0 or sy > ch: continue
            col = ENTITY_COLORS.get(ent["type"], (200,200,200))
            r   = max(4, ts // 2 - 1)
            cx, cy = sx + ts//2, sy + ts//2
            pygame.draw.circle(c, col, (cx, cy), r)
            pygame.draw.circle(c, (0,0,0), (cx, cy), r, 1)
            if ent is self._sel_entity:
                pygame.draw.circle(c, COL_SELECT, (cx, cy), r+3, 2)

        # Preview drag
        if self._drag_start and self._drag_end and self.tool in ("rect", "line"):
            x0, y0 = self._drag_start; x1, y1 = self._drag_end
            if self.tool == "rect":
                sx0, sy0 = self._tile_to_canvas(min(x0,x1), min(y0,y1))
                sx1, sy1 = self._tile_to_canvas(max(x0,x1)+1, max(y0,y1)+1)
                pygame.draw.rect(c, COL_SELECT, (sx0, sy0, sx1-sx0, sy1-sy0), 2)
            else:
                for gx, gy in bresenham(x0, y0, x1, y1):
                    sx, sy = self._tile_to_canvas(gx, gy)
                    pygame.draw.rect(c, COL_SELECT, (sx, sy, ts, ts), 1)

        # Hover
        mx, my = pygame.mouse.get_pos()
        if 0 <= mx < cw and 0 <= my < ch:
            gx, gy = self._screen_to_tile(mx, my)
            sx, sy = self._tile_to_canvas(gx, gy)
            pygame.draw.rect(c, COL_SELECT, (sx, sy, ts, ts), 1)

    def _draw_palette(self, s, px, sh):
        pygame.draw.rect(s, COL_PANEL, (px, 0, PALETTE_W, sh - STATUS_H))
        s.blit(self.font_b.render("PALETTE", True, COL_SELECT), (px+6, 8))

        for i, item in enumerate(PALETTE_ITEMS):
            y  = PALETTE_ITEM_Y0 + i * PALETTE_ITEM_STRIDE
            bg = COL_HIGHLIGHT if i == self.palette_idx else COL_PANEL
            pygame.draw.rect(s, bg, (px+2, y, PALETTE_W-4, 30))
            if i == self.palette_idx:
                pygame.draw.rect(s, COL_SELECT, (px+2, y, PALETTE_W-4, 30), 1)
            col = (TILE_TYPES[item.value][1] if item.category == "tile"
                   else ENTITY_COLORS.get(item.value, COL_TEXT))
            pygame.draw.rect(s, col, (px+6, y+7, 12, 12))
            s.blit(self.font.render(f"[{item.key}] {item.label}", True, COL_TEXT),
                   (px+22, y+8))

        ty = PALETTE_ITEM_Y0 + len(PALETTE_ITEMS) * PALETTE_ITEM_STRIDE + 10
        pygame.draw.line(s, COL_GRID, (px+4, ty), (px+PALETTE_W-4, ty)); ty += 6
        s.blit(self.font_b.render("OUTILS", True, COL_SELECT), (px+6, ty)); ty += 18
        for k, lbl in [("B","Brush"),("F","Fill"),("E","Erase"),("R","Rect"),("L","Line")]:
            col = COL_SELECT if self.tool.lower() == lbl.lower() else COL_TEXT
            s.blit(self.font.render(f"[{k}] {lbl}", True, col), (px+6, ty)); ty += 18

        ty += 6
        pygame.draw.line(s, COL_GRID, (px+4, ty), (px+PALETTE_W-4, ty)); ty += 6
        for line in ["[G] Grille","[F5] Tester","[Ctrl+S] Sauv.",
                     "[Ctrl+Z] Annuler","[Esc] Retour","[H] Aide"]:
            s.blit(self.font.render(line, True, (140,140,160)), (px+6, ty)); ty += 17

    def _draw_status(self, s, sw, sh):
        y = sh - STATUS_H
        pygame.draw.rect(s, COL_STATUS_BG, (0, y, sw, STATUS_H))
        pygame.draw.line(s, COL_GRID, (0, y), (sw, y))
        name = (os.path.basename(self.ed.path) if self.ed.path
                else self.ed.name + ".json")
        txt = self.font.render(
            f"  {name}  |  {self.ed.map_w}×{self.ed.map_h}  |  {self._status}",
            True, COL_TEXT)
        s.blit(txt, (4, y+8))

    def _draw_help(self, s, sw, sh):
        lines = [
            "NEON MIAMI — Aide éditeur",
            "",
            "1-8       Sélectionner tile / entité",
            "B         Pinceau",
            "F         Remplissage (flood fill)",
            "E         Gomme",
            "R         Rectangle (drag)",
            "L         Ligne (Bresenham drag)",
            "G         Afficher/cacher grille",
            "Shift+LMC Pipette",
            "Clic droit Effacer tile",
            "Molette+drag  Pan du canvas",
            "Scroll    Zoom",
            "Suppr     Supprimer entité sélectionnée",
            "Ctrl+Z/Y  Annuler / Rétablir",
            "Ctrl+S    Sauvegarder",
            "Ctrl+O    Ouvrir",
            "N         Nouveau niveau",
            "F5        Tester dans le jeu",
            "Échap     Retour au menu",
            "H         Fermer cette aide",
        ]
        w = 360; h = len(lines)*20 + 20
        ov = pygame.Surface((w, h), pygame.SRCALPHA)
        ov.fill((20, 16, 32, 230))
        pygame.draw.rect(ov, COL_SELECT, (0, 0, w, h), 2)
        for i, line in enumerate(lines):
            ov.blit(self.font.render(line, True,
                                      COL_SELECT if i == 0 else COL_TEXT),
                    (12, 10+i*20))
        s.blit(ov, ((sw-w)//2, (sh-h)//2))


# ── Entrée standalone ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    Editor(open_path=path, embedded=False).run()
