"""
Lightweight meta progression — separate from savegame.json (session saves stay F5/F9 compatible).

Tracks career stats, unlocks weapons / wall skins / starting blocks, and optional harder spawns.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, List

import runtime as R
import settings as cfg


META_VERSION = 1


@dataclass
class MetaProgress:
    version: int = META_VERSION
    lifetime_kills: int = 0
    waves_cleared_total: int = 0
    best_wave_reached: int = 0
    unlocked_weapon_slots: List[int] = field(default_factory=lambda: [1])
    bonus_start_blocks: int = 0
    wall_tier: int = 0  # 0 stone "1", 1 brick "2", 2 concrete "3"
    hostile_momentum: bool = False  # heavier spawn mix + rare elites
    claimed: List[str] = field(default_factory=list)


_data = MetaProgress()
_loaded = False


def _path() -> str:
    return getattr(cfg, "META_PROGRESS_PATH", os.path.join(cfg.SCRIPT_DIR, "meta_progress.json"))


def load() -> None:
    global _data, _loaded
    path = _path()
    if not os.path.isfile(path):
        _data = MetaProgress()
        _loaded = True
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        _data = MetaProgress()
        _loaded = True
        return
    if not isinstance(raw, dict):
        _data = MetaProgress()
        _loaded = True
        return
    uw = raw.get("unlocked_weapon_slots", [1])
    if not isinstance(uw, list):
        uw = [1]
    uw = [int(x) for x in uw if int(x) in (1, 2, 3)]
    if 1 not in uw:
        uw.insert(0, 1)
    cl = raw.get("claimed", [])
    if not isinstance(cl, list):
        cl = []
    _data = MetaProgress(
        version=int(raw.get("version", META_VERSION)),
        lifetime_kills=max(0, int(raw.get("lifetime_kills", 0))),
        waves_cleared_total=max(0, int(raw.get("waves_cleared_total", 0))),
        best_wave_reached=max(0, int(raw.get("best_wave_reached", 0))),
        unlocked_weapon_slots=sorted(set(uw)),
        bonus_start_blocks=max(0, min(int(raw.get("bonus_start_blocks", 0)), cfg.META_BONUS_BLOCKS_CAP)),
        wall_tier=max(0, min(2, int(raw.get("wall_tier", 0)))),
        hostile_momentum=bool(raw.get("hostile_momentum", False)),
        claimed=[str(x) for x in cl],
    )
    _reconcile_unlocks_from_stats()
    _loaded = True


def save() -> None:
    path = _path()
    payload = {
        "version": META_VERSION,
        "lifetime_kills": _data.lifetime_kills,
        "waves_cleared_total": _data.waves_cleared_total,
        "best_wave_reached": _data.best_wave_reached,
        "unlocked_weapon_slots": list(_data.unlocked_weapon_slots),
        "bonus_start_blocks": _data.bonus_start_blocks,
        "wall_tier": _data.wall_tier,
        "hostile_momentum": _data.hostile_momentum,
        "claimed": list(_data.claimed),
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except OSError:
        pass


def _claim(mid: str) -> bool:
    if mid in _data.claimed:
        return False
    _data.claimed.append(mid)
    return True


def _reconcile_unlocks_from_stats() -> None:
    """If file was edited or milestones added in an update, catch up."""
    changed = False
    if _data.waves_cleared_total >= 2 or _data.best_wave_reached >= 2:
        if 2 not in _data.unlocked_weapon_slots:
            _data.unlocked_weapon_slots.append(2)
            changed = True
    if _data.waves_cleared_total >= 4 or _data.best_wave_reached >= 4:
        if 3 not in _data.unlocked_weapon_slots:
            _data.unlocked_weapon_slots.append(3)
            changed = True
    if _data.lifetime_kills >= cfg.META_KILLS_WALL_TIER1 and _data.wall_tier < 1:
        _data.wall_tier = 1
        changed = True
    if _data.lifetime_kills >= cfg.META_KILLS_WALL_TIER2 and _data.wall_tier < 2:
        _data.wall_tier = 2
        changed = True
    if _data.lifetime_kills >= cfg.META_KILLS_START_BLOCKS and _data.bonus_start_blocks < cfg.META_BONUS_BLOCKS_STEP1:
        _data.bonus_start_blocks = max(_data.bonus_start_blocks, cfg.META_BONUS_BLOCKS_STEP1)
        changed = True
    if _data.lifetime_kills >= cfg.META_KILLS_START_BLOCKS2 and _data.bonus_start_blocks < cfg.META_BONUS_BLOCKS_STEP2:
        _data.bonus_start_blocks = max(_data.bonus_start_blocks, cfg.META_BONUS_BLOCKS_STEP2)
        changed = True
    if _data.best_wave_reached >= cfg.META_WAVE_HOSTILE_MOMENTUM or _data.lifetime_kills >= cfg.META_KILLS_HOSTILE_MOMENTUM:
        if not _data.hostile_momentum:
            _data.hostile_momentum = True
            changed = True
    if changed:
        save()


def ensure_loaded() -> None:
    if not _loaded:
        load()


def register_kill(count: int = 1) -> None:
    if count <= 0:
        return
    ensure_loaded()
    _data.lifetime_kills += count
    for line in _evaluate_kill_milestones():
        R.pending_progression_hints.append(line)
    save()


def _evaluate_kill_milestones() -> List[str]:
    msgs: List[str] = []
    if _data.lifetime_kills >= cfg.META_KILLS_WALL_TIER1 and _data.wall_tier < 1:
        _data.wall_tier = 1
        if _claim("wall_tier_1"):
            msgs.append("Wall skin: urban brick (placed walls)")
    if _data.lifetime_kills >= cfg.META_KILLS_WALL_TIER2 and _data.wall_tier < 2:
        _data.wall_tier = 2
        if _claim("wall_tier_2"):
            msgs.append("Wall skin: concrete cover panels")
    if _data.lifetime_kills >= cfg.META_KILLS_START_BLOCKS and _claim("bonus_blocks_1"):
        _data.bonus_start_blocks = max(_data.bonus_start_blocks, cfg.META_BONUS_BLOCKS_STEP1)
        msgs.append(f"+{cfg.META_BONUS_BLOCKS_STEP1} bonus starting blocks (career)")
    if _data.lifetime_kills >= cfg.META_KILLS_START_BLOCKS2 and _claim("bonus_blocks_2"):
        _data.bonus_start_blocks = min(
            cfg.META_BONUS_BLOCKS_CAP,
            max(_data.bonus_start_blocks, cfg.META_BONUS_BLOCKS_STEP2),
        )
        msgs.append(f"+{cfg.META_BONUS_BLOCKS_STEP2 - cfg.META_BONUS_BLOCKS_STEP1} more starting blocks")
    if _data.lifetime_kills >= cfg.META_KILLS_HOSTILE_MOMENTUM and _claim("hostile_momentum_kills"):
        _data.hostile_momentum = True
        msgs.append("Hostile momentum: tougher mixes & occasional elites")
    return msgs


def on_wave_cleared(wave_just_cleared: int) -> List[str]:
    """
    Call once when a wave is cleared (R.wave_number at that moment).
    Returns human-readable reward lines for the UI.
    """
    ensure_loaded()
    msgs: List[str] = list(R.pending_progression_hints)
    R.pending_progression_hints.clear()

    _data.waves_cleared_total += 1
    _data.best_wave_reached = max(_data.best_wave_reached, int(wave_just_cleared))

    if wave_just_cleared >= 2 and 2 not in _data.unlocked_weapon_slots:
        _data.unlocked_weapon_slots.append(2)
        _data.unlocked_weapon_slots.sort()
        msgs.append("Unlocked weapon: Rifle (press 2)")
    if wave_just_cleared >= 4 and 3 not in _data.unlocked_weapon_slots:
        _data.unlocked_weapon_slots.append(3)
        _data.unlocked_weapon_slots.sort()
        msgs.append("Unlocked weapon: Shotgun (press 3)")

    if wave_just_cleared >= cfg.META_WAVE_HOSTILE_MOMENTUM and _claim("hostile_momentum_wave"):
        _data.hostile_momentum = True
        msgs.append("Hostile momentum: armored squads & elite rolls")

    msgs.extend(_evaluate_kill_milestones())
    save()
    refresh_runtime_wall_char()
    return msgs


def record_game_over(wave_at_end: int) -> List[str]:
    """Update career peak; optional immediate messages (usually empty)."""
    ensure_loaded()
    _data.best_wave_reached = max(_data.best_wave_reached, int(wave_at_end))
    save()
    return []


def refresh_runtime_wall_char() -> None:
    R.player_placed_wall_char = placement_wall_char()


def placement_wall_char() -> str:
    ensure_loaded()
    return ("1", "2", "3")[_data.wall_tier]


def bonus_start_blocks() -> int:
    ensure_loaded()
    return int(_data.bonus_start_blocks)


def is_weapon_slot_unlocked(slot: int) -> bool:
    ensure_loaded()
    return int(slot) in _data.unlocked_weapon_slots


def weapon_unlock_flags() -> tuple[bool, bool, bool]:
    ensure_loaded()
    return (
        1 in _data.unlocked_weapon_slots,
        2 in _data.unlocked_weapon_slots,
        3 in _data.unlocked_weapon_slots,
    )


def preferred_weapon_index(current: int, weapon_count: int = 3) -> int:
    ensure_loaded()
    cur = max(0, min(weapon_count - 1, current))
    if is_weapon_slot_unlocked(cur + 1):
        return cur
    for i in range(weapon_count):
        if is_weapon_slot_unlocked(i + 1):
            return i
    return 0


def spawn_mix_pressure() -> float:
    """0..1 — shifts spawn table toward heavies."""
    ensure_loaded()
    return 0.28 if _data.hostile_momentum else 0.0


def roll_elite_spawn(rng) -> bool:
    ensure_loaded()
    if not _data.hostile_momentum:
        return False
    return rng.random() < cfg.META_ELITE_SPAWN_CHANCE


def career_summary_line() -> str:
    ensure_loaded()
    return (
        f"Career  {_data.lifetime_kills} kills  ·  best wave {_data.best_wave_reached}  ·  "
        f"{len(_data.unlocked_weapon_slots)}/3 weapons"
    )


def to_hud_career_compact() -> str:
    ensure_loaded()
    return f"★ {_data.lifetime_kills} kills  ·  best W{_data.best_wave_reached}"


def meta_snapshot_for_ui() -> dict[str, Any]:
    ensure_loaded()
    return {
        "lifetime_kills": _data.lifetime_kills,
        "best_wave": _data.best_wave_reached,
        "waves_cleared": _data.waves_cleared_total,
        "weapons_unlocked": len(_data.unlocked_weapon_slots),
        "bonus_blocks": _data.bonus_start_blocks,
        "wall_tier": _data.wall_tier,
        "hostile_momentum": _data.hostile_momentum,
    }
