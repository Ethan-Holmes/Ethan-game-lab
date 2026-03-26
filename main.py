"""
Ethan-game-lab — raycast FPS entry point.

The game loop below is intentionally linear: events → simulate → render.
Systems live in other modules (see imports). Mutable session data is in `runtime`.
"""

import json
import math
import random
import time

import pygame

import ambient
import assets
import enemy
import game_flow
import objectives
import pickups
import player
import progression
import runtime as R
import settings as cfg
import ui
import world

# -----------------------------------------------------------------------------
# Pygame / window
# -----------------------------------------------------------------------------
pygame.init()
try:
    pygame.mixer.init()
except pygame.error:
    pass

screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
pygame.display.set_caption(cfg.GAME_TITLE)

SCREEN_WIDTH = screen.get_width()
SCREEN_HEIGHT = screen.get_height()
NUM_RAYS = SCREEN_WIDTH

assets.load_all(cfg.ASSETS_DIR)
ambient.init_channels()
game_flow.bootstrap_session()
progression.refresh_runtime_wall_char()

clock = pygame.time.Clock()

# -----------------------------------------------------------------------------
# View / camera feedback (not part of saved runtime — reset on F9 load)
# -----------------------------------------------------------------------------
screen_center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
view_buffer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
game_flow.sync_mouse_grab_for_state()
if R.game_state in (R.STATE_PLAYING, R.STATE_PAUSED, R.STATE_WAVE_COMPLETE):
    pygame.mouse.set_pos(screen_center)
    pygame.mouse.get_rel()

crosshair_flash_timer = 0.0
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
damage_flash_timer = 0.0
shoot_buffer_timer = 0.0
combat_hit_marker_timer = 0.0
combat_hit_marker_duration = cfg.HIT_MARKER_DURATION
combat_hit_marker_is_kill = False
current_weapon_index = progression.preferred_weapon_index(0)
weapon_switch_flash_timer = 0.0
last_muzzle_scale = 1.0
last_muzzle_warm = False
last_muzzle_dur = 0.11
day_night_time = 0.0

# Smoothed move wish (world space, unit-ish) and mouse look — reset on F9 load.
move_wish_x = 0.0
move_wish_y = 0.0
_mouse_look_dx = 0.0
_mouse_look_dy = 0.0
place_block_repeat_timer = 0.0
demolish_cooldown_remaining = 0.0


def reset_transient_combat_state():
    """Clear view kick / particles after a mid-session load (F9)."""
    global recoil_yaw_offset, recoil_pitch_px, head_bob_phase, head_bob_px
    global muzzle_flash_timer, weapon_switch_flash_timer, last_muzzle_scale, last_muzzle_warm, last_muzzle_dur
    global sway_x, sway_y, shake_shoot_x, shake_shoot_y
    global shake_damage_x, shake_damage_y, strafe_tilt_px, shot_particles
    global damage_flash_timer, crosshair_flash_timer, shoot_cooldown_remaining
    global shoot_buffer_timer, combat_hit_marker_timer, combat_hit_marker_duration, combat_hit_marker_is_kill
    global move_wish_x, move_wish_y, _mouse_look_dx, _mouse_look_dy
    global place_block_repeat_timer, demolish_cooldown_remaining
    recoil_yaw_offset = 0.0
    recoil_pitch_px = 0.0
    head_bob_phase = 0.0
    head_bob_px = 0.0
    muzzle_flash_timer = 0.0
    weapon_switch_flash_timer = 0.0
    last_muzzle_scale = 1.0
    last_muzzle_warm = False
    last_muzzle_dur = 0.11
    sway_x = sway_y = 0.0
    shake_shoot_x = shake_shoot_y = 0.0
    shake_damage_x = shake_damage_y = 0.0
    strafe_tilt_px = 0.0
    shot_particles.clear()
    damage_flash_timer = 0.0
    crosshair_flash_timer = 0.0
    shoot_cooldown_remaining = 0.0
    shoot_buffer_timer = 0.0
    combat_hit_marker_timer = 0.0
    combat_hit_marker_duration = cfg.HIT_MARKER_DURATION
    combat_hit_marker_is_kill = False
    R.death_effects.clear()
    R.player_invuln_timer = 0.0
    move_wish_x = move_wish_y = 0.0
    _mouse_look_dx = _mouse_look_dy = 0.0
    place_block_repeat_timer = 0.0
    demolish_cooldown_remaining = 0.0


# =============================================================================
# Main loop
# =============================================================================
running = True
while running:
    game_flow.sync_mouse_grab_for_state()

    if R.game_state == R.STATE_PLAYING:
        ni = progression.preferred_weapon_index(current_weapon_index)
        if ni != current_weapon_index:
            current_weapon_index = ni

    simulation_active = R.game_state == R.STATE_PLAYING
    camera_active = R.game_state in (R.STATE_PLAYING, R.STATE_WAVE_COMPLETE, R.STATE_GAME_OVER)

    is_shooting = False
    shoot_requested = False
    demolish_requested = False

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.event.set_grab(False)
            pygame.mouse.set_visible(True)
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if R.game_state == R.STATE_START_MENU:
                    pygame.event.set_grab(False)
                    pygame.mouse.set_visible(True)
                    running = False
                elif R.game_state == R.STATE_PLAYING:
                    R.game_state = R.STATE_PAUSED
                    game_flow.sync_mouse_grab_for_state()
                elif R.game_state == R.STATE_PAUSED:
                    R.game_state = R.STATE_PLAYING
                    game_flow.sync_mouse_grab_for_state()
                elif R.game_state in (R.STATE_WAVE_COMPLETE, R.STATE_GAME_OVER):
                    pygame.event.set_grab(False)
                    pygame.mouse.set_visible(True)
                    running = False
            elif event.key == pygame.K_q and R.game_state in (
                R.STATE_START_MENU,
                R.STATE_PAUSED,
                R.STATE_WAVE_COMPLETE,
                R.STATE_GAME_OVER,
            ):
                pygame.event.set_grab(False)
                pygame.mouse.set_visible(True)
                running = False
            elif event.key == pygame.K_F5:
                try:
                    game_flow.save_game_to_file()
                except OSError as e:
                    print("Save failed:", e)
                else:
                    print("Saved:", cfg.SAVE_FILE_PATH)
            elif event.key == pygame.K_F9:
                try:
                    with open(cfg.SAVE_FILE_PATH, "r", encoding="utf-8") as f:
                        game_flow.apply_save_data(json.load(f))
                    reset_transient_combat_state()
                except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                    print("Load failed:", e)
                else:
                    print("Loaded:", cfg.SAVE_FILE_PATH)
                    current_weapon_index = progression.preferred_weapon_index(current_weapon_index)
                    game_flow.sync_mouse_grab_for_state()
            elif simulation_active and event.key == pygame.K_r:
                wi = current_weapon_index
                ww = player.WEAPONS[wi]
                if (
                    progression.is_weapon_slot_unlocked(ww.slot)
                    and player.reload_timers[wi] <= 0
                    and player.weapon_ammo[wi] < ww.magazine_size
                ):
                    player.reload_timers[wi] = ww.reload_time
            elif event.key == pygame.K_n and R.game_state == R.STATE_WAVE_COMPLETE:
                game_flow.spawn_next_wave()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if R.game_state == R.STATE_START_MENU:
                    game_flow.begin_playing_from_menu()
                    current_weapon_index = progression.preferred_weapon_index(0)
                elif R.game_state == R.STATE_GAME_OVER:
                    game_flow.regenerate_world_map()
                    current_weapon_index = progression.preferred_weapon_index(0)
            elif event.key == pygame.K_p:
                if R.game_state == R.STATE_PLAYING:
                    R.game_state = R.STATE_PAUSED
                    game_flow.sync_mouse_grab_for_state()
                elif R.game_state == R.STATE_PAUSED:
                    R.game_state = R.STATE_PLAYING
                    game_flow.sync_mouse_grab_for_state()
            elif simulation_active:
                if event.key == pygame.K_f:
                    demolish_requested = True
                elif event.key == pygame.K_h:
                    R.construction_hint_dismissed = True
                    R.construction_hint_until_monotonic = 0.0
                slot_keys = {
                    pygame.K_1: 1,
                    pygame.K_2: 2,
                    pygame.K_3: 3,
                    pygame.K_4: 4,
                    pygame.K_5: 5,
                }
                sk = slot_keys.get(event.key)
                if sk is not None:
                    for idx, w in enumerate(player.WEAPONS):
                        if w.slot == sk:
                            if not progression.is_weapon_slot_unlocked(w.slot):
                                break
                            if idx != current_weapon_index:
                                current_weapon_index = idx
                                weapon_switch_flash_timer = cfg.WEAPON_SWITCH_FLASH_SEC
                            break

    # --- Update (time + simulation) ---
    dt = clock.tick(60) / 1000.0
    day_night_time += dt

    if simulation_active:
        for ri in range(len(player.WEAPONS)):
            if player.reload_timers[ri] > 0:
                player.reload_timers[ri] -= dt
                if player.reload_timers[ri] <= 0:
                    player.reload_timers[ri] = 0.0
                    player.weapon_ammo[ri] = player.WEAPONS[ri].magazine_size

    keys = pygame.key.get_pressed()
    mouse_buttons = pygame.mouse.get_pressed()

    if camera_active:
        mouse_dx, mouse_dy = pygame.mouse.get_rel()
        cl = cfg.MOUSE_DELTA_CLAMP_PX
        mouse_dx = max(-cl, min(cl, mouse_dx))
        mouse_dy = max(-cl, min(cl, mouse_dy))
        sm = cfg.MOUSE_LOOK_SMOOTHING
        _mouse_look_dx += (mouse_dx - _mouse_look_dx) * sm
        _mouse_look_dy += (mouse_dy - _mouse_look_dy) * sm
        R.player_angle += _mouse_look_dx * R.mouse_sensitivity
        turn = 0.0
        if keys[pygame.K_LEFT]:
            turn -= 1.0
        if keys[pygame.K_RIGHT]:
            turn += 1.0
        if turn != 0.0:
            R.player_angle += turn * cfg.PLAYER_TURN_KEYS_RAD_PER_SEC * dt
        sway_x += _mouse_look_dx * cfg.SWAY_MOUSE_SCALE
        sway_y += _mouse_look_dy * cfg.SWAY_MOUSE_SCALE
        sway_x = max(-cfg.SWAY_MAX_PX, min(cfg.SWAY_MAX_PX, sway_x))
        sway_y = max(-cfg.SWAY_MAX_PX, min(cfg.SWAY_MAX_PX, sway_y))
        pygame.mouse.set_pos(screen_center)
    else:
        pygame.mouse.get_rel()
        _mouse_look_dx = 0.0
        _mouse_look_dy = 0.0
    sway_x -= sway_x * cfg.SWAY_RECOVERY * dt
    sway_y -= sway_y * cfg.SWAY_RECOVERY * dt

    aim_x = int(screen_center[0] + sway_x)
    aim_y = int(screen_center[1] + sway_y)

    wpn = player.WEAPONS[current_weapon_index]
    wi_fire = current_weapon_index

    if simulation_active:
        if keys[pygame.K_SPACE] or mouse_buttons[0]:
            shoot_requested = True
            shoot_buffer_timer = cfg.SHOOT_INPUT_BUFFER_SEC

    if simulation_active:
        can_fire = (
            progression.is_weapon_slot_unlocked(wpn.slot)
            and player.reload_timers[wi_fire] <= 0
            and player.weapon_ammo[wi_fire] > 0
            and shoot_cooldown_remaining <= 0
        )
        if can_fire and (shoot_requested or shoot_buffer_timer > 0):
            is_shooting = True
            shoot_cooldown_remaining = wpn.cooldown
            player.weapon_ammo[wi_fire] -= 1
            shoot_buffer_timer = 0.0
        elif shoot_buffer_timer > 0:
            shoot_buffer_timer = max(0.0, shoot_buffer_timer - dt)
        shoot_requested = False
    if simulation_active:
        shoot_cooldown_remaining = max(0.0, shoot_cooldown_remaining - dt)

    if is_shooting and simulation_active:
        crosshair_flash_timer = cfg.CROSSHAIR_FLASH_DURATION
        last_muzzle_scale = wpn.muzzle_flash_scale
        last_muzzle_warm = wpn.tracer_style == 2
        last_muzzle_dur = wpn.muzzle_flash_duration
        muzzle_flash_timer = last_muzzle_dur
        assets.play_sfx(assets.SOUND_GUNSHOT)
        player.spawn_muzzle_particles(shot_particles, aim_x, aim_y, burst_mul=wpn.particle_burst_mul)
        recoil_yaw_offset += random.uniform(-wpn.recoil_yaw, wpn.recoil_yaw)
        recoil_pitch_px += random.uniform(wpn.recoil_pitch_px * 0.55, wpn.recoil_pitch_px * 1.15)
        recoil_yaw_offset = max(-cfg.RECOIL_YAW_CAP, min(cfg.RECOIL_YAW_CAP, recoil_yaw_offset))
        recoil_pitch_px = max(-cfg.RECOIL_PITCH_CAP_PX, min(cfg.RECOIL_PITCH_CAP_PX, recoil_pitch_px))
        smx = cfg.SCREEN_SHAKE_IMPULSE_X * wpn.screen_shake_mul
        smy = cfg.SCREEN_SHAKE_IMPULSE_Y * wpn.screen_shake_mul
        shake_shoot_x += random.uniform(-smx, smx)
        shake_shoot_y += random.uniform(-smy, smy)
        player.spawn_weapon_volley(
            player.player_bullets,
            R.player_x,
            R.player_y,
            R.player_angle + recoil_yaw_offset,
            wpn,
        )
        if player.weapon_ammo[wi_fire] <= 0 and player.reload_timers[wi_fire] <= 0:
            player.reload_timers[wi_fire] = wpn.reload_time
    crosshair_flash_timer = max(0.0, crosshair_flash_timer - dt)
    muzzle_flash_timer = max(0.0, muzzle_flash_timer - dt)
    weapon_switch_flash_timer = max(0.0, weapon_switch_flash_timer - dt)

    forward_x = math.cos(R.player_angle)
    forward_y = math.sin(R.player_angle)
    strafe_x = -math.sin(R.player_angle)
    strafe_y = math.cos(R.player_angle)

    is_moving = False
    if simulation_active:
        R.player_invuln_timer = max(0.0, R.player_invuln_timer - dt)
        hp_before = R.player_health
        raw_mx = 0.0
        raw_my = 0.0
        if keys[pygame.K_w]:
            raw_mx += forward_x
            raw_my += forward_y
        if keys[pygame.K_s]:
            raw_mx -= forward_x
            raw_my -= forward_y
        if keys[pygame.K_d]:
            raw_mx += strafe_x
            raw_my += strafe_y
        if keys[pygame.K_a]:
            raw_mx -= strafe_x
            raw_my -= strafe_y

        raw_len = math.hypot(raw_mx, raw_my)
        # No keys held: stop immediately (do not ease move_wish toward zero — that feels like ice skating).
        if raw_len < 1e-9:
            move_wish_x = 0.0
            move_wish_y = 0.0
        else:
            target_wx = raw_mx / raw_len
            target_wy = raw_my / raw_len
            sm = max(0.0, min(1.0, cfg.MOVE_INPUT_SMOOTH_RATE * dt))
            move_wish_x += (target_wx - move_wish_x) * sm
            move_wish_y += (target_wy - move_wish_y) * sm

        wish_len = math.hypot(move_wish_x, move_wish_y)
        is_moving = wish_len > 0.06
        shift_held = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        can_sprint = shift_held and raw_len > 1e-9 and R.stamina > cfg.STAMINA_MIN_TO_SPRINT
        sprint_speed = cfg.PLAYER_SPEED_WALK * cfg.PLAYER_SPRINT_MULTIPLIER
        target_speed = sprint_speed if can_sprint else cfg.PLAYER_SPEED_WALK
        rate = (
            cfg.MOVE_ACCEL_RATE if target_speed > R.move_speed_smoothed else cfg.MOVE_DECEL_RATE
        )
        R.move_speed_smoothed += (target_speed - R.move_speed_smoothed) * min(1.0, rate * dt)
        if wish_len > 1e-9:
            nx = move_wish_x / wish_len
            ny = move_wish_y / wish_len
            move_x = nx * R.move_speed_smoothed * dt
            move_y = ny * R.move_speed_smoothed * dt
            R.player_x, R.player_y = world.apply_slide_move(
                R.player_x, R.player_y, move_x, move_y, cfg.TILE_SIZE
            )

        if can_sprint:
            R.stamina -= cfg.STAMINA_DRAIN_PER_SEC * dt
        else:
            R.stamina += cfg.STAMINA_REGEN_PER_SEC * dt
        R.stamina = max(0.0, min(cfg.STAMINA_MAX, R.stamina))

        pickups.collect_near_player(R.player_x, R.player_y)

        place_block_repeat_timer = max(0.0, place_block_repeat_timer - dt)
        demolish_cooldown_remaining = max(0.0, demolish_cooldown_remaining - dt)
        if mouse_buttons[2] and R.inventory_blocks > 0:
            if place_block_repeat_timer <= 0:
                if world.try_place_wall_block(
                    R.player_x,
                    R.player_y,
                    R.player_angle + recoil_yaw_offset,
                    cfg.TILE_SIZE,
                    R.enemies,
                    cfg.PLACE_BLOCK_MAX_DIST,
                ):
                    place_block_repeat_timer = cfg.PLACE_BLOCK_REPEAT_INTERVAL
                    R.construction_hint_dismissed = True
                    assets.play_sfx(assets.SOUND_HIT)
                else:
                    place_block_repeat_timer = 0.06
        else:
            place_block_repeat_timer = 0.0

        if demolish_requested and demolish_cooldown_remaining <= 0:
            if world.try_demolish_wall_block(
                R.player_x,
                R.player_y,
                R.player_angle + recoil_yaw_offset,
                cfg.TILE_SIZE,
                cfg.PLACE_BLOCK_MAX_DIST,
            ):
                demolish_cooldown_remaining = cfg.DEMOLISH_COOLDOWN
                R.construction_hint_dismissed = True
                assets.play_sfx(assets.SOUND_HIT)

        enemy.update_ai(R.enemies, R.player_x, R.player_y, dt, cfg.TILE_SIZE)
        enemy.update_hit_flash(R.enemies, dt)
        enemy.update_death_effects(dt)
        objectives.tick(dt)

        n_hits, n_kills = player.update_bullets(player.player_bullets, dt, cfg.TILE_SIZE, R.enemies)
        if n_kills > 0:
            R.inventory_blocks = min(
                R.inventory_blocks + n_kills * cfg.BLOCKS_PER_KILL,
                cfg.INVENTORY_BLOCKS_MAX,
            )
            combat_hit_marker_timer = cfg.KILL_MARKER_DURATION
            combat_hit_marker_duration = cfg.KILL_MARKER_DURATION
            combat_hit_marker_is_kill = True
        elif n_hits > 0:
            combat_hit_marker_timer = cfg.HIT_MARKER_DURATION
            combat_hit_marker_duration = cfg.HIT_MARKER_DURATION
            combat_hit_marker_is_kill = False

        can_take_damage = R.player_invuln_timer <= 0
        shot_dmg = enemy.update_shooting(
            R.enemies, R.player_x, R.player_y, dt, cfg.TILE_SIZE, apply_damage=can_take_damage
        )
        contact_dmg = 0.0
        if can_take_damage:
            for e in R.enemies:
                d = math.hypot(e.x - R.player_x, e.y - R.player_y)
                if d < cfg.ENEMY_CONTACT_RANGE:
                    contact_dmg += e.spec().contact_dps * e.combat_scale * dt
        R.player_health -= shot_dmg + contact_dmg
        R.player_health = max(0.0, R.player_health)
        if R.player_health < hp_before - 1e-9:
            delta_hp = hp_before - R.player_health
            R.player_invuln_timer = cfg.PLAYER_INVULN_DURATION
            damage_flash_timer = min(
                cfg.DAMAGE_FLASH_CAP,
                damage_flash_timer + cfg.DAMAGE_FLASH_BASE + cfg.DAMAGE_FLASH_PER_HP * delta_hp,
            )
            if shot_dmg > 1e-6:
                damage_flash_timer = min(
                    cfg.DAMAGE_FLASH_CAP,
                    damage_flash_timer + cfg.ENEMY_SHOT_FEEDBACK_EXTRA,
                )
            dmg_shake_scale = min(
                cfg.DAMAGE_SHAKE_HP_SCALE_CAP,
                1.0 + delta_hp * cfg.DAMAGE_SHAKE_HP_SCALE,
            )
            shake_damage_x += (
                random.uniform(-cfg.DAMAGE_SHAKE_IMPULSE_X, cfg.DAMAGE_SHAKE_IMPULSE_X) * dmg_shake_scale
            )
            shake_damage_y += (
                random.uniform(-cfg.DAMAGE_SHAKE_IMPULSE_Y, cfg.DAMAGE_SHAKE_IMPULSE_Y) * dmg_shake_scale
            )
            if shot_dmg > 1e-6:
                shake_damage_x += random.uniform(-2.5, 2.5)
                shake_damage_y += random.uniform(-2.5, 2.5)
        if R.player_health <= 0:
            progression.record_game_over(R.wave_number)
            R.game_state = R.STATE_GAME_OVER
            print("GAME OVER")
        elif R.wave_in_progress and objectives.is_satisfied():
            R.inventory_blocks = min(
                R.inventory_blocks + cfg.BLOCKS_WAVE_CLEAR_BONUS,
                cfg.INVENTORY_BLOCKS_MAX,
            )
            R.pending_reward_lines = progression.on_wave_cleared(R.wave_number)
            R.game_state = R.STATE_WAVE_COMPLETE
            R.wave_in_progress = False

    else:
        sm = max(0.0, min(1.0, cfg.MOVE_INPUT_SMOOTH_RATE * dt))
        move_wish_x += (0.0 - move_wish_x) * sm
        move_wish_y += (0.0 - move_wish_y) * sm

    if R.game_state == R.STATE_GAME_OVER:
        R.move_speed_smoothed += (cfg.PLAYER_SPEED_WALK - R.move_speed_smoothed) * min(
            1.0, cfg.MOVE_DECEL_RATE * dt
        )

    ambient.tick(
        dt,
        assets.SOUND_AMBIENT_WIND,
        assets.SOUND_AMBIENT_TRAFFIC,
        assets.SOUND_AMBIENT_INDUSTRIAL,
    )

    combat_hit_marker_timer = max(0.0, combat_hit_marker_timer - dt)
    damage_flash_timer = max(0.0, damage_flash_timer - dt * 2.4)

    if simulation_active and is_moving:
        head_bob_phase += (
            2 * math.pi * cfg.HEAD_BOB_FREQ_HZ * (R.move_speed_smoothed / cfg.HEAD_BOB_REF_SPEED) * dt
        )
    bob_target = (
        math.sin(head_bob_phase) * cfg.HEAD_BOB_AMPLITUDE_PX if (simulation_active and is_moving) else 0.0
    )
    head_bob_px += (bob_target - head_bob_px) * min(1.0, cfg.HEAD_BOB_SMOOTH * dt)

    strafe_tilt_target = 0.0
    if simulation_active:
        if keys[pygame.K_d] and not keys[pygame.K_a]:
            strafe_tilt_target = cfg.STRAFE_TILT_MAX_PX
        elif keys[pygame.K_a] and not keys[pygame.K_d]:
            strafe_tilt_target = -cfg.STRAFE_TILT_MAX_PX
    strafe_tilt_px += (strafe_tilt_target - strafe_tilt_px) * min(1.0, cfg.STRAFE_TILT_SMOOTH * dt)

    recoil_yaw_offset -= recoil_yaw_offset * cfg.RECOIL_RECOVERY * dt
    recoil_pitch_px -= recoil_pitch_px * cfg.RECOIL_RECOVERY * dt
    shake_shoot_x -= shake_shoot_x * cfg.SCREEN_SHAKE_DECAY * dt
    shake_shoot_y -= shake_shoot_y * cfg.SCREEN_SHAKE_DECAY * dt
    shake_damage_x -= shake_damage_x * cfg.DAMAGE_SHAKE_DECAY * dt
    shake_damage_y -= shake_damage_y * cfg.DAMAGE_SHAKE_DECAY * dt

    if simulation_active:
        player.update_shot_particles(shot_particles, dt)

    world.update_chunk_streaming(R.player_x, R.player_y, cfg.TILE_SIZE)
    view_yaw = R.player_angle + recoil_yaw_offset
    view_pitch_px = recoil_pitch_px + head_bob_px

    ray_hits = world.compute_ray_hits(R.player_x, R.player_y, view_yaw, cfg.TILE_SIZE, cfg.FOV, NUM_RAYS)

    placement_preview = None
    if R.game_state == R.STATE_PLAYING:
        placement_preview = world.get_placement_preview(
            R.player_x,
            R.player_y,
            view_yaw,
            cfg.TILE_SIZE,
            R.enemies,
            cfg.PLACE_BLOCK_MAX_DIST,
            R.inventory_blocks,
        )

    demolish_cd_ratio = (
        demolish_cooldown_remaining / cfg.DEMOLISH_COOLDOWN if demolish_cooldown_remaining > 0 else 0.0
    )

    # --- Render ---
    world.draw_raycast_view(
        view_buffer,
        ray_hits,
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
        cfg.TILE_SIZE,
        cfg.FOV,
        view_pitch_px,
        assets.WALL_TEXTURES,
        horizon_skew_px=strafe_tilt_px,
        player_x=R.player_x,
        player_y=R.player_y,
        view_yaw=view_yaw,
    )
    if placement_preview is not None:
        ui.draw_placement_preview(
            view_buffer,
            placement_preview,
            R.player_x,
            R.player_y,
            view_yaw,
            ray_hits,
            SCREEN_WIDTH,
            SCREEN_HEIGHT,
            cfg.FOV,
            view_pitch_px,
            strafe_tilt_px,
            cfg.TILE_SIZE,
        )
    enemy.draw_billboards(
        view_buffer,
        R.enemies,
        R.player_x,
        R.player_y,
        view_yaw,
        ray_hits,
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
        cfg.FOV,
        view_pitch_px,
        horizon_skew_px=strafe_tilt_px,
        billboard_texture=None,
    )
    pickups.draw_pickups(
        view_buffer,
        R.player_x,
        R.player_y,
        view_yaw,
        ray_hits,
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
        cfg.FOV,
        view_pitch_px,
        strafe_tilt_px,
    )
    enemy.draw_death_effects(
        view_buffer,
        R.player_x,
        R.player_y,
        view_yaw,
        ray_hits,
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
        cfg.FOV,
        view_pitch_px,
        horizon_skew_px=strafe_tilt_px,
    )
    player.draw_bullet_tracers(
        view_buffer,
        player.player_bullets,
        R.player_x,
        R.player_y,
        view_yaw,
        ray_hits,
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
        cfg.FOV,
        view_pitch_px,
        horizon_skew_px=strafe_tilt_px,
    )
    mdur = last_muzzle_dur if last_muzzle_dur > 1e-6 else cfg.MUZZLE_FLASH_DURATION
    player.draw_muzzle_flash(
        view_buffer, aim_x, aim_y, muzzle_flash_timer, mdur, last_muzzle_scale, last_muzzle_warm
    )
    player.draw_shot_particles(view_buffer, shot_particles)
    rti_hud = player.reload_timers[current_weapon_index]
    reloading_hud = rti_hud > 0
    low_ammo_hud = (
        not reloading_hud
        and wpn.magazine_size > 0
        and player.weapon_ammo[current_weapon_index] <= max(1, int(wpn.magazine_size * 0.25))
    )
    ui.draw_crosshair(view_buffer, aim_x, aim_y, crosshair_flash_timer, low_ammo=low_ammo_hud)
    ui.draw_hit_marker(
        view_buffer,
        SCREEN_WIDTH // 2,
        SCREEN_HEIGHT // 2,
        combat_hit_marker_timer,
        combat_hit_marker_duration,
        combat_hit_marker_is_kill,
    )
    ui.draw_minimap(
        view_buffer,
        R.player_x,
        R.player_y,
        R.player_angle,
        cfg.TILE_SIZE,
        SCREEN_WIDTH,
        R.enemies,
        objective_world=objectives.minimap_objective(),
        district_label=R.ambient_zone_label,
    )
    ui.draw_damage_flash(view_buffer, damage_flash_timer, SCREEN_WIDTH, SCREEN_HEIGHT)
    ui.draw_damage_edge(view_buffer, damage_flash_timer, SCREEN_WIDTH, SCREEN_HEIGHT)
    rti = player.reload_timers[current_weapon_index]
    reloading = rti > 0
    reload_progress = (1.0 - rti / wpn.reload_time) if reloading and wpn.reload_time > 0 else None
    m_title, m_detail, m_prog = objectives.hud_objective_lines()
    ui.draw_hud(
        view_buffer,
        R.player_health,
        cfg.PLAYER_HP_MAX,
        wpn,
        len(R.enemies),
        player.weapon_ammo[current_weapon_index],
        wpn.magazine_size,
        reloading,
        reload_progress,
        R.inventory_blocks,
        cfg.INVENTORY_BLOCKS_MAX,
        R.stamina,
        cfg.STAMINA_MAX,
        R.enemies_defeated,
        R.kills_this_wave,
        R.wave_number,
        R.game_state,
        demolish_cd_ratio,
        m_title,
        m_detail,
        m_prog,
        weapon_unlocks=progression.weapon_unlock_flags(),
        career_line=progression.to_hud_career_compact(),
    )
    ui.draw_weapon_switch_banner(
        view_buffer,
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
        wpn.name,
        weapon_switch_flash_timer,
        cfg.WEAPON_SWITCH_FLASH_SEC,
    )
    if R.game_state == R.STATE_PLAYING:
        ui.draw_construction_hint(view_buffer, SCREEN_WIDTH, SCREEN_HEIGHT)
        if time.monotonic() < R.objective_intro_until_monotonic:
            ui.draw_objective_intro_banner(
                view_buffer,
                SCREEN_WIDTH,
                SCREEN_HEIGHT,
                R.objective_title,
                R.objective_detail,
            )
    if R.game_state == R.STATE_START_MENU:
        ui.draw_start_menu_overlay(
            view_buffer,
            SCREEN_WIDTH,
            SCREEN_HEIGHT,
            career_line=progression.career_summary_line(),
        )
    if R.game_state == R.STATE_WAVE_COMPLETE:
        ui.draw_wave_complete_overlay(
            view_buffer,
            SCREEN_WIDTH,
            SCREEN_HEIGHT,
            R.wave_number,
            R.wave_number + 1,
            objectives.wave_complete_subtitle(),
            reward_lines=getattr(R, "pending_reward_lines", None) or [],
        )
    if R.game_state == R.STATE_GAME_OVER:
        ui.draw_game_over_overlay(
            view_buffer,
            SCREEN_WIDTH,
            SCREEN_HEIGHT,
            career_line=progression.career_summary_line(),
        )
    if R.game_state == R.STATE_PAUSED:
        ui.draw_paused_overlay(view_buffer, SCREEN_WIDTH, SCREEN_HEIGHT)

    phase = 2 * math.pi * ((day_night_time % cfg.DAY_NIGHT_PERIOD_SEC) / cfg.DAY_NIGHT_PERIOD_SEC)
    t = 0.5 + 0.5 * math.sin(phase)
    mr, mg, mb = cfg.DAY_NIGHT_MULT_MIN
    xr, xg, xb = cfg.DAY_NIGHT_MULT_MAX
    r_mul = int(255 * (mr + (xr - mr) * t))
    g_mul = int(255 * (mg + (xg - mg) * t))
    b_mul = int(255 * (mb + (xb - mb) * t))
    view_buffer.fill((r_mul, g_mul, b_mul), special_flags=pygame.BLEND_RGBA_MULT)

    screen.fill((0, 0, 0))
    shake_x = shake_shoot_x + shake_damage_x
    shake_y = shake_shoot_y + shake_damage_y
    screen.blit(view_buffer, (int(shake_x), int(shake_y)))
    pygame.display.flip()

pygame.quit()
