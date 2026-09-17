window.makeCaptionLineInput=function(text, i){
  const inp=document.createElement('input');
  inp.type='text'; inp.value=text; inp.dataset.capline='1';
  inp.style.cssText='width:100%;background:#0a1017;border:1px solid var(--line);color:var(--txt);'
                   +'border-radius:8px;padding:7px 10px;font-size:14px;margin-bottom:5px';
  inp.addEventListener('keydown', ev=>{
    if(ev.key==='Enter'){
      // 커서 자리에서 자른다 → 뒤쪽이 새 줄이 된다(워드프로세서와 같은 감각)
      ev.preventDefault();
      const at=inp.selectionStart, head=inp.value.slice(0,at).trim(), tail=inp.value.slice(at).trim();
      if(!head || !tail) return;                 // 빈 줄은 안 만든다
      inp.value=head;
      const nxt=window.makeCaptionLineInput(tail, i+1);
      inp.parentNode.insertBefore(nxt, inp.nextSibling);
      nxt.focus(); nxt.setSelectionRange(0,0);
    } else if(ev.key==='Backspace' && inp.selectionStart===0 && inp.selectionEnd===0){
      // 줄 맨 앞에서 지우면 윗줄과 합친다
      const prev=inp.previousElementSibling;
      if(!prev || prev.dataset.capline!=='1') return;
      ev.preventDefault();
      const at=prev.value.length;
      prev.value=(prev.value+' '+inp.value).trim();
      inp.parentNode.removeChild(inp);
      prev.focus(); prev.setSelectionRange(at, at);
    }
  });
  return inp;
}
;
