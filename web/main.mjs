import { analyzeBeam, PRESETS } from "./beam.mjs";
const byId=(id)=>document.getElementById(id);
let viewer=null;
let mode="demo";
let currentFile=null;
let points={fixed:null,load:null};
let calculated=null;

function announce(msg){byId("modelStatus").textContent=msg;}
function number(id){return Number(byId(id).value);}
function beamInput() {
  return {
    length:number("length"),
    width:number("width"),
    height:number("height"),
    force:number("force"),
    modulus:PRESETS[byId("material").value].modulus,
    yield:PRESETS[byId("material").value].yield
  };
}
function format(value,digits=3){
  if(!Number.isFinite(value))return "—";
  if(value===0)return "0";
  if(Math.abs(value)>=10000||Math.abs(value)<0.001)return value.toExponential(2);
  return Number(value.toPrecision(digits)).toLocaleString("en-US",{maximumFractionDigits:6});
}
function clearResults(){
  calculated=null;
  byId("resultValues").hidden=true;
  byId("resultPlaceholder").hidden=mode!=="demo";
  byId("cadNoSolver").hidden=mode==="demo";
}
function updateMode(){
  const demo=mode==="demo";
  byId("beamControls").hidden=!demo;
  byId("demoConnections").hidden=!demo;
  byId("customConnections").hidden=demo;
  byId("runBtn").hidden=!demo;
  byId("runCaption").hidden=!demo;
  byId("viewerOverlay").hidden=!demo;
  byId("viewBadge").textContent=demo?"BEAM EXAMPLE":"CAD PREVIEW ONLY";
  byId("viewerHeading").textContent=demo?"Example beam":(currentFile?.name||"Your model");
  byId("viewerSub").textContent=demo?"Real 2D beam calculation, visualized in 3D":"Geometry only. No structural solve has been performed.";
  byId("modeDesc").textContent=demo?
    "Try the example and see real calculated displacement and bending stress.":
    "We can preview and mark locations on this part, but a full 3D FEA solver is not available on GitHub Pages.";
  byId("connectionHint").textContent=demo?
    "The beam is held still on the left. Its far end gets pushed down.":
    "Choose a marker, then click the model where the connection or force acts.";
  clearResults();
}
function renderDemo(){
  if(mode!=="demo"||!viewer)return;
  try{
    const p=beamInput();
    if(!(p.length>0&&p.width>0&&p.height>0))return;
    viewer.showDemo(p,PRESETS[byId("material").value].tint);
  }catch(err){announce("Preview update: "+err.message);}
}
function useDemo(){
  mode="demo";
  currentFile=null;
  points={fixed:null,load:null};
  byId("fileInput").value="";
  byId("partInfo").textContent="Example: 150 × 25 × 10 mm beam";
  updateMode();
  renderDemo();
  announce("Example beam ready. Enter a force and calculate.");
}
function calculate(){
  if(mode!=="demo")return;
  try{
    const b=analyzeBeam(beamInput(),8);
    calculated=b;
    byId("resultPlaceholder").hidden=true;
    byId("cadNoSolver").hidden=true;
    byId("resultValues").hidden=false;
    byId("rDeflection").textContent=format(b.deflection_mm)+" mm";
    byId("rStress").textContent=format(b.peak_bending_stress_mpa)+" MPa";
    byId("rSafety").textContent=b.safety_factor_yield==null?"Not applicable":format(b.safety_factor_yield,4)+" ×";
    const ratio=b.nominal_yield_mpa>0?100*b.peak_bending_stress_mpa/b.nominal_yield_mpa:0;
    byId("rPercent").textContent=format(ratio)+"%";
    byId("stressFill").style.width=Math.max(0,Math.min(ratio,100))+"%";
    byId("stressFill").classList.toggle("warn",ratio>=90);
    const sign=b.exceeds_nominal_yield?"Exceeds the example material's nominal yield.":
      "Below the example material's nominal yield in this simplified beam model.";
    byId("resultSummary").textContent=sign+" This is NOT a prediction of whole-part safety.";
    let scale=1;
    if(viewer)scale=viewer.showBending(b,number("height"));
    announce("Beam solved numerically. Orange centerline shows bending at "+format(scale,3)+"× visual scale.");
  }catch(err){
    clearResults();
    announce("Input error: "+err.message);
    alert("Check the values: "+err.message);
  }
}
function setupSelection(){
  if(mode==="demo")return;
  const fixed=points.fixed?"Connection marked":"Connection not marked";
  const load=points.load?"Force location marked":"Force location not marked";
  byId("selectionStatus").textContent=fixed+" · "+load;
}
function beginMark(which){
  if(mode!=="custom")return;
  if(!viewer){
    announce("The 3D viewer isn't available. Reload with an internet connection.");
    return;
  }
  viewer.setPicking(which);
  announce("Click a spot on the model to mark "+(which==="fixed"?"its connection":"where force acts")+".");
}
function onPick(which,location){
  points[which]=location;
  setupSelection();
  announce((which==="fixed"?"Connection":"Force location")+" marked. This is a visual reference, not a solver constraint.");
}
function downloadSetup(){
  if(!currentFile)return;
  const preset=PRESETS[byId("material").value];
  const setupPayload={
    schema:"ezfea.web.setup.v1",
    source_file:currentFile.name,
    source_file_size_bytes:currentFile.size,
    source_file_included:false,
    analysis_status:"NOT_RUN",
    engine:"none (GitHub Pages preview only)",
    connection_point_preview_mm:points.fixed,
    load_point_preview_mm:points.load,
    intended_vertical_load_n:-number("force"),
    material_name:preset.name,
    modulus_mpa:preset.modulus,
    nominal_yield_mpa:preset.yield,
    important:"Preview coordinates and markers are not Gmsh CAD surface IDs. Recheck connections and units in the 3D solver. Keep original CAD source file."
  };
  const data=new Blob([JSON.stringify(setupPayload,null,2)],{type:"application/json"});
  const url=URL.createObjectURL(data);
  const a=document.createElement("a");
  a.href=url;
  a.download="ezfea_setup.json";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),250);
}
async function loadScript(source) {
  return new Promise((resolve,reject)=>{
    const script=document.createElement("script");
    script.src=source;
    script.onload=resolve;
    script.onerror=()=>reject(new Error("Cannot load the free CAD importer. Check network access."));
    document.head.appendChild(script);
  });
}
let occtPromise=null;
async function readStep(buffer) {
  if(!occtPromise){
    occtPromise=(async()=>{
      if(!globalThis.occtimportjs)await loadScript("https://cdn.jsdelivr.net/npm/occt-import-js@0.0.23/dist/occt-import-js.js");
      if(!globalThis.occtimportjs)throw new Error("Browser STEP importer unavailable.");
      return globalThis.occtimportjs({
        locateFile:(filename)=>"https://cdn.jsdelivr.net/npm/occt-import-js@0.0.23/dist/"+filename
      });
    })().catch((error)=>{occtPromise=null;throw error;});
  }
  const occt=await occtPromise;
  const result=occt.ReadStepFile(new Uint8Array(buffer),{
    linearUnit:"millimeter",
    linearDeflectionType:"bounding_box_ratio",
    linearDeflection:0.05,
    angularDeflection:0.35
  });
  if(!result?.success)throw new Error("Unable to import this STEP file. Try a smaller or valid solid STEP.");
  return result;
}
async function openPart(file){
  if(!file)return;
  const name=file.name.toLowerCase();
  const ext=name.slice(name.lastIndexOf("."));
  if(![".step",".stp",".stl",".obj"].includes(ext)){
    announce("Supported models: STEP, STL or OBJ.");
    return;
  }
  if(file.size>50*1024*1024){announce("File is over the 50 MB browser-preview limit.");return;}
  if(!viewer){announce("3D preview unavailable. Browser may be offline or graphics unsupported.");return;}
  announce("Opening "+file.name+" locally... Large STEP models may take a moment.");
  try{
    const buffer=await file.arrayBuffer();
    if(ext===".step"||ext===".stp")viewer.showStep(await readStep(buffer));
    else if(ext===".stl")viewer.showStl(buffer);
    else viewer.showObj(await file.text());
    mode="custom";
    currentFile=file;
    points={fixed:null,load:null};
    byId("partInfo").textContent=file.name+" · "+Math.max(1,Math.round(file.size/1024))+" KB";
    updateMode();
    setupSelection();
    announce("Part preview ready. Mark a connection or force location. Full 3D analysis is not online yet.");
  }catch(err){
    announce("Unable to open model: "+err.message);
    alert("Unable to preview this model.\n"+err.message);
  }
}
function start(){
  byId("demoBtn").addEventListener("click",useDemo);
  byId("resetDemoTop").addEventListener("click",useDemo);
  byId("runBtn").addEventListener("click",calculate);
  byId("resetView").addEventListener("click",()=>viewer?.focus());
  byId("fileInput").addEventListener("change",e=>openPart(e.target.files?.[0]));
  byId("setFixedBtn").addEventListener("click",()=>beginMark("fixed"));
  byId("setLoadBtn").addEventListener("click",()=>beginMark("load"));
  byId("saveSetup").addEventListener("click",downloadSetup);
  byId("material").addEventListener("change",()=>{
    const p=PRESETS[byId("material").value];
    byId("materialNote").textContent=p.name+": E "+p.modulus.toLocaleString()+" MPa, nominal yield "+p.yield+" MPa. Verify your actual material.";
    if(mode==="demo"){clearResults();renderDemo();}
  });
  for(const id of ["length","width","height"]){
    byId(id).addEventListener("change",()=>{
      if(mode==="demo"){
        byId("partInfo").textContent="Example: "+number("length")+" × "+number("width")+" × "+number("height")+" mm beam";
        clearResults();renderDemo();
      }
    });
  }
  byId("force").addEventListener("input",()=>{
    if(mode==="demo")clearResults();
  });
  const drop=byId("dropZone");
  for(const event of ["dragenter","dragover"]){
    drop.addEventListener(event,e=>{e.preventDefault();drop.classList.add("dragover");});
  }
  for(const event of ["dragleave","drop"]){
    drop.addEventListener(event,e=>{e.preventDefault();drop.classList.remove("dragover");});
  }
  drop.addEventListener("drop",(e)=>{const file=e.dataTransfer?.files?.[0];if(file)openPart(file);});
  updateMode();
  import("./viewer.mjs").then(({Viewer})=>{
    viewer=new Viewer(byId("viewerCanvas"),onPick);
    renderDemo();
  }).catch(err=>{
    byId("fallback").hidden=false;
    announce("3D preview unavailable: "+err.message+". Beam calculation still works.");
  });
}
start();
