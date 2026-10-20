import test from "node:test";
import assert from "node:assert/strict";
import {analyzeBeam, PRESETS} from "../beam.mjs";
import {reviewBeam, reviewCad, reviewFrameStudies} from "../bean_advisor.mjs";

function beam(force=100,length=150,height=10) {
  return {length,width:25,height,force,
          modulus:PRESETS.a36.modulus,yield:PRESETS.a36.yield};
}

test("BEAN reads actual computed beam results rather than manufactured values",()=>{
  const result=analyzeBeam(beam());
  const review=reviewBeam(beam(),result);
  assert.match(review.advice,/bending stress/);
  assert.match(review.advice,/analytical cantilever/);
  assert.match(review.advice,new RegExp(String(Number((100*result.peak_bending_stress_mpa/result.nominal_yield_mpa).toPrecision(3)))));
});

test("BEAN flags a deep beam and high-yield usage",()=>{
  const params=beam(9000,50,12);
  const result=analyzeBeam(params);
  const review=reviewBeam(params,result);
  assert.equal(review.kind,"review");
  assert.match(review.advice,/shear deflection/);
  assert.match(review.advice,/nominal yield/);
});

test("BEAN never claims CAD marks are actual FEA joint restraints",()=>{
  const review=reviewCad({filename:"fixture.step",fixed:{x:0,y:0,z:0},load:{x:30,y:40,z:0}});
  assert.match(review.advice,/50/);
  assert.match(review.advice,/not solver-ready/);
  assert.doesNotMatch(review.advice,/certified/);
});

test("BEAN recognizes missing numerical evidence",()=>{
  const params=beam();
  const review=reviewBeam(params,{deflection_mm:1,peak_bending_stress_mpa:NaN,verification_relative_error:0});
  assert.equal(review.kind,"needs-input");
});

test("recorded frame evidence only produces a comparison when full evidence exists",()=>{
  const studies=[
    {key:"01_portal_vertical",max_displacement_mm:.0027,max_von_mises_mpa:1.42,force_balance_relative_error:1e-8},
    {key:"02_rectangle_racking",max_displacement_mm:.01346,max_von_mises_mpa:4.74,force_balance_relative_error:1e-8},
    {key:"03_braced_racking",max_displacement_mm:.00204,max_von_mises_mpa:1.12,force_balance_relative_error:1e-8},
  ];
  const check=reviewFrameStudies(studies);
  assert.equal(check.bracedStiffer,true);
  assert.ok(check.ratio>6);
  assert.throws(()=>reviewFrameStudies(studies.map((s,i)=>i===2?{...s,max_displacement_mm:NaN}:s)));
});
