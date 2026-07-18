"""Aesthetic quality subpackage.

Enabled by default and disabled only with ``--no-aesthetic``. Kept isolated so the core
validation pipeline has zero dependency on the aesthetic engine.
"""

from .validator import QualityValidator

__all__ = ["QualityValidator"]
