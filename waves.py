"""
Wave spawning: safe positions away from the player + wave-scaled counts and enemy mix.
"""

import math
import random

import enemy
import enemy_types as et
import progression
import runtime as R
import settings as cfg
import world


def pick_spawn_type_for_wave(rng: random.Random, wave_n: int, pressure: float = 0.0) -> str:
    """Slightly more heavies/scouts at higher waves (still beginner-readable)."""
    t = max(0, wave_n - 1)
    p = max(0.0, min(1.0, pressure))
    w_grunt = 0.5 - min(0.22, t * 0.034) - p * 0.1
    w_heavy = 0.25 + min(0.18, t * 0.022) + p * 0.14
    w_scout = 0.25 + min(0.18, t * 0.022) - p * 0.04
    s = w_grunt + w_heavy + w_scout
    w_grunt /= s
    w_heavy /= s
    w_scout /= s
    r = rng.random()
    if r < w_grunt:
        return et.TYPE_GRUNT
    if r < w_grunt + w_heavy:
        return et.TYPE_HEAVY
    return et.TYPE_SCOUT


def _cell_center_world(mx, my, tile_size):
    return (mx + 0.5) * tile_size, (my + 0.5) * tile_size


def _collect_spawn_cells(px, py, tile_size, num_needed, min_dist_sq, rng, max_ring=140):
    """
    Walkable cells in expanding rings, preferring tiles at least sqrt(min_dist_sq) from the player.
    """
    pmx = int(math.floor(px / tile_size))
    pmy = int(math.floor(py / tile_size))
    far = []
    near = []
    for radius in range(1, max_ring):
        for mx in range(pmx - radius, pmx + radius + 1):
            for my in range(pmy - radius, pmy + radius + 1):
                if max(abs(mx - pmx), abs(my - pmy)) != radius:
                    continue
                if not world.is_walkable_cell(world.sample_world_cell(mx, my)):
                    continue
                if (mx, my) == (pmx, pmy):
                    continue
                cx, cy = _cell_center_world(mx, my, tile_size)
                d2 = (cx - px) ** 2 + (cy - py) ** 2
                if d2 >= min_dist_sq:
                    far.append((mx, my))
                else:
                    near.append((mx, my))
        if len(far) >= num_needed:
            break
    rng.shuffle(far)
    if len(far) >= num_needed:
        return far[:num_needed]
    rng.shuffle(near)
    merged = far + [c for c in near if c not in far]
    return merged[:num_needed]


def _spread_spawn_cells(cells, px, py, tile_size, n, rng):
    """Prefer spawns from different compass buckets so squads don’t stack on one bearing."""
    if n <= 2 or len(cells) <= n:
        rng.shuffle(cells)
        return cells[:n]
    buckets = [[] for _ in range(4)]
    for mx, my in cells:
        cx, cy = _cell_center_world(mx, my, tile_size)
        ang = math.atan2(cy - py, cx - px)
        q = int((ang + math.pi) / (0.5 * math.pi)) % 4
        buckets[q].append((mx, my))
    for b in buckets:
        rng.shuffle(b)
    out = []
    q = 0
    while len(out) < n:
        progressed = False
        for _ in range(4):
            b = buckets[q % 4]
            q += 1
            if b:
                out.append(b.pop())
                progressed = True
                break
        if not progressed:
            break
    if len(out) < n:
        rest = []
        for b in buckets:
            rest.extend(b)
        rng.shuffle(rest)
        out.extend(rest[: n - len(out)])
    return out[:n]


def spawn_wave_enemies(px, py, tile_size, wave_number, rng=None, spawn_style="normal"):
    """Spawn a full wave: scaled count, difficulty, and safe spawn points."""
    if rng is None:
        rng = random.Random()
    elif not isinstance(rng, random.Random):
        rng = random.Random()
    n = cfg.wave_enemy_count(wave_number)
    min_dist = cfg.WAVE_SPAWN_MIN_DIST
    if spawn_style == "ambush":
        min_dist = max(tile_size * 1.15, cfg.WAVE_SPAWN_MIN_DIST * cfg.WAVE_AMBUSH_SPAWN_DIST_MULT)
    min_dist_sq = min_dist * min_dist
    cells = _collect_spawn_cells(px, py, tile_size, n, min_dist_sq, rng)

    if len(cells) < n:
        relaxed = min_dist * 0.62
        cells = _collect_spawn_cells(px, py, tile_size, n, relaxed * relaxed, rng)
    if len(cells) < n:
        cells = _collect_spawn_cells(px, py, tile_size, n, (min_dist * 0.22) ** 2, rng)

    picked = _spread_spawn_cells(cells, px, py, tile_size, n, rng)
    pressure = progression.spawn_mix_pressure()
    out = []
    for mx, my in picked:
        tkey = pick_spawn_type_for_wave(rng, wave_number, pressure=pressure)
        cx, cy = _cell_center_world(mx, my, tile_size)
        jx = cx + rng.uniform(-10.0, 10.0)
        jy = cy + rng.uniform(-10.0, 10.0)
        if world.can_walk_world(jx, jy, tile_size):
            cx, cy = jx, jy
        elite = progression.roll_elite_spawn(rng)
        out.append(
            enemy.create_enemy(
                tkey,
                cx,
                cy,
                rng,
                wave_number=wave_number,
                player_x=px,
                player_y=py,
                elite=elite,
            )
        )
    return out


def find_spawn_and_enemies(tile_size, wave_number=1, rng=None, skip_enemies=False, spawn_style="normal"):
    """
    Spiral from origin for a floor cell for the player.
    If skip_enemies is True (e.g. main menu), return [] for the enemy list.
    """
    if rng is None:
        rng = random.Random()
    elif not isinstance(rng, random.Random):
        rng = random.Random()
    found = None
    for radius in range(0, 256):
        for mx in range(-radius, radius + 1):
            for my in range(-radius, radius + 1):
                if max(abs(mx), abs(my)) != radius:
                    continue
                if world.is_walkable_cell(world.sample_world_cell(mx, my)):
                    found = (mx, my)
                    break
            if found:
                break
        if found:
            break
    if not found:
        R.world_cell_edits[(0, 0)] = "0"
        found = (0, 0)
    pmx, pmy = found
    px = (pmx + 0.5) * tile_size
    py = (pmy + 0.5) * tile_size

    if skip_enemies:
        return px, py, []
    enemies = spawn_wave_enemies(px, py, tile_size, wave_number, rng=rng, spawn_style=spawn_style)
    return px, py, enemies
