/**
 * EZ-FEA browser-only, genuinely calculated 2D beam element analysis.
 * A fixed-free prismatic rectangular beam with transverse end point load.
 * N, mm, MPa. Small-deflection linear Euler-Bernoulli beam FEM.
 * NOT a 3D analysis of imported CAD.
 */
export const PRESETS = Object.freeze({
  a36: { name: "A36 steel (nominal)", modulus: 200000, yield: 250, tint: 0x8ca6be },
  aluminum: { name: "6061-T6 aluminum (nominal)", modulus: 69000, yield: 275, tint: 0xaeb8c8 },
  stainless: { name: "304 stainless (nominal)", modulus: 193000, yield: 215, tint: 0xa7bfcb }
});

const finite = (v) => Number.isFinite(v);
export function solveLinear(matrix, vector) {
  const n = vector.length;
  const a = matrix.map((row, i) => row.slice().concat(vector[i]));
  for (let i=0; i<n; i++) {
    let pivot = i;
    for (let r=i+1; r<n; r++) if (Math.abs(a[r][i]) > Math.abs(a[pivot][i])) pivot=r;
    if (Math.abs(a[pivot][i]) < 1e-18) throw new Error("The beam model is unstable or singular.");
    [a[i],a[pivot]]=[a[pivot],a[i]];
    const scale=a[i][i];
    for (let col=i; col<=n; col++) a[i][col] /= scale;
    for (let r=0; r<n; r++) {
      if (r===i) continue;
      const m=a[r][i];
      if (!m) continue;
      for (let col=i; col<=n; col++) a[r][col]-=m*a[i][col];
    }
  }
  return a.map(row=>row[n]);
}
function validate(p) {
  const keys=["length","width","height","force","modulus","yield"];
  for (const key of keys) if (!finite(p[key])) throw new Error(key+" must be a number.");
  for (const key of ["length","width","height","modulus","yield"]) {
    if (p[key]<=0) throw new Error(key+" must be greater than zero.");
  }
  if (p.length>1e7 || p.width>1e7 || p.height>1e7) throw new Error("Dimensions are outside demo limits.");
  if (Math.abs(p.force)>1e9) throw new Error("Load is outside demo limits.");
}
export function analyzeBeam(params, segments=8) {
  const p={...params};
  validate(p);
  if (!Number.isInteger(segments)||segments<1||segments>200) throw new Error("Invalid element count.");
  const {length:L,width:b,height:h,force:P,modulus:E,yield:Sy}=p;
  const area=b*h;
  const inertia=b*h*h*h/12;
  const le=L/segments;
  const count=2*(segments+1);
  const K=Array.from({length:count},()=>Array(count).fill(0));
  const factor=E*inertia/Math.pow(le,3);
  const k=[
    [12, 6*le, -12, 6*le],
    [6*le, 4*le*le, -6*le, 2*le*le],
    [-12, -6*le, 12, -6*le],
    [6*le, 2*le*le, -6*le, 4*le*le]
  ];
  for (let e=0;e<segments;e++) {
    const ids=[e*2,e*2+1,e*2+2,e*2+3];
    for(let i=0;i<4;i++) for(let j=0;j<4;j++) K[ids[i]][ids[j]] += factor*k[i][j];
  }
  const f=Array(count).fill(0);
  f[count-2]=-P; // Positive force means downward.
  const free=Array.from({length:count-2},(_,i)=>i+2);
  const solution=solveLinear(free.map(i=>free.map(j=>K[i][j])),free.map(i=>f[i]));
  const d=[0,0,...solution];
  const tip=d[count-2];
  const exact=P*Math.pow(L,3)/(3*E*inertia);
  const deflection=Math.abs(tip);
  const stress=Math.abs(P)*L*(h/2)/inertia;
  const safety=stress===0 ? null : Sy/stress;
  const x=Array.from({length:segments+1},(_,i)=>i*le);
  const curve=x.map((position,i)=>({x:position,y:d[2*i],slope:d[2*i+1]}));
  return {
    method:"2D Euler-Bernoulli beam finite elements (fixed-free, transverse end point force)",
    assumptions:["Rectangular, uniform, homogeneous, isotropic section","Fully fixed left end, end point load at right","Small deformations and linear elastic behavior","Static planar bending only; no shear deformation or buckling"],
    units:{length:"mm",load:"N",stress:"MPa",displacement:"mm"},
    area_mm2:area,second_moment_mm4:inertia,element_count:segments,
    deflection_mm:deflection,signed_tip_y_mm:tip,
    analytical_reference_mm:Math.abs(exact),
    verification_relative_error:Math.abs(deflection-Math.abs(exact))/Math.max(Math.abs(exact),1e-12),
    peak_bending_stress_mpa:stress,nominal_yield_mpa:Sy,
    safety_factor_yield:safety,
    exceeds_nominal_yield:stress>Sy,
    curve,
    validation_status:"UNVALIDATED EDUCATIONAL DEMO, NOT 3D CAD FEA"
  };
}
