# EZ-FEA

Experimental structural analysis using a genuine Gmsh tetrahedral mesher and CalculiX native solver, with a separate educational browser workbench. The browser must not be mistaken for a server-side CAD solver.

## Current build and verification

**Reviewed:** 2026-10-20 · **Inspected `main`:** `6a930409775f` · **Status:** experimental research/beta, not an engineering certification.

- [Tests](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39503596467) — **Passed** at inspected `main`.
- [Real 3D Solver Smoke Test](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39503596430) — **Passed** at inspected `main`.

[Live Actions](https://github.com/danieloculus0-bot/EZ-FEA/actions) supersedes this recorded state.

## Implemented now

- Real STEP single-solid linear-static solves, multi-face fixtures/loads, numerical reaction-force **and reaction-moment** equilibrium checks.
- **Native force introduction:** choose an entire-face distributed load or a positionable Gaussian traction footprint with specified total XYZ force, center XYZ and spread (mm). Real T3/T6 surface quadrature produces equivalent FE nodal loads and reports the actual resultant force, eccentric moment and reaction balance. This approximates a pressure pad; it does **not** simulate nonlinear physical contact.
- **True native normal pressure (experimental backend):** CalculiX `*DSLOAD P` applied to real tetrahedral exterior faces, independently checked against pressure-integrated total force and support reaction moments. The [four-solve native benchmark](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39508482477) passed for C3D4 and C3D10.
- **Real separable contact proof:** two independent C3D8 steel solids with a genuine CalculiX frictionless surface-to-surface contact pair transferred **962.7 N** in compression, versus **0 N** with the contact pair disabled and approximately **0 N** during separation. This is an [isolated controlled specimen](docs/PRESSURE_CONTACT.md), not arbitrary multibody STEP support.
- **Grounded STEP assembly mate graph + Joint Matrix prototype:** auto-detect candidate opposing planar CAD mates, preserve part/face IDs and reachability from a grounded component, and review joints in an Excel-like dropdown / drag-to-fill grid. Geometry never guesses welded/bolted/pinned physics. [Joint Matrix instructions](docs/JOINT_MATRIX.md) · [standalone spreadsheet preview](https://danieloculus0-bot.github.io/EZ-FEA/joint-matrix.html).
- Six native frame specimens and repeatable multi-grid mesh refinement; C3D4/C3D10 element-order studies have independent CI.
- [Browser demo](https://danieloculus0-bot.github.io/EZ-FEA/) performs simplified beam physics and displays archived native results. Arbitrary uploaded CAD is **preview only**.

## Run and test

Install Gmsh and native CalculiX (`ccx`) and use `python -m ezfea.convergence --demo --meshes 12 8 5` for native multi-mesh evidence. [Full earlier installation and validation guide](docs/archive/README_2026-10-20_before_refresh.md).

## Latest physics verification (October 20, 2026)

- [**12 real load-footprint simulations**](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39507346099) using C3D4/C3D10 on 10 and 7 mm meshes: uniform whole-face traction versus centered and eccentric finite Gaussian pads, all at the same 100 N axial force. At 7 mm C3D10, moving the pad raised the applied bending moment from **500 to 679 N·mm** and peak recorded native stress from **1.03 to 2.44 MPa**. Every case passed numerical force and moment equilibrium. [Native workflow](https://github.com/danieloculus0-bot/EZ-FEA/actions/workflows/load-introduction.yml).
- [36 real frame solves comparing C3D10 Gauss-coordinate stress reconstruction](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39505031019): same XYZ stress sampling; **8/24** physical probe histories met the provisional 10% two-step criterion, compared with **1/24** using element-mean stress recovery. Six other probes remain boundary-adjacent; ten are still mesh-sensitive.
- [12 native analytical axial and bending comparison solves](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39505678274): at 7 mm mesh, **C3D10** cantilever deflection was 0.200384 mm against an Euler–Bernoulli reference of 0.200000 mm (0.192% difference). At the same fixed material stress point, C3D10 produced 18.979 MPa against a 19.3644 MPa analytical bending stress (1.99% difference). C3D4 was much too stiff at this mesh density.
- [Automated native analytical benchmark workflow](https://github.com/danieloculus0-bot/EZ-FEA/actions/workflows/analytic-stress-benchmark.yml) now tests tensile and bending behavior independently of the solver code; full details, limits and methods remain in [engineering validation notes](docs/VALIDATION.md).

These measurements support a limited experimental solver regression baseline, **not** general-purpose engineering certification. The [browser demo](https://danieloculus0-bot.github.io/EZ-FEA/) is deliberately unchanged.

## Unverified and out of scope

- Not validated for engineering sign-off. Mesh stability is not physical accuracy, and idealized fixed-edge stresses may diverge.
- The generic `Analysis` API still handles only one STEP solid; the independently verified two-brick frictionless contact specimen does **not** constitute arbitrary STEP assemblies, welds, pins, bolts or actuator joint support.
- Native solver CI success and the browser's educational beam result are different verification scopes.

## Next engineering work

Extend planar geometric mates to verified face intersections, cylindrical axes and hole patterns; preserve explicit joint classifications and translate only confirmed physical models into native contact/connector physics. Continue pressure API, general multibody STEP contact, and independent shear/torsion benchmarks.

## Reference

- [Browser demo](https://danieloculus0-bot.github.io/EZ-FEA/)
- [Validation report](docs/VALIDATION.md)
- [Native pressure & separable contact evidence](docs/PRESSURE_CONTACT.md)
- [Grounded assembly Joint Matrix and real STEP mate-detection test](docs/JOINT_MATRIX.md)
- [Mesh refinement code](ezfea/convergence.py)
- [**Archived full README: development history, experiments and original setup details**](docs/archive/README_2026-10-20_before_refresh.md)
