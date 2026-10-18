"""Aesthetic quality subpackage.

Optional subsystem enabled by ``--enable-aesthetic``. Kept isolated so the core
validation pipeline has zero dependency on the aesthetic engine.
"""

from .validator import QualityValidator

__all__ = ["QualityValidator"]
