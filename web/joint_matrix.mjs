import {
  JOINT_TYPES,SCHEMA,validateMatrix,sampleMatrix,setJointType,
  fillDown,pasteColumn,toCSV
} from "./joint_matrix_core.mjs";

const el=id=>document.getElementById(id);
let matrix=sampleMatrix();
let undoStack=[],redoStack=[];
let selection={start:0,end:0};
let drag=null;
let indexToCell=[];

function message(text,error=false) {
  el("feedback").textContent=text;
  el("feedback").style.color=error?"#f6b65c":"#b3ff52";
}
function commit(next,label) {
  undoStack.push(matrix);
  if (undoStack.length>100) undoStack.shift();
  redoStack=[];
  matrix=next;
  render();
  message(label);
}
function labelFor(id) {
  const comp=(matrix.components??[]).find(x=>Number(x.id)===Number(id));
  return comp ? String(comp.label??("Part "+id)) : "Part "+id;
}
function render() {
  const body=el("rows");
  body.replaceChildren();
  indexToCell=[];
  matrix.rows.forEach((row,index)=>{
    const tr=document.createElement("tr");
    const add=(txt,className)=>{
      const td=document.createElement("td");
      if(className)td.className=className;
      td.textContent=txt;
      tr.append(td);
      return td;
    };
    add(String(index+1),"num");
    add(row.joint_id,"joint");
    add(labelFor(row.component_a));
    add(labelFor(row.component_b));
    add(String(row.face_a)+" ⇄ "+String(row.face_b));
    const cell=add("","cell");
    cell.dataset.row=String(index);
    cell.dataset.selected=String(index===selection.start);
    cell.dataset.range=String(
      index>=Math.min(selection.start,selection.end)&&
      index<=Math.max(selection.start,selection.end)&&index!==selection.start
    );
    const select=document.createElement("select");
    select.setAttribute("aria-label","Joint type for "+row.joint_id);
    select.dataset.row=String(index);
    JOINT_TYPES.forEach(choice=>{
      const o=document.createElement("option");
      o.textContent=choice;
      o.value=choice;
      select.append(o);
    });
    select.value=row.joint_type;
    select.addEventListener("change",()=>{
      selection={start:index,end:index};
      try {commit(setJointType(matrix,index,select.value),
           row.joint_id+" set to "+select.value+". Solver connection remains unassigned.");}
      catch(ex){message(ex.message,true);render();}
    });
    select.addEventListener("click",event=>{
      if(event.shiftKey)selection.end=index;
      else selection={start:index,end:index};
      highlight();
    });
    cell.append(select);
    indexToCell[index]=cell;
    if(index===selection.start){
      const handle=document.createElement("span");
      handle.className="handle";
      handle.title="Drag down to fill joint type";
      handle.setAttribute("aria-label","Drag to fill joint types downward");
      handle.setAttribute("role","button");
      handle.tabIndex=0;
      handle.addEventListener("pointerdown",ev=>{
        ev.stopPropagation();
        ev.preventDefault();
        drag={anchor:index,end:index};
        window.addEventListener("pointermove",dragMove);
        window.addEventListener("pointerup",dragEnd,{once:true});
      });
      handle.addEventListener("keydown",ev=>{
        if(ev.key==="Enter"){ev.preventDefault();fillSelected();}
      });
      cell.append(handle);
    }
    const st=add("","last");
    const indicator=document.createElement("span");
    const assigned=row.joint_type!=="Unassigned";
    indicator.className="status "+(assigned?"selected":"new");
    indicator.textContent=assigned?"Type selected · physics unassigned":"Needs identification";
    st.append(indicator);
    body.append(tr);
  });
  el("total").textContent=String(matrix.rows.length);
  const selected=matrix.rows.filter(x=>x.joint_type!=="Unassigned").length;
  el("classified").textContent=String(selected);
  el("remaining").textContent=String(matrix.rows.length-selected);
  el("ground").textContent=String(matrix.ground_component??"—");
  el("undo").disabled=undoStack.length===0;
  el("redo").disabled=redoStack.length===0;
  el("fill").disabled=matrix.rows.length<2;
}
function highlight() {
  for(const [i,cell] of indexToCell.entries()){
    cell.dataset.selected=String(i===selection.start);
    cell.dataset.range=String(i>=Math.min(selection.start,selection.end)&&
                                 i<=Math.max(selection.start,selection.end)&&
                                 i!==selection.start);
  }
}
function dragMove(ev){
  if(!drag)return;
  const item=document.elementFromPoint(ev.clientX,ev.clientY);
  const td=item?.closest?.("td.cell");
  if(!td)return;
  const row=Number(td.dataset.row);
  drag.end=Math.max(drag.anchor,row);
  selection={start:drag.anchor,end:drag.end};
  highlight();
}
function dragEnd(){
  window.removeEventListener("pointermove",dragMove);
  if(!drag)return;
  const a=drag.anchor,b=drag.end;
  drag=null;
  if(b<=a){message("Drag the green handle downward to copy the selected joint type.");return;}
  try{commit(fillDown(matrix,a,b),"Filled "+(b-a)+" joints with "+matrix.rows[a].joint_type+".");}
  catch(e){message(e.message,true);render();}
}
function fillSelected(){
  try {
    const start=Math.min(selection.start,selection.end);
    const end=Math.max(selection.start,selection.end);
    if(start===end){message("Shift-click a lower joint row, or drag the green handle downward.");return;}
    commit(fillDown(matrix,start,end),"Filled "+(end-start)+" joints.");
  }catch(ex){message(ex.message,true);}
}
function copySelection(){
  const a=Math.min(selection.start,selection.end);
  const b=Math.max(selection.start,selection.end);
  return matrix.rows.slice(a,b+1).map(x=>x.joint_type).join("\n");
}
async function copySelected(){
  const contents=copySelection();
  try{await navigator.clipboard.writeText(contents);message("Copied "+(selection.end-selection.start+1)+" joint types.");}
  catch(e){message("Clipboard unavailable. Select and copy text using your browser.",true);}
}
async function pasteSelected(){
  try {
    const clipboard=await navigator.clipboard.readText();
    commit(pasteColumn(matrix,selection.start,clipboard),"Pasted joint classifications.");
  }catch(e){message("Clipboard paste unavailable. Use Ctrl/Cmd+V on the table or permit clipboard access.",true);}
}
function undo(){
  if(!undoStack.length)return;
  redoStack.push(matrix);
  matrix=undoStack.pop();
  render();message("Undid last Joint Matrix edit.");
}
function redo(){
  if(!redoStack.length)return;
  undoStack.push(matrix);
  matrix=redoStack.pop();
  render();message("Redid last Joint Matrix edit.");
}
function saveFile(text,name,type){
  const objectUrl=URL.createObjectURL(new Blob([text],{type}));
  const a=document.createElement("a");
  a.href=objectUrl;a.download=name;a.click();
  setTimeout(()=>URL.revokeObjectURL(objectUrl),2500);
}
function importGraph(graph){
  if(!Array.isArray(graph.joints)||!Array.isArray(graph.components)||
     !Number.isInteger(graph.ground_component))throw new Error("Invalid scanned CAD graph");
  return validateMatrix({
    schema:SCHEMA,
    ground_component:graph.ground_component,
    components:graph.components,
    rows:graph.joints.map((j,i)=>({
      joint_id:String(j.joint_id??("J-"+String(i+1).padStart(3,"0"))),
      component_a:j.component_a,component_b:j.component_b,
      face_a:j.face_a,face_b:j.face_b,
      candidate_kind:j.candidate_kind,
      overlap_area_bbox_mm2:j.overlap_area_bbox_mm2,
      joint_type:"Unassigned",
      joint_confirmation:"not_reviewed",
      mechanical_model:"unassigned"
    }))
  });
}
el("file").addEventListener("change",async ev=>{
  const file=ev.target.files?.[0];
  if(!file)return;
  try{
    const data=JSON.parse(await file.text());
    const imported= data.schema==="ezfea.assembly_joint_graph.v1"?
      importGraph(data):validateMatrix(data);
    if(imported.rows.length===0)throw new Error("No candidate mate joints in this file");
    selection={start:0,end:0};
    commit(imported,"Imported "+imported.rows.length+" candidate CAD joints for review.");
  }catch(err){message(err.message,true);}
  ev.target.value="";
});
el("fill").addEventListener("click",fillSelected);
el("copy").addEventListener("click",copySelected);
el("paste").addEventListener("click",pasteSelected);
el("undo").addEventListener("click",undo);
el("redo").addEventListener("click",redo);
el("load").addEventListener("click",()=>el("file").click());
el("save").addEventListener("click",()=>saveFile(JSON.stringify(matrix,null,2)+"\n",
  "EZ-FEA-joint-matrix.json","application/json"));
el("csv").addEventListener("click",()=>saveFile(toCSV(matrix),
  "EZ-FEA-joint-matrix.csv","text/csv"));
el("reset").addEventListener("click",()=>{selection={start:0,end:0};commit(sampleMatrix(),"Sample matrix reset.");});
el("rows").addEventListener("click",e=>{
  const td=e.target.closest?.("td.cell");
  if(!td||e.target.tagName==="SELECT")return;
  const row=Number(td.dataset.row);
  if(e.shiftKey)selection.end=row;
  else selection={start:row,end:row};
  render();
});
document.addEventListener("keydown",event=>{
  if(!(event.ctrlKey||event.metaKey)||["INPUT","TEXTAREA"].includes(event.target.tagName))return;
  if(event.key.toLowerCase()==="z"){event.preventDefault();event.shiftKey?redo():undo();}
  if(event.key.toLowerCase()==="y"){event.preventDefault();redo();}
  if(event.key.toLowerCase()==="c" && document.activeElement?.tagName!=="SELECT"){
    event.preventDefault();copySelected();
  }
});
el("rows").addEventListener("paste",event=>{
  const text=event.clipboardData?.getData("text/plain");
  if(!text)return;
  event.preventDefault();
  try{commit(pasteColumn(matrix,selection.start,text),"Pasted joint classifications.");}
  catch(err){message(err.message,true);}
});
render();
