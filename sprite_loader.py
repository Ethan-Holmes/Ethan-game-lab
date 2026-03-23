"""
Load and scale 2D sprites safely (missing files never crash the game).

Typical use: try a few paths under assets/player/ or assets/enemies/, then fall back
to a generated placeholder Surface.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Sequence

import pygame


def asset_path(assets_root: str, *relative_parts: str) -> str:
    """Join `assets_root` with path pieces (no slashes in each piece)."""
    return os.path.join(assets_root, *relative_parts)


def asset_path_from_relative(assets_root: str, dotted_relative: str) -> str:
    """
    Turn "enemies/grunt.png" into a filesystem path under assets_root.
    Works on Windows (normalizes separators).
    """
    rel = dotted_relative.replace("\\", "/").strip("/")
    if not rel:
        return assets_root
    return os.path.join(assets_root, *rel.split("/"))


def load_scaled_image(
    path: str,
    size: tuple[int, int],
    *,
    convert: bool = True,
) -> pygame.Surface | None:
    """
    Load an image from disk and smooth-scale it to `size` (width, height).

    Returns None if the path is missing or pygame cannot load or scale the file.
    After scaling, uses convert_alpha() when possible so PNG transparency is kept.
    """
    if not path or not os.path.isfile(path):
        return None
    try:
        img = pygame.image.load(path)
    except (pygame.error, OSError):
        return None
    w, h = int(size[0]), int(size[1])
    if w < 1 or h < 1:
        return None
    if img.get_width() < 1 or img.get_height() < 1:
        return None
    try:
        scaled = pygame.transform.smoothscale(img, (w, h))
    except pygame.error:
        return None
    if not convert:
        return scaled
    try:
        return scaled.convert_alpha()
    except pygame.error:
        return scaled.convert()


def load_scaled_image_from_candidates(
    paths: Iterable[str],
    size: tuple[int, int],
    *,
    convert: bool = True,
) -> pygame.Surface | None:
    """Try each path in order; return the first successful `load_scaled_image` result."""
    for p in paths:
        surf = load_scaled_image(p, size, convert=convert)
        if surf is not None:
            return surf
    return None


def load_scaled_image_with_fallback(
    paths: Sequence[str],
    size: tuple[int, int],
    make_placeholder: Callable[[tuple[int, int]], pygame.Surface],
    *,
    convert: bool = True,
) -> pygame.Surface:
    """
    Try every path; if all fail, build a surface with `make_placeholder(size)`.

    The placeholder factory should return an RGB surface (no alpha is fine).
    """
    found = load_scaled_image_from_candidates(paths, size, convert=convert)
    if found is not None:
        return found
    ph = make_placeholder(size)
    if convert:
        try:
            return ph.convert_alpha()
        except pygame.error:
            return ph.convert()
    return ph
