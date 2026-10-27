import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import { OBJLoader } from "three/addons/loaders/OBJLoader.js";
import { STLExporter } from "three/addons/exporters/STLExporter.js";
import { analyzeBeam,PRESETS } from "./beam.mjs";
import { validateTrussEvidence } from "./truss_evidence.mjs";
import { DEFAULT_TRUSS,validateTrussInputs,isRecordedTruss,alteredMembers } from "./workbench_state.mjs";

const el=id=>document.getElementById(id);
let evidence=null;
let scene=null,camera=null,renderer=null,orbit=null,group=null;
let mode="truss";
let trussInputs={...DEFAULT_TRUSS};
let nativeStlBuffer=null;
let imported=null;
let activePreviewSha=null;
let markMode=null;
let marked={hold:null,load:null};
let visibleSupports=true,visibleLoad=true;
const selectors=[];
let down=null,canvasReady=false;
const SOURCE="https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/40473627691";

const value=(id)=>Number(el(id).value);
const fmt=(v,d=6)=>Number(v).toLocaleString("en-US",{maximumSignificantDigits:d});
function say(s){el("trussViewerStatus").textContent=s;}
function note(s){el("selectedFeature").textContent=s;}
function evidenceLink(url,label){
  el("trussSourceLink").href=url;
  el("trussSourceLink").textContent=label;
}
function resetOutput(message="No new 3D calculation has been run for these inputs."){
  for(const key of ["trussDisplacement","trussStress","trussElements",
                     "trussForceBalance","trussMomentBalance"])
    el(key).textContent="—";
  el("trussProof").textContent="NOT SOLVED";
  el("resultStatus").textContent=message;
  evidenceLink(SOURCE,"See the original reference solve ↗");
}
function showRecorded(){
  if(!evidence)return resetOutput("Recorded native data unavailable");
  const n=evidence.native;
  el("trussDisplacement").textContent=fmt(n.max_displacement_mm)+" mm";
  el("trussStress").textContent=fmt(n.peak_von_mises_mpa)+" MPa";
  el("trussElements").textContent=n.elements.toLocaleString("en-US")+" "+n.mesh_type;
  el("trussForceBalance").textContent=n.force_balance_check.toUpperCase();
  el("trussMomentBalance").textContent=n.moment_balance_check.toUpperCase();
  el("trussProof").textContent="Original run";
  el("resultStatus").textContent="Measured for the exact original 600 × 180 mm fused truss with 1,000 N applied. Editing requires a new native solve.";
  el("resultPanelTitle").textContent="REAL SOLVER MEASUREMENTS";
  el("fixtureState").textContent="Left fixed · right slides X";
  evidenceLink(evidence.source_run,"Inspect original native solve ↗");
}
function clearGroup(){
  if(!group)return;
  selectors.length=0;
  for(const child of [...group.children]){
    group.remove(child);
    child.traverse(mesh=>{
      mesh.geometry?.dispose?.();
      if(mesh.material)
        for(const m of Array.isArray(mesh.material)?mesh.material:[mesh.material])m.dispose?.();
    });
  }
}
function init3D(){
  if(canvasReady)return;
  const host=el("trussCanvas");
  scene=new THREE.Scene();
  scene.background=new THREE.Color("#0b1413");
  camera=new THREE.PerspectiveCamera(40,1,.1,100000);
  renderer=new THREE.WebGLRenderer({antialias:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
  host.appendChild(renderer.domElement);
  group=new THREE.Group();scene.add(group);
  scene.add(new THREE.HemisphereLight(0xffffff,0x5b8377,2));
  const sun=new THREE.DirectionalLight(0xffffff,2.8);
  sun.position.set(400,420,450);scene.add(sun);
  const fill=new THREE.DirectionalLight(0x81daa5,1.2);
  fill.position.set(-350,150,-300);scene.add(fill);
  orbit=new OrbitControls(camera,renderer.domElement);
  orbit.enableDamping=true;orbit.dampingFactor=.07;
  orbit.minDistance=3;orbit.maxDistance=50000;
  renderer.domElement.style.cursor="grab";
  renderer.domElement.addEventListener("pointerdown",e=>{
    down={x:e.clientX,y:e.clientY};
  });
  renderer.domElement.addEventListener("pointerup",e=>{
    if(!down)return;
    const distance=Math.hypot(e.clientX-down.x,e.clientY-down.y);
    down=null;
    if(distance<=6)clickGeometry(e);
  });
  const resize=()=>{
    const w=Math.max(host.clientWidth,1),h=Math.max(host.clientHeight,1);
    renderer.setSize(w,h,false);
    camera.aspect=w/h;camera.updateProjectionMatrix();
  };
  new ResizeObserver(resize).observe(host);
  resize();
  canvasReady=true;
  el("trussStatic").hidden=true;
  (function animate(){
    orbit.update();
    renderer.render(scene,camera);
    requestAnimationFrame(animate);
  })();
}
function centerCamera(){
  if(!canvasReady||!group.children.length)return;
  const bounds=new THREE.Box3().setFromObject(group);
  const center=bounds.getCenter(new THREE.Vector3());
  const size=bounds.getSize(new THREE.Vector3());
  const radius=Math.max(size.length()*.73,5);
  orbit.target.copy(center);
  camera.near=Math.max(.01,radius/10000);
  camera.far=radius*1000;
  camera.position.copy(center).add(new THREE.Vector3(radius*.82,radius*.50,radius*1.15));
  camera.updateProjectionMatrix();orbit.update();
}
function material(hex,transparency=false){
  return new THREE.MeshStandardMaterial({
    color:hex,metalness:.43,roughness:.43,
    transparent:transparency,opacity:transparency?.84:1
  });
}
function box(length,height,depth,cx,cy,cz,color,id=null,exportable=false){
  const obj=new THREE.Mesh(new THREE.BoxGeometry(length,height,depth),material(color));
  obj.position.set(cx,cy,cz);
  obj.userData.feature=id;
  obj.userData.exportable=exportable;
  group.add(obj);
  if(id)selectors.push(obj);
  return obj;
}
function rod(item){
  const start=new THREE.Vector3(...item.start);
  const end=new THREE.Vector3(...item.end);
  const axis=end.clone().sub(start);
  const extent=axis.length();
  const overrun=item.kind==="web"?7:0;
  const obj=box(extent+2*overrun,item.square_side_mm,item.square_side_mm,
                0,0,0,0x8fbfac,item.id,true);
  obj.position.copy(start.clone().add(end).multiplyScalar(.5));
  obj.quaternion.setFromUnitVectors(new THREE.Vector3(1,0,0),axis.normalize());
}
function addTrussFixtures(){
  const span=trussInputs.span,rise=trussInputs.rise;
  const factor=Math.min(2,Math.max(.5,span/600));
  const w=36*factor,depth=30*factor,thickness=29*factor;
  for(const [id,x,color] of [["LEFT_SUPPORT",0,0x5ff39a],
                               ["RIGHT_SUPPORT",span,0x62cbe4]]){
    const obj=box(w,thickness,depth,x,-(trussInputs.chord/2+thickness/2),0,color,id,true);
    obj.name="support";
  }
  const pad=box(40*factor,19*factor,30*factor,span/2,
    rise+trussInputs.chord/2+9.5*factor,0,0xc5ff4a,"LOAD_PAD",true);
  pad.name="load";
  const height=Math.max(50,rise*.40);
  const arrow=new THREE.ArrowHelper(new THREE.Vector3(0,-1,0),
      new THREE.Vector3(span/2,rise+trussInputs.chord/2+height+25,0),
      height,0xc5ff4a,Math.min(height*.3,18),Math.min(height*.16,10));
  arrow.name="load";group.add(arrow);
}
function showNativeMesh(){
  if(!nativeStlBuffer)return false;
  const geometry=new STLLoader().parse(nativeStlBuffer.slice(0));
  geometry.computeVertexNormals();
  const solid=new THREE.Mesh(geometry,material(0x8fbfac));
  solid.userData.feature="FUSED_CAD";
  group.add(solid);selectors.push(solid);
  return true;
}
function renderTruss(){
  if(!canvasReady||!evidence)return;
  clearGroup();
  const isOriginalGeometry=trussInputs.span===600&&trussInputs.rise===180&&
                           trussInputs.chord===24&&trussInputs.web===18;
  const native=isOriginalGeometry&&showNativeMesh();
  if(!native){
    const built=alteredMembers(evidence.geometry,trussInputs);
    for(const member of built)rod(member);
  }
  addTrussFixtures();setVisibility();centerCamera();
  if(isRecordedTruss(trussInputs)){
    showRecorded();
    el("evidenceBadge").textContent=native?"Original STEP · native solve":"Original recipe · native solve";
    say(native?"Rotate the original STEP solid · click model, support or load to inspect.":
      "Rotate the original model recipe · original measured CalculiX results are available.");
  }else{
    resetOutput("Edited truss is UNSOLVED. Do not use original stress or displacement for changed geometry, material or load. Save setup and solve in native EZ-FEA.");
    el("resultPanelTitle").textContent="CURRENT EDITED MODEL";
    el("evidenceBadge").textContent="EDITED · NOT SOLVED";
    say("Geometry updated. Rotate to inspect; save setup or export the mesh. A new native FEA solve is required.");
  }
  el("fixtureState").textContent=
    "Left "+trussInputs.leftAxes+" · right "+trussInputs.rightAxes;
  el("editNotice").textContent=isRecordedTruss(trussInputs)
    ?"Original measured case. Change any input to edit the model; native results clear until the original is restored."
    :"This is a real editable 3D model, NOT a newly solved 3D FEA case. Exported STL contains intersecting bars, not a fused STEP weldment.";
  note("Click a member or support for its definition. Drag to rotate; scroll or pinch to zoom.");
}
function setVisibility(){
  if(!group)return;
  for(const obj of group.children){
    if(obj.name==="support")obj.visible=visibleSupports;
    if(obj.name==="load")obj.visible=visibleLoad;
  }
  el("toggleSupports").setAttribute("aria-pressed",String(visibleSupports));
  el("toggleLoad").setAttribute("aria-pressed",String(visibleLoad));
}
function readTrussInputs(){
  const vals={
    span:value("editSpan"),rise:value("editRise"),
    chord:value("editChord"),web:value("editWeb"),load:value("editLoad"),
    young:value("editYoung"),poisson:value("editPoisson"),yield:value("editYield"),
    leftAxes:el("editLeftSupport").value,rightAxes:el("editRightSupport").value,
  };
  return validateTrussInputs(vals);
}
function trussEdited(){
  if(mode!=="truss")return;
  try{
    trussInputs=readTrussInputs();
    renderTruss();
  }catch(err){
    resetOutput("Invalid setup: "+err.message);
    el("evidenceBadge").textContent="CHECK INPUT";
    el("editNotice").textContent="Check input: "+err.message;
    say("Fix the highlighted truss dimensions before exporting.");
  }
}
function drawBeam(){
  if(!canvasReady)return;
  clearGroup();
  const length=value("beamLength"),width=value("beamWidth"),height=value("beamHeight");
  const force=value("beamLoad"),preset=PRESETS[el("beamMaterial").value];
  try{
    const sol=analyzeBeam({
      length,width,height,force,modulus:preset.modulus,yield:preset.yield
    },8);
    const steel=box(length,height,width,length/2,0,0,0x8fbfac,"BEAM");
    const hold=box(Math.max(2,length*.017),height*1.5,width*1.35,
        -Math.max(1,length*.01),0,0,0x5ff39a,"BEAM_HOLD");
    hold.name="support";
    const arrow=new THREE.ArrowHelper(
      new THREE.Vector3(0,-1,0),
      new THREE.Vector3(length,height*.9+Math.max(height*2,length*.20),0),
      Math.max(height*2,length*.18),0xc5ff4a,
      Math.max(height*.4,2),Math.max(height*.2,1));
    arrow.name="load";group.add(arrow);
    setVisibility();centerCamera();
    el("resultPanelTitle").textContent="LIVE 2D BEAM FE CALCULATION";
    el("trussDisplacement").textContent=fmt(sol.deflection_mm)+" mm";
    el("trussStress").textContent=fmt(sol.peak_bending_stress_mpa)+" MPa";
    el("trussElements").textContent=sol.element_count+" 2D beam elements";
    el("trussForceBalance").textContent="2D reference";
    el("trussMomentBalance").textContent=fmt(100*sol.verification_relative_error,4)+"% ref. diff.";
    el("fixtureState").textContent="Fixed end · free end load";
    el("trussProof").textContent="RECALCULATED";
    el("evidenceBadge").textContent="LIVE BROWSER BEAM FE";
    el("resultStatus").textContent="Calculated now using an 8-element Euler–Bernoulli beam solver with an independent deflection reference. This is not a 3D CAD / truss analysis.";
    evidenceLink("https://github.com/danieloculus0-bot/EZ-FEA/blob/main/web/beam.mjs","Inspect actual 2D solver ↗");
    say("Beam recalculated for your current dimensions, load and material. Drag to rotate the 3D geometry.");
    note("2D finite-element beam result, displayed in 3D. This model cannot assess 3D CAD stresses, welds or buckling.");
  }catch(err){
    resetOutput("Beam cannot be solved: "+err.message);
    say("Invalid beam parameters: "+err.message);
  }
}
function showImportDefault(){
  if(!canvasReady)return;
  clearGroup();
  if(imported?.group){
    imported.group.traverse(o=>{
      if(o.isMesh){o.userData.feature="IMPORT";selectors.push(o);}
    });
    group.add(imported.group);
    centerCamera();
    say("Rotate your imported "+imported.name+". Click HOLD or LOAD to place preview markers.");
    note("Uploaded CAD is preview-only here. Use the actual desktop solver for native 3D structural analysis.");
  }else{
    say("Choose a STEP, STL, or OBJ file. The 3D viewer will rotate your own model.");
    note("No CAD imported yet. Geometry does not leave the browser.");
  }
  resetOutput("An imported 3D model has not been solved. Browser markers are not original STEP CAD face IDs.");
  el("resultPanelTitle").textContent="YOUR MODEL · NOT SOLVED";
  el("fixtureState").textContent="Select HOLD and LOAD markers";
  el("evidenceBadge").textContent="CAD PREVIEW";
  el("trussStatic").hidden=!!canvasReady;
}
function renderMode(){
  for(const [name,id,panel] of [
    ["truss","modeTruss","editTrussPanel"],
    ["import","modeImport","openCadPanel"],
    ["beam","modeBeam","beamPanel"],
  ]){
    const active=mode===name;
    el(id).classList.toggle("active",active);
    el(id).setAttribute("aria-pressed",String(active));
    el(panel).hidden=!active;
  }
  if(mode==="truss")renderTruss();
  else if(mode==="beam")drawBeam();
  else showImportDefault();
}
function pickFeature(event){
  const rect=renderer.domElement.getBoundingClientRect();
  const point=new THREE.Vector2(
    (event.clientX-rect.left)/rect.width*2-1,
    -(event.clientY-rect.top)/rect.height*2+1);
  const ray=new THREE.Raycaster();ray.setFromCamera(point,camera);
  const hit=ray.intersectObjects(selectors.filter(o=>o.visible),false)[0];
  return hit||null;
}
function setMarker(which,position){
  const old=marked[which];
  if(old?.mesh){
    group.remove(old.mesh);old.mesh.geometry.dispose();old.mesh.material.dispose();
  }
  const boxSize=imported?.bounds?.getSize(new THREE.Vector3()).length()||50;
  const mark=new THREE.Mesh(
    new THREE.SphereGeometry(Math.max(1,boxSize*.009),12,12),
    new THREE.MeshBasicMaterial({color:which==="hold"?0x5ff39a:0xffbd79}));
  mark.position.copy(position);
  group.add(mark);
  marked[which]={position:position.toArray(),mesh:mark};
}
function clickGeometry(e){
  const hit=pickFeature(e);
  if(!hit){
    note("Click the 3D geometry itself to inspect or mark it.");
    return;
  }
  if(mode==="import"){
    if(markMode){
      setMarker(markMode,hit.point);
      note((markMode==="hold"?"HOLD":"LOAD")+" preview marker set at ["+
        hit.point.toArray().map(n=>fmt(n,5)).join(", ")+"] mm. Not a verified CAD surface ID.");
      markMode=null;
      renderer.domElement.style.cursor="grab";
      el("cadNotice").textContent="Markers are planning coordinates only; a real solver must identify actual STEP faces and restraints.";
    }else note("Imported surface selected. Choose HOLD or LOAD above to place a removable planning marker.");
    return;
  }
  const id=hit.object.userData.feature;
  if(mode==="beam"){note("Beam cross-section preview · live 2D beam displacement and bending stress appear on the right.");return;}
  if(id==="FUSED_CAD"){
    note("Original fused STEP surface. Its individual welds are idealized as fully continuous steel, not independently verified.");
  }else if(id==="LEFT_SUPPORT"){
    note("Left support pad: constrained in "+trussInputs.leftAxes+
      " (global translations). Idealized fixture, not a physical bolt solve.");
  }else if(id==="RIGHT_SUPPORT"){
    note("Right support pad: constrained in "+trussInputs.rightAxes+
      " (global translations). Changing restraint requires a new FEA solve.");
  }else if(id==="LOAD_PAD"){
    note("Center upper pad: "+fmt(trussInputs.load)+" N downward. Loads changed in the editor require a new FEA solve.");
  }else{
    const m=evidence.geometry.members.find(a=>a.id===id);
    note(m?m.id+" · "+m.kind+" · "+(m.kind==="web"?trussInputs.web:trussInputs.chord)+
      " mm solid square section. This is geometry, not a member-by-member stress result.":
      "Solid geometry from the truss construction recipe.");
  }
}
let occtPromise=null;
async function occtStep(buffer){
  if(!occtPromise){
    occtPromise=(async()=>{
      if(!globalThis.occtimportjs){
        await new Promise((resolve,reject)=>{
          const node=document.createElement("script");
          node.src="https://cdn.jsdelivr.net/npm/occt-import-js@0.0.23/dist/occt-import-js.js";
          node.onload=resolve;node.onerror=()=>reject(new Error("STEP importer could not load"));
          document.head.appendChild(node);
        });
      }
      if(!globalThis.occtimportjs)throw new Error("STEP importer unavailable");
      return globalThis.occtimportjs({
        locateFile:name=>"https://cdn.jsdelivr.net/npm/occt-import-js@0.0.23/dist/"+name
      });
    })().catch(err=>{occtPromise=null;throw err;});
  }
  const importer=await occtPromise;
  const result=importer.ReadStepFile(new Uint8Array(buffer),{
    linearUnit:"millimeter",linearDeflectionType:"bounding_box_ratio",
    linearDeflection:.05,angularDeflection:.35
  });
  if(!result?.success||!Array.isArray(result.meshes)||!result.meshes.length)
    throw new Error("The STEP file did not contain a displayable solid");
  const g=new THREE.Group();
  for(const body of result.meshes){
    const p=body.attributes?.position?.array;
    if(!p||p.length<9)continue;
    const geo=new THREE.BufferGeometry();
    geo.setAttribute("position",new THREE.Float32BufferAttribute(p,3));
    if(body.attributes?.normal?.array?.length===p.length)
      geo.setAttribute("normal",new THREE.Float32BufferAttribute(body.attributes.normal.array,3));
    else geo.computeVertexNormals();
    if(body.index?.array?.length)geo.setIndex(Array.from(body.index.array));
    g.add(new THREE.Mesh(geo,material(0x9abcb2)));
  }
  if(!g.children.length)throw new Error("No valid STEP triangles were produced");
  return g;
}
async function importPart(file){
  if(!file)return;
  if(file.size>50*1024*1024){
    say("CAD file exceeds 50 MB browser preview limit.");
    return;
  }
  const ext=file.name.toLowerCase().slice(file.name.lastIndexOf("."));
  if(![".step",".stp",".stl",".obj"].includes(ext)){
    say("Choose a STEP, STL or OBJ file.");return;
  }
  try{
    say("Loading "+file.name+" as a rotatable 3D model…");
    const buffer=await file.arrayBuffer();
    const object=ext===".step"||ext===".stp"?
      await occtStep(buffer):ext===".stl"?
      new THREE.Mesh(new STLLoader().parse(buffer),material(0x96b8aa,true)):
      new OBJLoader().parse(await file.text());
    if(ext===".obj"){
      object.traverse(child=>{if(child.isMesh)child.material=material(0x96b8aa,true);});
    }
    imported={name:file.name,size:file.size,group:object,
              bounds:new THREE.Box3().setFromObject(object)};
    marked={hold:null,load:null};
    markMode=null;
    mode="import";renderMode();
    el("cadNotice").textContent=file.name+" loaded into the rotatable viewer. Select HOLD / LOAD to place planning marks.";
  }catch(error){
    say("CAD import failed: "+error.message);
  }
}
function downloadFile(name,contents,type="application/json"){
  const blob=contents instanceof Blob?contents:new Blob([contents],{type});
  const url=URL.createObjectURL(blob);
  const link=document.createElement("a");link.href=url;link.download=name;
  document.body.appendChild(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),500);
}
function saveTruss(){
  try{
    const vals=readTrussInputs();
    const payload={
      schema:"ezfea.browser.truss_edit.v1",
      saved_from:"EZ-FEA public CAD editor",
      origin_run:evidence?.source_run||null,
      source_step_sha256:evidence?.source_step_sha256||null,
      source_step_is_unchanged:isRecordedTruss(vals),
      dimensions_mm:{span:vals.span,rise:vals.rise,chord_square:vals.chord,
                     web_square:vals.web},
      material:{elastic_modulus_mpa:vals.young,poisson_ratio:vals.poisson,
                nominal_yield_mpa:vals.yield},
      force_n:[0,-vals.load,0],
      members:alteredMembers(evidence.geometry,vals),
      suggested_supports:[
        {location_mm:[0,0,0],restrained_axes:vals.leftAxes},
        {location_mm:[vals.span,0,0],restrained_axes:vals.rightAxes},
      ],
      analysis_status:isRecordedTruss(vals)?"ARCHIVED_REFERENCE_ONLY":"NOT_SOLVED",
      important:"This is an editable CAD construction recipe. New dimensions/forces need a new native Gmsh/CalculiX solve. Browser STL is not a fused watertight STEP weldment."
    };
    downloadFile("ezfea_truss_setup.json",JSON.stringify(payload,null,2));
  }catch(error){say("Cannot export invalid setup: "+error.message);}
}
function saveMesh(){
  if(mode!=="truss"||!evidence)return;
  try{
    const vals=readTrussInputs();
    if(isRecordedTruss(vals)&&nativeStlBuffer){
      downloadFile("ezfea_original_warren_truss.stl",
        new Blob([nativeStlBuffer],{type:"model/stl"}),"model/stl");
      say("Original truss STEP tessellation exported, not a new solved analysis.");
      return;
    }
    const meshGroup=new THREE.Group();
    for(const obj of group.children){
      if(obj.isMesh&&obj.userData.exportable===true)
        meshGroup.add(obj.clone());
    }
    if(!meshGroup.children.length)throw new Error("No truss bars to export");
    const stl=new STLExporter().parse(meshGroup,{binary:false});
    downloadFile("ezfea_edited_truss_preview.stl",stl,"model/stl");
    say("Editable truss preview STL exported. Bodies overlap; this is NOT a fused solver-ready STEP.");
  }catch(error){say("Mesh export error: "+error.message);}
}
function saveMarkers(){
  if(!imported){say("Open a STEP, STL or OBJ first.");return;}
  const json={
    schema:"ezfea.web.cad_markers.v1",
    source_filename:imported.name,source_size_bytes:imported.size,
    source_file_included:false,
    hold_preview_xyz_mm:marked.hold?.position||null,
    load_preview_xyz_mm:marked.load?.position||null,
    original_step_face_ids_known:false,analysis_status:"NOT_RUN",
    warning:"Markers are visual points only. They do not identify stable STEP CAD faces or verified physical supports. Reopen original CAD in native EZ-FEA."
  };
  downloadFile("ezfea_cad_markers.json",JSON.stringify(json,null,2));
}
async function loadRecordedSTL(){
  if(!evidence?.geometry?.stl_sha256)return;
  try{
    const response=await fetch("./data/warren_truss.stl",{cache:"no-store"});
    if(!response.ok)throw new Error("original STL unavailable");
    const buffer=await response.arrayBuffer();
    if(!crypto?.subtle)throw new Error("secure SHA256 verification unavailable");
    const hash=await crypto.subtle.digest("SHA-256",buffer);
    const digest=Array.from(new Uint8Array(hash)).map(n=>n.toString(16).padStart(2,"0")).join("");
    if(digest!==evidence.geometry.stl_sha256)
      throw new Error("original STEP tessellation digest mismatch");
    nativeStlBuffer=buffer;
  }catch(err){
    nativeStlBuffer=null;
    say("Original CAD surface temporarily unavailable; model recipe is still editable. "+err.message);
  }
}
function restoreTruss(){
  for(const [id,key] of [["editSpan","span"],["editRise","rise"],
    ["editChord","chord"],["editWeb","web"],["editLoad","load"],
    ["editYoung","young"],["editPoisson","poisson"],["editYield","yield"],
    ["editLeftSupport","leftAxes"],["editRightSupport","rightAxes"]])
    el(id).value=DEFAULT_TRUSS[key];
  trussInputs={...DEFAULT_TRUSS};
  mode="truss";renderMode();
}
async function launch(){
  const modes=[["modeTruss","truss"],["modeImport","import"],["modeBeam","beam"]];
  for(const [id,m] of modes)el(id).addEventListener("click",()=>{
    mode=m;renderMode();
  });
  el("toggleSupports").addEventListener("click",()=>{
    visibleSupports=!visibleSupports;setVisibility();
  });
  el("toggleLoad").addEventListener("click",()=>{
    visibleLoad=!visibleLoad;setVisibility();
  });
  el("resetTrussView").addEventListener("click",centerCamera);
  el("restoreTruss").addEventListener("click",restoreTruss);
  el("downloadSetup").addEventListener("click",saveTruss);
  el("downloadMesh").addEventListener("click",saveMesh);
  el("saveCadSetup").addEventListener("click",saveMarkers);
  el("markHold").addEventListener("click",()=>{
    if(!imported)return say("Import a part first");
    markMode="hold";say("Click directly on the CAD surface to set a preview HOLD point.");
    renderer.domElement.style.cursor="crosshair";
  });
  el("markForce").addEventListener("click",()=>{
    if(!imported)return say("Import a part first");
    markMode="load";say("Click the surface where the force would act.");
    renderer.domElement.style.cursor="crosshair";
  });
  el("cadFileInput").addEventListener("change",e=>{
    void importPart(e.target.files?.[0]);
  });
  for(const id of ["editSpan","editRise","editChord","editWeb","editLoad",
                   "editYoung","editPoisson","editYield",
                   "editLeftSupport","editRightSupport"])
    el(id).addEventListener("input",trussEdited);
  for(const id of ["beamLength","beamWidth","beamHeight","beamLoad","beamMaterial"])
    el(id).addEventListener("input",()=>{
      if(mode==="beam")drawBeam();
    });
  try{
    const response=await fetch("./data/truss_demo.json",{cache:"no-store"});
    if(!response.ok)throw new Error("Native truss archive not available");
    evidence=validateTrussEvidence(await response.json());
    await loadRecordedSTL();
  }catch(err){
    say("Cannot load recorded truss: "+err.message);
    el("trussProof").textContent="Unavailable";
    return;
  }
  try{
    init3D();renderMode();
  }catch(err){
    el("evidenceBadge").textContent="3D preview unavailable";
    say("Could not initialize 3D rotation: "+err.message+". You can still access the verified numerical case.");
    showRecorded();
  }
}
void launch();
