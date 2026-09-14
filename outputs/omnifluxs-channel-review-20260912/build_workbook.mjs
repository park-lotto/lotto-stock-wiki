import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const outputDir = path.dirname(fileURLToPath(import.meta.url));
const workbook = Workbook.create();
const main = workbook.worksheets.add('구매 후보');
const checks = workbook.worksheets.add('구매 전 확인');

const rows = [
  [1,'$100~$200','검증우선','Serkan SEKOMY',120,137000,78300000,233,1950,'공개 표본 강함: 6.24M, 2.21M, 600K 등','예','OFF','판매자 문의 전송·답변 대기','AdSense 변경 OFF, 재사용/IP 및 월수익 진위 확인','https://omnifluxs.com/channel/f19d1240-1dd8-4b57-a1ac-0eec87477d26','https://www.youtube.com/@Serkan%C3%87elemo%C4%9Fluu','2026-09-12 상세 질문 전송'],
  [2,'$100~$200','추가확인','Zach_rhymaxxx',137,34000,14700000,37,0,'공개 표본: 400K, 76K, 67K, 38K 등','1차 수익화','미확인','쇼츠 테스트 조건 문의·답변 대기','1차 수익화. 72시간 200회 테스트와 취소 합의 필요','https://omnifluxs.com/channel/08676fb6-51e4-4069-9a29-acc4ce0c49d6','https://youtube.com/@zach_rhymaxxx','2026-09-12 테스트 조건 문의'],
  [3,'$100~$200','추가확인','ATULxRBLX',147,11000,13900000,254,73.68,'공개 표본: 820K, 150K, 79K, 43K 등','1차 수익화','미확인','쇼츠 테스트 조건 문의·답변 대기','1차 수익화. 실제 화면 증빙과 200회 테스트 합의 필요','https://omnifluxs.com/channel/90841c40-cfbe-4f6f-a40a-4a4953ae6df9','https://youtube.com/@atulxrblx','2026-09-12 테스트 조건 문의'],
  [4,'$100 미만','검증우선','fart.pranks09',76,21000,23700000,148,0,'공개 표본: 330K, 180K, 3.4K 등','예','ON','판매자 문의 전송·답변 대기','재사용 프랭크 콘텐츠 위험, 최근 성과 편차','https://omnifluxs.com/channel/6baf2fa7-8268-4377-871b-594fca5e0e4f','https://youtube.com/@fart.pranks09','2026-09-12 상세 질문 전송'],
  [5,'$100~$200','검증우선','Kashmiri Youtuber',158,11000,7500000,429,31.58,'공개 표본: 460K, 120K, 110K, 85K 등','예','미확인','판매자 문의 전송·답변 대기','언어·지역 시청자 전환 위험, 제재 이력 확인','https://omnifluxs.com/channel/1cf2751d-2f01-4227-910e-a203744b3b84','https://youtube.com/@kashmiriyoutuberex','2026-09-12 상세 질문 전송'],
  [6,'$100~$200','추가확인','VoxelSpire',157,8300,13500000,487,0,'공개 최근 표본 약함: 310, 7K','예','미확인','미문의','최근 조회수 약함, 수익 0','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [7,'$100~$200','추가확인','The Magical Earth',156,3500,989000,295,20,'공개 표본: 44K, 27K, 16K, 12K 등','예','미확인','미문의','규모 작음, 최근 성과 편차','https://omnifluxs.com/channel/4ac4adb4-aafb-49e4-b55b-871c23e9a791','https://youtube.com/@themagicalearth8152','미문의'],
  [8,'$100 미만','추가확인','Kishan vlog',79.37,49000,1300000,153,0,'공개 최근 표본: 14K, 6.4K, 1.2K, 다수 두 자릿수','예','ON','미문의','구독자 대비 최근 조회수 매우 약함','https://omnifluxs.com/channel/a3023b64-0a55-43bd-8909-ada83680adae','https://youtube.com/@kishanvlog652kviews','미문의'],
  [9,'$100~$200','추가확인','Score ticker',158,5300,653000,466,0,'공개 실사 미완료','예','미확인','미문의','영상 수 대비 누적조회수 낮음','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [10,'$100~$200','추가확인','Shades of Chenab',158,1600,675000,268,0,'공개 실사 미완료','예','미확인','미문의','규모 작고 수익 0','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [11,'$100~$200','추가확인','Rajugamer3d',130,3300,668000,94,0,'공개 표본: 10K, 5.4K, 4.6K, 1.3K 등','예','미확인','미문의','최근 성과 약함, 영상수 표기 불일치','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [12,'$100~$200','추가확인','Raw & Real',150,1300,467000,79,2.60,'공개 실사 미완료','예','미확인','미문의','규모·수익 작음','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [13,'$100~$200','추가확인','ANKIT',150,1600,900000,58,0.73,'공개 표본: 1.2K, 456, 261 등','예','미확인','미문의','최근 성과 약함','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [14,'$100~$200','추가확인','Monir Husen',110,1500,315000,9,0,'공개 실사 미완료','예','미확인','미문의','영상 수 적음, 수익 0','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [15,'$100~$200','추가확인','Earn with gopal',168,2400,87000,41,0,'공개 실사 미완료','예','미확인','미문의','누적조회수·수익 낮음','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [16,'$100~$200','추가확인','Aman ckt vlogs',158,11000,67000,23,0,'공개 실사 미완료','예','미확인','미문의','구독자 대비 누적조회수 불균형','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [17,'$100~$200','추가확인','AK_ANXARI_845',120,1000,68000,47,0,'공개 실사 미완료','예','미확인','미문의','규모 작고 수익 0','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [18,'$100~$200','제외','Notun Khobor 2.0',140,1100,490000,122,1900,'공개 표본: 13K, 7.4K, 6.7K 등','예','미확인','미문의','규모 대비 월수익 $1,900 비정상','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [19,'$100~$200','제외','Abhay Kushwaha',119,78000,34400000,189,10,'YouTube 링크 404','예','미확인','미문의','공개 채널 확인 불가','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [20,'$100~$200','제외','ScreenBlast',149,2800,3700000,177,0,'YouTube 링크가 OmniFluxs로 연결','예','미확인','미문의','대상 채널 검증 불가','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [21,'$100~$200','제외','Deej Vishnu',130,5200,3300000,41,3325,'YouTube 링크 오류','예','미확인','미문의','링크 오류 및 월수익 비정상','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [22,'$100~$200','제외','Auto Recenzje',120,1000,214000,126,1805000,'공개 실사 미완료','예','미확인','미문의','월수익 $1,805,000 표기 오류 의심','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [23,'$100~$200','제외','DIVYANSHU YADAV',126,1800,107000,1,211,'공개 실사 미완료','예','미확인','미문의','영상 1개·월수익 $211 불균형','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [24,'$100~$200','제외','FAIMG YT',165,691,106000,59,180,'공개 실사 미완료','예','미확인','미문의','구독자 691명인데 수익화 표시·수익 비정상','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [25,'$100~$200','제외','newviral',105,1000,3000,133,211,'공개 실사 미완료','예','미확인','미문의','누적 3천 조회에 월수익 $211 비정상','https://omnifluxs.com/buy-youtube-channel','', '미문의'],
  [26,'$100 미만','제외','Abixx.555',42.11,14000,0,0,10.53,'판매글: old videos removed, unmonetized clean slate','예','미확인','미문의','수익화 배지와 판매자 설명 정면 충돌','https://omnifluxs.com/channel/62beecc5-fd22-4e8d-a290-dd5f5c4d19a9','', '미문의'],
  [27,'$100 미만','제외','Tilawat',19,5300,1300000,26,0,'Studio 증빙: 유효 시청시간 0, Shorts 18K, Get notified','예','OFF','미문의','수익화 조건 미달 증빙 확인','https://omnifluxs.com/channel/d39d1aaa-e2e6-466e-8dc1-be19571be70e','', '미문의'],
  [28,'$100 미만','제외','Khairul786',52.63,116,101000,141,526,'공개 실사 미완료','예','미확인','미문의','구독자 116명·월수익 $526 비정상','https://omnifluxs.com/channel/50cbc066-b140-4ec3-bc26-71dd545e7406','', '미문의'],
  [29,'$100 미만','제외','GreenHandXD',11,129,226000,86,0,'판매자 설명: could monetize','예','미확인','미문의','수익화 배지와 설명 충돌','https://omnifluxs.com/channel/8d79149f-64ac-4b67-b77a-0fd0a7bd1f10','', '미문의'],
  [30,'$100 미만','제외','Xezox',10.53,182,32000,35,3.16,'공개 실사 미완료','예','미확인','미문의','YPP 일반 기준과 불일치 가능성','https://omnifluxs.com/channel/1fb53434-956d-4c75-aef5-a6fbe16a1e5f','', '미문의'],
  [31,'$100 미만','제외','Tha God 90',1.05,9,1900,12,21.05,'공개 실사 미완료','예','미확인','미문의','구독자 9명·월수익 $21.05 비정상','https://omnifluxs.com/channel/43a52cdc-b951-402c-800f-57a69046ba8f','', '미문의'],
  [32,'$100 미만','제외','Mr Hasnain',1.05,9,6700,14,0,'공개 실사 미완료','예','미확인','미문의','YPP 일반 기준과 불일치','https://omnifluxs.com/channel/1b22a348-7a40-44ae-9d06-07e2a1e0e251','', '미문의'],
  [33,'$100 미만','제외','Daddy Dustin',4.75,11,754,4,0,'공개 실사 미완료','예','미확인','미문의','YPP 일반 기준과 불일치','https://omnifluxs.com/channel/5415d118-4ae5-4faa-add4-974446b3b323','', '미문의']
];

const headers=['우선순위','가격구간','판정','채널명','가격(USD)','구독자','누적조회수','영상수','영상당 평균조회수','사이트 월수익(USD)','공개 조회수 실사','수익화 표시','AdSense 변경','검증상태','주요 위험','매물 URL','YouTube URL','판매자 채팅상태'];
main.getRange('A1:R1').merge();
main.getRange('A1').values=[['OmniFluxs 유튜브 채널 구매 검토']];
main.getRange('A2:R2').merge();
main.getRange('A2').values=[['2026-09-12 기준. 가격 $200 미만, 사이트 수익화 필터 7페이지를 조사한 결과입니다. 사이트 표시는 판매자 답변과 YouTube Studio 실시간 증빙 전까지 확정 사실로 보지 않습니다.']];
main.getRange('A4:H4').values=[['검증우선',3,'추가확인',14,'제외',16,'판매자 문의',5]];
main.getRange('A6:R6').values=[headers];
main.getRange(`A7:R${6+rows.length}`).values=rows.map(r=>[...r.slice(0,8),null,...r.slice(8)]);
main.getRange(`I7`).formulas=[['=IF(H7>0,G7/H7,"")']];
main.getRange(`I7:I${6+rows.length}`).fillDown();

const font='Arial';
main.getRange(`A1:R${6+rows.length}`).format.font={name:font,size:10};
main.getRange('A1:R1').format={fill:'#172554',font:{name:font,size:18,bold:true,color:'#FFFFFF'},horizontalAlignment:'left',verticalAlignment:'center'};
main.getRange('A2:R2').format={fill:'#E0E7FF',font:{name:font,size:10,color:'#1E3A8A'},wrapText:true,verticalAlignment:'center'};
main.getRange('A4:H4').format={fill:'#F8FAFC',font:{name:font,size:11,bold:true,color:'#0F172A'},horizontalAlignment:'center'};
main.getRange('A6:R6').format={fill:'#1E3A8A',font:{name:font,size:10,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center'};
main.getRange(`A7:R${6+rows.length}`).format.verticalAlignment='top';
main.getRange(`K7:R${6+rows.length}`).format.wrapText=true;
main.getRange(`E7:E${6+rows.length}`).format.numberFormat='$0.00';
main.getRange(`F7:I${6+rows.length}`).format.numberFormat='#,##0';
main.getRange(`J7:J${6+rows.length}`).format.numberFormat='$#,##0.00';
for(let i=0;i<rows.length;i++){
  const row=7+i, status=rows[i][2];
  const fill=status==='검증우선'?'#DCFCE7':status==='추가확인'?'#FEF3C7':'#FEE2E2';
  main.getRange(`C${row}`).format={fill,font:{name:font,bold:true,color:'#0F172A'},horizontalAlignment:'center'};
}
main.getRange(`A6:R${6+rows.length}`).format.borders={top:{style:'continuous',color:'#CBD5E1'},bottom:{style:'continuous',color:'#CBD5E1'},left:{style:'continuous',color:'#E2E8F0'},right:{style:'continuous',color:'#E2E8F0'}};
const widths=[9,12,11,19,11,12,15,9,16,16,31,11,13,24,34,42,35,25];
widths.forEach((w,i)=>main.getRangeByIndexes(0,i,6+rows.length,1).format.columnWidth=w);
main.getRange('1:1').format.rowHeight=32;
main.getRange('2:2').format.rowHeight=38;
main.getRange('6:6').format.rowHeight=34;
main.freezePanes.freezeRows(6);
main.freezePanes.freezeColumns(4);
main.tables.add(`A6:R${6+rows.length}`,true,'ChannelReviewTable');

checks.getRange('A1:F1').merge();
checks.getRange('A1').values=[['구매 전 확인 및 에스크로 조건']];
checks.getRange('A3:B8').values=[
  ['핵심 결론','7일은 환불 보증기간이 아니라 YouTube 소유권 이전 대기기간입니다.'],
  ['환불 제한','채널 접근권 수령 후 수익화 해제·정지·저작권 경고·조회수·수익 하락은 환불 불가라고 명시되어 있습니다.'],
  ['보장 범위','판매자 또는 제3자가 계정을 회수한 경우에만 100% 환불 보증을 명시합니다.'],
  ['필수 조치','결제 전에 에스크로 담당자에게 수익화·제재·소유권·AdSense 검증 항목을 서면으로 알립니다.'],
  ['권장 방식','Safest Deal을 선택하고 에스크로 담당자가 검증을 마치기 전 판매자에게 채널 금액을 보내지 않습니다.'],
  ['에스크로 수수료','채널 가격의 3% 또는 최소 $1 중 큰 금액입니다.']
];
checks.getRange('A10:F10').values=[['번호','구매 전 확인 항목','판매자에게 요구할 증빙','통과 기준','상태','메모']];
const checklist=[
  [1,'완전한 YPP 광고 수익화','현재 날짜가 보이는 Studio > Earn 화면','Watch Page Ads와 Shorts Feed Ads 활성','미확인','팬펀딩만 활성인 경우 불통과'],
  [2,'28일·90일 성과','Analytics 화면 녹화 또는 채팅 내 캡처','조회수·수익·트래픽 소스가 매물 설명과 일치','미확인','단일 스크린샷보다 화면 녹화 권장'],
  [3,'저작권·정책 상태','Copyright 및 Channel violations 화면','활성 경고·스트라이크·재사용 콘텐츠 이력 없음','미확인','과거 수익화 중지 이력도 질문'],
  [4,'무효 트래픽','수익 분석과 관련 알림 화면','무효 트래픽 경고·수익 조정 문제 없음','미확인','월수익 과장 후보는 특히 확인'],
  [5,'Brand Account','권한 관리 화면','Owner 초대 및 Primary Owner 변경 가능','미확인','개인 채널이면 안전 이전 불가'],
  [6,'AdSense 변경','Earn 화면의 연결 변경 옵션','현재 변경 가능, 32일 제한에 걸리지 않음','미확인','사이트 OFF 표시는 진행 중단 사유'],
  [7,'에스크로 검증 범위','에스크로 담당자와의 플랫폼 내 채팅','위 1~6을 결제 전 검증한다고 서면 확인','미확인','접근권 수령 뒤 환불 제한'],
  [8,'판매자 접근 제거','권한 관리 화면','구매자 Primary Owner 지정 후 판매자 완전 제거','미확인','복구 보증과 별개로 즉시 확인']
];
checks.getRange('A11:F18').values=checklist;
checks.getRange('A20:F20').values=[['문의 대상','가격','문의일','상태','다음 행동','매물 URL']];
checks.getRange('A21:F25').values=[
  ['Serkan SEKOMY',120,new Date('2026-09-12'),'답변 대기','AdSense OFF 사유와 실시간 증빙 확인','https://omnifluxs.com/channel/f19d1240-1dd8-4b57-a1ac-0eec87477d26'],
  ['Zach_rhymaxxx',137,new Date('2026-09-12'),'테스트 답변 대기','1차 수익화 허용 기준으로 72시간·200회 조건 문의','https://omnifluxs.com/channel/08676fb6-51e4-4069-9a29-acc4ce0c49d6'],
  ['ATULxRBLX',147,new Date('2026-09-12'),'테스트 답변 대기','1차 수익화 허용 기준으로 72시간·200회 조건 문의','https://omnifluxs.com/channel/90841c40-cfbe-4f6f-a40a-4a4953ae6df9'],
  ['fart.pranks09',76,new Date('2026-09-12'),'답변 대기','재사용 콘텐츠·저작권·수익 0 사유 확인','https://omnifluxs.com/channel/6baf2fa7-8268-4377-871b-594fca5e0e4f'],
  ['Kashmiri Youtuber',158,new Date('2026-09-12'),'답변 대기','시청자 국가·언어·정책 이력 확인','https://omnifluxs.com/channel/1cf2751d-2f01-4227-910e-a203744b3b84']
];
checks.getRange('A27:B30').values=[
  ['출처','URL'],
  ['OmniFluxs Escrow Services','https://omnifluxs.com/escrow-services'],
  ['YouTube YPP 개요','https://support.google.com/youtube/answer/72851'],
  ['YouTube AdSense 연결 변경','https://support.google.com/youtube/answer/7367146']
];
checks.getRange('A1:F30').format.font={name:font,size:10};
checks.getRange('A1:F1').format={fill:'#172554',font:{name:font,size:18,bold:true,color:'#FFFFFF'}};
for(const range of ['A10:F10','A20:F20','A27:B27']) checks.getRange(range).format={fill:'#1E3A8A',font:{name:font,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center'};
checks.getRange('A3:A8').format={fill:'#E0E7FF',font:{name:font,bold:true,color:'#1E3A8A'},verticalAlignment:'top'};
checks.getRange('B3:B8').format={fill:'#F8FAFC',wrapText:true,verticalAlignment:'top'};
checks.getRange('A11:F18').format.wrapText=true;
checks.getRange('A21:F25').format.wrapText=true;
checks.getRange('B21:B25').format.numberFormat='$0.00';
checks.getRange('C21:C25').format.numberFormat='yyyy-mm-dd';
[16,38,34,32,24,48].forEach((w,i)=>checks.getRangeByIndexes(0,i,30,1).format.columnWidth=w);
checks.getRange('A28:B30').format.wrapText=true;
checks.getRange('1:1').format.rowHeight=32;
checks.freezePanes.freezeRows(10);

workbook.recalculate();
const inspectMain=await workbook.inspect({kind:'table',range:`구매 후보!A1:R15`,include:'values,formulas',tableMaxRows:15,tableMaxCols:18});
const inspectErrors=await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},summary:'final formula error scan'});
console.log(inspectMain.ndjson);
console.log(inspectErrors.ndjson);
const p1=await workbook.render({sheetName:'구매 후보',range:'A1:R18',scale:1,format:'png'});
const p2=await workbook.render({sheetName:'구매 전 확인',range:'A1:F30',scale:1.2,format:'png'});
await fs.writeFile(`${outputDir}/구매후보_미리보기.png`,new Uint8Array(await p1.arrayBuffer()));
await fs.writeFile(`${outputDir}/구매전체크_미리보기.png`,new Uint8Array(await p2.arrayBuffer()));
const output=await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outputDir}/OmniFluxs_유튜브채널_구매검토_2026-09-12.xlsx`);
