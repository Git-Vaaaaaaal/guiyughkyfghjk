# physics.py – pymunk world: per-tile box shapes (supports destruction),
#              ragdolls, thrown weapons, ray-cast
import pymunk
import pygame
import math
import random
from constants import *


class PhysicsWorld:
    def __init__(self):
        self.space = pymunk.Space()
        self.space.gravity  = (0, 0)
        self.space.damping  = 0.45

        # Per-tile wall shapes: (row, col) → (body, shape)
        self._tile_shapes:  dict = {}
        self._shape_to_tile: dict = {}   # shape → (row, col)

        self.ragdolls: list = []
        self.thrown:   list = []
        self.blood_surf: pygame.Surface | None = None

    # ── Blood canvas ──────────────────────────────────────────────────────────
    def init_blood(self, w: int, h: int):
        self.blood_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        self.blood_surf.fill((0, 0, 0, 0))

    # ── Wall loading (per tile box shapes) ────────────────────────────────────
    def load_walls(self, map_obj):
        T = constants.TILE if hasattr(constants, 'TILE') else TILE
        for r in range(map_obj.rows):
            for c in range(map_obj.cols):
                ch = map_obj.tile_char(c, r)
                if ch in ('#', '='):
                    self._add_tile_shape(r, c, T)

    def _add_tile_shape(self, row: int, col: int, T: int):
        body = pymunk.Body(body_type=pymunk.Body.STATIC)
        body.position = (col * T + T / 2, row * T + T / 2)
        shape = pymunk.Poly.create_box(body, (T, T))
        shape.elasticity = 0.2
        shape.friction   = 1.0
        shape.filter     = pymunk.ShapeFilter(categories=CAT_WALL)
        self.space.add(body, shape)
        key = (row, col)
        self._tile_shapes[key]   = (body, shape)
        self._shape_to_tile[id(shape)] = key

    def destroy_wall_tile(self, row: int, col: int):
        key = (row, col)
        if key not in self._tile_shapes:
            return
        body, shape = self._tile_shapes.pop(key)
        self._shape_to_tile.pop(id(shape), None)
        self.space.remove(body, shape)

    # ── Ray-cast ──────────────────────────────────────────────────────────────
    def cast_ray(self, start: tuple, end: tuple,
                 radius: float = 0.5) -> tuple:
        """Returns (hit_point, normal, tile_rc) or (None, None, None)."""
        filt = pymunk.ShapeFilter(mask=CAT_WALL)
        hit  = self.space.segment_query_first(start, end, radius, filt)
        if hit:
            tile = self._shape_to_tile.get(id(hit.shape))
            return tuple(hit.point), tuple(hit.normal), tile
        return None, None, None

    def has_los(self, a: tuple, b: tuple) -> bool:
        pt, _, _ = self.cast_ray(a, b)
        return pt is None

    # ── Ragdolls ──────────────────────────────────────────────────────────────
    def spawn_ragdoll(self, x: float, y: float,
                      vel: tuple, color: tuple):
        offsets = [(0, 0), (-4, 7), (4, 7)]
        radii   = [6, 4, 4]
        parts   = []
        for (ox, oy), r in zip(offsets, radii):
            mass = 0.6
            body = pymunk.Body(mass, pymunk.moment_for_circle(mass, 0, r))
            body.position = (x + ox, y + oy)
            sc = 50
            body.velocity = (
                vel[0] + random.uniform(-sc, sc),
                vel[1] + random.uniform(-sc, sc),
            )
            body.angular_velocity = random.uniform(-7, 7)
            shape = pymunk.Circle(body, r)
            shape.elasticity = 0.15
            shape.friction   = 1.0
            shape.filter     = pymunk.ShapeFilter(
                categories=CAT_RAGDOLL, mask=CAT_WALL)
            self.space.add(body, shape)
            parts.append({"body": body, "shape": shape, "r": r})
        self.ragdolls.append({"parts": parts, "color": color, "ttl": 140})
        self.splat_blood(x, y)

    def splat_blood(self, x: float, y: float, size: int = 7):
        if not self.blood_surf:
            return
        ix, iy = int(x), int(y)
        pygame.draw.circle(self.blood_surf, (*COL_BLOOD, 210), (ix, iy), size)
        for _ in range(5):
            dx = random.randint(-size * 2, size * 2)
            dy = random.randint(-size * 2, size * 2)
            sr = random.randint(1, max(2, size // 2))
            pygame.draw.circle(self.blood_surf, (*COL_BLOOD, 150),
                               (ix + dx, iy + dy), sr)

    # ── Thrown weapons ────────────────────────────────────────────────────────
    def spawn_thrown(self, x: float, y: float,
                     vel: tuple, weapon_type: int) -> dict:
        mass = 0.3
        body = pymunk.Body(mass, pymunk.moment_for_circle(mass, 0, 6))
        body.position = (x, y)
        body.velocity = vel
        body.angular_velocity = random.choice([-12, 12])
        shape = pymunk.Circle(body, 6)
        shape.elasticity = 0.35
        shape.friction   = 0.8
        shape.filter     = pymunk.ShapeFilter(categories=CAT_ITEM, mask=CAT_WALL)
        self.space.add(body, shape)
        w = {"body": body, "shape": shape,
             "weapon": weapon_type, "active": True}
        self.thrown.append(w)
        return w

    def thrown_as_pickup(self) -> list:
        return [w for w in self.thrown
                if w["active"] and w["body"].velocity.length < 35]

    def remove_thrown(self, w: dict):
        if w in self.thrown:
            self.space.remove(w["body"], w["shape"])
            self.thrown.remove(w)

    # ── Step ──────────────────────────────────────────────────────────────────
    def update(self, dt: float):
        for rd in self.ragdolls:
            rd["ttl"] -= 1
            if rd["ttl"] < 0:
                for p in rd["parts"]:
                    spd = p["body"].velocity.length
                    if spd > 6:
                        p["body"].velocity = p["body"].velocity * 0.75
                    else:
                        p["body"].velocity = pymunk.Vec2d(0, 0)
                        p["body"].angular_velocity = 0
        self.space.step(dt)

    # ── Render ────────────────────────────────────────────────────────────────
    def render(self, surf: pygame.Surface, cam_x: float, cam_y: float):
        if self.blood_surf:
            surf.blit(self.blood_surf, (-int(cam_x), -int(cam_y)))
        for rd in self.ragdolls:
            for p in rd["parts"]:
                wx, wy = p["body"].position
                sx, sy = int(wx - cam_x), int(wy - cam_y)
                pygame.draw.circle(surf, rd["color"], (sx, sy), p["r"])
                pygame.draw.circle(surf, (0, 0, 0), (sx, sy), p["r"], 1)
        for w in self.thrown:
            if not w["active"]:
                continue
            wx, wy = w["body"].position
            sx, sy = int(wx - cam_x), int(wy - cam_y)
            _draw_weapon_icon(surf, w["weapon"], sx, sy, w["body"].angle)

    # ── Cleanup ───────────────────────────────────────────────────────────────
    def clear(self):
        for rd in self.ragdolls:
            for p in rd["parts"]:
                self.space.remove(p["body"], p["shape"])
        for w in self.thrown:
            self.space.remove(w["body"], w["shape"])
        for body, shape in self._tile_shapes.values():
            self.space.remove(body, shape)
        self.ragdolls.clear()
        self.thrown.clear()
        self._tile_shapes.clear()
        self._shape_to_tile.clear()
        if self.blood_surf:
            self.blood_surf.fill((0, 0, 0, 0))


def _draw_weapon_icon(surf, weapon, sx, sy, angle):
    col = WEAPON_COLORS.get(weapon, COL_WHITE)
    if weapon in (W_BAT, W_KATANA):
        L = 10 if weapon == W_KATANA else 8
        dx, dy = math.cos(angle) * L, math.sin(angle) * L
        pygame.draw.line(surf, col,
                         (int(sx-dx), int(sy-dy)),
                         (int(sx+dx), int(sy+dy)), 2)
    else:
        pygame.draw.circle(surf, col, (sx, sy), 4)
        pygame.draw.circle(surf, (0, 0, 0), (sx, sy), 4, 1)


import constants   # needed for TILE lookup at runtime
