import assert from "node:assert/strict";
import { test } from "node:test";
import { analyzeBeam, solveLinear, PRESETS } from "../beam.mjs";
test("reference cantilever deflection from beam FEM equals analytical theory",()=>{
  const b=analyzeBeam({length:150,width:25,height:10,force:100,modulus:200000,yield:250},8);
  const expected=100*150**3/(3*200000*(25*10**3/12));
  assert.ok(Math.abs(b.deflection_mm-expected)<1e-7);
  assert.ok(b.verification_relative_error<1e-8);
  assert.ok(Math.abs(b.peak_bending_stress_mpa-36)<1e-6);
  assert.ok(Math.abs(b.safety_factor_yield-250/36)<1e-6);
});
test("more elements preserve the reference result",()=>{
  for (const n of [1,2,4,12]) {
    const r=analyzeBeam({length:200,width:20,height:15,force:400,modulus:69000,yield:275},n);
    assert.ok(r.verification_relative_error<1e-7);
  }
});
test("zero force yields no displacement and no finite safety factor",()=>{
  const r=analyzeBeam({length:200,width:20,height:15,force:0,modulus:69000,yield:275});
  assert.equal(r.deflection_mm,0);
  assert.equal(r.safety_factor_yield,null);
});
test("increased load increases deflection linearly",()=>{
  const p={length:125,width:12,height:12,force:80,modulus:193000,yield:215};
  const one=analyzeBeam(p),two=analyzeBeam({...p,force:160});
  assert.ok(Math.abs(two.deflection_mm/one.deflection_mm-2)<1e-8);
  assert.ok(Math.abs(two.peak_bending_stress_mpa/one.peak_bending_stress_mpa-2)<1e-8);
});
test("negative load reverses deflection sign",()=>{
  const p={length:125,width:12,height:12,force:80,modulus:193000,yield:215};
  const one=analyzeBeam(p),two=analyzeBeam({...p,force:-80});
  assert.ok(one.signed_tip_y_mm<0);
  assert.ok(two.signed_tip_y_mm>0);
  assert.equal(one.deflection_mm,two.deflection_mm);
});
test("rejects invalid inputs",()=>{
  assert.throws(()=>analyzeBeam({length:0,width:10,height:10,force:1,modulus:200000,yield:250}),/greater than zero/);
  assert.throws(()=>analyzeBeam({length:100,width:10,height:10,force:1,modulus:200000,yield:250},0),/element/);
  assert.equal(PRESETS.a36.modulus,200000);
});
test("Gaussian elimination with pivoting",()=>{
  const s=solveLinear([[0,2],[3,4]],[4,11]);
  assert.ok(Math.abs(s[0]-1)<1e-12);
  assert.ok(Math.abs(s[1]-2)<1e-12);
});
