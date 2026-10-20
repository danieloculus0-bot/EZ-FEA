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
