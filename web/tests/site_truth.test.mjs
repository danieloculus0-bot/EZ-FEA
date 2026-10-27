import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";

const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
const styles=readFileSync(new URL("../styles.css",import.meta.url),"utf8");

test("homepage promotes genuine native desktop, not a false browser solver",()=>{
  assert.match(html,/id="native-app"/);
  assert.match(html,/>Get the desktop app/);
  assert.match(html,/python app\.py/);
  assert.match(html,/Gmsh \+ CalculiX/);
  assert.match(html,/single STEP solid/i);
  assert.match(html,/does <strong>not<\/strong> solve your uploaded CAD/);
  assert.match(html,/id="workspace"/);
  assert.match(html,/INTERACTIVE BROWSER LAB · NOT THE NATIVE SOLVER/);
});
test("experimental engineering modules are not advertised as complete general assembly solvers",()=>{
  assert.match(html,/Constraints need review/);
  assert.match(html,/not verified bolts or fixity/);
  assert.match(html,/previously solved 3D frame results/);
  assert.match(html,/not a live solver running in the browser/);
});
test("desktop and example actions remain real links and working native-demo controls",()=>{
  assert.match(html,/href="https:\/\/github\.com\/danieloculus0-bot\/EZ-FEA#run-the-actual-ez-fea-desktop-program"/);
  assert.match(html,/href="#workspace"/);
  for(const id of ["demoBtn","runBtn","frameSelect","viewerCanvas","resultValues","cadNoSolver"]){
    assert.ok(html.includes('id="'+id+'"'),"Existing browser demo element removed: "+id);
  }
});
test("home prioritizes near-black panels with a restrained lime primary action",()=>{
  assert.match(styles,/\.native-hero\s*\{/);
  assert.match(styles,/background:\s*#c5ff4a/);
  assert.match(styles,/#050607/);
  assert.match(styles,/@media\(max-width:640px\)/);
});
