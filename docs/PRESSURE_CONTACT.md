# EZ-FEA — Native pressure and experimental contact verification

Last verified: October 20, 2026

[**Native CI: pressure + two-body contact, successful**](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39508482477)

## 1. What is implemented

**Real normal pressure:** `ezfea/native_pressure.py` builds a genuine CalculiX `*SURFACE,TYPE=ELEMENT` from Gmsh CAD face triangles matched to the actual exterior faces of C3D4/C3D10 elements. It applies a positive compressive pressure through CalculiX `*DSLOAD` with label `P`, rather than disguising it as a prescribed nodal force. T3/T6 isoparametric integration independently calculates the expected pressure resultant and moment. Unknown, ambiguous or interior element faces are rejected. The verified experimental entry point is `ezfea.pressure_benchmarks`.

**Actual two-body contact:** `ezfea/contact_benchmarks.py` generates *two separate*, unmerged steel solids with distinct node IDs, a flat coincident interface, a native CalculiX `*CONTACT PAIR, TYPE=SURFACE TO SURFACE`, and a frictionless linear pressure-overclosure penalty relation. The contact is mechanical and separable: the base supports register load under compression, not when the interface is opened or when the contact pair is disabled. This is a controlled two-brick **C3D8 proof-of-physics only**, not yet arbitrary multibody STEP import or a supported standard EZ-FEA `Analysis` setting.

`FaceLoad` and `FaceFootprintLoad` are still the **existing single-solid analysis API** and apply conservative equivalent nodal force vectors. Do not confuse them with true pressure or solved contact.

## 2. Native evidence: normal pressure

Four true CalculiX solves, same steel 100 × 10 × 10 mm bar, x=0 fully fixed, 1 MPa positive pressure on x=100 end face. The area is 100 mm², so the independent integrated pressure is −100 N in X.

| Native tet | Requested mesh | Pressure resultant X | Max displacement | Reaction-force residual | Reaction-moment residual |
|---|---:|---:|---:|---:|---:|
| C3D4 | 10 mm | −100 N | 0.000497122 mm | 6.50e−7% | 3.36e−8% |
| C3D4 | 7 mm | −100 N | 0.000498488 mm | 5.02e−6% | 3.90e−7% |
| C3D10 | 10 mm | −100 N | 0.000498579 mm | 2.21e−6% | 4.29e−7% |
| C3D10 | 7 mm | −100 N | 0.000498683 mm | 2.72e−6% | 2.23e−7% |

The job archives CAD, CalculiX `.inp`, `.dat`, `.frd`, solver logs, pressure audit and reaction checks. Values are from [the actual successful run](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39508482477).

## 3. Native evidence: contact releases under tension

Each of two C3D8 cubes is 10 × 10 × 10 mm, E=200000 MPa, ν=0.26; they meet at z=10 mm without sharing mesh nodes. The lower cube is supported at its base; the top of the upper cube is prescribed ±0.001 mm vertical travel. The interface is frictionless with a linear penalty stiffness 100000 MPa/mm.

| Experiment | Contact present | Upper prescribed Z | Measured reaction at the base |
|---|---|---:|---:|
| Compression | yes | −0.001 mm | **962.744 N** |
| Compression control | no | −0.001 mm | **0 N** |
| Opening | yes | +0.001 mm | **approximately 0 N** |

The base reaction is **measured in native CalculiX RF data**, not estimated analytically or set to a desired expected value. All three jobs completed, and the run checks for nonzero compressive transfer and negligible transfer for the control and opening states.

## 4. Run locally

Requires Gmsh's Python module and native CalculiX `ccx` on PATH:

```bash
python -m unittest discover -s tests -p test_native_pressure.py -v
python -m unittest discover -s tests -p test_native_contact.py -v
python -m ezfea.pressure_benchmarks --out runs/native_pressure
python -m ezfea.contact_benchmarks --out runs/native_contact
```

Or start the [native GitHub Actions workflow](https://github.com/danieloculus0-bot/EZ-FEA/actions/workflows/native-pressure-contact.yml), which stores full artifacts.

## 5. Not yet supported

The first pressure implementation is a verified **native backend entry point**, not yet integrated as a `FaceNormalPressureLoad` option throughout the generic single-solid `Analysis` schema. The contact specimen is a verified **isolated two-brick proof**, not yet integrated with arbitrary Gmsh STEP assembly meshing, surface-pair selection, contact stabilization, mesh convergence or postprocessing.

There is **no** demonstrated bolt pretension, friction, bearing clearance, curved Hertzian contact, wear, plasticity, crack initiation, nonlinear shell-to-solid transition, or qualified weld assessment. Reaction balance alone cannot validate a contact pressure distribution.

**Next engineering targets:** (1) extend Gmsh import to preserve distinct solids and labeled exterior surface pairs; (2) integrate pressure types into `Analysis` with truthful pressure-specific load/reaction bookkeeping; (3) extend contact pair solving to supported two-solid STEP assemblies, with penetration/clearance and contact-force convergence checks; (4) only after those pass, investigate preload, friction, and bearing/bolt examples.

**No engineering signoff:** all findings remain experimental, and the browser educational demonstration is intentionally unchanged.
