(()=>{window.__fs=[];const proto=Object.getPrototypeOf(document.body.style);
Object.defineProperty(proto,'fontSize',{configurable:true,get(){return this.getPropertyValue('font-size')},
 set(v){const st=(new Error()).stack.split(String.fromCharCode(10)).slice(2,6).map(s=>s.trim().replace(/^at /,'').replace(/https?:[^ ]*precision20-ui\.js\?v=\d+:/,'L')).join(' < ');window.__fs.push({v:String(v),st});this.setProperty('font-size',v)}});})();
