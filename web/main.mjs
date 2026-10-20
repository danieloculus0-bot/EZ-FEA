import { analyzeBeam, PRESETS } from "./beam.mjs";
import { reviewBeam, reviewCad, reviewFrameStudies, reviewFrameSelection } from "./bean_advisor.mjs";
const byId=(id)=>document.getElementById(id);
let viewer=null;
let mode="demo";
let currentFile=null;
let points={fixed:null,load:null};
let calculated=null;
let beanPreviousMessage="";
let frameStudy=null;
let publishedFrames=null;
let evidencePromise=null;

function updateBean(){
  const review=mode==="demo" ? reviewBeam(beamInput(), calculated) :
    mode==="frame" ? reviewFrameSelection(frameStudy,publishedFrames?.studies||[]) :
    reviewCad({filename:currentFile?.name||"",fixed:points.fixed,load:points.load});
  byId("beanHeadline").textContent=review.headline;
  byId("beanAdvice").textContent=review.advice;
  const newMessage=review.headline+"|"+review.advice;
  if(beanPreviousMessage && newMessage!==beanPreviousMessage){
    const mascot=byId("beanMascot").parentElement;
    if(!matchMedia("(prefers-reduced-motion: reduce)").matches){
      mascot.classList.remove("bean-respond");
      void mascot.offsetWidth;
      mascot.classList.add("bean-respond");
    }
  }
  beanPreviousMessage=newMessage;
}

async function loadFrameEvidence(){
  if(!evidencePromise){
    evidencePromise=(async()=>{
      const response=await fetch("./data/frame_studies.json",{cache:"no-store"});
      if(!response.ok)throw new Error("Published CalculiX results unavailable");
      const evidence=await response.json();
      if(evidence.schema!=="ezfea.frame_evidence.v1" ||
         !Array.isArray(evidence.studies))throw new Error("Unrecognized published physics format");
      reviewFrameStudies(evidence.studies);
      publishedFrames=evidence;
      return evidence;
    })().catch(error=>{evidencePromise=null;throw error;});
  }
  return evidencePromise;
}

async function showFrameEvidence(){
  const target=byId("beanStudyList");
  try {
    const evidence=await loadFrameEvidence();
    const check=reviewFrameStudies(evidence.studies);
    target.replaceChildren();
    for(const entry of evidence.studies){
      const row=document.createElement("div");
      row.className="bean-study-row";
      const name=document.createElement("strong");
      name.textContent=entry.name;
      const info=document.createElement("span");
      info.textContent="Deflection "+format(entry.max_displacement_mm,4)+" mm · Stress "+
        format(entry.max_von_mises_mpa,4)+" MPa";
      row.append(name,info);
      target.appendChild(row);
    }
    const note=document.createElement("p");
    note.className="bean-study-takeaway";
    note.textContent=check.bracedStiffer ?
      "BEAN check: the braced frame deflected "+format(check.ratio,3)+
      "× less under identical lateral loading." :
      "BEAN check: bracing comparison requires investigation.";
    target.appendChild(note);
    if(/^https:\/\/github\.com\/danieloculus0-bot\/EZ-FEA\/actions\/runs\/\d+$/.test(evidence.source_run||"")){
      byId("beanStudySource").href=evidence.source_run;
    }
  } catch(_error){
    target.textContent="Recorded 3D results could not be loaded. The beam demo still works.";
  }
}

function renderFrameStudy(){
  if(mode!=="frame"||!frameStudy||!viewer)return;
  try{viewer.showFrameStudy(frameStudy);}
  catch(err){announce("Unable to preview recorded frame: "+err.message);}
}

function showFrameResults(study){
  if(!study)return;
  byId("frameResultValues").hidden=false;
  byId("frameDeflection").textContent=format(study.max_displacement_mm,5)+" mm";
  byId("frameStress").textContent=format(study.max_von_mises_mpa,5)+" MPa";
  byId("frameBalance").textContent=format(100*study.force_balance_relative_error,3)+"%";
  byId("frameResultSummary").textContent=
    "Previously solved with real 3D CalculiX (C3D4). The frame drawing is a reference silhouette, not a computed deformation or stress contour.";
  byId("frameResultProvenance").textContent=
    "Archived: "+(publishedFrames.generated_utc ?
      new Date(publishedFrames.generated_utc).toLocaleString() : "prior verified run")+
    " · "+study.mesh_elements+" tetrahedra · mesh "+study.mesh_size_mm+
    " mm · No new solve was launched from this browser.";
  const url=publishedFrames.source_run;
  if(/^https:\/\/github\.com\/danieloculus0-bot\/EZ-FEA\/actions\/runs\/\d+$/.test(url||"")){
    byId("frameSolverLink").href=url;
  }
}

function selectFrameStudy(key){
  const study=publishedFrames?.studies?.find(item=>item.key===key);
  if(!study)return;
  mode="frame";
  currentFile=null;
  frameStudy=study;
  points={fixed:null,load:null};
  byId("fileInput").value="";
  byId("partInfo").textContent=study.name+" · recorded 3D solve";
  updateMode();
  byId("frameParameters").textContent="";
  const detail=document.createElement("strong");
  detail.textContent="Fixed test conditions";
  const rest=document.createElement("div");
  const d=study.model_dimensions_mm;
  const force=study.force_n.map((n)=>format(n,4)).join(", ");
  rest.textContent=d.width+" × "+d.height+" × "+d.depth+" mm · "+d.member+
    " mm solid members · "+force+" N (X, Y, Z) · "+study.material_name;
  byId("frameParameters").append(detail,rest);
  showFrameResults(study);
  renderFrameStudy();
  updateBean();
  announce(study.name+": showing verified archived solver results, not a live analysis.");
}

async function populateFrameSelector(){
  const select=byId("frameSelect");
  try{
    const evidence=await loadFrameEvidence();
    select.replaceChildren();
    const placeholder=document.createElement("option");
    placeholder.value="";
    placeholder.textContent="Choose a real 3D study…";
    select.appendChild(placeholder);
    const selectable=evidence.studies.filter(study=>
      ["portal","rectangle","braced"].includes(study.construction) &&
      study.model_dimensions_mm && Number.isFinite(study.mesh_elements) &&
      study.force_balance_relative_error<=.01);
    for(const study of selectable){
      const option=document.createElement("option");
      option.value=study.key;
      option.textContent=study.name;
      select.appendChild(option);
    }
    select.disabled=selectable.length===0;
    byId("frameSelectNote").textContent=selectable.length+
      " real recorded 3D solves · fixed inputs, read-only results";
  }catch(_error){
    select.disabled=true;
    select.replaceChildren(new Option("Solver studies temporarily unavailable",""));
    byId("frameSelectNote").textContent="The real 2D beam demonstration still works.";
  }
}


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
  byId("frameResultValues").hidden=true;
  byId("resultPlaceholder").hidden=mode!=="demo";
  byId("cadNoSolver").hidden=mode!=="custom";
  updateBean();
}
function updateMode(){
  const demo=mode==="demo";
  const frame=mode==="frame";
  byId("beamControls").hidden=!demo;
  byId("beamLoadControls").hidden=frame;
  byId("materialControls").hidden=frame;
  byId("frameParameters").hidden=!frame;
  byId("demoConnections").hidden=!demo;
  byId("frameConnections").hidden=!frame;
  byId("customConnections").hidden=mode!=="custom";
  byId("runBtn").hidden=!demo;
  byId("runCaption").hidden=!demo;
  byId("viewerOverlay").hidden=!demo;
  byId("viewBadge").textContent=demo?"BEAM EXAMPLE":frame?"VERIFIED SOLVER STUDY":"CAD PREVIEW ONLY";
  byId("viewerHeading").textContent=demo?"Example beam":frame?frameStudy.name:(currentFile?.name||"Your model");
  byId("viewerSub").textContent=demo?"Real 2D beam calculation, visualized in 3D":
    frame?"Reference geometry · recorded native 3D CalculiX results":"Geometry only. No structural solve has been performed.";
  byId("modeDesc").textContent=demo?
    "Try the example and see real calculated displacement and bending stress.":
    frame?"Actual saved 3D finite-element results from GitHub Actions; fixed study conditions.":
    "We can preview and mark locations on this part, but a full 3D FEA solver is not available on GitHub Pages.";
  byId("connectionHint").textContent=demo?
    "The beam is held still on the left. Its far end gets pushed down.":
    frame?"The reference studies restrain bottom faces and distribute load on the top face.":
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
  frameStudy=null;
  byId("frameSelect").value="";
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
    updateBean();
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
  updateBean();
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
    frameStudy=null;
    byId("frameSelect").value="";
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
  byId("frameSelect").addEventListener("change",(event)=>{
    if(event.target.value)selectFrameStudy(event.target.value);
  });
  void populateFrameSelector();
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
  byId("beanMascot").addEventListener("error",()=>{
    const image=byId("beanMascot");
    if(!image.src.endsWith("/assets/bean-icon.svg"))image.src="./assets/bean-icon.svg";
  });
  byId("beanMascot").addEventListener("animationend",(event)=>{
    if(event.animationName==="bean-nod"){
      byId("beanMascot").parentElement.classList.remove("bean-respond");
    }
  });
  byId("beanFrameStudies").addEventListener("toggle",event=>{
    if(event.target.open && !event.target.dataset.loaded){
      event.target.dataset.loaded="yes";
      void showFrameEvidence();
    }
  });
  const drop=byId("dropZone");
  drop.addEventListener("keydown",(event)=>{
    if(event.key==="Enter"||event.key===" "){
      event.preventDefault();
      byId("fileInput").click();
    }
  });
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
    if(mode==="frame")renderFrameStudy(); else renderDemo();
  }).catch(err=>{
    byId("fallback").hidden=false;
    announce("3D preview unavailable: "+err.message+". Beam calculation still works.");
  });
}
start();
