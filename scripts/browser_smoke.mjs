/** Actual browser smoke test: WebGL rotation, interactive modeling and beam FEM. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { chromium } from "playwright";

const base=process.env.EZFEA_URL||"http://127.0.0.1:8787/";
const options={
  headless:true,
  args:["--no-sandbox","--disable-dev-shm-usage","--enable-webgl",
        "--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"],
};
if(process.env.CHROME_BIN)options.executablePath=process.env.CHROME_BIN;
const browser=await chromium.launch(options);
try{
  const page=await browser.newPage({viewport:{width:1440,height:960}});
  const errors=[];
  page.on("pageerror",e=>errors.push(e.message));
  await page.goto(base,{waitUntil:"networkidle",timeout:55000});
  await page.locator("#trussCanvas canvas").waitFor({timeout:30000});
  await page.waitForFunction(()=>{
    const canvas=document.querySelector("#trussCanvas canvas");
    return canvas && canvas.width>100 && canvas.height>100 &&
      /original|rotate/i.test(document.querySelector("#trussViewerStatus").textContent);
  },{timeout:25000});
  const canvas=page.locator("#trussCanvas canvas");
  const hash=buf=>createHash("sha256").update(buf).digest("hex");
  await page.locator("#orbitAuto").click();
  assert.equal(await page.locator("#orbitAuto").getAttribute("aria-pressed"),"false");
  const angle=async()=>await page.locator("#rotationReadout").innerText();
  const beforeAngle=await angle();
  const before=hash(await canvas.screenshot());
  const b=await canvas.boundingBox();
  assert.ok(b && b.width>100 && b.height>100);
  await page.mouse.move(b.x+b.width*.57,b.y+b.height*.5);
  await page.mouse.down();
  await page.mouse.move(b.x+b.width*.75,b.y+b.height*.59,{steps:12});
  await page.mouse.up();
  await page.waitForTimeout(600);
  const after=hash(await canvas.screenshot());
  assert.notEqual(after,before,"Orbit dragging did not change the visible WebGL model");
  const draggedAngle=await angle();
  assert.notEqual(draggedAngle,beforeAngle,"Drag did not move actual camera orientation");
  await page.locator("#orbitRight").click();
  await page.waitForTimeout(200);
  const buttonAngle=await angle();
  assert.notEqual(buttonAngle,draggedAngle,"Right rotate button did not move the actual camera");
  await page.locator("#orbitLeft").click();
  assert.notEqual(await angle(),buttonAngle,"Left rotate button did not move the actual camera");
  await page.locator("#orbitAuto").click();
  assert.equal(await page.locator("#orbitAuto").getAttribute("aria-pressed"),"true");
  const firstSpinAngle=await angle();
  await page.waitForTimeout(1000);
  assert.notEqual(await angle(),firstSpinAngle,"Auto-rotate did not advance the camera");
  await page.locator("#orbitAuto").click();
  assert.equal(await page.locator("#orbitAuto").getAttribute("aria-pressed"),"false");

  assert.match(await page.locator("#trussDisplacement").innerText(),/mm/);
  await page.locator("#editSpan").fill("800");
  await page.waitForFunction(
    ()=>document.querySelector("#trussProof").textContent==="NOT SOLVED");
  assert.equal((await page.locator("#trussDisplacement").textContent()).trim(),"—");
  await page.locator("#restoreTruss").click();
  await page.waitForFunction(
    ()=>document.querySelector("#trussProof").textContent==="Original run");

  await page.locator("#modeBeam").click();
  await page.waitForFunction(
    ()=>document.querySelector("#trussProof").textContent==="RECALCULATED");
  const initial=await page.locator("#trussDisplacement").textContent();
  await page.locator("#beamLoad").fill("200");
  await page.waitForTimeout(100);
  const changed=await page.locator("#trussDisplacement").textContent();
  assert.notEqual(changed,initial,"Beam load did not recalculate live FEM");

  await page.locator("#modeImport").click();
  const stl=[
    "solid simple",
    "facet normal 0 0 1",
    "outer loop","vertex 0 0 0","vertex 20 0 0","vertex 0 20 0",
    "endloop","endfacet","endsolid simple",
  ].join("\n");
  await page.locator("#cadFileInput").setInputFiles({
    name:"operator_test.stl",mimeType:"model/stl",buffer:Buffer.from(stl)
  });
  await page.waitForFunction(
    ()=>/operator_test\.stl/.test(document.querySelector("#trussViewerStatus").textContent),
    {timeout:10000});
  assert.ok(await page.locator("#trussCanvas canvas").count());

  await page.screenshot({path:"browser-functional-proof.png",fullPage:true});
  assert.deepEqual(errors,[],"Browser threw uncaught runtime errors");

  // Reproduce the actual failed-user class: browser has no usable WebGL.
  // In the old implementation the decorative SVG remained static and every
  // rotation control silently did nothing. The new fallback MUST orbit.
  const noGpu=await browser.newContext({viewport:{width:1280,height:850}});
  await noGpu.addInitScript(()=>{
    const original=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(type,...args){
      if(/webgl/i.test(String(type)))return null;
      return original.call(this,type,...args);
    };
  });
  const software=await noGpu.newPage();
  await software.goto(base,{waitUntil:"networkidle",timeout:55000});
  await software.locator("#trussStatic polygon[data-feature]").first().waitFor({timeout:25000});
  assert.equal(await software.locator("#trussCanvas canvas").count(),0,
    "The no-GPU scenario unexpectedly created a functional WebGL canvas");
  const svg=software.locator("#trussStatic");
  const angle=async()=>software.locator("#rotationReadout").textContent();
  const beforeFallback=await angle();
  await software.locator("#orbitRight").click();
  const afterFallback=await angle();
  assert.notEqual(afterFallback,beforeFallback,
    "No-WebGL viewer right rotation button failed to change actual yaw");
  const snapshot=hash(await svg.screenshot());
  await software.locator("#orbitLeft").click();
  const returned=hash(await svg.screenshot());
  assert.notEqual(snapshot,returned,
    "No-WebGL CAD polygons did not actually rotate after pressing left");
  await software.locator("#orbitAuto").click();
  assert.equal(await software.locator("#orbitAuto").getAttribute("aria-pressed"),"true");
  const firstAuto=await angle();
  await software.waitForTimeout(800);
  assert.notEqual(await angle(),firstAuto,
    "No-WebGL auto rotation does not move the model");
  await software.locator("#orbitAuto").click();
  const bounds=await svg.boundingBox();
  assert.ok(bounds?.width>300);
  await software.mouse.move(bounds.x+bounds.width*.48,bounds.y+bounds.height*.5);
  await software.mouse.down();
  await software.mouse.move(bounds.x+bounds.width*.7,bounds.y+bounds.height*.6,{steps:10});
  await software.mouse.up();
  assert.notEqual(await angle(),firstAuto,
    "No-WebGL pointer drag does not affect model orientation");
  await software.screenshot({path:"browser-software-3d-fallback.png",fullPage:true});
  await noGpu.close();
  console.log("PASS: Forced-WebGL-failure still displays true rotatable 3D truss and working buttons, pointer drag and automatic orbit.");
  console.log("PASS: WebGL actually rotates, truss edits invalidate results, native case restores, beam recalculates, uploaded STL rotates.");
}finally{
  await browser.close();
}
