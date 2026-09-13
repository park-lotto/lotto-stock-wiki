import * as T from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {prepareModel} from './hq-walk-model.js';
import {movePlayer} from './hq-navigation.js';

const $=s=>document.querySelector(s),canvas=$('#scene'),scene=new T.Scene();
scene.background=new T.Color('#bacbd5');scene.fog=new T.Fog('#bacbd5',130,400);
const renderer=new T.WebGLRenderer({canvas,antialias:true,powerPreference:'high-performance'});
renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1;
renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;
const camera=new T.PerspectiveCamera(48,1,.08,1500),orbit=new OrbitControls(camera,canvas);
orbit.enableDamping=true;orbit.minDistance=4;orbit.maxDistance=160;orbit.maxPolarAngle=Math.PI*.495;
const pmrem=new T.PMREMGenerator(renderer),env=new RoomEnvironment();scene.environment=pmrem.fromScene(env,.04).texture;env.dispose();pmrem.dispose();scene.environmentIntensity=.6;
const hemi=new T.HemisphereLight('#e1edff','#6a614e',1.8);scene.add(hemi);
const sun=new T.DirectionalLight('#fff0d3',3);sun.position.set(-40,65,40);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);
Object.assign(sun.shadow.camera,{left:-37,right:37,bottom:-28,top:35,near:1,far:150});sun.shadow.normalBias=.035;sun.shadow.bias=-.0001;scene.add(sun);
const lights=[];for(const [x,y,z,p] of [[0,8,1,160],[-14,3,1,120],[14,3,1,120],[-14,7,1,100],[14,7,1,100],[0,17,-2,100]]){const light=new T.PointLight('#ffe3b5',p,22,2);light.position.set(x,y,z);scene.add(light);lights.push(light);}

let mode='orbit',night=false,model=null,nav=null,feet={x:0,y:.045,z:17},yaw=0,pitch=0,door=0,last=0,frames=0,totalFrameTime=0;
const keys=new Set(),eye=1.65,coarse=matchMedia('(pointer: coarse)').matches;
const places={entrance:{p:[0,.045,16],yaw:0},lobby:{p:[0,.82,5.3],yaw:0},office:{p:[-14.4,.85,6],yaw:0},lounge:{p:[14.4,.85,6],yaw:0},stairs:{p:[-6.8,.82,5],yaw:0},mezzanine:{p:[0,5.235,-6],yaw:Math.PI},meeting:{p:[-14.4,5.15,6],yaw:0},third:{p:[14.4,9.45,6],yaw:0}};
function resize(){renderer.setSize(innerWidth,innerHeight,false);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();}addEventListener('resize',resize);resize();
function syncLook(){camera.rotation.order='YXZ';camera.rotation.set(pitch,yaw,0);}
function setMode(value){mode=value;keys.clear();orbit.enabled=value==='orbit';$('#orbit').setAttribute('aria-pressed',String(mode==='orbit'));$('#walk').setAttribute('aria-pressed',String(mode==='walk'));$('#crosshair').hidden=mode!=='walk';$('#touch').hidden=mode!=='walk';
 if(mode==='orbit'){document.exitPointerLock?.();camera.position.set(33,28,74);orbit.target.set(0,8,0);orbit.update();$('#hint').textContent='드래그: 회전 · 휠: 확대 / 축소';}
 else{camera.position.set(feet.x,feet.y+eye,feet.z);syncLook();$('#hint').textContent=coarse?'방향 버튼: 걷기 · 화면 드래그: 시점':'WASD / 방향키: 걷기 · 드래그: 시점 · 화면 클릭: 마우스 고정 · Esc: 해제';canvas.focus();}
}
function place(id){if(!places[id]||!nav)return;const v=places[id];feet={x:v.p[0],y:v.p[1],z:v.p[2]};yaw=v.yaw;pitch=0;setMode('walk');}
$('#orbit').onclick=()=>setMode('orbit');$('#walk').onclick=()=>{if(nav)setMode('walk');};$('#place').onchange=e=>place(e.target.value);
$('#night').onclick=()=>{night=!night;$('#night').setAttribute('aria-pressed',String(night));$('#night').textContent=night?'주간':'야간';scene.background.set(night?'#15263f':'#bacbd5');scene.fog.color.copy(scene.background);hemi.intensity=night?.55:1.8;sun.intensity=night?.22:3;sun.color.set(night?'#91b4f0':'#fff0d3');scene.environmentIntensity=night?.3:.6;lights.forEach(l=>l.intensity*=night?1.7:1/1.7);};
const aliases={ArrowUp:'KeyW',ArrowDown:'KeyS',ArrowLeft:'KeyA',ArrowRight:'KeyD'};
addEventListener('keydown',e=>{if(mode!=='walk'||!nav||e.target.tagName==='SELECT')return;const code=aliases[e.code]||e.code;if(['KeyW','KeyA','KeyS','KeyD','ShiftLeft','ShiftRight'].includes(code)){keys.add(code);e.preventDefault();}});
addEventListener('keyup',e=>keys.delete(aliases[e.code]||e.code));addEventListener('blur',()=>keys.clear());document.addEventListener('visibilitychange',()=>keys.clear());
let dragging=false,dragged=false,previous={x:0,y:0};
canvas.addEventListener('pointerdown',e=>{if(mode==='walk'&&!document.pointerLockElement){dragging=true;dragged=false;previous={x:e.clientX,y:e.clientY};canvas.setPointerCapture(e.pointerId);}});
canvas.addEventListener('pointermove',e=>{if(mode!=='walk'||document.pointerLockElement||!dragging)return;const dx=e.clientX-previous.x,dy=e.clientY-previous.y;if(Math.abs(dx)+Math.abs(dy)>2)dragged=true;yaw-=dx*.003;pitch=T.MathUtils.clamp(pitch-dy*.003,-1.35,1.35);previous={x:e.clientX,y:e.clientY};syncLook();});
canvas.addEventListener('pointerup',()=>{dragging=false;if(mode==='walk'&&!dragged&&!coarse){const request=canvas.requestPointerLock?.();request?.catch?.(()=>{});}});
canvas.addEventListener('pointercancel',()=>{dragging=false;});
document.addEventListener('mousemove',e=>{if(mode==='walk'&&document.pointerLockElement===canvas){yaw-=e.movementX*.002;pitch=T.MathUtils.clamp(pitch-e.movementY*.002,-1.35,1.35);syncLook();}});
document.addEventListener('pointerlockchange',()=>keys.clear());
for(const button of document.querySelectorAll('[data-key]')){button.addEventListener('pointerdown',e=>{keys.add(button.dataset.key);button.setPointerCapture(e.pointerId);e.preventDefault();});for(const event of ['pointerup','pointercancel','lostpointercapture'])button.addEventListener(event,()=>keys.delete(button.dataset.key));}

setMode('orbit');
async function load(){
 const response=await fetch('./navigation.json');if(!response.ok)throw new Error('Navigation load failed');const data=await response.json();
 const gltf=await new GLTFLoader().loadAsync('./hq-v3.glb',e=>{if(e.total)$('#loading').firstChild.textContent=`본사 3D 모델 불러오는 중… ${Math.round(e.loaded/e.total*100)}%`;});
 model=prepareModel(gltf.scene);scene.add(gltf.scene,model.merged);nav=data;$('#loading').hidden=true;document.body.dataset.ready='true';
}
load().catch(e=>{console.error(e);$('#loading').textContent='본사 모델을 불러오지 못했습니다. 새로고침해 주세요.';document.body.dataset.error='true';});
renderer.setAnimationLoop(time=>{
 const dt=Math.min((time-last)/1000||0,.05);last=time;
 if(nav&&model){
  const near=mode==='walk'&&Math.hypot(feet.x,feet.z-7.42)<4&&feet.y<1.5;
  door=T.MathUtils.damp(door,near?1:0,7,dt);for(const d of model.doors)d.object.position.x=d.base+d.side*door*2.5;
  if(mode==='walk'){
   let f=Number(keys.has('KeyW'))-Number(keys.has('KeyS')),r=Number(keys.has('KeyD'))-Number(keys.has('KeyA'));const n=Math.hypot(f,r)||1;f/=n;r/=n;
   const speed=keys.has('ShiftLeft')||keys.has('ShiftRight')?4.8:2.7;
   feet=movePlayer(feet,(r*Math.cos(yaw)-f*Math.sin(yaw))*speed*dt,(-f*Math.cos(yaw)-r*Math.sin(yaw))*speed*dt,nav,door>.75);
   camera.position.set(feet.x,feet.y+eye,feet.z);syncLook();
  }else orbit.update();
 }
 renderer.render(scene,camera);frames++;totalFrameTime+=dt;
 if(frames%30===0)$('#status').textContent=nav?`${mode==='walk'?'보행':'회전'} · ${night?'야간':'주간'} · ${Math.round(feet.y*10)/10}m 층 높이`:'모델 준비 중';
});
window.hqWalkDiagnostics=()=>({ready:!!nav,mode,night,feet:{...feet},camera:camera.position.toArray(),doorOpen:door,meshes:model?.sourceMeshes||0,drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles,averageFrameMs:frames?totalFrameTime/frames*1000:0});
