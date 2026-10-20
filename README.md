# EZ-FEA

Simple STEP-to-structural-FEA desktop app powered by the free **Gmsh** mesher and **CalculiX** physics solver.

**v0.1 EXPERIMENTAL. Not validated for professional engineering sign-off.**

## Live browser demo

**[Open EZ-FEA on GitHub Pages](https://danieloculus0-bot.github.io/EZ-FEA/)** — dark-green four-step workbench, real 2D eight-element cantilever FE example, and 3D STEP/STL/OBJ **preview only** for uploads.

BEAN's official green sprout mascot now appears as a gently animated engineering advisor. The browser BEAN panel uses deterministic, testable checks based on actual beam numerical output to explain bending stress vs nominal material yield, tip movement, agreement with the independent analytical cantilever reference, and model limitations. On imported CAD previews, it explains whether fixture and load marks are complete and why those marks are **not** physical restraints. Motion honors `prefers-reduced-motion`.

The browser BEAN panel also exposes **three genuine, previously calculated 3D frame studies** with displacement and stress metrics from a recorded native Gmsh/CalculiX GitHub Actions solve. This is a **static, provenance-linked result set**, not a fresh cloud solve, not a direct browser connection to the 3D solver, and not an autonomous BEAN Core model or safety approval. See [Browser Lab details](web/README.md).

## Repeatable frame physics specimens

The native Python engine now includes `ezfea/frame_benchmarks.py`: three parametric STEP test pieces with identical overall dimensions (240 × 180 × 20 mm), solid 20 mm members, nominal A36 steel, explicit supports/loads, and recorded case metadata:

- **Open portal**: 250 N vertical loading.
- **Closed rectangular frame**: 250 N horizontal racking.
- **Diagonally braced frame**: same 250 N horizontal racking, for a controlled comparison.

These are single continuous Boolean-fused solids representing idealized perfectly connected members, **not multi-component welded/bolted/contact assemblies**. Each is meshed and solved in CalculiX with equilibrium checks and saved STEP/inputs/FRD/DAT/log/JSON records. The dedicated [Frame Specimen Physics Suite](https://github.com/danieloculus0-bot/EZ-FEA/actions/workflows/frame-physics.yml) runs the real solver and archives artifacts, and it tests that the braced example reduces racking deflection relative to the unbraced frame. One mesh size does not prove convergence or engineering accuracy.

Generate model files without the solver:

~~~sh
python -m ezfea.frame_benchmarks --out frame_benchmark_artifacts --generate-only
~~~

With Gmsh Python API and the external `ccx` solver installed, run all three cases:

~~~sh
python -m ezfea.frame_benchmarks --out frame_benchmark_artifacts --mesh-mm 14
~~~

The latest browser-bundled reference results originate from [this successful recorded solver run](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39488256233). The solver evidence is intentionally kept separate from BEAN's advisory remarks; BEAN does not calculate or fabricate stress.

## Windows installation

Install Python 3.10+ and the free CalculiX CCX solver from https://www.calculix.de/. Put ccx.exe on PATH or point EZFEA_CCX at its full path.

In PowerShell, from the EZ-FEA folder:

~~~powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
~~~

Click Demo beam for a 100 x 10 x 10 mm cantilever with automatically selected end faces, or choose your own STEP solid and set its fully fixed connection face, loaded face and total XYZ force. Click RUN ANALYSIS. Real solver files and records go into the runs directory. View the analysis.frd result with free CalculiX GraphiX (cgx).

## Scope

- Real Gmsh STEP import and 3D linear C3D4 tetrahedral mesh.
- Face-based connections including independent global X/Y/Z translation restraints and multiple connection faces (Python engine API).
- Multiple independent total-force vectors distributed over CAD faces by triangle area, with exact summed XYZ load tracking.
- Six rigid-body-mode restraint rank check before multi-face solves. It detects obvious unconstrained motion, but cannot validate the mechanical authenticity of a fixture.
- Single-material, linear elastic, static CalculiX solves.
- N/mm/MPa units. Model STEP dimensions must already be millimeters.
- Recorded original STEP model and SHA256, inputs, mesh statistics, solver logs and native result files.
- BEAN handoff as JSON. Optional verified BEAN Core log-note inbox interface if EZFEA_BEAN_INBOX is set to the same location as BEAN_INBOX_DIR. BEAN logs a factual run record, not an engineering review.
- Automated tests and optional full solver smoke test.

**Important limits:** only one continuous solid is supported, not a multi-component door assembly. A face restraint is not a real bolt, hinge, bearing, pin, or actuator connection. First-order C3D4 is inaccurate for some bending scenarios; no automatic mesh convergence, contact/ties, nonlinear material law, print orientation effects, built-in result contour viewer, or validated factor of safety. Yield strength is stored for indicative comparison. No fabricated results on failures. A real Gmsh + CalculiX solver smoke test is exercised in GitHub Actions.

Run automated tests:

~~~sh
python -m unittest discover -s tests -v
~~~

Enable installed-solver smoke testing with environment variable EZFEA_RUN_INTEGRATION=1.

## Validation

See docs/VALIDATION.md. Target ASME V&V 10-2019 (R2025), relevant NAFEMS benchmarks, mesh convergence, independent results and physical measurements.

## Licensing

EZ-FEA is GPL-3.0-or-later. Gmsh uses GPL-2.0-or-later with special exceptions, and its license conditions must be respected when distributing. CalculiX is free and open source and is called as an external executable. There is no paid solver requirement.

BEAN_FEA_Genius can later provide advisory analysis and comparisons; it must never be represented as the source of physics calculations.


## Multi-face fixture/load engine (Python API)

The legacy single fixed-face and single load-face GUI remains supported. For
advanced cases the solver can now assign independent translation constraints and
distributed force loads to multiple CAD faces. Face IDs must be obtained from
`inspect_step` for the exact current STEP model.

~~~python
from ezfea.core import Analysis, FaceConstraint, FaceLoad
from ezfea.workflow import run_case

case = Analysis(
    step_file="part.step", fixed_face=0, loaded_face=0,
    force_n=(0, 0, 0), mesh_size_mm=5,
    connections=(
        FaceConstraint(face=1, axes=(1, 2, 3)),
        FaceConstraint(face=3, axes=(3,)),
    ),
    loads=(
        FaceLoad(face=2, force_n=(0, -100, 0)),
        FaceLoad(face=4, force_n=(0, 0, -40)),
    ),
)
run_case(case)
~~~

Constrain only degrees of freedom your actual mounting removes. Axis constraints
are applied to all nodes on the selected face; they are **not** hinge joints or
actuator elements. Separate physical components and connector physics will need
their own assembly/contact/connector phase. No default safety claims.

## Verified three-frame solver studies (2026-10-20)

The Python engine now includes a **repeatable real-solver frame suite**, separate from the simplified GitHub Pages browser beam demo:

- `01_portal_vertical`: idealized open-bottom portal under vertical loading.
- `02_rectangle_racking`: closed unbraced rectangular frame under lateral racking.
- `03_braced_racking`: matched braced rectangle under the same lateral force.

`ezfea/frame_benchmarks.py` constructs Boolean-fused continuous STEP solids with Gmsh, selects geometry-based face constraints, executes CalculiX, captures source parameters and SHA-256 identities, reports displacement/stress/reaction equilibrium, and checks that the braced specimen deflects less than its matched unbraced case. These three **actual 3D solves passed the October 20 Frame Specimen Physics Suite**. To reproduce with Gmsh and `ccx` installed:

~~~sh
python -m ezfea.frame_benchmarks --out runs/frame_benchmarks --mesh-mm 14
~~~

This is **regression evidence, not an independently validated welded-frame benchmark**. The members are fused as one solid; there are no weld beads, joint compliance, hinge pins, actuator connectors, multi-part contact or demonstrated mesh convergence. GitHub Pages remains a separate browser-only beam calculation/CAD preview, **not the server-side 3D CalculiX engine**.

[Portfolio-wide audit](https://github.com/danieloculus0-bot/Axiom_Beta/blob/main/docs/PORTFOLIO_AUDIT_2026-10-20.md).
