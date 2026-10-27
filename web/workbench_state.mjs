/** Geometry transformations and validity boundaries; no fake native solving. */
export const DEFAULT_TRUSS=Object.freeze({
  span:600,rise:180,chord:24,web:18,load:1000,
  young:200000,poisson:.26,yield:250,leftAxes:"XYZ",rightAxes:"YZ"
});

export function validateTrussInputs(v){
  if(!v||Object.keys(DEFAULT_TRUSS).filter(k=>!k.endsWith("Axes")).some(k=>!Number.isFinite(v[k])))
    throw new Error("Enter a finite number for every truss dimension and load");
  for(const [k,min,max] of [["span",150,3000],["rise",50,1500],
                            ["chord",5,150],["web",5,150],["load",0,1000000],
                            ["young",1,1000000],["poisson",-.99,.499],["yield",1,1000000]]){
    if(v[k]<min||v[k]>max)throw new Error(k+" outside "+min+"–"+max);
  }
  if(!["XYZ","YZ","XZ","XY"].includes(v.leftAxes) ||
     !["XYZ","YZ","XZ","XY"].includes(v.rightAxes))
    throw new Error("Select valid translational support directions");
  if(v.chord*3>=v.span || v.web*3>=v.rise)
    throw new Error("Section thickness is too large for the selected truss layout");
  return v;
}
export function isRecordedTruss(v){
  return Object.entries(DEFAULT_TRUSS).every(([k,value])=>v[k]===value);
}
export function alteredMembers(original,v){
  validateTrussInputs(v);
  if(!original || !Array.isArray(original.members) || original.members.length!==10)
    throw new Error("Source Warren truss recipe has not been loaded");
  return original.members.map(m=>({
    id:m.id,kind:m.kind,
    start:[m.start[0]*v.span/600,m.start[1]*v.rise/180,m.start[2]],
    end:[m.end[0]*v.span/600,m.end[1]*v.rise/180,m.end[2]],
    square_side_mm:m.kind==="chord"?v.chord:v.web
  }));
}
export function hasNativeResults(mode,v){
  return mode==="truss"&&isRecordedTruss(v);
}
