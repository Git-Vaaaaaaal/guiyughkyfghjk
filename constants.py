# Shared constants — every module imports this

SCREEN_W = 960
SCREEN_H = 540
FPS      = 60
TILE     = 16          # px per tile (was 32 — 16 gives apartment scale)

# ── Internal viewport (rendered at half-res, upscaled ×2) ────────────────────
VIEW_W   = 480
VIEW_H   = 270

# ── Cyberpunk palette ─────────────────────────────────────────────────────────
COL_BG        = ( 10,  10,  15)
COL_CYAN      = (  0, 255, 229)
COL_MAGENTA   = (255,  42, 109)
COL_AMBER     = (255, 159,  28)
COL_WHITE     = (220, 220, 220)
COL_WALL      = ( 15,  15,  25)   # thin wall
COL_WALL_STR  = ( 38,  30,  48)   # structural wall (concrete-ish)
COL_FLOOR     = ( 18,  18,  28)
COL_GRID      = ( 28,  28,  45)
COL_BLOOD     = (160,  15,  35)
COL_PLAYER    = (  0, 200, 180)
COL_E_PATROL  = (255,  60, 100)
COL_E_ALERT   = (255, 160,   0)
COL_E_COMBAT  = (255,  20,  20)

# ── Weapon IDs ────────────────────────────────────────────────────────────────
W_NONE    = 0
W_PISTOL  = 1
W_SHOTGUN = 2
W_BAT     = 3
W_KATANA  = 4

WEAPON_NAMES = {
    W_NONE:    "FISTS",
    W_PISTOL:  "PISTOL",
    W_SHOTGUN: "SHOTGUN",
    W_BAT:     "BAT",
    W_KATANA:  "KATANA",
}
WEAPON_COLORS = {
    W_NONE:    COL_WHITE,
    W_PISTOL:  COL_CYAN,
    W_SHOTGUN: COL_AMBER,
    W_BAT:     COL_WHITE,
    W_KATANA:  COL_MAGENTA,
}
RANGED = {W_PISTOL, W_SHOTGUN}
MELEE  = {W_NONE, W_BAT, W_KATANA}

# ── Enemy AI states ───────────────────────────────────────────────────────────
ST_PATROL = 0
ST_ALERT  = 1
ST_COMBAT = 2

# ── Top-level game states ─────────────────────────────────────────────────────
GS_TITLE    = 0
GS_PLAYING  = 1
GS_SCORE    = 2
GS_GAMEOVER = 3
GS_SETTINGS = 4
GS_EDITOR   = 5

# ── Pymunk collision categories ───────────────────────────────────────────────
CAT_WALL    = 1 << 0
CAT_RAGDOLL = 1 << 1
CAT_ITEM    = 1 << 2

# ── Player physics ────────────────────────────────────────────────────────────
ACCEL    = 1400    # px/s²
FRICTION = 8.0     # lerp factor when no key pressed
MAX_SPD  = 190     # px/s cap

# ── Dash ──────────────────────────────────────────────────────────────────────
DASH_SPD = 480     # impulse px/s
DASH_DUR = 0.12    # seconds of forced movement
DASH_CD  = 0.80    # cooldown seconds

# ── Camera ────────────────────────────────────────────────────────────────────
CAM_SMOOTH   = 6.0    # lerp factor
CAM_LOOKAHEAD = 0.28  # fraction of (mouse - center) added as look-ahead

# ── Destructible walls ────────────────────────────────────────────────────────
HP_THIN       = 2    # '#' thin wall
HP_STRUCTURAL = 999  # '=' outer structural — indestructible in practice
