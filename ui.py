"""
2D overlays: HUD, minimap, crosshair, menus, pause screen.

Visual style: dark panels, soft shadows, accent highlights — tuned via settings.
"""

import math

import pygame

import enemy_types as et
import settings as cfg
import world


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------


def _font(px):
    return pygame.font.Font(None, px)


def _blit_shadow_text(surface, font, text, color, pos, shadow=(0, 0, 0), off=1):
    x, y = pos
    sh = font.render(text, True, shadow)
    fg = font.render(text, True, color)
    surface.blit(sh, (x + off, y + off))
    surface.blit(fg, (x, y))


def _draw_soft_panel(surface, x, y, w, h, radius=6):
    """Drop shadow + filled panel + border (game-friendly readability)."""
    shadow = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)
    try:
        pygame.draw.rect(
            shadow,
            (0, 0, 0, 55),
            (4, 4, w, h),
            border_radius=radius,
        )
    except TypeError:
        pygame.draw.rect(shadow, (0, 0, 0, 55), (4, 4, w, h))
    surface.blit(shadow, (x - 2, y - 2))
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    bg = (*cfg.HUD_PANEL_BG, cfg.HUD_PANEL_BG_ALPHA)
    try:
        pygame.draw.rect(panel, bg, (0, 0, w, h), border_radius=radius)
        pygame.draw.rect(panel, cfg.HUD_PANEL_BORDER, (0, 0, w, h), 1, border_radius=radius)
        pygame.draw.rect(
            panel,
            cfg.HUD_PANEL_INNER_HIGHLIGHT,
            (1, 1, w - 2, h - 2),
            1,
            border_radius=max(0, radius - 1),
        )
    except TypeError:
        pygame.draw.rect(panel, bg, (0, 0, w, h))
        pygame.draw.rect(panel, cfg.HUD_PANEL_BORDER, (0, 0, w, h), 1)
    surface.blit(panel, (x, y))


def _health_bar_color(ratio):
    if ratio > 0.55:
        return cfg.HUD_HP_HIGH
    if ratio > 0.28:
        return cfg.HUD_HP_MID
    return cfg.HUD_HP_LOW


def _draw_health_bar(surface, x, y, w, h, cur, max_hp):
    if max_hp <= 0:
        return
    t = max(0.0, min(1.0, cur / max_hp))
    try:
        pygame.draw.rect(surface, (32, 36, 44), (x, y, w, h), border_radius=3)
        pygame.draw.rect(surface, (50, 54, 64), (x, y, w, h), 1, border_radius=3)
    except TypeError:
        pygame.draw.rect(surface, (32, 36, 44), (x, y, w, h))
        pygame.draw.rect(surface, (50, 54, 64), (x, y, w, h), 1)
    fill = int(w * t)
    if fill > 0:
        col = _health_bar_color(t)
        inner = pygame.Rect(x + 1, y + 1, fill - 2, h - 2)
        try:
            pygame.draw.rect(surface, col, inner, border_radius=2)
        except TypeError:
            pygame.draw.rect(surface, col, inner)


def _draw_stamina_bar_polished(surface, x, y, w, h, cur, max_s):
    if max_s <= 0:
        return
    t = max(0.0, min(1.0, cur / max_s))
    try:
        pygame.draw.rect(surface, (28, 30, 38), (x, y, w, h), border_radius=3)
        pygame.draw.rect(surface, (55, 60, 74), (x, y, w, h), 1, border_radius=3)
    except TypeError:
        pygame.draw.rect(surface, (28, 30, 38), (x, y, w, h))
        pygame.draw.rect(surface, (55, 60, 74), (x, y, w, h), 1)
    fill = int((w - 2) * t)
    if fill > 0:
        col = (96, 210, 155) if t > 0.22 else (230, 160, 95)
        try:
            pygame.draw.rect(surface, col, (x + 1, y + 1, fill, h - 2), border_radius=2)
        except TypeError:
            pygame.draw.rect(surface, col, (x + 1, y + 1, fill, h - 2))


def _draw_center_card(surface, screen_w, screen_h, card_w, card_h, radius=10):
    cx = (screen_w - card_w) // 2
    cy = (screen_h - card_h) // 2
    shadow = pygame.Surface((card_w + 12, card_h + 12), pygame.SRCALPHA)
    try:
        pygame.draw.rect(shadow, (0, 0, 0, 90), (6, 6, card_w, card_h), border_radius=radius)
    except TypeError:
        pygame.draw.rect(shadow, (0, 0, 0, 90), (6, 6, card_w, card_h))
    surface.blit(shadow, (cx - 4, cy - 4))
    card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
    try:
        pygame.draw.rect(card, (*cfg.UI_CARD_BG, cfg.UI_CARD_BG_ALPHA), (0, 0, card_w, card_h), border_radius=radius)
        pygame.draw.rect(card, cfg.UI_CARD_BORDER, (0, 0, card_w, card_h), 2, border_radius=radius)
    except TypeError:
        pygame.draw.rect(card, (*cfg.UI_CARD_BG, cfg.UI_CARD_BG_ALPHA), (0, 0, card_w, card_h))
        pygame.draw.rect(card, cfg.UI_CARD_BORDER, (0, 0, card_w, card_h), 2)
    surface.blit(card, (cx, cy))
    return cx, cy, card_w, card_h


def _accent_line(surface, screen_w, y):
    pygame.draw.line(
        surface,
        cfg.UI_CARD_ACCENT_LINE,
        (screen_w // 2 - 110, y),
        (screen_w // 2 + 110, y),
        2,
    )


# ---------------------------------------------------------------------------
# Combat / feedback
# ---------------------------------------------------------------------------


def draw_crosshair(surface, center_x, center_y, flash_timer):
    half = cfg.CROSSHAIR_HALF_LEN
    c = cfg.CROSSHAIR_FLASH_COLOR if flash_timer > 0 else cfg.CROSSHAIR_COLOR
    t = cfg.CROSSHAIR_THICKNESS
    pygame.draw.line(surface, c, (center_x - half, center_y), (center_x + half, center_y), t)
    pygame.draw.line(surface, c, (center_x, center_y - half), (center_x, center_y + half), t)


def draw_hit_marker(surface, cx, cy, timer, duration, is_kill=False):
    if timer <= 0 or duration <= 0:
        return
    t = min(1.0, timer / duration)
    a = max(0, min(255, int(250 * (t ** 0.5))))
    half = cfg.HIT_MARKER_HALF_EXTENT + (5 if is_kill else 0)
    tt = cfg.HIT_MARKER_THICKNESS + (1 if is_kill else 0)
    w = half * 2 + tt * 2
    s = pygame.Surface((w, w), pygame.SRCALPHA)
    col = (255, 230, 140, a) if is_kill else (255, 235, 220, a)
    pygame.draw.line(s, col, (tt, tt), (w - tt, w - tt), tt)
    pygame.draw.line(s, col, (w - tt, tt), (tt, w - tt), tt)
    if is_kill:
        pygame.draw.circle(s, (255, 235, 160, min(255, a + 20)), (w // 2, w // 2), half // 2, 1)
    surface.blit(s, (int(cx) - w // 2, int(cy) - w // 2))


def draw_damage_edge(surface, timer, w, h):
    if timer <= 0:
        return
    t = min(1.0, timer / cfg.DAMAGE_FLASH_CAP)
    a = int(120 * (t ** 0.5))
    e = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(e, (255, 90, 70, min(200, a)), (0, 0, w, h), 4)
    surface.blit(e, (0, 0))


def draw_damage_flash(surface, timer, w, h):
    if timer <= 0:
        return
    tnorm = min(1.0, timer / cfg.DAMAGE_FLASH_CAP)
    a = int(cfg.DAMAGE_FLASH_ALPHA_MAX * (tnorm ** 0.75))
    a = max(0, min(220, a))
    veil = pygame.Surface((w, h), pygame.SRCALPHA)
    veil.fill((195, 22, 38, a))
    surface.blit(veil, (0, 0))


# ---------------------------------------------------------------------------
# Minimap
# ---------------------------------------------------------------------------


def draw_minimap(
    surface,
    player_x,
    player_y,
    player_angle,
    tile_size,
    screen_w,
    enemies=None,
    player_icon=None,
    enemy_icon=None,
):
    import assets as _assets

    pl_icon = player_icon if player_icon is not None else _assets.PLAYER_MINIMAP_SPRITE
    ext = cfg.MINIMAP_HALF_EXTENT
    pmx = int(math.floor(player_x / tile_size))
    pmy = int(math.floor(player_y / tile_size))
    cols = 2 * ext + 1
    rows = cols
    cell = cfg.MINIMAP_CELL_PX
    inner_w = cols * cell
    inner_h = rows * cell
    p = cfg.MINIMAP_PAD + 4
    label_h = 22
    total_w = inner_w + p * 2
    total_h = inner_h + p * 2 + label_h

    ox = screen_w - cfg.MINIMAP_MARGIN - total_w
    oy = cfg.MINIMAP_MARGIN

    so = cfg.MINIMAP_SHADOW_OFFSET
    shadow = pygame.Surface((total_w + so, total_h + so), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 70), (so, so, total_w, total_h), border_radius=6)
    surface.blit(shadow, (ox - so + 2, oy - so + 2))

    frame = pygame.Surface((total_w, total_h), pygame.SRCALPHA)
    try:
        pygame.draw.rect(frame, (*cfg.MINIMAP_FRAME_OUTER, 255), (0, 0, total_w, total_h), border_radius=6)
        pygame.draw.rect(frame, (*cfg.MINIMAP_BG, 255), (2, 2, total_w - 4, total_h - 4), border_radius=4)
        pygame.draw.rect(frame, cfg.MINIMAP_FRAME_INNER, (2, 2, total_w - 4, total_h - 4), 1, border_radius=4)
    except TypeError:
        pygame.draw.rect(frame, (*cfg.MINIMAP_FRAME_OUTER, 255), (0, 0, total_w, total_h))
        pygame.draw.rect(frame, (*cfg.MINIMAP_BG, 255), (2, 2, total_w - 4, total_h - 4))
        pygame.draw.rect(frame, cfg.MINIMAP_FRAME_INNER, (2, 2, total_w - 4, total_h - 4), 1)
    surface.blit(frame, (ox, oy))

    fl = _font(18)
    map_lbl = fl.render("TACTICAL MAP", True, cfg.MINIMAP_LABEL)
    lr = map_lbl.get_rect(center=(ox + total_w // 2, oy + 12))
    _blit_shadow_text(surface, fl, "TACTICAL MAP", cfg.MINIMAP_LABEL, (lr.x, lr.y))

    base_x = ox + p
    base_y = oy + p + label_h

    for j in range(rows):
        my = pmy - ext + j
        for i in range(cols):
            mx = pmx - ext + i
            ch = world.sample_world_cell(mx, my)
            if world.is_walkable_cell(ch):
                if ch == "a":
                    color = cfg.MINIMAP_SIDEWALK
                elif ch == "b":
                    color = cfg.MINIMAP_LOT
                else:
                    color = cfg.MINIMAP_ROAD
            elif ch == "3":
                color = cfg.MINIMAP_COVER
            elif ch == "2":
                color = cfg.MINIMAP_BUILDING_B
            elif ch == "4":
                color = cfg.MINIMAP_PROP_CAR
            elif ch == "5":
                color = cfg.MINIMAP_PROP_CRATE
            elif ch == "6":
                color = cfg.MINIMAP_PROP_BARRIER
            elif ch == "7":
                color = cfg.MINIMAP_PROP_LAMP
            elif ch == "8":
                color = cfg.MINIMAP_PROP_DUMPSTER
            elif ch == "9":
                color = cfg.MINIMAP_PROP_PARAPET
            else:
                color = cfg.MINIMAP_WALL
            pygame.draw.rect(surface, color, (base_x + i * cell, base_y + j * cell, cell, cell))

    mx = player_x / tile_size
    my = player_y / tile_size
    plx = base_x + (mx - (pmx - ext)) * cell
    ply = base_y + (my - (pmy - ext)) * cell
    pr = pl_icon.get_rect(center=(int(plx), int(ply)))
    surface.blit(pl_icon, pr)
    dx = math.cos(player_angle) * cfg.MINIMAP_DIR_LEN
    dy = math.sin(player_angle) * cfg.MINIMAP_DIR_LEN
    pygame.draw.line(
        surface,
        cfg.MINIMAP_PLAYER,
        (int(plx), int(ply)),
        (int(plx + dx), int(ply + dy)),
        2,
    )

    if enemies:
        for e in enemies:
            emx = e.x / tile_size
            emy = e.y / tile_size
            ex = base_x + (emx - (pmx - ext)) * cell
            ey = base_y + (emy - (pmy - ext)) * cell
            col = et.get_spec(e.type_key).minimap_color
            dot_r = max(1, cell // 3)
            pygame.draw.circle(surface, col, (int(ex), int(ey)), dot_r)
            pygame.draw.circle(surface, (20, 20, 28), (int(ex), int(ey)), dot_r, 1)


# ---------------------------------------------------------------------------
# HUD
# ---------------------------------------------------------------------------


def draw_stamina_bar(surface, x, y, w, h, cur, max_s):
    _draw_stamina_bar_polished(surface, x, y, w, h, cur, max_s)


def draw_hud(
    surface,
    health,
    max_hp,
    weapon,
    enemy_count,
    ammo_cur,
    ammo_max,
    reloading,
    reload_progress,
    block_count,
    stamina_cur,
    stamina_max,
    enemies_defeated_total,
    kills_this_wave,
    wave_n,
    game_state,
):
    pw = cfg.HUD_PANEL_WIDTH
    pad = cfg.HUD_PANEL_PAD
    x0 = cfg.HUD_MARGIN_X
    y0 = cfg.HUD_MARGIN_Y
    inner_w = pw - pad * 2

    font_label = _font(cfg.HUD_FONT_TITLE)
    font_body = _font(cfg.HUD_FONT_BODY)
    font_small = _font(cfg.HUD_FONT_SMALL)

    hp_bar_h = 12
    section_gap = 10
    body_h = 392

    _draw_soft_panel(surface, x0, y0, pw, body_h, radius=cfg.HUD_CORNER_RADIUS)

    ix = x0 + pad
    iy = y0 + pad

    _blit_shadow_text(surface, font_label, "STATUS", cfg.HUD_ACCENT, (ix, iy))
    iy += 20 + cfg.HUD_LINE_SKIP

    _blit_shadow_text(
        surface,
        font_small,
        "HEALTH",
        cfg.HUD_TEXT_MUTED,
        (ix, iy),
    )
    hp_txt = f"{int(max(0, health))} / {max_hp}"
    tr = font_body.render(hp_txt, True, cfg.HUD_TEXT)
    surface.blit(tr, (ix + inner_w - tr.get_width(), iy - 2))
    iy += 22
    _draw_health_bar(surface, ix, iy, inner_w, hp_bar_h, health, max_hp)
    iy += hp_bar_h + section_gap

    # Weapon
    _blit_shadow_text(surface, font_label, "ARMAMENT", cfg.HUD_ACCENT, (ix, iy))
    iy += 22 + cfg.HUD_LINE_SKIP
    wpn_line = f"{weapon.name}"
    _blit_shadow_text(surface, font_body, wpn_line, cfg.HUD_TEXT, (ix, iy))
    if reloading:
        pct = int(round(100 * reload_progress)) if reload_progress is not None else 0
        ammo_str = f"RELOAD {pct}%"
        am_color = cfg.HUD_ACCENT_WARN
    else:
        ammo_str = f"{ammo_cur} / {ammo_max}"
        am_color = cfg.HUD_ACCENT if ammo_cur <= ammo_max * 0.25 else cfg.HUD_TEXT
    ar = font_body.render(ammo_str, True, am_color)
    surface.blit(ar, (ix + inner_w - ar.get_width(), iy))
    iy += 32
    if reloading and reload_progress is not None:
        try:
            pygame.draw.rect(surface, (30, 32, 40), (ix, iy, inner_w, 7), border_radius=2)
            pygame.draw.rect(surface, (55, 62, 78), (ix, iy, inner_w, 7), 1, border_radius=2)
        except TypeError:
            pygame.draw.rect(surface, (30, 32, 40), (ix, iy, inner_w, 7))
            pygame.draw.rect(surface, (55, 62, 78), (ix, iy, inner_w, 7), 1)
        fill = int(inner_w * reload_progress)
        if fill > 0:
            try:
                pygame.draw.rect(surface, (120, 200, 255), (ix, iy, fill, 7), border_radius=2)
            except TypeError:
                pygame.draw.rect(surface, (120, 200, 255), (ix, iy, fill, 7))
        iy += 12 + 4

    iy += section_gap - 4

    # Tactical
    _blit_shadow_text(surface, font_label, "MISSION", cfg.HUD_ACCENT, (ix, iy))
    iy += 22 + cfg.HUD_LINE_SKIP

    if game_state == "WAVE_COMPLETE":
        wave_line = f"Wave {wave_n} — standby (N next)"
        wave_color = cfg.HUD_ACCENT_WARN
    else:
        wave_line = f"Wave {wave_n}"
        wave_color = cfg.HUD_TEXT

    row1 = f"Hostiles  {enemy_count}"
    r1 = font_small.render(row1, True, cfg.HUD_TEXT)
    surface.blit(r1, (ix, iy))
    r2 = font_small.render(wave_line, True, wave_color)
    surface.blit(r2, (ix + inner_w - r2.get_width(), iy))
    iy += 22

    obj = font_small.render(cfg.OBJECTIVE_ELIMINATE, True, cfg.HUD_TEXT_DIM)
    surface.blit(obj, (ix, iy))
    iy += 22

    kill_line = f"Eliminated  {enemies_defeated_total}  ·  Wave {kills_this_wave} kills"
    kl = font_small.render(kill_line, True, cfg.HUD_TEXT_MUTED)
    surface.blit(kl, (ix, iy))
    iy += 22 + section_gap

    _blit_shadow_text(surface, font_label, "STAMINA", cfg.HUD_ACCENT, (ix, iy))
    iy += 22 + cfg.HUD_LINE_SKIP
    _draw_stamina_bar_polished(surface, ix, iy, inner_w, cfg.STAMINA_BAR_H, stamina_cur, stamina_max)
    iy += cfg.STAMINA_BAR_H + 8

    mat = f"Materials  {block_count}"
    ml = font_small.render(mat, True, cfg.HUD_TEXT_MUTED)
    surface.blit(ml, (ix, iy))


# ---------------------------------------------------------------------------
# Full-screen overlays
# ---------------------------------------------------------------------------


def draw_game_over_overlay(surface, screen_w, screen_h):
    veil = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    veil.fill((*cfg.UI_OVERLAY_DIM, cfg.UI_OVERLAY_ALPHA))
    surface.blit(veil, (0, 0))

    card_w, card_h = 560, 300
    cx, cy, _, _ = _draw_center_card(surface, screen_w, screen_h, card_w, card_h, radius=12)

    font_big = _font(cfg.UI_TITLE_MEDIUM)
    font_hint = _font(cfg.UI_HINT)
    font_tag = _font(cfg.UI_BODY)

    _accent_line(surface, screen_w, cy + 52)

    msg = "GAME OVER"
    shadow = font_big.render(msg, True, (0, 0, 0))
    fg = font_big.render(msg, True, (255, 210, 210))
    rect = fg.get_rect(center=(screen_w // 2, cy + 70))
    surface.blit(shadow, (rect.x + 3, rect.y + 3))
    surface.blit(fg, rect)

    tag = font_tag.render("Operation failed — hostiles remain in the sector.", True, cfg.HUD_TEXT_MUTED)
    tr = tag.get_rect(center=(screen_w // 2, cy + 130))
    surface.blit(tag, tr)

    hint = font_hint.render("Press  ENTER  to redeploy", True, cfg.HUD_TEXT)
    hr = hint.get_rect(center=(screen_w // 2, cy + 210))
    _blit_shadow_text(surface, font_hint, "Press  ENTER  to redeploy", cfg.HUD_TEXT, (hr.x, hr.y), off=2)


def draw_wave_complete_overlay(surface, screen_w, screen_h, wave_just_cleared, next_wave_index):
    veil = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    veil.fill((*cfg.UI_OVERLAY_DIM, cfg.UI_OVERLAY_ALPHA - 15))
    surface.blit(veil, (0, 0))

    card_w, card_h = 580, 320
    cx, cy, _, _ = _draw_center_card(surface, screen_w, screen_h, card_w, card_h, radius=12)

    font_big = _font(cfg.UI_TITLE_MEDIUM)
    font_sub = _font(cfg.UI_BODY)
    font_hint = _font(cfg.UI_HINT)

    _accent_line(surface, screen_w, cy + 52)

    title = "WAVE COMPLETE"
    shadow = font_big.render(title, True, (0, 0, 0))
    fg = font_big.render(title, True, (180, 255, 210))
    rect = fg.get_rect(center=(screen_w // 2, cy + 62))
    surface.blit(shadow, (rect.x + 3, rect.y + 3))
    surface.blit(fg, rect)

    sub = f"Sector {wave_just_cleared} cleared  ·  Next wave: {next_wave_index}"
    st = font_sub.render(sub, True, cfg.HUD_TEXT_MUTED)
    sr = st.get_rect(center=(screen_w // 2, cy + 128))
    surface.blit(st, sr)

    hint = "Press  N  to continue"
    ht = font_hint.render(hint, True, cfg.HUD_ACCENT)
    hr = ht.get_rect(center=(screen_w // 2, cy + 210))
    _blit_shadow_text(surface, font_hint, "Press  N  to continue", cfg.HUD_ACCENT, (hr.x, hr.y), off=2)


def draw_start_menu_overlay(surface, screen_w, screen_h):
    veil = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    veil.fill((*cfg.UI_OVERLAY_DIM, cfg.UI_OVERLAY_ALPHA + 25))
    surface.blit(veil, (0, 0))

    card_w, card_h = 560, 340
    cx, cy, _, _ = _draw_center_card(surface, screen_w, screen_h, card_w, card_h, radius=14)

    font_title = _font(cfg.UI_TITLE_LARGE)
    font_sub = _font(cfg.UI_BODY)
    font_hint = _font(cfg.UI_HINT)

    _accent_line(surface, screen_w, cy + 58)

    title = cfg.GAME_TITLE
    ts = font_title.render(title, True, (0, 0, 0))
    tf = font_title.render(title, True, (230, 238, 255))
    tr = tf.get_rect(center=(screen_w // 2, cy + 70))
    surface.blit(ts, (tr.x + 4, tr.y + 4))
    surface.blit(tf, tr)

    sub = cfg.GAME_SUBTITLE
    sf = font_sub.render(sub, True, cfg.HUD_TEXT_MUTED)
    sr = sf.get_rect(center=(screen_w // 2, cy + 145))
    surface.blit(sf, sr)

    hint = "Press  ENTER  to start"
    hr = font_hint.render(hint, True, cfg.HUD_TEXT)
    hrect = hr.get_rect(center=(screen_w // 2, cy + 230))
    _blit_shadow_text(surface, font_hint, "Press  ENTER  to start", cfg.HUD_TEXT, (hrect.x, hrect.y), off=2)

    esc = font_sub.render("ESC  —  exit", True, cfg.HUD_TEXT_DIM)
    er = esc.get_rect(center=(screen_w // 2, cy + 275))
    surface.blit(esc, er)


def draw_paused_overlay(surface, screen_w, screen_h):
    veil = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    veil.fill((*cfg.UI_OVERLAY_DIM, 110))
    surface.blit(veil, (0, 0))

    card_w, card_h = 420, 200
    cx, cy, _, _ = _draw_center_card(surface, screen_w, screen_h, card_w, card_h, radius=10)
    _accent_line(surface, screen_w, cy + 48)

    font_mid = _font(cfg.UI_TITLE_MEDIUM)
    font_hint = _font(cfg.UI_HINT)

    msg = "PAUSED"
    shadow = font_mid.render(msg, True, (0, 0, 0))
    fg = font_mid.render(msg, True, (240, 242, 255))
    rect = fg.get_rect(center=(screen_w // 2, screen_h // 2 - 20))
    surface.blit(shadow, (rect.x + 3, rect.y + 3))
    surface.blit(fg, rect)

    hint = font_hint.render("Press  P  to resume", True, cfg.HUD_TEXT_MUTED)
    hrect = hint.get_rect(center=(screen_w // 2, screen_h // 2 + 48))
    surface.blit(hint, hrect)
