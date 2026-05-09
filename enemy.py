# enemy.py – enemy entity with 3-state AI (PATROL / ALERT / COMBAT)
import pygame
import math
import random
from constants import *
from player import Bullet, _wall_hit

FOV_RANGE   = 140    # px – vision cone (≈9 tiles @16px)
FOV_ANGLE   = 80     # degrees half-arc
ALERT_TIME  = 3.5
SHOOT_CD    = 0.9
MOVE_SPEED  = 58     # px/s (smaller tiles → keep proportional feel)
ALERT_SPEED = 44
RADIUS      = 5      # px — matches TILE=16 scale
NOISE_RANGE = 190    # px


class Enemy:
    """Enemy with patrol waypoints, alert state, and combat shooting."""

    def __init__(self, x: float, y: float,
                 weapon: int, patrol: list, phys):
        self.x      = float(x)
        self.y      = float(y)
        self.radius = RADIUS
        self.weapon = weapon
        self.alive  = True
        self.angle  = 0.0       # facing direction (radians)

        self.state       = ST_PATROL
        self.patrol_pts  = [tuple(p) for p in patrol]
        self.patrol_idx  = 0
        self.alert_timer = 0.0
        self.alert_target: tuple | None = None  # last known noise position

        self.shoot_cd  = random.uniform(0, SHOOT_CD)   # stagger enemy shots
        self.bullets: list[Bullet] = []
        self._phys = phys

    # ── Public helpers ────────────────────────────────────────────────────────
    def alert(self, noise_x: float, noise_y: float):
        """External call: a nearby gunshot was heard."""
        if not self.alive:
            return
        if self.state == ST_PATROL:
            self.state        = ST_ALERT
            self.alert_timer  = ALERT_TIME
            self.alert_target = (noise_x, noise_y)

    def die(self, phys, impulse_dir=(0.0, 0.0)):
        if not self.alive:
            return
        self.alive = False
        self.bullets.clear()
        col = COL_E_COMBAT
        speed = 300
        vel = (impulse_dir[0] * speed, impulse_dir[1] * speed)
        phys.spawn_ragdoll(self.x, self.y, vel, col)

    # ── Update ────────────────────────────────────────────────────────────────
    def update(self, dt: float, player, game_map, phys, all_enemies):
        if not self.alive:
            return

        can_see = self._can_see_player(player, phys)

        # ── State transitions ─────────────────────────────────────────────────
        if can_see:
            self.state       = ST_COMBAT
            self.alert_timer = ALERT_TIME
        elif self.state == ST_COMBAT:
            # Lost sight
            self.state        = ST_ALERT
            self.alert_target = (player.x, player.y)
            self.alert_timer  = ALERT_TIME

        if self.state == ST_ALERT:
            self.alert_timer -= dt
            if self.alert_timer <= 0:
                self.state = ST_PATROL

        # ── Behaviour per state ───────────────────────────────────────────────
        if self.state == ST_PATROL:
            self._do_patrol(dt, game_map)
        elif self.state == ST_ALERT:
            self._do_alert(dt, game_map)
        elif self.state == ST_COMBAT:
            self._do_combat(dt, player, game_map, phys)

        # ── Bullet update (wall collision handled by main.py) ────────────────
        self.bullets = [b for b in self.bullets if b.update(dt)]

    # ── Internal behaviours ───────────────────────────────────────────────────
    def _do_patrol(self, dt: float, game_map):
        if not self.patrol_pts:
            return
        tx, ty = self.patrol_pts[self.patrol_idx]
        dist = math.hypot(tx - self.x, ty - self.y)
        if dist < 6:
            self.patrol_idx = (self.patrol_idx + 1) % len(self.patrol_pts)
            return
        self._move_toward(tx, ty, MOVE_SPEED, dt, game_map)

    def _do_alert(self, dt: float, game_map):
        if self.alert_target:
            tx, ty = self.alert_target
            dist = math.hypot(tx - self.x, ty - self.y)
            if dist < 10:
                self.alert_target = None
            else:
                self._move_toward(tx, ty, ALERT_SPEED, dt, game_map)

    def _do_combat(self, dt: float, player, game_map, phys):
        # Chase player
        self._move_toward(player.x, player.y, MOVE_SPEED, dt, game_map)

        # Shoot if ranged weapon and cooldown ready
        if self.weapon in RANGED:
            self.shoot_cd -= dt
            if self.shoot_cd <= 0:
                self.shoot_cd = SHOOT_CD
                self._fire_at(player, phys)

    def _move_toward(self, tx: float, ty: float,
                     speed: float, dt: float, game_map):
        dx = tx - self.x
        dy = ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 1:
            return
        dx /= dist; dy /= dist
        self.angle = math.atan2(dy, dx)
        nx = self.x + dx * speed * dt
        ny = self.y + dy * speed * dt
        if not _wall_hit(nx, self.y, self.radius, game_map):
            self.x = nx
        if not _wall_hit(self.x, ny, self.radius, game_map):
            self.y = ny

    def _fire_at(self, player, phys):
        # Aim with slight inaccuracy
        ang = math.atan2(player.y - self.y, player.x - self.x)
        ang += random.uniform(-0.12, 0.12)
        b = Bullet(self.x, self.y, ang, 500, "enemy", self.weapon)
        self.bullets.append(b)

    def _can_see_player(self, player, phys) -> bool:
        """Cone vision check then LOS ray-cast."""
        if not player.alive:
            return False
        dx = player.x - self.x
        dy = player.y - self.y
        dist = math.hypot(dx, dy)
        if dist > FOV_RANGE:
            return False
        # Angle between facing direction and player direction
        angle_to = math.atan2(dy, dx)
        diff = abs(_angle_diff(self.angle, angle_to))
        if math.degrees(diff) > FOV_ANGLE:
            return False
        # LOS wall check
        return phys.has_los((self.x, self.y), (player.x, player.y))

    # ── Render ────────────────────────────────────────────────────────────────
    def render(self, surface: pygame.Surface, cam_x: float, cam_y: float):
        if not self.alive:
            return
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)

        col = {
            ST_PATROL: COL_E_PATROL,
            ST_ALERT:  COL_E_ALERT,
            ST_COMBAT: COL_E_COMBAT,
        }[self.state]

        pygame.draw.circle(surface, col, (sx, sy), self.radius)
        pygame.draw.circle(surface, (0, 0, 0), (sx, sy), self.radius, 2)

        # Vision arc indicator
        for da in (-FOV_ANGLE, 0, FOV_ANGLE):
            a2 = self.angle + math.radians(da)
            ex = sx + int(math.cos(a2) * 18)
            ey = sy + int(math.sin(a2) * 18)
            pygame.draw.line(surface, (*col, 80), (sx, sy), (ex, ey), 1)

        # Direction nub
        ex = sx + int(math.cos(self.angle) * (self.radius + 5))
        ey = sy + int(math.sin(self.angle) * (self.radius + 5))
        pygame.draw.line(surface, col, (sx, sy), (ex, ey), 2)

        # Bullets
        for b in self.bullets:
            bx = int(b.x - cam_x)
            by = int(b.y - cam_y)
            pygame.draw.circle(surface, COL_MAGENTA, (bx, by), 3)

    # ── Alert cone FOV outline (debug, optional) ──────────────────────────────
    def render_fov(self, surface: pygame.Surface, cam_x: float, cam_y: float):
        if not self.alive or self.state != ST_COMBAT:
            return
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        pts = [(sx, sy)]
        steps = 12
        for i in range(steps + 1):
            a = self.angle - math.radians(FOV_ANGLE) + \
                i * math.radians(FOV_ANGLE * 2) / steps
            pts.append((
                sx + int(math.cos(a) * FOV_RANGE),
                sy + int(math.sin(a) * FOV_RANGE),
            ))
        fov_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(fov_surf, (255, 60, 60, 25), pts)
        surface.blit(fov_surf, (0, 0))


# ── Utility ───────────────────────────────────────────────────────────────────
def _angle_diff(a: float, b: float) -> float:
    """Signed shortest angle from a to b in radians."""
    d = (b - a) % (2 * math.pi)
    if d > math.pi:
        d -= 2 * math.pi
    return d
