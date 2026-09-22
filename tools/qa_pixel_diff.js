// 두 폴더의 같은 이름 PNG를 픽셀 단위로 비교한다 — "같게 나온다"를 눈이 아니라 숫자로 말하기 위한 도구.
//   실행: node tools/qa_pixel_diff.js <기준폴더> <새폴더> [차이그림폴더]
//   판정: 채널값 차이가 THRESH(기본 12)를 넘는 픽셀 수. 0이면 같다. 차이그림 = 다른 픽셀을 빨강으로 칠한 새 화면.
//   PNG 라이브러리 없이 브라우저 캔버스로 읽는다(추가 설치 없음).
const puppeteer=require('puppeteer'),fs=require('fs'),path=require('path');
const [A,B,D]=process.argv.slice(2);const THRESH=Number(process.env.THRESH||12);
if(!A||!B){console.error('폴더 두 개를 주세요');process.exit(1);}
if(D)fs.mkdirSync(D,{recursive:true});
(async()=>{
  const browser=await puppeteer.launch({headless:true});const page=await browser.newPage();
  const files=fs.readdirSync(A).filter(f=>f.endsWith('.png')&&fs.existsSync(path.join(B,f))).sort();
  const rows=[];
  for(const f of files){
    const a=fs.readFileSync(path.join(A,f)).toString('base64'),b=fs.readFileSync(path.join(B,f)).toString('base64');
    const r=await page.evaluate(async(a,b,T,wantImage)=>{
      const load=async s=>{const i=new Image();i.src='data:image/png;base64,'+s;await i.decode();return i};
      const ia=await load(a),ib=await load(b);
      if(ia.width!==ib.width||ia.height!==ib.height)return {크기다름:ia.width+'x'+ia.height+' vs '+ib.width+'x'+ib.height};
      const c=document.createElement('canvas');c.width=ia.width;c.height=ia.height;const x=c.getContext('2d',{willReadFrequently:true});
      x.drawImage(ia,0,0);const da=x.getImageData(0,0,c.width,c.height).data;x.drawImage(ib,0,0);const img=x.getImageData(0,0,c.width,c.height),db=img.data;
      let n=0,minY=1e9,maxY=-1,minX=1e9,maxX=-1;
      for(let i=0;i<da.length;i+=4){if(Math.abs(da[i]-db[i])>T||Math.abs(da[i+1]-db[i+1])>T||Math.abs(da[i+2]-db[i+2])>T){n++;const p=i/4,y=Math.floor(p/c.width),xx=p%c.width;
        if(y<minY)minY=y;if(y>maxY)maxY=y;if(xx<minX)minX=xx;if(xx>maxX)maxX=xx;db[i]=255;db[i+1]=0;db[i+2]=0;}}
      let image=null;if(n&&wantImage){x.putImageData(img,0,0);image=c.toDataURL('image/png').split(',')[1];}
      return {다른픽셀:n,전체:c.width*c.height,범위:n?{세로:Math.round(minY/c.height*1000)/10+'~'+Math.round(maxY/c.height*1000)/10+'%',가로:Math.round(minX/c.width*1000)/10+'~'+Math.round(maxX/c.width*1000)/10+'%'}:null,image};
    },a,b,THRESH,!!D);
    if(r.image){fs.writeFileSync(path.join(D,f),Buffer.from(r.image,'base64'));}
    delete r.image;rows.push({파일:f,...r});
  }
  const bad=rows.filter(r=>r.다른픽셀||r.크기다름);
  console.log(JSON.stringify({비교한칸:rows.length,같은칸:rows.length-bad.length,다른칸:bad.length,다른칸목록:bad},null,1));
  await browser.close();process.exit(bad.length?1:0);
})().catch(e=>{console.error(String(e).slice(0,300));process.exit(1)});
