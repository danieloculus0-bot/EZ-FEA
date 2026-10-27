// Pages serves a self-contained Three.js bundle so 3D rotation does not
// depend on third-party CDNs. Local Python dev servers fall back to sources.
import("./truss_bundle.mjs").catch(()=>import("./truss_demo.mjs")).catch(error=>{
  const status=document.getElementById("trussViewerStatus");
  if(status)status.textContent="3D model failed to start: "+error.message+
    ". Reopen the page or use a current browser with WebGL enabled.";
});
