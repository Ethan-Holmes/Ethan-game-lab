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
    shoot_cooldown: float  # seconds between shots (when in ATTACK)
    contact_dps: float  # damage per second when touching the player
    billboard_width: float  # world units (same meaning as old ENEMY_SPRITE_WIDTH)
    billboard_height: float
    minimap_color: tuple  # RGB dot on minimap
    placeholder_fill: tuple  # RGB for generated billboard if no PNG
    placeholder_edge: tuple
    # Warm tint added while telegraphing a ranged attack (see enemy.draw_billboards).
    attack_telegraph_rgb: tuple = (255, 95, 75)
    # Optional: path under assets/ (e.g. "enemies/grunt.png"). None = placeholder only.
    sprite_file: str | None = None
    # --- Rule-based AI (see enemy_ai.py; multipliers apply to settings.ENEMY_* ranges) ---
    prefers_patrol_when_calm: bool = True  # False = idle hold at anchor when no target
    detect_range_mult: float = 1.0
    lost_range_mult: float = 1.0
    attack_range_mult: float = 1.0
    attack_leave_range_mult: float = 1.0
    patrol_radius: float = 155.0  # max wander distance from patrol anchor
    patrol_wander_mult: float = 1.0  # scales idle/patrol turn jitter
    separation_radius: float = 92.0  # push away from allies within this distance
    separation_weight: float = 0.9  # how strongly separation steers vs goal
    attack_standoff_min_frac: float = 0.36  # of ENEMY_SHOOT_RANGE — too close → back up
    attack_standoff_max_frac: float = 0.88  # too far in attack band → inch in
    # Chase: blend perpendicular vector so scouts flank, heavies stay direct.
    chase_flank_bias: float = 0.1
    # Attack strafe angular speed multiplier (heavy = slow pressure, scout = jittery).
    attack_strafe_mult: float = 1.0
    # SEARCH state duration multiplier (heavy persists, scout gives up faster).
    search_duration_mult: float = 1.0
    # Extra billboard scale for silhouette read (in addition to width/height).
    billboard_scale_mul: float = 1.0
    # Random alert delay upper bound (seconds) before calm → CHASE (spawn variety).
    spawn_alert_delay_max: float = 0.38
    # Telegraph window as a fraction of shoot cooldown (larger = longer wind-up).
    telegraph_cooldown_frac: float = 0.30


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
        attack_telegraph_rgb=(255, 105, 70),
        sprite_file="enemies/grunt.png",
        prefers_patrol_when_calm=True,
        detect_range_mult=1.0,
        patrol_radius=150.0,
        separation_radius=90.0,
        attack_standoff_min_frac=0.38,
        attack_standoff_max_frac=0.86,
        chase_flank_bias=0.1,
        attack_strafe_mult=1.0,
        search_duration_mult=1.0,
        billboard_scale_mul=1.0,
        spawn_alert_delay_max=0.36,
        telegraph_cooldown_frac=0.30,
    ),
    TYPE_HEAVY: EnemyTypeSpec(
        key=TYPE_HEAVY,
        label="Heavy",
        max_hp=220.0,
        speed=48.0,
        ranged_damage=19.0,
        shoot_cooldown=1.72,
        contact_dps=16.0,
        billboard_width=48.0,
        billboard_height=62.0,
        minimap_color=(120, 95, 200),
        placeholder_fill=(95, 75, 175),
        placeholder_edge=(45, 35, 95),
        attack_telegraph_rgb=(255, 75, 195),
        sprite_file="enemies/heavy.png",
        prefers_patrol_when_calm=False,
        detect_range_mult=0.92,
        lost_range_mult=0.95,
        attack_range_mult=0.88,
        attack_leave_range_mult=0.92,
        patrol_radius=72.0,
        patrol_wander_mult=0.4,
        separation_radius=108.0,
        separation_weight=1.15,
        attack_standoff_min_frac=0.22,
        attack_standoff_max_frac=0.58,
        chase_flank_bias=0.05,
        attack_strafe_mult=0.5,
        search_duration_mult=1.38,
        billboard_scale_mul=1.09,
        spawn_alert_delay_max=0.58,
        telegraph_cooldown_frac=0.44,
    ),
    TYPE_SCOUT: EnemyTypeSpec(
        key=TYPE_SCOUT,
        label="Scout",
        max_hp=55.0,
        speed=126.0,
        ranged_damage=8.0,
        shoot_cooldown=1.02,
        contact_dps=28.0,
        billboard_width=34.0,
        billboard_height=48.0,
        minimap_color=(90, 210, 130),
        placeholder_fill=(55, 185, 115),
        placeholder_edge=(25, 95, 60),
        attack_telegraph_rgb=(255, 220, 95),
        sprite_file="enemies/scout.png",
        prefers_patrol_when_calm=True,
        detect_range_mult=1.18,
        lost_range_mult=1.0,
        attack_range_mult=1.0,
        patrol_radius=205.0,
        patrol_wander_mult=1.35,
        separation_radius=68.0,
        separation_weight=0.65,
        attack_standoff_min_frac=0.48,
        attack_standoff_max_frac=0.94,
        chase_flank_bias=0.48,
        attack_strafe_mult=1.62,
        search_duration_mult=0.72,
        billboard_scale_mul=0.93,
        spawn_alert_delay_max=0.22,
        telegraph_cooldown_frac=0.24,
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
