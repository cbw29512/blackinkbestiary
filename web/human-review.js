const $=(id)=>document.getElementById(id);
const esc=(s)=>String(s??'').replace(/[&<>"]/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let model=null;
let currentPageId=null;

function pct(v){return v==null?'—':Number(v).toFixed(1)+'/100';}
function short(s){return String(s||'unknown').slice(0,8);}
function currentPage(){return (model?.pages||[]).find(p=>p.page_id===currentPageId)||null;}
function reviewablePages(){return (model?.pages||[]).filter(p=>p.awaiting_human);}

async function load(){
  const res=await fetch('/api/human-review',{cache:'no-store'});
  const data=await res.json();
  if(!res.ok||data.error) throw new Error(data.error||'Review API failed');
  model=data;
  const queue=reviewablePages();
  if(!currentPageId||!queue.some(p=>p.page_id===currentPageId)){
    currentPageId=queue[0]?.page_id||null;
  }
  render();
}

function render(){
  const q=model.quality||{};
  const cards=[
    ['Book readiness',pct(q.overall_automated_readiness)],
    ['Human canaries',model.human_approved+'/'+model.canary_total],
    ['Awaiting you',String(model.awaiting_human)],
    ['Need generation',String(model.needs_generation)],
    ['Engine',short(model.engine_commit)]
  ];
  $('scoreStrip').innerHTML=cards.map(([a,b])=>'<div class="score-card"><div class="score-label">'+esc(a)+'</div><div class="score-value">'+esc(b)+'</div></div>').join('');

  if(q.stale){
    $('staleBanner').classList.remove('hidden');
    $('staleBanner').textContent='The displayed 0–100 snapshot is stale relative to the current engine or quality contract. It is shown for context but will not be treated as current truth until the next publish.';
  }else $('staleBanner').classList.add('hidden');

  $('queueCount').textContent=model.human_approved+'/'+model.canary_total+' human approved';
  $('queue').innerHTML=(model.pages||[]).map(p=>{
    const img=p.image_url?'<img src="'+esc(p.image_url)+'?t='+Date.now()+'" alt="">':'<div></div>';
    const state=p.human_approved?'Human approved':(p.awaiting_human?'Needs your review':(p.needs_generation?'Regenerating':'Waiting'));
    return '<button class="queue-item '+(p.page_id===currentPageId?'active ':'')+(p.human_approved?'approved':'')+'" data-page="'+esc(p.page_id)+'">'+img+'<span><span class="queue-name">'+esc(p.page_id)+' · '+esc(p.monster_name||'')+'</span><br><span class="queue-status">'+esc(state)+'</span></span></button>';
  }).join('');
  document.querySelectorAll('.queue-item').forEach(b=>b.onclick=()=>{const p=model.pages.find(x=>x.page_id===b.dataset.page);if(p?.awaiting_human){currentPageId=p.page_id;render();}});

  const p=currentPage();
  if(!p){
    $('reviewContent').classList.add('hidden');
    $('emptyState').classList.remove('hidden');
  }else{
    $('emptyState').classList.add('hidden');
    $('reviewContent').classList.remove('hidden');
    $('candidateImage').src=(p.image_url||'')+'?t='+Date.now();
    $('candidateImage').alt=p.page_id+' '+(p.monster_name||'');
    $('pageId').textContent=p.page_id;
    $('pageStatus').textContent=p.status;
    $('reviewId').textContent=p.review_id||'no exact hash';
    $('monsterName').textContent=p.monster_name||p.page_id;
    $('habitat').textContent=p.habitat||'Not specified';
    $('storyMoment').textContent=p.story_moment||'Not specified';
    $('mustInclude').innerHTML=(p.must_include||[]).length?(p.must_include||[]).map(x=>'<li>'+esc(x)+'</li>').join(''):'<li>No explicit list in page contract.</li>';
    const a=p.advisory||{};
    $('advisoryStage').textContent=a.stage||'no stage';
    $('advisoryScore').textContent=a.score==null?'No local score available.':'Local score '+a.score+' / 100';
    $('advisoryDefects').innerHTML=(a.defects||[]).length?(a.defects||[]).map(x=>'<li>'+esc(x)+'</li>').join(''):'<li>No advisory defect text.</li>';
    const h=p.human_history||[];
    $('historyCard').classList.toggle('hidden',!h.length);
    $('history').innerHTML=h.slice().reverse().map(x=>'<div class="history-entry"><b>'+esc(x.decision)+' · '+esc(x.stage||'')+'</b><div>'+esc(x.notes||'')+'</div></div>').join('');
    $('rejectFields').classList.add('hidden');
    $('notes').value='';
    $('decisionMessage').textContent='';
    $('decisionMessage').className='message';
  }

  const metrics=q.metrics||{};
  const ordered=[
    ['Foundation',metrics.foundation_readiness],
    ['Technical QA',metrics.technical_qa_pass_rate],
    ['Premium visual',metrics.visual_cleanliness],
    ['Semantic accuracy',metrics.semantic_accuracy],
    ['Completeness',metrics.completeness],
    ['Print/package',metrics.print_package_readiness],
    ['Locked pages',metrics.locked_page_progress],
    ['Replication',metrics.replication_readiness]
  ];
  $('metrics').innerHTML=ordered.map(([k,v])=>'<div class="metric-card"><div class="metric-name">'+esc(k)+'</div><div class="metric-value">'+esc(pct(v))+'</div></div>').join('');
  $('metricTimestamp').textContent=q.measured_at?'measured '+new Date(q.measured_at).toLocaleString():'not measured yet';
  const f=model.human_feedback||{};
  $('feedbackSummary').innerHTML='<div class="metric-value">'+(f.approvals||0)+' approved / '+(f.rejections||0)+' rejected</div><div class="muted">'+(f.distinct_pages_reviewed||0)+' distinct pages reviewed</div>';
  const blockers=q.known_blockers||[];
  $('blockers').innerHTML=blockers.length?blockers.map(x=>'<div>'+esc(x)+'</div>').join(''):'<div class="muted">No current blockers recorded.</div>';
}

async function decide(decision){
  const p=currentPage();
  if(!p)return;
  const payload={page_id:p.page_id,candidate:p.candidate,review_id:p.review_id,decision};
  if(decision==='reject'){
    payload.stage=$('stage').value;
    payload.notes=$('notes').value.trim();
    if(!payload.notes){
      $('decisionMessage').textContent='A rejection reason is required.';
      $('decisionMessage').className='message error';
      return;
    }
  }
  $('approveBtn').disabled=true;$('confirmRejectBtn').disabled=true;
  $('decisionMessage').textContent='Saving decision…';
  try{
    const res=await fetch('/api/human-review/decision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data=await res.json();
    if(!res.ok||data.error)throw new Error(data.error||'Decision failed');
    model=data;
    if(data.publish_warning){
      $('decisionMessage').textContent='Decision saved locally. '+data.publish_warning;
      $('decisionMessage').className='message error';
    }
    const queue=reviewablePages();
    currentPageId=queue[0]?.page_id||null;
    render();
  }catch(e){
    $('decisionMessage').textContent=e.message;
    $('decisionMessage').className='message error';
  }finally{
    $('approveBtn').disabled=false;$('confirmRejectBtn').disabled=false;
  }
}

$('approveBtn').onclick=()=>decide('approve');
$('rejectBtn').onclick=()=>$('rejectFields').classList.toggle('hidden');
$('confirmRejectBtn').onclick=()=>decide('reject');
$('skipBtn').onclick=()=>{
  const q=reviewablePages();if(!q.length)return;
  const i=Math.max(0,q.findIndex(p=>p.page_id===currentPageId));
  currentPageId=q[(i+1)%q.length]?.page_id||null;render();
};
$('refreshBtn').onclick=()=>load().catch(showFatal);

function showFatal(e){
  $('staleBanner').classList.remove('hidden');
  $('staleBanner').textContent='Review Studio API unavailable: '+e.message;
}
load().catch(showFatal);
setInterval(()=>load().catch(()=>{}),15000);
