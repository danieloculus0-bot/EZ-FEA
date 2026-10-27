import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import {
  DEFAULT_TRUSS,validateTrussInputs,isRecordedTruss,alteredMembers,hasNativeResults
} from "../workbench_state.mjs";

const source=JSON.parse(readFileSync(new URL("../data/truss_demo.json",import.meta.url),"utf8"));
test("original truss exactly matches archived solved case",()=>{
  assert.equal(isRecordedTruss(DEFAULT_TRUSS),true);
  assert.equal(hasNativeResults("truss",DEFAULT_TRUSS),true);
  assert.deepEqual(alteredMembers(source.geometry,DEFAULT_TRUSS),
                   source.geometry.members);
});
test("changing ANY structural input invalidates old CalculiX results",()=>{
  for(const key of Object.keys(DEFAULT_TRUSS)){
    const changed={...DEFAULT_TRUSS,[key]:DEFAULT_TRUSS[key]+5};
    assert.equal(isRecordedTruss(changed),false,key);
    assert.equal(hasNativeResults("truss",changed),false,key);
  }
  assert.equal(hasNativeResults("import",DEFAULT_TRUSS),false);
  assert.equal(hasNativeResults("beam",DEFAULT_TRUSS),false);
});
test("edited Warren truss retains its member identity and transforms real geometry",()=>{
  const v={...DEFAULT_TRUSS,span:1200,rise:300,chord:32,web:22,load:5000};
  const bars=alteredMembers(source.geometry,v);
  assert.equal(bars.length,10);
  assert.equal(bars[0].end[0],1200);
  assert.equal(bars[1].start[1],300);
  assert.equal(bars.filter(b=>b.kind==="web").length,8);
  assert.equal(bars.filter(b=>b.kind==="chord").every(b=>b.square_side_mm===32),true);
  assert.equal(bars.filter(b=>b.kind==="web").every(b=>b.square_side_mm===22),true);
});
test("refuse invalid truss designs rather than generate misleading CAD",()=>{
  for(const v of [
    {span:0},{rise:1},{chord:0},{web:999},{load:-1000},
    {span:NaN},{span:Infinity},{span:150,chord:100},
  ]){
    assert.throws(()=>validateTrussInputs({...DEFAULT_TRUSS,...v}));
  }
});
