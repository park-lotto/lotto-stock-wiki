import test from 'node:test';
import assert from 'node:assert/strict';
import {aBuildings} from '../scene/campus-a-layout.js';
test('A campus has stable identities, rear central HQ and independent left/right programs',()=>{
 const by=id=>aBuildings.find(b=>b.id===id);
 assert.equal(by('hq').x,0);assert(by('hq').z<by('projects').z);
 assert(by('shortem').x<0);assert(by('stock').x>0);
 assert.equal(new Set(aBuildings.map(b=>b.id)).size,aBuildings.length);
 assert(aBuildings.every(b=>b.w>0&&b.d>0&&b.floors>=1));
});
