// Always install a dependency-free, truly rotatable CAD preview first.
// If hardware WebGL or the 3D library fails, the visible truss and its
// rotation buttons still work; no dead controls beside a static SVG.
import "./truss_fallback.mjs?viewer=20261027c";
import("./truss_bundle.mjs?viewer=20261027c")
  .catch(()=>import("./truss_demo.mjs?viewer=20261027c"))
  .catch(error=>{
    const status=document.getElementById("trussViewerStatus");
    if(status)status.textContent=
      "Hardware 3D unavailable ("+error.message+"). Software 3D rotation is active; native solver physics is unchanged.";
  });
