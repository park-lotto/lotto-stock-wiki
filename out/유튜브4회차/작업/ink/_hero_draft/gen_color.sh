#!/bin/bash
# 컬러판 생성 — SHOTLIST §3 문장 그대로, 흑백 g_<이름>.png 를 기준그림으로. 쓰기: bash gen_color.sh f_hope m_tired ...
# 여(f_*)는 "white shirt … tie black" 대신 넥타이 없는 문장(설계 문장대로 하면 여자에게 넥타이를 그려 넣었다, f_tired 실측)
# 동시 2개까지(그 이상이면 429 로 20회 재시도를 다 쓰고 실패했다)
cd "$(dirname "$0")"; export PYTHONUTF8=1
PM="Keep every black line of the reference exactly as it is, same pose, same framing, same size. Add only soft flat watercolor-style coloring with no gradients: skin #F2C9B8, hair #6E6761, white shirt stays white with faint blue-grey #C9D4DE fold shadows only, tie black, laptop or furniture sand #E9DCC6. Pure white background, no new lines, no outlines thicker, no text."
PF="Keep every black line of the reference exactly as it is, same pose, same framing, same size. Add only soft flat watercolor-style coloring with no gradients: skin #F2C9B8, hair #6E6761, white top stays white with faint blue-grey #C9D4DE fold shadows only, no tie, laptop or furniture sand #E9DCC6. Pure white background, no new lines, no new objects, no outlines thicker, no text."
one(){ n=$1; P="$PM"; [[ $n == f_* ]] && P="$PF"
  # 노트북 없는 포즈에 "laptop or furniture" 를 주면 노트북·책상·스카프를 새로 그려 넣었다(m_point·f_point·f_excited 실측) → 그 구절 빼고 '새 물체 금지'
  [[ $n != *laptop* ]] && P="${P/, laptop or furniture sand #E9DCC6/}" && P="${P/no new lines,/no new lines, no new objects, no desk, no laptop, no scarf, no necklace,}"; py gen_hero.py "c_$n" "$P" "g_$n.png" --color > "_genc_$n.log" 2>&1; echo "$n: $(tail -1 _genc_$n.log | cut -c1-40)"; }
args=("$@"); i=0
while [ $i -lt ${#args[@]} ]; do one "${args[$i]}" & [ $((i+1)) -lt ${#args[@]} ] && one "${args[$((i+1))]}" & wait; i=$((i+2)); done
