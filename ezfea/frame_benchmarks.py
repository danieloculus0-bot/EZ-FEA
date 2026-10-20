"""Deterministic *definition* of three small welded-frame physics specimens.

These are monolithic Boolean-fused solid weldment analogues, not contact/bolt/
weld-connector assemblies. The shared outer dimensions make racking comparisons
meaningful. Do not use them as certification benchmarks.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import argparse
import hashlib
import json
import math

from .core import Analysis, FaceConstraint, FaceLoad, Material
from .mesh import inspect_step
from .workflow import run_case


@dataclass(frozen=True)
class FrameSpec:
    key: str
    construction: str
    width_mm: float = 240.0
    height_mm: float = 180.0
    depth_mm: float = 20.0
    member_mm: float = 20.0
    brace_mm: float = 14.0
    load_n: tuple[float, float, float] = (250., 0., 0.)

    def check(self):
        if self.construction not in {"portal", "rectangle", "braced"}:
            raise ValueError("Unsupported frame geometry.")
        if (min(self.width_mm,self.height_mm,self.depth_mm,self.member_mm,
                self.brace_mm) <= 0
                or self.width_mm <= 4*self.member_mm
                or self.height_mm <= 4*self.member_mm
                or self.brace_mm > self.member_mm):
            raise ValueError("Frame dimensions would create degenerate profiles.")
        if not all(math.isfinite(v) for v in asdict(self).values()
                   if isinstance(v, (int,float))):
            raise ValueError("Dimensions must be finite.")
        if not all(math.isfinite(v) for v in self.load_n) or not any(self.load_n):
            raise ValueError("Nonzero finite force is required.")


STUDIES = (
    FrameSpec("01_portal_vertical", "portal", load_n=(0., 0., -250.)),
    FrameSpec("02_rectangle_racking", "rectangle"),
    FrameSpec("03_braced_racking", "braced"),
)


def geometry_definition_sha256(spec):
    """Stable identity of parameters, distinct from a STEP file hash."""
    return hashlib.sha256(
        json.dumps(asdict(spec), sort_keys=True, separators=(",",":")).encode()
    ).hexdigest()


def create_step(spec: FrameSpec, destination):
    """Create one continuously fused solid from rectangular CAD prisms.

    Gmsh OpenCascade must be present. All lengths are millimeters; the three
    examples use solid stock to isolate the FEA engine from wall thickness,
    bolted/tied connectors, beam shell theory, and contact.
    """
    spec.check()
    import gmsh
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add(spec.key)
        occ = gmsh.model.occ
        w,h,d,t = spec.width_mm,spec.height_mm,spec.depth_mm,spec.member_mm
        volumes = [
            occ.addBox(0,0,0, t,d,h),
            occ.addBox(w-t,0,0, t,d,h),
            occ.addBox(t,0,h-t, w-2*t,d,t),
        ]
        if spec.construction in ("rectangle","braced"):
            volumes.append(occ.addBox(t,0,0,w-2*t,d,t))
        if spec.construction == "braced":
            # The diagonal is placed across the X-Z plane and joined to the
            # inner faces of the uprights and cross members.
            dx,dz = w-2*t,h-2*t
            length=math.hypot(dx,dz)
            brace=occ.addBox(t,0,t-spec.brace_mm/2,
                             length,d,spec.brace_mm)
            occ.rotate([(3,brace)],t,0,t,0,1,0,-math.atan2(dz,dx))
            volumes.append(brace)
        # Fuse all independent prisms to one continuous solid. Zero
        # disconnected components is an engine guarantee, not an assumption.
        fused, _ = occ.fuse([(3, volumes[0])],
                            [(3, part) for part in volumes[1:]],
                            removeObject=True, removeTool=True)
        occ.synchronize()
        solids=gmsh.model.getEntities(3)
        if len(fused) != 1 or len(solids) != 1:
            raise ValueError(f"{spec.key}: expected one Boolean-fused solid; got {len(solids)}")
        gmsh.write(str(dest))
    finally:
        gmsh.finalize()
    return dest


def case_from_step(spec:FrameSpec, step_file, mesh_size_mm=14.):
    """Select faces *by geometry*, avoiding hard-coded STEP face numbers.

    The bottom exposed horizontal faces are completely fixed; top plane gets
    the total tangential (racking) or vertical (portal) force. This is a
    laboratory idealization, not authentic welded footing behavior.
    """
    if not math.isfinite(mesh_size_mm) or mesh_size_mm<=0:
        raise ValueError("Positive finite mesh length required.")
    faces=inspect_step(str(step_file))
    w,h=spec.width_mm,spec.height_mm
    tol=1e-3
    flat_at=lambda face,z: abs(face.bbox_mm[2]-z)<tol and abs(face.bbox_mm[5]-z)<tol
    bottoms=[f for f in faces if flat_at(f,0.)]
    tops=[f for f in faces if flat_at(f,h)]
    if len(bottoms) < 1 or len(tops) < 1:
        raise ValueError(f"{spec.key}: missing footing or load face, cannot guess.")
    # The STEP Boolean may split coplanar exterior faces into several patches.
    # Include all patches on each prescribed plane, apportioning top load by
    # their actual rectangle areas (all selected planes are axis-aligned).
    patches=[]
    for face in tops:
        xmin,ymin,_,xmax,ymax,_=face.bbox_mm
        area=(xmax-xmin)*(ymax-ymin)
        if area<=0:
            raise ValueError(f"{spec.key}: degenerate top load patch.")
        patches.append((face,area))
    total_area=sum(area for _,area in patches)
    loads=tuple(FaceLoad(f.tag,tuple(value*area/total_area
                                   for value in spec.load_n))
                for f,area in patches)
    return Analysis(
        str(step_file), 0, 0, (0.,0.,0.), mesh_size_mm,
        material=Material(),
        connections=tuple(FaceConstraint(f.tag) for f in sorted(bottoms,key=lambda f:f.center_mm[0])),
        loads=loads
    )


def run_study(spec, root, mesh_size_mm=14., *, generate_only=False):
    """Store fixed parameters, solid STEP, load/fixture references and results."""
    root=Path(root)
    folder=root/spec.key
    folder.mkdir(parents=True,exist_ok=True)
    cad=create_step(spec, folder/(spec.key+".step"))
    case=case_from_step(spec,cad,mesh_size_mm)
    definition={
        "schema":"ezfea.frame_specimen.v1",
        "identity_sha256":geometry_definition_sha256(spec),
        "geometry":asdict(spec),
        "step_file":cad.name,
        "material":asdict(case.material),
        "mesh_size_mm":mesh_size_mm,
        "supports":[asdict(c) for c in case.connections],
        "loads":[asdict(l) for l in case.loads],
        "units":"mm, N, MPa",
        "joint_model":"monolithic Boolean-fused solid (idealized perfectly joined members)",
        "restrictions":["linear elastic and static","C3D4 solid tets","entire bottom faces fully fixed",
                        "total force distributed to top face",
                        "no weld, bolt, contact, buckling, or fatigue modeling",
                        "not validated engineering sign-off"]
    }
    (folder/"specimen.json").write_text(json.dumps(definition,indent=2)+"\n",encoding="utf-8")
    if generate_only:
        return {"key":spec.key,"specimen":folder/"specimen.json","run":None}
    output=run_case(case,folder/"runs")
    data=json.loads((output/"case.json").read_text(encoding="utf-8"))
    if data["status"]!="completed":
        raise RuntimeError(f"{spec.key}: solver not completed: {data['status']}")
    physics=data["results"]
    if physics["force_balance_check"]!="pass" or physics["max_displacement_mm"]<=0:
        raise RuntimeError(f"{spec.key}: bad solver physics metrics: {physics}")
    (folder/"latest_result.json").write_text(
        json.dumps({"specimen":definition["identity_sha256"],
                    "status":data["status"],"mesh":data["mesh"],
                    "results":physics,"run_dir":str(output.relative_to(folder))},
                   indent=2)+"\n",encoding="utf-8")
    return {"key":spec.key,"specimen":folder/"specimen.json","run":output,
            "max_displacement_mm":physics["max_displacement_mm"],
            "max_von_mises_mpa":physics["max_von_mises_mpa"],
            "force_balance_error":physics["force_balance_relative_error"]}


def run_suite(output_dir,mesh_size_mm=14.,*,generate_only=False):
    """Same three cases each run; compare like-for-like lateral racking.

    Relative stiffness check is a useful regression, not ground truth for
    accurate welded frames. Record numbers without claiming convergence.
    """
    results=[run_study(s,output_dir,mesh_size_mm,generate_only=generate_only)
             for s in STUDIES]
    report={"schema":"ezfea.frame_suite.v1","mesh_size_mm":mesh_size_mm,
            "case_results":results,
            "comparison":"Braced and unbraced rectangular frames share dimensions and lateral load.",
            "engineering_status":"experimental_unvalidated"}
    if not generate_only:
        plain=results[1]["max_displacement_mm"]
        braced=results[2]["max_displacement_mm"]
        report["bracing_stiffness_ratio_unbraced_to_braced"]=plain/braced
        report["braced_displacement_less_than_unbraced"]=braced<plain
        if not braced < plain:
            raise RuntimeError(
                "Physics regression: the idealized braced frame should "
                "deflect less than its otherwise identical unbraced frame."
            )
    target=Path(output_dir)/"suite_summary.json"
    target.write_text(json.dumps(report,indent=2,default=str)+"\n",encoding="utf-8")
    return report


def main():
    parser=argparse.ArgumentParser(description="EZ-FEA repeatable welded frame study suite")
    parser.add_argument("--out",default="runs/frame_benchmarks")
    parser.add_argument("--mesh-mm",type=float,default=14.)
    parser.add_argument("--generate-only",action="store_true",
                        help="Only create the STEP parts and their explicit fixture/load definitions")
    args=parser.parse_args()
    print(json.dumps(run_suite(args.out,args.mesh_mm,generate_only=args.generate_only),
                     indent=2,default=str))


if __name__=="__main__":
    main()
