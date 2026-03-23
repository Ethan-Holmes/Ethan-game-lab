"""
Save/load, new game, wave advance, and the high-level game-state machine.
"""

import json
import os
import random

import pygame

import enemy
import player
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
    spawned = waves.spawn_wave_enemies(R.player_x, R.player_y, cfg.TILE_SIZE, R.wave_number, rng=rng)
    R.enemies.clear()
    R.enemies.extend(spawned)
    R.wave_number = 1
    R.kills_this_wave = 0
    R.wave_in_progress = len(spawned) > 0
    R.death_effects.clear()
    R.player_invuln_timer = 0.0
    R.game_state = R.STATE_PLAYING


def sync_mouse_grab_for_state():
    if R.game_state in (R.STATE_PLAYING, R.STATE_PAUSED, R.STATE_WAVE_COMPLETE):
        pygame.event.set_grab(True)
        pygame.mouse.set_visible(False)
    else:
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(True)


def spawn_next_wave():
    """WAVE_COMPLETE → PLAYING: spawn the next wave (higher index + scaling)."""
    rng = random.Random()
    next_w = R.wave_number + 1
    spawned = waves.spawn_wave_enemies(R.player_x, R.player_y, cfg.TILE_SIZE, next_w, rng=rng)
    R.enemies.clear()
    R.enemies.extend(spawned)
    R.wave_number = next_w
    R.kills_this_wave = 0
    R.wave_in_progress = len(spawned) > 0
    R.death_effects.clear()
    R.player_invuln_timer = 0.0
    R.game_state = R.STATE_PLAYING


def regenerate_world_map(seed=None):
    rng = random.Random(seed) if seed is not None else random
    R.world_gen_seed = rng.randint(1, 2**30)
    world.init_perlin_noise(R.world_gen_seed)
    R.world_cell_edits.clear()
    R.chunk_cache.clear()
    R.player_x, R.player_y, spawned = waves.find_spawn_and_enemies(cfg.TILE_SIZE, wave_number=1, rng=rng)
    R.enemies.clear()
    R.enemies.extend(spawned)
    world.update_chunk_streaming(R.player_x, R.player_y, cfg.TILE_SIZE)
    R.player_angle = 0.0
    R.player_health = float(cfg.PLAYER_HP_MAX)
    player.player_bullets.clear()
    player.weapon_ammo[:] = [w.magazine_size for w in player.WEAPONS]
    player.reload_timers[:] = [0.0] * len(player.WEAPONS)
    R.inventory_blocks = cfg.INVENTORY_BLOCKS_START
    R.stamina = float(cfg.STAMINA_MAX)
    R.move_speed_smoothed = cfg.PLAYER_SPEED_WALK
    R.enemies_defeated = 0
    R.kills_this_wave = 0
    R.wave_number = 1
    R.wave_in_progress = len(spawned) > 0
    R.death_effects.clear()
    R.player_invuln_timer = 0.0
    R.game_state = R.STATE_PLAYING


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
    R.inventory_blocks = int(data.get("inventory_blocks", cfg.INVENTORY_BLOCKS_START))
    R.stamina = float(data.get("stamina", cfg.STAMINA_MAX))
    R.move_speed_smoothed = float(data.get("move_speed_smoothed", cfg.PLAYER_SPEED_WALK))
    R.enemies_defeated = int(data.get("enemies_defeated", 0))
    R.wave_number = int(data.get("wave_number", 1))
    R.kills_this_wave = int(data.get("kills_this_wave", 0))
    R.death_effects.clear()
    R.player_invuln_timer = 0.0
    R.enemies.clear()
    for raw in data.get("enemies", []):
        R.enemies.append(enemy.from_save_obj(raw))
    player.player_bullets.clear()
    world.update_chunk_streaming(R.player_x, R.player_y, cfg.TILE_SIZE)
    resolve_state_after_load()


def save_game_to_file():
    chunks = {f"{cx},{cy}": grid for (cx, cy), grid in R.chunk_cache.items()}
    edits = {f"{mx},{my}": ch for (mx, my), ch in R.world_cell_edits.items()}
    payload = {
        "version": 2,
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
    }
    with open(cfg.SAVE_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def bootstrap_session():
    """Set starting player position / state before the main loop (new game or load)."""
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
