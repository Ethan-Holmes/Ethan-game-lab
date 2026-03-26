"""
Player weapons, projectiles, and on-screen bullet tracers.
"""

import math
import random
from dataclasses import dataclass

import pygame

import assets
import progression
import runtime as R
import settings as cfg
import world


@dataclass(frozen=True)
class Weapon:
    """One firearm; extend WEAPONS to add more (number keys switch slot)."""

    slot: int
    name: str
    cooldown: float
    recoil_yaw: float
    recoil_pitch_px: float
    damage: float
    destroys_wall: bool
    bullet_speed: float
    magazine_size: int
    reload_time: float
    # Volley / feel (single-shot: pellet_count=1, spread_rad=0).
    pellet_count: int = 1
    spread_rad: float = 0.0
    pellet_damage: float | None = None  # None → use `damage` for each pellet
    muzzle_flash_scale: float = 1.0
    muzzle_flash_duration: float = 0.11
    screen_shake_mul: float = 1.0
    particle_burst_mul: float = 1.0
    tracer_style: int = 0  # 0 pistol 1 rifle 2 shotgun (tracer colors)


WEAPONS = (
    Weapon(
        1,
        "Pistol",
        0.16,
        0.02,
        11.0,
        24.0,
        False,
        840.0,
        12,
        0.92,
        pellet_count=1,
        spread_rad=0.0,
        muzzle_flash_scale=0.92,
        muzzle_flash_duration=0.078,
        screen_shake_mul=0.78,
        particle_burst_mul=0.82,
        tracer_style=0,
    ),
    Weapon(
        2,
        "Rifle",
        0.34,
        0.045,
        26.0,
        28.0,
        False,
        920.0,
        30,
        1.48,
        pellet_count=1,
        spread_rad=0.0,
        muzzle_flash_scale=1.12,
        muzzle_flash_duration=0.125,
        screen_shake_mul=1.32,
        particle_burst_mul=1.18,
        tracer_style=1,
    ),
    Weapon(
        3,
        "Shotgun",
        0.86,
        0.055,
        34.0,
        12.0,
        False,
        720.0,
        6,
        2.35,
        pellet_count=7,
        spread_rad=0.15,
        pellet_damage=11.0,
        muzzle_flash_scale=1.55,
        muzzle_flash_duration=0.15,
        screen_shake_mul=1.62,
        particle_burst_mul=1.45,
        tracer_style=2,
    ),
)

weapon_ammo = [w.magazine_size for w in WEAPONS]
reload_timers = [0.0] * len(WEAPONS)

# [x, y, angle, dist, damage, destroys_wall, speed, prev_x, prev_y, tracer_style]
player_bullets = []


def sync_weapon_ammo_for_unlocks():
    """Zero ammo for locked weapons; full mags for unlocked (call after load / new run)."""
    progression.ensure_loaded()
    for i, w in enumerate(WEAPONS):
        if progression.is_weapon_slot_unlocked(w.slot):
            weapon_ammo[i] = w.magazine_size
        else:
            weapon_ammo[i] = 0
    for i in range(len(reload_timers)):
        reload_timers[i] = 0.0

_TRACER_BY_STYLE = (
    ((255, 220, 140), (255, 255, 245)),  # pistol — warm
    ((255, 190, 90), (255, 255, 255)),  # rifle — crisp
    ((255, 160, 70), (255, 240, 200)),  # shotgun — orange bloom
)


def _append_bullet(bullets, bx, by, ang, dmg, dest_wall, bspd, tracer_style):
    if len(bullets) >= cfg.BULLET_MAX_ALIVE:
        return
    bullets.append([bx, by, ang, 0.0, dmg, dest_wall, bspd, bx, by, tracer_style])


def spawn_weapon_volley(bullets, px, py, base_angle, wpn):
    """Fire one trigger pull: one or many pellets with spread."""
    c = math.cos(base_angle)
    s = math.sin(base_angle)
    o = cfg.BULLET_SPAWN_OFFSET
    pdmg = wpn.pellet_damage if wpn.pellet_damage is not None else wpn.damage
    n = max(1, wpn.pellet_count)
    dw = 1 if wpn.destroys_wall else 0
    for i in range(n):
        if n == 1:
            off = 0.0
        else:
            u = -1.0 + 2.0 * i / max(n - 1, 1)
            jitter = wpn.spread_rad * 0.14
            off = u * wpn.spread_rad * 0.52 + random.uniform(-jitter, jitter)
        ang = base_angle + off
        cc = math.cos(ang)
        ss = math.sin(ang)
        bx = px + cc * o
        by = py + ss * o
        _append_bullet(bullets, bx, by, ang, pdmg, dw, wpn.bullet_speed, wpn.tracer_style)


def update_bullets(bullets, dt, tile_size, enemies):
    hits = 0
    kills = 0
    i = 0
    while i < len(bullets):
        b = bullets[i]
        if len(b) < 9:
            bullets.pop(i)
            continue
        if len(b) == 9:
            b.append(0)
        bx, by, ang, dist_acc, dmg, dest_wall, bspd = (
            b[0],
            b[1],
            b[2],
            b[3],
            b[4],
            b[5],
            b[6],
        )
        prev_x, prev_y = bx, by
        step = bspd * dt
        nx = bx + math.cos(ang) * step
        ny = by + math.sin(ang) * step
        dist_acc += step

        if dist_acc >= cfg.BULLET_MAX_RANGE:
            bullets.pop(i)
            continue

        mx = int(math.floor(nx / tile_size))
        my = int(math.floor(ny / tile_size))
        cell = world.lod_world_cell(mx, my)
        if not world.is_walkable_cell(cell):
            if dest_wall and world.chunk_is_active(mx, my) and not world.is_walkable_cell(
                world.sample_world_cell(mx, my)
            ):
                R.world_cell_edits[(mx, my)] = "0"
            bullets.pop(i)
            continue

        hit_enemy = False
        for ei, e in enumerate(enemies):
            ex, ey = e.x, e.y
            if math.hypot(nx - ex, ny - ey) <= cfg.BULLET_ENEMY_HIT_RADIUS:
                e.hp -= dmg
                e.hit_flash_timer = cfg.ENEMY_HIT_FLASH_DURATION
                assets.play_sfx(assets.SOUND_HIT)
                if e.hp <= 0:
                    R.death_effects.append([ex, ey, float(cfg.DEATH_BURST_DURATION), 0.0])
                    enemies.pop(ei)
                    R.enemies_defeated += 1
                    R.kills_this_wave += 1
                    kills += 1
                    progression.register_kill(1)
                hits += 1
                hit_enemy = True
                break
        if hit_enemy:
            bullets.pop(i)
            continue

        b[0], b[1], b[3] = nx, ny, dist_acc
        b[7], b[8] = prev_x, prev_y
        i += 1
    return hits, kills


def _project_bullet_to_screen(
    bx, by, px, py, yaw, ray_hits, screen_w, screen_h, fov, pitch_offset_px, horizon_skew_px):
    proj_plane = (screen_w / 2) / math.tan(fov / 2)
    half_fov = fov / 2
    n = len(ray_hits)
    if n == 0:
        return None

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
    dist = math.hypot(bx - px, by - py)
    along_view = (bx - px) * cos_y + (by - py) * sin_y
    if along_view <= 0:
        return None
    ang = math.atan2(by - py, bx - px)
    rel = ang - yaw
    while rel > math.pi:
        rel -= 2 * math.pi
    while rel < -math.pi:
        rel += 2 * math.pi
    if abs(rel) > half_fov * 1.02:
        return None
    sx = int(screen_w / 2 + math.tan(rel) * proj_plane)
    if sx < 0 or sx >= screen_w:
        return None
    ri = world.screen_column_to_ray_index(sx, screen_w, n)
    r_ang = world.ray_angle_for_index(ri, n, yaw, fov)
    d_bullet = world.perpendicular_depth_along_ray(px, py, bx, by, r_ang)
    if d_bullet <= 0 or d_bullet >= depth_at_column(sx):
        return None
    hy = world.horizon_y_at_screen_x(sx, screen_w, n, screen_h, pitch_offset_px, horizon_skew_px)
    return sx, hy, dist


def draw_bullet_tracers(
    surface, bullets, px, py, yaw, ray_hits, screen_w, screen_h, fov, pitch_offset_px=0, horizon_skew_px=0.0
):
    if not bullets:
        return
    n = len(ray_hits)
    if n == 0:
        return

    ordered = sorted(bullets, key=lambda bb: -(math.hypot(bb[0] - px, bb[1] - py)))

    for b in ordered:
        bx, by = b[0], b[1]
        prx = b[7] if len(b) > 8 else bx
        pry = b[8] if len(b) > 8 else by
        st = b[9] if len(b) > 9 else 0
        if st < 0 or st >= len(_TRACER_BY_STYLE):
            st = 0
        glow, core = _TRACER_BY_STYLE[st]
        col = core
        cur = _project_bullet_to_screen(
            bx, by, px, py, yaw, ray_hits, screen_w, screen_h, fov, pitch_offset_px, horizon_skew_px
        )
        if cur is None:
            continue
        sx, hy, dist = cur
        prev = _project_bullet_to_screen(
            prx, pry, px, py, yaw, ray_hits, screen_w, screen_h, fov, pitch_offset_px, horizon_skew_px
        )
        if prev is not None:
            psx, phy, _ = prev
            pygame.draw.line(surface, glow, (psx, phy), (sx, hy), 2)
            pygame.draw.line(surface, col, (psx, phy), (sx, hy), 1)
        r = max(2, min(8, int(380 / max(dist, 8.0))))
        pygame.draw.circle(surface, glow, (sx, hy), r + 2)
        pygame.draw.circle(surface, col, (sx, hy), r)
        pygame.draw.circle(surface, (255, 255, 255), (sx, hy), max(1, r // 2))


def spawn_muzzle_particles(particles, cx, cy, burst_mul=1.0):
    room = cfg.PARTICLE_MAX_ALIVE - len(particles)
    base = int(round(cfg.PARTICLE_BURST_COUNT * burst_mul))
    n = min(max(4, base), max(0, room))
    for _ in range(n):
        a = random.uniform(0, 2 * math.pi)
        sp = random.uniform(cfg.PARTICLE_SPEED_MIN, cfg.PARTICLE_SPEED_MAX)
        particles.append(
            [float(cx), float(cy), math.cos(a) * sp, math.sin(a) * sp, cfg.PARTICLE_LIFETIME, cfg.PARTICLE_LIFETIME]
        )


def update_shot_particles(particles, dt):
    i = 0
    while i < len(particles):
        p = particles[i]
        p[0] += p[2] * dt
        p[1] += p[3] * dt
        p[4] -= dt
        if p[4] <= 0:
            particles.pop(i)
        else:
            i += 1


def draw_muzzle_flash(surface, cx, cy, timer, duration, scale=1.0, warm_tint=False):
    if timer <= 0:
        return
    t = timer / duration if duration > 0 else 0
    rad = max(8, int(cfg.MUZZLE_FLASH_RADIUS * scale * (0.45 + 0.55 * t)))
    if warm_tint:
        col = (255, min(255, 150 + int(90 * t)), min(255, 70 + int(80 * t)))
        halo = (255, 200, 120)
    else:
        col = (255, min(255, 180 + int(75 * t)), 90)
        halo = (255, 240, 200)
    ix, iy = int(cx), int(cy)
    pygame.draw.circle(surface, halo, (ix, iy), rad + 5, 3)
    pygame.draw.circle(surface, col, (ix, iy), rad)
    for i in range(6):
        ang = i * (math.pi / 3) + t * 0.5
        dx = math.cos(ang) * (rad + 8)
        dy = math.sin(ang) * (rad + 8)
        pygame.draw.line(surface, (255, 230, 170), (ix, iy), (int(ix + dx), int(iy + dy)), 2)
    pygame.draw.circle(surface, (255, 255, 255), (ix, iy), max(2, rad // 3))


def draw_shot_particles(surface, particles):
    for p in particles:
        life = p[4] / p[5] if p[5] > 0 else 0.0
        g = int(200 * life)
        b = int(120 * life)
        pygame.draw.circle(surface, (255, g, b), (int(p[0]), int(p[1])), 2)
