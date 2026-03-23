"""
Ethan-game-lab — raycast FPS entry point.

The game loop below is intentionally linear: events → simulate → render.
Systems live in other modules (see imports). Mutable session data is in `runtime`.
"""

import json
import math
import random

import pygame

import assets
import enemy
import game_flow
import player
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
game_flow.bootstrap_session()

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
current_weapon_index = 0
day_night_time = 0.0


def reset_transient_combat_state():
    """Clear view kick / particles after a mid-session load (F9)."""
    global recoil_yaw_offset, recoil_pitch_px, head_bob_phase, head_bob_px
    global muzzle_flash_timer, sway_x, sway_y, shake_shoot_x, shake_shoot_y
    global shake_damage_x, shake_damage_y, strafe_tilt_px, shot_particles
    global damage_flash_timer, crosshair_flash_timer, shoot_cooldown_remaining
    global shoot_buffer_timer, combat_hit_marker_timer, combat_hit_marker_duration, combat_hit_marker_is_kill
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
    damage_flash_timer = 0.0
    crosshair_flash_timer = 0.0
    shoot_cooldown_remaining = 0.0
    shoot_buffer_timer = 0.0
    combat_hit_marker_timer = 0.0
    combat_hit_marker_duration = cfg.HIT_MARKER_DURATION
    combat_hit_marker_is_kill = False
    R.death_effects.clear()
    R.player_invuln_timer = 0.0


# =============================================================================
# Main loop
# =============================================================================
running = True
while running:
    game_flow.sync_mouse_grab_for_state()

    simulation_active = R.game_state == R.STATE_PLAYING
    camera_active = R.game_state in (R.STATE_PLAYING, R.STATE_WAVE_COMPLETE, R.STATE_GAME_OVER)

    is_shooting = False
    shoot_requested = False
    place_block_requested = False

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
                    game_flow.sync_mouse_grab_for_state()
            elif simulation_active and event.key == pygame.K_r:
                wi = current_weapon_index
                ww = player.WEAPONS[wi]
                if player.reload_timers[wi] <= 0 and player.weapon_ammo[wi] < ww.magazine_size:
                    player.reload_timers[wi] = ww.reload_time
            elif event.key == pygame.K_n and R.game_state == R.STATE_WAVE_COMPLETE:
                game_flow.spawn_next_wave()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if R.game_state == R.STATE_START_MENU:
                    game_flow.begin_playing_from_menu()
                elif R.game_state == R.STATE_GAME_OVER:
                    game_flow.regenerate_world_map()
            elif event.key == pygame.K_p:
                if R.game_state == R.STATE_PLAYING:
                    R.game_state = R.STATE_PAUSED
                elif R.game_state == R.STATE_PAUSED:
                    R.game_state = R.STATE_PLAYING
            elif simulation_active:
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
                            current_weapon_index = idx
                            break
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if simulation_active:
                shoot_requested = True
                shoot_buffer_timer = cfg.SHOOT_INPUT_BUFFER_SEC
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if simulation_active:
                place_block_requested = True

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

    if camera_active:
        mouse_dx, mouse_dy = pygame.mouse.get_rel()
        R.player_angle += mouse_dx * R.mouse_sensitivity
        sway_x += mouse_dx * cfg.SWAY_MOUSE_SCALE
        sway_y += mouse_dy * cfg.SWAY_MOUSE_SCALE
        sway_x = max(-cfg.SWAY_MAX_PX, min(cfg.SWAY_MAX_PX, sway_x))
        sway_y = max(-cfg.SWAY_MAX_PX, min(cfg.SWAY_MAX_PX, sway_y))
        pygame.mouse.set_pos(screen_center)
    else:
        pygame.mouse.get_rel()
    sway_x -= sway_x * cfg.SWAY_RECOVERY * dt
    sway_y -= sway_y * cfg.SWAY_RECOVERY * dt

    aim_x = int(screen_center[0] + sway_x)
    aim_y = int(screen_center[1] + sway_y)

    wpn = player.WEAPONS[current_weapon_index]
    wi_fire = current_weapon_index

    if simulation_active:
        can_fire = (
            player.reload_timers[wi_fire] <= 0
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
        muzzle_flash_timer = cfg.MUZZLE_FLASH_DURATION
        assets.play_sfx(assets.SOUND_GUNSHOT)
        player.spawn_muzzle_particles(shot_particles, aim_x, aim_y)
        recoil_yaw_offset += random.uniform(-wpn.recoil_yaw, wpn.recoil_yaw)
        recoil_pitch_px += random.uniform(wpn.recoil_pitch_px * 0.55, wpn.recoil_pitch_px * 1.1)
        recoil_yaw_offset = max(-0.12, min(0.12, recoil_yaw_offset))
        recoil_pitch_px = max(-90.0, min(90.0, recoil_pitch_px))
        shake_shoot_x += random.uniform(-cfg.SCREEN_SHAKE_IMPULSE_X, cfg.SCREEN_SHAKE_IMPULSE_X)
        shake_shoot_y += random.uniform(-cfg.SCREEN_SHAKE_IMPULSE_Y, cfg.SCREEN_SHAKE_IMPULSE_Y)
        player.spawn_bullet(
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

    keys = pygame.key.get_pressed()
    forward_x = math.cos(R.player_angle)
    forward_y = math.sin(R.player_angle)
    strafe_x = -math.sin(R.player_angle)
    strafe_y = math.cos(R.player_angle)

    is_moving = False
    if simulation_active:
        R.player_invuln_timer = max(0.0, R.player_invuln_timer - dt)
        hp_before = R.player_health
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

        length = math.hypot(move_x, move_y)
        is_moving = length > 0
        shift_held = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        can_sprint = shift_held and is_moving and R.stamina > cfg.STAMINA_MIN_TO_SPRINT
        sprint_speed = cfg.PLAYER_SPEED_WALK * cfg.PLAYER_SPRINT_MULTIPLIER
        target_speed = sprint_speed if can_sprint else cfg.PLAYER_SPEED_WALK
        R.move_speed_smoothed += (target_speed - R.move_speed_smoothed) * min(
            1.0, cfg.MOVE_SPEED_SMOOTH_RATE * dt
        )
        if length > 0:
            move_x = (move_x / length) * R.move_speed_smoothed * dt
            move_y = (move_y / length) * R.move_speed_smoothed * dt
            R.player_x, R.player_y = world.apply_slide_move(
                R.player_x, R.player_y, move_x, move_y, cfg.TILE_SIZE
            )

        if can_sprint:
            R.stamina -= cfg.STAMINA_DRAIN_PER_SEC * dt
        else:
            R.stamina += cfg.STAMINA_REGEN_PER_SEC * dt
        R.stamina = max(0.0, min(cfg.STAMINA_MAX, R.stamina))

        enemy.update_ai(R.enemies, R.player_x, R.player_y, dt, cfg.TILE_SIZE)
        enemy.update_hit_flash(R.enemies, dt)
        enemy.update_death_effects(dt)

        n_hits, n_kills = player.update_bullets(player.player_bullets, dt, cfg.TILE_SIZE, R.enemies)
        if n_kills > 0:
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
            R.game_state = R.STATE_GAME_OVER
            print("GAME OVER")
        elif R.wave_in_progress and len(R.enemies) == 0:
            R.game_state = R.STATE_WAVE_COMPLETE
            R.wave_in_progress = False

    elif R.game_state == R.STATE_GAME_OVER:
        R.move_speed_smoothed += (cfg.PLAYER_SPEED_WALK - R.move_speed_smoothed) * min(
            1.0, cfg.MOVE_SPEED_SMOOTH_RATE * dt
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

    if simulation_active and place_block_requested and R.inventory_blocks > 0:
        world.try_place_wall_block(
            R.player_x, R.player_y, view_yaw, cfg.TILE_SIZE, R.enemies, cfg.PLACE_BLOCK_MAX_DIST
        )

    ray_hits = world.compute_ray_hits(R.player_x, R.player_y, view_yaw, cfg.TILE_SIZE, cfg.FOV, NUM_RAYS)

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
    player.draw_muzzle_flash(view_buffer, aim_x, aim_y, muzzle_flash_timer, cfg.MUZZLE_FLASH_DURATION)
    player.draw_shot_particles(view_buffer, shot_particles)
    ui.draw_crosshair(view_buffer, aim_x, aim_y, crosshair_flash_timer)
    ui.draw_hit_marker(
        view_buffer,
        SCREEN_WIDTH // 2,
        SCREEN_HEIGHT // 2,
        combat_hit_marker_timer,
        combat_hit_marker_duration,
        combat_hit_marker_is_kill,
    )
    ui.draw_minimap(view_buffer, R.player_x, R.player_y, R.player_angle, cfg.TILE_SIZE, SCREEN_WIDTH, R.enemies)
    ui.draw_damage_flash(view_buffer, damage_flash_timer, SCREEN_WIDTH, SCREEN_HEIGHT)
    ui.draw_damage_edge(view_buffer, damage_flash_timer, SCREEN_WIDTH, SCREEN_HEIGHT)
    rti = player.reload_timers[current_weapon_index]
    reloading = rti > 0
    reload_progress = (1.0 - rti / wpn.reload_time) if reloading and wpn.reload_time > 0 else None
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
        R.stamina,
        cfg.STAMINA_MAX,
        R.enemies_defeated,
        R.kills_this_wave,
        R.wave_number,
        R.game_state,
    )
    if R.game_state == R.STATE_START_MENU:
        ui.draw_start_menu_overlay(view_buffer, SCREEN_WIDTH, SCREEN_HEIGHT)
    if R.game_state == R.STATE_WAVE_COMPLETE:
        ui.draw_wave_complete_overlay(
            view_buffer, SCREEN_WIDTH, SCREEN_HEIGHT, R.wave_number, R.wave_number + 1
        )
    if R.game_state == R.STATE_GAME_OVER:
        ui.draw_game_over_overlay(view_buffer, SCREEN_WIDTH, SCREEN_HEIGHT)
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
