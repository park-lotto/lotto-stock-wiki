import * as T from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {atlas} from './atlas-data.js';
const colors={running:'#53d9b4',waiting:'#8190ad',blocked:'#ffb36d'};
export function createAtlas(canvas,onSelect,onFrame){
 const scene=new T.Scene();scene.background=new T.Color('#0b1220');
 const renderer=new T.WebGLRenderer({canvas,antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputColorSpace=T.SRGBColorSpace;
 const camera=new T.OrthographicCamera(-50,50,35,-35,.1,500);
 const controls=new OrbitControls(camera,canvas);controls.enableDamping=true;controls.minZoom=.2;controls.maxZoom=7;controls.maxPolarAngle=Math.PI*.44;controls.minPolarAngle=.02;
 controls.mouseButtons.LEFT=T.MOUSE.PAN;controls.mouseButtons.RIGHT=T.MOUSE.ROTATE;controls.touches.ONE=T.TOUCH.PAN;controls.touches.TWO=T.TOUCH.DOLLY_PAN;
 scene.add(new T.HemisphereLight('#dcecff','#28364c',2.6));const light=new T.DirectionalLight('#ffffff',3);light.position.set(-20,80,30);scene.add(light);
 const box=new T.BoxGeometry(1,1,1),sphere=new T.SphereGeometry(1,12,8),dummy=new T.Object3D();
 const mat=color=>new T.MeshStandardMaterial({color,roughness:.65,metalness:.12});
 const ground=new T.Mesh(new T.PlaneGeometry(250,220),new T.MeshBasicMaterial({color:'#0e1928'}));ground.rotation.x=-Math.PI/2;ground.position.set(40,-.5,25);scene.add(ground);
 const grid=new T.GridHelper(200,100,'#23354a','#162536');grid.position.set(40,-.45,25);scene.add(grid);
 for(const t of atlas.teams){
  const floor=new T.Mesh(box,new T.MeshBasicMaterial({color:'#1c2b3e'}));floor.position.set(t.x+t.width/2,-.1,t.z+t.height/2);floor.scale.set(t.width,.5,t.height);scene.add(floor);
  const edge=new T.LineSegments(new T.EdgesGeometry(new T.BoxGeometry(t.width,.5,t.height)),new T.LineBasicMaterial({color:t.color,transparent:true,opacity:.5}));edge.position.copy(floor.position);scene.add(edge);
 }
 const meshes=[];
 function instances(geometry,color,scale,offset){
  const m=new T.InstancedMesh(geometry,mat(color),atlas.workers.length);
  atlas.workers.forEach((w,i)=>{dummy.position.set(w.x+offset[0],offset[1],w.z+offset[2]);dummy.scale.set(...scale);dummy.updateMatrix();m.setMatrixAt(i,dummy.matrix);m.setColorAt(i,new T.Color(color));});m.instanceMatrix.needsUpdate=true;scene.add(m);meshes.push({m,color});return m;
 }
 instances(box,'#364b64',[1.95,.15,.85],[0,.6,-.55]); // work surface
 instances(box,'#1e2b40',[1.5,.5,.6],[0,.3,-.55]);
 instances(box,'#182536',[.85,.6,.09],[0,1.02,-.8]);
 instances(box,'#6ebecf',[.7,.4,.03],[0,1.03,-.74]);
 instances(sphere,'#d3dde7',[.28,.4,.24],[0,.62,.25]);
 const heads=instances(sphere,'#e0e8ee',[.4,.34,.32],[0,1.13,.24]);
 instances(box,'#203b50',[.52,.17,.04],[0,1.14,.54]);
 instances(box,'#a1eced',[.08,.06,.04],[-.13,1.16,.57]);instances(box,'#a1eced',[.08,.06,.04],[.13,1.16,.57]);
 const dots=instances(sphere,'#53d9b4',[.11,.11,.11],[.83,.85,-.38]);
 atlas.workers.forEach((w,i)=>dots.setColorAt(i,new T.Color(colors[w.status])));dots.instanceColor.needsUpdate=true;
 // Invisible but generously sized pick volumes; independent of zoomed label visibility.
 const pick=new T.InstancedMesh(box,new T.MeshBasicMaterial({visible:false}),atlas.workers.length);
 atlas.workers.forEach((w,i)=>{dummy.position.set(w.x,.7,w.z);dummy.scale.set(2.2,1.7,2.3);dummy.updateMatrix();pick.setMatrixAt(i,dummy.matrix);});scene.add(pick);
 const ring=new T.Mesh(new T.RingGeometry(.95,1.05,40),new T.MeshBasicMaterial({color:'#b2f3ff',side:T.DoubleSide}));ring.rotation.x=-Math.PI/2;ring.visible=false;scene.add(ring);
 let lines=null,selected=null,activeIds=new Set(atlas.workers.map(w=>w.id));
 function highlight(ids,workerId=null){
  activeIds=new Set(ids);selected=workerId;
  for(const {m,color} of meshes){atlas.workers.forEach((w,i)=>{const c=new T.Color(m===dots?colors[w.status]:color);if(!activeIds.has(w.id))c.multiplyScalar(.22);m.setColorAt(i,c);});m.instanceColor.needsUpdate=true;}
  const w=atlas.workers.find(w=>w.id===workerId);ring.visible=!!w;if(w)ring.position.set(w.x,.24,w.z);
 }
 function route(workers){
  if(lines){scene.remove(lines);lines.geometry.dispose();lines.material.dispose();lines=null;}
  if(workers.length<2)return;
  const pts=[];for(let i=1;i<workers.length;i++){const a=workers[i-1],b=workers[i];const z=Math.max(a.z,b.z)+1.5;const v=[[a.x,.3,a.z],[a.x,.3,z],[b.x,.3,z],[b.x,.3,b.z]];for(let j=1;j<v.length;j++)pts.push(new T.Vector3(...v[j-1]),new T.Vector3(...v[j]));}
  lines=new T.LineSegments(new T.BufferGeometry().setFromPoints(pts),new T.LineBasicMaterial({color:'#62d4ed',transparent:true,opacity:.65}));scene.add(lines);
 }
 function resize(){const r=canvas.getBoundingClientRect(),a=r.width/r.height;camera.left=-48*a;camera.right=48*a;camera.top=48;camera.bottom=-48;camera.updateProjectionMatrix();renderer.setSize(r.width,r.height,false);}
 new ResizeObserver(resize).observe(canvas.parentElement);resize();
 function home(){camera.position.set(40,100,81);controls.target.set(40,0,24);camera.zoom=Math.min(1.4,(camera.right-camera.left)/90);camera.updateProjectionMatrix();controls.update();}
 function focus(x,z,zoom=3){const delta=camera.position.clone().sub(controls.target);controls.target.set(x,0,z);camera.position.copy(controls.target).add(delta);camera.zoom=zoom;camera.updateProjectionMatrix();controls.update();}
 home();const ray=new T.Raycaster(),pointer=new T.Vector2();let down=null,multi=false;const touches=new Set();
 canvas.addEventListener('pointerdown',e=>{touches.add(e.pointerId);if(touches.size>1)multi=true;down=e.button===0?{x:e.clientX,y:e.clientY,moved:false}:null;});
 canvas.addEventListener('pointermove',e=>{if(down&&Math.hypot(e.clientX-down.x,e.clientY-down.y)>5)down.moved=true;});
 canvas.addEventListener('pointercancel',e=>{touches.delete(e.pointerId);down=null;if(!touches.size)multi=false;});
 canvas.addEventListener('pointerup',e=>{touches.delete(e.pointerId);const skip=multi,start=down;down=null;if(!touches.size)multi=false;if(!start||skip||start.moved||e.button!==0||Math.hypot(e.clientX-start.x,e.clientY-start.y)>5)return;
  const r=canvas.getBoundingClientRect();pointer.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);ray.setFromCamera(pointer,camera);const hit=ray.intersectObject(pick)[0];if(hit){const w=atlas.workers[hit.instanceId];if(activeIds.has(w.id))onSelect(w);}
 });
 const projected=new T.Vector3();function project(x,z,y=0){projected.set(x,y,z).project(camera);return {x:(projected.x+1)*canvas.clientWidth/2,y:(1-projected.y)*canvas.clientHeight/2,visible:Math.abs(projected.x)<1&&Math.abs(projected.y)<1};}
 let last=0;
 renderer.setAnimationLoop(time=>{controls.update();renderer.render(scene,camera);if(time-last>65){onFrame({project,zoom:camera.zoom,target:controls.target,selected});last=time;}});
 return {home,focus,highlight,route,project,zoomBy:factor=>{camera.zoom=T.MathUtils.clamp(camera.zoom*factor,.2,7);camera.updateProjectionMatrix();},rotate:enabled=>{controls.mouseButtons.LEFT=enabled?T.MOUSE.ROTATE:T.MOUSE.PAN;},diagnostics:()=>({zoom:camera.zoom,activeCount:activeIds.size,target:controls.target.toArray(),drawCalls:renderer.info.render.calls,points:atlas.workers.map(w=>({id:w.id,...project(w.x,w.z,.8)}))})};
}
