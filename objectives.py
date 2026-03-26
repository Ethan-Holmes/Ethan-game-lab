"""
Per-wave mission objectives layered on top of the existing wave spawn / scaling system.

Adding a new objective: extend WAVE_OBJECTIVE_ROTATION or pick_kind_for_wave, handle the kind
in apply_start / tick / is_satisfied, and add HUD strings in hud_objective_lines.
"""

from __future__ import annotations

import math
import random
import time
from typing import Any, Dict, List, Optional, Tuple

import runtime as R
import settings as cfg
import world

# Objective ids (stable for saves)
OBJ_CLEAR = "clear_hostiles"
OBJ_HOLD = "hold_position"
OBJ_REACH = "reach_marker"
OBJ_DEFEND = "defend_zone"
OBJ_AMBUSH = "ambush_survive"

# Wave N (1-based) uses rotation[(N - 1) % len]; tweak order for pacing.
WAVE_OBJECTIVE_ROTATION: List[str] = [
    OBJ_CLEAR,
    OBJ_REACH,
    OBJ_HOLD,
    OBJ_CLEAR,
    OBJ_DEFEND,
    OBJ_AMBUSH,
    OBJ_HOLD,
]


def pick_kind_for_wave(wave_n: int, rng: random.Random) -> str:
    """Deterministic variety from wave index, with a small shuffle on high waves."""
    base = WAVE_OBJECTIVE_ROTATION[(max(1, wave_n) - 1) % len(WAVE_OBJECTIVE_ROTATION)]
    if wave_n >= 5 and rng.random() < 0.18:
        alts = [OBJ_CLEAR, OBJ_REACH, OBJ_AMBUSH]
        return rng.choice(alts)
    return base


def spawn_style_for_kind(kind: str) -> str:
    return "ambush" if kind == OBJ_AMBUSH else "normal"


def _find_reach_point(px: float, py: float, tile_size: float, rng: random.Random) -> Tuple[float, float]:
    """Walkable cell ring around the player for rally / exfil markers."""
    pmx = int(math.floor(px / tile_size))
    pmy = int(math.floor(py / tile_size))
    min_tiles = max(6, int(cfg.OBJECTIVE_REACH_MIN_TILES))
    max_tiles = max(min_tiles + 2, int(cfg.OBJECTIVE_REACH_MAX_TILES))
    for radius in range(min_tiles, max_tiles + 1):
        candidates = []
        for mx in range(pmx - radius, pmx + radius + 1):
            for my in range(pmy - radius, pmy + radius + 1):
                if max(abs(mx - pmx), abs(my - pmy)) != radius:
                    continue
                if not world.is_walkable_cell(world.sample_world_cell(mx, my)):
                    continue
                cx, cy = (mx + 0.5) * tile_size, (my + 0.5) * tile_size
                if math.hypot(cx - px, cy - py) < min_tiles * tile_size * 0.92:
                    continue
                candidates.append((cx, cy))
        if candidates:
            return rng.choice(candidates)
    return px + min_tiles * tile_size, py


def _titles(kind: str) -> Tuple[str, str]:
    if kind == OBJ_CLEAR:
        return ("Clear hostiles", "Eliminate all threats in the sector.")
    if kind == OBJ_AMBUSH:
        return ("Survive ambush", "Close-range contact — clear all hostiles.")
    if kind == OBJ_HOLD:
        return ("Hold extraction", f"Stay in the marked zone for {int(cfg.OBJECTIVE_HOLD_SECONDS)}s.")
    if kind == OBJ_DEFEND:
        return ("Defend sector", f"Hold the zone under fire ({int(cfg.OBJECTIVE_DEFEND_SECONDS)}s).")
    if kind == OBJ_REACH:
        return ("Reach rally point", "Move to the waypoint on your minimap.")
    return ("Mission", "Complete the objective.")


def apply_start(kind: str, wave_n: int, px: float, py: float, rng: random.Random) -> None:
    """Call right after a wave spawns (player position = op start)."""
    R.objective_kind = kind
    R.objective_wave = wave_n
    R.obj_hold_progress = 0.0
    title, detail = _titles(kind)
    R.objective_title = title
    R.objective_detail = detail
    R.objective_intro_until_monotonic = time.monotonic() + cfg.OBJECTIVE_INTRO_BANNER_SEC

    if kind in (OBJ_HOLD, OBJ_DEFEND):
        R.obj_anchor_x = px
        R.obj_anchor_y = py
        if kind == OBJ_HOLD:
            R.obj_zone_radius = cfg.OBJECTIVE_HOLD_RADIUS
            R.obj_hold_required = cfg.OBJECTIVE_HOLD_SECONDS
        else:
            R.obj_zone_radius = cfg.OBJECTIVE_DEFEND_RADIUS
            R.obj_hold_required = cfg.OBJECTIVE_DEFEND_SECONDS
        R.obj_target_x = R.obj_target_y = 0.0
    elif kind == OBJ_REACH:
        tx, ty = _find_reach_point(px, py, cfg.TILE_SIZE, rng)
        R.obj_target_x = tx
        R.obj_target_y = ty
        R.obj_zone_radius = cfg.OBJECTIVE_REACH_RADIUS
        R.obj_hold_required = 0.0
        R.obj_anchor_x = R.obj_anchor_y = 0.0
    else:
        R.obj_anchor_x = R.obj_anchor_y = 0.0
        R.obj_target_x = R.obj_target_y = 0.0
        R.obj_zone_radius = 0.0
        R.obj_hold_required = 0.0


def migrate_legacy_no_save() -> None:
    """Older saves without objective blob — assume classic elimination."""
    R.objective_kind = OBJ_CLEAR
    R.objective_wave = R.wave_number
    R.objective_title, R.objective_detail = _titles(OBJ_CLEAR)
    R.obj_hold_progress = 0.0
    R.obj_anchor_x = R.obj_anchor_y = 0.0
    R.obj_target_x = R.obj_target_y = 0.0
    R.obj_zone_radius = 0.0
    R.obj_hold_required = 0.0
    R.objective_intro_until_monotonic = 0.0


def to_save_dict() -> Dict[str, Any]:
    return {
        "k": R.objective_kind,
        "w": R.objective_wave,
        "t": R.objective_title,
        "d": R.objective_detail,
        "hp": R.obj_hold_progress,
        "ax": R.obj_anchor_x,
        "ay": R.obj_anchor_y,
        "tx": R.obj_target_x,
        "ty": R.obj_target_y,
        "zr": R.obj_zone_radius,
        "hr": R.obj_hold_required,
    }


def load_from_save_dict(raw: Optional[Dict[str, Any]]) -> None:
    if not raw:
        migrate_legacy_no_save()
        return
    R.objective_kind = str(raw.get("k", OBJ_CLEAR))
    R.objective_wave = int(raw.get("w", R.wave_number))
    R.objective_title = str(raw.get("t", _titles(R.objective_kind)[0]))
    R.objective_detail = str(raw.get("d", _titles(R.objective_kind)[1]))
    R.obj_hold_progress = float(raw.get("hp", 0.0))
    R.obj_anchor_x = float(raw.get("ax", 0.0))
    R.obj_anchor_y = float(raw.get("ay", 0.0))
    R.obj_target_x = float(raw.get("tx", 0.0))
    R.obj_target_y = float(raw.get("ty", 0.0))
    R.obj_zone_radius = float(raw.get("zr", 0.0))
    R.obj_hold_required = float(raw.get("hr", 0.0))
    R.objective_intro_until_monotonic = 0.0


def tick(dt: float) -> None:
    """Progress hold/defend timers while PLAYING."""
    if R.game_state != R.STATE_PLAYING or not R.wave_in_progress:
        return
    k = R.objective_kind
    px, py = R.player_x, R.player_y
    if k == OBJ_HOLD:
        d = math.hypot(px - R.obj_anchor_x, py - R.obj_anchor_y)
        if d <= R.obj_zone_radius:
            R.obj_hold_progress += dt
        else:
            R.obj_hold_progress = max(0.0, R.obj_hold_progress - dt * cfg.OBJECTIVE_HOLD_LEAK_DECAY)
    elif k == OBJ_DEFEND:
        d = math.hypot(px - R.obj_anchor_x, py - R.obj_anchor_y)
        in_zone = d <= R.obj_zone_radius
        pressured = len(R.enemies) > 0
        if in_zone and pressured:
            R.obj_hold_progress += dt
        elif in_zone and not pressured:
            R.obj_hold_progress += dt * 0.35
        else:
            R.obj_hold_progress = max(0.0, R.obj_hold_progress - dt * cfg.OBJECTIVE_DEFEND_LEAK_DECAY)


def is_satisfied() -> bool:
    if not R.wave_in_progress:
        return False
    k = R.objective_kind
    if k in (OBJ_CLEAR, OBJ_AMBUSH):
        return len(R.enemies) == 0
    if k == OBJ_REACH:
        d = math.hypot(R.player_x - R.obj_target_x, R.player_y - R.obj_target_y)
        return d <= R.obj_zone_radius
    if k in (OBJ_HOLD, OBJ_DEFEND):
        return R.obj_hold_progress >= R.obj_hold_required
    return len(R.enemies) == 0


def hud_objective_lines() -> Tuple[str, str, Optional[float]]:
    """
    Primary line, secondary line, optional progress 0..1 for bar (None = no bar).
    """
    k = R.objective_kind
    if k in (OBJ_CLEAR, OBJ_AMBUSH):
        n = len(R.enemies)
        return (R.objective_title, f"Remaining: {n}" if n else "Sector clear — stand by", None if n else 1.0)
    if k == OBJ_REACH:
        d = math.hypot(R.player_x - R.obj_target_x, R.player_y - R.obj_target_y)
        r = max(R.obj_zone_radius, 1.0)
        # bar = how close (inverse): 1 at center
        close = max(0.0, 1.0 - min(1.0, d / (r * 6.0)))
        return (R.objective_title, f"Distance ~{int(d)}u  ·  Rally on map", close)
    if k in (OBJ_HOLD, OBJ_DEFEND):
        req = max(R.obj_hold_required, 0.01)
        pct = min(1.0, R.obj_hold_progress / req)
        d = math.hypot(R.player_x - R.obj_anchor_x, R.player_y - R.obj_anchor_y)
        st = "In zone" if d <= R.obj_zone_radius else "Return to zone!"
        return (R.objective_title, f"{st}  ·  {int(pct * 100)}%", pct)
    return (R.objective_title, R.objective_detail, None)


def wave_complete_subtitle() -> str:
    k = R.objective_kind
    if k == OBJ_REACH:
        return "Rally point secured"
    if k == OBJ_HOLD:
        return "Extraction hold complete"
    if k == OBJ_DEFEND:
        return "Sector defense successful"
    if k == OBJ_AMBUSH:
        return "Ambush neutralized"
    return "Hostiles eliminated"


def minimap_objective() -> Optional[Tuple[str, float, float, float]]:
    """kind tag, wx, wy, radius_world — or None."""
    k = R.objective_kind
    if k == OBJ_REACH:
        return ("reach", R.obj_target_x, R.obj_target_y, R.obj_zone_radius)
    if k in (OBJ_HOLD, OBJ_DEFEND):
        return ("zone", R.obj_anchor_x, R.obj_anchor_y, R.obj_zone_radius)
    return None
