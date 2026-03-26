"""
Optional looping ambient layers (wind, distant traffic, industrial hum).

Place .wav / .ogg files under assets/ambient/ (see assets.load_all). If files are missing,
tick() is a no-op — hooks remain for later content without crashing.

Volume follows district (districts.ambient_weights) and distance to main road grid.
"""

from __future__ import annotations

import pygame

import districts
import runtime as R
import settings as cfg
import world


def _road_proximity(mx: int, my: int, rg: int) -> float:
    """1 on main thoroughfares, falling off into blocks (boosts traffic layer)."""
    if mx % rg == 0 or my % rg == 0:
        return 1.0
    dv = min(mx % rg, rg - (mx % rg))
    dh = min(my % rg, rg - (my % rg))
    d = min(dv, dh)
    return max(0.18, 1.0 - d * 0.2)


def _vol(layer: str, w: dict[str, float], road: float) -> float:
    if layer == "traffic":
        base = w["traffic"] * (0.28 + 0.72 * road)
    elif layer == "wind":
        base = w["wind"] * (0.5 + 0.5 * (1.0 - road * 0.45))
    else:
        base = w["industrial"] * (0.55 + 0.45 * (1.0 - road * 0.25))
    return max(0.0, min(1.0, base * cfg.AMBIENT_MASTER_VOLUME))


def init_channels() -> None:
    """Reserve mixer channels for ambient loops (safe to call once after pygame.mixer.init)."""
    try:
        n = pygame.mixer.get_num_channels()
        if n < 28:
            pygame.mixer.set_num_channels(32)
    except pygame.error:
        pass
    global _ch_wind, _ch_traffic, _ch_industrial
    _ch_wind = pygame.mixer.Channel(24)
    _ch_traffic = pygame.mixer.Channel(25)
    _ch_industrial = pygame.mixer.Channel(26)


_ch_wind = None
_ch_traffic = None
_ch_industrial = None


def _apply_loop(ch, sound, vol: float) -> None:
    if ch is None or sound is None:
        return
    if vol < 0.03:
        if ch.get_busy():
            ch.stop()
        return
    if not ch.get_busy():
        ch.play(sound, loops=-1)
    ch.set_volume(vol)


def tick(dt: float, sound_wind, sound_traffic, sound_industrial) -> None:
    """Update district label + ambient volumes (call from main loop while PLAYING)."""
    if R.game_state != R.STATE_PLAYING:
        R.ambient_zone_label = ""
        for ch in (_ch_wind, _ch_traffic, _ch_industrial):
            if ch is not None and ch.get_busy():
                ch.stop()
        return

    mx, my = world.world_pos_to_grid(R.player_x, R.player_y, cfg.TILE_SIZE)
    rg = cfg.URBAN_ROAD_SPACING
    bx, by = mx // rg, my // rg
    dist = districts.district_type_at_block(bx, by, int(R.world_gen_seed))
    R.ambient_zone_label = districts.display_name(dist)
    w = districts.ambient_weights(dist)
    road = _road_proximity(mx, my, rg)

    _apply_loop(_ch_wind, sound_wind, _vol("wind", w, road))
    _apply_loop(_ch_traffic, sound_traffic, _vol("traffic", w, road))
    _apply_loop(_ch_industrial, sound_industrial, _vol("industrial", w, road))
