"""
District and landmark generation for the procedural urban map.

All functions are deterministic from world block coordinates (bx, by) and
`R.world_gen_seed` so chunk streaming and save/load stay consistent.

- **District types** (`district_type_at_block`): each region of DISTRICT_BLOCKS_SPAN×
  city blocks shares one style (downtown glass, industrial metal, alleys, etc.).
- **Landmarks** (`try_landmark_cell`): rare 1-block footprints (water tower,
  checkpoint, fenced yard, plaza statue, warehouse façade) anchored to a block
  inside each district region.

`world.urban_cell` calls into this module after resolving roads/sidewalks and
computing alley geometry, but before generic building fill.
"""

from __future__ import annotations

import settings as cfg

# District ids (per region of DISTRICT_BLOCKS_SPAN × DISTRICT_BLOCKS_SPAN city blocks)
DIST_DOWNTOWN = 0
DIST_INDUSTRIAL = 1
DIST_ALLEY = 2
DIST_RESIDENTIAL = 3
DIST_PLAZA = 4

# Landmark kinds (internal — paired with try_landmark_cell)
_LM_WATER_TOWER = 0
_LM_CHECKPOINT = 1
_LM_FENCED_YARD = 2
_LM_PLAZA_STATUE = 3
_LM_WAREHOUSE = 4


def _mix_u32(*parts):
    h = 2166136261
    for p in parts:
        h = (h ^ (int(p) & 0xFFFFFFFF)) * 16777619 & 0xFFFFFFFF
    return h


def district_type_at_block(bx: int, by: int, seed: int) -> int:
    """
    Which district style applies to this city block.

    Regions are keyed by grouping blocks in squares of DISTRICT_BLOCKS_SPAN so
    adjacent chunks agree on district boundaries.
    """
    span = cfg.DISTRICT_BLOCKS_SPAN
    dbx = bx // span
    dby = by // span
    h = _mix_u32(dbx, dby, seed, 0xD15C)
    r = h % 100
    if r < 22:
        return DIST_DOWNTOWN
    if r < 42:
        return DIST_INDUSTRIAL
    if r < 58:
        return DIST_ALLEY
    if r < 78:
        return DIST_RESIDENTIAL
    return DIST_PLAZA


def shell_chars_for_district(dist: int, h: int) -> tuple[str, str]:
    """Primary / alternate building shell characters for procedural variety."""
    flip = (h & 0x100) == 0
    if dist == DIST_DOWNTOWN:
        return ("D", "D") if flip else ("D", "2")
    if dist == DIST_INDUSTRIAL:
        return ("W", "M") if flip else ("M", "W")
    if dist == DIST_ALLEY:
        return ("2", "1") if flip else ("1", "2")
    if dist == DIST_RESIDENTIAL:
        return ("L", "L") if flip else ("L", "2")
    if dist == DIST_PLAZA:
        return ("2", "L") if flip else ("L", "2")
    return ("1", "2")


def _landmark_anchor(bx: int, by: int, seed: int) -> tuple[int | None, int | None, int | None]:
    """
    If this district region hosts a landmark, return (kind, anchor_bx, anchor_by).
    Otherwise (None, None, None).
    """
    span = cfg.DISTRICT_BLOCKS_SPAN
    dbx = bx // span
    dby = by // span
    h = _mix_u32(dbx, dby, seed, 0x1A4D)
    if (h % 23) != 0:
        return None, None, None
    kind = (h >> 8) % 5
    abx = dbx * span + (h & 1)
    aby = dby * span + ((h >> 1) & 1)
    return kind, abx, aby


def try_landmark_cell(
    ix: int,
    iy: int,
    bx: int,
    by: int,
    rg: int,
    seed: int,
    alley_v: bool,
    alley_h: bool,
    vx: int,
    vy: int,
) -> str | None:
    """
    Return a landmark cell char for (ix, iy) in block (bx, by), or None.

    Requires 2 <= ix, iy <= rg - 2 (inner block). Alley cells must not be
    overwritten — caller should only invoke for inner coordinates that are not
    alley cuts.
    """
    kind, abx, aby = _landmark_anchor(bx, by, seed)
    if kind is None or bx != abx or by != aby:
        return None

    if kind == _LM_WATER_TOWER:
        if 2 <= ix <= 3 and 2 <= iy <= 3:
            return "T"
        return None

    if kind == _LM_FENCED_YARD:
        if alley_v or alley_h:
            return None
        if 2 <= ix <= 4 and 2 <= iy <= 4:
            if ix in (2, 4) or iy in (2, 4):
                return "E"
            return "f"
        return None

    if kind == _LM_PLAZA_STATUE:
        if ix == rg // 2 and iy == rg // 2:
            return "S"
        return None

    if kind == _LM_WAREHOUSE:
        if iy == 2 and 2 <= ix <= 4:
            return "W"
        return None

    return None


def try_landmark_sidewalk_cell(
    bx: int,
    by: int,
    rg: int,
    ix: int,
    iy: int,
    seed: int,
) -> str | None:
    """
    Checkpoint pillars sit on the inner sidewalk ring (shared with landmark anchor block).
    Called from world.urban_cell before generic sidewalk props.
    """
    kind, abx, aby = _landmark_anchor(bx, by, seed)
    if kind != _LM_CHECKPOINT or bx != abx or by != aby:
        return None
    if iy == 1 and ix in (2, 3):
        return "K"
    return None


def is_plaza_center_cell(ix: int, iy: int, rg: int, dist: int) -> bool:
    """True if this inner cell should be plaza pavement (PLAZA district)."""
    if dist != DIST_PLAZA:
        return False
    return 2 <= ix <= 4 and 2 <= iy <= 4


def alley_flags_for_district(dist: int, h: int, h2: int) -> tuple[bool, bool]:
    """
    Vertical / horizontal alley presence. ALLEY district forces both for a dense grid.
    """
    if dist == DIST_ALLEY:
        return True, True
    alley_v = (h >> 16) & 3 == 0
    alley_h = (h2 >> 16) & 3 == 0
    return alley_v, alley_h


def env_prop_density_shift(dist: int) -> float:
    """Multiplier for prop roll thresholds in _apply_env_props (1.0 = default)."""
    if dist == DIST_INDUSTRIAL:
        return 1.18
    if dist == DIST_RESIDENTIAL:
        return 0.92
    if dist == DIST_DOWNTOWN:
        return 1.08
    if dist == DIST_PLAZA:
        return 0.78
    if dist == DIST_ALLEY:
        return 1.05
    return 1.0


def display_name(dist: int) -> str:
    """Short HUD / minimap label for the district style at the player."""
    if dist == DIST_DOWNTOWN:
        return "Downtown core"
    if dist == DIST_INDUSTRIAL:
        return "Industrial yard"
    if dist == DIST_ALLEY:
        return "Back-alley grid"
    if dist == DIST_RESIDENTIAL:
        return "Residential blocks"
    if dist == DIST_PLAZA:
        return "Civic plaza"
    return "Urban sector"


def floor_rgb_multipliers(dist: int) -> tuple[float, float, float]:
    """Subtle per-district floor tint (multipliers on base floor RGB)."""
    if dist == DIST_INDUSTRIAL:
        return (0.94, 0.95, 1.04)
    if dist == DIST_PLAZA:
        return (1.05, 1.03, 0.98)
    if dist == DIST_RESIDENTIAL:
        return (1.02, 1.01, 0.97)
    if dist == DIST_ALLEY:
        return (0.96, 0.96, 1.02)
    if dist == DIST_DOWNTOWN:
        return (1.02, 1.02, 1.05)
    return (1.0, 1.0, 1.0)


def ambient_weights(dist: int) -> dict[str, float]:
    """
    Relative weights for ambient layers (wind / traffic / industrial hum).
    Used by ambient.py; values are 0..1-ish and blended with road proximity.
    """
    if dist == DIST_INDUSTRIAL:
        return {"wind": 0.35, "traffic": 0.25, "industrial": 0.95}
    if dist == DIST_DOWNTOWN:
        return {"wind": 0.45, "traffic": 0.85, "industrial": 0.25}
    if dist == DIST_ALLEY:
        return {"wind": 0.55, "traffic": 0.35, "industrial": 0.45}
    if dist == DIST_RESIDENTIAL:
        return {"wind": 0.65, "traffic": 0.55, "industrial": 0.15}
    if dist == DIST_PLAZA:
        return {"wind": 0.5, "traffic": 0.6, "industrial": 0.2}
    return {"wind": 0.5, "traffic": 0.5, "industrial": 0.35}


# Cumulative sidewalk prop thresholds (0..255) before scaling — see world._cum_prop.
# Order: car, lamp, dumpster, barrier, crate, utility box.
_SIDECAR_CUM = {
    DIST_DOWNTOWN: [16, 34, 46, 56, 64, 70],
    DIST_INDUSTRIAL: [10, 22, 44, 62, 78, 88],
    DIST_ALLEY: [8, 20, 42, 56, 66, 72],
    DIST_RESIDENTIAL: [22, 38, 50, 60, 68, 74],
    DIST_PLAZA: [12, 32, 44, 54, 64, 70],
}
_LOT_CUM = {
    DIST_DOWNTOWN: [46, 60, 72, 82, 90, 96],
    DIST_INDUSTRIAL: [42, 58, 78, 90, 98, 104],
    DIST_ALLEY: [44, 58, 74, 86, 94, 100],
    DIST_RESIDENTIAL: [50, 64, 76, 86, 94, 100],
    DIST_PLAZA: [48, 62, 74, 84, 92, 98],
}
_ALLEY_CUM = {
    DIST_DOWNTOWN: [18, 36, 52, 64, 74, 80],
    DIST_INDUSTRIAL: [16, 32, 54, 70, 82, 90],
    DIST_ALLEY: [14, 30, 50, 66, 78, 86],
    DIST_RESIDENTIAL: [20, 38, 56, 68, 78, 84],
    DIST_PLAZA: [18, 36, 52, 66, 76, 82],
}
_PLAZA_CUM = [22, 40, 52, 62, 70, 76]


def sidewalk_prop_cumulative(dist: int) -> list[int]:
    return list(_SIDECAR_CUM.get(dist, _SIDECAR_CUM[DIST_DOWNTOWN]))


def lot_prop_cumulative(dist: int) -> list[int]:
    return list(_LOT_CUM.get(dist, _LOT_CUM[DIST_DOWNTOWN]))


def alley_road_prop_cumulative(dist: int) -> list[int]:
    return list(_ALLEY_CUM.get(dist, _ALLEY_CUM[DIST_DOWNTOWN]))


def plaza_prop_cumulative(dist: int) -> list[int]:
    if dist == DIST_PLAZA:
        return list(_PLAZA_CUM)
    if dist == DIST_DOWNTOWN:
        return [20, 38, 50, 60, 68, 74]
    return [24, 42, 54, 64, 72, 78]
