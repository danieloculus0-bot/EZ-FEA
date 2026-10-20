# EZ-FEA

Experimental structural analysis using a genuine Gmsh tetrahedral mesher and CalculiX native solver, with a separate educational browser workbench. The browser must not be mistaken for a server-side CAD solver.

## Current build and verification

**Reviewed:** 2026-10-20 · **Inspected `main`:** `6a930409775f` · **Status:** experimental research/beta, not an engineering certification.

- [Tests](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39503596467) — **Passed** at inspected `main`.
- [Real 3D Solver Smoke Test](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39503596430) — **Passed** at inspected `main`.

[Live Actions](https://github.com/danieloculus0-bot/EZ-FEA/actions) supersedes this recorded state.

## Implemented now

- Real STEP single-solid linear-static solves, multi-face fixtures/loads, numerical reaction-force and equilibrium checks.
- Six native frame specimens and repeatable multi-grid mesh refinement; C3D4/C3D10 element-order studies have independent CI.
- [Browser demo](https://danieloculus0-bot.github.io/EZ-FEA/) performs simplified beam physics and displays archived native results. Arbitrary uploaded CAD is **preview only**.

## Run and test

Install Gmsh and native CalculiX (`ccx`) and use `python -m ezfea.convergence --demo --meshes 12 8 5` for native multi-mesh evidence. [Full earlier installation and validation guide](docs/archive/README_2026-10-20_before_refresh.md).

## Unverified and out of scope

- Not validated for engineering sign-off. Mesh stability is not physical accuracy, and idealized fixed-edge stresses may diverge.
- Fused frame solids do not demonstrate realistic welds, pin joints, actuators, contact or nonlinear multi-body physics.
- Native solver CI success and the browser's educational beam result are different verification scopes.

## Next engineering work

Validate element formulations and convergence against analytical/physical benchmarks and build genuine mechanical joint modeling.

## Reference

- [Browser demo](https://danieloculus0-bot.github.io/EZ-FEA/)
- [Validation report](docs/VALIDATION.md)
- [Mesh refinement code](ezfea/convergence.py)
- [**Archived full README: development history, experiments and original setup details**](docs/archive/README_2026-10-20_before_refresh.md)
