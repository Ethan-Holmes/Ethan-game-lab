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
mouse_sensitivity = cfg.MOUSE_SENSITIVITY
player_health = float(cfg.PLAYER_HP_MAX)
inventory_blocks = cfg.INVENTORY_BLOCKS_START

# --- Enemies (list of rows: x, y, wander, hp, shoot_cd, ai_state, …) ---
enemies = []
enemies_defeated = 0
kills_this_wave = 0
wave_number = 1
# True after a wave spawns with at least one enemy; False after WAVE_COMPLETE or menu.
wave_in_progress = False
# Per-wave mission (see objectives.py); reset when a new wave spawns.
objective_kind = "clear_hostiles"
objective_wave = 1
objective_title = "Clear hostiles"
objective_detail = ""
objective_intro_until_monotonic = 0.0
obj_anchor_x = 0.0
obj_anchor_y = 0.0
obj_target_x = 0.0
obj_target_y = 0.0
obj_zone_radius = 0.0
obj_hold_required = 0.0
obj_hold_progress = 0.0
# Set by ambient.tick — district display name near player (HUD / minimap).
ambient_zone_label = ""
# Short-lived world-space bursts when an enemy dies (rendered in enemy.draw_death_effects).
death_effects = []
# Counts down after the player takes damage; blocks further damage (see settings.PLAYER_INVULN_DURATION).
player_invuln_timer = 0.0

# First-session construction hint (see game_flow.begin_playing_from_menu).
construction_hint_until_monotonic = 0.0
construction_hint_dismissed = False

# Meta progression (see progression.py): queued lines shown on wave-clear card.
pending_progression_hints = []
pending_reward_lines = []
# Map char for player-placed walls ("1" stone, "2" brick, "3" concrete) — from career unlocks.
player_placed_wall_char = "1"

# Health / stamina field pickups (see pickups.py)
field_pickups = []

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
