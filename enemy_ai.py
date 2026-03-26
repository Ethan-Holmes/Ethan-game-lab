"""
Rule-based enemy AI: idle, patrol, chase, attack, search.

State numbers match settings.ENEMY_ST_*. Per-type tuning lives in enemy_types.EnemyTypeSpec.
"""

from __future__ import annotations

import math
import random
from typing import Tuple

import settings as cfg
import world


def _has_los_to_player(ex: float, ey: float, px: float, py: float, tile_size: float) -> bool:
    """Ray from enemy to player clears walls (same idea as enemy.clear_shot_to_player)."""
    dx = px - ex
    dy = py - ey
    dist_p = math.hypot(dx, dy)
    if dist_p < 1e-6:
        return True
    ang = math.atan2(dy, dx)
    d_wall, _mx, _my, _side, hx, hy, _wc = world.cast_ray(ex, ey, ang, tile_size)
    if math.isinf(d_wall):
        return True
    dist_w = math.hypot(hx - ex, hy - ey)
    return dist_w >= dist_p - cfg.ENEMY_SHOOT_LOS_EPS


def _ranges(sp):
    """Effective detection / combat distances for this archetype."""
    return (
        cfg.ENEMY_DETECT_RANGE * sp.detect_range_mult,
        cfg.ENEMY_LOST_RANGE * sp.lost_range_mult,
        cfg.ENEMY_ATTACK_RANGE * sp.attack_range_mult,
        cfg.ENEMY_ATTACK_LEAVE_RANGE * sp.attack_leave_range_mult,
    )


def _calm_state(sp):
    return cfg.ENEMY_ST_PATROL if sp.prefers_patrol_when_calm else cfg.ENEMY_ST_IDLE


def _awareness_ok(dist: float, has_los: bool) -> bool:
    """Player counts as “noticed” for committing to CHASE (sight or very close)."""
    return has_los or dist <= cfg.ENEMY_HEAR_RANGE


def _update_aggro_state(e, sp, dist: float, has_los: bool, px: float, py: float, dt: float) -> None:
    """
    Hysteresis + LOS: lose sight while still inside lost-range → SEARCH at last known point.
    Calm → CHASE only after a short alert delay (staggered spawns).
    """
    d_det, d_lost, a_in, a_out = _ranges(sp)
    st = e.ai_state

    if dist > d_lost:
        e.ai_state = _calm_state(sp)
        e.search_timer = 0.0
        e.acquire_delay = e.acquire_delay_reset
        return

    if has_los and st in (cfg.ENEMY_ST_CHASE, cfg.ENEMY_ST_ATTACK, cfg.ENEMY_ST_SEARCH):
        e.last_seen_px, e.last_seen_py = px, py

    # --- SEARCH ---
    if st == cfg.ENEMY_ST_SEARCH:
        e.search_timer -= dt
        if has_los:
            e.ai_state = cfg.ENEMY_ST_CHASE
        elif e.search_timer <= 0.0:
            e.ai_state = _calm_state(sp)
            e.patrol_ox = e.last_seen_px
            e.patrol_oy = e.last_seen_py
            e.acquire_delay = e.acquire_delay_reset
        return

    in_detect = dist <= d_det and _awareness_ok(dist, has_los)

    # Broke LOS while still engaged → investigate (not if we’re already in knife-fight range).
    if st in (cfg.ENEMY_ST_CHASE, cfg.ENEMY_ST_ATTACK) and not has_los:
        if dist > cfg.ENEMY_HEAR_RANGE * 1.05:
            e.ai_state = cfg.ENEMY_ST_SEARCH
            e.search_timer = cfg.ENEMY_SEARCH_DURATION * sp.search_duration_mult
            return

    if not in_detect:
        if st in (cfg.ENEMY_ST_CHASE, cfg.ENEMY_ST_ATTACK):
            if not has_los:
                e.ai_state = cfg.ENEMY_ST_SEARCH
                e.search_timer = cfg.ENEMY_SEARCH_DURATION * sp.search_duration_mult
                return
            # Still have LOS past the inner detect ring — keep pushing (memory is outer lost range).
        else:
            e.ai_state = _calm_state(sp)
            e.acquire_delay = e.acquire_delay_reset
            return

    # in_detect — calm states commit after alert delay
    if st in (cfg.ENEMY_ST_IDLE, cfg.ENEMY_ST_PATROL):
        e.acquire_delay -= dt
        if e.acquire_delay <= 0.0:
            e.ai_state = cfg.ENEMY_ST_CHASE
            e.last_seen_px, e.last_seen_py = px, py
        return

    # CHASE / ATTACK band hysteresis
    if st == cfg.ENEMY_ST_CHASE and dist <= a_in:
        e.ai_state = cfg.ENEMY_ST_ATTACK
    elif st == cfg.ENEMY_ST_ATTACK and dist > a_out:
        e.ai_state = cfg.ENEMY_ST_CHASE


def _separation(e_idx: int, enemies, radius: float) -> Tuple[float, float]:
    """Push vector away from nearby allies (scaled 0..~1)."""
    ex, ey = enemies[e_idx].x, enemies[e_idx].y
    sx, sy = 0.0, 0.0
    for j, o in enumerate(enemies):
        if j == e_idx:
            continue
        dx = ex - o.x
        dy = ey - o.y
        d = math.hypot(dx, dy)
        if d < 1e-5 or d >= radius:
            continue
        pen = (radius - d) / max(radius, 1e-5)
        inv = 1.0 / d
        sx += dx * inv * pen
        sy += dy * inv * pen
    return sx, sy


def _blend_dir(mx: float, my: float, sx: float, sy: float, sep_w: float) -> Tuple[float, float]:
    fx = mx + sx * sep_w
    fy = my + sy * sep_w
    mag = math.hypot(fx, fy)
    if mag < 1e-6:
        return 0.0, 0.0
    return fx / mag, fy / mag


def _patrol_heading(e, sp, dt: float) -> Tuple[float, float]:
    """Wander near patrol anchor; steer back if too far."""
    dx = e.x - e.patrol_ox
    dy = e.y - e.patrol_oy
    d = math.hypot(dx, dy)
    pr = sp.patrol_radius
    if d > pr:
        inv = 1.0 / max(d, 1e-5)
        return -dx * inv, -dy * inv
    jitter = cfg.ENEMY_WANDER_TURN_MAX * sp.patrol_wander_mult
    e.wander_heading += random.uniform(-jitter, jitter) * dt
    c = math.cos(e.wander_heading)
    s = math.sin(e.wander_heading)
    return c, s


def _attack_move(e, sp, dx: float, dy: float, dist: float, dt: float) -> Tuple[float, float]:
    """Standoff + strafe; speed varies by type."""
    shoot_r = cfg.ENEMY_SHOOT_RANGE
    lo = shoot_r * sp.attack_standoff_min_frac
    hi = shoot_r * sp.attack_standoff_max_frac
    sm = sp.attack_strafe_mult
    e.strafe_phase += dt * (2.1 + 0.12 * math.sin(e.patrol_ox * 0.02 + e.patrol_oy * 0.02)) * sm
    if dist < 1e-5:
        return 0.0, 0.0
    ux, uy = dx / dist, dy / dist
    px, py = -uy, ux
    if dist < lo:
        return -ux, -uy
    if dist > hi:
        return ux, uy
    w = math.sin(e.strafe_phase)
    return px * w, py * w


def _chase_heading(e, sp, dx: float, dy: float, dist: float) -> Tuple[float, float]:
    """Move toward player with optional flank offset (scouts circle, heavies march in)."""
    if dist < 1e-5:
        return 0.0, 0.0
    ux, uy = dx / dist, dy / dist
    px, py = -uy, ux
    f = sp.chase_flank_bias
    if f < 1e-6:
        return ux, uy
    side = math.sin(e.strafe_phase * 0.85 + e.patrol_ox * 0.01)
    fx = ux + px * f * side
    fy = uy + py * f * side
    m = math.hypot(fx, fy)
    if m < 1e-6:
        return ux, uy
    return fx / m, fy / m


def _search_heading(e, sp, dt: float) -> Tuple[float, float]:
    """Go to last seen; small wander when close."""
    dx = e.last_seen_px - e.x
    dy = e.last_seen_py - e.y
    d = math.hypot(dx, dy)
    if d < 36.0:
        jitter = cfg.ENEMY_WANDER_TURN_MAX * (0.55 + 0.35 * sp.patrol_wander_mult)
        e.wander_heading += random.uniform(-jitter, jitter) * dt
        c = math.cos(e.wander_heading)
        s = math.sin(e.wander_heading)
        return c, s
    inv = 1.0 / d
    return dx * inv, dy * inv


def _try_slide(ex, ey, mx, my, step, tile_size):
    for scale in (1.0, 0.55, 0.28):
        s = step * scale
        nx = ex + mx * s
        ny = ey + my * s
        if world.can_walk_world(nx, ny, tile_size):
            return nx, ny
        if world.can_walk_world(nx, ey, tile_size):
            return nx, ey
        if world.can_walk_world(ex, ny, tile_size):
            return ex, ny
    return ex, ey


def tick(enemies, px: float, py: float, dt: float, tile_size: float) -> None:
    """Advance AI for one frame."""
    for i, e in enumerate(enemies):
        sp = e.spec()
        dx = px - e.x
        dy = py - e.y
        dist_sq = dx * dx + dy * dy
        if dist_sq < 1e-8:
            continue
        dist = math.sqrt(dist_sq)

        has_los = _has_los_to_player(e.x, e.y, px, py, tile_size)
        _update_aggro_state(e, sp, dist, has_los, px, py, dt)

        sx, sy = _separation(i, enemies, sp.separation_radius)
        sep_w = sp.separation_weight * cfg.ENEMY_SEPARATION_BLEND

        st = e.ai_state
        mx, my = 0.0, 0.0

        if st == cfg.ENEMY_ST_IDLE:
            mx, my = 0.0, 0.0
        elif st == cfg.ENEMY_ST_PATROL:
            mx, my = _patrol_heading(e, sp, dt)
        elif st == cfg.ENEMY_ST_CHASE:
            e.strafe_phase += dt * (1.2 + 0.35 * sp.chase_flank_bias)
            if dist >= cfg.ENEMY_MIN_MOVE_DIST:
                mx, my = _chase_heading(e, sp, dx, dy, dist)
        elif st == cfg.ENEMY_ST_ATTACK:
            mx, my = _attack_move(e, sp, dx, dy, dist, dt)
        elif st == cfg.ENEMY_ST_SEARCH:
            mx, my = _search_heading(e, sp, dt)

        mx, my = _blend_dir(mx, my, sx, sy, sep_w)

        if st == cfg.ENEMY_ST_IDLE and math.hypot(mx, my) < 1e-6:
            mx, my = _blend_dir(0.0, 0.0, sx, sy, sep_w)
            if mx == 0.0 and my == 0.0:
                continue

        if dist < cfg.ENEMY_MIN_MOVE_DIST and st not in (
            cfg.ENEMY_ST_ATTACK,
            cfg.ENEMY_ST_CHASE,
            cfg.ENEMY_ST_SEARCH,
        ):
            if st == cfg.ENEMY_ST_IDLE:
                continue
            if math.hypot(mx, my) < 1e-6:
                continue

        if dist < cfg.ENEMY_MIN_MOVE_DIST and st == cfg.ENEMY_ST_CHASE and math.hypot(mx, my) < 1e-6:
            continue

        step = sp.speed * dt
        nx, ny = _try_slide(e.x, e.y, mx, my, step, tile_size)
        e.x, e.y = nx, ny
