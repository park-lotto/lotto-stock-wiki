import * as T from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

function grain(name){
 const canvas=document.createElement('canvas');canvas.width=canvas.height=256;
 const ctx=canvas.getContext('2d'),data=ctx.createImageData(256,256);let seed=193;
 for(let y=0;y<256;y++)for(let x=0;x<256;x++){
  seed=(Math.imul(seed,1664525)+1013904223)>>>0;
  const noise=seed/4294967296;
  const band=name.includes('Walnut')?Math.sin(y*.38+Math.sin(x*.055)*1.3)*22:name.includes('Stone')||name.includes('Marble')?Math.sin(y*.17+Math.sin(x*.043)) *9:0;
  const value=218+band+(noise-.5)*(name.includes('Fabric')||name.includes('Carpet')?42:13),i=(y*256+x)*4;
  data.data[i]=data.data[i+1]=data.data[i+2]=value;data.data[i+3]=255;
 }
 ctx.putImageData(data,0,0);const texture=new T.CanvasTexture(canvas);texture.wrapS=texture.wrapT=T.RepeatWrapping;texture.colorSpace=T.SRGBColorSpace;return texture;
}
export function prepareModel(root){
 root.updateMatrixWorld(true);const groups=new Map(),doors=[],materials=new Set();let sourceMeshes=0;
 root.traverse(o=>{if(o.userData.doorSide){doors.push({object:o,side:o.userData.doorSide,base:o.position.x});}});
 const dynamic=o=>{for(let p=o;p;p=p.parent)if(p.userData.doorSide)return true;return false;};
 root.traverse(o=>{
  if(!o.isMesh)return;sourceMeshes++;
  for(const m of Array.isArray(o.material)?o.material:[o.material])materials.add(m);
  if(dynamic(o))return;
  const geometry=o.geometry.index?o.geometry.toNonIndexed():o.geometry.clone();geometry.applyMatrix4(o.matrixWorld);
  if(!geometry.attributes.normal)geometry.computeVertexNormals();
  const pos=geometry.attributes.position,norm=geometry.attributes.normal,uv=new Float32Array(pos.count*2);
  for(let i=0;i<pos.count;i++){
   const nx=Math.abs(norm.getX(i)),ny=Math.abs(norm.getY(i)),nz=Math.abs(norm.getZ(i));
   uv[i*2]=(nx>ny&&nx>nz?pos.getZ(i):pos.getX(i))*.35;
   uv[i*2+1]=(ny>nx&&ny>nz?pos.getZ(i):pos.getY(i))*.35;
  }
  geometry.setAttribute('uv',new T.BufferAttribute(uv,2));
  for(const attr of Object.keys(geometry.attributes))if(!['position','normal','uv'].includes(attr))geometry.deleteAttribute(attr);
  const key=o.material.uuid;if(!groups.has(key))groups.set(key,{material:o.material,geometries:[]});groups.get(key).geometries.push(geometry);o.visible=false;
 });
 for(const m of materials){
  if(m.name.includes('Glass')){m.transmission=0;m.transparent=true;m.opacity=.17;m.depthWrite=false;m.roughness=.08;m.metalness=.12;m.side=T.DoubleSide;}
  if(/HD_(Stone|Walnut|Fabric|TealFabric|Carpet|HonedMarble)/.test(m.name)){m.map=grain(m.name);m.bumpMap=m.map;m.bumpScale=.012;}
  m.envMapIntensity=.65;
 }
 const merged=new T.Group();merged.name='HQ_StaticGeometry';
 for(const {material,geometries} of groups.values()){
  const geometry=mergeGeometries(geometries,false);if(!geometry)throw new Error('Static geometry merge failed');
  const mesh=new T.Mesh(geometry,material);mesh.castShadow=!material.transparent;mesh.receiveShadow=true;merged.add(mesh);
  geometries.forEach(g=>g.dispose());
 }
 return {merged,doors,sourceMeshes,materials};
}
