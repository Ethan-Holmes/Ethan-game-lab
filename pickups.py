"""
Field pickups: health packs and stamina (energy) packs on walkable ground.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, List, Optional

import pygame

import assets
import runtime as R
import settings as cfg
import world


@dataclass
class Pickup:
    x: float
    y: float
    kind: str  # "health" | "stamina"


def clear() -> None:
    R.field_pickups.clear()


def _pickup_count_for_wave(wave_number: int) -> int:
    w = max(1, wave_number)
    n = cfg.PICKUP_BASE_COUNT + (w - 1) // cfg.PICKUP_WAVE_EXTRA_INTERVAL
    return max(0, min(cfg.PICKUP_MAX_PER_WAVE, n))


def spawn_wave_pickups(px: float, py: float, tile_size: int, wave_number: int, rng: random.Random) -> None:
    """Place a batch of pickups away from the player; mix health / stamina."""
    n = _pickup_count_for_wave(wave_number)
    if n <= 0:
        return
    from waves import _cell_center_world, _collect_spawn_cells

    min_dist = cfg.PICKUP_SPAWN_MIN_DIST
    min_dist_sq = min_dist * min_dist
    cells = _collect_spawn_cells(px, py, tile_size, n * 8, min_dist_sq, rng)
    rng.shuffle(cells)
    placed = 0
    min_enemy_sq = (cfg.TILE_SIZE * 0.85) ** 2
    for mx, my in cells:
        if placed >= n:
            break
        cx, cy = _cell_center_world(mx, my, tile_size)
        jx = cx + rng.uniform(-9.0, 9.0)
        jy = cy + rng.uniform(-9.0, 9.0)
        if not world.can_walk_world(jx, jy, tile_size):
            continue
        blocked = False
        for e in R.enemies:
            if (e.x - jx) ** 2 + (e.y - jy) ** 2 < min_enemy_sq:
                blocked = True
                break
        if blocked:
            continue
        kind = "health" if rng.random() < 0.52 else "stamina"
        R.field_pickups.append(Pickup(jx, jy, kind))
        placed += 1


def collect_near_player(px: float, py: float) -> int:
    """Pick up any packs within radius; returns number collected."""
    if not R.field_pickups:
        return 0
    r2 = cfg.PICKUP_COLLECT_RADIUS ** 2
    got = 0
    i = 0
    while i < len(R.field_pickups):
        p = R.field_pickups[i]
        if (p.x - px) ** 2 + (p.y - py) ** 2 <= r2:
            if p.kind == "health":
                R.player_health = min(float(cfg.PLAYER_HP_MAX), R.player_health + cfg.PICKUP_HEALTH_AMOUNT)
            else:
                R.stamina = min(float(cfg.STAMINA_MAX), R.stamina + cfg.PICKUP_STAMINA_AMOUNT)
            assets.play_sfx(assets.SOUND_HIT)
            R.field_pickups.pop(i)
            got += 1
        else:
            i += 1
    return got


def draw_pickups(
    surface: pygame.Surface,
    px: float,
    py: float,
    yaw: float,
    ray_hits,
    screen_w: int,
    screen_h: int,
    fov: float,
    pitch_offset_px: float = 0.0,
    horizon_skew_px: float = 0.0,
) -> None:
    if not R.field_pickups:
        return
    proj_plane = (screen_w / 2) / math.tan(fov / 2)
    ordered = sorted(R.field_pickups, key=lambda p: -math.hypot(p.x - px, p.y - py))
    for p in ordered:
        pr = world.project_world_point_to_screen(
            px, py, p.x, p.y, yaw, ray_hits, screen_w, screen_h, fov, pitch_offset_px, horizon_skew_px
        )
        if pr is None:
            continue
        sx, hy, _ = pr
        dist = math.hypot(p.x - px, p.y - py)
        line_h = int(
            max(16, min(96, (cfg.PICKUP_BILLBOARD_HEIGHT_WORLD * proj_plane) / max(dist, 1.0)))
        )
        half_w = max(5, line_h // 2)
        top = int(hy - line_h * 0.88)
        col = cfg.PICKUP_HEALTH_COLOR if p.kind == "health" else cfg.PICKUP_STAMINA_COLOR
        try:
            pygame.draw.ellipse(surface, col, (sx - half_w, top, half_w * 2, line_h))
            pygame.draw.ellipse(surface, (255, 255, 248), (sx - half_w, top, half_w * 2, line_h), 2)
        except TypeError:
            pygame.draw.ellipse(surface, col, (sx - half_w, top, half_w * 2, line_h))
            pygame.draw.ellipse(surface, (255, 255, 248), (sx - half_w, top, half_w * 2, line_h), 2)
        # Plus / bolt hint
        mid_y = top + line_h // 2
        if p.kind == "health":
            pygame.draw.line(
                surface,
                (20, 40, 24),
                (sx - half_w // 2, mid_y),
                (sx + half_w // 2, mid_y),
                max(1, half_w // 5),
            )
            pygame.draw.line(
                surface,
                (20, 40, 24),
                (sx, mid_y - line_h // 4),
                (sx, mid_y + line_h // 4),
                max(1, half_w // 5),
            )
        else:
            pygame.draw.line(
                surface,
                (18, 32, 48),
                (sx - half_w // 3, top + line_h // 3),
                (sx + half_w // 3, top + 2 * line_h // 3),
                max(1, half_w // 6),
            )


def to_save_list() -> List[dict[str, Any]]:
    return [{"x": p.x, "y": p.y, "k": p.kind} for p in R.field_pickups]


def load_from_save(raw: Optional[List[Any]]) -> None:
    R.field_pickups.clear()
    if not raw:
        return
    for r in raw:
        if isinstance(r, dict):
            R.field_pickups.append(
                Pickup(float(r["x"]), float(r["y"]), str(r.get("k", "health")))
            )
