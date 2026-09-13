const places={
 hq:['메이커스랩 중앙 본사','전체 프로그램의 상태와 대표 판단을 모으는 중심입니다. 중앙 원형 본사와 주변 수공간·방사형 연결 동선을 외관 기준으로 유지합니다. 실제 관제 연결은 별도 작업입니다.'],
 shortem:['숏템메이커 구역','왼쪽 프로그램 구역 안에 내부 작업공간을 연결합니다. 표시한 건물은 진입점 후보이며, 정확한 동·층 배치는 아직 확정하지 않았습니다.'],
 stock:['스탁브레인 구역','메이커스랩의 두 번째 출시 프로그램 구역입니다. 오른쪽 건물군을 유지하며, 숏템메이커와 같은 한 회사의 관제 아래 연결합니다. 내부 배치는 아직 설계하지 않았습니다.'],
 expansion:['외곽 확장 구역','새 프로그램·프로젝트 증가에 따라 바깥쪽 건물군과 층을 늘리는 방향입니다. 기존 동·방·워커의 위치는 유지하고 새 공간을 추가합니다. 자동 증축은 아직 구현하지 않았습니다.']
};
document.querySelectorAll('[data-place]').forEach(button=>{button.addEventListener('click',()=>{const id=button.dataset.place;document.querySelectorAll('[data-place]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));document.querySelector('#title').textContent=places[id][0];document.querySelector('#description').textContent=places[id][1];document.querySelector('#mapping').hidden=id!=='shortem';});});
