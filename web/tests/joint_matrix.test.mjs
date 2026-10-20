import test from "node:test";
import assert from "node:assert/strict";
import {
  JOINT_TYPES, sampleMatrix, validateMatrix, setJointType, fillDown,
  pasteColumn, toCSV
} from "../joint_matrix_core.mjs";

test("Joint Matrix dropdown preserves mechanical physics unassigned",()=>{
  const sample=sampleMatrix();
  assert.equal(sample.rows.length,5);
  assert.deepEqual(JOINT_TYPES.slice(0,3),["Unassigned","Welded","Bolted"]);
  assert.equal(sample.rows[0].joint_type,"Unassigned");
  const changed=setJointType(sample,0,"Welded");
  assert.equal(changed.rows[0].joint_type,"Welded");
  assert.equal(changed.rows[0].mechanical_model,"unassigned");
  assert.equal(sample.rows[0].joint_type,"Unassigned");
});

test("Excel-style fill down copies welded to all selected joints",()=>{
  const first=setJointType(sampleMatrix(),0,"Welded");
  const filled=fillDown(first,0,4);
  assert.deepEqual(filled.rows.map(r=>r.joint_type),Array(5).fill("Welded"));
  assert.ok(filled.rows.every(r=>r.mechanical_model==="unassigned"));
  assert.deepEqual(filled.rows.map(r=>r.joint_id),first.rows.map(r=>r.joint_id));
  assert.ok(validateMatrix(filled));
});

test("paste supports classifications in rows and is atomic on invalid input",()=>{
  const matrix=sampleMatrix();
  const pasted=pasteColumn(matrix,1,"Welded\nBolted\nPinned");
  assert.deepEqual(pasted.rows.slice(1,4).map(r=>r.joint_type),
                   ["Welded","Bolted","Pinned"]);
  assert.throws(()=>pasteColumn(matrix,1,"Welded\nUnicorn"),/Invalid joint type/);
  assert.throws(()=>pasteColumn(matrix,4,"Welded\nPinned"),/exceeds/);
  assert.equal(matrix.rows[1].joint_type,"Unassigned");
});

test("JSON schema and spreadsheet CSV keep CAD mate identities",()=>{
  const original=sampleMatrix();
  const serialized=JSON.stringify(original);
  const imported=validateMatrix(JSON.parse(serialized));
  assert.equal(imported.ground_component,1);
  assert.equal(imported.rows[0].face_a,101);
  assert.match(toCSV(imported),/joint_id,component_a,component_b/);
  const corrupted=JSON.parse(serialized);
  corrupted.rows[1].joint_id=corrupted.rows[0].joint_id;
  assert.throws(()=>validateMatrix(corrupted),/duplicate/);
  corrupted.rows[1].joint_id="J-002";
  corrupted.rows[1].mechanical_model="ideal_bonded";
  assert.throws(()=>validateMatrix(corrupted),/Physical solver/);
});
