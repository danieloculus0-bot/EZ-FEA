/* Dependency-free 3D geometry preview for machines without WebGL.
 * Unlike the old fixed 2D illustration, this renders real rotated 3D
 * square-bar prisms with 6 visible/hidden faces and supports mouse, touch,
 * button and automatic orbit. It NEVER fabricates stress contours.
 */
import { validateTrussEvidence } from "./truss_evidence.mjs";

const $=id=>document.getElementById(id);
const NS="http://www.w3.org/2000/svg";
const svg=$("trussStatic");
let azimuth=.63,elevation=.33,zoom=1.0,auto=true;
let pointer=null,frame=0,lastTime=0,data=null,currentData=null,wasHardware=false;
const DEFAULT={span:600,rise:180,chord:24,web:18,load:1000,
               young:200000,poisson:.26,yield:250,leftAxes:"XYZ",rightAxes:"YZ"};
const memberRecipe=[
 ["BOTTOM","chord",[0,0,0],[600,0,0],24],
 ["TOP","chord",[75,180,0],[525,180,0],24],
 ["W01","web",[0,0,0],[75,180,0],18],
 ["W02","web",[75,180,0],[150,0,0],18],
 ["W03","web",[150,0,0],[225,180,0],18],
 ["W04","web",[225,180,0],[300,0,0],18],
 ["W05","web",[300,0,0],[375,180,0],18],
 ["W06","web",[375,180,0],[450,0,0],18],
 ["W07","web",[450,0,0],[525,180,0],18],
 ["W08","web",[525,180,0],[600,0,0],18]
];
const FACES=[[0,1,3,2],[4,5,7,6],[0,1,5,4],[2,3,7,6],[0,2,6,4],[1,3,7,5]];
function hardware(){
  return !!document.querySelector("#trussCanvas canvas:not([data-disabled])")&&svg.hidden;
}
function values(){
  const numeric=id=>Number($(id)?.value);
  const out={
    span:numeric("editSpan"),rise:numeric("editRise"),
    chord:numeric("editChord"),web:numeric("editWeb"),
    load:numeric("editLoad"),young:numeric("editYoung"),
    poisson:numeric("editPoisson"),yield:numeric("editYield"),
    leftAxes:$("editLeftSupport")?.value,rightAxes:$("editRightSupport")?.value
  };
  const sane=out.span>=150&&out.span<=3000&&out.rise>=50&&out.rise<=1500&&
    out.chord>=5&&out.chord*3<out.span&&out.web>=5&&out.web*3<out.rise&&
    out.load>=0&&out.load<=1000000;
  return sane?out:DEFAULT;
}
function pristine(v){
  return Object.entries(DEFAULT).every(([key,val])=>v[key]===val);
}
function updateStatus(){
  if(hardware())return;
  $("rotationReadout").textContent="Software 3D orbit · horizontal "+
    Math.round(azimuth*180/Math.PI)+"° · vertical "+
    Math.round(elevation*180/Math.PI)+"° · drag/swipe to rotate · wheel to zoom";
  $("evidenceBadge").textContent="ROTATABLE SOFTWARE 3D PREVIEW";
  if(!$("trussViewerStatus").textContent.includes("WebGL")){
    $("trussViewerStatus").textContent=
      "3D rotation running without WebGL acceleration. This geometry is a construction preview, not an FEA stress contour.";
  }
}
function geometry(){
  const v=values();
  const objects=[];
  for(const [id,kind,start,end,defaultSize] of memberRecipe){
    const a=[start[0]*v.span/600,start[1]*v.rise/180,0];
    const b=[end[0]*v.span/600,end[1]*v.rise/180,0];
    const size=kind==="chord"?v.chord:v.web;
    const dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy),ux=dx/len,uy=dy/len;
    const nx=-uy,ny=ux,half=size/2,ext=kind==="web"?7:0;
    const vertices=[];
    for(const t of [-ext,len+ext]){
      const x=a[0]+ux*t,y=a[1]+uy*t;
      for(const sign of [-1,1]){
        for(const signz of [-1,1]){
          vertices.push([x+nx*half*sign,y+ny*half*sign,size/2*signz]);
        }
      }
    }
    objects.push({id,kind,vertices,color:kind==="web"?"#75ab92":"#97c9b0"});
  }
  const span=v.span,s=v.chord,scale=Math.min(2,Math.max(.5,span/600));
  const addBox=(id,x,y,z,w,h,d,color)=>{
    const verts=[];
    for(const xx of [-1,1]){
      for(const yy of [-1,1]){
        for(const zz of [-1,1])verts.push([x+xx*w/2,y+yy*h/2,z+zz*d/2]);
      }
    }
    objects.push({id,kind:"pad",vertices:verts,color});
  };
  if($("toggleSupports")?.getAttribute("aria-pressed")!=="false"){
    addBox("Left HOLD",0,-s/2-29*scale/2,0,36*scale,29*scale,30*scale,"#5ff39a");
    addBox("Right HOLD",span,-s/2-29*scale/2,0,36*scale,29*scale,30*scale,"#6ec5de");
  }
  if($("toggleLoad")?.getAttribute("aria-pressed")!=="false"){
    addBox("Load pad",span/2,v.rise+s/2+19*scale/2,0,40*scale,19*scale,30*scale,"#c5ff4a");
  }
  return {objects,v};
}
function project(pts,center){
  const cy=Math.cos(azimuth),sy=Math.sin(azimuth);
  const cp=Math.cos(elevation),sp=Math.sin(elevation);
  return pts.map(([x,y,z])=>{
    const a=x-center[0],b=y-center[1],c=z-center[2];
    const x1=cy*a+sy*c,z1=-sy*a+cy*c;
    const y2=cp*b-sp*z1,z2=sp*b+cp*z1;
    return [x1,y2,z2];
  });
}
function el(name,attrs={},textContent=null){
  const element=document.createElementNS(NS,name);
  for(const [key,value] of Object.entries(attrs))element.setAttribute(key,String(value));
  if(textContent!==null)element.textContent=textContent;
  return element;
}
function draw(){
  if(!svg||hardware())return;
  const {objects,v}=geometry();
  const center=[v.span/2,v.rise/2,0];
  const verts=objects.map(obj=>project(obj.vertices,center));
  const all=verts.flat();
  const xmax=Math.max(...all.map(p=>Math.abs(p[0])),1);
  const ymax=Math.max(...all.map(p=>Math.abs(p[1])),1);
  const factor=Math.min(335/xmax,157/ymax)*zoom;
  const xmid=400,ymid=195;
  const rows=[];
  for(let i=0;i<objects.length;i++){
    const points=verts[i],obj=objects[i];
    for(const face of FACES){
      const coords=face.map(k=>points[k]);
      const a=coords[0],b=coords[1],c=coords[2];
      const cross=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
      if(Math.abs(cross)<.0001)continue;
      const coords2=coords.map(p=>[xmid+p[0]*factor,ymid-p[1]*factor]);
      rows.push({
        depth:coords.reduce((sum,p)=>sum+p[2],0)/4,
        pts:coords2.map(p=>p.map(x=>x.toFixed(1)).join(",")).join(" "),
        id:obj.id,color:obj.color,
        shade:cross>=0?"0.90":"0.76"
      });
    }
  }
  rows.sort((a,b)=>a.depth-b.depth);
  const fragment=document.createDocumentFragment();
  fragment.appendChild(el("rect",{width:800,height:390,fill:"#0c1715"}));
  for(const row of rows){
    const poly=el("polygon",{
      points:row.pts,fill:row.color,"fill-opacity":row.shade,
      stroke:"#182b22","stroke-width":".65","data-feature":row.id
    });
    fragment.appendChild(poly);
  }
  fragment.appendChild(el("text",{x:22,y:28,fill:"#abc6af","font-size":13,
    "font-family":"Arial,sans-serif"},"CAD member preview · software 3D orbit"));
  if($("toggleLoad")?.getAttribute("aria-pressed")!=="false"){
    const top=project([[v.span/2,v.rise+Math.max(48,v.rise*.45),0]],center)[0];
    const p=project([[v.span/2,v.rise+v.chord/2+10,0]],center)[0];
    const x=xmid+top[0]*factor,y=ymid-top[1]*factor,xx=xmid+p[0]*factor,yy=ymid-p[1]*factor;
    fragment.appendChild(el("line",{x1:x,y1:y,x2:xx,y2:yy,
      stroke:"#c5ff4a","stroke-width":4}));
    fragment.appendChild(el("polygon",{points:
      (xx-10)+","+(yy-13)+" "+(xx+10)+","+(yy-13)+" "+xx+","+yy,
      fill:"#c5ff4a"}));
  }
  svg.replaceChildren(fragment);
  updateStatus();
}
function rotate(amount){
  if(hardware())return;
  auto=false;
  $("orbitAuto").setAttribute("aria-pressed","false");
  $("orbitAuto").textContent="Auto-rotate: OFF";
  azimuth+=amount;draw();
}
function updateAuto(enabled){
  if(hardware())return;
  auto=enabled;
  $("orbitAuto").setAttribute("aria-pressed",String(auto));
  $("orbitAuto").textContent="Auto-rotate: "+(auto?"ON":"OFF");
  lastTime=0;draw();
}
function tick(time){
  frame=requestAnimationFrame(tick);
  if(hardware()){
    if(!wasHardware){wasHardware=true;}
    return;
  }
  wasHardware=false;
  if(!lastTime)lastTime=time;
  const dt=Math.min(50,Math.max(0,time-lastTime))/1000;
  lastTime=time;
  if(auto){azimuth+=dt*.47;draw();}
}
function currentMode(){
  return $("modeTruss")?.getAttribute("aria-pressed")!=="false";
}
if(svg){
  svg.style.touchAction="none";
  svg.style.cursor="grab";
  svg.setAttribute("tabindex","0");
  svg.setAttribute("aria-label","Rotatable 3D truss prism preview, rendered without WebGL. Drag or swipe, use arrow keys or rotate buttons.");
  svg.addEventListener("pointerdown",e=>{
    if(hardware())return;
    pointer={x:e.clientX,y:e.clientY,yaw:azimuth,pitch:elevation};
    svg.setPointerCapture(e.pointerId);
    svg.style.cursor="grabbing";
  });
  svg.addEventListener("pointermove",e=>{
    if(hardware()||!pointer)return;
    if(Math.abs(e.clientX-pointer.x)+Math.abs(e.clientY-pointer.y)>2){
      auto=false;
      $("orbitAuto").setAttribute("aria-pressed","false");
      $("orbitAuto").textContent="Auto-rotate: OFF";
      azimuth=pointer.yaw+(e.clientX-pointer.x)*.012;
      elevation=Math.max(-1.35,Math.min(1.35,pointer.pitch-(e.clientY-pointer.y)*.009));
      draw();
    }
  });
  const up=()=>{pointer=null;svg.style.cursor="grab";};
  svg.addEventListener("pointerup",up);
  svg.addEventListener("pointercancel",up);
  svg.addEventListener("wheel",e=>{
    if(hardware())return;
    e.preventDefault();zoom=Math.max(.45,Math.min(2.3,zoom*(e.deltaY<0?1.10:.90)));draw();
  },{passive:false});
  svg.addEventListener("keydown",e=>{
    if(hardware())return;
    if(e.key==="ArrowLeft"||e.key==="ArrowRight"){
      e.preventDefault();rotate(e.key==="ArrowLeft"?-.20:.20);
    }else if(e.key==="ArrowUp"||e.key==="ArrowDown"){
      e.preventDefault();
      elevation=Math.max(-1.35,Math.min(1.35,elevation+(e.key==="ArrowUp"?.15:-.15)));
      draw();
    }
  });
  const on=(id,fn)=>$(id)?.addEventListener("click",()=>{if(!hardware())fn();});
  on("orbitLeft",()=>rotate(-.34));
  on("orbitRight",()=>rotate(.34));
  on("orbitAuto",()=>updateAuto(!auto));
  on("resetTrussView",()=>{azimuth=.63;elevation=.33;zoom=1;updateAuto(false);});
  on("toggleSupports",()=>requestAnimationFrame(draw));
  on("toggleLoad",()=>requestAnimationFrame(draw));
  for(const key of ["editSpan","editRise","editChord","editWeb","editLoad",
                     "editYoung","editPoisson","editYield","editLeftSupport","editRightSupport"]){
    $(key)?.addEventListener("input",()=>{
      if(hardware())return;
      const v=values();
      if(!pristine(v)){
        for(const field of ["trussDisplacement","trussStress","trussElements",
                            "trussForceBalance","trussMomentBalance"])$(field).textContent="—";
        $("trussProof").textContent="NOT SOLVED";
        $("resultStatus").textContent="Edited specimen has NOT been solved. Run native EZ-FEA for new results.";
      }
      draw();
    });
  }
  draw();
  frame=requestAnimationFrame(tick);
}
export const softwareOrbitReady=Boolean(svg);
