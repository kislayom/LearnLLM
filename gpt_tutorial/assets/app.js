/* Interactive layer for the GPT tutorial.
   - "My Questions & Notes" saved in localStorage (with export)
   - per-section progress checkboxes + progress bar (saved in localStorage)
   - live math widgets: softmax, gradient descent, attention, LR schedule, sampling
   All widgets are optional: each init() runs only if its placeholder exists on the page. */

document.addEventListener('DOMContentLoaded', () => {
  initProgress();
  initNotes();
  initSoftmax();
  initGradientDescent();
  initAttention();
  initLRSchedule();
  initSampling();
});

const PAGE = document.body.dataset.page || 'page';
const LS = {
  get:(k,d)=>{ try{ const v=JSON.parse(localStorage.getItem(k)); return v==null?d:v; }catch(e){ return d; } },
  set:(k,v)=>localStorage.setItem(k,JSON.stringify(v))
};
const $ = (sel,root=document)=>root.querySelector(sel);
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function download(name,content){const b=new Blob([content],{type:'text/plain'});const a=document.createElement('a');
  a.href=URL.createObjectURL(b);a.download=name;a.click();URL.revokeObjectURL(a.href);}
function softmaxArr(z){const m=Math.max(...z.filter(isFinite));const e=z.map(v=>isFinite(v)?Math.exp(v-m):0);
  const s=e.reduce((a,b)=>a+b,0)||1;return e.map(x=>x/s);}

/* ---------- progress ---------- */
function initProgress(){
  const key='gpt_progress_'+PAGE;
  const state=LS.get(key,{});
  const heads=[...document.querySelectorAll('h2')];
  function updateBar(){
    const done=heads.filter(h=>state[h.id]).length;
    const bar=$('#progress-bar'), lbl=$('#progress-label');
    if(bar) bar.style.width=(heads.length?done/heads.length*100:0)+'%';
    if(lbl) lbl.textContent=`${done} / ${heads.length} sections marked done`;
  }
  heads.forEach((h,i)=>{
    if(!h.id) h.id='sec'+i;
    const lab=document.createElement('label'); lab.className='prog';
    const cb=document.createElement('input'); cb.type='checkbox'; cb.checked=!!state[h.id];
    cb.addEventListener('change',()=>{state[h.id]=cb.checked; LS.set(key,state); updateBar();});
    lab.append(cb, Object.assign(document.createElement('span'),{textContent:'done'}));
    h.appendChild(lab);
  });
  updateBar();
}

/* ---------- notes (shared across all days) ---------- */
function initNotes(){
  const mount=$('#notes'); if(!mount) return;
  const key='gpt_notes';
  let notes=LS.get(key,[]);
  mount.innerHTML=`
    <h3>📝 My Questions &amp; Notes</h3>
    <p class="muted">Saved privately in your browser (localStorage); persists across reloads and is shared between Day 1 &amp; Day 2. Export anytime.</p>
    <div class="note-input">
      <input id="note-q" placeholder="Type a question or note, then press Enter (e.g. why divide by √d?)"/>
      <button id="note-add">Save</button>
    </div>
    <div id="note-list"></div>
    <div class="note-actions">
      <button id="note-md">⬇ Export .md</button>
      <button id="note-json">⬇ Export .json</button>
      <button id="note-clear" class="danger">Clear all</button>
    </div>`;
  const list=$('#note-list',mount);
  const render=()=>{
    list.innerHTML = notes.length ? '' : '<p class="muted">No notes yet — jot your first question above.</p>';
    notes.forEach((n,i)=>{
      const row=document.createElement('div'); row.className='note-item';
      row.innerHTML=`<div><span class="note-page">[${escapeHtml(n.page)}]</span> ${escapeHtml(n.text)}<div class="note-time">${escapeHtml(n.time)}</div></div>`;
      const del=document.createElement('button'); del.className='note-del'; del.textContent='✕';
      del.onclick=()=>{notes.splice(i,1);LS.set(key,notes);render();};
      row.appendChild(del); list.appendChild(row);
    });
  };
  const add=()=>{const inp=$('#note-q',mount);const t=inp.value.trim();if(!t)return;
    notes.unshift({text:t,page:PAGE,time:new Date().toLocaleString()});LS.set(key,notes);inp.value='';render();};
  $('#note-add',mount).onclick=add;
  $('#note-q',mount).addEventListener('keydown',e=>{if(e.key==='Enter')add();});
  $('#note-md',mount).onclick=()=>download('my-questions.md',
    '# My Questions & Notes\n\n'+notes.map(n=>`- **[${n.page}] ${n.time}** — ${n.text}`).join('\n')+'\n');
  $('#note-json',mount).onclick=()=>download('my-questions.json',JSON.stringify(notes,null,2));
  $('#note-clear',mount).onclick=()=>{if(confirm('Delete ALL saved notes?')){notes=[];LS.set(key,notes);render();}};
  render();
}

/* ---------- softmax playground ---------- */
function initSoftmax(){
  const m=$('#w-softmax'); if(!m) return;
  m.innerHTML=`<h4>🎛️ Softmax playground</h4>
    <p class="muted">Drag the logits and watch probabilities recompute. Lower temperature = sharper (more confident).</p>
    <div class="sliders">
      <label>z₁ <input type="range" id="z0" min="-3" max="5" step="0.1" value="2"><span id="z0v"></span></label>
      <label>z₂ <input type="range" id="z1" min="-3" max="5" step="0.1" value="1"><span id="z1v"></span></label>
      <label>z₃ <input type="range" id="z2" min="-3" max="5" step="0.1" value="0.1"><span id="z2v"></span></label>
      <label>temperature <input type="range" id="temp" min="0.2" max="3" step="0.1" value="1"><span id="tempv"></span></label>
    </div>
    <div id="sm-bars" class="bars"></div>`;
  const upd=()=>{
    const T=+$('#temp',m).value; $('#tempv',m).textContent=T.toFixed(1);
    const z=['z0','z1','z2'].map(id=>{const v=+$('#'+id,m).value;$('#'+id+'v',m).textContent=v.toFixed(1);return v/T;});
    const p=softmaxArr(z);
    $('#sm-bars',m).innerHTML=p.map((pi,i)=>
      `<div class="bar"><div class="bar-fill" style="height:${pi*120}px"></div><div class="bar-lbl">${(pi*100).toFixed(1)}%</div><div class="muted">z${i+1}</div></div>`).join('');
  };
  m.querySelectorAll('input').forEach(i=>i.addEventListener('input',upd)); upd();
}

/* ---------- gradient descent simulator ---------- */
function initGradientDescent(){
  const m=$('#w-gd'); if(!m) return;
  m.innerHTML=`<h4>⛰️ Gradient-descent simulator &nbsp;<span class="muted">(loss L(θ)=θ²)</span></h4>
    <p class="muted">Step downhill with θ ← θ − η·2θ. Try η &gt; 0.5 to see it overshoot, and η &gt; 1 to diverge.</p>
    <div class="sliders">
      <label>learning rate η <input type="range" id="gd-lr" min="0.01" max="1.1" step="0.01" value="0.1"><span id="gd-lrv"></span></label>
      <button id="gd-step">Step</button><button id="gd-run">Run ▶</button><button id="gd-reset">Reset</button>
    </div>
    <canvas id="gd-canvas" width="520" height="240"></canvas>
    <div id="gd-msg" class="muted"></div>`;
  const cv=$('#gd-canvas',m), ctx=cv.getContext('2d');
  const X0=-3,X1=3; let x=-2.6, timer=null;
  const toPx=v=>40+(v-X0)/(X1-X0)*(cv.width-80);
  const toPy=L=>cv.height-30-L/9*(cv.height-50);
  function draw(){
    ctx.clearRect(0,0,cv.width,cv.height);
    ctx.strokeStyle='#3a4150';ctx.lineWidth=1;ctx.beginPath();
    ctx.moveTo(40,10);ctx.lineTo(40,cv.height-30);ctx.lineTo(cv.width-15,cv.height-30);ctx.stroke();
    ctx.strokeStyle='#7cc4ff';ctx.lineWidth=2;ctx.beginPath();
    for(let i=0;i<=100;i++){const xx=X0+(X1-X0)*i/100;const px=toPx(xx),py=toPy(xx*xx);i?ctx.lineTo(px,py):ctx.moveTo(px,py);}
    ctx.stroke();
    const px=toPx(Math.max(X0,Math.min(X1,x))),py=toPy(Math.min(9,x*x));
    ctx.fillStyle=Math.abs(x)>2.9?'#ff9d7c':'#ffd479';ctx.beginPath();ctx.arc(px,py,7,0,7);ctx.fill();
    ctx.fillStyle='#9aa3b2';ctx.font='12px monospace';ctx.fillText('θ',cv.width-26,cv.height-12);ctx.fillText('L(θ)=θ²',48,20);
  }
  function step(){
    const lr=+$('#gd-lr',m).value; x=x-lr*2*x;
    const msg=$('#gd-msg',m);
    if(!isFinite(x)||Math.abs(x)>6){msg.textContent='⚠️ Diverged! η is too large — each step overshoots the valley and grows.';x=Math.sign(x||1)*6;stop();}
    else if(Math.abs(x)<0.02){msg.textContent='✅ Converged to the minimum (θ≈0).';}
    else msg.textContent=`θ = ${x.toFixed(3)},  loss = ${(x*x).toFixed(3)}`;
    draw();
  }
  function stop(){if(timer){clearInterval(timer);timer=null;}}
  $('#gd-step',m).onclick=step;
  $('#gd-run',m).onclick=()=>{stop();timer=setInterval(step,160);};
  $('#gd-reset',m).onclick=()=>{stop();x=-2.6;$('#gd-msg',m).textContent='';draw();};
  $('#gd-lr',m).addEventListener('input',()=>$('#gd-lrv',m).textContent=(+$('#gd-lr',m).value).toFixed(2));
  $('#gd-lrv',m).textContent=(+$('#gd-lr',m).value).toFixed(2);
  draw();
}

/* ---------- attention weights ---------- */
function initAttention(){
  const m=$('#w-attn'); if(!m) return;
  m.innerHTML=`<h4>🔎 Attention weights</h4>
    <p class="muted">1-D query &amp; keys for clarity. Weightⱼ = softmax(query · keyⱼ). Align the query with a key to send attention there.</p>
    <div class="sliders">
      <label>query q <input type="range" id="aq" min="-2" max="2" step="0.1" value="1"><span id="aqv"></span></label>
      <label>key k₁ <input type="range" id="ak0" min="-2" max="2" step="0.1" value="1.5"><span id="ak0v"></span></label>
      <label>key k₂ <input type="range" id="ak1" min="-2" max="2" step="0.1" value="0.5"><span id="ak1v"></span></label>
      <label>key k₃ <input type="range" id="ak2" min="-2" max="2" step="0.1" value="-1"><span id="ak2v"></span></label>
      <label>key k₄ <input type="range" id="ak3" min="-2" max="2" step="0.1" value="0"><span id="ak3v"></span></label>
    </div>
    <div id="attn-bars" class="bars"></div>`;
  const upd=()=>{
    const q=+$('#aq',m).value; $('#aqv',m).textContent=q.toFixed(1);
    const ks=[0,1,2,3].map(i=>{const v=+$('#ak'+i,m).value;$('#ak'+i+'v',m).textContent=v.toFixed(1);return v;});
    const w=softmaxArr(ks.map(k=>q*k));
    $('#attn-bars',m).innerHTML=w.map((wi,i)=>
      `<div class="bar"><div class="bar-fill" style="height:${wi*120}px"></div><div class="bar-lbl">${(wi*100).toFixed(0)}%</div><div class="muted">k${i+1}</div></div>`).join('');
  };
  m.querySelectorAll('input').forEach(i=>i.addEventListener('input',upd)); upd();
}

/* ---------- learning-rate schedule (warmup + cosine decay) ---------- */
function initLRSchedule(){
  const m=$('#w-lr'); if(!m) return;
  m.innerHTML=`<h4>📈 LR schedule: warmup + cosine decay</h4>
    <p class="muted">Ramp up linearly during warmup, then cosine-decay toward a small floor. Stabilises early training, fine-tunes late.</p>
    <div class="sliders">
      <label>warmup steps <input type="range" id="lr-w" min="0" max="3000" step="50" value="500"><span id="lr-wv"></span></label>
      <label>total steps <input type="range" id="lr-t" min="3000" max="20000" step="500" value="10000"><span id="lr-tv"></span></label>
    </div>
    <canvas id="lr-canvas" width="520" height="200"></canvas>`;
  const cv=$('#lr-canvas',m), ctx=cv.getContext('2d');
  const MAX=1, MIN=0.1;
  const lrAt=(it,w,t)=> it<w ? MAX*it/Math.max(1,w)
    : it>t ? MIN
    : MIN+(MAX-MIN)*0.5*(1+Math.cos(Math.PI*(it-w)/(t-w)));
  function draw(){
    const w=+$('#lr-w',m).value, t=+$('#lr-t',m).value;
    $('#lr-wv',m).textContent=w; $('#lr-tv',m).textContent=t;
    ctx.clearRect(0,0,cv.width,cv.height);
    ctx.strokeStyle='#3a4150';ctx.beginPath();ctx.moveTo(40,10);ctx.lineTo(40,cv.height-25);ctx.lineTo(cv.width-12,cv.height-25);ctx.stroke();
    ctx.strokeStyle='#7ee787';ctx.lineWidth=2;ctx.beginPath();
    for(let i=0;i<=200;i++){const it=t*i/200;const lr=lrAt(it,w,t);
      const px=40+(cv.width-55)*i/200, py=(cv.height-25)-(lr/MAX)*(cv.height-45);i?ctx.lineTo(px,py):ctx.moveTo(px,py);}
    ctx.stroke();
    const wx=40+(cv.width-55)*(w/t); ctx.strokeStyle='#ffd479';ctx.setLineDash([4,4]);ctx.beginPath();
    ctx.moveTo(wx,10);ctx.lineTo(wx,cv.height-25);ctx.stroke();ctx.setLineDash([]);
    ctx.fillStyle='#9aa3b2';ctx.font='12px monospace';ctx.fillText('lr',46,18);ctx.fillText('step',cv.width-38,cv.height-9);
    ctx.fillStyle='#ffd479';ctx.fillText('warmup',wx+4,22);
  }
  m.querySelectorAll('input').forEach(i=>i.addEventListener('input',draw)); draw();
}

/* ---------- sampling: temperature & top-k ---------- */
function initSampling(){
  const m=$('#w-sampling'); if(!m) return;
  const base=[3.2,2.5,2.1,1.0,0.5,0.2,-0.5,-1.0];
  const labels=['the','cat','dog','sat','ran','sky','qx','zz'];
  m.innerHTML=`<h4>🌡️ Sampling: temperature &amp; top-k</h4>
    <p class="muted">High temperature flattens the distribution (more random/creative); top-k keeps only the k most likely tokens.</p>
    <div class="sliders">
      <label>temperature <input type="range" id="s-t" min="0.2" max="2" step="0.05" value="1"><span id="s-tv"></span></label>
      <label>top-k <input type="range" id="s-k" min="1" max="8" step="1" value="8"><span id="s-kv"></span></label>
    </div>
    <div id="s-bars" class="bars wide"></div>`;
  const upd=()=>{
    const T=+$('#s-t',m).value, k=+$('#s-k',m).value;
    $('#s-tv',m).textContent=T.toFixed(2); $('#s-kv',m).textContent=k;
    let z=base.map(v=>v/T);
    const thr=[...z].sort((a,b)=>b-a)[k-1];
    z=z.map(v=>v>=thr?v:-Infinity);
    const p=softmaxArr(z);
    $('#s-bars',m).innerHTML=p.map((pi,i)=>
      `<div class="bar"><div class="bar-fill ${pi===0?'zero':''}" style="height:${pi*120}px"></div><div class="bar-lbl">${(pi*100).toFixed(0)}</div><div class="muted">${labels[i]}</div></div>`).join('');
  };
  m.querySelectorAll('input').forEach(i=>i.addEventListener('input',upd)); upd();
}
