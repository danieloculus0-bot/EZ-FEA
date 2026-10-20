# EZ-FEA

Simple STEP-to-structural-FEA desktop app powered by the free **Gmsh** mesher and **CalculiX** physics solver.

**v0.1 EXPERIMENTAL. Not validated for professional engineering sign-off.**

## Windows installation

Install Python 3.10+ and the free CalculiX CCX solver from https://www.calculix.de/. Put ccx.exe on PATH or point EZFEA_CCX at its full path.

In PowerShell, from the EZ-FEA folder:

~~~powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
~~~

Choose a STEP solid, its fully fixed connection face, its loaded face and total XYZ force. Click RUN ANALYSIS. Real solver files and records go into the runs directory. View the analysis.frd result with free CalculiX GraphiX (cgx).

## Scope

- Real Gmsh STEP import and 3D linear C3D4 tetrahedral mesh.
- Face-based connections (all three displacement degrees fixed).
- Force distributed over a selected surface by triangle area.
- Single-material, linear elastic, static CalculiX solves.
- N/mm/MPa units. Model STEP dimensions must already be millimeters.
- Recorded CAD SHA256, inputs, mesh statistics, solver logs and native result files.
- BEAN handoff as JSON. Optional verified BEAN Core log-note inbox interface if EZFEA_BEAN_INBOX is set to the same location as BEAN_INBOX_DIR. BEAN logs a factual run record, not an engineering review.
- Automated tests and optional full solver smoke test.

**Important limits:** first-order C3D4 is inaccurate for some bending scenarios; no automatic mesh convergence, no contact/bolts/pins/weld physics, no nonlinear material law, no print orientation effects, no built-in result contour viewer, no automatic factor of safety. Yield strength is stored for later use. No fabricated results on failures. Gmsh and CalculiX were not installed in the development environment, so the end-to-end solve remains to be tested on a solver-equipped PC.

Run automated tests:

~~~sh
python -m unittest discover -s tests -v
~~~

Enable installed-solver smoke testing with environment variable EZFEA_RUN_INTEGRATION=1.

## Validation

See docs/VALIDATION.md. Target ASME V&V 10-2019 (R2025), relevant NAFEMS benchmarks, mesh convergence, independent results and physical measurements.

## Licensing

EZ-FEA is GPL-3.0-or-later. Gmsh uses GPL-2.0-or-later with special exceptions, and its license conditions must be respected when distributing. CalculiX is free and open source and is called as an external executable. There is no paid solver requirement.

BEAN_FEA_Genius can later provide advisory analysis and comparisons; it must never be represented as the source of physics calculations.
