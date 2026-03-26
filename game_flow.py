"""
Save/load, new game, wave advance, and the high-level game-state machine.
"""

import json
import os
import random
import time

import pygame

import enemy
import objectives
import pickups
import player
import progression
import runtime as R
import settings as cfg
import waves
import world


def resolve_state_after_load():
    """Derive R.game_state from health + enemy list after JSON load."""
    if R.player_health <= 0:
        R.game_state = R.STATE_GAME_OVER
    elif len(R.enemies) == 0:
        R.game_state = R.STATE_WAVE_COMPLETE
        R.wave_in_progress = False
    else:
        R.game_state = R.STATE_PLAYING
        R.wave_in_progress = True


def begin_playing_from_menu():
    """START_MENU → PLAYING: spawn wave 1 if the enemy list is still empty."""
    if len(R.enemies) > 0:
        R.game_state = R.STATE_PLAYING
        R.wave_in_progress = True
        return
    rng = random.Random()
    kind = objectives.pick_kind_for_wave(R.wave_number, rng)
    style = objectives.spawn_style_for_kind(kind)
    spawned = waves.spawn_wave_enemies(
        R.player_x, R.player_y, cfg.TILE_SIZE, R.wave_number, rng=rng, spawn_style=style
    )
    R.enemies.clear()
    R.enemies.extend(spawned)
    R.wave_number = 1
    R.kills_this_wave = 0
    pickups.clear()
    pickups.spawn_wave_pickups(R.player_x, R.player_y, cfg.TILE_SIZE, R.wave_number, rng)
    R.wave_in_progress = len(spawned) > 0
    R.death_effects.clear()
    R.player_invuln_timer = 0.0
    R.game_state = R.STATE_PLAYING
    objectives.apply_start(kind, R.wave_number, R.player_x, R.player_y, rng)
    R.inventory_blocks = min(
        cfg.INVENTORY_BLOCKS_START + progression.bonus_start_blocks(),
        cfg.INVENTORY_BLOCKS_MAX,
    )
    player.sync_weapon_ammo_for_unlocks()
    progression.refresh_runtime_wall_char()
    if not R.construction_hint_dismissed and R.wave_number == 1:
        R.construction_hint_until_monotonic = time.monotonic() + cfg.CONSTRUCTION_HINT_SECONDS


def sync_mouse_grab_for_state():
    # Paused: free cursor so ESC pause feels like a real menu break.
    if R.game_state == R.STATE_PAUSED:
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(True)
    elif R.game_state in (R.STATE_PLAYING, R.STATE_WAVE_COMPLETE):
        pygame.event.set_grab(True)
        pygame.mouse.set_visible(False)
    else:
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(True)


def spawn_next_wave():
    """WAVE_COMPLETE → PLAYING: spawn the next wave (higher index + scaling)."""
    R.pending_reward_lines.clear()
    rng = random.Random()
    next_w = R.wave_number + 1
    kind = objectives.pick_kind_for_wave(next_w, rng)
    style = objectives.spawn_style_for_kind(kind)
    spawned = waves.spawn_wave_enemies(
        R.player_x, R.player_y, cfg.TILE_SIZE, next_w, rng=rng, spawn_style=style
    )
    R.enemies.clear()
    R.enemies.extend(spawned)
    R.wave_number = next_w
    R.kills_this_wave = 0
    R.wave_in_progress = len(spawned) > 0
    R.death_effects.clear()
    R.player_invuln_timer = 0.0
    pickups.clear()
    pickups.spawn_wave_pickups(R.player_x, R.player_y, cfg.TILE_SIZE, R.wave_number, rng)
    R.game_state = R.STATE_PLAYING
    objectives.apply_start(kind, next_w, R.player_x, R.player_y, rng)


def regenerate_world_map(seed=None):
    rng = random.Random(seed) if seed is not None else random
    R.world_gen_seed = rng.randint(1, 2**30)
    world.init_perlin_noise(R.world_gen_seed)
    R.world_cell_edits.clear()
    R.chunk_cache.clear()
    kind = objectives.pick_kind_for_wave(1, rng)
    style = objectives.spawn_style_for_kind(kind)
    R.player_x, R.player_y, spawned = waves.find_spawn_and_enemies(
        cfg.TILE_SIZE, wave_number=1, rng=rng, spawn_style=style
    )
    R.enemies.clear()
    R.enemies.extend(spawned)
    world.update_chunk_streaming(R.player_x, R.player_y, cfg.TILE_SIZE)
    R.player_angle = 0.0
    R.player_health = float(cfg.PLAYER_HP_MAX)
    player.player_bullets.clear()
    R.inventory_blocks = min(
        cfg.INVENTORY_BLOCKS_START + progression.bonus_start_blocks(),
        cfg.INVENTORY_BLOCKS_MAX,
    )
    R.construction_hint_dismissed = False
    R.construction_hint_until_monotonic = 0.0
    R.stamina = float(cfg.STAMINA_MAX)
    R.move_speed_smoothed = cfg.PLAYER_SPEED_WALK
    R.enemies_defeated = 0
    R.kills_this_wave = 0
    R.wave_number = 1
    R.wave_in_progress = len(spawned) > 0
    R.death_effects.clear()
    R.player_invuln_timer = 0.0
    R.game_state = R.STATE_PLAYING
    objectives.apply_start(kind, 1, R.player_x, R.player_y, rng)
    pickups.clear()
    pickups.spawn_wave_pickups(R.player_x, R.player_y, cfg.TILE_SIZE, R.wave_number, rng)
    player.sync_weapon_ammo_for_unlocks()
    progression.refresh_runtime_wall_char()
    if not R.construction_hint_dismissed and R.wave_number == 1:
        R.construction_hint_until_monotonic = time.monotonic() + cfg.CONSTRUCTION_HINT_SECONDS


def apply_save_data(data):
    R.world_gen_seed = int(data["world_gen_seed"])
    world.init_perlin_noise(R.world_gen_seed)
    R.chunk_cache.clear()
    for key, grid in data["chunk_cache"].items():
        cx, cy = key.split(",")
        R.chunk_cache[(int(cx), int(cy))] = [list(row) for row in grid]
    R.world_cell_edits.clear()
    for key, ch in data["world_cell_edits"].items():
        mx, my = key.split(",")
        R.world_cell_edits[(int(mx), int(my))] = str(ch)
    R.player_x = float(data["player_x"])
    R.player_y = float(data["player_y"])
    R.player_angle = float(data["player_angle"])
    R.player_health = float(data.get("player_health", cfg.PLAYER_HP_MAX))
    R.inventory_blocks = min(
        int(data.get("inventory_blocks", cfg.INVENTORY_BLOCKS_START)),
        cfg.INVENTORY_BLOCKS_MAX,
    )
    R.stamina = float(data.get("stamina", cfg.STAMINA_MAX))
    R.move_speed_smoothed = float(data.get("move_speed_smoothed", cfg.PLAYER_SPEED_WALK))
    R.enemies_defeated = int(data.get("enemies_defeated", 0))
    R.wave_number = int(data.get("wave_number", 1))
    R.kills_this_wave = int(data.get("kills_this_wave", 0))
    R.construction_hint_dismissed = bool(data.get("construction_hint_dismissed", True))
    R.construction_hint_until_monotonic = 0.0
    R.death_effects.clear()
    R.player_invuln_timer = 0.0
    R.enemies.clear()
    for raw in data.get("enemies", []):
        R.enemies.append(enemy.from_save_obj(raw))
    player.player_bullets.clear()
    world.update_chunk_streaming(R.player_x, R.player_y, cfg.TILE_SIZE)
    objectives.load_from_save_dict(data.get("objective"))
    resolve_state_after_load()
    pickups.load_from_save(data.get("pickups"))
    player.sync_weapon_ammo_for_unlocks()
    progression.refresh_runtime_wall_char()
    R.pending_reward_lines.clear()


def save_game_to_file():
    chunks = {f"{cx},{cy}": grid for (cx, cy), grid in R.chunk_cache.items()}
    edits = {f"{mx},{my}": ch for (mx, my), ch in R.world_cell_edits.items()}
    payload = {
        "version": 5,
        "world_gen_seed": R.world_gen_seed,
        "chunk_cache": chunks,
        "world_cell_edits": edits,
        "player_x": R.player_x,
        "player_y": R.player_y,
        "player_angle": R.player_angle,
        "player_health": R.player_health,
        "inventory_blocks": R.inventory_blocks,
        "stamina": R.stamina,
        "move_speed_smoothed": R.move_speed_smoothed,
        "enemies_defeated": R.enemies_defeated,
        "kills_this_wave": R.kills_this_wave,
        "wave_number": R.wave_number,
        "enemies": [enemy.to_save_dict(e) for e in R.enemies],
        "construction_hint_dismissed": R.construction_hint_dismissed,
        "objective": objectives.to_save_dict(),
        "pickups": pickups.to_save_list(),
    }
    with open(cfg.SAVE_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def bootstrap_session():
    """Set starting player position / state before the main loop (new game or load)."""
    progression.load()
    if os.path.isfile(cfg.SAVE_FILE_PATH):
        try:
            with open(cfg.SAVE_FILE_PATH, "r", encoding="utf-8") as f:
                apply_save_data(json.load(f))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            print("Save load failed, starting fresh:", e)
            _bootstrap_fresh_start_menu()
    else:
        _bootstrap_fresh_start_menu()


def _bootstrap_fresh_start_menu():
    R.player_x, R.player_y, _ = waves.find_spawn_and_enemies(
        cfg.TILE_SIZE, wave_number=1, skip_enemies=True
    )
    R.enemies.clear()
    world.update_chunk_streaming(R.player_x, R.player_y, cfg.TILE_SIZE)
    R.wave_number = 1
    R.enemies_defeated = 0
    R.kills_this_wave = 0
    R.wave_in_progress = False
    R.game_state = R.STATE_START_MENU
    R.field_pickups.clear()
    objectives.migrate_legacy_no_save()
