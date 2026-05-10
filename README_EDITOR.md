# Neon Miami — Level Editor

## Launch

```
python editor.py              # blank level
python editor.py levels/x.json  # open existing
python main.py                # default hardcoded level
python main.py --level levels/x.json  # custom level
```

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `1–8` | Select tile / entity |
| `B` | Brush (paint while held) |
| `F` | Flood fill (4-connected) |
| `E` | Eraser |
| `R` | Rectangle (click + drag) |
| `L` | Line (Bresenham, click + drag) |
| `G` | Toggle grid |
| `Tab` | Toggle preview mode |
| `H` | Help overlay |
| `Del` | Delete selected entity |
| `Ctrl+Z` | Undo (50 levels) |
| `Ctrl+Y` | Redo |
| `Ctrl+S` | Save → levels/current.json |
| `Ctrl+O` | Open file dialog |
| `N` | New level (enter W × H) |
| `F5` | Save + launch game with this level |

## Mouse

| Input | Action |
|-------|--------|
| Left click | Paint active tile / place entity |
| Right click | Erase (place floor) |
| Shift + left | Pipette (copy tile under cursor) |
| Middle + drag | Pan canvas |
| Scroll wheel | Zoom (×0.5 – ×4) |
| Click entity | Select it (then Del to remove) |

## Tile types

| Key | Type | Description |
|-----|------|-------------|
| `1` | floor | Open floor |
| `2` | wall_thin | Destructible wall (HP 2) |
| `3` | wall_solid | Structural wall (HP 999) |
| `4` | floor_parquet | Parquet floor (cosmetic) |

## Entities

| Key | Type | Properties |
|-----|------|-----------|
| `5` | Player spawn | Unique — required |
| `6` | Enemy | weapon, patrol, vision |
| `7` | Weapon pickup | pistol / shotgun / bat / katana |
| `8` | Exit trigger | Unique — ends level |

## Level JSON format

```json
{
  "meta": { "name": "my_level", "width": 60, "height": 38,
            "tile_size": 16, "version": 2 },
  "tiles": [[0,1,1,...], ...],
  "entities": [
    {"type": "player_spawn", "gx": 2, "gy": 2},
    {"type": "enemy", "gx": 12, "gy": 5,
     "weapon": "shotgun", "patrol": "loop", "vision": "wide"},
    {"type": "weapon_pickup", "gx": 8, "gy": 3, "weapon": "uzi"},
    {"type": "exit_trigger", "gx": 58, "gy": 36}
  ]
}
```
