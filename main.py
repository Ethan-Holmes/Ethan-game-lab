import json
import math
import os
import random
from dataclasses import dataclass

import pygame

# init
pygame.init()
try:
    pygame.mixer.init()
except pygame.error:
    pass  # no audio device — SOUND_* will stay None

# Fullscreen at the monitor's current resolution (0, 0) = desktop size.
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
pygame.display.set_caption("Pygame Test")

# Keep the playable area size handy for positioning sprites, UI, etc.
SCREEN_WIDTH = screen.get_width()
SCREEN_HEIGHT = screen.get_height()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, "assets")
SAVE_FILE_PATH = os.path.join(SCRIPT_DIR, "savegame.json")
# assets/<filename> — map cell char → texture file (multiple chars may share one file).
WALL_TEXTURE_FILES = {
    "1": "stone.png",
    "2": "grass.png",
}


def _ensure_default_wall_assets(assets_dir):
    """Create simple placeholder PNGs in assets/ if missing (so load succeeds first run)."""
    os.makedirs(assets_dir, exist_ok=True)
    stone_path = os.path.join(assets_dir, "stone.png")
    grass_path = os.path.join(assets_dir, "grass.png")
    if not os.path.isfile(stone_path):
        s = pygame.Surface((64, 64))
        s.fill((118, 108, 92))
        for x in range(0, 64, 8):
            pygame.draw.line(s, (88, 80, 68), (x, 0), (x, 63), 1)
        for y in range(0, 64, 8):
            pygame.draw.line(s, (88, 80, 68), (0, y), (63, y), 1)
        pygame.image.save(s, stone_path)
    if not os.path.isfile(grass_path):
        g = pygame.Surface((64, 64))
        g.fill((52, 128, 58))
        for _ in range(500):
            x, y = random.randint(0, 63), random.randint(0, 63)
            g.set_at(
                (x, y),
                (
                    random.randint(55, 95),
                    random.randint(130, 175),
                    random.randint(48, 85),
                ),
            )
        pygame.image.save(g, grass_path)


def _load_wall_textures(assets_dir):
    """Load wall textures into a dict keyed by map char; None if a file fails."""
    out = {}
    for key, fname in WALL_TEXTURE_FILES.items():
        path = os.path.join(assets_dir, fname)
        try:
            out[key] = pygame.image.load(path).convert()
        except Exception:
            out[key] = None
    return out


def _load_sfx_first_available(candidates):
    """Return pygame.mixer.Sound for first existing path, or None."""
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            return pygame.mixer.Sound(path)
        except Exception:
            continue
    return None


def _play_sfx(sound):
    """Play a loaded sound using module-level SFX_VOLUME (0.0–1.0)."""
    if sound is None:
        return
    sound.set_volume(max(0.0, min(1.0, SFX_VOLUME)))
    sound.play()


_ensure_default_wall_assets(ASSETS_DIR)
WALL_TEXTURES = _load_wall_textures(ASSETS_DIR)

# Sound effects (prefer .wav; .mp3 fallback if present). Tune SFX_VOLUME globally.
SFX_VOLUME = 0.75
SOUND_GUNSHOT = _load_sfx_first_available(
    [os.path.join(ASSETS_DIR, "gunshot.wav"), os.path.join(ASSETS_DIR, "gunshot.mp3")]
)
SOUND_HIT = _load_sfx_first_available(
    [os.path.join(ASSETS_DIR, "hit.wav"), os.path.join(ASSETS_DIR, "hit.mp3")]
)

# Limit how fast the loop runs (frames per second). tick() sleeps to hit the target FPS.
clock = pygame.time.Clock()

# Day/night: continuous sine loop; post-multiply on VIEW_BUFFER (subtle dim + cool tint at night).
DAY_NIGHT_PERIOD_SEC = 200.0
DAY_NIGHT_MULT_MIN = (0.76, 0.80, 0.92)  # night (slightly cooler)
DAY_NIGHT_MULT_MAX = (1.0, 1.0, 1.0)

# Raycast scene: ceiling / floor (classic “sky” and “ground” bands).
CEILING_COLOR = (28, 28, 42)
FLOOR_COLOR = (42, 34, 28)
# Base wall tint before distance shading.
WALL_COLOR_BASE = (175, 155, 130)
# Past this distance, walls are at minimum brightness.
MAX_SHADE_DISTANCE = 720.0
# Dark edges between grid blocks (vertical + optional horizontal bands).
OUTLINE_COLOR = (22, 20, 18)
OUTLINE_WIDTH = 1
# Horizontal “mortar” lines across each wall strip (0 = off).
WALL_BANDS = 4

# Minimap (top-right HUD; world coords → tiny grid).
MINIMAP_CELL_PX = 5
MINIMAP_MARGIN = 14
MINIMAP_PAD = 2
MINIMAP_BG = (14, 14, 22)
MINIMAP_BORDER = (70, 75, 90)
MINIMAP_WALL = (52, 52, 62)
MINIMAP_FLOOR = (26, 26, 34)
MINIMAP_PLAYER = (130, 255, 150)
MINIMAP_DIR_LEN = 10

# HUD (top-left stack; single font for readability).
HUD_FONT_SIZE = 32
HUD_MARGIN_X = 18
HUD_MARGIN_Y = 14
HUD_LINE_SKIP = 6
HUD_TEXT = (235, 235, 242)
HUD_SHADOW = (12, 12, 18)
# Sprint / stamina (hold Shift; speed eases toward walk or sprint).
PLAYER_SPEED_WALK = 300.0
PLAYER_SPRINT_MULTIPLIER = 1.52
MOVE_SPEED_SMOOTH_RATE = 14.0
STAMINA_MAX = 100.0
STAMINA_DRAIN_PER_SEC = 44.0
STAMINA_REGEN_PER_SEC = 24.0
STAMINA_MIN_TO_SPRINT = 1.5
STAMINA_BAR_W = 220
STAMINA_BAR_H = 10

# Objectives (expand later: multiple goals, flags, scripted waves).
OBJECTIVE_ELIMINATE = "Eliminate all enemies"

# Inventory: simple counts (expand later, e.g. dict of item_id -> count).
INVENTORY_BLOCKS_START = 50

# Player health (contact damage from nearby enemies).
PLAYER_HP_MAX = 100
ENEMY_CONTACT_RANGE = 52.0  # world pixels — enemy closer than this drains HP
ENEMY_CONTACT_DPS = 22.0  # damage per second per enemy in range

# World: infinite procedural grid + sparse edits (destroyed walls). '0' = floor; non-'0' = wall.
# Chunks are CHUNK_SIZE × CHUNK_SIZE cells; only chunks within Chebyshev radius CHUNK_LOAD_RADIUS
# of the player's chunk are simulated (else treated as solid for physics/rays).
# World scale: one map cell = TILE_SIZE × TILE_SIZE world units (pixels).
TILE_SIZE = 64
# Right-click build: max range from player (world px) along view ray.
PLACE_BLOCK_MAX_DIST = 3.0 * TILE_SIZE
CHUNK_SIZE = 10  # cells per chunk edge
# Chebyshev distance in chunk space: keep (2*R+1)² chunks around the player (e.g. R=3 → 7×7 chunks).
CHUNK_LOAD_RADIUS = 3
# Perlin terrain: lower threshold → more open floor; higher → denser wall clusters.
TERRAIN_NOISE_SCALE = 0.065
TERRAIN_WALL_THRESHOLD = 0.46
TERRAIN_OCTAVES = 3
# Minimap: half-width in cells (window is 2*extent+1 square, centered on player).
MINIMAP_HALF_EXTENT = 12
# Raycasting: horizontal fan of rays — one per screen column for a sharp 3D strip.
FOV = math.pi / 3
NUM_RAYS = SCREEN_WIDTH

# Moving enemies: [x, y, wander_heading_rad, hp, shoot_cd, ai_state] in world pixels.
ENEMY_COUNT = 3
ENEMY_SPEED = 85.0  # pixels per second
ENEMY_HIT_RADIUS = 28.0
ENEMY_HP_MAX = 100.0
# AI states (simple FSM; index stored on each enemy).
ENEMY_ST_IDLE = 0
ENEMY_ST_CHASING = 1
ENEMY_ST_ATTACKING = 2
# Idle → chase when player this close; chase/attack → idle beyond this (hysteresis).
ENEMY_DETECT_RANGE = 480.0
ENEMY_LOST_RANGE = 620.0
# Chasing → hold position and shoot; leave attacking if player backs past this.
ENEMY_ATTACK_RANGE = 400.0
ENEMY_ATTACK_LEAVE_RANGE = 468.0
# Legacy name: same as detect (chase when aware).
ENEMY_AGRO_RANGE = ENEMY_DETECT_RANGE
# Inside this radius, stop closing in (avoids jitter on the player's cell).
ENEMY_MIN_MOVE_DIST = 16.0
# Wander: heading drifts by up to this many rad/s (continuous smooth paths).
ENEMY_WANDER_TURN_MAX = 1.35
# Billboard size in world units (width × height) — scales with distance like walls.
ENEMY_SPRITE_WIDTH = 40.0
ENEMY_SPRITE_HEIGHT = 56.0
ENEMY_COLOR = (230, 70, 70)
ENEMY_EDGE_COLOR = (40, 20, 20)
# Ranged attacks: ray toward player; blocked by walls (same cast_ray as rendering).
ENEMY_SHOOT_RANGE = 540.0
ENEMY_SHOOT_COOLDOWN = 1.2  # seconds between enemy shots (per enemy)
ENEMY_SHOOT_DAMAGE = 10.0
ENEMY_SHOOT_LOS_EPS = 16.0  # wall must be at least this far past player along ray to count as block

# ---------------------------------------------------------------------------
# Player & session state (mutable; read/written in main loop)
# ---------------------------------------------------------------------------
player_angle = 0.0
move_speed_smoothed = PLAYER_SPEED_WALK
stamina = float(STAMINA_MAX)
mouse_sensitivity = 0.0025
player_health = float(PLAYER_HP_MAX)
game_over = False
inventory_blocks = INVENTORY_BLOCKS_START
# Enemy entities: single list mutated by spawn, save/load, and combat (never rebind the name).
ENEMIES = []
enemies_defeated = 0
wave_number = 1

# Procedural world + streaming (updated each frame from player position).
world_gen_seed = 7
world_cell_edits = {}  # (mx, my) -> char; overrides procedural / cached chunk for that cell
_chunk_player_cx = 0
_chunk_player_cy = 0
# Persistent memo: (chunk_x, chunk_y) -> CHUNK_SIZE×CHUNK_SIZE grid; each chunk generated at most once.
chunk_cache = {}
# Chunks within CHUNK_LOAD_RADIUS of the player (simulated / not LOD-solid); updated every frame.
_active_chunk_keys = set()

# Perlin permutation (512 entries) + world-space offsets; rebuilt when world_gen_seed changes.
_perlin_perm = None
_terrain_off_x = 0.0
_terrain_off_y = 0.0


def _init_perlin_noise(seed):
    """Shuffle permutation table and pick terrain offsets so each seed differs."""
    global _perlin_perm, _terrain_off_x, _terrain_off_y
    rng = random.Random(seed)
    p = list(range(256))
    rng.shuffle(p)
    _perlin_perm = p + p
    _terrain_off_x = rng.uniform(0.0, 10000.0)
    _terrain_off_y = rng.uniform(0.0, 10000.0)


def _fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


def _lerp(a, b, t):
    return a + t * (b - a)


def _perlin_grad(h, x, y):
    """Gradient dot (distance from grid corner); hash picks quadrant blend (classic 2D Perlin style)."""
    h = h & 15
    u = x if h < 8 else y
    v = y if h < 4 else x
    return (u if (h & 1) == 0 else -u) + (v if (h & 2) == 0 else -v)


def _perlin2(x, y):
    """Single octave 2D Perlin noise, ~[-1, 1]."""
    p = _perlin_perm
    xi = int(math.floor(x)) & 255
    yi = int(math.floor(y)) & 255
    xf = x - math.floor(x)
    yf = y - math.floor(y)
    u = _fade(xf)
    v = _fade(yf)
    aa = p[p[xi] + yi]
    ab = p[p[xi] + yi + 1]
    ba = p[p[xi + 1] + yi]
    bb = p[p[xi + 1] + yi + 1]
    x1 = _lerp(_perlin_grad(aa, xf, yf), _perlin_grad(ba, xf - 1, yf), u)
    x2 = _lerp(_perlin_grad(ab, xf, yf - 1), _perlin_grad(bb, xf - 1, yf - 1), u)
    return _lerp(x1, x2, v)


def _terrain_noise01(mx, my):
    """Fractal sum of Perlin octaves → roughly [0, 1]; smooth blobs and corridors."""
    ox = mx + _terrain_off_x
    oy = my + _terrain_off_y
    s = 0.0
    a = 0.5
    f = TERRAIN_NOISE_SCALE
    w = 0.0
    for _ in range(TERRAIN_OCTAVES):
        s += a * _perlin2(ox * f, oy * f)
        w += a
        a *= 0.5
        f *= 2.0
    s = s / max(w, 1e-6)
    return max(0.0, min(1.0, (s + 1.0) * 0.5))


def procedural_cell(mx, my):
    """Deterministic floor / wall from Perlin terrain + solid chunk boundaries (two wall chars)."""
    cx = mx // CHUNK_SIZE
    cy = my // CHUNK_SIZE
    lx = mx - cx * CHUNK_SIZE
    ly = my - cy * CHUNK_SIZE
    if lx == 0 or lx == CHUNK_SIZE - 1 or ly == 0 or ly == CHUNK_SIZE - 1:
        return "1"
    n = _terrain_noise01(mx, my)
    if n < TERRAIN_WALL_THRESHOLD:
        return "0"
    n2 = _terrain_noise01(mx + 31.7, my + 17.3)
    return "2" if n2 >= TERRAIN_WALL_THRESHOLD else "1"


_init_perlin_noise(world_gen_seed)


def generate_chunk_grid(chunk_x, chunk_y):
    """Build one chunk’s cells from procedural_cell (used only when filling the cache)."""
    rows = []
    for ly in range(CHUNK_SIZE):
        row = []
        base_my = chunk_y * CHUNK_SIZE + ly
        for lx in range(CHUNK_SIZE):
            mx = chunk_x * CHUNK_SIZE + lx
            row.append(procedural_cell(mx, base_my))
        rows.append(row)
    return rows


def get_chunk_cached(chunk_x, chunk_y):
    """Return cached chunk data; generate and store on first request for this coordinate."""
    key = (chunk_x, chunk_y)
    if key not in chunk_cache:
        chunk_cache[key] = generate_chunk_grid(chunk_x, chunk_y)
    return chunk_cache[key]


def sample_world_cell(mx, my):
    """Authoritative cell: edits override cache, then cached chunk if visited, else procedural."""
    k = (mx, my)
    if k in world_cell_edits:
        return world_cell_edits[k]
    cx, cy = chunk_coords_for_cell(mx, my)
    ch = chunk_cache.get((cx, cy))
    if ch is not None:
        lx = mx - cx * CHUNK_SIZE
        ly = my - cy * CHUNK_SIZE
        return ch[ly][lx]
    return procedural_cell(mx, my)


def chunk_coords_for_cell(mx, my):
    """Chunk index (cx, cy) containing map cell (mx, my)."""
    return mx // CHUNK_SIZE, my // CHUNK_SIZE


def chunk_is_active(mx, my):
    cx, cy = chunk_coords_for_cell(mx, my)
    return (cx, cy) in _active_chunk_keys


def lod_world_cell(mx, my):
    """Cell for simulation: outside loaded chunks reads as solid ('1') so nothing leaks into void."""
    if not chunk_is_active(mx, my):
        return "1"
    return sample_world_cell(mx, my)


def update_chunk_streaming(px, py, tile_size):
    """
    Track which chunks are simulated (near player). Ensure each active chunk is in chunk_cache
    via get_chunk_cached — never regenerates an already-cached chunk.
    """
    global _chunk_player_cx, _chunk_player_cy, _active_chunk_keys
    pmx = int(math.floor(px / tile_size))
    pmy = int(math.floor(py / tile_size))
    _chunk_player_cx, _chunk_player_cy = chunk_coords_for_cell(pmx, pmy)
    active = set()
    for dcx in range(-CHUNK_LOAD_RADIUS, CHUNK_LOAD_RADIUS + 1):
        for dcy in range(-CHUNK_LOAD_RADIUS, CHUNK_LOAD_RADIUS + 1):
            active.add((_chunk_player_cx + dcx, _chunk_player_cy + dcy))
    _active_chunk_keys = active
    for cx, cy in active:
        get_chunk_cached(cx, cy)


def find_spawn_and_enemies(tile_size, num_enemies=ENEMY_COUNT, rng=None):
    """Spiral from origin for a floor cell (sample_world_cell); place enemies on nearby floors."""
    rng = rng or random
    found = None
    for radius in range(0, 256):
        for mx in range(-radius, radius + 1):
            for my in range(-radius, radius + 1):
                if max(abs(mx), abs(my)) != radius:
                    continue
                if sample_world_cell(mx, my) == "0":
                    found = (mx, my)
                    break
            if found:
                break
        if found:
            break
    if not found:
        world_cell_edits[(0, 0)] = "0"
        found = (0, 0)
    pmx, pmy = found
    player_x = (pmx + 0.5) * tile_size
    player_y = (pmy + 0.5) * tile_size

    floors = []
    for radius in range(1, 96):
        for mx in range(pmx - radius, pmx + radius + 1):
            for my in range(pmy - radius, pmy + radius + 1):
                if max(abs(mx - pmx), abs(my - pmy)) != radius:
                    continue
                if sample_world_cell(mx, my) == "0":
                    floors.append((mx, my))
        if len(floors) >= num_enemies + 8:
            break
    rng.shuffle(floors)
    enemies = []
    for mx, my in floors:
        if mx == pmx and my == pmy:
            continue
        if len(enemies) >= num_enemies:
            break
        enemies.append(
            [
                (mx + 0.5) * tile_size,
                (my + 0.5) * tile_size,
                rng.uniform(0, 2 * math.pi),
                float(ENEMY_HP_MAX),
                rng.uniform(0, ENEMY_SHOOT_COOLDOWN * 0.9),
                ENEMY_ST_IDLE,
            ]
        )
    return player_x, player_y, enemies


def spawn_enemies_near(px, py, tile_size, num_enemies, rng=None):
    """Place enemies on floor cells in rings around the player (for mid-game waves)."""
    rng = rng or random
    pmx = int(math.floor(px / tile_size))
    pmy = int(math.floor(py / tile_size))
    floors = []
    for radius in range(1, 96):
        for mx in range(pmx - radius, pmx + radius + 1):
            for my in range(pmy - radius, pmy + radius + 1):
                if max(abs(mx - pmx), abs(my - pmy)) != radius:
                    continue
                if sample_world_cell(mx, my) == "0":
                    floors.append((mx, my))
        if len(floors) >= num_enemies + 8:
            break
    rng.shuffle(floors)
    out = []
    for mx, my in floors:
        if mx == pmx and my == pmy:
            continue
        if len(out) >= num_enemies:
            break
        out.append(
            [
                (mx + 0.5) * tile_size,
                (my + 0.5) * tile_size,
                rng.uniform(0, 2 * math.pi),
                float(ENEMY_HP_MAX),
                rng.uniform(0, ENEMY_SHOOT_COOLDOWN * 0.9),
                ENEMY_ST_IDLE,
            ]
        )
    return out


def spawn_next_wave():
    """Optional: new enemy wave after LEVEL COMPLETE (same ENEMIES list, wave counter +1)."""
    global wave_number
    rng = random.Random()
    spawned = spawn_enemies_near(player_x, player_y, TILE_SIZE, ENEMY_COUNT, rng=rng)
    ENEMIES.clear()
    ENEMIES.extend(spawned)
    wave_number += 1


def regenerate_world_map(seed=None):
    """
    New world seed, clear edits, re-place player and enemies.
    Resets health and game_over for a fresh run.
    """
    global world_gen_seed, world_cell_edits, chunk_cache, player_x, player_y, player_angle
    global player_health, game_over, player_bullets, weapon_ammo, reload_timers, inventory_blocks
    global stamina, move_speed_smoothed, enemies_defeated, wave_number
    rng = random.Random(seed) if seed is not None else random
    world_gen_seed = rng.randint(1, 2**30)
    _init_perlin_noise(world_gen_seed)
    world_cell_edits.clear()
    chunk_cache.clear()
    player_x, player_y, spawned = find_spawn_and_enemies(TILE_SIZE, ENEMY_COUNT, rng=rng)
    ENEMIES.clear()
    ENEMIES.extend(spawned)
    update_chunk_streaming(player_x, player_y, TILE_SIZE)
    player_angle = 0.0
    player_health = float(PLAYER_HP_MAX)
    game_over = False
    player_bullets.clear()
    weapon_ammo[:] = [w.magazine_size for w in WEAPONS]
    reload_timers[:] = [0.0] * len(WEAPONS)
    inventory_blocks = INVENTORY_BLOCKS_START
    stamina = float(STAMINA_MAX)
    move_speed_smoothed = PLAYER_SPEED_WALK
    enemies_defeated = 0
    wave_number = 1


def apply_save_data(data):
    """Restore world + player from a JSON dict (see save_game_to_file)."""
    global world_gen_seed, world_cell_edits, chunk_cache, player_x, player_y, player_angle
    global ENEMIES
    global player_health, inventory_blocks, game_over, player_bullets, stamina, move_speed_smoothed
    global enemies_defeated, wave_number
    world_gen_seed = int(data["world_gen_seed"])
    _init_perlin_noise(world_gen_seed)
    chunk_cache.clear()
    for key, grid in data["chunk_cache"].items():
        cx, cy = key.split(",")
        chunk_cache[(int(cx), int(cy))] = [list(row) for row in grid]
    world_cell_edits.clear()
    for key, ch in data["world_cell_edits"].items():
        mx, my = key.split(",")
        world_cell_edits[(int(mx), int(my))] = str(ch)
    player_x = float(data["player_x"])
    player_y = float(data["player_y"])
    player_angle = float(data["player_angle"])
    player_health = float(data.get("player_health", PLAYER_HP_MAX))
    inventory_blocks = int(data.get("inventory_blocks", INVENTORY_BLOCKS_START))
    stamina = float(data.get("stamina", STAMINA_MAX))
    move_speed_smoothed = float(data.get("move_speed_smoothed", PLAYER_SPEED_WALK))
    enemies_defeated = int(data.get("enemies_defeated", 0))
    wave_number = int(data.get("wave_number", 1))
    ENEMIES.clear()
    for e in data.get("enemies", []):
        ENEMIES.append([float(x) for x in e])
    game_over = False
    player_bullets.clear()
    update_chunk_streaming(player_x, player_y, TILE_SIZE)


def save_game_to_file():
    """Write chunk grids, edits, seed, and player state to SAVE_FILE_PATH."""
    chunks = {f"{cx},{cy}": grid for (cx, cy), grid in chunk_cache.items()}
    edits = {f"{mx},{my}": ch for (mx, my), ch in world_cell_edits.items()}
    payload = {
        "version": 1,
        "world_gen_seed": world_gen_seed,
        "chunk_cache": chunks,
        "world_cell_edits": edits,
        "player_x": player_x,
        "player_y": player_y,
        "player_angle": player_angle,
        "player_health": player_health,
        "inventory_blocks": inventory_blocks,
        "stamina": stamina,
        "move_speed_smoothed": move_speed_smoothed,
        "enemies_defeated": enemies_defeated,
        "wave_number": wave_number,
        "enemies": ENEMIES,
    }
    with open(SAVE_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


player_bullets = []
if os.path.isfile(SAVE_FILE_PATH):
    try:
        with open(SAVE_FILE_PATH, "r", encoding="utf-8") as f:
            apply_save_data(json.load(f))
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        player_x, player_y, spawned = find_spawn_and_enemies(TILE_SIZE, ENEMY_COUNT)
        ENEMIES.clear()
        ENEMIES.extend(spawned)
        update_chunk_streaming(player_x, player_y, TILE_SIZE)
else:
    player_x, player_y, spawned = find_spawn_and_enemies(TILE_SIZE, ENEMY_COUNT)
    ENEMIES.clear()
    ENEMIES.extend(spawned)
    update_chunk_streaming(player_x, player_y, TILE_SIZE)


def _inv_dir_component(v):
    return abs(1.0 / v) if abs(v) > 1e-9 else float("inf")


# Ray march step cap for infinite chunked map (LOD may end rays at “far wall”).
RAYCAST_MAX_STEPS = 512


def cast_ray(px, py, angle, tile_size):
    """
    DDA ray vs grid walls. Returns:
      (perp_distance_world, map_x, map_y, side, hit_x, hit_y, wall_char)
    side: 0 = x-facing wall (E/W), 1 = y-facing wall (N/S).
    wall_char: map cell char at hit ('0' on miss).
    On miss: (inf, -1, -1, -1, 0.0, 0.0, '0').
    """
    pos_x = px / tile_size
    pos_y = py / tile_size
    ray_dir_x = math.cos(angle)
    ray_dir_y = math.sin(angle)

    map_x = int(math.floor(pos_x))
    map_y = int(math.floor(pos_y))

    _cell0 = lod_world_cell(map_x, map_y)
    if _cell0 != "0":
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

    for _ in range(RAYCAST_MAX_STEPS):
        if side_dist_x < side_dist_y:
            side_dist_x += delta_dist_x
            map_x += step_x
            side = 0
        else:
            side_dist_y += delta_dist_y
            map_y += step_y
            side = 1

        _cell = lod_world_cell(map_x, map_y)
        if _cell != "0":
            if side == 0:
                perp = (map_x - pos_x + (1 - step_x) / 2) / ray_dir_x
            else:
                perp = (map_y - pos_y + (1 - step_y) / 2) / ray_dir_y
            perp_world = abs(perp) * tile_size
            # Distance along ray to intersection (for hit point on the wall face).
            if side == 0:
                d_along = perp_world / max(abs(ray_dir_x), 1e-9)
            else:
                d_along = perp_world / max(abs(ray_dir_y), 1e-9)
            hit_x = px + ray_dir_x * d_along
            hit_y = py + ray_dir_y * d_along
            return perp_world, map_x, map_y, side, hit_x, hit_y, _cell

    return float("inf"), -1, -1, -1, 0.0, 0.0, "0"


def placement_cell_in_front_of_hit(mx, my, side, yaw):
    """
    Grid cell adjacent to the struck wall face on the player's side (along the ray).
    DDA stepped into (mx, my); the prior cell is one step back along the ray axis that moved.
    """
    ray_dir_x = math.cos(yaw)
    ray_dir_y = math.sin(yaw)
    step_x = -1 if ray_dir_x < 0 else 1
    step_y = -1 if ray_dir_y < 0 else 1
    if side == 0:
        return mx - step_x, my
    return mx, my - step_y


def try_place_wall_block(px, py, yaw, tile_size, enemies, max_dist_world):
    """
    Place a stone wall ('1') in the floor cell just in front of the centered ray hit.
    Uses the same grid as world_cell_edits; only on empty floor in loaded chunks.
    Consumes one block from inventory on success.
    """
    global inventory_blocks
    if inventory_blocks <= 0:
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
    if sample_world_cell(cx, cy) != "0":
        return False

    pmx = int(math.floor(px / tile_size))
    pmy = int(math.floor(py / tile_size))
    if (cx, cy) == (pmx, pmy):
        return False

    for e in enemies:
        emx = int(math.floor(e[0] / tile_size))
        emy = int(math.floor(e[1] / tile_size))
        if (emx, emy) == (cx, cy):
            return False

    world_cell_edits[(cx, cy)] = "1"
    inventory_blocks -= 1
    return True


def world_pos_to_grid(wx, wy, tile_size):
    """Map world pixel coordinates to grid cell indices (floor of tile coords)."""
    return int(math.floor(wx / tile_size)), int(math.floor(wy / tile_size))


def compute_ray_hits(px, py, yaw, tile_size, fov, num_rays):
    """One hit tuple per ray, left to right across the field of view."""
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
    """True if the grid cell under this world position is walkable floor (loaded chunk)."""
    mx = int(math.floor(wx / tile_size))
    my = int(math.floor(wy / tile_size))
    return lod_world_cell(mx, my) == "0"


def enemy_clear_shot_to_player(ex, ey, px, py, tile_size):
    """
    True if a ray from the enemy toward the player hits no wall before reaching the player.
    Uses Euclidean distance to the wall hit vs to the player (cheap one cast_ray per check).
    """
    dx = px - ex
    dy = py - ey
    dist_p = math.hypot(dx, dy)
    if dist_p < 1e-6:
        return True
    ang = math.atan2(dy, dx)
    d_wall, _mx, _my, _side, hx, hy, _wc = cast_ray(ex, ey, ang, tile_size)
    if math.isinf(d_wall):
        return True
    dist_w = math.hypot(hx - ex, hy - ey)
    return dist_w >= dist_p - ENEMY_SHOOT_LOS_EPS


def update_enemy_shooting(enemies, px, py, dt, tile_size):
    """
    Only enemies in ATTACKING state shoot. Per-enemy cooldown, range, LOS.
    Returns total damage to apply to the player this frame.
    """
    dmg = 0.0
    for e in enemies:
        if len(e) < 5:
            e.append(0.0)
        if len(e) < 6:
            e.append(ENEMY_ST_IDLE)
        if e[5] != ENEMY_ST_ATTACKING:
            e[4] = max(0.0, e[4] - dt)
            continue
        ex, ey = e[0], e[1]
        e[4] = max(0.0, e[4] - dt)
        dist = math.hypot(px - ex, py - ey)
        if dist > ENEMY_SHOOT_RANGE or e[4] > 0:
            continue
        if not enemy_clear_shot_to_player(ex, ey, px, py, tile_size):
            continue
        dmg += ENEMY_SHOOT_DAMAGE
        e[4] = ENEMY_SHOOT_COOLDOWN
    return dmg


def _enemy_try_slide(ex, ey, mx, my, step, tile_size):
    """
    Try diagonal move, then axis slides, then shorter steps — smooth motion along walls
    without pathfinding.
    """
    for scale in (1.0, 0.55, 0.28):
        s = step * scale
        nx = ex + mx * s
        ny = ey + my * s
        if can_walk_world(nx, ny, tile_size):
            return nx, ny
        if can_walk_world(nx, ey, tile_size):
            return nx, ey
        if can_walk_world(ex, ny, tile_size):
            return ex, ny
    return ex, ey


def update_enemies(enemies, px, py, dt, tile_size):
    """
    Each enemy is [x, y, wander_heading, hp, shoot_cd, ai_state].
    Idle: wander. Chasing: move toward player. Attacking: hold position (shoot handled elsewhere).
    Transitions use distance hysteresis to avoid flicker.
    """
    for e in enemies:
        if len(e) < 3:
            e.append(random.uniform(0, 2 * math.pi))
        if len(e) < 4:
            e.append(float(ENEMY_HP_MAX))
        if len(e) < 5:
            e.append(0.0)
        if len(e) < 6:
            e.append(ENEMY_ST_IDLE)

        ex, ey = e[0], e[1]
        wander_ang = e[2]
        st = e[5]
        dx = px - ex
        dy = py - ey
        dist_sq = dx * dx + dy * dy
        if dist_sq < 1e-8:
            continue
        dist = math.sqrt(dist_sq)

        # --- state transitions (order: lose player first, then escalate) ---
        if dist > ENEMY_LOST_RANGE:
            st = ENEMY_ST_IDLE
        elif st == ENEMY_ST_IDLE:
            if dist <= ENEMY_DETECT_RANGE:
                st = ENEMY_ST_CHASING
        elif st == ENEMY_ST_CHASING:
            if dist <= ENEMY_ATTACK_RANGE:
                st = ENEMY_ST_ATTACKING
        elif st == ENEMY_ST_ATTACKING:
            if dist > ENEMY_ATTACK_LEAVE_RANGE:
                st = ENEMY_ST_CHASING
        e[5] = st

        if st == ENEMY_ST_ATTACKING:
            e[2] = wander_ang
            continue

        if dist < ENEMY_MIN_MOVE_DIST:
            e[2] = wander_ang
            continue

        step = ENEMY_SPEED * dt
        if st == ENEMY_ST_CHASING:
            move_ang = math.atan2(dy, dx)
        else:
            wander_ang += random.uniform(-ENEMY_WANDER_TURN_MAX, ENEMY_WANDER_TURN_MAX) * dt
            move_ang = wander_ang

        mx = math.cos(move_ang)
        my = math.sin(move_ang)
        nx, ny = _enemy_try_slide(ex, ey, mx, my, step, tile_size)
        e[0], e[1] = nx, ny
        e[2] = wander_ang


def spawn_player_bullet(bullets, px, py, angle, wpn):
    """Append one projectile; respects BULLET_MAX_ALIVE."""
    if len(bullets) >= BULLET_MAX_ALIVE:
        return
    c = math.cos(angle)
    s = math.sin(angle)
    o = BULLET_SPAWN_OFFSET
    bullets.append(
        [
            px + c * o,
            py + s * o,
            angle,
            0.0,
            wpn.damage,
            1 if wpn.destroys_wall else 0,
            wpn.bullet_speed,
        ]
    )


def update_player_bullets(bullets, dt, tile_size, enemies):
    """Move bullets, wall/enemy hits, range limit; mutates bullets and enemies. Returns enemy hits."""
    global enemies_defeated
    hits = 0
    i = 0
    while i < len(bullets):
        b = bullets[i]
        bx, by, ang, dist_acc, dmg, dest_wall, bspd = (
            b[0],
            b[1],
            b[2],
            b[3],
            b[4],
            b[5],
            b[6],
        )
        step = bspd * dt
        nx = bx + math.cos(ang) * step
        ny = by + math.sin(ang) * step
        dist_acc += step

        if dist_acc >= BULLET_MAX_RANGE:
            bullets.pop(i)
            continue

        mx = int(math.floor(nx / tile_size))
        my = int(math.floor(ny / tile_size))
        cell = lod_world_cell(mx, my)
        if cell != "0":
            if dest_wall and chunk_is_active(mx, my) and sample_world_cell(mx, my) != "0":
                world_cell_edits[(mx, my)] = "0"
            bullets.pop(i)
            continue

        hit_enemy = False
        for ei, e in enumerate(enemies):
            ex, ey = e[0], e[1]
            if math.hypot(nx - ex, ny - ey) <= BULLET_ENEMY_HIT_RADIUS:
                if len(e) < 4:
                    e.append(float(ENEMY_HP_MAX))
                e[3] -= dmg
                _play_sfx(SOUND_HIT)
                if e[3] <= 0:
                    enemies.pop(ei)
                    enemies_defeated += 1
                    print("ENEMY DOWN")
                hits += 1
                hit_enemy = True
                break
        if hit_enemy:
            bullets.pop(i)
            continue

        b[0], b[1], b[3] = nx, ny, dist_acc
        i += 1
    return hits


def draw_player_bullets(
    surface, bullets, px, py, yaw, ray_hits, screen_w, screen_h, fov, pitch_offset_px=0, horizon_skew_px=0.0
):
    """Small bright dots; depth-tested against wall columns (draw after walls, before/after enemies)."""
    if not bullets:
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

    ordered = sorted(bullets, key=lambda bb: -(math.hypot(bb[0] - px, bb[1] - py)))
    cos_y = math.cos(yaw)
    sin_y = math.sin(yaw)
    col = (255, 255, 210)
    glow = (255, 220, 120)

    for b in ordered:
        bx, by = b[0], b[1]
        dist = math.hypot(bx - px, by - py)
        along_t = (bx - px) * cos_y + (by - py) * sin_y
        if along_t <= 0:
            continue
        ang = math.atan2(by - py, bx - px)
        rel = ang - yaw
        while rel > math.pi:
            rel -= 2 * math.pi
        while rel < -math.pi:
            rel += 2 * math.pi
        if abs(rel) > half_fov * 1.02:
            continue
        sx = int(screen_w / 2 + math.tan(rel) * proj_plane)
        if sx < 0 or sx >= screen_w:
            continue
        if along_t >= depth_at_column(sx):
            continue
        hy = horizon_y_at_screen_x(sx, screen_w, n, screen_h, pitch_offset_px, horizon_skew_px)
        r = max(2, min(6, int(320 / max(dist, 6.0))))
        pygame.draw.circle(surface, glow, (sx, hy), r + 1)
        pygame.draw.circle(surface, col, (sx, hy), r)


def draw_enemies(
    surface, enemies, px, py, yaw, ray_hits, screen_w, screen_h, fov, pitch_offset_px=0, horizon_skew_px=0.0
):
    """Billboard rectangles: draw back-to-front; clip columns where the wall ray is closer."""
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

    ordered = sorted(
        enemies,
        key=lambda t: -(math.hypot(t[0] - px, t[1] - py)),
    )

    cos_y = math.cos(yaw)
    sin_y = math.sin(yaw)

    # Enemies are [x, y, wander_heading, hp, shoot_cd, ai_state, …] — only position is drawn.
    for item in ordered:
        tx, ty = item[0], item[1]
        dist = math.hypot(tx - px, ty - py)
        if dist < 1e-3:
            continue
        # Depth along view axis (same units as wall distance from cast_ray).
        along_t = (tx - px) * cos_y + (ty - py) * sin_y
        if along_t <= 0:
            continue

        ang = math.atan2(ty - py, tx - px)
        rel = ang - yaw
        while rel > math.pi:
            rel -= 2 * math.pi
        while rel < -math.pi:
            rel += 2 * math.pi
        if abs(rel) > half_fov * 1.02:
            continue

        sx = screen_w / 2 + math.tan(rel) * proj_plane
        line_h = int((ENEMY_SPRITE_HEIGHT * proj_plane) / dist)
        line_h = min(max(line_h, 2), screen_h * 2)
        half_w = int((ENEMY_SPRITE_WIDTH * proj_plane) / dist / 2)
        half_w = max(half_w, 1)
        left = int(sx - half_w)
        right = int(sx + half_w)

        shade = max(0.35, 1.0 - 0.65 * min(dist / MAX_SHADE_DISTANCE, 1.0))
        r = int(ENEMY_COLOR[0] * shade)
        g = int(ENEMY_COLOR[1] * shade)
        b = int(ENEMY_COLOR[2] * shade)
        fill = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

        any_vis = False
        outline_top = None
        outline_bot = None
        for col in range(left, right):
            if col < 0 or col >= screen_w:
                continue
            if along_t >= depth_at_column(col):
                continue
            hy = horizon_y_at_screen_x(col, screen_w, n, screen_h, pitch_offset_px, horizon_skew_px)
            top = hy - line_h // 2
            bot = top + line_h
            if outline_top is None or top < outline_top:
                outline_top = top
            if outline_bot is None or bot > outline_bot:
                outline_bot = bot
            any_vis = True
            pygame.draw.line(surface, fill, (col, top), (col, top + line_h - 1))
        if any_vis and outline_top is not None and outline_bot is not None:
            pygame.draw.rect(
                surface,
                ENEMY_EDGE_COLOR,
                (left, outline_top, max(1, right - left), outline_bot - outline_top),
                1,
            )


def wall_color(mx, my, side, hit_x, hit_y, tile_size, distance_shade):
    """Slight per-cell tint + face alignment + cheap brick bands (no textures)."""
    br, bg, bb = WALL_COLOR_BASE
    # Per-cell hue shift so neighboring blocks read as separate cubes.
    cell = (mx * 17 + my * 31 + side * 7) & 7
    br = br + (cell - 3) * 4
    bg = bg + ((cell * 2) & 7) - 3
    bb = bb + ((cell * 3) & 5) - 2
    # E/W vs N/S faces read as different planes (classic raycast look).
    if side == 1:
        br, bg, bb = int(br * 0.88), int(bg * 0.88), int(bb * 0.88)
    # Light banding along the face using grid position on the wall (blocky mortar).
    if side == 0:
        u = (hit_y % tile_size) / tile_size
    else:
        u = (hit_x % tile_size) / tile_size
    band = 0.82 + 0.18 * (1 if int(u * 3) % 2 == 0 else 0)
    r = max(0, min(255, int(br * band * distance_shade)))
    g = max(0, min(255, int(bg * band * distance_shade)))
    b = max(0, min(255, int(bb * band * distance_shade)))
    return r, g, b


# Crosshair (HUD only — not tied to player_x / player_y / player_angle).
CROSSHAIR_COLOR = (255, 255, 255)
CROSSHAIR_FLASH_COLOR = (255, 64, 72)
CROSSHAIR_FLASH_DURATION = 0.1  # seconds the “shot” tint stays visible
# Recoil: decays toward 0 after each shot (higher = faster recovery).
RECOIL_RECOVERY = 7.0


@dataclass(frozen=True)
class Weapon:
    """Extend WEAPONS with new entries to add guns; switch with number keys (slot)."""

    slot: int  # key label (1, 2, …)
    name: str
    cooldown: float  # seconds between shots
    recoil_yaw: float  # max yaw kick (radians); scaled ±random like before
    recoil_pitch_px: float  # max pitch kick (pixels)
    damage: float  # per-hit damage to enemies
    destroys_wall: bool  # if True, shots remove a struck wall cell
    bullet_speed: float  # world pixels per second
    magazine_size: int
    reload_time: float  # seconds to refill magazine (R when not full)


WEAPONS = (
    Weapon(1, "Pistol", 0.22, 0.019, 11.0, 26.0, False, 780.0, 12, 1.15),
    Weapon(2, "Rifle", 0.42, 0.041, 24.0, 100.0, True, 860.0, 30, 1.78),
)
weapon_ammo = [w.magazine_size for w in WEAPONS]
reload_timers = [0.0] * len(WEAPONS)
# Player-fired bullets: [x, y, angle, dist_traveled, damage, destroys_wall 0/1, speed].
BULLET_MAX_RANGE = 2600.0
BULLET_MAX_ALIVE = 96
BULLET_SPAWN_OFFSET = 22.0  # spawn in front of player (world px)
BULLET_ENEMY_HIT_RADIUS = 30.0  # combined with enemy size for hit test
# Head bob: vertical sine offset while moving (frequency scales with smoothed move speed).
HEAD_BOB_AMPLITUDE_PX = 3.2
HEAD_BOB_FREQ_HZ = 1.75
HEAD_BOB_REF_SPEED = 300.0
HEAD_BOB_SMOOTH = 14.0  # how fast bob settles when movement stops
CROSSHAIR_HALF_LEN = 10
CROSSHAIR_THICKNESS = 2
# Hit feedback: X at screen center on enemy hit; red vignette when player loses HP.
HIT_MARKER_DURATION = 0.13
HIT_MARKER_HALF_EXTENT = 11
HIT_MARKER_THICKNESS = 3
DAMAGE_FLASH_CAP = 0.34
DAMAGE_FLASH_BASE = 0.055
DAMAGE_FLASH_PER_HP = 0.026
DAMAGE_FLASH_ALPHA_MAX = 118
# Mouse-movement sway (HUD only): nudges crosshair / muzzle; decays toward center.
SWAY_MOUSE_SCALE = 0.055
SWAY_RECOVERY = 11.0
SWAY_MAX_PX = 12.0
# Screen shake on shoot: impulse (px) then smooth decay toward 0 (separate from damage shake).
SCREEN_SHAKE_DECAY = 14.0
SCREEN_SHAKE_IMPULSE_X = 3.0
SCREEN_SHAKE_IMPULSE_Y = 2.6
# Stronger shake on HP loss; decays a bit slower so it feels weighted, not snappy.
DAMAGE_SHAKE_IMPULSE_X = 9.5
DAMAGE_SHAKE_IMPULSE_Y = 8.0
DAMAGE_SHAKE_HP_SCALE = 0.34  # extra scale per HP lost (capped)
DAMAGE_SHAKE_HP_SCALE_CAP = 2.15
DAMAGE_SHAKE_DECAY = 10.5
# Strafe “camera tilt”: horizon skews slightly left/right (pixels at screen edge); eased in/out.
STRAFE_TILT_MAX_PX = 2.6
STRAFE_TILT_SMOOTH = 11.0

# Muzzle flash + particles (screen space, centered on view).
MUZZLE_FLASH_DURATION = 0.075
MUZZLE_FLASH_RADIUS = 32
PARTICLE_BURST_COUNT = 14
PARTICLE_LIFETIME = 0.38
PARTICLE_SPEED_MIN = 130.0
PARTICLE_SPEED_MAX = 300.0
PARTICLE_MAX_ALIVE = 256


def spawn_muzzle_particles(particles, cx, cy):
    """Append outward-moving dots; [x, y, vx, vy, life, max_life]."""
    room = PARTICLE_MAX_ALIVE - len(particles)
    n = min(PARTICLE_BURST_COUNT, max(0, room))
    for _ in range(n):
        a = random.uniform(0, 2 * math.pi)
        sp = random.uniform(PARTICLE_SPEED_MIN, PARTICLE_SPEED_MAX)
        particles.append(
            [float(cx), float(cy), math.cos(a) * sp, math.sin(a) * sp, PARTICLE_LIFETIME, PARTICLE_LIFETIME]
        )


def update_shot_particles(particles, dt):
    """Integrate motion, decrement life, drop expired entries."""
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


def draw_muzzle_flash(surface, cx, cy, timer, duration):
    if timer <= 0:
        return
    t = timer / duration if duration > 0 else 0
    rad = max(6, int(MUZZLE_FLASH_RADIUS * (0.45 + 0.55 * t)))
    col = (255, min(255, 180 + int(75 * t)), 90)
    pygame.draw.circle(surface, col, (int(cx), int(cy)), rad)


def draw_shot_particles(surface, particles):
    for p in particles:
        life = p[4] / p[5] if p[5] > 0 else 0.0
        g = int(200 * life)
        b = int(120 * life)
        pygame.draw.circle(surface, (255, g, b), (int(p[0]), int(p[1])), 2)


def draw_crosshair(surface, center_x, center_y, flash_timer):
    """Draw a small + at the screen center; red tint while flash_timer > 0."""
    half = CROSSHAIR_HALF_LEN
    c = CROSSHAIR_FLASH_COLOR if flash_timer > 0 else CROSSHAIR_COLOR
    t = CROSSHAIR_THICKNESS
    pygame.draw.line(surface, c, (center_x - half, center_y), (center_x + half, center_y), t)
    pygame.draw.line(surface, c, (center_x, center_y - half), (center_x, center_y + half), t)


def draw_hit_marker(surface, cx, cy, timer, duration):
    """Brief X at screen center; fades with remaining timer."""
    if timer <= 0 or duration <= 0:
        return
    t = min(1.0, timer / duration)
    a = max(0, min(255, int(250 * (t ** 0.5))))
    half = HIT_MARKER_HALF_EXTENT
    tt = HIT_MARKER_THICKNESS
    w = half * 2 + tt * 2
    s = pygame.Surface((w, w), pygame.SRCALPHA)
    col = (255, 235, 220, a)
    pygame.draw.line(s, col, (tt, tt), (w - tt, w - tt), tt)
    pygame.draw.line(s, col, (w - tt, tt), (tt, w - tt), tt)
    surface.blit(s, (int(cx) - w // 2, int(cy) - w // 2))


def draw_damage_flash(surface, timer, w, h):
    """Full-screen translucent red; strength follows timer (fast fade)."""
    if timer <= 0:
        return
    tnorm = min(1.0, timer / DAMAGE_FLASH_CAP)
    a = int(DAMAGE_FLASH_ALPHA_MAX * (tnorm ** 0.75))
    a = max(0, min(220, a))
    veil = pygame.Surface((w, h), pygame.SRCALPHA)
    veil.fill((195, 22, 38, a))
    surface.blit(veil, (0, 0))


def draw_minimap(surface, player_x, player_y, player_angle, tile_size, screen_w, enemies=None):
    """Top-down window around player using procedural + edits (not LOD — shows terrain beyond load ring)."""
    ext = MINIMAP_HALF_EXTENT
    pmx = int(math.floor(player_x / tile_size))
    pmy = int(math.floor(player_y / tile_size))
    cols = 2 * ext + 1
    rows = cols
    cell = MINIMAP_CELL_PX
    inner_w = cols * cell
    inner_h = rows * cell
    p = MINIMAP_PAD
    total_w = inner_w + p * 2
    total_h = inner_h + p * 2

    ox = screen_w - MINIMAP_MARGIN - total_w
    oy = MINIMAP_MARGIN

    pygame.draw.rect(surface, MINIMAP_BG, (ox, oy, total_w, total_h))
    pygame.draw.rect(surface, MINIMAP_BORDER, (ox, oy, total_w, total_h), 1)

    base_x = ox + p
    base_y = oy + p

    for j in range(rows):
        my = pmy - ext + j
        for i in range(cols):
            mx = pmx - ext + i
            ch = sample_world_cell(mx, my)
            color = MINIMAP_WALL if ch != "0" else MINIMAP_FLOOR
            pygame.draw.rect(surface, color, (base_x + i * cell, base_y + j * cell, cell, cell))

    # Player position (fractional map coords → minimap pixels, centered window).
    mx = player_x / tile_size
    my = player_y / tile_size
    plx = base_x + (mx - (pmx - ext)) * cell
    ply = base_y + (my - (pmy - ext)) * cell
    pr = max(2, cell // 2)
    pygame.draw.circle(surface, MINIMAP_PLAYER, (int(plx), int(ply)), pr)
    # Facing direction (same yaw as raycasting).
    dx = math.cos(player_angle) * MINIMAP_DIR_LEN
    dy = math.sin(player_angle) * MINIMAP_DIR_LEN
    pygame.draw.line(
        surface,
        MINIMAP_PLAYER,
        (int(plx), int(ply)),
        (int(plx + dx), int(ply + dy)),
        2,
    )

    if enemies:
        for e in enemies:
            emx = e[0] / tile_size
            emy = e[1] / tile_size
            ex = base_x + (emx - (pmx - ext)) * cell
            ey = base_y + (emy - (pmy - ext)) * cell
            pygame.draw.circle(surface, ENEMY_COLOR, (int(ex), int(ey)), max(1, cell // 3))


def draw_stamina_bar(surface, x, y, w, h, cur, max_s):
    """Simple horizontal bar under HUD text."""
    if max_s <= 0:
        return
    t = max(0.0, min(1.0, cur / max_s))
    pygame.draw.rect(surface, (26, 28, 36), (x, y, w, h))
    pygame.draw.rect(surface, (72, 78, 96), (x, y, w, h), 1)
    fill = int(w * t)
    if fill > 0:
        col = (88, 210, 145) if t > 0.22 else (220, 150, 88)
        pygame.draw.rect(surface, col, (x, y, fill, h))


def draw_hud(
    surface,
    health,
    max_hp,
    weapon,
    enemy_count,
    ammo_cur,
    ammo_max,
    reloading,
    block_count,
    stamina_cur,
    stamina_max,
    enemies_defeated_total,
    wave_n,
):
    """Minimal top-left: health, weapon, ammo, enemies, objectives, blocks, stamina + bar."""
    font = pygame.font.Font(None, HUD_FONT_SIZE)
    ammo_line = f"Ammo: {ammo_cur} / {ammo_max}"
    if reloading:
        ammo_line = "Reloading…"
    lines = (
        f"HP: {int(max(0, health))} / {max_hp}",
        f"Weapon: [{weapon.slot}] {weapon.name}",
        ammo_line,
        f"Enemies: {enemy_count}",
        f"Objective: {OBJECTIVE_ELIMINATE}",
        f"Defeated: {enemies_defeated_total}",
        f"Wave: {wave_n}",
        f"Blocks: {block_count}",
        f"Stamina: {int(stamina_cur)} / {int(stamina_max)}",
    )
    y = HUD_MARGIN_Y
    shadow_off = 1
    for line in lines:
        sh = font.render(line, True, HUD_SHADOW)
        fg = font.render(line, True, HUD_TEXT)
        surface.blit(sh, (HUD_MARGIN_X + shadow_off, y + shadow_off))
        surface.blit(fg, (HUD_MARGIN_X, y))
        y += font.get_linesize() + HUD_LINE_SKIP
    draw_stamina_bar(surface, HUD_MARGIN_X, y, STAMINA_BAR_W, STAMINA_BAR_H, stamina_cur, stamina_max)


def draw_game_over_overlay(surface, screen_w, screen_h):
    """Light dim + large centered title; 3D view remains visible underneath."""
    veil = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 100))
    surface.blit(veil, (0, 0))

    font = pygame.font.Font(None, 112)
    msg = "GAME OVER"
    shadow = font.render(msg, True, (0, 0, 0))
    fg = font.render(msg, True, (255, 235, 235))
    rect = fg.get_rect(center=(screen_w // 2, screen_h // 2))
    surface.blit(shadow, (rect.x + 4, rect.y + 4))
    surface.blit(fg, rect)


def draw_level_complete_overlay(surface, screen_w, screen_h):
    """Center banner when all enemies are cleared (expand: timers, stats, next level id)."""
    font = pygame.font.Font(None, 96)
    msg = "LEVEL COMPLETE"
    shadow = font.render(msg, True, (0, 0, 0))
    fg = font.render(msg, True, (120, 255, 180))
    rect = fg.get_rect(center=(screen_w // 2, screen_h // 2 - 24))
    surface.blit(shadow, (rect.x + 4, rect.y + 4))
    surface.blit(fg, rect)
    hint_font = pygame.font.Font(None, 28)
    hint = "Press N — next wave"
    hs = hint_font.render(hint, True, (0, 0, 0))
    hf = hint_font.render(hint, True, (200, 220, 210))
    hr = hf.get_rect(center=(screen_w // 2, screen_h // 2 + 48))
    surface.blit(hs, (hr.x + 2, hr.y + 2))
    surface.blit(hf, hr)


def _wall_texture_u(hit_x, hit_y, tile_size, side):
    """Fraction along the wall face (0..1) for sampling a vertical texture column."""
    if side == 0:
        return (hit_y % tile_size) / tile_size
    return (hit_x % tile_size) / tile_size


def _horizon_y_at_ray_column(i, n, screen_h, pitch_offset_px, horizon_skew_px):
    """Horizon row for ray column i; horizon_skew_px tilts the view along the width (strafe lean)."""
    u = (2.0 * i / (n - 1) - 1.0) if n > 1 else 0.0
    hy = int(screen_h // 2 + pitch_offset_px + horizon_skew_px * u)
    return max(2, min(screen_h - 3, hy))


def horizon_y_at_screen_x(x, screen_w, n, screen_h, pitch_offset_px, horizon_skew_px):
    """Same horizon as the ray column under pixel x (billboards / tracers)."""
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
):
    """
    Early-FPS style: one vertical strip per ray; height ~ 1 / distance; darker when farther.
    With wall_textures: sample one texture column per strip, scaled to strip height (distance shading
    + slightly darker N/S faces). Without a loaded texture for a cell char, falls back to wall_color.
    pitch_offset_px shifts the horizon (positive = look up / recoil kick).
    horizon_skew_px adds subtle roll: left vs right columns shift vertically (strafe tilt).
    """
    n = len(ray_hits)
    if n == 0:
        hy = int(screen_h // 2 + pitch_offset_px)
        hy = max(2, min(screen_h - 3, hy))
        surface.fill(CEILING_COLOR, (0, 0, screen_w, hy))
        surface.fill(FLOOR_COLOR, (0, hy, screen_w, screen_h - hy))
        return

    proj_plane = (screen_w / 2) / math.tan(fov / 2)
    col_w = screen_w / n

    for i in range(n):
        x0 = int(i * col_w)
        x1 = int((i + 1) * col_w)
        w = max(1, x1 - x0)
        hy_i = _horizon_y_at_ray_column(i, n, screen_h, pitch_offset_px, horizon_skew_px)
        pygame.draw.rect(surface, CEILING_COLOR, (x0, 0, w, hy_i))
        pygame.draw.rect(surface, FLOOR_COLOR, (x0, hy_i, w, screen_h - hy_i))

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

        t = min(d / MAX_SHADE_DISTANCE, 1.0)
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
            color = wall_color(mx, my, side, hit_x, hit_y, tile_size, distance_shade)
            pygame.draw.rect(surface, color, (x0, top, w, line_h))

        # Vertical seam where two adjacent rays hit different wall cells or faces.
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
                pygame.draw.line(surface, OUTLINE_COLOR, (px_line, y0), (px_line, y1), OUTLINE_WIDTH)

        # Optional horizontal bands (flat-shaded walls only).
        if tex is None and WALL_BANDS > 1 and line_h > WALL_BANDS * 3:
            for b in range(1, WALL_BANDS):
                y = top + (b * line_h) // WALL_BANDS
                pygame.draw.line(
                    surface,
                    OUTLINE_COLOR,
                    (x0, y),
                    (x0 + w - 1, y),
                    OUTLINE_WIDTH,
                )


# Mouse look: hide cursor, keep pointer inside the window, start at screen center.
pygame.mouse.set_visible(False)
pygame.event.set_grab(True)
_screen_center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
pygame.mouse.set_pos(_screen_center)
pygame.mouse.get_rel()  # clear relative delta after the initial warp
VIEW_BUFFER = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

# game loop
crosshair_flash_timer = 0.0
shot_hit_x = 0.0
shot_hit_y = 0.0
shoot_cooldown_remaining = 0.0
recoil_yaw_offset = 0.0
recoil_pitch_px = 0.0
head_bob_phase = 0.0
head_bob_px = 0.0
muzzle_flash_timer = 0.0
sway_x = 0.0
sway_y = 0.0
shake_shoot_x = 0.0
shake_shoot_y = 0.0
shake_damage_x = 0.0
shake_damage_y = 0.0
strafe_tilt_px = 0.0
shot_particles = []
hit_marker_timer = 0.0
damage_flash_timer = 0.0
current_weapon_index = 0


def _reset_transient_combat_state():
    """Clear bullets / camera feedback after mid-session load (F9)."""
    global recoil_yaw_offset, recoil_pitch_px, head_bob_phase, head_bob_px
    global muzzle_flash_timer, sway_x, sway_y, shake_shoot_x, shake_shoot_y
    global shake_damage_x, shake_damage_y, strafe_tilt_px, shot_particles
    global hit_marker_timer, damage_flash_timer, crosshair_flash_timer, shoot_cooldown_remaining
    recoil_yaw_offset = 0.0
    recoil_pitch_px = 0.0
    head_bob_phase = 0.0
    head_bob_px = 0.0
    muzzle_flash_timer = 0.0
    sway_x = sway_y = 0.0
    shake_shoot_x = shake_shoot_y = 0.0
    shake_damage_x = shake_damage_y = 0.0
    strafe_tilt_px = 0.0
    shot_particles.clear()
hit_marker_timer = 0.0
damage_flash_timer = 0.0
crosshair_flash_timer = 0.0
shoot_cooldown_remaining = 0.0
day_night_time = 0.0


running = True
while running:
    level_complete = len(ENEMIES) == 0 and not game_over

    # Shooting: cleared every frame; True only when LMB is accepted (cooldown ready).
    is_shooting = False
    shoot_requested = False
    place_block_requested = False

    # Event handling: keyboard, mouse, window close, etc.
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.event.set_grab(False)
            pygame.mouse.set_visible(True)
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                pygame.event.set_grab(False)
                pygame.mouse.set_visible(True)
                running = False
            elif event.key == pygame.K_F5:
                try:
                    save_game_to_file()
                except OSError as e:
                    print("Save failed:", e)
                else:
                    print("Saved:", SAVE_FILE_PATH)
            elif event.key == pygame.K_F9:
                try:
                    with open(SAVE_FILE_PATH, "r", encoding="utf-8") as f:
                        apply_save_data(json.load(f))
                    _reset_transient_combat_state()
                except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                    print("Load failed:", e)
                else:
                    print("Loaded:", SAVE_FILE_PATH)
            elif event.key == pygame.K_r and not game_over:
                wi = current_weapon_index
                ww = WEAPONS[wi]
                if reload_timers[wi] <= 0 and weapon_ammo[wi] < ww.magazine_size:
                    reload_timers[wi] = ww.reload_time
            elif event.key == pygame.K_n and level_complete:
                spawn_next_wave()
            else:
                slot_keys = {
                    pygame.K_1: 1,
                    pygame.K_2: 2,
                    pygame.K_3: 3,
                    pygame.K_4: 4,
                    pygame.K_5: 5,
                }
                sk = slot_keys.get(event.key)
                if sk is not None:
                    for idx, w in enumerate(WEAPONS):
                        if w.slot == sk:
                            current_weapon_index = idx
                            break
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            shoot_requested = True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            place_block_requested = True

    # update
    # Seconds since last frame — scale movement so it feels the same at 30, 60, or 144 FPS.
    dt = clock.tick(60) / 1000.0
    day_night_time += dt

    for ri in range(len(WEAPONS)):
        if reload_timers[ri] > 0:
            reload_timers[ri] -= dt
            if reload_timers[ri] <= 0:
                reload_timers[ri] = 0.0
                weapon_ammo[ri] = WEAPONS[ri].magazine_size

    # Mouse look (yaw) + view sway: movement since last frame, then snap cursor to center again.
    mouse_dx, mouse_dy = pygame.mouse.get_rel()
    if not game_over:
        player_angle += mouse_dx * mouse_sensitivity
        sway_x += mouse_dx * SWAY_MOUSE_SCALE
        sway_y += mouse_dy * SWAY_MOUSE_SCALE
        sway_x = max(-SWAY_MAX_PX, min(SWAY_MAX_PX, sway_x))
        sway_y = max(-SWAY_MAX_PX, min(SWAY_MAX_PX, sway_y))
    sway_x -= sway_x * SWAY_RECOVERY * dt
    sway_y -= sway_y * SWAY_RECOVERY * dt
    pygame.mouse.set_pos(_screen_center)

    aim_x = int(_screen_center[0] + sway_x)
    aim_y = int(_screen_center[1] + sway_y)

    wpn = WEAPONS[current_weapon_index]

    # Shoot: need ammo, not reloading, and off cooldown.
    wi_fire = current_weapon_index
    if not game_over and shoot_requested:
        if (
            reload_timers[wi_fire] <= 0
            and weapon_ammo[wi_fire] > 0
            and shoot_cooldown_remaining <= 0
        ):
            is_shooting = True
            shoot_cooldown_remaining = wpn.cooldown
            weapon_ammo[wi_fire] -= 1
        shoot_requested = False
    elif shoot_requested:
        shoot_requested = False
    shoot_cooldown_remaining = max(0.0, shoot_cooldown_remaining - dt)

    # Crosshair shoot feedback: refill on click, then count down each frame.
    if is_shooting and not game_over:
        crosshair_flash_timer = CROSSHAIR_FLASH_DURATION
        muzzle_flash_timer = MUZZLE_FLASH_DURATION
        _play_sfx(SOUND_GUNSHOT)
        spawn_muzzle_particles(shot_particles, aim_x, aim_y)
        # Recoil impulse (view kicks; recovered smoothly below).
        recoil_yaw_offset += random.uniform(-wpn.recoil_yaw, wpn.recoil_yaw)
        recoil_pitch_px += random.uniform(wpn.recoil_pitch_px * 0.55, wpn.recoil_pitch_px * 1.1)
        recoil_yaw_offset = max(-0.12, min(0.12, recoil_yaw_offset))
        recoil_pitch_px = max(-90.0, min(90.0, recoil_pitch_px))
        shake_shoot_x += random.uniform(-SCREEN_SHAKE_IMPULSE_X, SCREEN_SHAKE_IMPULSE_X)
        shake_shoot_y += random.uniform(-SCREEN_SHAKE_IMPULSE_Y, SCREEN_SHAKE_IMPULSE_Y)
        spawn_player_bullet(
            player_bullets,
            player_x,
            player_y,
            player_angle + recoil_yaw_offset,
            wpn,
        )
    crosshair_flash_timer = max(0.0, crosshair_flash_timer - dt)
    muzzle_flash_timer = max(0.0, muzzle_flash_timer - dt)

    keys = pygame.key.get_pressed()
    # Facing direction (radians, standard math: CCW from +x). Forward unit vector.
    forward_x = math.cos(player_angle)
    forward_y = math.sin(player_angle)
    # Strafe right = forward rotated 90° CCW → (-sin, cos); same length, perpendicular.
    strafe_x = -math.sin(player_angle)
    strafe_y = math.cos(player_angle)

    is_moving = False
    if not game_over:
        hp_before = player_health
        move_x = 0.0
        move_y = 0.0
        if keys[pygame.K_w]:
            move_x += forward_x
            move_y += forward_y
        if keys[pygame.K_s]:
            move_x -= forward_x
            move_y -= forward_y
        if keys[pygame.K_d]:
            move_x += strafe_x
            move_y += strafe_y
        if keys[pygame.K_a]:
            move_x -= strafe_x
            move_y -= strafe_y

        # Same speed in all directions; diagonals don't move faster than cardinals.
        length = math.hypot(move_x, move_y)
        is_moving = length > 0
        shift_held = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        can_sprint = (
            shift_held
            and is_moving
            and stamina > STAMINA_MIN_TO_SPRINT
        )
        sprint_speed = PLAYER_SPEED_WALK * PLAYER_SPRINT_MULTIPLIER
        target_speed = sprint_speed if can_sprint else PLAYER_SPEED_WALK
        move_speed_smoothed += (target_speed - move_speed_smoothed) * min(
            1.0, MOVE_SPEED_SMOOTH_RATE * dt
        )
        if length > 0:
            move_x = (move_x / length) * move_speed_smoothed * dt
            move_y = (move_y / length) * move_speed_smoothed * dt
            player_x += move_x
            player_y += move_y

        if can_sprint:
            stamina -= STAMINA_DRAIN_PER_SEC * dt
        else:
            stamina += STAMINA_REGEN_PER_SEC * dt
        stamina = max(0.0, min(STAMINA_MAX, stamina))

        update_enemies(ENEMIES, player_x, player_y, dt, TILE_SIZE)
        n_enemy_hits = update_player_bullets(player_bullets, dt, TILE_SIZE, ENEMIES)
        if n_enemy_hits > 0:
            hit_marker_timer = HIT_MARKER_DURATION
        player_health -= update_enemy_shooting(ENEMIES, player_x, player_y, dt, TILE_SIZE)

        # Contact damage: each enemy within range drains HP over time.
        for e in ENEMIES:
            d = math.hypot(e[0] - player_x, e[1] - player_y)
            if d < ENEMY_CONTACT_RANGE:
                player_health -= ENEMY_CONTACT_DPS * dt
        player_health = max(0.0, player_health)
        if player_health < hp_before - 1e-9:
            delta_hp = hp_before - player_health
            damage_flash_timer = min(
                DAMAGE_FLASH_CAP,
                damage_flash_timer + DAMAGE_FLASH_BASE + DAMAGE_FLASH_PER_HP * delta_hp,
            )
            dmg_shake_scale = min(
                DAMAGE_SHAKE_HP_SCALE_CAP,
                1.0 + delta_hp * DAMAGE_SHAKE_HP_SCALE,
            )
            shake_damage_x += (
                random.uniform(-DAMAGE_SHAKE_IMPULSE_X, DAMAGE_SHAKE_IMPULSE_X) * dmg_shake_scale
            )
            shake_damage_y += (
                random.uniform(-DAMAGE_SHAKE_IMPULSE_Y, DAMAGE_SHAKE_IMPULSE_Y) * dmg_shake_scale
            )
        if player_health <= 0 and not game_over:
            game_over = True
            print("GAME OVER")

    else:
        move_speed_smoothed += (PLAYER_SPEED_WALK - move_speed_smoothed) * min(
            1.0, MOVE_SPEED_SMOOTH_RATE * dt
        )

    hit_marker_timer = max(0.0, hit_marker_timer - dt)
    damage_flash_timer = max(0.0, damage_flash_timer - dt * 2.4)

    # Head bob: sine vertical offset while moving; frequency tied to current move speed; smooth stop.
    if not game_over and is_moving:
        head_bob_phase += (
            2 * math.pi * HEAD_BOB_FREQ_HZ * (move_speed_smoothed / HEAD_BOB_REF_SPEED) * dt
        )
    bob_target = (
        math.sin(head_bob_phase) * HEAD_BOB_AMPLITUDE_PX if (not game_over and is_moving) else 0.0
    )
    head_bob_px += (bob_target - head_bob_px) * min(1.0, HEAD_BOB_SMOOTH * dt)

    # Strafe tilt: eased toward ±max while holding A/D alone; releases smoothly when stopped.
    strafe_tilt_target = 0.0
    if not game_over:
        if keys[pygame.K_d] and not keys[pygame.K_a]:
            strafe_tilt_target = STRAFE_TILT_MAX_PX
        elif keys[pygame.K_a] and not keys[pygame.K_d]:
            strafe_tilt_target = -STRAFE_TILT_MAX_PX
    strafe_tilt_px += (strafe_tilt_target - strafe_tilt_px) * min(1.0, STRAFE_TILT_SMOOTH * dt)

    # Recoil / shake: smooth exponential decay toward 0 (frame-rate friendly).
    recoil_yaw_offset -= recoil_yaw_offset * RECOIL_RECOVERY * dt
    recoil_pitch_px -= recoil_pitch_px * RECOIL_RECOVERY * dt
    shake_shoot_x -= shake_shoot_x * SCREEN_SHAKE_DECAY * dt
    shake_shoot_y -= shake_shoot_y * SCREEN_SHAKE_DECAY * dt
    shake_damage_x -= shake_damage_x * DAMAGE_SHAKE_DECAY * dt
    shake_damage_y -= shake_damage_y * DAMAGE_SHAKE_DECAY * dt

    update_shot_particles(shot_particles, dt)

    update_chunk_streaming(player_x, player_y, TILE_SIZE)
    view_yaw = player_angle + recoil_yaw_offset
    view_pitch_px = recoil_pitch_px + head_bob_px

    if not game_over and place_block_requested and inventory_blocks > 0:
        try_place_wall_block(
            player_x, player_y, view_yaw, TILE_SIZE, ENEMIES, PLACE_BLOCK_MAX_DIST
        )

    # Raycasting: wall hit per column (distance + grid cell + face + world hit point).
    ray_hits = compute_ray_hits(player_x, player_y, view_yaw, TILE_SIZE, FOV, NUM_RAYS)

    # render (world + HUD into buffer, then whole frame shifts for screen shake)
    draw_raycast_view(
        VIEW_BUFFER,
        ray_hits,
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
        TILE_SIZE,
        FOV,
        view_pitch_px,
        WALL_TEXTURES,
        horizon_skew_px=strafe_tilt_px,
    )
    draw_enemies(
        VIEW_BUFFER,
        ENEMIES,
        player_x,
        player_y,
        view_yaw,
        ray_hits,
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
        FOV,
        view_pitch_px,
        horizon_skew_px=strafe_tilt_px,
    )
    draw_player_bullets(
        VIEW_BUFFER,
        player_bullets,
        player_x,
        player_y,
        view_yaw,
        ray_hits,
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
        FOV,
        view_pitch_px,
        horizon_skew_px=strafe_tilt_px,
    )
    draw_muzzle_flash(VIEW_BUFFER, aim_x, aim_y, muzzle_flash_timer, MUZZLE_FLASH_DURATION)
    draw_shot_particles(VIEW_BUFFER, shot_particles)
    draw_crosshair(VIEW_BUFFER, aim_x, aim_y, crosshair_flash_timer)
    draw_hit_marker(
        VIEW_BUFFER,
        SCREEN_WIDTH // 2,
        SCREEN_HEIGHT // 2,
        hit_marker_timer,
        HIT_MARKER_DURATION,
    )
    draw_minimap(VIEW_BUFFER, player_x, player_y, player_angle, TILE_SIZE, SCREEN_WIDTH, ENEMIES)
    draw_damage_flash(VIEW_BUFFER, damage_flash_timer, SCREEN_WIDTH, SCREEN_HEIGHT)
    draw_hud(
        VIEW_BUFFER,
        player_health,
        PLAYER_HP_MAX,
        wpn,
        len(ENEMIES),
        weapon_ammo[current_weapon_index],
        wpn.magazine_size,
        reload_timers[current_weapon_index] > 0,
        inventory_blocks,
        stamina,
        STAMINA_MAX,
        enemies_defeated,
        wave_number,
    )
    if level_complete:
        draw_level_complete_overlay(VIEW_BUFFER, SCREEN_WIDTH, SCREEN_HEIGHT)
    if game_over:
        draw_game_over_overlay(VIEW_BUFFER, SCREEN_WIDTH, SCREEN_HEIGHT)
    # Smooth day ↔ night: full-frame multiply (whole view dims together).
    phase = 2 * math.pi * ((day_night_time % DAY_NIGHT_PERIOD_SEC) / DAY_NIGHT_PERIOD_SEC)
    t = 0.5 + 0.5 * math.sin(phase)
    mr, mg, mb = DAY_NIGHT_MULT_MIN
    xr, xg, xb = DAY_NIGHT_MULT_MAX
    r_mul = int(255 * (mr + (xr - mr) * t))
    g_mul = int(255 * (mg + (xg - mg) * t))
    b_mul = int(255 * (mb + (xb - mb) * t))
    VIEW_BUFFER.fill((r_mul, g_mul, b_mul), special_flags=pygame.BLEND_RGBA_MULT)

    screen.fill((0, 0, 0))
    shake_x = shake_shoot_x + shake_damage_x
    shake_y = shake_shoot_y + shake_damage_y
    screen.blit(VIEW_BUFFER, (int(shake_x), int(shake_y)))
    pygame.display.flip()

pygame.quit()
