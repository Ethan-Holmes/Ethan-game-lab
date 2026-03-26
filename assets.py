"""
Load images and sounds from assets/. Character sprites load from assets/player/ and
assets/enemies/ with safe fallbacks. Wall placeholders are generated when PNGs are missing.
"""

import os
import random

import pygame

import settings as cfg
import sprite_loader

WALL_TEXTURES = {}
SOUND_GUNSHOT = None
SOUND_HIT = None
SOUND_AMBIENT_WIND = None
SOUND_AMBIENT_TRAFFIC = None
SOUND_AMBIENT_INDUSTRIAL = None
# Full-body player art at CHARACTER_SPRITE_BASE_SIZE (minimap scales from this).
PLAYER_CHARACTER_SPRITE = None
PLAYER_MINIMAP_SPRITE = None
# Legacy single enemy art (shared fallback).
ENEMY_BILLBOARD_SPRITE = None
# Loaded or generated once per enemy type key (grunt / heavy / scout / …).
ENEMY_BILLBOARD_BY_TYPE = {}


def _ensure_default_wall_assets(assets_dir):
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
    out = {}
    for key, fname in cfg.WALL_TEXTURE_FILES.items():
        path = os.path.join(assets_dir, fname)
        try:
            out[key] = pygame.image.load(path).convert()
        except Exception:
            out[key] = None
    # Share stone art for urban brick if the dedicated file is missing.
    if out.get("2") is None and out.get("1") is not None:
        out["2"] = out["1"]
    if out.get("3") is None and out.get("1") is not None:
        out["3"] = out["1"]
    if out.get("u") is None and out.get("3") is not None:
        out["u"] = out["3"]
    for key, fallback in (
        ("D", "2"),
        ("L", "1"),
        ("W", "3"),
        ("M", "3"),
        ("T", "3"),
        ("K", "3"),
        ("E", "1"),
        ("S", "1"),
    ):
        if out.get(key) is None and out.get(fallback) is not None:
            out[key] = out[fallback]
    return out


def _load_sfx_first_available(candidates):
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            return pygame.mixer.Sound(path)
        except Exception:
            continue
    return None


def play_sfx(sound):
    if sound is None:
        return
    sound.set_volume(max(0.0, min(1.0, cfg.SFX_VOLUME)))
    sound.play()


def _make_placeholder_sprite(size, fill_rgb, edge_rgb=None):
    w, h = size
    surf = pygame.Surface((w, h))
    surf.fill(fill_rgb)
    if edge_rgb is not None:
        pygame.draw.rect(surf, edge_rgb, (0, 0, w, h), max(1, min(w, h) // 16))
    cx, cy = w // 2, h // 3
    pygame.draw.circle(surf, (28, 32, 40), (cx, cy), max(2, min(w, h) // 8))
    return surf


def _load_image_scaled_or_placeholder(path, size, fill_rgb, edge_rgb):
    return sprite_loader.load_scaled_image_with_fallback(
        [path],
        size,
        lambda s: _make_placeholder_sprite(s, fill_rgb, edge_rgb),
        convert=True,
    )


def _make_typed_enemy_placeholder(spec, size):
    """Distinct silhouette per class when no PNG is present (beginner-friendly defaults)."""
    import enemy_types as et

    w, h = size
    surf = pygame.Surface((w, h))
    surf.fill(spec.placeholder_fill)
    pygame.draw.rect(surf, spec.placeholder_edge, (0, 0, w, h), max(2, min(w, h) // 18))

    if spec.key == et.TYPE_HEAVY:
        pygame.draw.rect(surf, (40, 40, 55), (w // 10, h // 5, w * 4 // 5, h * 3 // 5), 2)
        pygame.draw.line(surf, (60, 60, 80), (w // 4, h // 3), (w * 3 // 4, h // 3), 2)
    elif spec.key == et.TYPE_SCOUT:
        pygame.draw.rect(surf, (35, 40, 38), (w // 4, h // 6, w // 2, h * 2 // 3), 2)
        pygame.draw.rect(surf, (20, 24, 22), (w // 3, h // 3, w // 3, h // 8))
    else:
        cx, cy = w // 2, h // 3
        pygame.draw.circle(surf, (28, 32, 40), (cx, cy), max(2, min(w, h) // 7))

    return surf


# Old flat filenames in assets/ root (still tried if subfolder art is missing).
_LEGACY_ENEMY_ROOT_FILE = {
    "grunt": "enemy_grunt.png",
    "heavy": "enemy_heavy.png",
    "scout": "enemy_scout.png",
}


def _enemy_sprite_candidate_paths(assets_dir, spec):
    import enemy_types as et

    paths = []
    if spec.sprite_file:
        paths.append(sprite_loader.asset_path_from_relative(assets_dir, spec.sprite_file))
    leg = _LEGACY_ENEMY_ROOT_FILE.get(spec.key)
    if leg:
        paths.append(sprite_loader.asset_path(assets_dir, leg))
    paths.append(
        sprite_loader.asset_path(assets_dir, cfg.ENEMY_SPRITE_DIR, f"{spec.key}.png")
    )
    return paths


def _load_enemy_billboards(assets_dir):
    """Fill ENEMY_BILLBOARD_BY_TYPE from PNGs under assets/enemies/ or typed placeholders."""
    global ENEMY_BILLBOARD_BY_TYPE, ENEMY_BILLBOARD_SPRITE
    import enemy_types as et

    ENEMY_BILLBOARD_BY_TYPE = {}
    base_size = cfg.CHARACTER_SPRITE_BASE_SIZE
    for spec in et.TYPES.values():
        candidates = _enemy_sprite_candidate_paths(assets_dir, spec)
        ENEMY_BILLBOARD_BY_TYPE[spec.key] = sprite_loader.load_scaled_image_with_fallback(
            candidates,
            base_size,
            lambda s, sp=spec: _make_typed_enemy_placeholder(sp, s),
            convert=True,
        )

    fb_paths = []
    grunt_spec = et.TYPES[et.TYPE_GRUNT]
    if grunt_spec.sprite_file:
        fb_paths.append(
            sprite_loader.asset_path_from_relative(assets_dir, grunt_spec.sprite_file)
        )
    fb_paths.append(sprite_loader.asset_path(assets_dir, cfg.ENEMY_SPRITE_FILENAME))
    ENEMY_BILLBOARD_SPRITE = sprite_loader.load_scaled_image_with_fallback(
        fb_paths,
        base_size,
        lambda s: _make_placeholder_sprite(s, (210, 55, 55), (45, 15, 15)),
        convert=True,
    )


def billboard_for_enemy_type(type_key):
    """Return a billboard Surface for this type (always valid after load_all)."""
    import enemy_types as et

    s = ENEMY_BILLBOARD_BY_TYPE.get(type_key)
    if s is not None:
        return s
    return ENEMY_BILLBOARD_BY_TYPE.get(et.DEFAULT_TYPE_KEY, ENEMY_BILLBOARD_SPRITE)


def load_all(assets_dir):
    """Call once after pygame.init() and display mode are set. Fills module-level surfaces."""
    global WALL_TEXTURES, SOUND_GUNSHOT, SOUND_HIT
    global SOUND_AMBIENT_WIND, SOUND_AMBIENT_TRAFFIC, SOUND_AMBIENT_INDUSTRIAL
    global PLAYER_CHARACTER_SPRITE, PLAYER_MINIMAP_SPRITE, ENEMY_BILLBOARD_SPRITE

    _ensure_default_wall_assets(assets_dir)
    os.makedirs(sprite_loader.asset_path(assets_dir, cfg.PLAYER_SPRITE_DIR), exist_ok=True)
    os.makedirs(sprite_loader.asset_path(assets_dir, cfg.ENEMY_SPRITE_DIR), exist_ok=True)
    amb_dir = os.path.join(assets_dir, "ambient")
    try:
        os.makedirs(amb_dir, exist_ok=True)
    except OSError:
        pass
    WALL_TEXTURES = _load_wall_textures(assets_dir)
    SOUND_GUNSHOT = _load_sfx_first_available(
        [os.path.join(assets_dir, "gunshot.wav"), os.path.join(assets_dir, "gunshot.mp3")]
    )
    SOUND_HIT = _load_sfx_first_available(
        [os.path.join(assets_dir, "hit.wav"), os.path.join(assets_dir, "hit.mp3")]
    )

    SOUND_AMBIENT_WIND = _load_sfx_first_available(
        [
            os.path.join(amb_dir, "wind.wav"),
            os.path.join(amb_dir, "wind.ogg"),
            os.path.join(assets_dir, "ambient_wind.wav"),
        ]
    )
    SOUND_AMBIENT_TRAFFIC = _load_sfx_first_available(
        [
            os.path.join(amb_dir, "traffic.wav"),
            os.path.join(amb_dir, "traffic.ogg"),
            os.path.join(assets_dir, "ambient_traffic.wav"),
        ]
    )
    SOUND_AMBIENT_INDUSTRIAL = _load_sfx_first_available(
        [
            os.path.join(amb_dir, "industrial.wav"),
            os.path.join(amb_dir, "industrial.ogg"),
            os.path.join(assets_dir, "ambient_industrial.wav"),
        ]
    )

    player_paths = [
        sprite_loader.asset_path(assets_dir, cfg.PLAYER_SPRITE_DIR, name)
        for name in cfg.PLAYER_SPRITE_FILENAMES
    ]
    player_paths.append(sprite_loader.asset_path(assets_dir, cfg.PLAYER_SPRITE_FILENAME))

    base = cfg.CHARACTER_SPRITE_BASE_SIZE
    PLAYER_CHARACTER_SPRITE = sprite_loader.load_scaled_image_with_fallback(
        player_paths,
        base,
        lambda s: _make_placeholder_sprite(s, (90, 200, 120), (24, 70, 40)),
        convert=True,
    )
    mm = cfg.MINIMAP_PLAYER_ICON_SIZE
    PLAYER_MINIMAP_SPRITE = pygame.transform.smoothscale(PLAYER_CHARACTER_SPRITE, mm)
    try:
        PLAYER_MINIMAP_SPRITE = PLAYER_MINIMAP_SPRITE.convert_alpha()
    except pygame.error:
        PLAYER_MINIMAP_SPRITE = PLAYER_MINIMAP_SPRITE.convert()

    _load_enemy_billboards(assets_dir)
