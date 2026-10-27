# Real Warren-style truss example for EZ-FEA

![Schematic of the Warren truss with center load and two end supports](warren_truss_example.svg)

**[Download the actual STEP files and raw Gmsh/CalculiX analysis from the successful workflow](https://github.com/danieloculus0-bot/EZ-FEA/actions/workflows/truss-weldment-example.yml)**. Open the latest passing **Real Warren Truss Weldment Example** run and download its archived `EZ-FEA-Warren-truss-STEP-and-real-FEA` artifact.

This is a **real native solid model and a real native FEA solve**, not a fake screenshot, assumed stress field, or a simulation running on GitHub Pages. The geometry is intentionally modest enough for a reliable first end-to-end STEP/3D benchmark.

## Two STEP files, two fundamentally different physical assumptions

- **`separate_members.step`** contains ten independent solid square-section bars (two chords and eight diagonal web members), organized in a Warren-type planar layout. The bars overlap at joints but have no miter/coping operations, welds, ties, friction, or structural contact definitions. **Do not solve it as if the members transfer load.** It exists to expose the currently unsupported multibody weldment workflow.
- **`fused_ideal_joints.step`** Boolean-unites those same bars and three small loading/support pads into **one closed STEP volume**. This can be meshed with the current single-solid EZ-FEA backend. The union mathematically creates **perfectly continuous material** across all junctions. It does **not** calculate actual weld size, throat, HAZ, fatigue or joint failure.

Both truss members are **solid** square bars, not hollow RHS/HSS tubing. This keeps the specimen inexpensive enough to mesh and reveals the two very different CAD import states without suggesting that tubing behavior or welded connection strength has been modeled.

## Loading and fixtures

| Parameter | Example value |
|---|---|
| Bottom chord span | 600 mm |
| Truss rise | 180 mm |
| Chords | 24 × 24 mm solid steel bars |
| Diagonals | 18 × 18 mm solid steel bars |
| Material | illustrative E=200,000 MPa, ν=0.26, nominal yield 250 MPa |
| Load | 1,000 N downward at a small center-top pad |
| Left support | pad face X/Y/Z fully restrained |
| Right support | pad face Y/Z restrained, X unrestrained |
| Element | real quadratic C3D10 tetrahedra |

**Engineering limitations:** the finite pads are not idealized mathematical support points. The load is spread on a face rather than attached by a connector. No buckling, weld qualification, fatigue, plasticity, thin-walled RHS, service-code loads or physical testing is established.

## Actual native results

The first [completed native truss run](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/40473627691) solved the fused STEP body with a target 16 mm C3D10 mesh:

- **3,595 actual 10-node tetrahedra**
- **0.0108109 mm** maximum total nodal displacement
- **10.1066 MPa** peak integration-point von Mises stress
- Real support-reaction force equilibrium: **pass**
- Real support-reaction moment equilibrium: **pass**

These are numerical measurements from the particular idealized continuous-solid model, **not proof of structural or welded design adequacy**. A second, finer mesh is separately recorded in current CI when completed; two mesh sizes alone do not establish stress convergence.

## Reproduce on your own machine

From the original EZ-FEA Python repository, with Gmsh and CalculiX installed:

```powershell
py -m ezfea.truss_example --out runs/truss_example
py -m ezfea.truss_example --solve --mesh 16 --out runs/truss_analysis
```

The generator preserves:

- `GEOMETRY.json`: dimensions, members, distinct CAD source SHA256s and model limits
- `separate_members.step`, `fused_ideal_joints.step`: original 3D CAD sources
- `FACE_SELECTION.json`: actual Gmsh STEP face IDs for left/right restraints and the upper load
- `native_results/.../case.json`: mesh, numerical stress, displacement and force/moment checks
- `native_results/.../analysis.inp/.dat/.frd`: complete actual solver input and results
- `TRUSS_RESULT.json`, `RESULTS.md`: concise results and declared assumptions
- CI comparison file `MESH_COMPARISON.json/.md`: two-grid observations when available

The standard graphical desktop currently supports a **single fixed face**. The truss example needs **two supports**; the command above invokes the existing verified Python multi-face backend. You can view the *fused* STEP in the desktop's rotatable CAD preview, but the ordinary **HOLD / LOAD / SOLVE** controls are **not yet a complete two-support truss workflow**.

That gap—not more hand-authored CAD—is the next real assembly and GUI feature to build.

[Example source](../../ezfea/truss_example.py) · [Test workflow](https://github.com/danieloculus0-bot/EZ-FEA/actions/workflows/truss-weldment-example.yml)
