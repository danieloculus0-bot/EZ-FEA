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
class FaceConstraint:
    """Restrain selected global translations on every node of a CAD face.

    axes uses CalculiX directions 1=X, 2=Y, 3=Z. A face fixture is not
    equivalent to a physical pin, bolt, bearing or actuator joint.
    """
    face: int
    axes: tuple[int, ...] = (1, 2, 3)

    def validate(self):
        if not isinstance(self.face, int) or isinstance(self.face, bool) or self.face <= 0:
            raise ValueError("Connection face must be a positive CAD face ID.")
        if not self.axes or len(set(self.axes)) != len(self.axes) or any(
            type(axis) is not int or axis not in (1, 2, 3) for axis in self.axes
        ):
            raise ValueError("Connection axes must be unique directions selected from 1, 2, 3.")


@dataclass(frozen=True)
class FaceLoad:
    """Total XYZ force distributed by actual triangulated surface area."""
    face: int
    force_n: tuple[float, float, float]

    def validate(self):
        if not isinstance(self.face, int) or isinstance(self.face, bool) or self.face <= 0:
            raise ValueError("Load face must be a positive CAD face ID.")
        if len(self.force_n) != 3 or not all(math.isfinite(v) for v in self.force_n):
            raise ValueError("Load must be a finite three-component XYZ force.")
        if not any(v != 0 for v in self.force_n):
            raise ValueError("Each surface load must have nonzero force.")


@dataclass(frozen=True)
class Analysis:
    step_file: str
    fixed_face: int
    loaded_face: int
    force_n: tuple[float, float, float]
    mesh_size_mm: float
    material: Material = Material()
    connections: tuple[FaceConstraint, ...] = ()
    loads: tuple[FaceLoad, ...] = ()

    @property
    def active_connections(self):
        return self.connections if self.connections else (FaceConstraint(self.fixed_face),)

    @property
    def active_loads(self):
        return self.loads if self.loads else (FaceLoad(self.loaded_face, self.force_n),)

    @property
    def total_force_n(self):
        return tuple(sum(load.force_n[i] for load in self.active_loads) for i in range(3))

    @property
    def force_scale_n(self):
        return sum(math.sqrt(sum(v*v for v in load.force_n)) for load in self.active_loads)

    def validate(self):
        if not Path(self.step_file).is_file() or Path(self.step_file).suffix.lower() not in {".step", ".stp"}:
            raise ValueError("Select an existing .step or .stp file.")
        if not math.isfinite(self.mesh_size_mm) or self.mesh_size_mm <= 0:
            raise ValueError("Mesh size must be positive (mm).")
        extended = bool(self.connections or self.loads)
        if extended:
            if not self.connections or not self.loads:
                raise ValueError("Provide both connections and loads for a multi-face analysis.")
            if self.fixed_face != 0 or self.loaded_face != 0 or self.force_n != (0, 0, 0):
                raise ValueError("Use zero legacy face/force fields with connections and loads.")
        else:
            if self.fixed_face <= 0 or self.loaded_face <= 0 or self.fixed_face == self.loaded_face:
                raise ValueError("Select different connection and load faces.")
        for c in self.active_connections:
            c.validate()
        for load in self.active_loads:
            load.validate()
        fixed_faces = [c.face for c in self.active_connections]
        if len(set(fixed_faces)) != len(fixed_faces):
            raise ValueError("A connection face may only occur once. Combine its restrained axes.")
        if set(fixed_faces) & {load.face for load in self.active_loads}:
            raise ValueError("Connection and load cannot use the same CAD face.")
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
