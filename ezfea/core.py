"""Validated analysis inputs. Units: mm, N, MPa."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import math

@dataclass(frozen=True)
class Material:
    name: str = "A36 (nominal example)"
    elastic_modulus_mpa: float = 200000.0
    poisson_ratio: float = 0.26
    yield_mpa: float = 250.0

    def validate(self):
        if not self.name.strip():
            raise ValueError("Material name is required.")
        if not math.isfinite(self.elastic_modulus_mpa) or self.elastic_modulus_mpa <= 0:
            raise ValueError("Young's modulus must be positive.")
        if not math.isfinite(self.poisson_ratio) or not (-1 < self.poisson_ratio < 0.5):
            raise ValueError("Poisson ratio must be between -1 and 0.5.")
        if not math.isfinite(self.yield_mpa) or self.yield_mpa <= 0:
            raise ValueError("Yield strength must be positive.")

@dataclass(frozen=True)
class Analysis:
    step_file: str
    fixed_face: int
    loaded_face: int
    force_n: tuple[float, float, float]
    mesh_size_mm: float
    material: Material = Material()

    def validate(self):
        if not Path(self.step_file).is_file() or Path(self.step_file).suffix.lower() not in {".step", ".stp"}:
            raise ValueError("Select an existing .step or .stp file.")
        if self.fixed_face <= 0 or self.loaded_face <= 0 or self.fixed_face == self.loaded_face:
            raise ValueError("Select different connection and load faces.")
        if not math.isfinite(self.mesh_size_mm) or self.mesh_size_mm <= 0:
            raise ValueError("Mesh size must be positive (mm).")
        if not all(math.isfinite(v) for v in self.force_n) or not any(v != 0 for v in self.force_n):
            raise ValueError("Supply a finite, nonzero force vector (N).")
        self.material.validate()

    def as_dict(self):
        return asdict(self)

@dataclass(frozen=True)
class Face:
    tag: int
    center_mm: tuple[float, float, float]
    bbox_mm: tuple[float, float, float, float, float, float]

    @property
    def label(self):
        return f"Face {self.tag} | center ({', '.join(f'{v:.1f}' for v in self.center_mm)}) mm"
