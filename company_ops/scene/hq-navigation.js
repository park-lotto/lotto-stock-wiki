// Feet coordinates in glTF Y-up space. No rendering dependencies.
export function floorAt(x,z,feet,floors){
  let height=null;
  for(const f of floors){
    if(x>=f.min[0]-.12&&x<=f.max[0]+.12&&z>=f.min[2]-.12&&z<=f.max[2]+.12&&f.max[1]<=feet+.36){
      if(height===null||f.max[1]>height)height=f.max[1];
    }
  }
  return height;
}
function blocked(x,z,y,solids,doorOpen){
  const radius=.27;
  return solids.some(b=>{
    if(b.door&&doorOpen)return false;
    if(b.max[1]<=y+.08||b.min[1]>=y+1.72)return false;
    const nx=Math.max(b.min[0],Math.min(x,b.max[0])),nz=Math.max(b.min[2],Math.min(z,b.max[2]));
    return (x-nx)**2+(z-nz)**2<radius**2;
  });
}
export function movePlayer(position,dx,dz,data,doorOpen=false){
  const p={...position},steps=Math.max(1,Math.ceil(Math.hypot(dx,dz)/.07));
  for(let i=0;i<steps;i++){
    for(const [axis,delta] of [['x',dx/steps],['z',dz/steps]]){
      if(!delta)continue;
      const x=p.x+(axis==='x'?delta:0),z=p.z+(axis==='z'?delta:0);
      const y=floorAt(x,z,p.y,data.floors);
      if(y===null||p.y-y>.48||blocked(x,z,y,data.solids,doorOpen))continue;
      p.x=x;p.z=z;p.y=y;
    }
  }
  return p;
}
