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
