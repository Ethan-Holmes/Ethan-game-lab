"""
Enemy archetypes: stats + art hints. Add new entries to TYPES to expand the roster.

Each type has combat numbers and visual hints. Optional PNGs in assets/enemies/ (or legacy
flat files in assets/) override placeholders. Placeholders are built at runtime if missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

# Keys used in saves and spawn logic — keep stable strings.
TYPE_GRUNT = "grunt"
TYPE_HEAVY = "heavy"
TYPE_SCOUT = "scout"


@dataclass(frozen=True)
class EnemyTypeSpec:
    """One enemy class (Grunt / Heavy / Scout / …)."""

    key: str
    label: str
    max_hp: float
    speed: float  # world pixels per second (movement)
    ranged_damage: float  # damage per shot to the player
    shoot_cooldown: float  # seconds between shots (when in ATTACKING)
    contact_dps: float  # damage per second when touching the player
    billboard_width: float  # world units (same meaning as old ENEMY_SPRITE_WIDTH)
    billboard_height: float
    minimap_color: tuple  # RGB dot on minimap
    placeholder_fill: tuple  # RGB for generated billboard if no PNG
    placeholder_edge: tuple
    # Optional: path under assets/ (e.g. "enemies/grunt.png"). None = placeholder only.
    sprite_file: str | None = None


# Baseline tuned from the original single enemy type (roughly a Grunt).
TYPES: Dict[str, EnemyTypeSpec] = {
    TYPE_GRUNT: EnemyTypeSpec(
        key=TYPE_GRUNT,
        label="Grunt",
        max_hp=100.0,
        speed=85.0,
        ranged_damage=10.0,
        shoot_cooldown=1.2,
        contact_dps=22.0,
        billboard_width=40.0,
        billboard_height=56.0,
        minimap_color=(230, 70, 70),
        placeholder_fill=(200, 60, 55),
        placeholder_edge=(90, 30, 28),
        sprite_file="enemies/grunt.png",
    ),
    TYPE_HEAVY: EnemyTypeSpec(
        key=TYPE_HEAVY,
        label="Heavy",
        max_hp=220.0,
        speed=52.0,
        ranged_damage=14.0,
        shoot_cooldown=1.45,
        contact_dps=18.0,
        billboard_width=48.0,
        billboard_height=62.0,
        minimap_color=(120, 95, 200),
        placeholder_fill=(95, 75, 175),
        placeholder_edge=(45, 35, 95),
        sprite_file="enemies/heavy.png",
    ),
    TYPE_SCOUT: EnemyTypeSpec(
        key=TYPE_SCOUT,
        label="Scout",
        max_hp=55.0,
        speed=118.0,
        ranged_damage=8.0,
        shoot_cooldown=0.95,
        contact_dps=28.0,
        billboard_width=34.0,
        billboard_height=48.0,
        minimap_color=(90, 210, 130),
        placeholder_fill=(55, 185, 115),
        placeholder_edge=(25, 95, 60),
        sprite_file="enemies/scout.png",
    ),
}

DEFAULT_TYPE_KEY = TYPE_GRUNT

# Weighted pick when spawning (higher = more common).
SPAWN_WEIGHTS: List[tuple[str, float]] = [
    (TYPE_GRUNT, 0.5),
    (TYPE_HEAVY, 0.25),
    (TYPE_SCOUT, 0.25),
]


def get_spec(type_key: str) -> EnemyTypeSpec:
    """Return the definition for type_key, falling back to Grunt if unknown."""
    return TYPES.get(type_key, TYPES[DEFAULT_TYPE_KEY])


def pick_spawn_type(rng) -> str:
    """Random type according to SPAWN_WEIGHTS."""
    total = sum(w for _, w in SPAWN_WEIGHTS)
    r = rng.uniform(0.0, total)
    acc = 0.0
    for key, w in SPAWN_WEIGHTS:
        acc += w
        if r <= acc:
            return key
    return SPAWN_WEIGHTS[-1][0]
