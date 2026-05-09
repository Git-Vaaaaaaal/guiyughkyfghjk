#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# main.py – game loop, 480×270 viewport upscaled ×2, smooth camera, wall destruction

import sys
import math
import time
import random

import music
music.pre_init()

import pygame

import constants
from constants import *
from map      import Map, camera_for, LEVEL_DATA
from physics  import PhysicsWorld
from player   import Player, FloorItem, PICKUP_DIST
from enemy    import Enemy, NOISE_RANGE
from settings import Settings, RESOLUTIONS, KEY_LABELS
from ui       import (ScreenFlash, render_hud, render_scanlines,
                      render_title, render_score, render_gameover,
                      render_settings)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * min(t, 1.0)

def _adiff(a: float, b: float) -> float:
    d = (b - a) % (2 * math.pi)
    return d - 2 * math.pi if d > math.pi else d


class Game:

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("NEON HOMICIDE")

        self.cfg    = Settings()
        self.screen = self.cfg.apply_display()
        self.clock  = pygame.time.Clock()

        # Internal 480×270 surface — rendered at half-res, upscaled ×2
        self.view = pygame.Surface((VIEW_W, VIEW_H))

        # Smooth camera state (world coordinates)
        self.cam_x = 0.0
        self.cam_y = 0.0

        # Screen shake
        self.shake_mag = 0.0

        # Settings UI
        self._set_cursor    = 0
        self._set_rebind    = False
        self._set_from_game = False

        self.state  = GS_TITLE
        self.level  = 0
        self._scr_t = 0.0

        self.phys    = PhysicsWorld()
        self.flash   = ScreenFlash()

        self.map:     Map          | None = None
        self.player:  Player       | None = None
        self.enemies: list[Enemy]         = []
        self.items:   list[FloorItem]     = []

        self.level_start  = 0.0
        self.total_kills  = 0
        self.kill_variety: set = set()

        try:
            music.play(self.cfg.music_vol)
        except Exception as e:
            print(f"[music] {e}")

    # ── Main loop ─────────────────────────────────────────────────────────────
    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            self._scr_t += dt
            self.flash.update()

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.cfg.save(); pygame.quit(); sys.exit()
                self._handle(ev)

            if   self.state == GS_TITLE:
                render_title(self.screen, self._scr_t)
            elif self.state == GS_PLAYING:
                self._update(dt)
                self._render()
            elif self.state == GS_SCORE:
                elapsed = time.time() - self.level_start
                render_score(self.screen, self.total_kills,
                             len(self.kill_variety), elapsed, self.level)
            elif self.state == GS_GAMEOVER:
                render_gameover(self.screen, self._scr_t)
            elif self.state == GS_SETTINGS:
                render_settings(self.screen, self.cfg,
                                self._set_cursor, self._set_rebind,
                                self._set_from_game)

            pygame.display.flip()

    # ── Event routing ─────────────────────────────────────────────────────────
    def _handle(self, ev):
        if   self.state == GS_TITLE:    self._ev_title(ev)
        elif self.state == GS_PLAYING:  self._ev_play(ev)
        elif self.state == GS_SCORE:    self._ev_score(ev)
        elif self.state == GS_GAMEOVER: self._ev_over(ev)
        elif self.state == GS_SETTINGS: self._ev_settings(ev)

    def _ev_title(self, ev):
        if ev.type != pygame.KEYDOWN: return
        if ev.key == pygame.K_RETURN:
            self._load(0); self._goto(GS_PLAYING)
        elif ev.key == pygame.K_s:
            self._set_from_game = False; self._goto(GS_SETTINGS)

    def _ev_play(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 1: self._fire()
            if ev.button == 3: self._melee()
        elif ev.type == pygame.KEYDOWN:
            if ev.key == self.cfg.keys.get("throw",  pygame.K_f): self._throw()
            if ev.key == self.cfg.keys.get("pickup", pygame.K_e): self._pickup()
            if ev.key == pygame.K_ESCAPE:
                self._set_from_game = True; self._goto(GS_SETTINGS)

    def _ev_score(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_RETURN:
            nxt = self.level + 1
            if nxt >= len(LEVEL_DATA): self._goto(GS_TITLE)
            else:
                self.level = nxt; self._load(nxt); self._goto(GS_PLAYING)

    def _ev_over(self, ev):
        if ev.type != pygame.KEYDOWN: return
        if ev.key == pygame.K_r:
            self._load(self.level); self._goto(GS_PLAYING)
        elif ev.key == pygame.K_ESCAPE:
            self._goto(GS_TITLE)

    def _ev_settings(self, ev):
        if ev.type != pygame.KEYDOWN: return
        n_rows = 3 + len(KEY_LABELS)

        if self._set_rebind:
            if ev.key == pygame.K_ESCAPE:
                self._set_rebind = False; return
            actions = list(KEY_LABELS.keys())
            self.cfg.keys[actions[self._set_cursor - 3]] = ev.key
            self._set_rebind = False; self.cfg.save(); return

        if ev.key == pygame.K_ESCAPE:
            self.cfg.save()
            self._goto(GS_PLAYING if self._set_from_game else GS_TITLE)
        elif ev.key == pygame.K_UP:
            self._set_cursor = (self._set_cursor - 1) % n_rows
        elif ev.key == pygame.K_DOWN:
            self._set_cursor = (self._set_cursor + 1) % n_rows
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self._set_cursor >= 3: self._set_rebind = True
        elif ev.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self._settings_change(1 if ev.key == pygame.K_RIGHT else -1)
        elif ev.key == pygame.K_BACKSPACE and self._set_cursor >= 3:
            from settings import DEFAULT_KEYS
            actions = list(KEY_LABELS.keys())
            self.cfg.keys[actions[self._set_cursor - 3]] = \
                DEFAULT_KEYS[actions[self._set_cursor - 3]]
            self.cfg.save()

    def _settings_change(self, d: int):
        c = self._set_cursor
        if c == 0:
            self.cfg.resolution_idx = (self.cfg.resolution_idx + d) % len(RESOLUTIONS)
            self.screen = self.cfg.apply_display()
        elif c == 1:
            self.cfg.fullscreen = not self.cfg.fullscreen
            self.screen = self.cfg.apply_display()
        elif c == 2:
            self.cfg.music_vol = max(0.0, min(1.0, self.cfg.music_vol + d * 0.05))
            music.set_volume(self.cfg.music_vol)
        self.cfg.save()

    # ── Level loading ─────────────────────────────────────────────────────────
    def _load(self, idx: int):
        self.phys.clear()
        self.map = Map(LEVEL_DATA[idx])
        self.phys.init_blood(self.map.width, self.map.height)
        self.phys.load_walls(self.map)          # pass map object, not segments

        px, py = self.map.player_start
        self.player = Player(px, py)
        self.player.pickup(W_PISTOL)

        # Initialise camera to player position
        self.cam_x, self.cam_y = camera_for(px, py,
                                             self.map.width, self.map.height,
                                             VIEW_W, VIEW_H)

        self.enemies = [Enemy(e["x"], e["y"], e["weapon"],
                              e["patrol"], self.phys)
                        for e in self.map.enemy_starts]
        self.items   = [FloorItem(it["x"], it["y"], it["weapon"])
                        for it in self.map.item_spawns]

        self.level_start  = time.time()
        self.total_kills  = 0
        self.kill_variety = set()
        self.shake_mag    = 0.0

    # ── Player actions ────────────────────────────────────────────────────────
    def _fire(self):
        p = self.player
        if not p or not p.alive: return
        if p.weapon in RANGED:
            if p.shoot(): self._noise(p.x, p.y)
        else:
            self._melee()

    def _melee(self):
        p = self.player
        if not p or not p.alive: return
        info = p.melee_info()
        if not info: return
        ang = info["angle"]
        arc = math.radians(info["arc_deg"])
        for e in self.enemies:
            if not e.alive: continue
            dx = e.x - p.x; dy = e.y - p.y
            dist = math.hypot(dx, dy)
            if dist > info["arc_deg"] + 5: continue
            if abs(_adiff(ang, math.atan2(dy, dx))) > arc: continue
            m = max(dist, 1)
            e.die(self.phys, (dx / m, dy / m))
            self._kill(info["weapon"])
            self.flash.trigger(
                COL_MAGENTA if info["weapon"] == W_KATANA else COL_CYAN,
                frames=3)
            self._shake(7)

    def _throw(self):
        p = self.player
        if p and p.alive: p.throw_weapon(self.phys)

    def _pickup(self):
        p = self.player
        if not p or not p.alive: return
        for item in self.items:
            if item.active and math.hypot(item.x-p.x, item.y-p.y) < PICKUP_DIST:
                p.pickup(item.weapon); item.active = False; return
        for tw in self.phys.thrown_as_pickup():
            pos = tw["body"].position
            if math.hypot(pos.x-p.x, pos.y-p.y) < PICKUP_DIST:
                p.pickup(tw["weapon"]); self.phys.remove_thrown(tw); return

    # ── Update ────────────────────────────────────────────────────────────────
    def _update(self, dt: float):
        p    = self.player
        gm   = self.map
        keys = pygame.key.get_pressed()

        # Movement input (settings keybindings + fallback WASD/ZQSD/arrows)
        dx = dy = 0
        if self.cfg.key_held("up",    keys) or keys[pygame.K_w] or keys[pygame.K_z] or keys[pygame.K_UP]:    dy -= 1
        if self.cfg.key_held("down",  keys) or keys[pygame.K_s] or keys[pygame.K_DOWN]:                       dy += 1
        if self.cfg.key_held("left",  keys) or keys[pygame.K_a] or keys[pygame.K_q] or keys[pygame.K_LEFT]:  dx -= 1
        if self.cfg.key_held("right", keys) or keys[pygame.K_d] or keys[pygame.K_RIGHT]:                      dx += 1
        dx = max(-1, min(1, dx))
        dy = max(-1, min(1, dy))

        p._ext_dx   = dx
        p._ext_dy   = dy
        p._ext_dash = keys[pygame.K_SPACE]

        # ── Aim: convert screen mouse → world coords via viewport scale ────────
        sw, sh   = self.screen.get_size()
        mx, my   = pygame.mouse.get_pos()
        # Mouse in view space
        vmx = (mx / sw) * VIEW_W
        vmy = (my / sh) * VIEW_H
        # World space
        world_mx = vmx + self.cam_x
        world_my = vmy + self.cam_y
        p.aim_at(world_mx, world_my)

        p.update(dt, keys, gm, self.phys)

        for e in self.enemies:
            e.update(dt, p, gm, self.phys, self.enemies)

        for item in self.items:
            item.update(dt)

        self.phys.update(dt)

        # ── Bullet collisions (all sources, walls + entities) ─────────────────
        self._update_bullets(dt)

        # ── Thrown weapon kills ───────────────────────────────────────────────
        self._thrown_vs_all()

        # ── Auto-pickup ───────────────────────────────────────────────────────
        if p.alive and p.weapon == W_NONE:
            for item in self.items:
                if item.active and math.hypot(item.x-p.x, item.y-p.y) < PICKUP_DIST // 2:
                    p.pickup(item.weapon); item.active = False; break

        # ── Win / lose ────────────────────────────────────────────────────────
        if all(not e.alive for e in self.enemies):
            self._goto(GS_SCORE)
        if not p.alive:
            self._goto(GS_GAMEOVER)

        # ── Smooth camera with look-ahead ─────────────────────────────────────
        target_cx, target_cy = camera_for(p.x, p.y,
                                          gm.width, gm.height,
                                          VIEW_W, VIEW_H)
        # Look-ahead: bias camera toward mouse
        look_x = (vmx - VIEW_W / 2) * CAM_LOOKAHEAD
        look_y = (vmy - VIEW_H / 2) * CAM_LOOKAHEAD
        target_cx = max(0.0, min(target_cx + look_x,
                                 float(max(0, gm.width  - VIEW_W))))
        target_cy = max(0.0, min(target_cy + look_y,
                                 float(max(0, gm.height - VIEW_H))))

        self.cam_x = _lerp(self.cam_x, target_cx, CAM_SMOOTH * dt)
        self.cam_y = _lerp(self.cam_y, target_cy, CAM_SMOOTH * dt)

        # Shake decay
        self.shake_mag *= 0.80

    # ── Bullet + wall resolution ───────────────────────────────────────────────
    def _update_bullets(self, dt: float):
        p   = self.player
        gm  = self.map
        dead: set = set()

        all_bullets = list(p.bullets)
        for e in self.enemies:
            all_bullets.extend(e.bullets)

        for b in all_bullets:
            if id(b) in dead:
                continue
            prev = (b.x - b.vx * dt, b.y - b.vy * dt)
            curr = (b.x, b.y)

            hit_pt, _, tile = self.phys.cast_ray(prev, curr)

            if hit_pt is not None:
                dead.add(id(b))
                if tile:
                    r, c = tile
                    destroyed = gm.hit_wall(r, c)
                    if destroyed:
                        self.phys.destroy_wall_tile(r, c)
                        self._wall_debris(hit_pt[0], hit_pt[1])
                continue

            if b.owner == "player" and p.alive:
                for e in self.enemies:
                    if not e.alive: continue
                    if math.hypot(b.x-e.x, b.y-e.y) < e.radius + 3:
                        ang = math.atan2(b.vy, b.vx)
                        e.die(self.phys, (math.cos(ang), math.sin(ang)))
                        self._kill(b.weapon)
                        self._noise(b.x, b.y)
                        self.flash.trigger(
                            WEAPON_COLORS.get(b.weapon, COL_CYAN), 3)
                        self._shake(8)
                        dead.add(id(b))
                        break

            elif b.owner == "enemy" and p.alive:
                if math.hypot(b.x-p.x, b.y-p.y) < p.radius + 3:
                    ang = math.atan2(b.vy, b.vx)
                    p.die(self.phys, (math.cos(ang), math.sin(ang)))
                    self.flash.trigger(COL_MAGENTA, 6)
                    self._shake(14)
                    dead.add(id(b))

        p.bullets = [b for b in p.bullets if id(b) not in dead]
        for e in self.enemies:
            e.bullets = [b for b in e.bullets if id(b) not in dead]

    def _thrown_vs_all(self):
        p = self.player
        for tw in list(self.phys.thrown):
            if not tw["active"] or tw["body"].velocity.length < 70:
                continue
            pos = tw["body"].position
            wx, wy = float(pos.x), float(pos.y)
            for e in self.enemies:
                if not e.alive: continue
                if math.hypot(wx-e.x, wy-e.y) < e.radius + 7:
                    vel = tw["body"].velocity
                    m   = max(vel.length, 1)
                    e.die(self.phys, (vel.x/m, vel.y/m))
                    self._kill(tw["weapon"])
                    self.flash.trigger(WEAPON_COLORS.get(tw["weapon"], COL_CYAN), 3)
                    self._shake(7)
                    tw["active"] = False; break
            if p.alive and tw["active"]:
                if math.hypot(wx-p.x, wy-p.y) < p.radius + 7:
                    vel = tw["body"].velocity
                    m   = max(vel.length, 1)
                    p.die(self.phys, (vel.x/m, vel.y/m))
                    self.flash.trigger(COL_MAGENTA, 6)
                    self._shake(14); tw["active"] = False

    # ── Wall debris (simple bright squares) ───────────────────────────────────
    def _wall_debris(self, wx: float, wy: float):
        self.phys.splat_blood(wx, wy, size=5)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _noise(self, nx: float, ny: float):
        for e in self.enemies:
            if e.alive and math.hypot(e.x-nx, e.y-ny) < NOISE_RANGE:
                e.alert(nx, ny)

    def _kill(self, weapon: int):
        self.total_kills += 1
        self.kill_variety.add(weapon)

    def _shake(self, mag: float):
        self.shake_mag = max(self.shake_mag, mag)

    def _goto(self, state: int):
        self.state  = state
        self._scr_t = 0.0

    # ── Render ────────────────────────────────────────────────────────────────
    def _render(self):
        p   = self.player
        gm  = self.map

        # Apply screen shake to camera for this frame only
        sx_off = int(random.gauss(0, self.shake_mag * 0.5)) if self.shake_mag > 0.5 else 0
        sy_off = int(random.gauss(0, self.shake_mag * 0.5)) if self.shake_mag > 0.5 else 0
        cam_x = self.cam_x + sx_off
        cam_y = self.cam_y + sy_off

        # Render to internal 480×270 surface
        v = self.view

        gm.render(v, cam_x, cam_y)
        self.phys.render(v, cam_x, cam_y)

        for item in self.items:
            item.render(v, cam_x, cam_y)
        for e in self.enemies:
            e.render(v, cam_x, cam_y)
        p.render(v, cam_x, cam_y)

        enemies_left = sum(1 for e in self.enemies if e.alive)
        render_hud(v, p.weapon if p.alive else W_NONE,
                   gm.name, enemies_left, self.level)
        self.flash.render(v)
        render_scanlines(v)

        # Upscale ×2 to actual screen
        sw, sh = self.screen.get_size()
        pygame.transform.scale(v, (sw, sh), self.screen)


# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    Game().run()
