import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';

/** Visualizer only. The displayed geometry is not an FEA solver. */
export class Viewer {
  constructor(holder, onPick) {
    this.holder=holder;
    this.onPick=onPick;
    this.scene=new THREE.Scene();
    this.camera=new THREE.PerspectiveCamera(40,1,0.1,10000000);
    this.renderer=new THREE.WebGLRenderer({alpha:true,antialias:true});
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
    holder.appendChild(this.renderer.domElement);
    this.controls=new OrbitControls(this.camera,this.renderer.domElement);
    this.controls.enableDamping=true;
    this.controls.dampingFactor=.09;
    this.controls.minDistance=2;
    this.controls.maxDistance=10000000;
    this.scene.add(new THREE.HemisphereLight(0xffffff,0x9fa9b9,2.0));
    const sun=new THREE.DirectionalLight(0xffffff,2.5);
    sun.position.set(100,160,200);
    this.scene.add(sun);
    const other=new THREE.DirectionalLight(0xa5d9ed,.8);
    other.position.set(-100,40,-140);
    this.scene.add(other);
    this.geometryGroup=new THREE.Group();
    this.scene.add(this.geometryGroup);
    this.markerGroup=new THREE.Group();
    this.scene.add(this.markerGroup);
    this.overlayGroup=new THREE.Group();
    this.scene.add(this.overlayGroup);
    this.pickMode=null;
    this.demo=true;
    this.bounds=null;
    this.raycaster=new THREE.Raycaster();
    this.pointer=new THREE.Vector2();
    this.down=null;
    this.renderer.domElement.addEventListener("pointerdown",(e)=>{this.down={x:e.clientX,y:e.clientY};});
    this.renderer.domElement.addEventListener("pointerup",(e)=>this.pick(e));
    this.resizeObserver=new ResizeObserver(()=>this.resize());
    this.resizeObserver.observe(holder);
    this.resize();
    this.draw=()=>{
      this.controls.update();
      this.renderer.render(this.scene,this.camera);
      requestAnimationFrame(this.draw);
    };
    requestAnimationFrame(this.draw);
  }
  resize() {
    const w=Math.max(1,this.holder.clientWidth);
    const h=Math.max(1,this.holder.clientHeight);
    this.renderer.setSize(w,h,false);
    this.camera.aspect=w/h;
    this.camera.updateProjectionMatrix();
  }
  clearGroup(g) {
    for (const child of [...g.children]) {
      g.remove(child);
      child.traverse((o)=>{
        if(o.geometry)o.geometry.dispose();
        if(o.material) {
          const all=Array.isArray(o.material)?o.material:[o.material];
          for(const m of all)m.dispose();
        }
      });
    }
  }
  showDemo({length, width, height}, materialColor) {
    this.demo=true;
    this.pickMode=null;
    this.clearGroup(this.geometryGroup);
    this.clearGroup(this.markerGroup);
    this.clearGroup(this.overlayGroup);
    const beam=new THREE.Mesh(new THREE.BoxGeometry(length,height,width),
      new THREE.MeshStandardMaterial({color:materialColor||0x96b7ca,metalness:.32,roughness:.32}));
    beam.position.x=length/2;
    beam.userData.pickable=true;
    this.geometryGroup.add(beam);
    const outline=new THREE.LineSegments(new THREE.EdgesGeometry(beam.geometry),
      new THREE.LineBasicMaterial({color:0x62849a,transparent:true,opacity:.65}));
    outline.position.copy(beam.position);
    this.geometryGroup.add(outline);
    const plate=new THREE.Mesh(new THREE.BoxGeometry(Math.max(length*.016,2),height*1.65,width*1.65),
      new THREE.MeshStandardMaterial({color:0x1daa7d,roughness:.55}));
    plate.position.x=-Math.max(length*.01,1);
    this.geometryGroup.add(plate);
    const loadArrow=new THREE.ArrowHelper(
      new THREE.Vector3(0,-1,0),
      new THREE.Vector3(length,height/2+Math.max(height*2.6,length*.20),0),
      Math.max(height*2.35,length*.18),0xc5ff4a,
      Math.max(2,Math.min(height*.75,length*.045)),Math.max(1.1,height*.4));
    this.geometryGroup.add(loadArrow);
    this.bounds=new THREE.Box3().setFromObject(this.geometryGroup);
    this.focus();
  }
  showStl(buffer) {
    const geometry=new STLLoader().parse(buffer);
    geometry.computeVertexNormals();
    const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:0x85acbf,metalness:.24,roughness:.48,side:THREE.DoubleSide}));
    mesh.userData.pickable=true;
    this.setCustom(mesh);
  }
  showObj(text) {
    const obj=new OBJLoader().parse(text);
    obj.traverse((child)=>{
      if(!child.isMesh)return;
      child.material=new THREE.MeshStandardMaterial({color:0x85acbf,metalness:.24,roughness:.48,side:THREE.DoubleSide});
      child.userData.pickable=true;
    });
    this.setCustom(obj);
  }
  showStep(result) {
    if(!result.success||!Array.isArray(result.meshes)||!result.meshes.length) throw new Error("STEP importer did not produce viewable geometry.");
    const group=new THREE.Group();
    for(const m of result.meshes) {
      const p=m.attributes?.position?.array;
      if(!p||p.length<9)continue;
      const geo=new THREE.BufferGeometry();
      geo.setAttribute("position",new THREE.Float32BufferAttribute(p,3));
      if(m.attributes?.normal?.array?.length===p.length){
        geo.setAttribute("normal",new THREE.Float32BufferAttribute(m.attributes.normal.array,3));
      } else geo.computeVertexNormals();
      if(m.index?.array?.length)geo.setIndex(Array.from(m.index.array));
      geo.computeBoundingSphere();
      const color=Array.isArray(m.color)?new THREE.Color(m.color[0],m.color[1],m.color[2]):new THREE.Color(0x85acbf);
      const mesh=new THREE.Mesh(geo,new THREE.MeshStandardMaterial({color,metalness:.22,roughness:.46,side:THREE.DoubleSide}));
      mesh.userData.pickable=true;
      mesh.userData.brep_faces=m.brep_faces||[];
      group.add(mesh);
    }
    if(!group.children.length)throw new Error("No displayable STEP faces were returned.");
    this.setCustom(group);
  }
  setCustom(object) {
    this.demo=false;
    this.pickMode=null;
    this.clearGroup(this.geometryGroup);
    this.clearGroup(this.markerGroup);
    this.clearGroup(this.overlayGroup);
    this.geometryGroup.add(object);
    this.bounds=new THREE.Box3().setFromObject(this.geometryGroup);
    this.focus();
  }
  focus() {
    if(!this.bounds||this.bounds.isEmpty())return;
    const center=this.bounds.getCenter(new THREE.Vector3());
    const size=this.bounds.getSize(new THREE.Vector3());
    const radius=Math.max(size.length()*.8,1);
    this.controls.target.copy(center);
    this.camera.near=Math.max(.001,radius/10000);
    this.camera.far=radius*1000;
    this.camera.position.copy(center).add(new THREE.Vector3(radius*.9,radius*.65,radius*1.2));
    this.camera.updateProjectionMatrix();
    this.controls.update();
  }
  setPicking(mode) {
    this.pickMode=mode;
    this.renderer.domElement.style.cursor=mode?"crosshair":"grab";
  }
  pick(e) {
    if(this.demo||!this.pickMode||!this.down)return;
    if(Math.hypot(e.clientX-this.down.x,e.clientY-this.down.y)>6)return;
    const rect=this.renderer.domElement.getBoundingClientRect();
    this.pointer.set(((e.clientX-rect.left)/rect.width)*2-1,-((e.clientY-rect.top)/rect.height)*2+1);
    this.raycaster.setFromCamera(this.pointer,this.camera);
    const hits=this.raycaster.intersectObjects(this.geometryGroup.children,true).filter(h=>h.object.userData.pickable);
    if(!hits.length)return;
    const hit=hits[0];
    const point=hit.point.clone();
    const mode=this.pickMode;
    this.mark(mode,point);
    this.setPicking(null);
    if(this.onPick)this.onPick(mode,{x:point.x,y:point.y,z:point.z,triangle:hit.faceIndex??null});
  }
  mark(mode,point) {
    const current=this.markerGroup.getObjectByName(mode);
    if(current) {
      this.markerGroup.remove(current);
      current.geometry.dispose();
      current.material.dispose();
    }
    const dimensions=this.bounds.getSize(new THREE.Vector3());
    const radius=Math.max(dimensions.length()*.012,0.3);
    const marker=new THREE.Mesh(new THREE.SphereGeometry(radius,20,12),
      new THREE.MeshBasicMaterial({color:mode==="fixed"?0x16b88b:0xc5ff4a,depthTest:false}));
    marker.position.copy(point);
    marker.renderOrder=3;
    marker.name=mode;
    this.markerGroup.add(marker);
  }
  showBending(result, height) {
    this.clearGroup(this.overlayGroup);
    if(!result||!result.curve||!result.deflection_mm)return 1;
    const size=Math.max(result.curve.at(-1).x,1);
    const amplification=Math.min(5000,Math.max(1,size*.12/result.deflection_mm));
    const points=result.curve.map(p=>new THREE.Vector3(p.x,p.y*amplification,0));
    const lineGeometry=new THREE.BufferGeometry().setFromPoints(points);
    const line=new THREE.Line(lineGeometry,new THREE.LineBasicMaterial({color:0xc5ff4a,linewidth:3}));
    this.overlayGroup.add(line);
    const tip=points.at(-1);
    const endBall=new THREE.Mesh(new THREE.SphereGeometry(Math.max(height*.12,1),12,10),
      new THREE.MeshBasicMaterial({color:0xc5ff4a}));
    endBall.position.copy(tip);
    this.overlayGroup.add(endBall);
    return amplification;
  }
}
