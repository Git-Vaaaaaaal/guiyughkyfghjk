# settings.py – persistent settings: resolution, fullscreen, volume, keybindings
import json
import os
import pygame
import constants

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "settings.json")

RESOLUTIONS = [(960, 540), (1280, 720), (1920, 1080)]

# Action name → default pygame key constant
DEFAULT_KEYS = {
    "up":     pygame.K_w,
    "down":   pygame.K_s,
    "left":   pygame.K_a,
    "right":  pygame.K_d,
    "throw":  pygame.K_f,
    "pickup": pygame.K_e,
}

# Display names for the settings menu
KEY_LABELS = {
    "up":     "MOVE UP",
    "down":   "MOVE DOWN",
    "left":   "MOVE LEFT",
    "right":  "MOVE RIGHT",
    "throw":  "THROW",
    "pickup": "PICK UP",
}


class Settings:
    """Loads, saves, and applies all user preferences."""

    def __init__(self):
        self.resolution_idx: int   = 0
        self.fullscreen:     bool  = False
        self.music_vol:      float = 0.6
        self.keys:           dict  = dict(DEFAULT_KEYS)
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────
    def _load(self):
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
            self.resolution_idx = max(0, min(
                int(data.get("resolution_idx", self.resolution_idx)),
                len(RESOLUTIONS) - 1))
            self.fullscreen = bool(data.get("fullscreen", self.fullscreen))
            self.music_vol  = float(data.get("music_vol",  self.music_vol))
            for k in self.keys:
                if k in data.get("keys", {}):
                    self.keys[k] = int(data["keys"][k])
        except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError):
            pass

    def save(self):
        data = {
            "resolution_idx": self.resolution_idx,
            "fullscreen":     self.fullscreen,
            "music_vol":      round(self.music_vol, 2),
            "keys":           {k: int(v) for k, v in self.keys.items()},
        }
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    # ── Helpers ───────────────────────────────────────────────────────────────
    @property
    def resolution(self) -> tuple:
        return RESOLUTIONS[self.resolution_idx]

    def key_held(self, action: str, keys_pressed) -> bool:
        k = self.keys.get(action)
        return bool(keys_pressed[k]) if k is not None else False

    # ── Apply display (call after pygame.init) ────────────────────────────────
    def apply_display(self) -> pygame.Surface:
        w, h  = self.resolution
        flags = pygame.FULLSCREEN if self.fullscreen else 0
        screen = pygame.display.set_mode((w, h), flags)
        # Update module-level constants so camera/HUD use correct values
        constants.SCREEN_W = w
        constants.SCREEN_H = h
        return screen
