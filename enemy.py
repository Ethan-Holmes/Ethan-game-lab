"""
Enemy entities: AI, shooting, and 3D billboards.

Each enemy is an `Enemy` row with a `type_key` into `enemy_types.TYPES` (Grunt, Heavy, Scout, …).
To add a new class, define it in enemy_types.py and optional assets/<sprite_file>.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

import assets
import enemy_ai
import enemy_types as et
import runtime as R
import settings as cfg
import world


@dataclass
class Enemy:
    """One living enemy in the world (mutated each frame by AI / combat)."""

    type_key: str
    x: float
    y: float
    wander_heading: float
    hp: float
    shoot_cd: float
    ai_state: int
    combat_scale: float = 1.0
    hit_flash_timer: float = 0.0
    patrol_ox: float = 0.0
    patrol_oy: float = 0.0
    strafe_phase: float = 0.0

    def spec(self) -> et.EnemyTypeSpec:
        return et.get_spec(self.type_key)


def create_enemy(
    type_key: str,
    x: float,
    y: float,
    rng: random.Random,
    wave_number: int = 1,
) -> Enemy:
    """Spawn with wave-scaled HP and outgoing damage (combat_scale)."""
    sp = et.get_spec(type_key)
    hp_mult = cfg.wave_hp_multiplier(wave_number)
    d_mult = cfg.wave_damage_multiplier(wave_number)
    calm = cfg.ENEMY_ST_PATROL if sp.prefers_patrol_when_calm else cfg.ENEMY_ST_IDLE
    return Enemy(
        type_key=type_key,
        x=x,
        y=y,
        wander_heading=rng.uniform(0, 2 * math.pi),
        hp=sp.max_hp * hp_mult,
        shoot_cd=rng.uniform(0, sp.shoot_cooldown * 0.9),
        ai_state=calm,
        combat_scale=d_mult,
        hit_flash_timer=0.0,
        patrol_ox=x,
        patrol_oy=y,
        strafe_phase=rng.uniform(0, 2 * math.pi),
    )


def to_save_dict(e: Enemy) -> dict:
    """JSON-friendly dict (used by game_flow.save_game_to_file)."""
    return {
        "type": e.type_key,
        "x": e.x,
        "y": e.y,
        "w": e.wander_heading,
        "hp": e.hp,
        "cd": e.shoot_cd,
        "ai": e.ai_state,
        "cs": e.combat_scale,
        "ai_mode": "v2",
        "pox": e.patrol_ox,
        "poy": e.patrol_oy,
        "sf": e.strafe_phase,
    }


def from_save_obj(raw) -> Enemy:
    """
    Restore from save. Supports:
      - dict (version 2+)
      - list of 6 numbers (legacy v1 Grunt-only rows)
    """
    if isinstance(raw, dict):
        px = float(raw["x"])
        py = float(raw["y"])
        ai = int(raw["ai"])
        if raw.get("ai_mode") != "v2":
            if ai == 0:
                ai = cfg.ENEMY_ST_PATROL
            elif ai == 1:
                ai = cfg.ENEMY_ST_CHASE
            elif ai == 2:
                ai = cfg.ENEMY_ST_ATTACK
        return Enemy(
            type_key=str(raw.get("type", et.DEFAULT_TYPE_KEY)),
            x=px,
            y=py,
            wander_heading=float(raw["w"]),
            hp=float(raw["hp"]),
            shoot_cd=float(raw["cd"]),
            ai_state=ai,
            combat_scale=float(raw.get("cs", 1.0)),
            hit_flash_timer=0.0,
            patrol_ox=float(raw.get("pox", px)),
            patrol_oy=float(raw.get("poy", py)),
            strafe_phase=float(raw.get("sf", 0.0)),
        )
    if isinstance(raw, (list, tuple)) and len(raw) >= 6:
        px = float(raw[0])
        py = float(raw[1])
        ai = int(raw[5])
        if ai == 0:
            ai = cfg.ENEMY_ST_PATROL
        elif ai == 1:
            ai = cfg.ENEMY_ST_CHASE
        elif ai == 2:
            ai = cfg.ENEMY_ST_ATTACK
        return Enemy(
            type_key=et.DEFAULT_TYPE_KEY,
            x=px,
            y=py,
            wander_heading=float(raw[2]),
            hp=float(raw[3]),
            shoot_cd=float(raw[4]),
            ai_state=ai,
            combat_scale=1.0,
            hit_flash_timer=0.0,
            patrol_ox=px,
            patrol_oy=py,
            strafe_phase=0.0,
        )
    raise ValueError(f"Bad enemy save data: {raw!r}")


def clear_shot_to_player(ex, ey, px, py, tile_size):
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


def update_shooting(enemies, px, py, dt, tile_size, apply_damage: bool = True):
    dmg = 0.0
    for e in enemies:
        sp = e.spec()
        if e.ai_state != cfg.ENEMY_ST_ATTACK:
            e.shoot_cd = max(0.0, e.shoot_cd - dt)
            continue
        e.shoot_cd = max(0.0, e.shoot_cd - dt)
        dist = math.hypot(px - e.x, py - e.y)
        if dist > cfg.ENEMY_SHOOT_RANGE or e.shoot_cd > 0:
            continue
        if not clear_shot_to_player(e.x, e.y, px, py, tile_size):
            continue
        e.shoot_cd = sp.shoot_cooldown
        if apply_damage:
            dmg += sp.ranged_damage * e.combat_scale
    return dmg


def update_ai(enemies, px, py, dt, tile_size):
    enemy_ai.tick(enemies, px, py, dt, tile_size)


def update_hit_flash(enemies, dt):
    for e in enemies:
        if e.hit_flash_timer > 0:
            e.hit_flash_timer = max(0.0, e.hit_flash_timer - dt)


def update_death_effects(dt):
    i = 0
    while i < len(R.death_effects):
        R.death_effects[i][2] -= dt
        R.death_effects[i][3] += dt * 14.0
        if R.death_effects[i][2] <= 0:
            R.death_effects.pop(i)
        else:
            i += 1


def draw_death_effects(
    surface,
    px,
    py,
    yaw,
    ray_hits,
    screen_w,
    screen_h,
    fov,
    pitch_offset_px=0,
    horizon_skew_px=0.0,
):
    """Expanding rings at world positions where enemies were just destroyed."""
    if not R.death_effects:
        return
    proj_plane = (screen_w / 2) / math.tan(fov / 2)
    half_fov = fov / 2
    n = len(ray_hits)
    if n == 0:
        return

    def depth_at_column(x):
        if x < 0:
            x = 0
        if x >= screen_w:
            x = screen_w - 1
        ci = int(x / screen_w * n)
        if ci >= n:
            ci = n - 1
        d = ray_hits[ci][0]
        return float("inf") if math.isinf(d) else float(d)

    cos_y = math.cos(yaw)
    sin_y = math.sin(yaw)

    for burst in R.death_effects:
        wx, wy, t_left, phase = burst[0], burst[1], burst[2], burst[3]
        dist = math.hypot(wx - px, wy - py)
        if dist < 1e-3:
            continue
        along_t = (wx - px) * cos_y + (wy - py) * sin_y
        if along_t <= 0:
            continue
        ang = math.atan2(wy - py, wx - px)
        rel = ang - yaw
        while rel > math.pi:
            rel -= 2 * math.pi
        while rel < -math.pi:
            rel += 2 * math.pi
        if abs(rel) > half_fov * 1.02:
            continue
        sx = screen_w / 2 + math.tan(rel) * proj_plane
        line_h = int((56 * proj_plane) / max(dist, 1.0))
        line_h = min(max(line_h, 4), screen_h * 2)
        hy = world.horizon_y_at_screen_x(int(sx), screen_w, n, screen_h, pitch_offset_px, horizon_skew_px)
        cy = hy - line_h // 3
        sx_i = int(sx)
        life = t_left / cfg.DEATH_BURST_DURATION if cfg.DEATH_BURST_DURATION > 0 else 0
        life = max(0.0, min(1.0, life))
        rad = int(8 + phase * 0.35 + (1.0 - life) * 22)
        a = int(200 * life)
        if sx_i < 0 or sx_i >= screen_w:
            continue
        if along_t >= depth_at_column(sx_i):
            continue
        ring = pygame.Surface((rad * 2 + 4, rad * 2 + 4), pygame.SRCALPHA)
        col = (255, 220, 120, min(220, a))
        pygame.draw.circle(ring, col, (rad + 2, rad + 2), rad, 2)
        pygame.draw.circle(ring, (255, 255, 255, min(180, a)), (rad + 2, rad + 2), max(2, rad - 3), 1)
        surface.blit(ring, (sx_i - rad - 2, cy - rad - 2))


def draw_billboards(
    surface,
    enemies,
    px,
    py,
    yaw,
    ray_hits,
    screen_w,
    screen_h,
    fov,
    pitch_offset_px=0,
    horizon_skew_px=0.0,
    billboard_texture=None,
):
    """
    Per-enemy billboard: texture from assets.billboard_for_enemy_type(type_key).
    Pass billboard_texture only to override all (legacy); normally None.
    """
    if not enemies:
        return
    proj_plane = (screen_w / 2) / math.tan(fov / 2)
    half_fov = fov / 2
    n = len(ray_hits)
    if n == 0:
        return

    def depth_at_column(x):
        if x < 0:
            x = 0
        if x >= screen_w:
            x = screen_w - 1
        i = int(x / screen_w * n)
        if i >= n:
            i = n - 1
        d = ray_hits[i][0]
        return float("inf") if math.isinf(d) else float(d)

    ordered = sorted(enemies, key=lambda t: -(math.hypot(t.x - px, t.y - py)))

    cos_y = math.cos(yaw)
    sin_y = math.sin(yaw)

    for ent in ordered:
        sp = ent.spec()
        tex_src = billboard_texture if billboard_texture is not None else assets.billboard_for_enemy_type(ent.type_key)
        if tex_src.get_width() < 1 or tex_src.get_height() < 1:
            continue

        dist = math.hypot(ent.x - px, ent.y - py)
        if dist < 1e-3:
            continue
        along_t = (ent.x - px) * cos_y + (ent.y - py) * sin_y
        if along_t <= 0:
            continue

        ang = math.atan2(ent.y - py, ent.x - px)
        rel = ang - yaw
        while rel > math.pi:
            rel -= 2 * math.pi
        while rel < -math.pi:
            rel += 2 * math.pi
        if abs(rel) > half_fov * 1.02:
            continue

        sx = screen_w / 2 + math.tan(rel) * proj_plane
        line_h = int((sp.billboard_height * proj_plane) / dist)
        line_h = min(max(line_h, 2), screen_h * 2)
        half_w = int((sp.billboard_width * proj_plane) / dist / 2)
        half_w = max(half_w, 1)
        left = int(sx - half_w)
        right = int(sx + half_w)
        sprite_screen_w = max(1, right - left)

        scaled = pygame.transform.smoothscale(tex_src, (sprite_screen_w, line_h))
        sw = scaled.get_width()

        shade = max(0.35, 1.0 - 0.65 * min(dist / cfg.MAX_SHADE_DISTANCE, 1.0))
        ds = max(0, min(255, int(255 * shade)))

        any_vis = False
        outline_top = None
        outline_bot = None
        for col in range(left, right):
            if col < 0 or col >= screen_w:
                continue
            if along_t >= depth_at_column(col):
                continue
            lx = col - left
            if lx < 0 or lx >= sw:
                continue
            hy = world.horizon_y_at_screen_x(col, screen_w, n, screen_h, pitch_offset_px, horizon_skew_px)
            top = hy - line_h // 2
            bot = top + line_h
            if outline_top is None or top < outline_top:
                outline_top = top
            if outline_bot is None or bot > outline_bot:
                outline_bot = bot
            any_vis = True
            strip = scaled.subsurface((lx, 0, 1, line_h))
            strip = strip.copy()
            strip.fill((ds, ds, ds), special_flags=pygame.BLEND_MULT)
            if ent.hit_flash_timer > 0:
                hf = min(1.0, ent.hit_flash_timer / max(1e-6, cfg.ENEMY_HIT_FLASH_DURATION))
                add_amt = int(70 * hf)
                strip.fill((add_amt, add_amt // 3, add_amt // 5), special_flags=pygame.BLEND_ADD)
            surface.blit(strip, (col, top))
        if any_vis and outline_top is not None and outline_bot is not None:
            pygame.draw.rect(
                surface,
                sp.placeholder_edge,
                (left, outline_top, max(1, right - left), outline_bot - outline_top),
                1,
            )
