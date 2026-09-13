import test from 'node:test';
import assert from 'node:assert/strict';
import {movePlayer,floorAt} from '../scene/hq-navigation.js';
const floor={min:[-20,-.1,-20],max:[20,0,20]};
test('walks on floor',()=>{const p=movePlayer({x:0,y:0,z:0},1,0,{floors:[floor],solids:[]});assert(Math.abs(p.x-1)<.001);assert.equal(p.y,0);});
test('cannot tunnel through wall',()=>{const wall={min:[.8,0,-2],max:[1,3,2]};const p=movePlayer({x:0,y:0,z:0},4,0,{floors:[floor],solids:[wall]});assert(p.x<.55);});
test('closed door blocks; open door passes',()=>{const door={min:[.8,0,-2],max:[1,3,2],door:true};const data={floors:[floor],solids:[door]};assert(movePlayer({x:0,y:0,z:0},2,0,data,false).x<.55);assert(movePlayer({x:0,y:0,z:0},2,0,data,true).x>1.9);});
test('small steps climb; tall wall and unsupported drops do not',()=>{const step={min:[.5,0,-1],max:[3,.2,1]};assert.equal(movePlayer({x:0,y:0,z:0},1,0,{floors:[floor,step],solids:[]}).y,.2);assert.equal(floorAt(0,0,0,[{min:[-1,0,-1],max:[1,5,1]}]),null);const p=movePlayer({x:0,y:3,z:0},3,0,{floors:[floor,{min:[-1,2,-1],max:[1,3,1]}],solids:[]});assert(p.x<1.3);assert.equal(p.y,3);});
