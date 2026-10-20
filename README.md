# EZ-FEA

Simple STEP-to-structural-FEA desktop app powered by the free **Gmsh** mesher and **CalculiX** physics solver.

**v0.1 EXPERIMENTAL. Not validated for professional engineering sign-off.**

## Live browser demo

**[Open EZ-FEA on GitHub Pages](https://danieloculus0-bot.github.io/EZ-FEA/)** — dark-green four-step workbench, real 2D eight-element cantilever FE example, and 3D STEP/STL/OBJ **preview only** for uploads.

BEAN's official green sprout mascot now appears as a gently animated engineering advisor. The browser BEAN panel uses deterministic, testable checks based on actual beam numerical output to explain bending stress vs nominal material yield, tip movement, agreement with the independent analytical cantilever reference, and model limitations. On imported CAD previews, it explains whether fixture and load marks are complete and why those marks are **not** physical restraints. Motion honors `prefers-reduced-motion`.

The browser BEAN panel also exposes **six genuine, previously calculated 3D frame studies** with displacement and stress metrics from a recorded native Gmsh/CalculiX GitHub Actions solve. This is a **workflow-refreshed, provenance-linked result set**, not a fresh browser-triggered cloud solve, not a direct browser connection to the 3D solver, and not an autonomous BEAN Core model or safety approval. See [Browser Lab details](web/README.md).

## Repeatable frame physics specimens

The native Python engine now includes `ezfea/frame_benchmarks.py`: six repeatable STEP loading cases for three parametric frame shapes with identical overall dimensions (240 × 180 × 20 mm), solid 20 mm members, nominal A36 steel, explicit supports/loads, and recorded case metadata:

- **Open portal**: 250 N vertical loading.
- **Closed rectangular frame**: 250 N horizontal racking.
- **Diagonally braced frame**: same 250 N horizontal racking, for a controlled comparison.
- **Open portal, rectangle and braced rectangle**: each also tested under the complementary 250 N lateral or downward load, for six actual studies in total.

These are single continuous Boolean-fused solids representing idealized perfectly connected members, **not multi-component welded/bolted/contact assemblies**. Each is meshed and solved in CalculiX with equilibrium checks and saved STEP/inputs/FRD/DAT/log/JSON records. The dedicated [Frame Specimen Physics Suite](https://github.com/danieloculus0-bot/EZ-FEA/actions/workflows/frame-physics.yml) runs the real solver and archives artifacts, and it tests that the braced example reduces racking deflection relative to the unbraced frame. One mesh size does not prove convergence or engineering accuracy.

Generate model files without the solver:

~~~sh
python -m ezfea.frame_benchmarks --out frame_benchmark_artifacts --generate-only
~~~

With Gmsh Python API and the external `ccx` solver installed, run all three cases:

~~~sh
python -m ezfea.frame_benchmarks --out frame_benchmark_artifacts --mesh-mm 14
~~~

GitHub Pages now automatically overlays the latest successful archived six-case result set at deployment; [review the solver workflow](https://github.com/danieloculus0-bot/EZ-FEA/actions/workflows/frame-physics.yml). The repository carries a three-case offline fallback. The solver evidence is intentionally kept separate from BEAN's advisory remarks; BEAN does not calculate or fabricate stress.

### Automatic native-physics results bridge

A successful authorized frame workflow run uses `scripts/publish_frame_evidence.py` to verify six solved cases and upload a JSON artifact, complete with the source run, commit, frame geometry, forces, material, mesh counts, solver displacement, von Mises stress and reaction equilibrium. The **Pages workflow automatically downloads the latest good artifact and redeploys the website**. Failed solver runs cannot replace published results. The browser displays a selectable 3D **reference geometry** alongside these real, archived values; it does not make up stress contours.

To add another repeatable simulation, extend `STUDIES` in `ezfea/frame_benchmarks.py`, assign its label in `scripts/publish_frame_evidence.py`, and include comparison/test expectations. The workflow does the Gmsh/CalculiX solve and refreshes the site's selector without a manual web result update.

The workflow may also be manually started by a repo maintainer in **Actions → Frame Specimen Physics Suite → Run workflow**. Anonymous GitHub Pages visitors **cannot** launch arbitrary user-uploaded 3D jobs, which would require an authenticated compute service. No tokens or privileged workflow endpoints are embedded in website HTML. See [web/README.md](web/README.md).

## Quadratic C3D10 tetrahedra (experimental)

EZ-FEA now accepts an explicit `Analysis(..., element_type="C3D10")` option alongside its original `"C3D4"` default. The real Gmsh pipeline generates ten-node tetrahedra, converts Gmsh's midside edge order into CalculiX's C3D10 convention, constrains quadratic face nodes, and integrates uniformly distributed total forces using the second-order triangular face shape functions. The CalculiX input deck and result archive identify the actual element type; unknown/mismatched element types are rejected.

**Native solver verification:** `tests/test_integration.py` runs a genuine C3D10 cantilever solve through Gmsh and CalculiX, including stress, deflection and reaction-force checks. The [C3D4 vs C3D10 Native Comparison](https://github.com/danieloculus0-bot/EZ-FEA/actions/workflows/element-order-comparison.yml) uses byte-identical STEP geometry, matching fixtures/loads, and 14/10/7 mm grids for all six frame/load combinations (36 native solves). The workflow archives native solver records and an independent side-by-side comparison report. Use the **latest successful workflow run** for actual observations, rather than assuming a quadratic element must converge.

The interpolation order is independent of mesh density. A passing solve or apparently stable displacement is **not** engineering validation, and high peak stress at idealized fixed edges may remain mesh sensitive. C3D10 boundary traction integration currently assumes planar triangular surfaces; its curved-CAD loading should be upgraded to isoparametric quadrature before extending this pathway to curved parts.


### First measured element-order comparison (October 20, 2026)

[**Successful C3D4 vs C3D10 real-physics run**](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39499859849): 12 native solves; both element types used the **same STEP file bytes** and identical 14/10/7 mm requested meshes, 250 N load and support definition.

| Frame | C3D4 last displacement change (10 → 7 mm) | C3D10 last displacement change (10 → 7 mm) |
|---|---:|---:|
| Rectangular frame, lateral load | 23.371% | **1.128%** |
| Braced rectangle, lateral load | 3.965% | **0.303%** |

At the 7 mm requested mesh size, rectangular-frame maximum displacement was **0.0194903 mm** using C3D4 versus **0.0254805 mm** using C3D10. Both C3D10 cases met the limited **5% displacement-change criterion at both refinement steps**; neither met the separate peak-stress sensitivity screening criterion. Quadratic interpolation improved the observed displacement mesh stability in these examples, **not independently proven physical accuracy**. The existing native-only benchmark result bridge continues to publish the original fixed-case records without altering the browser visual design.


### Full six-frame C3D10 refinement and stress diagnosis — October 20, 2026

[**Completed 36-solve comparison**](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39501652909): the same six STEP specimens, with byte-identical geometry for C3D4/C3D10 and requested mesh sizes 14, 10 and 7 mm.

| Frame/load | C3D4 last displacement change | C3D10 last displacement change | C3D10 last global peak-stress change |
|---|---:|---:|---:|
| Portal, downward | 28.09% | **0.64%** | 12.97% |
| Rectangle, sideways | 23.37% | **1.13%** | 13.91% |
| Braced rectangle, sideways | 3.97% | **0.30%** | 12.19% |
| Portal, sideways | 21.21% | **0.57%** | 13.68% |
| Rectangle, downward | 29.06% | **0.79%** | 15.72% |
| Braced rectangle, downward | 25.61% | **0.70%** | 8.28% |

Quadratic elements showed smaller displacement changes in every test. Peak stress remained mesh-sensitive, so this does not establish independent physical accuracy.

The native stress-diagnostics module groups *actual CalculiX integration-point stresses* by approximate host tetrahedron centroid distance from fixed and loaded faces, with unchanged **20 and 40 mm** physical exclusion bands. In five of six cases, the largest-stress element center was approximately **158–161 mm above the fixed base**, near the upper load/joint region. The lateral rectangular case peaked approximately **22 mm** above the base. Excluding 40 mm around the loaded top reduced the final peak-stress change to **3.84%, 7.79%, 5.76%, 4.58%, and 3.28%** in the five upper-localized cases; lateral rectangular remained **13.91%**, consistent with a lower hotspot.

Distances reflect tetrahedron **corner centroids**, not actual Gauss point positions. These are screening trends, not proof of a stress singularity or convergence. Follow-up validation requires load/joint modeling investigations, fixed-position stress comparisons, improved curved-surface quadrature and independent analytical or physical benchmarks. EZ-FEA remains **experimental and not for engineering sign-off**.

## Six-frame automatic mesh-convergence experiment

[**Real 3D Frame Mesh Convergence — GitHub Actions**](https://github.com/danieloculus0-bot/EZ-FEA/actions/workflows/frame-convergence.yml) runs **18 genuine Gmsh + CalculiX analyses**: all six repeatable frame load cases at **14, 10, and 7 mm** requested tetrahedral mesh sizes. Geometry, support faces, load vectors and nominal material are held constant within each three-grid series.

- `ezfea/frame_convergence.py` reuses the tested `ezfea.convergence.run_refinement` engine rather than introducing another solver.
- Each frame records STEP and input hashes, element/node counts, full CalculiX result files, force equilibrium, maximum displacement and peak integration-point von Mises stress on every grid.
- `convergence_summary.json`, `convergence_summary.csv` and `CONVERGENCE_REPORT.md` record **adjacent mesh changes**. The final two changes must each be ≤ 5% for the label `stable_at_checked_mesh_sizes` in displacement. Peak stress gets its **own** 10% trend screening; it is never implicitly called converged merely because movement stabilized.
- The Actions run page displays the human-readable report and provides the complete native solver files as a downloadable artifact. An unresolved result is **reported as needing further refinement**, not quietly declared successful.
- This is **mesh-sensitivity/regression evidence, not verification against an independent physical or analytic truth, not validated safety**, especially near fully fixed corners and for bending with first-order C3D4 elements.

With Gmsh and native `ccx` installed, run the same experiment locally:

~~~sh
python -m ezfea.frame_convergence --out runs/frame_convergence --meshes 14 10 7
~~~

The public GitHub Pages interface remains unchanged; these are traceable native experiments, not browser calculations.

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

**Important limits:** only one continuous solid is supported, not a multi-component door assembly. A face restraint is not a real bolt, hinge, bearing, pin, or actuator connection. C3D4 bending may be overly stiff and the experimental C3D10 mode is not independently validated; no automatic engineering accuracy certification, contact/ties, nonlinear material law, print orientation effects, built-in result contour viewer, or validated factor of safety. Yield strength is stored for indicative comparison. No fabricated results on failures. A real Gmsh + CalculiX solver smoke test is exercised in GitHub Actions.

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

## Initial three-frame solver studies (historical baseline, 2026-10-20)

The Python engine now includes a **repeatable real-solver frame suite**, separate from the simplified GitHub Pages browser beam demo:

- `01_portal_vertical`: idealized open-bottom portal under vertical loading.
- `02_rectangle_racking`: closed unbraced rectangular frame under lateral racking.
- `03_braced_racking`: matched braced rectangle under the same lateral force.

`ezfea/frame_benchmarks.py` constructs Boolean-fused continuous STEP solids with Gmsh, selects geometry-based face constraints, executes CalculiX, captures source parameters and SHA-256 identities, reports displacement/stress/reaction equilibrium, and checks that the braced specimen deflects less than its matched unbraced case. These initial three **actual 3D solves passed the October 20 Frame Specimen Physics Suite**; the repeatable suite has since expanded to six combinations. To reproduce with Gmsh and `ccx` installed:

~~~sh
python -m ezfea.frame_benchmarks --out runs/frame_benchmarks --mesh-mm 14
~~~

This is **regression evidence, not an independently validated welded-frame benchmark**. The members are fused as one solid; there are no weld beads, joint compliance, hinge pins, actuator connectors, multi-part contact or demonstrated mesh convergence. GitHub Pages remains a separate browser-only beam calculation/CAD preview, **not the server-side 3D CalculiX engine**.

[Portfolio-wide audit](https://github.com/danieloculus0-bot/Axiom_Beta/blob/main/docs/PORTFOLIO_AUDIT_2026-10-20.md).

## Three-grid mesh-refinement evidence

Run three or more real Gmsh/CalculiX solves of one STEP solid, material, load,
and fixture arrangement. The only input varied is the requested mesh size.
The output \`refinement.json\` records native solver evidence, mesh element
counts, adjacent displacement changes and global peak-stress changes.

~~~sh
python -m ezfea.convergence --demo --meshes 12 8 5 --out runs/refinement_demo
~~~

For your own STEP, use \`--step part.step --fixed-face N --loaded-face M\`
and the same mesh flags. Multi-face load/constraint scenarios are supported
from Python through \`run_refinement(case, ...)\`.

This is an **experimental numerical sensitivity study**, *not* NAFEMS
validation or engineering sign-off. Two relatively similar displacement
results do not prove accuracy, stress singularities may grow with refinement,
and first-order C3D4 elements can lock in bending. Record independent
analytical benchmarks, physical experiments and appropriate higher-order
elements before professional use.
