import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";

const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
const legacy=readFileSync(new URL("../beam-lab.html",import.meta.url),"utf8");
const styles=readFileSync(new URL("../styles.css",import.meta.url),"utf8");
const main=readFileSync(new URL("../truss_demo.mjs",import.meta.url),"utf8");

test("primary homepage is the native Warren truss experiment, not the beam",()=>{
  assert.match(html,/id="workspace"/);
  assert.match(html,/10-member Warren steel truss/);
  assert.match(html,/truss_demo\.mjs/);
  assert.match(html,/1,000 N/);
  assert.match(html,/Left fixed · right slides X/);
  assert.match(html,/id="trussCanvas"/);
  assert.match(html,/id="trussDisplacement"/);
  assert.match(html,/id="trussStress"/);
  assert.match(html,/id="trussSourceLink"/);
  assert.doesNotMatch(html,/id="demoBtn"/);
  assert.doesNotMatch(html,/Try example beam/);
});
test("browser does not claim to compute structural analyses from uploaded STEP",()=>{
  assert.match(html,/not a browser simulation/);
  assert.match(html,/clicking a support does not recompute stress/);
  assert.match(html,/Run EZ-FEA on your own STEP/);
  assert.match(html,/continuous steel members/);
  assert.match(html,/No calculated stress-color contour/);
  assert.match(html,/weld throat rating/);
  assert.match(main,/new native (?:FEA )?solve|new native Gmsh\/CalculiX solve/i);
  assert.match(main,/crypto\.subtle\.digest\("SHA-256"/);
});
test("main page supports rotation, live model edits, CAD import and actual browser beam solving",()=>{
  for(const id of ["modeTruss","modeImport","modeBeam","editSpan","editRise","editChord","editWeb","editLoad",
                    "cadFileInput","markHold","markForce","saveCadSetup",
                    "downloadSetup","downloadMesh","restoreTruss",
                    "beamLength","beamWidth","beamHeight","beamLoad","beamMaterial"])
    assert.ok(html.includes('id="'+id+'"'),"Missing functional on-page input: "+id);
  assert.match(main,/new OrbitControls\(/);
  assert.match(main,/function renderTruss\(/);
  assert.match(main,/function trussEdited\(/);
  assert.match(main,/function importPart\(/);
  assert.match(main,/function drawBeam\(/);
  assert.match(main,/analyzeBeam\(/);
  assert.match(main,/resetOutput\(/);
  assert.match(main,/STLExporter/);
  assert.match(main,/ReadStepFile/);
});

test("legacy beam education is preserved off the primary homepage",()=>{
  assert.match(html,/href="\.\/beam-lab.html"/);
  assert.match(legacy,/id="demoBtn"/);
  assert.match(legacy,/id="runBtn"/);
  assert.match(legacy,/id="viewerCanvas"/);
  assert.match(legacy,/main\.mjs/);
});
test("real case provenance and specimen interaction are accessible",()=>{
  assert.match(html,/href="https:\/\/github\.com\/danieloculus0-bot\/EZ-FEA\/actions\/runs\/40473627691"/);
  assert.match(html,/id="toggleSupports"/);
  assert.match(html,/id="toggleLoad"/);
  assert.match(html,/id="resetTrussView"/);
  assert.match(main,/STLLoader/);
  assert.match(main,/warren_truss\.stl/);
  assert.match(main,/SHA-256/);
});
test("dark restrained website remains responsive",()=>{
  assert.match(styles,/\.truss-page\s*\{/);
  assert.match(styles,/#050607/);
  assert.match(styles,/#c5ff4a/);
  assert.match(styles,/@media\(max-width:600px\)/);
});
