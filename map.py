# map.py – apartment level, tile rendering, wall HP, camera
import pygame
import constants   # access via module so resolution/tile changes apply


# ── Grid builder ──────────────────────────────────────────────────────────────
def _build(w: int, h: int,
           floors: list,       # [(r1,c1,r2,c2) inclusive]
           entities: list,     # [(row,col,char)]
           obstacles: list = None   # [(row,col)] thin-wall obstacles in rooms
           ) -> list:
    """Start all tiles as '#'; fill room rects as floor; stamp entities."""
    g = [['=' if (r < 2 or r >= h - 2 or c < 2 or c >= w - 2)
          else '#'
          for c in range(w)]
         for r in range(h)]
    for r1, c1, r2, c2 in floors:
        for r in range(max(0, r1), min(h, r2 + 1)):
            for c in range(max(0, c1), min(w, c2 + 1)):
                g[r][c] = '.'
    if obstacles:
        for r, c in obstacles:
            if 0 <= r < h and 0 <= c < w:
                g[r][c] = '#'   # thin wall re-inserted inside room
    for row, col, ch in entities:
        if 0 <= row < h and 0 <= col < w:
            g[row][col] = ch
    return [''.join(row) for row in g]


def _wp(col: int, row: int) -> tuple:
    T = constants.TILE
    return (col * T + T // 2, row * T + T // 2)


# ── Apartment level ───────────────────────────────────────────────────────────
def _apartment():
    """
    60 × 38 tiles at TILE=16 px → 960 × 608 px world.
    Layout (all rects inclusive):

    ENTRANCE HALL  rows 2-10, cols 2-8
    LIVING ROOM    rows 2-13, cols 9-27   (open to entrance)
    BALCONY        rows 2-9,  cols 29-57
    SERVER ROOM    rows 11-13,cols 29-57
    CORRIDOR       rows 14-16,cols 2-57
    BEDROOM 1      rows 17-35,cols 2-11
    BEDROOM 2      rows 17-26,cols 13-22
    BATHROOM       rows 17-26,cols 24-29
    KITCHEN        rows 28-35,cols 13-29
    OFFICE         rows 17-35,cols 31-57
    """
    W, H = 60, 38

    floors = [
        # Upper rooms
        (2,  2, 10,  8),    # Entrance hall
        (2,  9, 13, 27),    # Living room (open to entrance — cols adjoin)
        (2, 29,  9, 57),    # Balcony
        (11,29, 13, 57),    # Server room
        # Main corridor
        (14, 2, 16, 57),
        # Bottom rooms
        (17, 2, 35, 11),    # Bedroom 1
        (17,13, 26, 22),    # Bedroom 2
        (17,24, 26, 29),    # Bathroom
        (28,13, 35, 29),    # Kitchen
        (17,31, 35, 57),    # Office / security room
        # ── Doors / connections (1-2 tile floor gaps through walls) ────────────
        # Entrance → Corridor (entrance ends r10, corridor starts r14 → need bridge)
        (11, 4, 13,  5),    # narrow passage cols 4-5 rows 11-13
        # Balcony → Server room (gap at row 10)
        (10,38, 10, 44),
        # Bedroom 2 → Bathroom (gap at col 23)
        (21,23, 22, 23),
        # Bedroom 1 → Bedroom 2 (gap at col 12)
        (22,12, 23, 12),
        # Bedroom 2 → Kitchen (gap at row 27, cols 16-18)
        (27,16, 27, 18),
        # Kitchen → Office (gap at col 30)
        (31,30, 32, 30),
    ]

    # Obstacles: thin '#' walls re-inserted inside floor areas
    #   Kitchen counter (L-shape)
    kitchen_counter = [
        (29,14),(29,15),(29,16),(29,17),(29,18),(29,19),  # horizontal
        (30,19),(31,19),                                   # vertical leg
    ]
    #   Server racks in office (4 rows of 3)
    server_racks = [
        (19,33),(19,34),(19,35),
        (23,40),(23,41),(23,42),
        (27,46),(27,47),(27,48),
        (31,33),(31,34),(31,35),
    ]
    obstacles = kitchen_counter + server_racks

    entities = [
        # Player start (entrance)
        ( 5,  4, 'P'),
        # Entrance guard
        ( 8,  6, 'E'),
        # Living room — 2 enemies
        ( 5, 15, 'E'),
        ( 9, 23, 'S'),
        # Corridor mobiles — 2 enemies
        (15, 10, 'E'),
        (15, 45, 'E'),
        # Balcony sniper
        ( 5, 50, 'E'),
        # Bedroom 1
        (24,  6, 'E'),
        # Bedroom 2
        (21, 17, 'E'),
        # Kitchen — 2 enemies (ambush behind counter)
        (31, 16, 'E'),
        (32, 26, 'E'),
        # Office — 2 enemies
        (20, 38, 'S'),
        (30, 50, 'S'),
        # Weapon pickups
        (10,  5, 'g'),   # pistol near entrance
        ( 7, 24, 'x'),   # shotgun in living room
        (34, 19, 'k'),   # katana bottom of kitchen
        (25, 52, 'b'),   # bat in office
    ]

    patrols = {
        ( 8,  6): [_wp(3,8),   _wp(7,8)],
        ( 5, 15): [_wp(10,5),  _wp(26,5)],
        ( 9, 23): [_wp(10,9),  _wp(26,9)],
        (15, 10): [_wp(3,15),  _wp(25,15)],
        (15, 45): [_wp(32,15), _wp(56,15)],
        ( 5, 50): [_wp(30,5),  _wp(56,5)],
        (24,  6): [_wp(3,20),  _wp(10,25)],
        (21, 17): [_wp(14,20), _wp(22,24)],
        (31, 16): [_wp(14,31), _wp(14,34)],
        (32, 26): [_wp(14,32), _wp(28,32)],
        (20, 38): [_wp(32,19), _wp(56,19)],
        (30, 50): [_wp(32,29), _wp(56,29)],
    }

    return {
        "name":      "RESIDENTIAL BLOCK 7  //  APT 404",
        "grid":      _build(W, H, floors, entities, obstacles),
        "patrols":   patrols,
    }


LEVEL_DATA = [_apartment()]


# ── Map class ─────────────────────────────────────────────────────────────────
class Map:
    def __init__(self, data: dict):
        self.name:    str       = data["name"]
        self.grid:    list[str] = list(data["grid"])   # mutable copy
        self.patrols: dict      = data.get("patrols", {})
        self.rows:    int       = len(self.grid)
        self.cols:    int       = max(len(r) for r in self.grid)

        T = constants.TILE
        self.width:  int = self.cols * T
        self.height: int = self.rows * T

        # Wall HP: '#' → HP_THIN, '=' → HP_STRUCTURAL (never 0)
        self.wall_hp: dict = {}
        self.player_start: tuple = (T * 1.5, T * 1.5)
        self.enemy_starts: list  = []
        self.item_spawns:  list  = []
        self._parse()

        self._bg = pygame.Surface((self.width, self.height))
        self._render_bg()

    # ── Parsing ───────────────────────────────────────────────────────────────
    def _parse(self):
        T = constants.TILE
        ENEMY = {"E": 1, "S": 2}
        ITEM  = {"g": 1, "x": 2, "b": 3, "k": 4}
        for r, row in enumerate(self.grid):
            for c, ch in enumerate(row):
                wx = c * T + T // 2
                wy = r * T + T // 2
                if ch == '#':
                    self.wall_hp[(r, c)] = constants.HP_THIN
                elif ch == '=':
                    self.wall_hp[(r, c)] = constants.HP_STRUCTURAL
                elif ch == 'P':
                    self.player_start = (float(wx), float(wy))
                elif ch in ENEMY:
                    patrol = self.patrols.get((r, c), [(wx, wy)])
                    self.enemy_starts.append({
                        "x": float(wx), "y": float(wy),
                        "weapon": ENEMY[ch], "patrol": patrol,
                    })
                elif ch in ITEM:
                    self.item_spawns.append({
                        "x": float(wx), "y": float(wy), "weapon": ITEM[ch],
                    })

    # ── Background render ─────────────────────────────────────────────────────
    def _render_bg(self):
        T    = constants.TILE
        surf = self._bg
        surf.fill(constants.COL_BG)
        for r, row in enumerate(self.grid):
            for c, ch in enumerate(row):
                rx, ry = c * T, r * T
                rect = pygame.Rect(rx, ry, T, T)
                if ch == '=':
                    pygame.draw.rect(surf, constants.COL_WALL_STR, rect)
                    pygame.draw.rect(surf, (50, 40, 62), rect, 1)
                elif ch == '#':
                    pygame.draw.rect(surf, constants.COL_WALL, rect)
                    # Neon edge highlight: top + left 1px
                    pygame.draw.line(surf, (0, 120, 110),
                                     (rx, ry), (rx + T - 1, ry))
                    pygame.draw.line(surf, (0, 120, 110),
                                     (rx, ry), (rx, ry + T - 1))
                    # Brick texture: tiny 4×4 pattern
                    for br in range(0, T, 4):
                        for bc in range(0, T, 4):
                            if (br // 4 + bc // 4) % 2 == 0:
                                pygame.draw.rect(surf, (20, 20, 32),
                                                 (rx + bc, ry + br, 4, 4))
                else:
                    # Floor: dark base + parquet lines every 8 px
                    pygame.draw.rect(surf, constants.COL_FLOOR, rect)
                    if ry % 8 == 0:
                        pygame.draw.line(surf, constants.COL_GRID,
                                         (rx, ry), (rx + T - 1, ry))

    # ── Live queries ──────────────────────────────────────────────────────────
    def tile_char(self, col: int, row: int) -> str:
        if row < 0 or row >= self.rows or col < 0 or col >= self.cols:
            return '='
        s = self.grid[row]
        return s[col] if col < len(s) else '='

    def is_wall(self, wx: float, wy: float) -> bool:
        T = constants.TILE
        return self.tile_char(int(wx // T), int(wy // T)) in ('#', '=')

    # ── Wall damage ───────────────────────────────────────────────────────────
    def hit_wall(self, row: int, col: int, dmg: int = 1) -> bool:
        """Apply damage; return True if the tile was just destroyed."""
        key = (row, col)
        if key not in self.wall_hp:
            return False
        self.wall_hp[key] -= dmg
        if self.wall_hp[key] <= 0:
            del self.wall_hp[key]
            # Replace the grid row with tile converted to floor
            old = self.grid[row]
            self.grid[row] = old[:col] + '.' + old[col + 1:]
            # Erase the tile on the background surface
            T = constants.TILE
            rx, ry = col * T, row * T
            pygame.draw.rect(self._bg, constants.COL_FLOOR,
                             (rx, ry, T, T))
            if ry % 8 == 0:
                pygame.draw.line(self._bg, constants.COL_GRID,
                                 (rx, ry), (rx + T - 1, ry))
            return True
        return False

    # ── Render ────────────────────────────────────────────────────────────────
    def render(self, surf: pygame.Surface, cam_x: float, cam_y: float):
        surf.blit(self._bg, (-int(cam_x), -int(cam_y)))


# ── Camera helper ─────────────────────────────────────────────────────────────
def camera_for(px: float, py: float,
               map_w: int, map_h: int,
               view_w: int, view_h: int) -> tuple:
    cx = px - view_w / 2
    cy = py - view_h / 2
    cx = max(0.0, min(cx, float(max(0, map_w - view_w))))
    cy = max(0.0, min(cy, float(max(0, map_h - view_h))))
    return cx, cy
