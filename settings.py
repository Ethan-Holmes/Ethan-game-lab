"""
Tunable constants for the FPS prototype (no pygame Surfaces here — safe to import anywhere).
Screen width/height and ray count are set from main.py after the display is created.
"""

import math
import os

# Paths (same folder as this package / repo root for savegame).
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, "assets")
SAVE_FILE_PATH = os.path.join(SCRIPT_DIR, "savegame.json")

# --- Wall textures (map char → filename in assets/) ---
# "1"/"2" building faces, "3" concrete cover — missing files use placeholder colors in world.py.
WALL_TEXTURE_FILES = {
    "1": "stone.png",
    "2": "urban_brick.png",
    "3": "concrete.png",
}

# --- Character sprites (under assets/player/, assets/enemies/; see assets.load_all) ---
# All character art is scaled to this pixel size first (consistent “gameplay” resolution).
CHARACTER_SPRITE_BASE_SIZE = (80, 112)
ENEMY_BILLBOARD_TEX_SIZE = CHARACTER_SPRITE_BASE_SIZE

PLAYER_SPRITE_DIR = "player"
PLAYER_SPRITE_FILENAMES = ("player.png", "sprite.png", "character.png")
# Fallback if nothing exists under player/
PLAYER_SPRITE_FILENAME = "player.png"

ENEMY_SPRITE_DIR = "enemies"
ENEMY_SPRITE_FILENAME = "enemy.png"

MINIMAP_PLAYER_ICON_SIZE = (12, 12)
MINIMAP_ENEMY_ICON_SIZE = (8, 8)

# --- Audio ---
SFX_VOLUME = 0.75

# --- Day / night post-process ---
DAY_NIGHT_PERIOD_SEC = 200.0
DAY_NIGHT_MULT_MIN = (0.76, 0.80, 0.92)
DAY_NIGHT_MULT_MAX = (1.0, 1.0, 1.0)

# --- Raycast view ---
CEILING_COLOR = (34, 38, 52)
# Walkable terrain tints (roads / lots / sidewalks) — sampled per ray for readability.
FLOOR_COLOR_ROAD = (36, 34, 38)
FLOOR_COLOR_SIDEWALK = (44, 46, 52)
FLOOR_COLOR_LOT = (46, 52, 44)
FLOOR_COLOR = FLOOR_COLOR_ROAD
WALL_COLOR_BASE = (175, 155, 130)
MAX_SHADE_DISTANCE = 720.0
OUTLINE_COLOR = (22, 20, 18)
OUTLINE_WIDTH = 1
WALL_BANDS = 4
RAYCAST_MAX_STEPS = 512
FOV = math.pi / 3

# --- Minimap ---
MINIMAP_CELL_PX = 5
MINIMAP_MARGIN = 14
MINIMAP_PAD = 2
MINIMAP_BG = (14, 14, 22)
MINIMAP_BORDER = (70, 75, 90)
MINIMAP_WALL = (48, 50, 58)
MINIMAP_FLOOR = FLOOR_COLOR_ROAD
MINIMAP_ROAD = (38, 40, 48)
MINIMAP_SIDEWALK = (58, 62, 70)
MINIMAP_LOT = (48, 58, 52)
MINIMAP_COVER = (88, 82, 68)
MINIMAP_BUILDING_B = (42, 44, 52)
# Environmental props (solid cells; raycast + minimap)
MINIMAP_PROP_CAR = (72, 92, 118)
MINIMAP_PROP_CRATE = (110, 78, 52)
MINIMAP_PROP_BARRIER = (210, 175, 55)
MINIMAP_PROP_LAMP = (190, 198, 215)
MINIMAP_PROP_DUMPSTER = (58, 92, 62)
MINIMAP_PROP_PARAPET = (96, 100, 108)
MINIMAP_PLAYER = (130, 255, 150)
MINIMAP_DIR_LEN = 10
MINIMAP_HALF_EXTENT = 12

# --- Game branding (window title + menus) ---
GAME_TITLE = "Combat Zone"
GAME_SUBTITLE = "Urban operations"

# --- HUD & UI theme ---
HUD_MARGIN_X = 20
HUD_MARGIN_Y = 16
HUD_PANEL_WIDTH = 368
HUD_PANEL_PAD = 14
HUD_CORNER_RADIUS = 4
HUD_FONT_TITLE = 22
HUD_FONT_BODY = 26
HUD_FONT_SMALL = 20
HUD_LINE_SKIP = 4
HUD_TEXT = (235, 237, 245)
HUD_TEXT_MUTED = (148, 154, 168)
HUD_TEXT_DIM = (110, 116, 130)
HUD_SHADOW = (8, 9, 14)
HUD_PANEL_BG = (16, 18, 26)
HUD_PANEL_BG_ALPHA = 220
HUD_PANEL_BORDER = (52, 58, 74)
HUD_PANEL_INNER_HIGHLIGHT = (68, 76, 94)
HUD_ACCENT = (120, 205, 255)
HUD_ACCENT_WARN = (255, 190, 100)
HUD_HP_HIGH = (96, 220, 150)
HUD_HP_MID = (255, 200, 90)
HUD_HP_LOW = (255, 95, 105)
OBJECTIVE_ELIMINATE = "Eliminate all hostiles"

# Minimap chrome
MINIMAP_FRAME_OUTER = (24, 26, 34)
MINIMAP_FRAME_INNER = (78, 86, 108)
MINIMAP_LABEL = (160, 168, 188)
MINIMAP_SHADOW_OFFSET = 4

# Full-screen overlays (game over, wave clear, title)
UI_OVERLAY_DIM = (6, 8, 14)
UI_OVERLAY_ALPHA = 165
UI_CARD_BG = (22, 24, 34)
UI_CARD_BG_ALPHA = 245
UI_CARD_BORDER = (90, 98, 120)
UI_CARD_ACCENT_LINE = (120, 205, 255)
UI_TITLE_LARGE = 78
UI_TITLE_MEDIUM = 52
UI_BODY = 26
UI_HINT = 24

# --- Player movement / stamina ---
PLAYER_SPEED_WALK = 300.0
PLAYER_SPRINT_MULTIPLIER = 1.52
MOVE_SPEED_SMOOTH_RATE = 14.0
STAMINA_MAX = 100.0
STAMINA_DRAIN_PER_SEC = 44.0
STAMINA_REGEN_PER_SEC = 24.0
STAMINA_MIN_TO_SPRINT = 1.5
STAMINA_BAR_W = 220
STAMINA_BAR_H = 10

INVENTORY_BLOCKS_START = 50
PLAYER_HP_MAX = 100

# --- World grid ---
TILE_SIZE = 64
PLACE_BLOCK_MAX_DIST = 3.0 * TILE_SIZE
CHUNK_SIZE = 10
CHUNK_LOAD_RADIUS = 3
# Urban grid: main roads every N cells; blocks contain sidewalks, buildings, alleys, cover.
URBAN_ROAD_SPACING = 6

# --- Enemies ---
ENEMY_SPEED = 85.0
ENEMY_HIT_RADIUS = 28.0
ENEMY_HP_MAX = 100.0
# AI states (rule-based; see enemy_ai.py)
ENEMY_ST_IDLE = 0  # hold position (no wander)
ENEMY_ST_PATROL = 1  # wander near spawn anchor
ENEMY_ST_CHASE = 2  # move toward player (player inside detection)
ENEMY_ST_ATTACK = 3  # shoot + reposition at standoff
ENEMY_DETECT_RANGE = 480.0
ENEMY_LOST_RANGE = 620.0
ENEMY_ATTACK_RANGE = 400.0
ENEMY_ATTACK_LEAVE_RANGE = 468.0
# How far apart enemies try to stay (world units; weighted per type).
ENEMY_SEPARATION_RADIUS = 92.0
ENEMY_SEPARATION_BLEND = 0.55
ENEMY_AGRO_RANGE = ENEMY_DETECT_RANGE
ENEMY_MIN_MOVE_DIST = 16.0
ENEMY_WANDER_TURN_MAX = 1.35
ENEMY_SPRITE_WIDTH = 40.0
ENEMY_SPRITE_HEIGHT = 56.0
ENEMY_COLOR = (230, 70, 70)
ENEMY_EDGE_COLOR = (40, 20, 20)
ENEMY_SHOOT_RANGE = 540.0
ENEMY_SHOOT_COOLDOWN = 1.2
ENEMY_SHOOT_DAMAGE = 10.0
ENEMY_SHOOT_LOS_EPS = 16.0

# Contact damage (stacking per nearby enemy)
ENEMY_CONTACT_RANGE = 52.0
ENEMY_CONTACT_DPS = 22.0

# --- Waves (tune difficulty curve here) ---
# Enemy count = base + (wave - 1) * step, clamped to max.
WAVE_BASE_ENEMY_COUNT = 3
WAVE_ENEMIES_PER_WAVE = 1
WAVE_MAX_ENEMIES = 26
# Per-wave scaling applied to spawned enemies (wave 1 = no bonus).
WAVE_HP_SCALE_PER_WAVE = 0.08
WAVE_DAMAGE_SCALE_PER_WAVE = 0.055
# Spawns only on tiles at least this far from the player (world units).
WAVE_SPAWN_MIN_DIST = 3.75 * TILE_SIZE


def wave_enemy_count(wave_n: int) -> int:
    """How many enemies spawn for this wave index (1-based)."""
    w = max(1, wave_n)
    n = WAVE_BASE_ENEMY_COUNT + (w - 1) * WAVE_ENEMIES_PER_WAVE
    return max(1, min(WAVE_MAX_ENEMIES, n))


def wave_hp_multiplier(wave_n: int) -> float:
    w = max(1, wave_n)
    return max(0.55, 1.0 + (w - 1) * WAVE_HP_SCALE_PER_WAVE)


def wave_damage_multiplier(wave_n: int) -> float:
    w = max(1, wave_n)
    return max(0.65, 1.0 + (w - 1) * WAVE_DAMAGE_SCALE_PER_WAVE)

# --- Crosshair / view kick ---
CROSSHAIR_COLOR = (255, 255, 255)
CROSSHAIR_FLASH_COLOR = (255, 64, 72)
CROSSHAIR_FLASH_DURATION = 0.1
RECOIL_RECOVERY = 7.0

# --- Weapons / bullets (Weapon dataclass lives in player.py) ---
BULLET_MAX_RANGE = 2600.0
BULLET_MAX_ALIVE = 96
BULLET_SPAWN_OFFSET = 22.0
BULLET_ENEMY_HIT_RADIUS = 30.0

HEAD_BOB_AMPLITUDE_PX = 3.2
HEAD_BOB_FREQ_HZ = 1.75
HEAD_BOB_REF_SPEED = 300.0
HEAD_BOB_SMOOTH = 14.0
CROSSHAIR_HALF_LEN = 10
CROSSHAIR_THICKNESS = 2

HIT_MARKER_DURATION = 0.14
KILL_MARKER_DURATION = 0.38
HIT_MARKER_HALF_EXTENT = 11
HIT_MARKER_THICKNESS = 3
# Brief invulnerability after taking damage (stops burst / contact chain deaths).
PLAYER_INVULN_DURATION = 0.48
# Extra screen flash when damaged by enemy gunfire (on top of base damage flash).
ENEMY_SHOT_FEEDBACK_EXTRA = 0.06
DAMAGE_FLASH_CAP = 0.42
DAMAGE_FLASH_BASE = 0.055
DAMAGE_FLASH_PER_HP = 0.026
DAMAGE_FLASH_ALPHA_MAX = 118

SWAY_MOUSE_SCALE = 0.055
SWAY_RECOVERY = 11.0
SWAY_MAX_PX = 12.0

SCREEN_SHAKE_DECAY = 14.0
SCREEN_SHAKE_IMPULSE_X = 3.0
SCREEN_SHAKE_IMPULSE_Y = 2.6
DAMAGE_SHAKE_IMPULSE_X = 9.5
DAMAGE_SHAKE_IMPULSE_Y = 8.0
DAMAGE_SHAKE_HP_SCALE = 0.34
DAMAGE_SHAKE_HP_SCALE_CAP = 2.15
DAMAGE_SHAKE_DECAY = 10.5

STRAFE_TILT_MAX_PX = 2.6
STRAFE_TILT_SMOOTH = 11.0

MUZZLE_FLASH_DURATION = 0.09
MUZZLE_FLASH_RADIUS = 38
# Queues a shot for a few frames if you click slightly early (snappier feel).
SHOOT_INPUT_BUFFER_SEC = 0.1
ENEMY_HIT_FLASH_DURATION = 0.14
DEATH_BURST_DURATION = 0.45
PARTICLE_BURST_COUNT = 14
PARTICLE_LIFETIME = 0.38
PARTICLE_SPEED_MIN = 130.0
PARTICLE_SPEED_MAX = 300.0
PARTICLE_MAX_ALIVE = 256
