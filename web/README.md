# EZ-FEA Browser Lab

Static site intended for GitHub Pages. No application server or account needed.

## What's real in v0.2

- Open a genuine 150 x 25 x 10 mm cantilever example with a simple 3D display.
- Change the force, material and beam dimensions.
- Click Calculate beam to compute displacement with an 8-element Euler-Bernoulli beam FE stiffness model solved by Gaussian elimination. Peak stress is separately calculated from classical cantilever bending theory, not a 3D tensor field.
- Compare the finite-element tip deflection against the closed-form cantilever equation. Unit tests exercise numerical scaling and reference behavior.
- Preview STEP (.step, .stp) with the optional browser-only OpenCascade WebAssembly importer, plus STL and OBJ using Three.js. Imports run in the browser.
- Rotate and zoom the 3D representation. On imported parts, click Mark connection or Mark force, click a location, and export a JSON setup with reference points.
- View BEAN's official smiling green mascot, animated with a gentle idle float and contextual response nod (disabled when reduced motion is requested).
- Use BEAN browser-side engineering checks: assess actual beam FE result quantities, stress usage vs nominal yield, deflection ratio, agreement with the analytical beam reference, and short-beam/shear-model limitations; or review which CAD locations remain merely unverified visual marks.
- Expand **See 3D physics results from the real engine** to view three provenance-linked, previously calculated Gmsh/CalculiX solid-frame studies. The data come from GitHub Actions run [39488256233](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39488256233) and are displayed unchanged from the recorded case metrics, not recomputed in the browser.

**What is NOT available on Pages:** Running Python, Gmsh, native CalculiX, executing new full 3D FEA on uploaded parts, validated safety ratings of uploaded parts, mechanically determining physical bolted/welded/pinned connections, or live autonomous BEAN Core review. All of these require further engineering and (for the Python solver) a computation server, or a separate future browser-compatible solver.

A STEP preview triangle or point does not automatically map to a mechanically correct constraint and is not a stable Gmsh surface ID. JSON exported here is a planning aid, not a complete solver input.

## Software

- Vanilla HTML/CSS/JavaScript and Three.js for interface.
- Open-source occt-import-js (WebAssembly) for optional STEP preview.
- Native server-side solver code remains in repository's Python ezfea/ package.
- Browser FE calculation is independent of Python and only applies to its built-in prismatic cantilever beam.
- The BEAN browser advisor is a transparent deterministic engineering-check module, not the BEAN Core runtime or an LLM; it never claims to run native physics or certify a model.
- The official mascot image is referenced from the project's BEAN repository, with a locally stored official BEAN SVG as fallback. Animations respect the `prefers-reduced-motion` setting.
- Recorded solver evidence lives in `web/data/frame_studies.json` with source workflow, SHA, mesh nominal size and assumptions. It is a fixed reference dataset, not a live GitHub workflow API or an analysis of user-uploaded geometry.

External JS/Wasm code is delivered from cdn.jsdelivr.net. CAD files are loaded from local browser memory and not sent to an EZ-FEA server. Avoid using confidential CAD unless you approve of the page and its third-party script dependencies.

## Local use / tests

From repository root:

~~~sh
python -m http.server 8000 --directory web
~~~

Open http://localhost:8000 to test interface (requires internet to load WebGL dependencies).

~~~sh
node --test web/tests/*.test.mjs
node --check web/main.mjs
node --check web/viewer.mjs
node --check web/bean_advisor.mjs
~~~

## Deploy on GitHub Pages

The workflow at .github/workflows/pages.yml uploads web/ on pushes to main. In GitHub repository Settings > Pages, choose GitHub Actions as the build/deploy source. The site is then expected at:

https://danieloculus0-bot.github.io/EZ-FEA/

Do not claim it is live until the deployment workflow finishes successfully.

This is intentionally experimental, not an engineering-certified system.
