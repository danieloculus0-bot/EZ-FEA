import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import { validateTrussEvidence } from "./truss_evidence.mjs";

const el=id=>document.getElementById(id);
let scene=null,camera=null,renderer=null,orbit=null,group=null;
let data=null,model=null,visibleSupports=true,visibleLoad=true,selected=null;
const selectors=[];
let draggedFrom=null;
const nativeColor=0x87b5a2;

function fmt(value,digits=5){
  return Number(value).toLocaleString("en-US",{maximumSignificantDigits:digits});
}
function say(msg){el("trussViewerStatus").textContent=msg;}
function emptyGroup(sceneGroup){
  for(const child of [...sceneGroup.children]){
    sceneGroup.remove(child);
    child.traverse(obj=>{
      obj.geometry?.dispose?.();
      if(obj.material){
        for(const mat of Array.isArray(obj.material)?obj.material:[obj.material])mat.dispose?.();
      }
    });
  }
}
function baseModel(){
  const host=el("trussCanvas");
  scene=new THREE.Scene();
  scene.background=new THREE.Color("#0b1413");
  camera=new THREE.PerspectiveCamera(40,1,0.1,10000);
  renderer=new THREE.WebGLRenderer({antialias:true,alpha:false});
  renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));
  host.append(renderer.domElement);
  group=new THREE.Group();
  scene.add(group);
  scene.add(new THREE.HemisphereLight(0xffffff,0x567d70,2.2));
  const light=new THREE.DirectionalLight(0xf9ffea,2.7);
  light.position.set(-130,480,480);scene.add(light);
  const edge=new THREE.DirectionalLight(0x88e6b0,1.2);
  edge.position.set(600,110,-350);scene.add(edge);
  orbit=new OrbitControls(camera,renderer.domElement);
  orbit.enableDamping=true;
  orbit.dampingFactor=.07;
  orbit.minDistance=150;
  orbit.maxDistance=2500;
  renderer.domElement.style.cursor="grab";
  renderer.domElement.addEventListener("pointerdown",e=>{
    draggedFrom={x:e.clientX,y:e.clientY};
  });
  renderer.domElement.addEventListener("pointerup",e=>{
    if(!draggedFrom || Math.hypot(e.clientX-draggedFrom.x,e.clientY-draggedFrom.y)>6)return;
    draggedFrom=null;
    selectMember(e);
  });
  const resize=()=>{
    const w=Math.max(1,host.clientWidth),h=Math.max(1,host.clientHeight);
    renderer.setSize(w,h,false);
    camera.aspect=w/h;
    camera.updateProjectionMatrix();
  };
  new ResizeObserver(resize).observe(host);
  resize();
  const animate=()=>{
    orbit.update();
    renderer.render(scene,camera);
    requestAnimationFrame(animate);
  };
  animate();
}
function viewHome(){
  orbit.target.set(300,85,0);
  camera.position.set(765,395,740);
  camera.near=.1;camera.far=5000;
  camera.updateProjectionMatrix();
  orbit.update();
}
function box(sx,sy,sz,x,y,z,material,tag=null){
  const geo=new THREE.BoxGeometry(sx,sy,sz);
  const obj=new THREE.Mesh(geo,material);
  obj.position.set(x,y,z);
  obj.userData.memberId=tag;
  group.add(obj);
  return obj;
}
function bar(item,material,selectable=true){
  const start=new THREE.Vector3(...item.start);
  const end=new THREE.Vector3(...item.end);
  const direction=end.clone().sub(start);
  const length=direction.length();
  const extended=item.kind==="web"?7:0;
  const obj=box(length+extended*2,item.square_side_mm,item.square_side_mm,
      0,0,0,material,item.id);
  obj.position.copy(start.add(end).multiplyScalar(.5));
  obj.quaternion.setFromUnitVectors(
      new THREE.Vector3(1,0,0),direction.normalize());
  if(selectable)selectors.push(obj);
  return obj;
}
function reconstructGeometry(){
  // This is the documented CAD construction recipe, not a native stress mesh.
  const material=new THREE.MeshStandardMaterial({
    color:nativeColor,metalness:.43,roughness:.43});
  data.geometry.members.forEach(m=>bar(m,material));
  say("Rotatable model reconstructed from the exact truss CAD recipe. Numerical results come from native CalculiX.");
}
function addFixtures(){
  const supportMat=new THREE.MeshStandardMaterial({
    color:0x5ff39a,metalness:.25,roughness:.55,transparent:true,opacity:.96});
  const sliderMat=new THREE.MeshStandardMaterial({
    color:0x66bcd5,metalness:.25,roughness:.53,transparent:true,opacity:.96});
  const left=box(36,29,30,0,-22.5,0,supportMat);
  const right=box(36,29,30,600,-22.5,0,sliderMat);
  left.userData.memberId="LEFT_SUPPORT";
  right.userData.memberId="RIGHT_SUPPORT";
  left.name="support";right.name="support";
  selectors.push(left,right);
  return [left,right];
}
function addLoad(){
  const pad=new THREE.Mesh(new THREE.BoxGeometry(40,19,30),
    new THREE.MeshStandardMaterial({
      color:0xc5ff4a,metalness:.12,roughness:.5,
      transparent:true,opacity:.9}));
  pad.position.set(300,197.5,0);
  pad.userData.memberId="LOAD_PAD";
  pad.name="load";
  group.add(pad);
  selectors.push(pad);
  const arrow=new THREE.ArrowHelper(
    new THREE.Vector3(0,-1,0),new THREE.Vector3(300,305,0),
    78,0xc5ff4a,23,13);
  arrow.name="load";group.add(arrow);
  return [pad,arrow];
}
function selectMember(e){
  if(!camera||!renderer)return;
  const rect=renderer.domElement.getBoundingClientRect();
  const mouse=new THREE.Vector2(
    (e.clientX-rect.left)/rect.width*2-1,
    -(e.clientY-rect.top)/rect.height*2+1);
  const ray=new THREE.Raycaster();
  ray.setFromCamera(mouse,camera);
  const hit=ray.intersectObjects(selectors.filter(x=>x.visible),false)[0];
  if(!hit){
    el("selectedFeature").textContent="Click a member or fixture to inspect it. Only whole-model stress results are available in this archive.";
    return;
  }
  const id=hit.object.userData.memberId;
  if(id==="LEFT_SUPPORT"){
    el("selectedFeature").textContent="Left foot: actual native boundary condition fixed translations X, Y and Z. This is a finite area support, not a physical bolt model.";
  }else if(id==="RIGHT_SUPPORT"){
    el("selectedFeature").textContent="Right foot: actual native restraint in Y and Z, free in X (sliding support). The support's real-world stiffness is not simulated.";
  }else if(id==="FUSED_CAD"){
    el("selectedFeature").textContent="Actual fused STEP solid: ten overlapping structural bars joined as ideal continuous steel. Whole-model displacement and stress are measured; real weld throat or fastener physics are not modeled.";
  }else if(id==="LOAD_PAD"){
    el("selectedFeature").textContent="Top-center pad: 1,000 N downward (global −Y), distributed over its original STEP face in the native solver.";
  }else{
    const m=data.geometry.members.find(x=>x.id===id);
    el("selectedFeature").textContent=
      (m?.kind==="web"?"Diagonal web ":"Chord ")+id+
      " · "+m?.square_side_mm+" × "+m?.square_side_mm+
      " mm solid square bar. The archive reports overall peak stress, not independently measured stress per member.";
  }
}
function applyVisibility(){
  if(!group)return;
  for(const object of group.children){
    if(object.name==="support")object.visible=visibleSupports;
    if(object.name==="load")object.visible=visibleLoad;
  }
  el("toggleSupports").setAttribute("aria-pressed",String(visibleSupports));
  el("toggleLoad").setAttribute("aria-pressed",String(visibleLoad));
}
async function loadAuthenticSTL(){
  const sha=data.geometry.stl_sha256;
  if(!sha) return false;
  const response=await fetch("./data/warren_truss.stl",{cache:"no-store"});
  if(!response.ok)throw new Error("Published CAD surface not accessible");
  const raw=await response.arrayBuffer();
  const digest=await crypto.subtle.digest("SHA-256",raw);
  const hex=Array.from(new Uint8Array(digest)).map(x=>x.toString(16).padStart(2,"0")).join("");
  if(hex!==sha)throw new Error("Published STEP tessellation failed SHA-256 verification");
  const geometry=new STLLoader().parse(raw);
  geometry.computeVertexNormals();
  const cad=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({
    color:nativeColor,metalness:.42,roughness:.46,side:THREE.DoubleSide}));
  cad.userData.memberId="FUSED_CAD";
  group.add(cad);
  selectors.push(cad);
  // The tessellation represents the unioned CAD solid. Do not fabricate
  // per-member stress labels or claim the fused STEP retains separate bodies.
  say("Showing tessellated original fused STEP surface, verified by SHA-256. Drag to rotate; saved native numbers are below.");
  return true;
}
function fillNumbers(){
  const n=data.native;
  el("trussDisplacement").textContent=fmt(n.max_displacement_mm,6)+" mm";
  el("trussStress").textContent=fmt(n.peak_von_mises_mpa,6)+" MPa";
  el("trussElements").textContent=n.elements.toLocaleString("en-US")+" "+n.mesh_type;
  el("trussForceBalance").textContent=n.force_balance_check.toUpperCase();
  el("trussMomentBalance").textContent=n.moment_balance_check.toUpperCase();
  el("trussSourceLink").href=data.source_run;
  el("trussProof").textContent="Recorded · source linked";
}
async function launch(){
  for(const [id,key] of [["toggleSupports","supports"],["toggleLoad","load"]]){
    el(id).addEventListener("click",()=>{
      if(key==="supports")visibleSupports=!visibleSupports;
      else visibleLoad=!visibleLoad;
      applyVisibility();
    });
  }
  el("resetTrussView").addEventListener("click",viewHome);
  try{
    const response=await fetch("./data/truss_demo.json",{cache:"no-store"});
    if(!response.ok)throw new Error("Published native results unavailable");
    data=validateTrussEvidence(await response.json());
    fillNumbers();
  }catch(err){
    say("Native evidence unavailable: "+err.message+". Open the linked solver run instead.");
    el("trussProof").textContent="Unavailable";
    return;
  }
  try{
    baseModel();
    let real=false;
    try{real=await loadAuthenticSTL();}
    catch(e){say("Native CAD preview unavailable ("+e.message+"). Showing the construction recipe with real archived results.");}
    if(!real)reconstructGeometry();
    addFixtures();addLoad();applyVisibility();viewHome();
    el("trussStatic").hidden=true;
    el("evidenceBadge").textContent="Verified archived 3D solve";
  }catch(err){
    say("3D rendering unavailable: "+err.message+". Schematic shown; original native results are still displayed.");
    el("evidenceBadge").textContent="Archived native results";
  }
}
launch();
