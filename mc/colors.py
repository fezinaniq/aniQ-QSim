"""Complex phase -> block colour, so superposition and interference are visible.

Twelve concrete colours around the hue wheel; slot k is the phase k * 30 degrees.
Global phase is physically meaningless, so phases are shown relative to the first
amplitude that is actually present (that amplitude is always red).
Landmarks: 0 = red, +90 = lime, 180 (a minus sign) = light blue, -90 = magenta.
"""

from __future__ import annotations

import cmath
import math

WHEEL = [
    "red_concrete", "orange_concrete", "yellow_concrete", "lime_concrete",
    "green_concrete", "cyan_concrete", "light_blue_concrete", "blue_concrete",
    "purple_concrete", "magenta_concrete", "pink_concrete", "brown_concrete",
]
PRESENT = 1e-9  # |amplitude|^2 below this counts as absent


def phase_slot(amp: complex, reference: complex = 1 + 0j) -> int:
    """Which of the 12 hue slots the phase of `amp` (relative to `reference`) falls in."""
    angle = cmath.phase(amp / reference)  # -pi..pi
    return round(angle / (2 * math.pi) * len(WHEEL)) % len(WHEEL)


def reference_amplitude(amps: list[complex]) -> complex:
    """The first present amplitude, used as the zero of phase."""
    for a in amps:
        if abs(a) ** 2 >= PRESENT:
            return a
    return 1 + 0j


def phase_block(amp: complex, reference: complex = 1 + 0j) -> str:
    return WHEEL[phase_slot(amp, reference)]
