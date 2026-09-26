const byId=(id)=>document.getElementById(id);
const esc=(s)=>String(s??'').replace(/[&<>"]/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const short=(s)=>String(s||'unknown').slice(0,8);
function age(ts){if(!ts)return 'unknown';const n=(Date.now()-Date.parse(ts))/1000;if(n<60)return Math.max(0,Math.round(n))+'s ago';if(n<3600)return Math.round(n/60)+'m ago';return Math.round(n/3600)+'h ago';}
async function load(){
 try{
  const r=await fetch('/api/autopilot-status',{cache:'no-store'});const d=await r.json();
  const h=d.heartbeat||{},rt=d.runtime||{},pf=d.preflight||{},c=d.canary_counts||{};
  const cards=[['Engine',short(d.engine_commit),esc(d.engine_commit)],['Autopilot',esc(h.phase||'unknown')+' / '+esc(h.status||'unknown'),age(h.updated_at)],['ComfyUI',esc(rt.status||'unknown'),esc(rt.stage||'')],['Preflight',esc(pf.status||'unknown'),age(pf.updated_at)],['Approved',c.approved||0,'of '+(d.canary_total||0)],['Awaiting review',c.review||0,'fresh candidates']];
  byId('summary').innerHTML=cards.map((x)=>'<div class="card"><div class="muted">'+x[0]+'</div><div class="big">'+x[1]+'</div><div class="muted">'+x[2]+'</div></div>').join('');
  const pct=d.canary_total?Math.round(((c.approved||0)/d.canary_total)*100):0;
  byId('progressText').textContent=(c.approved||0)+' approved • '+(c.review||0)+' awaiting review • '+(c.failed||0)+' failed • '+(c.other||0)+' generating/other';
  byId('progressFill').style.width=pct+'%';
  byId('canaries').innerHTML=(d.canaries||[]).map((x)=>{const img=x.image_path?'<img src="/'+esc(x.image_path)+'?t='+Date.now()+'" alt="'+esc(x.page_id)+'">':'<div class="muted">No current image</div>';const err=x.error?'<pre class="bad">'+esc(x.error)+'</pre>':'';return '<div class="card canary">'+img+'<div class="big">'+esc(x.page_id)+' — '+esc(x.monster_name||'')+'</div><div>'+esc(x.status)+'</div><div class="muted">engine '+short(x.engine_commit)+' • '+esc(x.review_stage||'no review')+(x.review_score!=null?' • score '+x.review_score:'')+'</div>'+err+'</div>';}).join('');
  byId('failures').innerHTML=(d.latest_failures||[]).length?(d.latest_failures||[]).map((x)=>'<div class="card"><b>'+esc(x.page_id||'system')+'</b><div class="bad">'+esc(x.status)+'</div><div class="muted">'+age(x.finished_at)+'</div><pre>'+esc(x.error||'')+'</pre></div>').join(''):'<div class="card ok">No current recorded failures.</div>';
 }catch(e){byId('summary').innerHTML='<div class="card bad">Monitor API unavailable: '+esc(e.message)+'</div>';}
}
load();setInterval(load,5000);
