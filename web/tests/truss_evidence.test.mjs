import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { validateTrussEvidence } from "../truss_evidence.mjs";

const fallback=JSON.parse(readFileSync(new URL("../data/truss_demo.json",import.meta.url),"utf8"));
const clone=x=>structuredClone(x);

test("published archived 3D truss has a real original solver provenance",()=>{
  const data=validateTrussEvidence(fallback);
  assert.equal(data.geometry.member_count,10);
  assert.equal(data.native.mesh_type,"C3D10");
  assert.equal(data.native.elements,3595);
  assert.ok(data.native.max_displacement_mm>0);
  assert.ok(data.native.peak_von_mises_mpa>0);
  assert.equal(data.geometry.support_pads.left.axes,"XYZ");
  assert.equal(data.geometry.support_pads.right.axes,"YZ");
  assert.deepEqual(data.geometry.load_pad.force_n,[0,-1000,0]);
  assert.match(data.source_run,/github\.com\/danieloculus0-bot\/EZ-FEA\/actions\/runs\/\d+$/);
});

test("browser refuses fabricated or imbalanced truss numbers",()=>{
  for(const update of [
    d=>d.native.force_balance_check="review",
    d=>d.native.moment_balance_check="review",
    d=>d.native.max_displacement_mm=NaN,
    d=>d.native.peak_von_mises_mpa=-1,
    d=>d.native.mesh_type="C3D4",
    d=>d.native.elements=0,
    d=>d.source_run="https://example.com/fake",
    d=>d.status="live_browser_solved",
    d=>d.geometry.support_pads.right.axes="XYZ",
    d=>d.geometry.load_pad.force_n=[0,-500,0],
    d=>d.geometry.members.pop(),
  ]){
    const d=clone(fallback);
    update(d);
    assert.throws(()=>validateTrussEvidence(d));
  }
});

test("both a checked-in historical fallback and a CI-overlaid original STEP surface disclose their origin",()=>{
  if(fallback.geometry.stl_sha256){
    assert.match(fallback.geometry.stl_sha256,/^[a-f0-9]{64}$/);
    assert.ok(fallback.geometry.stl_surface_triangle_count>=100);
    assert.match(fallback.browser_preview,/tessellated/);
    assert.match(fallback.source_step_sha256,/^[a-f0-9]{64}$/);
  }else{
    assert.match(fallback.browser_preview,/reconstructed/);
  }
  assert.match(fallback.status,/archived_real/);
  assert.match(fallback.limits.join(" "),/not real weld(?: strength|s)/);
});
