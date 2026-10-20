/** Explicit spreadsheet operations over *candidate* joint records.
 * Nothing here sends solver constraints or fabricates connection stiffness.
 */
export const JOINT_TYPES = Object.freeze(["Unassigned","Welded","Bolted","Pinned","Bearing","Bonded","Sliding","Contact only"]);
export const EDITABLE = Object.freeze(["joint_type"]);
export const SCHEMA = "ezfea.joint_matrix.v1";

export function checkedType(text) {
  if (typeof text !== "string") throw new Error("Joint type must be text");
  const value=text.trim().toLowerCase().replaceAll("_"," ");
  const type=JOINT_TYPES.find(x=>x.toLowerCase()===value);
  if (!type) throw new Error("Invalid joint type: "+String(text));
  return type;
}
export function validateMatrix(data) {
  if (!data || data.schema !== SCHEMA || !Array.isArray(data.rows)) throw new Error("Expected EZ-FEA Joint Matrix JSON");
  const seen = new Set();
  const rows = data.rows.map(r => {
    if (typeof r.joint_id !== "string" || !r.joint_id || seen.has(r.joint_id)) throw new Error("Missing/duplicate joint ID");
    seen.add(r.joint_id);
    for (const key of ["component_a","component_b","face_a","face_b"]) {
      if (!Number.isInteger(Number(r[key])) || r[key] === "" || r[key] == null) throw new Error("Bad geometric mate identity");
    }
    const type=checkedType(r.joint_type);
    if (r.mechanical_model != null && r.mechanical_model !== "unassigned")
      throw new Error("Physical solver connection models must be reviewed in native tooling; no automatic constraints");
    return {
      ...r,
      joint_type:type,
      joint_confirmation: type === "Unassigned" ? "not_reviewed" : "explicit_user_choice",
      mechanical_model:"unassigned"
    };
  });
  return {...data, rows};
}
export function sampleMatrix() {
  return validateMatrix({
    schema:SCHEMA,ground_component:1,
    components:[{id:1,label:"Base plate",grounded:true},
      {id:2,label:"Upright",grounded:false},
      {id:3,label:"Crossmember",grounded:false},
      {id:4,label:"Support bracket",grounded:false},
      {id:5,label:"Arm",grounded:false},
      {id:6,label:"Shaft",grounded:false}],
    rows:[
      [1,2,101,201],[2,3,102,202],[3,4,103,203],[4,5,104,204],[5,6,105,205]
    ].map(([a,b,f,g],i)=>({joint_id:\`J-\${String(i+1).padStart(3,"0")}\`,
      component_a:a,component_b:b,face_a:f,face_b:g,joint_type:"Unassigned",
      joint_confirmation:"not_reviewed",mechanical_model:"unassigned",
      candidate_kind:"sample_only_not_from_cad"}))
  });
}
function change(row,value) {
  const joint_type=checkedType(value);
  return {...row,joint_type,
    joint_confirmation:joint_type==="Unassigned"?"not_reviewed":"explicit_user_choice",
    mechanical_model:"unassigned"};
}
export function setJointType(matrix,row,value) {
  if (!Number.isInteger(row) || row<0 || row>=matrix.rows.length) throw new Error("Row out of range");
  return {...matrix,rows:matrix.rows.map((r,i)=>i===row?change(r,value):r)};
}
export function fillDown(matrix,start,end) {
  if (!Number.isInteger(start)||!Number.isInteger(end)||start<0||start>end||end>=matrix.rows.length)
    throw new Error("Invalid fill range");
  const value=matrix.rows[start].joint_type;
  return {...matrix,rows:matrix.rows.map((r,i)=>i>start&&i<=end?change(r,value):r)};
}
export function pasteColumn(matrix,start,tsv) {
  if (typeof tsv !== "string"||!tsv.trim()) throw new Error("Empty clipboard");
  const values=tsv.trim().split(/\r?\n/).map(s=>s.trim());
  if (values.some(x=>x.includes("\t"))) throw new Error("Paste must be a single joint-type column");
  if (!Number.isInteger(start)||start<0||start+values.length>matrix.rows.length)
    throw new Error("Paste exceeds the available joint rows");
  // Normalize the ENTIRE paste before writing, so failures are atomic.
  const verified=values.map(checkedType);
  let rows=matrix.rows.map(r=>({...r}));
  verified.forEach((value,i)=>{rows[start+i]=change(rows[start+i],value)});
  return {...matrix,rows};
}
export function toCSV(matrix) {
  const cols=["joint_id","component_a","component_b","face_a","face_b","joint_type","joint_confirmation","mechanical_model"];
  const csv=v=> '"' + String(v??"").replaceAll('"','""') + '"';
  return [cols.join(","),...matrix.rows.map(row=>cols.map(c=>csv(row[c])).join(","))].join("\r\n")+"\r\n";
}
export function userSelectionCounts(matrix) {
  return matrix.rows.reduce((t,r)=>(t[r.joint_type]=(t[r.joint_type]??0)+1,t),{});
}
