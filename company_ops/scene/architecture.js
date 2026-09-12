import * as T from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

// This is a proposed physical layout, not a second business catalog.
export const FLOOR_IDS = ['ops', 'cs', 'qa', 'improve', 'new'];
const accents = ['#83c8c2', '#d69a71', '#b8a1df', '#7ecfb2', '#9fbce0'];
const geometries = new Map(), materials = new Map();
function material(color, metalness = 0, roughness = .7) {
  const key = `${color}:${metalness}:${roughness}`;
  if (!materials.has(key)) materials.set(key, new T.MeshStandardMaterial({color, metalness, roughness}));
  return materials.get(key);
}
function geometry(w,h,d,r) {
  const key = [w,h,d,r].join(':');
  if (!geometries.has(key)) geometries.set(key,r ? new RoundedBoxGeometry(w,h,d,2,r) : new T.BoxGeometry(w,h,d));
  return geometries.get(key);
}
function box(parent,w,h,d,x,y,z,color,r=0) {
  const mesh = new T.Mesh(geometry(w,h,d,r), typeof color==='string'? material(color):color);
  mesh.position.set(x,y,z); mesh.castShadow=true; mesh.receiveShadow=true; parent.add(mesh);return mesh;
}
function cylinder(parent,rt,rb,h,x,y,z,color) {
  const key=[rt,rb,h,'c'].join(':');
  if(!geometries.has(key))geometries.set(key,new T.CylinderGeometry(rt,rb,h,12));
  const mesh=new T.Mesh(geometries.get(key),material(color));mesh.position.set(x,y,z);mesh.castShadow=true;parent.add(mesh);return mesh;
}
function plant(parent,x,y,z,scale=1) {
  const g=new T.Group();g.position.set(x,y,z);g.scale.setScalar(scale);parent.add(g);
  cylinder(g,.23,.17,.43,0,.215,0,'#b1a28b');
  for(let i=0;i<5;i++){
    const a=i*2.4;
    const leaf=new T.Mesh(new T.SphereGeometry(.16,8,6),material(i%2?'#466652':'#769075'));
    leaf.position.set(Math.cos(a)*.17,.64+(i%3)*.12,Math.sin(a)*.17);
    leaf.scale.set(.65,2.1,.7);leaf.rotation.z=Math.cos(a)*.45;leaf.castShadow=true;g.add(leaf);
  }
}
function label(parent,text,w,h,x,y,z,{bg='#243333',fg='#f1e8d5',size=48}={}) {
  const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=Math.round(1024*h/w);
  const c=canvas.getContext('2d');c.fillStyle=bg;c.fillRect(0,0,canvas.width,canvas.height);
  c.fillStyle=fg;c.font=`700 ${size}px LINESeed, sans-serif`;c.textAlign='center';c.textBaseline='middle';c.fillText(text,512,canvas.height/2,960);
  const texture=new T.CanvasTexture(canvas);texture.colorSpace=T.SRGBColorSpace;
  const mesh=new T.Mesh(new T.PlaneGeometry(w,h),new T.MeshBasicMaterial({map:texture}));mesh.position.set(x,y,z);parent.add(mesh);return mesh;
}
function monitor(parent,x,y,z,accent) {
  box(parent,.76,.48,.09,x,y,z,'#303c3c',.035);
  const screen=new T.MeshBasicMaterial({color:'#162c32'});
  box(parent,.65,.37,.01,x,y,z+.051,screen,.01);
  for(let j=0;j<4;j++)box(parent,.26+(j%3)*.12,.015,.006,x-.09,y+.105-j*.067,z+.059,material(accent));
  box(parent,.05,.2,.05,x,y-.29,z,'#3b4545');box(parent,.34,.035,.24,x,y-.38,z+.03,'#414b4b',.012);
}
function robot(parent,x,z,accent,role,index) {
  const g=new T.Group();g.position.set(x,0,z);parent.add(g);
  // Rounded shell, compact feet, visor and side sensors: no humanoid clothing.
  box(g,.5,.52,.43,0,.52,0,accent,.13);
  box(g,.67,.51,.49,0,1.06,0,'#eeeadd',.17);
  box(g,.54,.31,.065,0,1.04,.225,'#12282c',.1);
  const eye=new T.MeshBasicMaterial({color:'#b4ffdf'});
  box(g,.063,.103,.024,-.14,1.06,.268,eye,.025);
  box(g,.063,.103,.024,.14,1.06,.268,eye,.025);
  box(g,.105,.022,.019,0,.955,.267,eye,.007);
  box(g,.16,.24,.2,-.35,.57,.015,'#e4e0d4',.075);box(g,.16,.24,.2,.35,.57,.015,'#e4e0d4',.075);
  box(g,.22,.17,.31,-.15,.18,.04,'#394b4b',.07);box(g,.22,.17,.31,.15,.18,.04,'#394b4b',.07);
  cylinder(g,.022,.022,.15,0,1.385,0,'#516263');
  const antenna=new T.Mesh(new T.SphereGeometry(.05,8,6),eye);antenna.position.set(0,1.48,0);g.add(antenna);
  box(g,.17,.09,.035,0,.57,.233,'#edeadf',.018);
  const hit=new T.Mesh(new T.BoxGeometry(.95,1.7,.85),new T.MeshBasicMaterial({visible:false}));hit.position.y=.82;g.add(hit);
  const ring=new T.Mesh(new T.RingGeometry(.5,.54,40),new T.MeshBasicMaterial({color:accent,side:T.DoubleSide}));ring.rotation.x=-Math.PI/2;ring.position.y=.08;ring.visible=false;g.add(ring);
  return {group:g,hit,ring,role,index,point:new T.Vector3()};
}
function desk(parent,x,z,accent) {
  box(parent,1.7,.12,.83,x,.84,z,'#baa386',.05);
  for(const dx of [-.65,.65])box(parent,.055,.8,.6,x+dx,.4,z,'#3a4846');
  monitor(parent,x,.84+.43,z-.1,accent);
  box(parent,.55,.025,.19,x, .925,z+.25,'#d9d5c8',.015);
  cylinder(parent,.08,.07,.15,x+.61,.98,z+.16,'#ebdfc9');
  box(parent,.59,.1,.49,x,.46,z+1.25,'#506461',.08);
  box(parent,.6,.57,.1,x,.8,z+1.47,'#506461',.08);
  cylinder(parent,.045,.045,.4,x,.22,z+1.25,'#586765');
}

export function buildHeadquarters(scene,teams,company) {
  const root=new T.Group();scene.add(root);const floors=[],workers=[],picks=[];
  const stone=material('#d2c7b2',.05,.85), dark=material('#344442',.25,.4);
  const glass=new T.MeshStandardMaterial({color:'#9bc9c5',transparent:true,opacity:.18,roughness:.1,metalness:.1,depthWrite:false});
  const glow=new T.MeshBasicMaterial({color:'#ffe1a9'});
  box(root,17.6,.44,10.4,0,-.27,0,stone,.12);
  for(let j=0;j<3;j++)box(root,12+j*.65,.14,1.25+j*.5,0,-.43-j*.14,5.05+j*.35,stone,.03);
  box(root,19,.18,12.4,0,-.85,.4,material('#657672'),.1);
  box(root,22,.15,15.4,0,-1.02,.4,material('#74847b'),.14);
  for(const x of [-8,8])for(const z of [-3.5,3.7])plant(root,x,0,z,1.65);
  for(let i=0;i<5;i++) {
    const team=teams.find(t=>t.id===FLOOR_IDS[i]);if(!team)continue;
    const y=i*2.65,g=new T.Group();g.position.y=y;root.add(g);
    box(g,15.4,.24,8,0,0,0,stone,.035);
    box(g,15,.05,7.6,0,.145,0,material(i%2?'#b4a58d':'#c5b8a0'));
    box(g,15.4,2.4,.2,0,1.31,-3.86,stone);
    box(g,.22,2.4,8,-7.6,1.31,0,stone);
    box(g,.12,2.4,7.6,7.6,1.31,0,glass);
    // Back windows and timber fluting.
    for(let j=0;j<6;j++){
      box(g,1.65,1.47,.03,-5.6+j*2.15,1.49,-3.74,material('#526b6a',.25,.32),.018);
      box(g,.035,1.47,.05,-5.6+j*2.15,1.49,-3.7,'#a49f8f');
    }
    for(const x of [-7.4,0,7.4]){box(g,.16,2.48,.16,x,1.34,3.68,dark);box(g,.16,2.48,.16,x,1.34,-3.6,dark);}
    box(g,15.4,.16,.24,0,2.45,3.72,dark);
    box(g,14.8,.025,.07,0,2.34,3.63,glow);
    box(g,14.8,.025,.07,0,2.34,-3.58,glow);
    for(const x of [-5,0,5]){box(g,2.2,.03,.65,x,2.36,-.5,glow,.015);}
    const interiorLight=new T.PointLight('#ffce82',14,10,2);interiorLight.position.set(0,2,-.5);g.add(interiorLight);
    for(let j=0;j<13;j++)box(g,.075,1.85,.06,6.08+j*.07,1.24,-3.68,'#987a55');
    const color=accents[i];
    const plaque=label(g,`${i+1}F   ${team.name}`,3.7,.58,-5.2,.36,4.04,{bg:'#314743',fg:'#f8ebd1',size:70});
    plaque.userData={kind:'team',teamId:team.id};picks.push(plaque);
    box(g,3.86,.68,.09,-5.2,.36,3.98,dark,.02);
    box(g,.14,.5,.025,-7,.36,4.05,material(color));
    label(g,'SHORTEM MAKER',3.7,.4,4.75,1.92,-3.72,{bg:'#526b6a',size:52});
    for(let j=0;j<3;j++) {
      const x=-4.8+j*4.45;
      for(let k=0;k<2;k++) {
        const z=-2.1+k*2.8;
        desk(g,x,z,color);
        const role=['planner','executor','reviewer'][j];
        const worker=robot(g,x+.98,z+.45,j===1?'#72a99b':'#d59871',team.workflow[role],j*2+k);
        worker.teamId=team.id;worker.floor=i;worker.title=k===0?{planner:'팀장석',executor:'실행석',reviewer:'검수석'}[role]:'확장 좌석';
        worker.assignedSeat=k===0;worker.hit.userData={kind:'worker',worker};
        worker.group.rotation.y=-.16;workers.push(worker);picks.push(worker.hit);
      }
    }
    plant(g,-6.6,.17,-2.8);plant(g,6.5,.17,2.9);plant(g,6.5,.17,-2.8);
    // Perimeter glass with thin brass rail, open central entrance.
    for(const x of [-5.1,5.1]){box(g,4.65,.65,.05,x,.52,3.78,glass);box(g,4.65,.03,.06,x,.87,3.78,dark);}
    const plane=new T.Mesh(new T.PlaneGeometry(15,2.5),new T.MeshBasicMaterial({visible:false}));plane.position.set(0,1.3,3.6);plane.userData={kind:'team',teamId:team.id};g.add(plane);
    floors.push({group:g,team,index:i,y,color,plane});
  }
  const roof=new T.Group();roof.position.y=13.25;root.add(roof);
  box(roof,15.9,.26,8.6,0,0,0,stone,.045);
  box(roof,8.3,1.2,.32,1.8,.62,-.2,dark,.035);
  label(roof,company.name,7.5,.85,1.8,.66,-.02,{size:96});
  label(roof,'AI COMPANY / WORK IN MOTION',5.9,.23,1.8,.09,-.01,{size:31});
  for(let j=0;j<4;j++)plant(roof,-6.5+j*1.3,.15,-2.6,1.3);
  // Roof terrace, pergola and low seating.
  for(let j=0;j<9;j++)box(roof,.1,.13,3.1,-6.5+j*.43,1.9,.4,'#a89579');
  for(const x of [-6.5,-3])for(const z of [-1.1,1.9])box(roof,.08,1.8,.08,x,.95,z,dark);
  box(roof,2.6,.42,.72,-4.75,.39,.45,'#7d9184',.12);
  box(roof,2.6,.36,.2,-4.75,.7,.1,'#7d9184',.08);
  // A quiet plaza with landscaped islands frames the miniature.
  for(const x of [-10.2,10.2])for(const z of [-4,3]){box(root,1.55,.16,2.5,x,-.93,z,'#485f51',.3);plant(root,x,-.85,z,2.15);}
  scene.updateMatrixWorld(true);workers.forEach(w=>w.group.getWorldPosition(w.point));
  return {root,floors,workers,picks,roof};
}
