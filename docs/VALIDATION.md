# Verification and validation plan

EZ-FEA v0.1 is EXPERIMENTAL, not approved for engineering sign-off.

1. Define exact intended-use envelope: 3D isotropic, linear elastic, static solid analysis with fixed and loaded faces.
2. Compare against independent beam-bending, tension, compression and torsion equations, capturing fixed reference answers.
3. Run published NAFEMS benchmarks under documented boundary conditions.
4. Test mesh refinement, element order, singularities, loads and convergence. Upgrade C3D4 before making broad professional claims.
5. Test instrumented physical parts: measured load, strain, deflection, uncertainty and actual material characterization.
6. Compare with other established solvers under the same assumptions.
7. Obtain independent qualified engineering review and maintain a release-level regression/QA package.
8. Maintain case-level review of geometry, units, fixtures, connection conditions, loads and results.

ASME V&V 10-2019 (R2025): https://www.asme.org/codes-standards/find-codes-standards/standard-for-verification-and-validation-in-computational-solid-mechanics

NAFEMS: https://www.nafems.org/

BEAN can recommend hypotheses and run comparisons, but it may not alter benchmark truth values or claim analysis it has not performed.

## Automated refinement evidence

\`python -m ezfea.convergence --demo --meshes 12 8 5\` runs the
same physical cantilever with three C3D4 meshes. Every record comes from a
completed Gmsh/CalculiX solve with verified support-force equilibrium.
\`refinement.json\` includes mesh counts and displacement/stress differences.
The report calls a pair of changes \`stable_at_checked_mesh_sizes\` only
when the two most recent relative displacement changes are below the
specified tolerance and the element counts increase. That flag means
**numerical observation only**; \`engineering_validation\` remains
\`not_established\` for every report. Max stress is not presumed to
converge at restrained edges. The native CI smoke test runs a three-grid
case on real CalculiX instead of supplying preset numbers.

## Six-frame native convergence evidence — 2026-10-20

[Completed 18-solve Gmsh + CalculiX run](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39498582062).
The frame_convergence.py workflow runs the same six repeatable
specimens at requested tetrahedral sizes **14, 10 and 7 mm**. For each physical
case, the STEP source hash, material, fixture faces, and 250 N load remain
fixed. Full node/element counts, CalculiX files, logs and numerical outputs
are archived; force-balance checks passed for all three grids in every case.

The relative change from 10 mm to 7 mm is:

| Case | Maximum displacement (mm): 14 → 10 → 7 | Change 10→7 | Peak stress change 10→7 |
|---|---|---:|---:|
| Portal, downward | 0.0026748 → 0.0028140 → 0.0039133 | 28.09% | 15.09% |
| Rectangle, sideways | 0.013459 → 0.014935 → 0.019490 | 23.37% | 4.51% |
| Braced rectangle, sideways | 0.0020449 → 0.0020874 → 0.0021736 | 3.97% | 19.49% |
| Portal, sideways | 0.015649 → 0.017802 → 0.022594 | 21.21% | 16.17% |
| Rectangle, downward | 0.0026216 → 0.0027314 → 0.0038501 | 29.06% | 20.17% |
| Braced rectangle, downward | 0.0023723 → 0.0024964 → 0.0033560 | 25.61% | 30.53% |

**Result:** Five of six displacement studies did not meet the 5% criterion
for *both* adjacent grid changes. The braced lateral case did meet that
limited stabilization criterion, but not validation. **None of the six peak
global stress histories met the separate 10% screening criterion for both
steps.** Do not use any case's mesh-dependent peak as a certified allowable.

Potential contributors to investigate, rather than assume, include
insufficient through-thickness discretization, C3D4 artificial bending
stiffness, fixed-face edge singularities, and intersections of
Boolean-fused members. Further smaller grids, C3D10 or other suitable element
types, localized stress sampling away from singular edges, benchmark solutions,
and independent validation are needed. No published safety claim is supported.

The report is a **success for numerical observability and repeatability**,
but evidence that the current C3D4 implementation is **not yet generally
mesh-independent for these frames**. Do not relabel it converged.

## Quadratic element comparison — 2026-10-20

[Full native Gmsh + CalculiX 12-run comparison](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39499859849).
The solver now supports explicitly selected **C3D10** 10-node tetrahedra as well as
the backward-compatible **C3D4** formulation. It reorders Gmsh midside
tetrahedral nodes for CalculiX and distributes total force consistently over
planar quadratic triangular facets. Native cantilever and controlled frame
analyses passed solver completion and equilibrium tests.

For the same byte-identical CAD geometry under 250 N lateral loading, with
three requested mesh sizes 14/10/7 mm:

| Frame | Last C3D4 displacement change | Last C3D10 displacement change | C3D10 peak stress last change |
|---|---:|---:|---:|
| Rectangle under racking | 23.371% | **1.128%** | **13.910%** |
| Braced rectangle under racking | 3.965% | **0.303%** | **12.185%** |

Both C3D10 displacement histories meet the **two-successive-changes ≤ 5%**
screening condition. The rectangle's 7-mm deflection changed from 0.0194903 mm
under C3D4 to 0.0254805 mm under C3D10, consistent with earlier C3D4
bending stiffness concerns. **Neither global peak stress history passed
the separate two-step 10% stability screening.**

These comparisons are **numerical consistency evidence, not analytical
verification or physical validation**. They cover only two fused-solid frames
under one load direction, planar face-loading assumptions, and idealized
fixed faces. General C3D10 claims require broader geometry, curved face
quadrature, higher refinement, stress sampling away from singularities,
independent analytical benchmarks and physical results. Not for design signoff.

## Six-frame C3D10 comparison and stress localization — October 20, 2026

[Full native 36-solve evidence](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39501652909). All six specimens were solved at 14/10/7 mm using first-order C3D4 and quadratic C3D10 meshes with byte-identical STEP files, identical fixtures, material and loading. All six C3D10 maximum-displacement changes from 10 to 7 mm were **0.30–1.13%**, compared with **3.97–29.06%** for C3D4.

Global peak integration-point stress changed **8.28–15.72%** from 10 to 7 mm on the six C3D10 cases. The hotspot-localization diagnostic classifies actual integration-point stresses using approximate host-tetra corner centroids relative to physically fixed 20/40 mm exclusion distances from the bottom support and top loaded face. The global peak occurred about **158–161 mm above the base** in five cases, but roughly **22 mm above** in the laterally loaded rectangle.

Excluding 40 mm of the **top loaded plane** reduced the fine-step peak-stress changes in five upper-hotspot cases to **3.837%, 7.791%, 5.758%, 4.575%, and 3.284%**. The rectangular lateral case remained at **13.910%**, consistent with a hotspot near the lower support. The peak-position classification is **approximate**, not the actual Gauss-point position, and comparisons of successive global maxima do not track an identical material point.

**Limitations:** Improved displacement stability does not validate physical accuracy. Hotspot findings do not prove a singularity; abrupt load application and perfectly fused joints also merit study. Further work requires exact Gauss-point spatial localization, stress sampling at fixed physical coordinates, independent benchmarks, improved curved-surface load integration, and better joint idealization. No engineering sign-off is warranted.
