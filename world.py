"""
Urban arena map: tile-based grid with roads, sidewalks, lots, buildings, cover, and props.

Cell chars: 0/a/b walkable; 1/2 buildings; 3 corner cover; 4 car; 5 crates; 6 barrier;
7 lamp; 8 dumpster; 9 parapet façade. Chunks cache characters; non-walkable cells are solid.
"""

import math

import pygame

import runtime as R
import settings as cfg

# Walkable terrain (movement, bullets, LOS through these floor types).
_WALKABLE = frozenset({"0", "a", "b"})

def _is_main_road_cell(mx, my, rg):
    """Thoroughfare grid lines — kept clear so movement stays fluid."""
    return (mx % rg == 0) or (my % rg == 0)


def _apply_env_props(mx, my, base, rg, ix, iy):
    """
    Place props on walkable terrain: sidewalks, lots, and alleys — not on main road lines.
    Deterministic from world seed for stable saves and chunk streaming.
    """
    if base not in _WALKABLE:
        return base
    if base == "0" and _is_main_road_cell(mx, my, rg):
        return "0"

    h = _mix_u32(mx, my, int(R.world_gen_seed), 0xD0DEC0)
    h2 = _mix_u32(mx * 31 + 7, my * 17 + 3, int(R.world_gen_seed), 0xC0DEEF)
    h3 = _mix_u32(mx + 999, my + 333, int(R.world_gen_seed), 0xA11E00)

    # Sidewalks: curb parking, street furniture, cover
    if base == "a":
        if (h & 0xFF) < 14:
            return "4"
        if (h & 0xFF) < 28:
            return "7"
        if (h & 0xFF) < 40:
            return "8"
        if (h & 0xFF) < 50:
            return "6"
        return "a"

    # Open lots: staging, crates, barriers
    if base == "b":
        if (h2 & 0xFF) < 48:
            return "5"
        if (h2 & 0xFF) < 62:
            return "6"
        if (h2 & 0xFF) < 74:
            return "8"
        if (h2 & 0xFF) < 82:
            return "4"
        return "b"

    # Alley / interior walkable road (not main grid): tighter combat lanes
    if base == "0":
        if (h3 & 0xFF) < 20:
            return "5"
        if (h3 & 0xFF) < 34:
            return "8"
        if (h3 & 0xFF) < 48:
            return "6"
        if (h3 & 0xFF) < 62:
            return "7"
        return "0"

    return base


def _facade_parapet(mx, my, base, rg, ix, iy):
    """Some outward-facing building cells read as parapet / roofline (visual only, still solid)."""
    if base not in ("1", "2"):
        return base
    on_face = ix == 2 or ix == rg - 2 or iy == 2 or iy == rg - 2
    if not on_face:
        return base
    hp = _mix_u32(mx, my, int(R.world_gen_seed), 0x9A9A9E)
    if ((hp >> 9) & 7) <= 2:
        return "9"
    return base


def init_perlin_noise(seed):
    """
    Kept for compatibility with save/load and game_flow (name is historical).
    Urban layout uses R.world_gen_seed directly.
    """
    _ = seed


def _mix_u32(*parts):
    h = 2166136261
    for p in parts:
        h = (h ^ (int(p) & 0xFFFFFFFF)) * 16777619 & 0xFFFFFFFF
    return h


def is_walkable_cell(ch):
    """True if the player and enemies can occupy the center of this cell."""
    return ch in _WALKABLE


def urban_cell(mx, my):
    """
    Deterministic city block: roads, sidewalks, shells, lots, alleys, cover,
    environmental props, and occasional façade parapet detail.
    """
    rg = cfg.URBAN_ROAD_SPACING
    ix = mx % rg
    iy = my % rg

    if mx % rg == 0 or my % rg == 0:
        return _apply_env_props(mx, my, "0", rg, ix, iy)

    if ix == 1 or ix == rg - 1 or iy == 1 or iy == rg - 1:
        return _apply_env_props(mx, my, "a", rg, ix, iy)

    bx = mx // rg
    by = my // rg
    h = _mix_u32(bx, by, int(R.world_gen_seed), 0xC0FFEE)
    h2 = _mix_u32(bx + 31, by + 17, int(R.world_gen_seed), 0xBEEF00)

    if not (2 <= ix <= rg - 2 and 2 <= iy <= rg - 2):
        base = "1" if (h & 0x200) == 0 else "2"
        return _facade_parapet(mx, my, base, rg, ix, iy)

    alley_v = (h >> 16) & 3 == 0
    alley_h = (h2 >> 16) & 3 == 0
    vx = 2 if (h & 1) == 0 else rg - 2
    vy = 2 if (h2 & 1) == 0 else rg - 2
    if alley_v and ix == vx:
        return _apply_env_props(mx, my, "0", rg, ix, iy)
    if alley_h and iy == vy:
        return _apply_env_props(mx, my, "0", rg, ix, iy)

    mid = rg // 2
    if ix == mid and iy == mid:
        return _apply_env_props(mx, my, "b", rg, ix, iy)

    corners = ((2, 2), (2, rg - 2), (rg - 2, 2), (rg - 2, rg - 2))
    if (ix, iy) in corners and ((h >> 8) & 3) < 2:
        return "3"

    base = "1" if (h & 0x100) == 0 else "2"
    return _facade_parapet(mx, my, base, rg, ix, iy)


def generate_chunk_grid(chunk_x, chunk_y):
    rows = []
    for ly in range(cfg.CHUNK_SIZE):
        row = []
        base_my = chunk_y * cfg.CHUNK_SIZE + ly
        for lx in range(cfg.CHUNK_SIZE):
            mx = chunk_x * cfg.CHUNK_SIZE + lx
            row.append(urban_cell(mx, base_my))
        rows.append(row)
    return rows


def get_chunk_cached(chunk_x, chunk_y):
    key = (chunk_x, chunk_y)
    if key not in R.chunk_cache:
        R.chunk_cache[key] = generate_chunk_grid(chunk_x, chunk_y)
    return R.chunk_cache[key]


def sample_world_cell(mx, my):
    k = (mx, my)
    if k in R.world_cell_edits:
        return R.world_cell_edits[k]
    cx, cy = chunk_coords_for_cell(mx, my)
    ch = R.chunk_cache.get((cx, cy))
    if ch is not None:
        lx = mx - cx * cfg.CHUNK_SIZE
        ly = my - cy * cfg.CHUNK_SIZE
        return ch[ly][lx]
    return urban_cell(mx, my)


def chunk_coords_for_cell(mx, my):
    return mx // cfg.CHUNK_SIZE, my // cfg.CHUNK_SIZE


def chunk_is_active(mx, my):
    cx, cy = chunk_coords_for_cell(mx, my)
    return (cx, cy) in R._active_chunk_keys


def lod_world_cell(mx, my):
    if not chunk_is_active(mx, my):
        return "1"
    return sample_world_cell(mx, my)


def update_chunk_streaming(px, py, tile_size):
    pmx = int(math.floor(px / tile_size))
    pmy = int(math.floor(py / tile_size))
    R._chunk_player_cx, R._chunk_player_cy = chunk_coords_for_cell(pmx, pmy)
    active = set()
    for dcx in range(-cfg.CHUNK_LOAD_RADIUS, cfg.CHUNK_LOAD_RADIUS + 1):
        for dcy in range(-cfg.CHUNK_LOAD_RADIUS, cfg.CHUNK_LOAD_RADIUS + 1):
            active.add((R._chunk_player_cx + dcx, R._chunk_player_cy + dcy))
    R._active_chunk_keys = active
    for cx, cy in active:
        get_chunk_cached(cx, cy)


def _inv_dir_component(v):
    return abs(1.0 / v) if abs(v) > 1e-9 else float("inf")


def cast_ray(px, py, angle, tile_size):
    pos_x = px / tile_size
    pos_y = py / tile_size
    ray_dir_x = math.cos(angle)
    ray_dir_y = math.sin(angle)

    map_x = int(math.floor(pos_x))
    map_y = int(math.floor(pos_y))

    _cell0 = lod_world_cell(map_x, map_y)
    if not is_walkable_cell(_cell0):
        return 0.0, map_x, map_y, 0, px, py, _cell0

    delta_dist_x = _inv_dir_component(ray_dir_x)
    delta_dist_y = _inv_dir_component(ray_dir_y)

    if ray_dir_x < 0:
        step_x = -1
        side_dist_x = (pos_x - map_x) * delta_dist_x
    else:
        step_x = 1
        side_dist_x = (map_x + 1.0 - pos_x) * delta_dist_x

    if ray_dir_y < 0:
        step_y = -1
        side_dist_y = (pos_y - map_y) * delta_dist_y
    else:
        step_y = 1
        side_dist_y = (map_y + 1.0 - pos_y) * delta_dist_y

    for _ in range(cfg.RAYCAST_MAX_STEPS):
        if side_dist_x < side_dist_y:
            side_dist_x += delta_dist_x
            map_x += step_x
            side = 0
        else:
            side_dist_y += delta_dist_y
            map_y += step_y
            side = 1

        _cell = lod_world_cell(map_x, map_y)
        if not is_walkable_cell(_cell):
            if side == 0:
                perp = (map_x - pos_x + (1 - step_x) / 2) / ray_dir_x
            else:
                perp = (map_y - pos_y + (1 - step_y) / 2) / ray_dir_y
            perp_world = abs(perp) * tile_size
            if side == 0:
                d_along = perp_world / max(abs(ray_dir_x), 1e-9)
            else:
                d_along = perp_world / max(abs(ray_dir_y), 1e-9)
            hit_x = px + ray_dir_x * d_along
            hit_y = py + ray_dir_y * d_along
            return perp_world, map_x, map_y, side, hit_x, hit_y, _cell

    return float("inf"), -1, -1, -1, 0.0, 0.0, "0"


def placement_cell_in_front_of_hit(mx, my, side, yaw):
    ray_dir_x = math.cos(yaw)
    ray_dir_y = math.sin(yaw)
    step_x = -1 if ray_dir_x < 0 else 1
    step_y = -1 if ray_dir_y < 0 else 1
    if side == 0:
        return mx - step_x, my
    return mx, my - step_y


def try_place_wall_block(px, py, yaw, tile_size, enemy_list, max_dist_world):
    if R.inventory_blocks <= 0:
        return False
    d, mx, my, side, _hx, _hy, _wc = cast_ray(px, py, yaw, tile_size)
    if math.isinf(d) or mx < 0:
        return False
    if d > max_dist_world or d < tile_size * 0.2:
        return False
    if not chunk_is_active(mx, my):
        return False

    cx, cy = placement_cell_in_front_of_hit(mx, my, side, yaw)
    if not chunk_is_active(cx, cy):
        return False
    if not is_walkable_cell(sample_world_cell(cx, cy)):
        return False

    pmx = int(math.floor(px / tile_size))
    pmy = int(math.floor(py / tile_size))
    if (cx, cy) == (pmx, pmy):
        return False

    for e in enemy_list:
        emx = int(math.floor(e.x / tile_size))
        emy = int(math.floor(e.y / tile_size))
        if (emx, emy) == (cx, cy):
            return False

    R.world_cell_edits[(cx, cy)] = "1"
    R.inventory_blocks -= 1
    return True


def world_pos_to_grid(wx, wy, tile_size):
    return int(math.floor(wx / tile_size)), int(math.floor(wy / tile_size))


def compute_ray_hits(px, py, yaw, tile_size, fov, num_rays):
    if num_rays <= 0:
        return []
    if num_rays == 1:
        return [cast_ray(px, py, yaw, tile_size)]

    half = fov / 2
    out = []
    for i in range(num_rays):
        t = i / (num_rays - 1)
        ray_angle = yaw - half + t * fov
        out.append(cast_ray(px, py, ray_angle, tile_size))
    return out


def can_walk_world(wx, wy, tile_size):
    mx = int(math.floor(wx / tile_size))
    my = int(math.floor(wy / tile_size))
    return is_walkable_cell(lod_world_cell(mx, my))


def apply_slide_move(px, py, dx, dy, tile_size):
    """Try full move, then axis slides (same idea as enemy movement)."""
    nx, ny = px + dx, py + dy
    if can_walk_world(nx, ny, tile_size):
        return nx, ny
    if can_walk_world(px + dx, py, tile_size):
        return px + dx, py
    if can_walk_world(px, py + dy, tile_size):
        return px, py + dy
    return px, py


def _wall_base_rgb(wall_char):
    if wall_char == "2":
        return (148, 136, 124)
    if wall_char == "3":
        return (72, 78, 88)
    if wall_char == "4":
        return (58, 62, 78)
    if wall_char == "5":
        return (108, 78, 52)
    if wall_char == "6":
        return (132, 128, 118)
    if wall_char == "7":
        return (44, 46, 54)
    if wall_char == "8":
        return (52, 74, 56)
    if wall_char == "9":
        return (118, 120, 128)
    return cfg.WALL_COLOR_BASE


def wall_color(mx, my, side, hit_x, hit_y, tile_size, distance_shade, wall_char="1"):
    br, bg, bb = _wall_base_rgb(wall_char)
    cell = (mx * 17 + my * 31 + side * 7) & 7
    br = br + (cell - 3) * 4
    bg = bg + ((cell * 2) & 7) - 3
    bb = bb + ((cell * 3) & 5) - 2
    if side == 1:
        br, bg, bb = int(br * 0.88), int(bg * 0.88), int(bb * 0.88)
    if side == 0:
        u = (hit_y % tile_size) / tile_size
    else:
        u = (hit_x % tile_size) / tile_size
    band = 0.82 + 0.18 * (1 if int(u * 3) % 2 == 0 else 0)
    # Voxel-style horizontal “floors” + window strip on buildings.
    if wall_char in ("1", "2"):
        win = 0.92 + 0.08 * (1 if int(u * 5) % 2 == 0 else 0)
        band *= win
    elif wall_char == "3":
        band *= 0.94 + 0.06 * (1 if int(u * 4) % 2 == 0 else 0)
    elif wall_char == "4":
        # Sedan: glass band, roof, wheel wells (blocky)
        if 0.2 < u < 0.48:
            band *= 1.18
            br = min(255, br + 28)
            bg = min(255, bg + 26)
            bb = min(255, bb + 32)
        elif u < 0.18 or u > 0.82:
            band *= 0.78
        mid = abs(u - 0.5)
        if mid < 0.08:
            band *= 0.92
    elif wall_char == "5":
        # Stacked wood / cargo crates
        plank = int(u * 6.0) % 2
        band *= 0.88 + 0.14 * plank
        br = min(255, br + plank * 12)
    elif wall_char == "6":
        # Jersey barrier: diagonal hazard feel via stepped bands
        stripe = (int(u * 9) + int(mx * 3 + my * 5)) % 2
        band *= 0.9 + 0.12 * stripe
        if stripe:
            br = min(255, br + 40)
            bg = min(255, bg + 36)
    elif wall_char == "7":
        # Lamp post: dark shaft, bright fixture cap
        if u < 0.72:
            band *= 0.85
        else:
            band *= 1.35
            br = min(255, br + 55)
            bg = min(255, bg + 52)
            bb = min(255, bb + 40)
        if 0.45 < u < 0.52:
            band *= 0.75
    elif wall_char == "8":
        # Dumpster: panels + rust
        rust = int(u * 5) % 2
        band *= 0.9 + 0.1 * rust
        if rust:
            br = min(255, br + 22)
            bg = min(255, bg + 10)
    elif wall_char == "9":
        # Parapet / coping: heavier top band
        if u < 0.22:
            band *= 1.12
            br, bg, bb = br + 8, bg + 8, bb + 10
        elif u > 0.78:
            band *= 0.88
        band *= 0.94 + 0.06 * (1 if int(u * 4) % 2 == 0 else 0)
    r = max(0, min(255, int(br * band * distance_shade)))
    g = max(0, min(255, int(bg * band * distance_shade)))
    b = max(0, min(255, int(bb * band * distance_shade)))
    return r, g, b


def floor_color_for_cell(ch):
    if ch == "a":
        return cfg.FLOOR_COLOR_SIDEWALK
    if ch == "b":
        return cfg.FLOOR_COLOR_LOT
    return cfg.FLOOR_COLOR_ROAD


def _wall_texture_u(hit_x, hit_y, tile_size, side):
    if side == 0:
        return (hit_y % tile_size) / tile_size
    return (hit_x % tile_size) / tile_size


def _horizon_y_at_ray_column(i, n, screen_h, pitch_offset_px, horizon_skew_px):
    u = (2.0 * i / (n - 1) - 1.0) if n > 1 else 0.0
    hy = int(screen_h // 2 + pitch_offset_px + horizon_skew_px * u)
    return max(2, min(screen_h - 3, hy))


def horizon_y_at_screen_x(x, screen_w, n, screen_h, pitch_offset_px, horizon_skew_px):
    if n <= 0:
        hy = int(screen_h // 2 + pitch_offset_px)
        return max(2, min(screen_h - 3, hy))
    i = int(x / screen_w * n)
    if i >= n:
        i = n - 1
    if i < 0:
        i = 0
    return _horizon_y_at_ray_column(i, n, screen_h, pitch_offset_px, horizon_skew_px)


def draw_raycast_view(
    surface,
    ray_hits,
    screen_w,
    screen_h,
    tile_size,
    fov,
    pitch_offset_px=0,
    wall_textures=None,
    horizon_skew_px=0.0,
    player_x=0.0,
    player_y=0.0,
    view_yaw=0.0,
):
    n = len(ray_hits)
    if n == 0:
        hy = int(screen_h // 2 + pitch_offset_px)
        hy = max(2, min(screen_h - 3, hy))
        surface.fill(cfg.CEILING_COLOR, (0, 0, screen_w, hy))
        surface.fill(cfg.FLOOR_COLOR, (0, hy, screen_w, screen_h - hy))
        return

    proj_plane = (screen_w / 2) / math.tan(fov / 2)
    col_w = screen_w / n
    half_fov = fov / 2

    for i in range(n):
        x0 = int(i * col_w)
        x1 = int((i + 1) * col_w)
        w = max(1, x1 - x0)
        hy_i = _horizon_y_at_ray_column(i, n, screen_h, pitch_offset_px, horizon_skew_px)
        pygame.draw.rect(surface, cfg.CEILING_COLOR, (x0, 0, w, hy_i))
        t = i / (n - 1) if n > 1 else 0.5
        ray_ang = view_yaw - half_fov + t * fov
        fd = 2.1 * tile_size
        fx = player_x + math.cos(ray_ang) * fd
        fy = player_y + math.sin(ray_ang) * fd
        fmx = int(math.floor(fx / tile_size))
        fmy = int(math.floor(fy / tile_size))
        fch = sample_world_cell(fmx, fmy)
        fr, fg, fb = floor_color_for_cell(fch)
        tdist = min(1.0, (2.1 * tile_size) / cfg.MAX_SHADE_DISTANCE)
        fshade = max(0.55, 1.0 - 0.38 * tdist)
        floor_rgb = (
            max(0, min(255, int(fr * fshade))),
            max(0, min(255, int(fg * fshade))),
            max(0, min(255, int(fb * fshade))),
        )
        pygame.draw.rect(surface, floor_rgb, (x0, hy_i, w, screen_h - hy_i))

    for i in range(n):
        dist, mx, my, side, hit_x, hit_y, wall_char = ray_hits[i]
        if math.isinf(dist) or dist <= 0:
            continue

        d = max(float(dist), 1e-3)
        line_h = int((tile_size * proj_plane) / d)
        line_h = min(line_h, screen_h * 2)
        if line_h < 1:
            continue
        hy_i = _horizon_y_at_ray_column(i, n, screen_h, pitch_offset_px, horizon_skew_px)
        top = hy_i - line_h // 2

        x0 = int(i * col_w)
        x1 = int((i + 1) * col_w)
        w = max(1, x1 - x0)

        t = min(d / cfg.MAX_SHADE_DISTANCE, 1.0)
        distance_shade = max(0.18, 1.0 - 0.82 * t)

        tex = None
        if wall_textures is not None:
            tex = wall_textures.get(wall_char)
        if tex is not None:
            tw, th = tex.get_size()
            if tw >= 1 and th >= 1:
                u = _wall_texture_u(hit_x, hit_y, tile_size, side)
                ifu = int(u * (tw - 1))
                ifu = max(0, min(tw - 1, ifu))
                col_strip = tex.subsurface((ifu, 0, 1, th))
                scaled = pygame.transform.scale(col_strip, (w, line_h))
                shade = distance_shade * (0.88 if side == 1 else 1.0)
                ds = max(0, min(255, int(255 * shade)))
                scaled.fill((ds, ds, ds), special_flags=pygame.BLEND_MULT)
                surface.blit(scaled, (x0, top))
            else:
                tex = None
        if tex is None:
            color = wall_color(
                mx, my, side, hit_x, hit_y, tile_size, distance_shade, wall_char=wall_char
            )
            pygame.draw.rect(surface, color, (x0, top, w, line_h))

        if i < n - 1:
            dist2, mx2, my2, side2, _, _, _ = ray_hits[i + 1]
            if (
                mx != -1
                and mx2 != -1
                and (mx, my, side) != (mx2, my2, side2)
                and not math.isinf(dist2)
                and dist2 > 0
            ):
                d2 = max(float(dist2), 1e-3)
                line_h2 = int((tile_size * proj_plane) / d2)
                line_h2 = min(line_h2, screen_h * 2)
                if line_h2 < 1:
                    y0, y1 = top, top + line_h - 1
                else:
                    hy_i2 = _horizon_y_at_ray_column(i + 1, n, screen_h, pitch_offset_px, horizon_skew_px)
                    top2 = hy_i2 - line_h2 // 2
                    y0 = min(top, top2)
                    y1 = max(top + line_h, top2 + line_h2) - 1
                px_line = x1 - 1
                pygame.draw.line(surface, cfg.OUTLINE_COLOR, (px_line, y0), (px_line, y1), cfg.OUTLINE_WIDTH)

        if (
            tex is None
            and wall_char in ("1", "2", "3", "9")
            and cfg.WALL_BANDS > 1
            and line_h > cfg.WALL_BANDS * 3
        ):
            for b in range(1, cfg.WALL_BANDS):
                y = top + (b * line_h) // cfg.WALL_BANDS
                pygame.draw.line(
                    surface,
                    cfg.OUTLINE_COLOR,
                    (x0, y),
                    (x0 + w - 1, y),
                    cfg.OUTLINE_WIDTH,
                )
