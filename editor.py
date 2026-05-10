#!/usr/bin/env python3
# editor.py – Neon Miami level editor (v4 – simplifié, entièrement cliquable)

import sys, os, json, copy, math, subprocess
import pygame

PALETTE_W  = 160
STATUS_H   = 36
TILE       = 16
LEVELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "levels")
DEFAULT_W, DEFAULT_H = 60, 38
UNDO_LIMIT = 50

# ── Couleurs tiles (bien visibles) ───────────────────────────────────────────
TILE_COLOR = {
    0: (30,  30,  48),    # floor   – bleu nuit
    1: (0,  160, 140),    # wall_thin  – cyan vif
    2: (110, 55, 140),    # wall_solid – violet
    3: (55,  45,  75),    # parquet  – légèrement plus clair
}
TILE_NAME = {0:"floor", 1:"wall_thin", 2:"wall_solid", 3:"parquet"}
ENTITY_COLOR = {
    "player_spawn": (0, 220, 180),
    "enemy":        (255, 60, 100),
    "weapon_pickup":(255, 159, 28),
    "exit_trigger": (80, 220, 80),
}
WEAPON_LIST = ["pistol","shotgun","bat","katana"]
PATROL_LIST = ["static","loop","rand"]

COL_BG     = (10,  10,  15)
COL_PANEL  = (22,  18,  32)
COL_BORDER = (45,  40,  65)
COL_SEL    = (0,  230, 210)
COL_TEXT   = (210, 210, 210)
COL_DIM    = (100, 100, 130)
COL_GRID   = (28,  28,  46)
COL_STATUS = (12,  12,  22)

# ── Items de la palette ───────────────────────────────────────────────────────
class PItem:
    def __init__(self, label, kind, value):
        self.label = label
        self.kind  = kind   # "tile" | "entity"
        self.value = value  # int (tile id) ou str (entity type)

PALETTE = [
    PItem("Floor",         "tile",   0),
    PItem("Wall thin",     "tile",   1),
    PItem("Wall solid",    "tile",   2),
    PItem("Parquet",       "tile",   3),
    PItem("Player spawn",  "entity", "player_spawn"),
    PItem("Enemy",         "entity", "enemy"),
    PItem("Weapon",        "entity", "weapon_pickup"),
    PItem("Exit",          "entity", "exit_trigger"),
]
PAL_Y0, PAL_H = 44, 36   # position et hauteur de chaque item


# ── Popup entièrement cliquable ───────────────────────────────────────────────
class EntityPopup:
    """Popup pour configurer une entité. Cliquable à la souris."""

    def __init__(self, etype: str, font, sw: int, sh: int):
        self.etype     = etype
        self.font      = font
        self.confirmed = False
        self.cancelled = False

        if etype == "enemy":
            self.fields = [
                {"label":"Arme",    "opts": WEAPON_LIST, "idx": 0},
                {"label":"Patrouille","opts": PATROL_LIST,"idx": 0},
            ]
        elif etype == "weapon_pickup":
            self.fields = [{"label":"Arme", "opts": WEAPON_LIST, "idx": 0}]
        else:
            self.fields = []

        n    = max(len(self.fields), 1)
        self.w = 340
        self.h = 60 + n * 54 + 54
        self.x = (sw - self.w) // 2
        self.y = (sh - self.h) // 2
        self._btn_ok  = pygame.Rect(self.x + 20,           self.y + self.h - 44,
                                     (self.w - 52) // 2,    36)
        self._btn_can = pygame.Rect(self.x + self.w // 2 + 6, self.y + self.h - 44,
                                     (self.w - 52) // 2,    36)

    # ── "<" / ">" arrow buttons for one field ────────────────────────────────
    def _field_rects(self, fi: int):
        fy = self.y + 50 + fi * 54
        lx = self.x + 10
        rx = self.x + self.w - 40
        prev = pygame.Rect(lx,      fy + 14, 32, 26)
        nxt  = pygame.Rect(rx,      fy + 14, 32, 26)
        return prev, nxt

    def handle_key(self, ev) -> bool:
        if ev.key == pygame.K_ESCAPE:   self.cancelled = True; return False
        if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.confirmed = True; return False
        if self.fields:
            if ev.key == pygame.K_LEFT:
                f = self.fields[0]; f["idx"] = (f["idx"]-1) % len(f["opts"])
            if ev.key == pygame.K_RIGHT:
                f = self.fields[0]; f["idx"] = (f["idx"]+1) % len(f["opts"])
        return True

    def handle_click(self, pos) -> bool:
        """True = popup reste ouverte, False = fermée."""
        mx, my = pos
        if self._btn_ok.collidepoint(mx, my):
            self.confirmed = True; return False
        if self._btn_can.collidepoint(mx, my):
            self.cancelled = True; return False
        for fi, f in enumerate(self.fields):
            prev, nxt = self._field_rects(fi)
            if prev.collidepoint(mx, my):
                f["idx"] = (f["idx"] - 1) % len(f["opts"]); return True
            if nxt.collidepoint(mx, my):
                f["idx"] = (f["idx"] + 1) % len(f["opts"]); return True
        return True   # clic hors boutons = on reste

    @property
    def result(self) -> dict:
        d = {"type": self.etype}
        for f in self.fields:
            d[f["label"].lower().split()[0]] = f["opts"][f["idx"]]
        # normalise les clés en anglais
        if "arme" in d:    d["weapon"] = d.pop("arme")
        if "patrouille" in d: d["patrol"] = d.pop("patrouille")
        return d

    def draw(self, surf: pygame.Surface):
        # Fond semi-transparent
        ov = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160)); surf.blit(ov, (0,0))

        box = pygame.Surface((self.w, self.h))
        box.fill((26, 20, 40))
        pygame.draw.rect(box, COL_SEL, (0,0,self.w,self.h), 2)

        f_big  = pygame.font.SysFont("consolas", 15, bold=True)
        f_norm = self.font

        # Titre
        t = f_big.render(self.etype.replace("_"," ").upper(), True, COL_SEL)
        box.blit(t, (10, 12))

        # Champs
        for fi, f in enumerate(self.fields):
            fy = 50 + fi * 54
            box.blit(f_norm.render(f["label"] + ":", True, COL_DIM), (10, fy))
            val = f["opts"][f["idx"]]
            # < val >  (boutons)
            prev_r = pygame.Rect(10, fy+16, 32, 24)
            nxt_r  = pygame.Rect(self.w-42, fy+16, 32, 24)
            pygame.draw.rect(box, COL_BORDER, prev_r, border_radius=4)
            pygame.draw.rect(box, COL_BORDER, nxt_r,  border_radius=4)
            box.blit(f_norm.render("<", True, COL_SEL), (prev_r.x+9, prev_r.y+4))
            box.blit(f_norm.render(">", True, COL_SEL), (nxt_r.x+10, nxt_r.y+4))
            vs = f_big.render(val.upper(), True, COL_TEXT)
            box.blit(vs, (self.w//2 - vs.get_width()//2, fy+18))

        # Boutons OK / Annuler (relatifs au box)
        ok_r  = pygame.Rect(20,           self.h-44, (self.w-52)//2, 36)
        can_r = pygame.Rect(self.w//2+6,  self.h-44, (self.w-52)//2, 36)
        pygame.draw.rect(box, (0, 120, 100), ok_r,  border_radius=6)
        pygame.draw.rect(box, (100, 30, 50), can_r, border_radius=6)
        box.blit(f_big.render("OK", True, COL_TEXT),
                 (ok_r.centerx  - f_big.size("OK")[0]//2, ok_r.y+8))
        box.blit(f_big.render("Annuler", True, COL_TEXT),
                 (can_r.centerx - f_big.size("Annuler")[0]//2, can_r.y+8))

        surf.blit(box, (self.x, self.y))


# ── Données d'un niveau ───────────────────────────────────────────────────────
class LevelData:
    def __init__(self, w=DEFAULT_W, h=DEFAULT_H):
        self.w        = w
        self.h        = h
        self.tiles    = [[0]*w for _ in range(h)]
        self.entities: list[dict] = []
        self.name     = "untitled"
        self.path     = None

    def to_dict(self):
        return {"meta":{"name":self.name,"width":self.w,"height":self.h,
                        "tile_size":TILE,"version":2},
                "tiles":self.tiles,"entities":self.entities}

    @classmethod
    def from_dict(cls, d):
        m = d["meta"]
        lv = cls(m["width"], m["height"])
        lv.name     = m.get("name","untitled")
        lv.tiles    = [list(r) for r in d["tiles"]]
        lv.entities = list(d.get("entities",[]))
        return lv

    def save(self, path):
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path,"w") as f: json.dump(self.to_dict(), f, indent=2)
        self.path = path

    @classmethod
    def load(cls, path):
        with open(path) as f: d = json.load(f)
        lv = cls.from_dict(d); lv.path = path; return lv


# ── Utilitaires ───────────────────────────────────────────────────────────────
def bresenham(x0,y0,x1,y1):
    pts=[]; dx,dy=abs(x1-x0),abs(y1-y0)
    sx=1 if x0<x1 else -1; sy=1 if y0<y1 else -1; err=dx-dy
    while True:
        pts.append((x0,y0))
        if x0==x1 and y0==y1: break
        e2=2*err
        if e2>-dy: err-=dy; x0+=sx
        if e2<dx:  err+=dx; y0+=sy
    return pts

def flood_fill(tiles,gx,gy,val):
    rows,cols=len(tiles),len(tiles[0]) if tiles else 0
    if not(0<=gx<cols and 0<=gy<rows): return
    old=tiles[gy][gx]
    if old==val: return
    stk,vis=[(gx,gy)],set()
    while stk:
        cx,cy=stk.pop()
        if (cx,cy) in vis or not(0<=cx<cols and 0<=cy<rows): continue
        if tiles[cy][cx]!=old: continue
        vis.add((cx,cy)); tiles[cy][cx]=val
        stk+=[(cx+1,cy),(cx-1,cy),(cx,cy+1),(cx,cy-1)]


# ── Éditeur ───────────────────────────────────────────────────────────────────
class Editor:
    def __init__(self, open_path=None, embedded=False):
        self._embedded = embedded
        self._result: str | None = None

        if not embedded:
            pygame.init()
            self._screen = pygame.display.set_mode((1100, 620))
            pygame.display.set_caption("Neon Miami — Level Editor")
            self._clock  = pygame.time.Clock()
        else:
            self._screen = None

        self.font  = pygame.font.SysFont("consolas", 13)
        self.fontb = pygame.font.SysFont("consolas", 13, bold=True)
        self.fontL = pygame.font.SysFont("consolas", 15, bold=True)

        self._canvas: pygame.Surface | None = None
        self._csz = (0, 0)

        if open_path:
            self.lv = LevelData.load(open_path)
        else:
            self.lv = LevelData()
            self._make_starter()

        self.zoom   = 1.75
        self.pan_x  = 0.0
        self.pan_y  = 0.0

        self.pal_idx = 1          # Wall thin sélectionné par défaut
        self.tool    = "brush"    # brush | fill | erase | rect | line
        self.grid    = True

        self._drag0  = None       # (gx, gy) début drag rect/line
        self._drag1  = None
        self._panning = False
        self._pan0   = None

        self._undo: list = []
        self._redo: list = []
        self._sel_ent    = None
        self._popup: EntityPopup | None = None
        self._pending    = None   # (gx,gy) en attente de popup

        self._status = "Clic gauche = peindre | Clic droit = effacer | [H] aide"
        self._help   = False

        os.makedirs(LEVELS_DIR, exist_ok=True)

    # ── Carte de démarrage ────────────────────────────────────────────────────
    def _make_starter(self):
        w, h = self.lv.w, self.lv.h
        for c in range(w):
            self.lv.tiles[0][c]   = 2
            self.lv.tiles[h-1][c] = 2
        for r in range(h):
            self.lv.tiles[r][0]   = 2
            self.lv.tiles[r][w-1] = 2
        self.lv.entities.append({"type":"player_spawn","gx":w//2,"gy":h//2})

    # ── Dimensions dynamiques ─────────────────────────────────────────────────
    def _sw_sh(self, surface: pygame.Surface):
        return surface.get_size()

    def _cw_ch(self, sw, sh):
        return sw - PALETTE_W, sh - STATUS_H

    def _get_canvas(self, cw, ch):
        if self._csz != (cw, ch):
            self._canvas = pygame.Surface((cw, ch))
            self._csz    = (cw, ch)
        return self._canvas

    # ── Coordonnées ──────────────────────────────────────────────────────────
    def s2t(self, sx, sy):
        """Screen → tile (gx, gy)"""
        return int((sx/self.zoom + self.pan_x)//TILE), \
               int((sy/self.zoom + self.pan_y)//TILE)

    def t2c(self, gx, gy):
        """Tile → canvas pixel (top-left)"""
        return int((gx*TILE - self.pan_x)*self.zoom), \
               int((gy*TILE - self.pan_y)*self.zoom)

    def tpx(self):
        return max(2, int(TILE * self.zoom))

    def valid(self, gx, gy):
        return 0 <= gx < self.lv.w and 0 <= gy < self.lv.h

    # ── Undo ──────────────────────────────────────────────────────────────────
    def _push(self):
        self._undo.append((copy.deepcopy(self.lv.tiles),
                           copy.deepcopy(self.lv.entities)))
        if len(self._undo) > UNDO_LIMIT: self._undo.pop(0)
        self._redo.clear()

    def _undo_step(self):
        if not self._undo: return
        self._redo.append((copy.deepcopy(self.lv.tiles),
                           copy.deepcopy(self.lv.entities)))
        t, e = self._undo.pop(); self.lv.tiles = t; self.lv.entities = e
        self._status = "Annulé"

    def _redo_step(self):
        if not self._redo: return
        self._undo.append((copy.deepcopy(self.lv.tiles),
                           copy.deepcopy(self.lv.entities)))
        t, e = self._redo.pop(); self.lv.tiles = t; self.lv.entities = e
        self._status = "Rétabli"

    # ── Tile value helpers ────────────────────────────────────────────────────
    def _tile_val(self):
        p = PALETTE[self.pal_idx]
        return p.value if p.kind == "tile" else 0

    def _paint(self, gx, gy, val):
        if self.valid(gx, gy):
            self.lv.tiles[gy][gx] = val

    def _entity_at(self, gx, gy):
        for e in self.lv.entities:
            if e["gx"]==gx and e["gy"]==gy: return e
        return None

    def _place_entity(self, gx, gy, etype, props=None):
        if not self.valid(gx, gy): return
        if etype in ("player_spawn","exit_trigger"):
            self.lv.entities = [e for e in self.lv.entities
                                 if e["type"] != etype]
        ent = {"type":etype,"gx":gx,"gy":gy}
        if props: ent.update(props)
        self.lv.entities.append(ent)

    # ── Fichiers ──────────────────────────────────────────────────────────────
    def _save(self):
        path = self.lv.path or os.path.join(LEVELS_DIR, self.lv.name+".json")
        self.lv.save(path)
        self._status = f"Sauvegarde : {os.path.basename(path)}"

    def _test(self):
        self._save()
        path = self.lv.path or os.path.join(LEVELS_DIR,"current.json")
        if self._embedded:
            self._result = f"test:{path}"
        else:
            mp = os.path.join(os.path.dirname(__file__), "main.py")
            subprocess.Popen([sys.executable, mp, "--level", path])

    # ── API embarquée ─────────────────────────────────────────────────────────
    def handle_event(self, ev) -> str | None:
        self._result = None
        if self._popup:
            if ev.type == pygame.KEYDOWN:
                if not self._popup.handle_key(ev):
                    self._close_popup()
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if not self._popup.handle_click(ev.pos):
                    self._close_popup()
            return self._result
        self._ev(ev)
        return self._result

    def _close_popup(self):
        p = self._popup; self._popup = None
        if p and p.confirmed and self._pending:
            gx, gy = self._pending
            self._push()
            self._place_entity(gx, gy, p.etype, p.result)
            self._status = f"Entité {p.etype} placée en ({gx},{gy})"
        self._pending = None

    def draw(self, surface: pygame.Surface):
        sw, sh = self._sw_sh(surface)
        cw, ch = self._cw_ch(sw, sh)
        canvas  = self._get_canvas(cw, ch)
        self._draw_all(surface, canvas, sw, sh, cw, ch)

    # ── Boucle standalone ─────────────────────────────────────────────────────
    def run(self):
        running = True
        while running:
            self._clock.tick(60)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT: running = False; break
                r = self.handle_event(ev)
                if r == "quit":   running = False; break
                if r and r.startswith("test:"):
                    mp = os.path.join(os.path.dirname(__file__),"main.py")
                    subprocess.Popen([sys.executable,mp,"--level",r[5:]])
            if running:
                self.draw(self._screen)
                pygame.display.flip()
        pygame.quit()

    # ── Gestion événements ────────────────────────────────────────────────────
    def _ev(self, ev):
        if ev.type == pygame.KEYDOWN:        self._key(ev); return
        if ev.type == pygame.MOUSEWHEEL:     self._wheel(ev); return
        if ev.type == pygame.MOUSEBUTTONDOWN:self._mdown(ev)
        elif ev.type == pygame.MOUSEBUTTONUP:self._mup(ev)
        elif ev.type == pygame.MOUSEMOTION:  self._mmove(ev)

    def _key(self, ev):
        ctrl = ev.mod & pygame.KMOD_CTRL
        if ev.key == pygame.K_ESCAPE:  self._result = "quit"; return
        if ev.key == pygame.K_h:       self._help = not self._help; return
        if ev.key == pygame.K_g:       self.grid   = not self.grid; return
        if ev.key == pygame.K_F5:      self._test(); return
        if ctrl and ev.key == pygame.K_s: self._save(); return
        if ctrl and ev.key == pygame.K_z: self._undo_step(); return
        if ctrl and ev.key == pygame.K_y: self._redo_step(); return
        if ev.key == pygame.K_DELETE:
            if self._sel_ent and self._sel_ent in self.lv.entities:
                self._push(); self.lv.entities.remove(self._sel_ent)
                self._sel_ent = None
                self._status  = "Entité supprimée"; return

        # Numéros → palette
        nums = {pygame.K_1:0,pygame.K_2:1,pygame.K_3:2,pygame.K_4:3,
                pygame.K_5:4,pygame.K_6:5,pygame.K_7:6,pygame.K_8:7}
        if ev.key in nums:
            self.pal_idx = min(nums[ev.key], len(PALETTE)-1)
            p = PALETTE[self.pal_idx]
            self.tool    = "entity" if p.kind=="entity" else "brush"
            self._status = f"Sélectionné : {p.label}"
            return

        # Outils
        t_map = {pygame.K_b:"brush",pygame.K_f:"fill",
                 pygame.K_e:"erase",pygame.K_r:"rect",pygame.K_l:"line"}
        if ev.key in t_map:
            self.tool = t_map[ev.key]
            self._status = f"Outil : {self.tool}"

    def _wheel(self, ev):
        mx, my = pygame.mouse.get_pos()
        old = self.zoom
        self.zoom = max(0.5, min(6.0, self.zoom + ev.y * 0.20))
        wx = mx/old + self.pan_x; wy = my/old + self.pan_y
        self.pan_x = wx - mx/self.zoom
        self.pan_y = wy - my/self.zoom

    def _mdown(self, ev):
        mx, my = ev.pos
        # On a besoin de cw pour distinguer canvas vs palette
        # On utilise le dernier canvas connu (ou la surface du jeu)
        cw = self._csz[0] if self._csz[0] else 800
        ch = self._csz[1] if self._csz[1] else 540

        # Clic molette → pan
        if ev.button == 2:
            self._panning = True; self._pan0 = (mx, my); return

        # Clic dans la palette
        if mx >= cw:
            self._pal_click(my); return
        if my >= ch: return   # barre de statut

        gx, gy = self.s2t(mx, my)

        # Clic droit → effacer
        if ev.button == 3:
            self._push(); self._paint(gx, gy, 0)
            self._status = f"Effacé ({gx},{gy})"; return

        if ev.button != 1: return

        # Shift + clic → pipette
        if pygame.key.get_mods() & pygame.KMOD_SHIFT:
            if self.valid(gx, gy):
                val = self.lv.tiles[gy][gx]
                for i, p in enumerate(PALETTE):
                    if p.kind=="tile" and p.value==val:
                        self.pal_idx = i; self.tool = "brush"
                        self._status = f"Pipette : {p.label}"; break
            return

        p = PALETTE[self.pal_idx]

        # --- Mode entité ---
        if p.kind == "entity" or self.tool == "entity":
            etype = p.value if p.kind == "entity" else None
            if etype is None: return
            ex = self._entity_at(gx, gy)
            if ex:
                self._sel_ent = ex
                self._status  = f"Entité sélectionnée : {ex['type']} (Suppr pour effacer)"
                return
            if etype in ("enemy","weapon_pickup"):
                sw_full = cw + PALETTE_W
                sh_full = ch + STATUS_H
                self._pending = (gx, gy)
                self._popup   = EntityPopup(etype, self.font, sw_full, sh_full)
                self._status  = "Configurez puis cliquez OK"
            else:
                self._push(); self._place_entity(gx, gy, etype)
                self._status = f"Placé : {etype} en ({gx},{gy})"
            return

        # --- Mode fill ---
        if self.tool == "fill":
            self._push(); flood_fill(self.lv.tiles, gx, gy, self._tile_val())
            self._status = f"Remplissage {TILE_NAME.get(self._tile_val(),'')} en ({gx},{gy})"; return

        # --- Mode rect / line → début drag ---
        if self.tool in ("rect","line"):
            self._drag0 = (gx, gy); self._drag1 = (gx, gy); return

        # --- Mode brush / erase ---
        if self.tool in ("brush","erase"):
            self._push()
            val = 0 if self.tool == "erase" else self._tile_val()
            self._paint(gx, gy, val)
            self._status = f"Posé : {TILE_NAME.get(val,'?')} en ({gx},{gy})"

    def _mup(self, ev):
        if ev.button == 2: self._panning = False; return
        if ev.button == 1 and self._drag0 and self._drag1:
            self._push()
            self._commit_drag(*self._drag0, *self._drag1)
            n = TILE_NAME.get(self._tile_val(),"?")
            self._status = f"Zone {self.tool} : {n}"
            self._drag0 = self._drag1 = None

    def _mmove(self, ev):
        mx, my = ev.pos
        cw, ch = self._csz

        if self._panning and self._pan0:
            dx = (mx - self._pan0[0]) / self.zoom
            dy = (my - self._pan0[1]) / self.zoom
            self.pan_x -= dx; self.pan_y -= dy
            self._pan0 = (mx, my)

        if cw == 0: return

        if 0 <= mx < cw and 0 <= my < ch:
            btn = pygame.mouse.get_pressed()
            if btn[0]:   # LMB tenu
                gx, gy = self.s2t(mx, my)
                if self.tool in ("brush","erase"):
                    val = 0 if self.tool == "erase" else self._tile_val()
                    self._paint(gx, gy, val)
                elif self.tool in ("rect","line") and self._drag0:
                    self._drag1 = (gx, gy)
            if btn[2]:   # RMB tenu → erase
                gx, gy = self.s2t(mx, my)
                self._paint(gx, gy, 0)

            gx, gy = self.s2t(mx, my)
            if self.valid(gx, gy):
                tid   = self.lv.tiles[gy][gx]
                pname = PALETTE[self.pal_idx].label
                self._status = (f"({gx},{gy}) {TILE_NAME.get(tid,'?')}  |  "
                                f"outil:{self.tool}  palette:{pname}  "
                                f"zoom:{self.zoom:.1f}x")

    def _commit_drag(self, x0, y0, x1, y1):
        val = self._tile_val()
        if self.tool == "rect":
            for r in range(min(y0,y1), max(y0,y1)+1):
                for c in range(min(x0,x1), max(x0,x1)+1):
                    self._paint(c, r, val)
        elif self.tool == "line":
            for gx, gy in bresenham(x0,y0,x1,y1):
                self._paint(gx, gy, val)

    def _pal_click(self, my):
        idx = (my - PAL_Y0) // PAL_H
        if 0 <= idx < len(PALETTE):
            self.pal_idx = idx
            p = PALETTE[idx]
            self.tool    = "entity" if p.kind == "entity" else "brush"
            self._status = f"Sélectionné : {p.label}"

    # ── Dessin ────────────────────────────────────────────────────────────────
    def _draw_all(self, surf, canvas, sw, sh, cw, ch):
        surf.fill(COL_BG)
        self._draw_canvas(canvas, cw, ch)
        surf.blit(canvas, (0, 0))
        self._draw_palette(surf, cw, sh)
        self._draw_status(surf, sw, sh)
        if self._popup:
            self._popup.draw(surf)
        if self._help:
            self._draw_help(surf, sw, sh)

    def _draw_canvas(self, c, cw, ch):
        c.fill(COL_BG)
        ts = self.tpx()
        lv = self.lv

        # Tiles
        for gy in range(lv.h):
            for gx in range(lv.w):
                sx, sy = self.t2c(gx, gy)
                if sx+ts<0 or sx>cw or sy+ts<0 or sy>ch: continue
                col = TILE_COLOR.get(lv.tiles[gy][gx], TILE_COLOR[0])
                pygame.draw.rect(c, col, (sx, sy, ts, ts))

        # Grille
        if self.grid and ts >= 5:
            for gy in range(lv.h+1):
                sy = int((gy*TILE - self.pan_y)*self.zoom)
                if 0<=sy<=ch: pygame.draw.line(c, COL_GRID,(0,sy),(cw,sy))
            for gx in range(lv.w+1):
                sx = int((gx*TILE - self.pan_x)*self.zoom)
                if 0<=sx<=cw: pygame.draw.line(c, COL_GRID,(sx,0),(sx,ch))

        # Entités
        for ent in lv.entities:
            sx, sy = self.t2c(ent["gx"], ent["gy"])
            if sx+ts<0 or sx>cw or sy+ts<0 or sy>ch: continue
            col = ENTITY_COLOR.get(ent["type"],(200,200,200))
            r   = max(5, ts//2 - 1)
            cx2 = sx + ts//2; cy2 = sy + ts//2
            pygame.draw.circle(c, col, (cx2,cy2), r)
            pygame.draw.circle(c, (0,0,0), (cx2,cy2), r, 1)
            if ent is self._sel_ent:
                pygame.draw.circle(c, COL_SEL, (cx2,cy2), r+3, 2)

        # Aperçu drag
        if self._drag0 and self._drag1 and self.tool in ("rect","line"):
            x0,y0=self._drag0; x1,y1=self._drag1
            if self.tool=="rect":
                sx0,sy0=self.t2c(min(x0,x1),min(y0,y1))
                sx1,sy1=self.t2c(max(x0,x1)+1,max(y0,y1)+1)
                pygame.draw.rect(c,COL_SEL,(sx0,sy0,sx1-sx0,sy1-sy0),2)
            else:
                for gx,gy in bresenham(x0,y0,x1,y1):
                    sx,sy=self.t2c(gx,gy)
                    pygame.draw.rect(c,COL_SEL,(sx,sy,ts,ts),1)

        # Hover
        mx, my = pygame.mouse.get_pos()
        if 0<=mx<cw and 0<=my<ch:
            gx,gy = self.s2t(mx,my)
            sx,sy = self.t2c(gx,gy)
            pygame.draw.rect(c, COL_SEL, (sx,sy,ts,ts), 2)

    def _draw_palette(self, s, px, sh):
        ch = sh - STATUS_H
        pygame.draw.rect(s, COL_PANEL, (px, 0, PALETTE_W, ch))
        pygame.draw.line(s, COL_BORDER, (px,0),(px,ch))

        s.blit(self.fontb.render("PALETTE", True, COL_SEL), (px+6, 10))

        for i, p in enumerate(PALETTE):
            y   = PAL_Y0 + i * PAL_H
            sel = (i == self.pal_idx)
            bg  = (40,36,60) if sel else COL_PANEL
            pygame.draw.rect(s, bg, (px+2, y, PALETTE_W-4, PAL_H-2),
                             border_radius=3)
            if sel:
                pygame.draw.rect(s, COL_SEL,(px+2,y,PALETTE_W-4,PAL_H-2),1,3)
            # Swatch couleur
            col = TILE_COLOR[p.value] if p.kind=="tile" \
                  else ENTITY_COLOR.get(p.value,(180,180,180))
            pygame.draw.rect(s, col, (px+7, y+10, 14, 14))
            # Label
            tcol = COL_SEL if sel else COL_TEXT
            s.blit(self.font.render(f"[{i+1}] {p.label}", True, tcol),
                   (px+27, y+10))

        # Séparateur + infos outils
        yt = PAL_Y0 + len(PALETTE)*PAL_H + 8
        pygame.draw.line(s, COL_BORDER, (px+4,yt),(px+PALETTE_W-4,yt))
        yt += 6
        s.blit(self.fontb.render("OUTILS", True, COL_SEL),(px+6,yt)); yt+=18
        for k,lb in [("B","Pinceau"),("F","Remplissage"),("E","Gomme"),
                      ("R","Rectangle"),("L","Ligne")]:
            tc = COL_SEL if self.tool.lower()==lb.lower()[:len(self.tool)] \
                         and self.tool!="brush" and lb=="Pinceau" \
                         or self.tool=="brush" and lb=="Pinceau" \
                         or self.tool=="fill" and lb=="Remplissage" \
                         or self.tool=="erase" and lb=="Gomme" \
                         or self.tool=="rect" and lb=="Rectangle" \
                         or self.tool=="line" and lb=="Ligne" \
                         else COL_DIM
            s.blit(self.font.render(f"[{k}] {lb}", True, tc),(px+6,yt)); yt+=16

        yt += 6
        pygame.draw.line(s, COL_BORDER, (px+4,yt),(px+PALETTE_W-4,yt)); yt+=6
        for line in ["[G] Grille","[Ctrl+S] Sauv.","[Ctrl+Z] Annuler",
                     "[F5] Tester","[Echap] Retour","[H] Aide"]:
            s.blit(self.font.render(line, True, COL_DIM),(px+6,yt)); yt+=16

    def _draw_status(self, s, sw, sh):
        y = sh - STATUS_H
        pygame.draw.rect(s, COL_STATUS, (0, y, sw, STATUS_H))
        pygame.draw.line(s, COL_BORDER,(0,y),(sw,y))
        name = os.path.basename(self.lv.path) if self.lv.path \
               else self.lv.name+".json"
        txt = self.fontb.render(f" {name}  |  {self._status}", True, COL_TEXT)
        s.blit(txt, (4, y + (STATUS_H - txt.get_height())//2))

    def _draw_help(self, s, sw, sh):
        lines = [
            "=== AIDE EDITEUR ===",
            "1–8      Choisir tile / entité",
            "B        Pinceau (maintenir = tracer)",
            "F        Remplissage",
            "E        Gomme",
            "R        Rectangle (drag)",
            "L        Ligne (drag)",
            "G        Afficher/cacher grille",
            "Clic G   Peindre tile actif",
            "Clic D   Effacer tile",
            "Shift+G  Pipette (copier tile)",
            "Molette  Zoom",
            "Molette  Pan (déplacer vue)",
            "Suppr    Supprimer entité cliquée",
            "Ctrl+Z/Y Annuler / Rétablir",
            "Ctrl+S   Sauvegarder",
            "F5       Tester en jeu",
            "Echap    Retour au menu",
            "H        Fermer l'aide",
        ]
        w=340; h=len(lines)*18+20
        ox=(sw-w)//2; oy=(sh-h)//2
        ov=pygame.Surface((w,h),pygame.SRCALPHA)
        ov.fill((18,14,30,230))
        pygame.draw.rect(ov,COL_SEL,(0,0,w,h),2)
        for i,l in enumerate(lines):
            ov.blit(self.font.render(l, True, COL_SEL if i==0 else COL_TEXT),
                    (10,10+i*18))
        s.blit(ov,(ox,oy))


# ── Standalone ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    Editor(sys.argv[1] if len(sys.argv)>1 else None, embedded=False).run()
