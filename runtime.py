"""
Mutable session state: position, health, world data, and mode flags.
The game loop and systems read/write these module-level variables (simple for beginners).
"""

import settings as cfg

# --- Player ---
player_x = 0.0
player_y = 0.0
player_angle = 0.0
move_speed_smoothed = cfg.PLAYER_SPEED_WALK
stamina = float(cfg.STAMINA_MAX)
mouse_sensitivity = 0.0025
player_health = float(cfg.PLAYER_HP_MAX)
inventory_blocks = cfg.INVENTORY_BLOCKS_START

# --- Enemies (list of rows: x, y, wander, hp, shoot_cd, ai_state, …) ---
enemies = []
enemies_defeated = 0
kills_this_wave = 0
wave_number = 1
# True after a wave spawns with at least one enemy; False after WAVE_COMPLETE or menu.
wave_in_progress = False
# Short-lived world-space bursts when an enemy dies (rendered in enemy.draw_death_effects).
death_effects = []
# Counts down after the player takes damage; blocks further damage (see settings.PLAYER_INVULN_DURATION).
player_invuln_timer = 0.0

# --- High-level game flow (see game_flow.py) ---
STATE_START_MENU = "START_MENU"
STATE_PLAYING = "PLAYING"
STATE_WAVE_COMPLETE = "WAVE_COMPLETE"
STATE_GAME_OVER = "GAME_OVER"
STATE_PAUSED = "PAUSED"

game_state = STATE_START_MENU

# --- Procedural world ---
world_gen_seed = 7
world_cell_edits = {}
_chunk_player_cx = 0
_chunk_player_cy = 0
chunk_cache = {}
_active_chunk_keys = set()

_perlin_perm = None
_terrain_off_x = 0.0
_terrain_off_y = 0.0
