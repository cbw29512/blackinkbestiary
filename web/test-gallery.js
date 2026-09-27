const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
async function api(path,options={}){const r=await fetch(path,{headers:{"Content-Type":"application/json"},...options});const d=await r.json();if(!r.ok)throw new Error(d.error||r.status);return d}
function render(d){
 const results=d.results||[], selections=d.selections||{}, groups=new Map();
 for(const item of results){if(!groups.has(item.page_id))groups.set(item.page_id,[]);groups.get(item.page_id).push(item)}
 document.querySelector("#summary").textContent=`${results.length} attempts · ${Object.keys(selections).length} pages have a selected best candidate`;
 document.querySelector("#gallery").innerHTML=[...groups.entries()].map(([page,items])=>{
   const name=items[0]?.monster_name||page, selected=selections[page]?.candidate;
   return `<section class="monster-group"><h2>${esc(page)} · ${esc(name)}</h2><div class="candidate-grid">${items.sort((a,b)=>a.candidate-b.candidate).map(x=>`
   <article class="candidate-card ${selected===x.candidate?"selected":""}">
   ${x.image_path?`<img src="/${esc(x.image_path)}?v=${encodeURIComponent(x.finished_at||"")}" alt="${esc(name)} candidate ${x.candidate}">`:`<div class="placeholder">No image</div>`}
   <p><strong>Candidate ${x.candidate}</strong> · ${esc(x.status)}</p><p class="meta">Seed ${esc(x.seed)}</p>
   ${x.status==="ready_for_review"?`<button class="pick" data-page="${esc(page)}" data-candidate="${x.candidate}">${selected===x.candidate?"Selected":"Pick Best"}</button>`:""}
   </article>`).join("")}</div></section>`
 }).join("");
 document.querySelectorAll(".pick").forEach(b=>b.onclick=async()=>{await api("/api/test-gallery/select",{method:"POST",body:JSON.stringify({page_id:b.dataset.page,candidate:Number(b.dataset.candidate)})});refresh()})
}
async function refresh(){try{render(await api("/api/test-gallery"))}catch(e){document.querySelector("#summary").textContent=e.message}}
refresh();setInterval(refresh,5000);