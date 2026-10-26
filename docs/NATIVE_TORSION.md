# Native circular-shaft torsion benchmark

This development feature introduces a **real CalculiX C3D10 torsion experiment** rather than treating bending or a force pair as an already validated torque solver.

## What is calculated

1. Gmsh/OpenCASCADE creates a STEP **solid circular shaft**, then reloads the STEP using explicit millimeter import settings and meshes a second-order tetrahedral volume.
2. The inlet circular face is restrained in X, Y and Z. The outlet circular face receives a **consistent tangential traction** `t_y=-alpha*z, t_z=alpha*y`, integrated over actual T6 isoparametric triangles using a seven-point quadrature rule.
3. The equivalent nodal forces are normalized to a verified net torque in N·mm. An audit verifies nearly zero net force and negligible unintended bending moments before release to CalculiX.
4. CalculiX actually solves the 3D shaft. The script reads the solver's measured tip displacements and support reaction forces, rejects missing/incorrect node identities, fits tip rotation from all circular end nodes, and calculates the fixed-end reaction torque.
5. The independently derived reference is the Saint-Venant linear-elastic round-shaft equation `theta = T*L/(G*J)`, where `G=E/[2(1+nu)]` and `J=pi*r^4/2`. Two mesh resolutions are required before the CI workflow is accepted.

The benchmark distinguishes **applied-torque correctness**, **reaction equilibrium**, and **displacement/twist agreement**. A successful native solve or reaction balance alone is not physical accuracy.

## Run

Requires real Gmsh Python bindings and CalculiX `ccx`:

```bash
python -m unittest discover -s tests -p test_torsion_benchmarks.py -v
python -m ezfea.torsion_benchmarks --out runs/native_torsion --meshes 6 4
```

[Native torsion workflow](https://github.com/danieloculus0-bot/EZ-FEA/actions/workflows/native-torsion.yml) archives source STEP, CalculiX `.inp/.dat/.frd`, mesh details, nodal-force torque audits and the numerical comparison report. Consult the actual workflow result before claiming a mesh study passed.

## Supported envelope

- One continuous **solid circular** shaft, 100 mm long and 10 mm radius in the default specimen.
- One end completely fixed, other end subjected to a pure tangential end traction.
- Isotropic, linear elasticity, small deformation, C3D10 tetrahedra and a controlled mesh density.
- Default input: `T=10000 N·mm`, `E=200000 MPa`, `nu=0.25`, with analytical twist and outer-fiber shear provided by the existing independent mechanics reference module.

## Not yet established

No general-purpose torque application control is connected into EZ-FEA's main single-solid `Analysis` UI or assemblies. There are no measured results yet for arbitrary cross-sections, fillet/weld stress concentration, torque-transmitting fasteners, nonlinear contact, buckling, plasticity, dynamic torsion, fatigue or failure initiation. This limited shaft benchmark is a regression gate, **not structural-engineering sign-off**.

Next: add fixed-physical-coordinate shear stress comparisons and additional grids, then introduce a carefully scoped face-level torque `Analysis` load type, keeping its resultant-force and moment audits explicit.
