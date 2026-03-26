"""
2D overlays: HUD, minimap, crosshair, menus, pause screen.

Visual style: dark panels, soft shadows, accent highlights — tuned via settings.
"""

import math

import pygame

import enemy_types as et
import runtime as R
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


def _accent_line(surface, screen_w, y, half_w=120):
    pygame.draw.line(
        surface,
        cfg.UI_CARD_ACCENT_LINE,
        (screen_w // 2 - half_w, y),
        (screen_w // 2 + half_w, y),
        2,
    )


def _hud_divider(surface, x, y, w):
    pygame.draw.line(surface, cfg.HUD_DIVIDER, (x, y), (x + w, y), 1)


def _hud_section_title(surface, font, text, x, y):
    surface.blit(font.render(text, True, cfg.HUD_SECTION_LABEL), (x, y))


def _blit_right(surface, font, text, color, right_x, y):
    s = font.render(text, True, color)
    surface.blit(s, (right_x - s.get_width(), y))


def _overlay_card_top_strip(surface, cx, cy, card_w, color, h=4):
    try:
        pygame.draw.rect(surface, color, (cx + 3, cy + 3, card_w - 6, h), border_radius=2)
    except TypeError:
        pygame.draw.rect(surface, color, (cx + 3, cy + 3, card_w - 6, h))


def _wrap_lines(text, font, max_w, max_lines=4):
    """Simple word-wrap for overlay subtitles."""
    if not text:
        return []
    words = text.split()
    if not words:
        return []
    lines = []
    cur = words[0]
    for w in words[1:]:
        test = f"{cur} {w}"
        if font.size(test)[0] <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
    if len(lines) < max_lines:
        lines.append(cur)
    return lines[:max_lines]


# ---------------------------------------------------------------------------
# Combat / feedback
# ---------------------------------------------------------------------------


def draw_crosshair(surface, center_x, center_y, flash_timer, low_ammo=False):
    half = cfg.CROSSHAIR_HALF_LEN
    if flash_timer > 0:
        c = cfg.CROSSHAIR_FLASH_COLOR
    elif low_ammo:
        c = cfg.CROSSHAIR_LOW_AMMO_COLOR
        half = int(round(half * 1.18))
    else:
        c = cfg.CROSSHAIR_COLOR
    t = cfg.CROSSHAIR_THICKNESS + (1 if low_ammo and flash_timer <= 0 else 0)
    pygame.draw.line(surface, c, (center_x - half, center_y), (center_x + half, center_y), t)
    pygame.draw.line(surface, c, (center_x, center_y - half), (center_x, center_y + half), t)
    if low_ammo and flash_timer <= 0:
        br = half + 7
        tick = 5
        cc = (min(255, c[0] + 25), min(255, c[1] + 15), c[2])
        pygame.draw.line(surface, cc, (center_x - br, center_y - br), (center_x - br + tick, center_y - br), 1)
        pygame.draw.line(surface, cc, (center_x - br, center_y - br), (center_x - br, center_y - br + tick), 1)
        pygame.draw.line(surface, cc, (center_x + br, center_y - br), (center_x + br - tick, center_y - br), 1)
        pygame.draw.line(surface, cc, (center_x + br, center_y - br), (center_x + br, center_y - br + tick), 1)
        pygame.draw.line(surface, cc, (center_x - br, center_y + br), (center_x - br + tick, center_y + br), 1)
        pygame.draw.line(surface, cc, (center_x - br, center_y + br), (center_x - br, center_y + br - tick), 1)
        pygame.draw.line(surface, cc, (center_x + br, center_y + br), (center_x + br - tick, center_y + br), 1)
        pygame.draw.line(surface, cc, (center_x + br, center_y + br), (center_x + br, center_y + br - tick), 1)


def draw_hit_marker(surface, cx, cy, timer, duration, is_kill=False):
    if timer <= 0 or duration <= 0:
        return
    t = min(1.0, timer / duration)
    a = max(0, min(255, int(250 * (t ** 0.5))))
    half = cfg.HIT_MARKER_HALF_EXTENT + (7 if is_kill else 0)
    tt = cfg.HIT_MARKER_THICKNESS + (2 if is_kill else 1)
    w = half * 2 + tt * 2
    s = pygame.Surface((w, w), pygame.SRCALPHA)
    col = (255, 220, 110, a) if is_kill else (255, 120, 95, a)
    glow = (255, 255, 255, min(200, a + 30)) if is_kill else (255, 200, 170, min(160, a))
    pygame.draw.line(s, glow, (tt, tt), (w - tt, w - tt), tt + 2)
    pygame.draw.line(s, glow, (w - tt, tt), (tt, w - tt), tt + 2)
    pygame.draw.line(s, col, (tt, tt), (w - tt, w - tt), tt)
    pygame.draw.line(s, col, (w - tt, tt), (tt, w - tt), tt)
    if is_kill:
        pygame.draw.circle(s, (255, 210, 90, min(255, a + 35)), (w // 2, w // 2), half // 2 + 2, 2)
        pygame.draw.circle(s, (255, 255, 230, min(255, a + 15)), (w // 2, w // 2), half // 2, 1)
    else:
        pygame.draw.circle(s, (255, 150, 120, min(120, a // 2)), (w // 2, w // 2), half // 3, 1)
    surface.blit(s, (int(cx) - w // 2, int(cy) - w // 2))


def draw_weapon_switch_banner(surface, screen_w, screen_h, weapon_name, timer, duration):
    if timer <= 0 or duration <= 0:
        return
    u = timer / duration
    a = int(215 * (u ** 0.5))
    if a < 10:
        return
    font = _font(26)
    text = weapon_name.upper()
    tw, th = font.size(text)
    pad_x, pad_y = 18, 10
    bw, bh = tw + pad_x * 2, th + pad_y * 2
    bx = (screen_w - bw) // 2
    by = int(screen_h * 0.72)
    panel = pygame.Surface((bw, bh), pygame.SRCALPHA)
    try:
        pygame.draw.rect(panel, (18, 22, 32, min(220, a)), (0, 0, bw, bh), border_radius=8)
        pygame.draw.rect(panel, (*cfg.HUD_ACCENT, min(200, a)), (0, 0, bw, bh), 2, border_radius=8)
    except TypeError:
        pygame.draw.rect(panel, (18, 22, 32), (0, 0, bw, bh))
        pygame.draw.rect(panel, cfg.HUD_ACCENT, (0, 0, bw, bh), 2)
    surface.blit(panel, (bx, by))
    fg = font.render(text, True, cfg.HUD_TEXT)
    shadow = font.render(text, True, (0, 0, 0))
    surface.blit(shadow, (bx + pad_x + 1, by + pad_y + 1))
    surface.blit(fg, (bx + pad_x, by + pad_y))


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
    objective_world=None,
    district_label="",
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
    pad = cfg.MINIMAP_PAD + 2
    label_h = 46 if district_label else 30
    total_w = inner_w + pad * 2
    total_h = inner_h + pad * 2 + label_h

    ox = screen_w - cfg.MINIMAP_MARGIN - total_w
    oy = cfg.MINIMAP_MARGIN

    so = cfg.MINIMAP_SHADOW_OFFSET
    shadow = pygame.Surface((total_w + so, total_h + so), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 82), (so, so, total_w, total_h), border_radius=8)
    surface.blit(shadow, (ox - so + 2, oy - so + 2))

    frame = pygame.Surface((total_w, total_h), pygame.SRCALPHA)
    try:
        pygame.draw.rect(frame, (*cfg.MINIMAP_FRAME_OUTER, 255), (0, 0, total_w, total_h), border_radius=8)
        pygame.draw.rect(frame, (*cfg.MINIMAP_BG, 255), (3, 3, total_w - 6, total_h - 6), border_radius=6)
        pygame.draw.rect(frame, cfg.MINIMAP_FRAME_INNER, (3, 3, total_w - 6, total_h - 6), 1, border_radius=6)
    except TypeError:
        pygame.draw.rect(frame, (*cfg.MINIMAP_FRAME_OUTER, 255), (0, 0, total_w, total_h))
        pygame.draw.rect(frame, (*cfg.MINIMAP_BG, 255), (3, 3, total_w - 6, total_h - 6))
        pygame.draw.rect(frame, cfg.MINIMAP_FRAME_INNER, (3, 3, total_w - 6, total_h - 6), 1)
    surface.blit(frame, (ox, oy))

    fl = _font(19)
    fs = _font(15)
    title_x = ox + 14
    title_y = oy + 10
    pygame.draw.rect(surface, cfg.HUD_ACCENT, (title_x, title_y + 2, 3, 18), border_radius=1)
    _blit_shadow_text(surface, fl, "Map", cfg.MINIMAP_LABEL, (title_x + 10, title_y), off=1)
    if district_label:
        dl = fs.render(district_label[:44], True, cfg.HUD_TEXT_MUTED)
        surface.blit(dl, (title_x + 10, title_y + 22))
    else:
        dl = fs.render("Local area", True, cfg.HUD_TEXT_DIM)
        surface.blit(dl, (title_x + 10, title_y + 22))

    base_x = ox + pad
    base_y = oy + pad + label_h

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
                elif ch == "P":
                    color = cfg.MINIMAP_PLAZA
                elif ch == "f":
                    color = cfg.MINIMAP_YARD
                else:
                    color = cfg.MINIMAP_ROAD
            elif ch == "3":
                color = cfg.MINIMAP_COVER
            elif ch == "2":
                color = cfg.MINIMAP_BUILDING_B
            elif ch == "D":
                color = cfg.MINIMAP_DOWNTOWN
            elif ch == "L":
                color = cfg.MINIMAP_RESIDENTIAL
            elif ch == "W":
                color = cfg.MINIMAP_WAREHOUSE
            elif ch == "M":
                color = cfg.MINIMAP_INDUSTRIAL_M
            elif ch in ("T", "K", "S"):
                color = cfg.MINIMAP_LANDMARK
            elif ch == "E":
                color = cfg.MINIMAP_FENCE
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
            elif ch == "u":
                color = cfg.MINIMAP_PROP_UTILITY
            elif ch == "9":
                color = cfg.MINIMAP_PROP_PARAPET
            else:
                color = cfg.MINIMAP_WALL
            pygame.draw.rect(surface, color, (base_x + i * cell, base_y + j * cell, cell, cell))

    try:
        pygame.draw.rect(
            surface,
            cfg.MINIMAP_GRID_BORDER,
            (base_x - 1, base_y - 1, inner_w + 2, inner_h + 2),
            1,
            border_radius=2,
        )
    except TypeError:
        pygame.draw.rect(
            surface,
            cfg.MINIMAP_GRID_BORDER,
            (base_x - 1, base_y - 1, inner_w + 2, inner_h + 2),
            1,
        )

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
            if getattr(e, "is_elite", False):
                pygame.draw.circle(surface, (255, 210, 120), (int(ex), int(ey)), dot_r + 3, 1)
            if getattr(e, "ai_state", 0) == cfg.ENEMY_ST_SEARCH:
                pygame.draw.circle(surface, cfg.ENEMY_SEARCH_RIM_COLOR, (int(ex), int(ey)), dot_r + 2, 1)

    for pk in R.field_pickups:
        gmx = pk.x / tile_size
        gmy = pk.y / tile_size
        pex = base_x + (gmx - (pmx - ext)) * cell
        pey = base_y + (gmy - (pmy - ext)) * cell
        col = cfg.MINIMAP_PICKUP_HEALTH if pk.kind == "health" else cfg.MINIMAP_PICKUP_STAMINA
        pygame.draw.rect(surface, col, (int(pex) - 1, int(pey) - 1, 3, 3))

    if objective_world:
        tag, owx, owy, orad = objective_world
        omx = owx / tile_size
        omy = owy / tile_size
        oqx = base_x + (omx - (pmx - ext)) * cell
        oqy = base_y + (omy - (pmy - ext)) * cell
        pr = max(2, int(orad / tile_size * cell))
        if tag == "reach":
            pts = [
                (int(oqx), int(oqy - pr)),
                (int(oqx + pr), int(oqy)),
                (int(oqx), int(oqy + pr)),
                (int(oqx - pr), int(oqy)),
            ]
            pygame.draw.polygon(surface, cfg.MINIMAP_OBJECTIVE_RALLY, pts, 0)
            pygame.draw.polygon(surface, (42, 32, 12), pts, 1)
        else:
            pygame.draw.circle(surface, cfg.MINIMAP_OBJECTIVE_ZONE, (int(oqx), int(oqy)), max(3, pr), 2)


def draw_objective_intro_banner(surface, screen_w, screen_h, title, detail):
    """Short mission card when a wave / objective starts."""
    if not title:
        return
    font_tag = _font(17)
    font_t = _font(26)
    font_d = _font(19)
    tw = max(font_t.size(title)[0], font_d.size(detail or "")[0], font_tag.size("Objective update")[0]) + 56
    th = 96
    bx = (screen_w - tw) // 2
    by = int(screen_h * 0.13)
    panel = pygame.Surface((tw, th), pygame.SRCALPHA)
    try:
        pygame.draw.rect(panel, (14, 16, 24, 238), (0, 0, tw, th), border_radius=10)
        pygame.draw.rect(panel, (*cfg.HUD_ACCENT, 200), (0, 0, tw, th), 1, border_radius=10)
        pygame.draw.rect(panel, cfg.HUD_ACCENT, (4, 4, 3, th - 8), border_radius=1)
    except TypeError:
        pygame.draw.rect(panel, (14, 16, 24), (0, 0, tw, th))
        pygame.draw.rect(panel, cfg.HUD_ACCENT, (0, 0, tw, th), 1)
    surface.blit(panel, (bx, by))
    _blit_shadow_text(surface, font_tag, "Objective update", cfg.HUD_SECTION_LABEL, (bx + 22, by + 10), off=1)
    _blit_shadow_text(surface, font_t, title, cfg.HUD_TEXT, (bx + 22, by + 34), off=1)
    if detail:
        _blit_shadow_text(surface, font_d, detail[:72], cfg.HUD_TEXT_MUTED, (bx + 22, by + 64), off=1)


# ---------------------------------------------------------------------------
# HUD
# ---------------------------------------------------------------------------


def draw_stamina_bar(surface, x, y, w, h, cur, max_s):
    _draw_stamina_bar_polished(surface, x, y, w, h, cur, max_s)


def draw_placement_preview(
    surface,
    preview,
    px,
    py,
    yaw,
    ray_hits,
    screen_w,
    screen_h,
    fov,
    pitch_offset_px,
    horizon_skew_px,
    tile_size,
):
    """Ghost tile at projected placement cell; green/orange/red by validity (see world.get_placement_preview)."""
    if not preview:
        return
    layout_ok = preview.get("layout_ok")
    affordable = preview.get("affordable", False)
    cx = preview.get("cx")
    cy = preview.get("cy")

    if layout_ok and cx is not None and cy is not None:
        wx = (cx + 0.5) * tile_size
        wy = (cy + 0.5) * tile_size
        pr = world.project_world_point_to_screen(
            px, py, wx, wy, yaw, ray_hits, screen_w, screen_h, fov, pitch_offset_px, horizon_skew_px
        )
        if pr is None:
            return
        sx, hy, dist = pr
        proj_plane = (screen_w / 2) / math.tan(fov / 2)
        w = max(10, min(220, int(tile_size * proj_plane / max(dist, 1.0))))
        fy = hy + min(int(w * 0.42), screen_h // 3)
        x0 = sx - w // 2
        if affordable:
            col = cfg.PLACEMENT_PREVIEW_VALID
        else:
            col = cfg.HUD_ACCENT_WARN
        try:
            pygame.draw.rect(surface, col, (x0, fy, w, max(6, w // 3)), 3, border_radius=2)
        except TypeError:
            pygame.draw.rect(surface, col, (x0, fy, w, max(6, w // 3)), 3)
        return

    # Invalid layout — subtle center cue
    cx_c = screen_w // 2
    cy_c = screen_h // 2 + 120
    try:
        pygame.draw.circle(surface, cfg.PLACEMENT_PREVIEW_INVALID, (cx_c, cy_c), 6, 2)
    except TypeError:
        pygame.draw.circle(surface, cfg.PLACEMENT_PREVIEW_INVALID, (cx_c, cy_c), 6)


def draw_construction_hint(surface, screen_w, screen_h):
    """First-wave tip: building matters; dismiss with H or by placing/breaking."""
    import time

    if R.construction_hint_dismissed:
        return
    if time.monotonic() >= R.construction_hint_until_monotonic:
        return

    bar_h = 86
    veil = pygame.Surface((screen_w, bar_h), pygame.SRCALPHA)
    veil.fill((*cfg.UI_OVERLAY_DIM, 188))
    surface.blit(veil, (0, screen_h - bar_h - 8))
    try:
        pygame.draw.line(
            surface,
            cfg.HUD_ACCENT_BUILD,
            (20, screen_h - bar_h - 4),
            (screen_w - 20, screen_h - bar_h - 4),
            1,
        )
    except TypeError:
        pass

    font = _font(20)
    font_m = _font(16)
    y = screen_h - bar_h + 8
    t1 = font.render("Build", True, cfg.HUD_ACCENT_BUILD)
    t2 = font.render(" — walls from kills and wave clears.", True, cfg.HUD_TEXT_MUTED)
    surface.blit(t1, (28, y))
    surface.blit(t2, (28 + t1.get_width(), y))
    _blit_shadow_text(
        surface,
        font_m,
        "Right-click place · F demolish · H dismiss",
        cfg.HUD_TEXT_DIM,
        (28, y + 28),
        off=1,
    )


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
    block_max,
    stamina_cur,
    stamina_max,
    enemies_defeated_total,
    kills_this_wave,
    wave_n,
    game_state,
    demolish_cooldown_ratio,
    mission_title="",
    mission_detail="",
    mission_progress=None,
    weapon_unlocks=(True, True, True),
    career_line="",
):
    pw = cfg.HUD_PANEL_WIDTH
    pad = cfg.HUD_PANEL_PAD
    x0 = cfg.HUD_MARGIN_X
    y0 = cfg.HUD_MARGIN_Y
    inner_w = pw - pad * 2

    font_sec = _font(cfg.HUD_FONT_TITLE)
    font_body = _font(cfg.HUD_FONT_BODY)
    font_small = _font(cfg.HUD_FONT_SMALL)
    font_micro = _font(cfg.HUD_FONT_MICRO)

    hp_bar_h = 11
    gap_after_div = 12
    body_h = 568 if career_line else 548

    _draw_soft_panel(surface, x0, y0, pw, body_h, radius=cfg.HUD_CORNER_RADIUS)

    ix = x0 + pad
    iy = y0 + pad

    # --- Health ---
    _hud_section_title(surface, font_sec, "Health", ix, iy)
    hp_txt = f"{int(max(0, health))} / {max_hp}"
    _blit_right(surface, font_body, hp_txt, cfg.HUD_TEXT, ix + inner_w, iy)
    iy += 22
    _draw_health_bar(surface, ix, iy, inner_w, hp_bar_h, health, max_hp)
    iy += hp_bar_h + gap_after_div
    _hud_divider(surface, ix, iy, inner_w)
    iy += 10

    # --- Loadout ---
    _hud_section_title(surface, font_sec, "Loadout", ix, iy)
    iy += 22
    wpn_line = weapon.name
    _blit_shadow_text(surface, font_body, wpn_line, cfg.HUD_TEXT, (ix, iy))
    if reloading:
        pct = int(round(100 * reload_progress)) if reload_progress is not None else 0
        ammo_str = f"Reload {pct}%"
        am_color = cfg.HUD_ACCENT_WARN
    else:
        ammo_str = f"{ammo_cur} / {ammo_max}"
        low_mag = ammo_max > 0 and ammo_cur <= max(1, int(ammo_max * 0.25))
        am_color = cfg.HUD_ACCENT_WARN if low_mag else cfg.HUD_TEXT
    _blit_right(surface, font_body, ammo_str, am_color, ix + inner_w, iy)
    iy += 30
    if reloading and reload_progress is not None:
        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.01)
        rim = (int(55 + 100 * pulse), int(130 + 90 * pulse), 255)
        try:
            pygame.draw.rect(surface, rim, (ix - 1, iy - 2, inner_w + 2, 11), 1, border_radius=3)
            pygame.draw.rect(surface, (30, 32, 40), (ix, iy, inner_w, 7), border_radius=2)
            pygame.draw.rect(surface, (55, 62, 78), (ix, iy, inner_w, 7), 1, border_radius=2)
        except TypeError:
            pygame.draw.rect(surface, rim, (ix - 1, iy - 2, inner_w + 2, 11), 1)
            pygame.draw.rect(surface, (30, 32, 40), (ix, iy, inner_w, 7))
            pygame.draw.rect(surface, (55, 62, 78), (ix, iy, inner_w, 7), 1)
        fill = int(inner_w * reload_progress)
        if fill > 0:
            hi = (int(100 + 80 * pulse), int(200 + 55 * pulse), 255)
            try:
                pygame.draw.rect(surface, hi, (ix, iy, fill, 7), border_radius=2)
            except TypeError:
                pygame.draw.rect(surface, hi, (ix, iy, fill, 7))
        iy += 16

    u1, u2, u3 = weapon_unlocks
    slot_txt = (
        ("1●" if u1 else "1○")
        + "  "
        + ("2●" if u2 else "2○")
        + "  "
        + ("3●" if u3 else "3○")
    )
    scol = cfg.HUD_TEXT_MUTED
    sl = font_micro.render(slot_txt, True, scol)
    surface.blit(sl, (ix, iy))
    iy += gap_after_div - 2
    _hud_divider(surface, ix, iy, inner_w)
    iy += 10

    # --- Engagement & objective ---
    _hud_section_title(surface, font_sec, "Engagement", ix, iy)
    iy += 22
    if game_state == "WAVE_COMPLETE":
        wave_line = f"Wave {wave_n} · standby — press N"
        wave_color = cfg.HUD_ACCENT_WARN
    else:
        wave_line = f"Wave {wave_n}"
        wave_color = cfg.HUD_TEXT
    wl = font_small.render(wave_line, True, wave_color)
    surface.blit(wl, (ix, iy))
    ec = str(enemy_count)
    num = font_body.render(ec, True, cfg.HUD_TEXT)
    suf = font_micro.render(" hostiles", True, cfg.HUD_TEXT_MUTED)
    tw = num.get_width() + suf.get_width()
    surface.blit(num, (ix + inner_w - tw, iy))
    surface.blit(suf, (ix + inner_w - tw + num.get_width(), iy + 3))
    iy += 26

    mt = mission_title or cfg.OBJECTIVE_ELIMINATE
    _blit_shadow_text(surface, font_small, "Objective", cfg.HUD_TEXT_MUTED, (ix, iy))
    iy += 20
    _blit_shadow_text(surface, font_body, mt, cfg.HUD_ACCENT, (ix, iy))
    iy += 28
    md = mission_detail or ""
    if md:
        sec_col = cfg.HUD_TEXT if mission_progress is None or mission_progress >= 0.999 else cfg.HUD_TEXT_MUTED
        _blit_shadow_text(surface, font_small, md[:58], sec_col, (ix, iy))
        iy += 22
    if mission_progress is not None:
        prog = max(0.0, min(1.0, float(mission_progress)))
        bar_y = iy
        try:
            pygame.draw.rect(surface, (26, 28, 36), (ix, bar_y, inner_w, 7), border_radius=2)
            pygame.draw.rect(surface, (44, 50, 62), (ix, bar_y, inner_w, 7), 1, border_radius=2)
        except TypeError:
            pygame.draw.rect(surface, (26, 28, 36), (ix, bar_y, inner_w, 7))
            pygame.draw.rect(surface, (44, 50, 62), (ix, bar_y, inner_w, 7), 1)
        fill = int(inner_w * prog)
        if fill > 0:
            try:
                pygame.draw.rect(surface, cfg.HUD_ACCENT, (ix, bar_y, fill, 7), border_radius=2)
            except TypeError:
                pygame.draw.rect(surface, cfg.HUD_ACCENT, (ix, bar_y, fill, 7))
        iy += 12

    kill_line = f"Eliminated {enemies_defeated_total} · {kills_this_wave} this wave"
    kl = font_micro.render(kill_line, True, cfg.HUD_TEXT_DIM)
    surface.blit(kl, (ix, iy))
    iy += 20 + gap_after_div
    _hud_divider(surface, ix, iy, inner_w)
    iy += 10

    # --- Build ---
    _hud_section_title(surface, font_sec, "Build", ix, iy)
    iy += 22
    _blit_shadow_text(surface, font_small, "Blocks", cfg.HUD_TEXT_MUTED, (ix, iy))
    _blit_right(surface, font_body, f"{block_count} / {block_max}", cfg.HUD_TEXT, ix + inner_w, iy)
    iy += 24
    if demolish_cooldown_ratio <= 0.02:
        demo_txt = "Demolish ready"
        demo_col = cfg.HUD_ACCENT_BUILD
    else:
        demo_txt = f"Demolish {int((1.0 - demolish_cooldown_ratio) * 100)}%"
        demo_col = cfg.HUD_TEXT_DIM
    _blit_shadow_text(surface, font_small, demo_txt, demo_col, (ix, iy))
    iy += 22
    _blit_shadow_text(
        surface,
        font_micro,
        "Right-click place · F demolish",
        cfg.HUD_TEXT_DIM,
        (ix, iy),
    )
    iy += 18 + gap_after_div
    _hud_divider(surface, ix, iy, inner_w)
    iy += 10

    # --- Stamina ---
    _hud_section_title(surface, font_sec, "Stamina", ix, iy)
    iy += 22
    _draw_stamina_bar_polished(surface, ix, iy, inner_w, cfg.STAMINA_BAR_H, stamina_cur, stamina_max)
    iy += cfg.STAMINA_BAR_H + 8
    if career_line:
        _hud_divider(surface, ix, iy, inner_w)
        iy += 8
        _blit_shadow_text(surface, font_micro, career_line[:52], cfg.HUD_TEXT_DIM, (ix, iy), off=1)


# ---------------------------------------------------------------------------
# Full-screen overlays
# ---------------------------------------------------------------------------


def draw_game_over_overlay(surface, screen_w, screen_h, career_line=""):
    veil = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    veil.fill((*cfg.UI_OVERLAY_DIM, cfg.UI_OVERLAY_ALPHA + 8))
    surface.blit(veil, (0, 0))

    card_w, card_h = 560, 312
    cx, cy, _, _ = _draw_center_card(surface, screen_w, screen_h, card_w, card_h, radius=12)
    _overlay_card_top_strip(surface, cx, cy, card_w, (255, 110, 110), h=4)

    font_big = _font(cfg.UI_TITLE_MEDIUM)
    font_hint = _font(cfg.UI_HINT)
    font_tag = _font(cfg.UI_BODY - 2)
    font_micro = _font(cfg.HUD_FONT_MICRO)

    msg = "Game over"
    shadow = font_big.render(msg, True, (0, 0, 0))
    fg = font_big.render(msg, True, (255, 218, 218))
    rect = fg.get_rect(center=(screen_w // 2, cy + 72))
    surface.blit(shadow, (rect.x + 3, rect.y + 3))
    surface.blit(fg, rect)

    tag = font_tag.render("Sector not cleared — hostiles remain.", True, cfg.HUD_TEXT_MUTED)
    tr = tag.get_rect(center=(screen_w // 2, cy + 128))
    surface.blit(tag, tr)

    sub = font_micro.render("You can redeploy and try again.", True, cfg.HUD_TEXT_DIM)
    sr = sub.get_rect(center=(screen_w // 2, cy + 158))
    surface.blit(sub, sr)

    if career_line:
        cr = font_micro.render(career_line[:64], True, cfg.HUD_SECTION_LABEL)
        crr = cr.get_rect(center=(screen_w // 2, cy + 198))
        surface.blit(cr, crr)

    hint = font_hint.render("Enter — redeploy", True, cfg.HUD_TEXT)
    hy = cy + 238 if career_line else cy + 228
    hr = hint.get_rect(center=(screen_w // 2, hy))
    _blit_shadow_text(surface, font_hint, "Enter — redeploy", cfg.HUD_TEXT, (hr.x, hr.y), off=2)
    qgo = font_micro.render("Esc or Q — quit to desktop", True, cfg.HUD_TEXT_DIM)
    surface.blit(qgo, qgo.get_rect(center=(screen_w // 2, hy + 30)))


def draw_wave_complete_overlay(
    surface,
    screen_w,
    screen_h,
    wave_just_cleared,
    next_wave_index,
    objective_subtitle="",
    reward_lines=None,
):
    veil = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    veil.fill((*cfg.UI_OVERLAY_DIM, cfg.UI_OVERLAY_ALPHA - 5))
    surface.blit(veil, (0, 0))

    reward_lines = reward_lines or []
    base_h = 340
    extra = min(len(reward_lines), 6) * 22 + (36 if reward_lines else 0)
    card_w, card_h = 600, min(540, base_h + extra)
    cx, cy, _, _ = _draw_center_card(surface, screen_w, screen_h, card_w, card_h, radius=12)
    _overlay_card_top_strip(surface, cx, cy, card_w, (120, 220, 170), h=4)

    font_big = _font(cfg.UI_TITLE_MEDIUM)
    font_sub = _font(cfg.UI_BODY - 1)
    font_hint = _font(cfg.UI_HINT)

    title = "Wave complete"
    shadow = font_big.render(title, True, (0, 0, 0))
    fg = font_big.render(title, True, (190, 255, 215))
    rect = fg.get_rect(center=(screen_w // 2, cy + 68))
    surface.blit(shadow, (rect.x + 3, rect.y + 3))
    surface.blit(fg, rect)

    sub_a = objective_subtitle or "Objective complete"
    lines = [
        sub_a,
        f"Sector {wave_just_cleared} cleared",
        f"Next wave: {next_wave_index}",
    ]
    y = cy + 118
    max_w = card_w - 72
    for line in lines:
        for wl in _wrap_lines(line, font_sub, max_w, max_lines=2):
            st = font_sub.render(wl, True, cfg.HUD_TEXT_MUTED)
            sr = st.get_rect(center=(screen_w // 2, y))
            surface.blit(st, sr)
            y += 26
        y += 4

    if reward_lines:
        y += 6
        _accent_line(surface, screen_w, y, half_w=min(140, card_w // 2 - 20))
        y += 16
        font_prog = _font(cfg.HUD_FONT_TITLE)
        surface.blit(font_prog.render("Progress", True, cfg.HUD_ACCENT_BUILD), (cx + 36, y))
        y += 24
        font_rw = _font(cfg.HUD_FONT_SMALL)
        for line in reward_lines[:6]:
            for wl in _wrap_lines(str(line), font_rw, card_w - 88, max_lines=2):
                t = font_rw.render(wl, True, cfg.HUD_TEXT)
                surface.blit(t, (cx + 40, y))
                y += 22
            y += 2

    hint_y = cy + card_h - 58
    hint = font_hint.render("N — continue", True, cfg.HUD_ACCENT)
    hr = hint.get_rect(center=(screen_w // 2, hint_y))
    _blit_shadow_text(surface, font_hint, "N — continue", cfg.HUD_ACCENT, (hr.x, hr.y), off=2)
    fm = _font(cfg.HUD_FONT_MICRO)
    qtxt = fm.render("Esc or Q — quit to desktop", True, cfg.HUD_TEXT_DIM)
    surface.blit(qtxt, qtxt.get_rect(center=(screen_w // 2, hint_y + 28)))


def draw_start_menu_overlay(surface, screen_w, screen_h, career_line=""):
    veil = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    veil.fill((*cfg.UI_OVERLAY_DIM, cfg.UI_OVERLAY_ALPHA + 20))
    surface.blit(veil, (0, 0))

    card_w, card_h = 700, 492
    cx, cy, _, _ = _draw_center_card(surface, screen_w, screen_h, card_w, card_h, radius=14)
    _overlay_card_top_strip(surface, cx, cy, card_w, cfg.HUD_ACCENT, h=4)

    font_title = _font(cfg.UI_TITLE_LARGE - 6)
    font_sub = _font(cfg.UI_BODY)
    font_hint = _font(cfg.UI_HINT - 2)
    font_ctrl = _font(20)
    font_head = _font(cfg.HUD_FONT_TITLE)

    title = cfg.GAME_TITLE
    ts = font_title.render(title, True, (0, 0, 0))
    tf = font_title.render(title, True, (230, 238, 255))
    tr = tf.get_rect(center=(screen_w // 2, cy + 64))
    surface.blit(ts, (tr.x + 4, tr.y + 4))
    surface.blit(tf, tr)

    sub = cfg.GAME_SUBTITLE
    sf = font_sub.render(sub, True, cfg.HUD_TEXT_MUTED)
    sr = sf.get_rect(center=(screen_w // 2, cy + 124))
    surface.blit(sf, sr)

    if career_line:
        cf = _font(cfg.HUD_FONT_MICRO)
        cl = cf.render(career_line[:70], True, cfg.HUD_SECTION_LABEL)
        clr = cl.get_rect(center=(screen_w // 2, cy + 150))
        surface.blit(cl, clr)
        accent_y = cy + 168
    else:
        accent_y = cy + 148

    _accent_line(surface, screen_w, accent_y, half_w=130)

    col_l = [
        "W / S — forward / back",
        "A / D — strafe",
        "Arrows — turn",
        "Mouse — look",
        "Shift — sprint",
    ]
    col_r = [
        "Space / click — fire",
        "R — reload",
        "1 / 2 / 3 — switch weapons (unlock in career)",
        "Right-click — place wall",
        "F — demolish",
        "Packs on ground — health & stamina",
        "Esc / P — pause · F5 / F9 — save / load",
    ]
    y0 = cy + (196 if career_line else 176)
    lx = cx + 36
    rx = cx + card_w // 2 + 4
    surface.blit(font_head.render("Movement", True, cfg.HUD_SECTION_LABEL), (lx, y0 - 26))
    surface.blit(font_head.render("Combat & build", True, cfg.HUD_SECTION_LABEL), (rx, y0 - 26))

    inset_l = pygame.Surface((card_w // 2 - 44, 210), pygame.SRCALPHA)
    try:
        pygame.draw.rect(inset_l, (18, 20, 30, 120), (0, 0, inset_l.get_width(), inset_l.get_height()), border_radius=8)
        pygame.draw.rect(inset_l, (*cfg.HUD_DIVIDER, 180), (0, 0, inset_l.get_width(), inset_l.get_height()), 1, border_radius=8)
    except TypeError:
        pygame.draw.rect(inset_l, (18, 20, 30), (0, 0, inset_l.get_width(), inset_l.get_height()))
    surface.blit(inset_l, (lx - 8, y0 - 8))
    inset_r = pygame.Surface((card_w // 2 - 44, 210), pygame.SRCALPHA)
    try:
        pygame.draw.rect(inset_r, (18, 20, 30, 120), (0, 0, inset_r.get_width(), inset_r.get_height()), border_radius=8)
        pygame.draw.rect(inset_r, (*cfg.HUD_DIVIDER, 180), (0, 0, inset_r.get_width(), inset_r.get_height()), 1, border_radius=8)
    except TypeError:
        pygame.draw.rect(inset_r, (18, 20, 30), (0, 0, inset_r.get_width(), inset_r.get_height()))
    surface.blit(inset_r, (rx - 8, y0 - 8))

    for i, line in enumerate(col_l):
        _blit_shadow_text(surface, font_ctrl, line, cfg.HUD_TEXT, (lx, y0 + i * 28), off=1)
    for i, line in enumerate(col_r):
        _blit_shadow_text(surface, font_ctrl, line, cfg.HUD_TEXT, (rx, y0 + i * 28), off=1)

    cta = font_hint.render("Enter — start operation", True, cfg.HUD_ACCENT)
    crect = cta.get_rect(center=(screen_w // 2, cy + 418))
    _blit_shadow_text(surface, font_hint, "Enter — start operation", cfg.HUD_ACCENT, (crect.x, crect.y), off=2)

    esc = font_sub.render("Esc or Q — quit to desktop", True, cfg.HUD_TEXT_DIM)
    er = esc.get_rect(center=(screen_w // 2, cy + 454))
    surface.blit(esc, er)


def draw_paused_overlay(surface, screen_w, screen_h):
    veil = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    veil.fill((*cfg.UI_OVERLAY_DIM, 135))
    surface.blit(veil, (0, 0))

    card_w, card_h = 460, 228
    cx, cy, _, _ = _draw_center_card(surface, screen_w, screen_h, card_w, card_h, radius=12)
    _overlay_card_top_strip(surface, cx, cy, card_w, (140, 155, 190), h=4)

    font_mid = _font(cfg.UI_TITLE_MEDIUM - 4)
    font_hint = _font(cfg.UI_HINT)
    font_sub = _font(cfg.UI_BODY - 2)

    msg = "Paused"
    shadow = font_mid.render(msg, True, (0, 0, 0))
    fg = font_mid.render(msg, True, (240, 242, 255))
    rect = fg.get_rect(center=(screen_w // 2, cy + 72))
    surface.blit(shadow, (rect.x + 3, rect.y + 3))
    surface.blit(fg, rect)

    sub = font_sub.render("Game is frozen — safe to step away.", True, cfg.HUD_TEXT_MUTED)
    srect = sub.get_rect(center=(screen_w // 2, cy + 118))
    surface.blit(sub, srect)

    bx = cx + card_w // 2 - 10
    by = cy + 138
    pygame.draw.rect(surface, cfg.HUD_TEXT_MUTED, (bx - 28, by, 8, 32), border_radius=1)
    pygame.draw.rect(surface, cfg.HUD_TEXT_MUTED, (bx + 8, by, 8, 32), border_radius=1)

    pause_hint = "P — resume  ·  Esc — resume  ·  Q — quit"
    ph = font_hint.render(pause_hint, True, cfg.HUD_TEXT)
    hrect = ph.get_rect(center=(screen_w // 2, cy + 196))
    _blit_shadow_text(surface, font_hint, pause_hint, cfg.HUD_TEXT, (hrect.x, hrect.y), off=1)
