# EZ-FEA native validation snapshot, 26 October 2026

This snapshot distinguishes **completed native calculations**, **screening checks**, and **unsupported conclusions**. These numbers are tied to GitHub Actions executions; never substitute the educational browser demo for the native solver.

## Native equivalent-unit STEP sources

[Successful inch/mm Gmsh + CalculiX run](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/40398030056)

The native benchmark builds two separate STEP files representing a 100 x 10 x 10 mm linear elastic bar. One uses real millimeter STEP units; the other has numerically inch-sized geometry with a conversion-based INCH STEP length-unit context (25.4 mm/inch). Both are imported through the EZ-FEA millimeter-normalizing CAD path and actually meshed/solved using C3D10.

- The imported physical dimensions were each 100.0000002 x 10.0000002 x 10.0000002 mm within STEP/geometry tolerance.
- Displacement differed by 0.002726% (relative error 2.72588e-5).
- Fixed physical-location stress differed by approximately 0.00000084% (relative error 8.37432e-9).
- Both solvers passed force and moment equilibrium checks.

**Meaning:** the two unit representations passed this particular importer/physics regression. Other STEP exporters, mixed-unit assemblies, and incomplete CAD unit metadata are not yet independently verified.

## Independent beam/axial references and stress-probe screening

[Six-grid native axial/bending/shear reference workflow](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/40398599231)

- Axial C3D10 fixed midspan stress: approximately 1.0 MPa for nominal F/A = 1.0 MPa at 14, 10, 7 mm.
- Bending C3D10, 7 mm: 0.200384 mm maximum displacement versus 0.200000 mm classical tip estimate, 0.192% discrepancy.
- Bending C3D10, 7 mm: fixed-location |sigma_x| 18.979 MPa versus nominal 19.3644 MPa, about 1.99% discrepancy.
- Transverse shear at the new fixed neutral-axis-adjacent probe: 7 mm C3D10 = 1.0795 MPa versus classical rectangular-beam approximation 1.4983 MPa (27.9% discrepancy).
- C3D4 shear on the same 7 mm grid differed by about 145% from that approximation. It is **not** established as reliable for the demonstrated coarse-grid transverse shear.
- Fixed-location probe histories are checked across repeated meshes. Failing or boundary-adjacent probes are explicitly reported as needing further refinement.

[Refined C3D10 probe study at 7, 5, 3.5 mm](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/40398900423):

| Mesh | C3D10 fixed shear stress | Reference discrepancy | C3D10 fixed bending stress | Bending reference discrepancy |
| --- | ---: | ---: | ---: | ---: |
| 7 mm | 1.0795 MPa | 27.9% | 18.979 MPa | 1.99% |
| 5 mm | 1.5853 MPa | 5.81% | 19.4319 MPa | 0.349% |
| 3.5 mm | 1.4609 MPa | 2.49% | 19.3021 MPa | 0.322% |

The shear agreement improved with these refinements but the stress history remained nonmonotonic; that is **not** the same as proven asymptotic convergence. The analytical shear distribution is an approximate beam-theory comparison, not an exact solution to the clamped 3D boundary-value problem.

[Follow-up finer-mesh study at 2.5 mm](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/40399064952) adds another physical mesh and archives native output.

## Next milestones

1. Establish stress-probe stabilization in multiple physically meaningful material points, not just a single peak; determine sensitivity to probe placement and meshing algorithm.
2. Verify mesh quality and **curved C3D10 Jacobians** against independent examples; the current Gmsh minSICN check is a rejection screen, not a full geometry/solver verification.
3. Add a physically well-defined native torsion case with controlled pure torque and independently established reference results. Analytical torsion formulas have unit tests, but **that is not yet a native torsion benchmark**.
4. Compare against published engineering benchmark cases and a qualified reviewer or measured parts before claiming a design-use validation envelope.

**Release claim remains experimental.** An equilibrium pass, small reference discrepancy, or stabilized three-grid quantity by itself does not demonstrate suitability for safety-critical design or engineering sign-off.
