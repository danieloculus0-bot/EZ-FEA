# EZ-FEA Browser Lab

Static site intended for GitHub Pages. No application server or account needed.

## What's real in v0.2

- Open a genuine 150 x 25 x 10 mm cantilever example with a simple 3D display.
- Change the force, material and beam dimensions.
- Click Calculate beam to compute displacement with an 8-element Euler-Bernoulli beam FE stiffness model solved by Gaussian elimination. Peak stress is separately calculated from classical cantilever bending theory, not a 3D tensor field.
- Compare the finite-element tip deflection against the closed-form cantilever equation. Unit tests exercise numerical scaling and reference behavior.
- Preview STEP (.step, .stp) with the optional browser-only OpenCascade WebAssembly importer, plus STL and OBJ using Three.js. Imports run in the browser.
- Rotate and zoom the 3D representation. On imported parts, click Mark connection or Mark force, click a location, and export a JSON setup with reference points.

**What is NOT available on Pages:** Running Python, Gmsh, native CalculiX, executing full 3D FEA, validated safety ratings of uploaded parts, automatically interpreting bolted/welded/pinned physics, or autonomous BEAN review. All of these require further engineering and (for the Python solver) a computation server, or a separate future browser-compatible solver.

A STEP preview triangle or point does not automatically map to a mechanically correct constraint and is not a stable Gmsh surface ID. JSON exported here is a planning aid, not a complete solver input.

## Software

- Vanilla HTML/CSS/JavaScript and Three.js for interface.
- Open-source occt-import-js (WebAssembly) for optional STEP preview.
- Native server-side solver code remains in repository's Python ezfea/ package.
- Browser FE calculation is independent of Python and only applies to its built-in prismatic cantilever beam.

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
~~~

## Deploy on GitHub Pages

The workflow at .github/workflows/pages.yml uploads web/ on pushes to main. In GitHub repository Settings > Pages, choose GitHub Actions as the build/deploy source. The site is then expected at:

https://danieloculus0-bot.github.io/EZ-FEA/

Do not claim it is live until the deployment workflow finishes successfully.

This is intentionally experimental, not an engineering-certified system.
