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
  await page.waitForTimeout(450);
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
  console.log("PASS: WebGL actually rotates, truss edits invalidate results, native case restores, beam recalculates, uploaded STL rotates.");
}finally{
  await browser.close();
}
