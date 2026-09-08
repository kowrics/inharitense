const CSRF=document.querySelector('meta[name=csrf-token]')?.content||document.querySelector('input[name=_csrf]')?.value||''; function secureFetch(url,opts={}){opts.headers={...(opts.headers||{}),...(CSRF?{'X-CSRFToken':CSRF}:{})};return fetch(url,opts)}
const $=s=>document.querySelector(s);let toastTimer;
function toast(msg,kind=''){const el=$('#toast');if(!el)return;el.textContent=msg;el.className='toast show '+kind;clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.className='toast',2600)}
function fmt(n){return Number(n||0).toLocaleString()}
function initTheme(){const saved=localStorage.getItem('inharitense-theme');if(saved==='dark')document.body.classList.add('dark');$('#themeBtn')?.addEventListener('click',()=>{document.body.classList.toggle('dark');localStorage.setItem('inharitense-theme',document.body.classList.contains('dark')?'dark':'light');if(window.__redrawDashboard)window.__redrawDashboard(window.DASH)})}
function initNotifications(){const btn=$('#notifBtn'),panel=$('#notifPanel');btn?.addEventListener('click',()=>{panel.classList.toggle('open');loadNotifications()});loadNotifications();setInterval(loadNotifications,10000)}
const NOTIF_ICON={request:'📋',approval:'✅',success:'✔',error:'✖',info:'•'};
function loadNotifications(){secureFetch('/api/notifications').then(r=>r.json()).then(list=>{const badge=$('#notifBadge');const unread=list.filter(x=>!x.read_flag).length;if(badge)badge.style.display=unread?'block':'none';const box=$('#notifList');if(box)box.innerHTML=list.length?list.map(x=>`<div class="notification ${x.read_flag?'':'unread'}"><b>${NOTIF_ICON[x.kind]||NOTIF_ICON.info} ${escapeHtml(x.title)}</b><p>${escapeHtml(x.message)}</p><small>${new Date(x.created_at).toLocaleString()}</small></div>`).join(''):'<div class="empty">No notifications.</div>'}).catch(()=>{})}
function markNotificationsRead(){secureFetch('/api/notifications/read',{method:'POST'}).then(()=>loadNotifications())}
function escapeHtml(s){return String(s??'').replace(/[&<>'"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[m]))}
function initDashboard(){if(!window.DASH||typeof Chart==='undefined')return;let charts={};function draw(d){window.DASH=d;Object.values(charts).forEach(c=>c.destroy());const common={responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{labels:{boxWidth:9,font:{size:10}}}},scales:{x:{ticks:{font:{size:9}},grid:{display:false}},y:{beginAtZero:true,ticks:{font:{size:9}},grid:{color:'rgba(30,60,45,.08)'}}}};charts.cat=new Chart($('#categoryChart'),{type:'bar',data:{labels:d.category_levels.map(x=>x.category.replace('PPE & Infection Control','PPE & Infection').replace('IT & BPO Equipment','IT & BPO').replace('Facility & Sanitation','Facility & Sanit.')),datasets:[{label:'On hand',data:d.category_levels.map(x=>x.qty),backgroundColor:'#2f8f68',borderRadius:7},{label:'Minimum',data:d.category_levels.map(x=>x.min),backgroundColor:'#e8b52e',borderRadius:7}]},options:{...common,scales:{...common.scales,x:{...common.scales.x},y:{...common.scales.y}}}});charts.mov=new Chart($('#movementChart'),{type:'line',data:{labels:d.movements.map(x=>x.label),datasets:[{label:'Stock IN',data:d.movements.map(x=>x.in),borderColor:'#2f8f68',backgroundColor:'rgba(47,143,104,.10)',fill:true,tension:.35,pointRadius:3},{label:'Stock OUT',data:d.movements.map(x=>x.out),borderColor:'#c75a4c',backgroundColor:'rgba(199,90,76,.06)',fill:true,tension:.35,pointRadius:3}]},options:{...common,elements:{line:{borderWidth:2}}}});charts.health=new Chart($('#healthChart'),{type:'doughnut',data:{labels:['Healthy','Reorder soon','Out of stock'],datasets:[{data:[d.health.healthy,d.health.reorder,d.health.out],backgroundColor:['#2f8f68','#e8b52e','#d89a8e'],borderWidth:0}]},options:{responsive:true,maintainAspectRatio:true,cutout:'72%',plugins:{legend:{display:false}}}});const total=d.total_items||1;$('#healthPct').textContent=Math.round(d.health.healthy/total*100)+'%';$('#hHealthy').textContent=d.health.healthy;$('#hReorder').textContent=d.health.reorder;$('#hOut').textContent=d.health.out;$('#movementCount').textContent=fmt(d.movements.reduce((a,x)=>a+x.count,0))+' movements';$('#lastUpdate').textContent=new Date().toLocaleTimeString([], {hour:'numeric',minute:'2-digit',second:'2-digit'});$('#activity').innerHTML=d.recent.length?d.recent.map(x=>`<div class="activity-row"><span class="move ${x.movement_type}">${x.movement_type==='in'?'↑':'↓'}</span><div><b>${escapeHtml(x.name)}</b><small>${escapeHtml(x.by_name||'System')} · ${new Date(x.created_at).toLocaleString()}</small></div><strong>${x.movement_type==='in'?'+':'-'}${x.quantity}</strong></div>`).join(''):'<div class="empty">No movements yet.</div>'}window.__redrawDashboard=draw;draw(window.DASH);setInterval(()=>secureFetch('/api/dashboard').then(r=>r.json()).then(draw).catch(()=>{}),5000)}
function initInventoryFilter(){const s=$('#search'),c=$('#cat');function run(){document.querySelectorAll('#inv tbody tr').forEach(r=>r.style.display=(!s.value||r.dataset.search.includes(s.value.toLowerCase()))&&(!c.value||r.dataset.cat===c.value)?'':'none')}s?.addEventListener('input',run);c?.addEventListener('change',run);run()}function quickMove(id,type){askQuantity(`Quantity for Stock ${type.toUpperCase()}:`,'1').then(qty=>{if(qty===null)return;secureFetch('/api/movement',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({inventory_id:id,movement_type:type,quantity:qty,note:'Quick dashboard adjustment'})}).then(r=>r.json().then(d=>({ok:r.ok,d}))).then(({ok,d})=>{if(!ok)throw Error(d.error||'Movement failed');toast(d.message,'success');setTimeout(()=>location.reload(),350)}).catch(e=>toast(e.message,'error'))})}
function initMovementForm(){$('#movementForm')?.addEventListener('submit',e=>{e.preventDefault();const body={inventory_id:$('#moveItem').value,movement_type:$('#moveType').value,quantity:$('#moveQty').value,note:$('#moveNote').value};secureFetch('/api/movement',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json().then(d=>({ok:r.ok,d}))).then(({ok,d})=>{if(!ok)throw Error(d.error);toast(d.message,'success');e.target.reset();setTimeout(()=>location.reload(),350)}).catch(e=>toast(e.message,'error'))})}
function openItemModal(item){const modal=$('#itemModal'),form=$('#itemForm');form.reset();$('#itemId').value='';$('#modalTitle').textContent=item?'Edit item':'Add item';if(item){Object.keys(item).forEach(k=>{const el=form.elements[k];if(el)el.value=item[k]??''});$('#itemId').value=item.id}modal.classList.add('open')}
function closeItemModal(){$('#itemModal')?.classList.remove('open')}
function editItem(item){openItemModal(item)}
$('#itemForm')?.addEventListener('submit',e=>{e.preventDefault();const fd=new FormData(e.target);const body=Object.fromEntries(fd.entries());secureFetch('/api/inventory',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json().then(d=>({ok:r.ok,d}))).then(({ok,d})=>{if(!ok)throw Error(d.error);toast(d.message,'success');closeItemModal();setTimeout(()=>location.reload(),350)}).catch(e=>toast(e.message,'error'))});
function deleteItem(id,name){askConfirm(`Delete ${name}? This cannot be undone.`).then(ok=>{if(!ok)return;secureFetch('/api/inventory/'+id,{method:'DELETE'}).then(r=>r.json().then(d=>({ok:r.ok,d}))).then(({ok,d})=>{if(!ok)throw Error(d.error);toast('Item deleted.','success');setTimeout(()=>location.reload(),350)}).catch(e=>toast(e.message,'error'))})}
function scanItem(){const q=$('#scan')?.value.trim();if(!q)return;secureFetch('/api/scan?q='+encodeURIComponent(q)).then(r=>r.json().then(d=>({ok:r.ok,d}))).then(({ok,d})=>{if(!ok)throw Error('No matching item found or you do not have access.');$('#scanResult').innerHTML=`<b>${escapeHtml(d.item.item_no)}</b> · ${escapeHtml(d.item.name)} · <strong>${d.item.qty} ${escapeHtml(d.item.unit)}</strong> on hand`;const sel=$('#moveItem');if(sel)sel.value=d.item.id}).catch(e=>$('#scanResult').textContent=e.message)}
let scannerStream=null,scanTimer=null;async function startScanner(){const modal=$('#scannerModal');modal.classList.add('open');const video=$('#scannerVideo'),status=$('#scannerStatus');try{if(!navigator.mediaDevices?.getUserMedia)throw Error('Camera access is not supported in this browser.');scannerStream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'}}});video.srcObject=scannerStream;
    if('BarcodeDetector' in window){
        // Preferred path: native decoder, handles QR + 1D barcodes (masks, gloves, etc. with real UPC/EAN codes).
        const detector=new BarcodeDetector({formats:['qr_code','code_128','code_39','ean_13','ean_8','upc_a','upc_e']});
        const scan=async()=>{if(!scannerStream)return;try{const codes=await detector.detect(video);if(codes.length){$('#scan').value=codes[0].rawValue;stopScanner();scanItem();return}}catch{}scanTimer=requestAnimationFrame(scan)};
        scan();
    } else if(typeof jsQR==='function'){
        // Fallback for Firefox/Safari/older Chrome, where BarcodeDetector doesn't exist: decode QR
        // codes ourselves from raw video frames via jsQR. Covers QR only, not 1D barcodes — item
        // codes here are alphanumeric text (e.g. ECMCI-ITB-002), which QR encodes natively.
        status.textContent='Camera is open — point it at a QR code.';
        const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d',{willReadFrequently:true});
        const scan=()=>{
            if(!scannerStream)return;
            if(video.readyState===video.HAVE_ENOUGH_DATA){
                canvas.width=video.videoWidth;canvas.height=video.videoHeight;
                ctx.drawImage(video,0,0,canvas.width,canvas.height);
                const imageData=ctx.getImageData(0,0,canvas.width,canvas.height);
                const result=jsQR(imageData.data,imageData.width,imageData.height,{inversionAttempts:'dontInvert'});
                if(result?.data){$('#scan').value=result.data;stopScanner();scanItem();return}
            }
            scanTimer=requestAnimationFrame(scan);
        };
        scan();
    } else status.textContent='Camera is open, but no barcode decoder is available in this browser. Use the manual code field or Demo scan.'
}catch(e){status.textContent=e.message+' Use Demo scan or manual code entry.'}}function stopScanner(){if(scanTimer)cancelAnimationFrame(scanTimer);if(scannerStream)scannerStream.getTracks().forEach(t=>t.stop());scannerStream=null;$('#scannerModal')?.classList.remove('open')}function suggestItemCode(){
    const catEl=$('#fCategory'),itemNoEl=$('#fItemNo'),codeEl=$('#fCode');
    const cat=catEl?.value;
    if(!cat||(itemNoEl&&itemNoEl.value.trim()))return; // never overwrite a number the user already has/typed
    secureFetch('/api/inventory/next-code?category='+encodeURIComponent(cat)).then(r=>r.json()).then(d=>{
        if(d.item_no&&itemNoEl&&!itemNoEl.value.trim())itemNoEl.value=d.item_no;
        if(d.code&&codeEl&&!codeEl.value.trim())codeEl.value=d.code;
    }).catch(()=>{});
}
function demoScan(){const first=document.querySelector('#moveItem option');if(first){$('#scan').value=first.dataset.code||first.textContent.split(' · ')[0];stopScanner();scanItem()}}
function askConfirm(message){
    return new Promise(resolve=>{
        const modal=$('#confirmModal');if(!modal){resolve(confirm(message));return}
        $('#confirmMessage').textContent=message;modal.classList.add('open');
        const yes=$('#confirmYes'),no=$('#confirmNo');
        function cleanup(result){modal.classList.remove('open');yes.removeEventListener('click',onYes);no.removeEventListener('click',onNo);resolve(result)}
        function onYes(){cleanup(true)} function onNo(){cleanup(false)}
        yes.addEventListener('click',onYes);no.addEventListener('click',onNo);
    });
}
function askQuantity(title,defaultValue){
    return new Promise(resolve=>{
        const modal=$('#quantityModal');if(!modal){const v=prompt(title,defaultValue);resolve(v===null?null:v);return}
        $('#quantityTitle').textContent=title;const input=$('#quantityInput');input.value=defaultValue;modal.classList.add('open');
        const ok=$('#quantityOk'),cancel=$('#quantityCancel');
        function cleanup(result){modal.classList.remove('open');ok.removeEventListener('click',onOk);cancel.removeEventListener('click',onCancel);resolve(result)}
        function onOk(){cleanup(input.value)} function onCancel(){cleanup(null)}
        ok.addEventListener('click',onOk);cancel.addEventListener('click',onCancel);
        setTimeout(()=>input.focus(),50);
    });
}
let forecastChart=null;
function initForecast(){const sel=$('#forecastItem');if(!sel)return;initForecastLoad()}
function filterForecastItems(){const q=($('#forecastSearch')?.value||'').toLowerCase();document.querySelectorAll('#forecastItem option').forEach(opt=>{opt.hidden=!!q&&!(opt.dataset.search||'').includes(q)})}
function initForecastLoad(){
    const sel=$('#forecastItem'),canvas=$('#forecastChart'),out=$('#forecastOutput');
    if(!sel||!sel.value)return;
    const lead=$('#fcLead')?.value||5,safety=$('#fcSafety')?.value||3;
    secureFetch(`/api/forecast/${sel.value}?lead=${encodeURIComponent(lead)}&safety=${encodeURIComponent(safety)}`).then(r=>r.json()).then(d=>{
        if(forecastChart)forecastChart.destroy();
        forecastChart=new Chart(canvas,{type:'line',data:{labels:d.history.map(x=>x.d),datasets:[{label:'Stock OUT',data:d.history.map(x=>x.outs),borderColor:'#2f8f68',backgroundColor:'rgba(47,143,104,.10)',fill:true,tension:.35,pointRadius:3}]},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},scales:{y:{beginAtZero:true}}}});
        out.innerHTML=`<div class="eyebrow">MODEL OUTPUT</div><h3>${escapeHtml(d.item.name)}</h3><p>Estimated daily usage: <b>${d.forecast.daily}</b> ${escapeHtml(d.item.unit)}/day.</p><div class="metric-grid"><div><b>${d.item.qty}</b><small>On hand</small></div><div><b>~${d.forecast.days_to_reorder}</b><small>Days to reorder point</small></div><div><b>${d.forecast.recommended}</b><small>Recommended qty</small></div></div><div class="forecast-verdict ${d.forecast.urgent?'urgent':''}">${d.forecast.urgent?'Review replenishment soon.':'Current stock is above the immediate reorder window.'}</div><div class="note">Lead time: ${d.forecast.lead_time} days · Safety threshold: ${d.forecast.safety} ${escapeHtml(d.item.unit)}. Procurement makes the final purchasing decision.</div>`
    }).catch(e=>out.innerHTML='<div class="empty">Unable to load forecast.</div>')
}
initTheme();initNotifications();
