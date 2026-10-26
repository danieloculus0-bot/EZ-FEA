# EZ-FEA: production-readiness plan

**Scope of the first release:** a dependable **single-solid, small-displacement, linear-elastic, static structural analysis tool** for carefully prepared STEP parts, with explicitly assigned isotropic material, restrained CAD faces, applied surface force/pressure, and reproducible Gmsh/CalculiX results.

Do not call arbitrary assemblies, contact, welds, bolts, pinned joints, buckling, fatigue, plasticity, dynamics, or a fully autonomous safety sign-off "supported" merely because the interface can display them.

## Existing evidence

- Gmsh/CalculiX native 3D runs and C3D4/C3D10 elements are implemented.
- The native test suite includes beam/axial analytical comparisons, reaction-force and reaction-moment checks, and repeated mesh studies.
- The browser beam lab is a separate educational demonstration, not a native CAD solver.
- Single-solid and carefully isolated contact demonstrations do **not** establish general assembly physics.
- The Joint Matrix can record candidate geometric mates and classifications; a selected joint classification is **not yet a solver connection**.
- Historic frame stress peaks remain mesh-sensitive. [Validation evidence](VALIDATION.md) describes the actual results and limits.

## Work toward a usable first release

| Priority | Work | Evidence required before claiming it is supported |
| --- | --- | --- |
| **P0: reject bad model setup** | Check fixture stability, mesh integrity/connectivity, element Jacobians, missing load faces, exact result node/element IDs, duplicate output, and unbalanced solver reactions. | Invalid models and corrupt/incomplete output must fail with actionable diagnostics; normal native regression solves must still pass. |
| **P0: units and source identity** | Preserve original STEP file/hash, clearly establish its source units and imported mm scale, record mesher/solver version, applied material and actual load/fixture faces. | Independent inch/mm equivalent STEP specimens must produce equivalent normalized physics; unknown unit provenance is made explicit, never silently trusted. |
| **P0: independent physics tests** | Expand verified C3D10 analytical benchmarks to axial, bending, shear and torsion cases. Include moment-sensitive and eccentric loads. | Fixed references independent of EZ-FEA, documented expected error bands, passing native CI, and archived raw solver files. |
| **P0: convergence and singularities** | Require more than one mesh for engineering review. Probe stresses at fixed physical positions away from artificial fixture/load singularities; report nonconverged metrics explicitly. | Demonstrate mesh refinement for each supported benchmark. A global peak at a singular corner cannot be advertised as a verified allowable stress. |
| **P1: engineering result report** | Show model assumptions, material, loads, supports, units, reactions, mesh checks, convergence, displacement, stress and unresolved warnings in one reviewable report. | Reviewer can reconstruct what was solved and distinguish numerical completion from independent engineering validation. |
| **P1: application and packaging** | Reliable STEP import, mesh preview, visible fixture/load selection, C3D10 selection, solver progress and actionable failures across supported desktop installs. | Repeatable clean-install test with native Gmsh/CalculiX, real example model, saved inputs/results, and no sample data represented as real results. |
| **P2: assembly capability** | Progress from face-evidence-based mate detection to parameterized, confirmed bonded/tied, contact, pin and bolt models individually. | Each joint family has independent DOF/load-transfer/reaction/separation benchmarks before use in multi-part engineering decisions. |

These priorities are **engineering work items**, not artificial restrictions on merging code to `main`. Implement and merge increments continuously, then run native CI. A supported-use claim needs evidence; an experimental feature can exist and be tested before that claim.

## Current immediate push: output integrity and fixture preflight

The October 26, 2026 hardening work adds:

- Exact CalculiX displacement/reaction node and stress element identity checks against the meshed case, not merely matching counts.
- Rejection of duplicate node/integration-point records and overflowed derived quantities.
- Legacy single-face rigid-body restraint checks using the same six-mode test as multi-face cases.
- Regression tests, including correct 3D synthetic fixtures and intentionally invalid supports.

[Inspect ongoing workflows](https://github.com/danieloculus0-bot/EZ-FEA/actions) for live status. A passing unit test is not an all-purpose native validation certificate.

## Release terminology

- **Tests pass:** the stated source revision passed specified automated tests.
- **Native solver verified:** Gmsh and CalculiX performed a documented run with expected numerical outputs.
- **Numerically converged:** defined quantities stabilized under the chosen refinement procedure, with exceptions identified.
- **Validated for a specific use:** independently compared against accepted analytical, benchmark or experimental evidence within an explicitly defined envelope.
- **Production-ready for that use:** the previous work plus operable installation, input controls, traceable results and a qualified engineering review process.

Every individual result must still be reviewed against its geometry, boundary conditions, material properties and real loading. BEAN can assist with explaining risks and proposing tests but cannot replace physics verification or a qualified reviewer.

See also: [Verification and validation plan](VALIDATION.md), [Pressure/contact limitations](PRESSURE_CONTACT.md), [Joint Matrix scope](JOINT_MATRIX.md).
