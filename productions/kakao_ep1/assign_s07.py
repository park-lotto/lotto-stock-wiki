"""S07 — 깨끗한 문장 라인에 단어 단위 정확 프레임 배정 (싱크 수정)"""
import sys, json, os, re
sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
words = json.load(open(os.path.join(BASE, "_audio", "S07_words.json"), encoding="utf-8"))
FPS = 30

def norm(s):
    return re.sub(r"[\s,.\?!]", "", s)

# (텍스트, accent) — v2 자연 문장 기준, 긴 건 분할, ASR오류 교정(나체빵 제거)·스터터 정리
LINES = [
    ("자 이제 방금 말씀드렸던 Play MCP를 다운받을 건데요", "Play MCP"),
    ("구글에 접속하셔서 Play MCP 들어가시면 되고", "Play MCP"),
    ("우측 상단에 있는 로그인 버튼을 눌러서 로그인 해주시면 됩니다", "로그인 버튼"),
    ("아래쪽에 보시면 네이버 MCP, 카카오톡 MCP가 두 개가 보이는데", "두 개"),
    ("안 보이시는 분들은 MCP 검색해서 찾으시면 됩니다", "MCP 검색"),
    ("네이버 MCP는 클로드가 네이버에 직접 검색하게 할 수 있는 기능이고", "네이버 MCP"),
    ("카카오톡 MCP는 검색된 정보를 카카오톡으로", "카카오톡 MCP"),
    ("보낼 수 있게 연결해주는 기능이라고 보시면 됩니다", "연결"),
    ("두 개 다 다운받아야 되니 하나씩", "두 개 다"),
    ("들어가셔서 도구함에 추가 누르시면 되고", "도구함에 추가"),
    ("카카오톡도 추가해주시면 됩니다", "추가"),
    ("그 다음 추가 있으면 코워크로 돌아와서 세팅을 해주셔야 되는데", "코워크"),
    ("들어와 보시면 플러스 버튼이 나오는데", "플러스 버튼"),
    ("커넥터 들어가시고 커넥터 관리 눌러 보시면", "커넥터 관리"),
    ("여기 커넥터 옆에 돋보기 모양이 보입니다", "돋보기"),
    ("돋보기에 커넥터 검색을 누르시고 플레이 MCP를 누르시면", "커넥터 검색"),
    ("아래쪽에 플레이 MCP라고 뜹니다", "플레이 MCP"),
    ("플레이 MCP를 누르시면 오른쪽 보시면 연결되지 않았습니다라 나옵니다", "연결되지 않았습니다"),
    ("그 아래 보시면 연결이라는 문구가 나오는데", "연결"),
    ("이 연결이라는 걸 눌러 보시면 연결이 될 겁니다", "연결"),
    ("잠시만 기다려 보세요", ""),
    ("클로드의 플레이 MCP를 연결하기가 나옵니다", "연결하기"),
    ("아래 보시면 필수 버튼 두 개를 눌러주시고", "필수 버튼 두 개"),
    ("모두 동의 후 계속하기", "모두 동의"),
    ("인증을 진행 중입니다", "인증"),
    ("잠시 후에 연결이 될 건데 조금만 기다려 주세요", "연결"),
    ("연결되면 나옵니다", "연결"),
    ("플레이 MCP가 연결이 되었다고 나왔습니다", "연결이 되었다"),
    ("연결이 되었으면 뒤로 가기를 누르셔서 메인화면으로 다시 오시고요", "뒤로 가기"),
    ("보시면 여기 검색창에 플레이 MCP가 연결이 잘 되었는지", "검색창"),
    ("간단하게 한번 해볼게요", ""),
    ("연결이 잘 되었으니 테스트를 간단하게 한번 해볼게요", "테스트"),
    ("연결된 플레이 MCP를 활용해서 네이버에서 오늘 증시가 어땠는지 검색하고", "검색하고"),
    ("카톡으로 보내주라고 한번 해보겠습니다", "카톡으로 보내"),
    ("네이버 검색 MCP가 잘 돌아가고 있네요", "잘 돌아가고"),
    ("카카오톡 MCP도 잘 돌아가고 있습니다", "잘 돌아가고"),
    ("중간에 이 작업에 허용이 나오시면 이걸 눌러 주셔야 됩니다", "허용"),
    ("카톡으로 전송이 완료됐다고 하는데 한번 볼게요", "전송이 완료"),
    ("카카오톡에 잘 왔는지 한번 보겠습니다", "잘 왔는지"),
    ("네 오늘 증시 마감 내용들 잘 나와 있죠", "잘 나와 있죠"),
    ("이렇게 해서 간단하게 테스트를 마쳤습니다", "테스트를 마쳤"),
    ("자 여기까지 잘 따라오셨습니다", "잘 따라오셨습니다"),
]

# 순차 매칭: 각 라인의 첫 토큰~끝 토큰을 단어스트림에서 순서대로 소비
p = 0
subs = []
N = len(words)
for text, accent in LINES:
    toks = [norm(t) for t in text.split() if norm(t)]
    first_tok, last_tok = toks[0], toks[-1]
    # 첫 토큰 찾기
    i = p
    while i < N and norm(words[i]["t"]) != first_tok:
        i += 1
    if i >= N:  # 폴백: 부분일치
        i = p
        while i < N and first_tok not in norm(words[i]["t"]) and norm(words[i]["t"]) not in first_tok:
            i += 1
    start_i = min(i, N - 1)
    # 끝 토큰 찾기 (start 이후)
    j = start_i
    last_j = start_i
    while j < N and norm(words[j]["t"]) != last_tok:
        j += 1
    if j >= N:
        j = start_i
        while j < N and last_tok not in norm(words[j]["t"]):
            j += 1
    last_j = min(j, N - 1)
    frm = round(words[start_i]["s"] * FPS)
    to = round(words[last_j]["e"] * FPS)
    subs.append({"from": frm, "to": to, "text": text, "accent": accent})
    p = last_j + 1

# 검증: 단조 증가 + 겹침 확인
prev = -1
print(f"총 {len(subs)} 라인")
for k, s in enumerate(subs):
    flag = ""
    if s["from"] < prev: flag += " ⚠겹침"
    if s["to"] <= s["from"]: flag += " ⚠역전"
    prev = s["to"]
    print(f"  {{ from: {s['from']:4d}, to: {s['to']:4d}, text: '{s['text']}', accent: '{s['accent']}' }},{flag}")

json.dump(subs, open(os.path.join(BASE,"_audio","S07_SUBS_final.json"),"w",encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("\n→ _audio/S07_SUBS_final.json")
