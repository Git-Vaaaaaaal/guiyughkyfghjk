# -*- coding: utf-8 -*-
# ui.py – all screen overlays: title, HUD, score, game-over, scanlines
import pygame
import math
import random
import time
from constants import *


# ── Font helpers ──────────────────────────────────────────────────────────────
_fonts: dict = {}

def _font(name: str = "Courier New", size: int = 16, bold: bool = True):
    key = (name, size, bold)
    if key not in _fonts:
        _fonts[key] = pygame.font.SysFont(name, size, bold=bold)
    return _fonts[key]


def _txt(text: str, size: int, color, bold: bool = True) -> pygame.Surface:
    return _font(size=size, bold=bold).render(text, True, color)


# ── Scanline overlay (created once, reused) ───────────────────────────────────
_scanlines: pygame.Surface | None = None

def _get_scanlines(w: int, h: int) -> pygame.Surface:
    global _scanlines
    if _scanlines is None or _scanlines.get_size() != (w, h):
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 3):
            pygame.draw.line(surf, (0, 0, 0, 38), (0, y), (w, y))
        _scanlines = surf
    return _scanlines


# ── Flash surface ─────────────────────────────────────────────────────────────
class ScreenFlash:
    """One-frame full-screen colour flash on kills / player death."""

    def __init__(self):
        self._timer = 0
        self._color = COL_MAGENTA

    def trigger(self, color=None, frames: int = 4):
        self._color = color or COL_MAGENTA
        self._timer = frames

    def update(self):
        if self._timer > 0:
            self._timer -= 1

    def render(self, surface: pygame.Surface):
        if self._timer <= 0:
            return
        alpha = int(120 * self._timer / 4)
        fl = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        fl.fill((*self._color, alpha))
        surface.blit(fl, (0, 0))


# ── HUD ───────────────────────────────────────────────────────────────────────
def render_hud(surface: pygame.Surface,
               weapon: int, room_name: str,
               enemies_left: int, level_idx: int):
    w, h = surface.get_size()

    # Weapon icon – bottom-left
    col  = WEAPON_COLORS.get(weapon, COL_WHITE)
    name = WEAPON_NAMES.get(weapon, "???")

    pygame.draw.rect(surface, (15, 15, 25),
                     pygame.Rect(8, h - 50, 130, 38), border_radius=4)
    pygame.draw.rect(surface, col,
                     pygame.Rect(8, h - 50, 130, 38), 1, border_radius=4)

    icon = _txt(f"[ {name} ]", 14, col)
    surface.blit(icon, (16, h - 42))

    # Room name – top-centre
    room_surf = _txt(room_name, 13, COL_CYAN)
    surface.blit(room_surf, (w // 2 - room_surf.get_width() // 2, 10))

    # Level indicator – top-left
    lv_surf = _txt(f"LV {level_idx + 1}", 12, COL_AMBER)
    surface.blit(lv_surf, (10, 10))

    # Enemies remaining – top-right
    en_surf = _txt(f"{enemies_left:02d} TARGETS", 12, COL_MAGENTA)
    surface.blit(en_surf, (w - en_surf.get_width() - 10, 10))

    # Controls hint (very faint, bottom-right)
    hint = _txt("LMB shoot  RMB melee  F throw  E pickup", 10,
                (60, 60, 80), bold=False)
    surface.blit(hint, (w - hint.get_width() - 8, h - 16))


# ── Scanlines ─────────────────────────────────────────────────────────────────
def render_scanlines(surface: pygame.Surface):
    surface.blit(_get_scanlines(*surface.get_size()), (0, 0))


# ── Title screen ──────────────────────────────────────────────────────────────
_ASCII_LOGO = [
    "  ██████╗██╗   ██╗██████╗ ███████╗██████╗ ",
    " ██╔════╝╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗",
    " ██║      ╚████╔╝ ██████╔╝█████╗  ██████╔╝",
    " ██║       ╚██╔╝  ██╔══██╗██╔══╝  ██╔══██╗",
    " ╚██████╗   ██║   ██████╔╝███████╗██║  ██║",
    "  ╚═════╝   ╚═╝   ╚═════╝ ╚══════╝╚═╝  ╚═╝",
    "",
    "        N E O N   H O M I C I D E",
]


def render_title(surface: pygame.Surface, elapsed: float):
    w, h = surface.get_size()
    surface.fill(COL_BG)

    # Animated scanline colour shift
    t = elapsed
    shift = int((math.sin(t * 1.3) + 1) * 0.5 * 80)
    logo_col = (0, 200 + shift, 180)

    # ASCII logo
    for i, line in enumerate(_ASCII_LOGO):
        lx = i * 0.15       # slight stagger phase
        alpha_mod = int((math.sin(t * 2 + lx) + 1) * 0.5 * 40) + 180
        col = (logo_col[0], min(255, logo_col[1]),
               min(255, logo_col[2] + shift // 2))
        surf = _txt(line, 14, col)
        y    = h // 4 + i * 20
        surface.blit(surf, (w // 2 - surf.get_width() // 2, y))

    # Blinking "PRESS ENTER" prompt
    if int(t * 2) % 2 == 0:
        p = _txt("[ PRESS ENTER TO EXECUTE ]", 16, COL_AMBER)
        surface.blit(p, (w // 2 - p.get_width() // 2, h * 3 // 4))

    # Subtitle
    sub = _txt("wasd/zqsd · mouse aim · lmb fire · rmb melee · f throw · e pickup",
               11, (80, 80, 110), bold=False)
    surface.blit(sub, (w // 2 - sub.get_width() // 2, h * 3 // 4 + 36))

    # Fake terminal flicker
    if random.random() < 0.015:
        fl = pygame.Surface((w, 2), pygame.SRCALPHA)
        fl.fill((0, 255, 229, 30))
        surface.blit(fl, (0, random.randint(0, h)))

    render_scanlines(surface)


# ── Score screen ──────────────────────────────────────────────────────────────
def render_score(surface: pygame.Surface,
                 kills: int, variety: int,
                 elapsed: float, level_idx: int):
    w, h = surface.get_size()
    surface.fill(COL_BG)

    title = _txt("// MISSION COMPLETE //", 28, COL_CYAN)
    surface.blit(title, (w // 2 - title.get_width() // 2, h // 4))

    style_score = kills * 100 + variety * 250
    rows = [
        ("KILLS",      str(kills),         COL_MAGENTA),
        ("VARIETY",    f"{variety} TYPES",  COL_AMBER),
        ("TIME",       f"{elapsed:.1f}s",   COL_WHITE),
        ("STYLE",      str(style_score),    COL_CYAN),
    ]
    for i, (label, val, col) in enumerate(rows):
        y = h // 2 - 40 + i * 38
        ls = _txt(f"{label:<12}", 18, (100, 100, 130))
        vs = _txt(val, 22, col)
        surface.blit(ls, (w // 2 - 160, y))
        surface.blit(vs, (w // 2 + 20,  y))

    blink = _txt("[ PRESS ENTER TO CONTINUE ]", 15, COL_AMBER)
    surface.blit(blink, (w // 2 - blink.get_width() // 2, h * 4 // 5))
    render_scanlines(surface)


# ── Game-over screen ──────────────────────────────────────────────────────────
def render_gameover(surface: pygame.Surface, elapsed: float):
    w, h = surface.get_size()
    surface.fill(COL_BG)

    # Glitch flicker
    if random.random() < 0.3:
        off = random.randint(-3, 3)
    else:
        off = 0

    title = _txt("// YOU DIED //", 36, COL_MAGENTA)
    surface.blit(title, (w // 2 - title.get_width() // 2 + off, h // 3))

    sub = _txt("NEURAL LINK SEVERED", 16, (160, 40, 80))
    surface.blit(sub, (w // 2 - sub.get_width() // 2, h // 3 + 50))

    if int(elapsed * 2) % 2 == 0:
        p = _txt("[ R — RETRY ROOM    ESC — TITLE ]", 15, COL_AMBER)
        surface.blit(p, (w // 2 - p.get_width() // 2, h * 2 // 3))

    render_scanlines(surface)


# ── Settings screen ────────────────────────────────────────────────────────────
def render_settings(surface: pygame.Surface,
                    settings,
                    cursor: int,
                    rebinding: bool,
                    from_game: bool = False):
    from settings import RESOLUTIONS, KEY_LABELS
    w, h = surface.get_size()
    surface.fill(COL_BG)

    title = _txt("// SETTINGS //", 26, COL_CYAN)
    surface.blit(title, (w // 2 - title.get_width() // 2, 26))

    res_str = "{}x{}".format(*RESOLUTIONS[settings.resolution_idx])
    rows = [
        ("RESOLUTION",  res_str,
         "x".join(""),  COL_AMBER),
        ("FULLSCREEN",  "ON" if settings.fullscreen else "OFF",   "", COL_AMBER),
        ("MUSIC VOL",   f"{int(settings.music_vol * 100):3d}%",   "", COL_AMBER),
    ]
    for action, label in KEY_LABELS.items():
        k = settings.keys[action]
        rows.append((label, pygame.key.name(k).upper(), action, COL_CYAN))

    start_y = 90
    row_h   = 34
    lx      = w // 2 - 200
    rx      = w // 2 + 30

    for i, (label, val, _action, col) in enumerate(rows):
        y      = start_y + i * row_h
        is_sel = (i == cursor)
        lcol   = COL_WHITE if is_sel else (70, 70, 105)

        if is_sel:
            surface.blit(_txt(">", 18, COL_MAGENTA), (lx - 22, y))

        surface.blit(_txt(f"{label:<18}", 16, lcol), (lx, y))

        if is_sel and rebinding and i >= 3:
            vsrf = _txt("[ PRESS KEY ]", 16, COL_MAGENTA)
        else:
            vsrf = _txt(val, 16, col if is_sel else (55, 55, 88))
        surface.blit(vsrf, (rx, y))

    back = "ESC back to game" if from_game else "ESC back to title"
    hint = ("↑↓ select   ←→ change value   ENTER rebind key   " + back
            if not rebinding else "Press any key…  ESC cancel")
    hs = _txt(hint, 10, (55, 55, 88), bold=False)
    surface.blit(hs, (w // 2 - hs.get_width() // 2, h - 22))

    render_scanlines(surface)
