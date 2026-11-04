"""Seeded synthetic data generator. Calibrated only with aggregate ratios (implementation plan 2b).

Nothing here is, or is derived row-by-row from, real data. Names, SKUs and codes are visibly
synthetic (``SYN-``, ``Proveedor Sintetico``).
"""

from .dataset import Dataset, GenerationConfig, generate

__all__ = ["Dataset", "GenerationConfig", "generate"]
