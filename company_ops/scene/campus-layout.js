export const waterRings=[[18,23],[40,44],[61,65]];
export const buildings=[];
for(const [program,sign]of [['shortem',-1],['stock',1]])for(const [row,radius]of [[0,33.5],[1,54]])for(let i=0;i<5;i++){
 const angle=sign*(.67+i*.45);
 buildings.push({id:`${program}-${row*5+i+1}`,program,angle,radius,depth:row?9:8,span:row?.31:.35,floors:2+(i+row)%2});
}
