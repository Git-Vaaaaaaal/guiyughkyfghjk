# player.py – player entity: inertia movement, dash, weapons, death
import pygame
import math
from constants import *

RADIUS      = 5     # px (fits 16-px tiles)
MELEE_RANGE = 26    # px
MELEE_HALF  = 55    # degrees half-arc
SHOOT_CD    = 0.22  # s between pistol shots
SHOTGUN_CD  = 0.55
THROW_SPD   = 380
PICKUP_DIST = 20    # px for auto-pickup


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * min(t, 1.0)


class Bullet:
    """A single fired projectile — movement only, collision handled by main."""
    __slots__ = ("x", "y", "vx", "vy", "life", "owner", "weapon")

    def __init__(self, x, y, angle, speed, owner, weapon):
        self.x      = x + math.cos(angle) * (RADIUS + 3)
        self.y      = y + math.sin(angle) * (RADIUS + 3)
        self.vx     = math.cos(angle) * speed
        self.vy     = math.sin(angle) * speed
        self.life   = 1.6
        self.owner  = owner   # "player" | "enemy"
        self.weapon = weapon

    def update(self, dt: float) -> bool:
        """Move; return True while alive."""
        self.x    += self.vx * dt
        self.y    += self.vy * dt
        self.life -= dt
        return self.life > 0


class Player:
    def __init__(self, x: float, y: float):
        self.x   = float(x)
        self.y   = float(y)
        self.vx  = 0.0
        self.vy  = 0.0
        self.angle = 0.0
        self.radius = RADIUS
        self.alive  = True

        self.weapon   = W_NONE
        self.shoot_cd = 0.0
        self.flash    = 0

        # Dash state
        self.dash_timer = 0.0   # >0 while actively dashing
        self.dash_cd    = 0.0   # cooldown remaining

        self.bullets: list[Bullet] = []

        # Set by main.py each frame (settings-aware keybinding)
        self._ext_dx   = 0
        self._ext_dy   = 0
        self._ext_dash = False

    # ── Update ────────────────────────────────────────────────────────────────
    def update(self, dt: float, keys, game_map, phys):
        if not self.alive:
            return

        dx, dy = self._ext_dx, self._ext_dy

        # ── Dash ──────────────────────────────────────────────────────────────
        if self.dash_timer > 0:
            self.dash_timer -= dt
            # velocity already set at dash initiation — just let it coast
        elif self._ext_dash and self.dash_cd <= 0:
            # Initiate dash in the facing direction
            self.dash_timer = DASH_DUR
            self.dash_cd    = DASH_CD
            self.vx = math.cos(self.angle) * DASH_SPD
            self.vy = math.sin(self.angle) * DASH_SPD

        if self.dash_cd > 0:
            self.dash_cd -= dt

        # ── Velocity / friction (only when not dashing) ───────────────────────
        if self.dash_timer <= 0:
            if dx or dy:
                ln = math.hypot(dx, dy)
                if ln:
                    dx /= ln; dy /= ln
                self.vx += dx * ACCEL * dt
                self.vy += dy * ACCEL * dt
                # Speed cap
                spd = math.hypot(self.vx, self.vy)
                if spd > MAX_SPD:
                    self.vx = self.vx / spd * MAX_SPD
                    self.vy = self.vy / spd * MAX_SPD
            else:
                # Smooth friction stop
                f = FRICTION * dt
                self.vx = _lerp(self.vx, 0.0, f)
                self.vy = _lerp(self.vy, 0.0, f)

        # ── Apply velocity with per-axis tile collision ────────────────────────
        nx = self.x + self.vx * dt
        ny = self.y + self.vy * dt
        if not _wall_hit(nx, self.y, self.radius, game_map):
            self.x = nx
        else:
            self.vx = 0.0
        if not _wall_hit(self.x, ny, self.radius, game_map):
            self.y = ny
        else:
            self.vy = 0.0

        # ── Timers ────────────────────────────────────────────────────────────
        if self.shoot_cd > 0: self.shoot_cd -= dt
        if self.flash    > 0: self.flash    -= 1

        # ── Bullets: move only (collision resolved in main.py) ────────────────
        self.bullets = [b for b in self.bullets if b.update(dt)]

    def aim_at(self, world_mx: float, world_my: float):
        self.angle = math.atan2(world_my - self.y, world_mx - self.x)

    # ── Actions ───────────────────────────────────────────────────────────────
    def shoot(self) -> list:
        if self.weapon not in RANGED or self.shoot_cd > 0 or not self.alive:
            return []
        self.shoot_cd = SHOTGUN_CD if self.weapon == W_SHOTGUN else SHOOT_CD
        speed = 600
        new_bs = []
        if self.weapon == W_PISTOL:
            new_bs.append(Bullet(self.x, self.y, self.angle,
                                 speed, "player", self.weapon))
        elif self.weapon == W_SHOTGUN:
            for sp in (-0.22, -0.11, 0, 0.11, 0.22):
                new_bs.append(Bullet(self.x, self.y, self.angle + sp,
                                     speed, "player", self.weapon))
        self.bullets.extend(new_bs)
        return new_bs

    def melee_info(self) -> dict | None:
        if self.weapon in RANGED or not self.alive:
            return None
        return {
            "x":       self.x + math.cos(self.angle) * MELEE_RANGE,
            "y":       self.y + math.sin(self.angle) * MELEE_RANGE,
            "angle":   self.angle,
            "arc_deg": MELEE_HALF,
            "weapon":  self.weapon,
            "impulse": 360 if self.weapon == W_BAT else 220,
        }

    def throw_weapon(self, phys) -> bool:
        if self.weapon == W_NONE or not self.alive:
            return False
        vx = math.cos(self.angle) * THROW_SPD
        vy = math.sin(self.angle) * THROW_SPD
        phys.spawn_thrown(self.x, self.y, (vx, vy), self.weapon)
        self.weapon = W_NONE
        return True

    def pickup(self, weapon: int):
        self.weapon = weapon

    def die(self, phys, impulse_dir=(0.0, 0.0)):
        if not self.alive:
            return
        self.alive = False
        self.bullets.clear()
        speed = 260
        phys.spawn_ragdoll(self.x, self.y,
                           (impulse_dir[0] * speed, impulse_dir[1] * speed),
                           COL_PLAYER)

    # ── Render ────────────────────────────────────────────────────────────────
    def render(self, surf: pygame.Surface, cam_x: float, cam_y: float):
        if not self.alive:
            return
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)

        body_col = COL_CYAN if self.flash % 2 == 0 else COL_WHITE

        # Dash trail (faint behind)
        if self.dash_timer > 0:
            trail_col = (*COL_CYAN, 60)
            for i in range(1, 4):
                tx = sx - int(math.cos(self.angle) * i * 4)
                ty = sy - int(math.sin(self.angle) * i * 4)
                ts = pygame.Surface((self.radius * 2, self.radius * 2),
                                    pygame.SRCALPHA)
                pygame.draw.circle(ts, trail_col,
                                   (self.radius, self.radius), self.radius)
                surf.blit(ts, (tx - self.radius, ty - self.radius))

        pygame.draw.circle(surf, body_col, (sx, sy), self.radius)
        pygame.draw.circle(surf, (0, 0, 0), (sx, sy), self.radius, 1)

        # Aim line
        ex = sx + int(math.cos(self.angle) * (self.radius + 6))
        ey = sy + int(math.sin(self.angle) * (self.radius + 6))
        pygame.draw.line(surf, COL_AMBER, (sx, sy), (ex, ey), 2)

        # Bullets
        for b in self.bullets:
            bx = int(b.x - cam_x)
            by = int(b.y - cam_y)
            pygame.draw.circle(surf, COL_AMBER, (bx, by), 2)


# ── Floor item ────────────────────────────────────────────────────────────────
class FloorItem:
    def __init__(self, x: float, y: float, weapon: int):
        self.x      = float(x)
        self.y      = float(y)
        self.weapon = weapon
        self.active = True
        self._bob   = 0.0

    def update(self, dt: float):
        self._bob += dt * 3.0

    def render(self, surf: pygame.Surface, cam_x: float, cam_y: float):
        if not self.active:
            return
        sx  = int(self.x - cam_x)
        sy  = int(self.y - cam_y + math.sin(self._bob) * 1.2)
        col = WEAPON_COLORS.get(self.weapon, COL_WHITE)
        pygame.draw.circle(surf, col, (sx, sy), 5)
        pygame.draw.circle(surf, COL_BG, (sx, sy), 5, 1)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _wall_hit(x: float, y: float, r: float, game_map) -> bool:
    for px, py in [(x-r, y), (x+r, y), (x, y-r), (x, y+r),
                   (x-r, y-r), (x+r, y-r), (x-r, y+r), (x+r, y+r)]:
        if game_map.is_wall(px, py):
            return True
    return False
