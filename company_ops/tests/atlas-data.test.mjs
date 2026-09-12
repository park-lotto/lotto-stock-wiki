import {test} from 'node:test';
import assert from 'node:assert/strict';
import {atlas, searchWorkers, counts} from '../scene/atlas-data.js';
test('200 unique fixed seats and 30 valid projects, explicitly illustrative',()=>{
 assert.equal(atlas.workers.length,200); assert.equal(atlas.projects.length,30);
 assert.equal(atlas.mode,'example');
 assert.equal(new Set(atlas.workers.map(w=>w.id)).size,200);
 assert.equal(new Set(atlas.workers.map(w=>`${w.x},${w.z}`)).size,200);
 for(const w of atlas.workers){assert(atlas.teams.some(t=>t.id===w.team));assert(atlas.projects.some(p=>p.id===w.project));}
 for(const p of atlas.projects)assert(atlas.workers.some(w=>w.project===p.id));
 assert.deepEqual(counts(atlas.workers),{total:200,running:140,waiting:50,blocked:10});
});
test('search combines ID, task, project and status without moving seats',()=>{
 const before=JSON.stringify(atlas.workers);
 assert.equal(searchWorkers('w-001').length,1);
 assert(searchWorkers('수집 안정화').length>=5);
 const blocked=searchWorkers('',{status:'blocked'});assert.equal(blocked.length,10);
 assert(searchWorkers('',{team:atlas.teams[0].id}).every(w=>w.team===atlas.teams[0].id));
 assert.equal(searchWorkers('존재하지않는워커').length,0);
 assert.equal(JSON.stringify(atlas.workers),before);
});
