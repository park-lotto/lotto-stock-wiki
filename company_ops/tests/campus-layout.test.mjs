import test from 'node:test';
import assert from 'node:assert/strict';
import {buildings,waterRings} from '../scene/campus-layout.js';
test('two program wings retain twenty unique buildings and clear waterways',()=>{
 assert.equal(buildings.length,20);assert.equal(new Set(buildings.map(b=>b.id)).size,20);
 for(const program of ['shortem','stock'])assert.equal(buildings.filter(b=>b.program===program).length,10);
 for(const b of buildings){assert(Math.abs(Math.sin(b.angle))>.45);for(const [inner,outer]of waterRings)assert(b.radius+b.depth/2<inner||b.radius-b.depth/2>outer);}
});
