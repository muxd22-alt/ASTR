"""Optional narrative reading layer.

This package turns calculated chart facts into reflective prose. It never
changes planetary positions, houses, aspects, or transit dates.
"""

from astromind.reading.story import generate_reading

__all__ = ["generate_reading"]
