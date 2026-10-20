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
