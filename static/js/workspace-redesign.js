(function(){
'use strict';
function initWorkspace(root){
  var type=root.dataset.workspace;
  var configs={
    'procurement':[['Approvals','Review purchase requests'],['Create order','Prepare a purchase order'],['Receiving','Verify delivered stock'],['Receipt history','View completed receipts']],
    'asset-operations':[['New transfer / maintenance','Create an asset transaction'],['Transfer history','Review custody changes'],['Maintenance history','Review asset care']],
    'asset-controls':[['Disposal request','Request disposal'],['Stock correction','Request an adjustment'],['Disposal approvals','Finance decisions'],['Stock approvals','Manager decisions']],
    'client-reports':[['Export report','Choose filters and format'],['Report overview','Review record totals']]
  };
  var cfg=configs[type];if(!cfg)return;
  var sections=[];
  if(type==='asset-operations'){
    var grid=root.querySelector('.cl-grid');
    var firstCards=grid?Array.from(grid.children).filter(function(n){return n.classList.contains('cl-card');}):[];
    if(firstCards.length===2){
      // put each form in its own tab without changing its POST or validation
      sections=[firstCards[0],firstCards[1]].concat(Array.from(root.children).filter(function(n){return n.classList.contains('cl-card');}));
      cfg=[['Transfer / Return','Request custody change'],['Maintenance entry','Record repair or inspection'],['Transfer history','Review movements'],['Maintenance history','Review work']];
      grid.style.display='contents';
    }
  } else if(type==='asset-controls'){
    sections=Array.from(root.children).filter(function(n){return n.classList.contains('panel');});
    // Conditional form visibility differs by role; infer labels from rendered headings.
    cfg=sections.map(function(sec){var title=(sec.querySelector('h2')||{}).textContent||'Task';return [title.trim(), 'Open this task'];});
  } else {
    sections=Array.from(root.children).filter(function(n){return n.classList.contains('cl-card');});
  }
  if(!sections.length)return;
  var tabs=document.createElement('div');tabs.className='workspace-tabs';tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','Workspace tasks');
  var buttons=[];
  sections.forEach(function(sec,i){
    sec.classList.add('workspace-view');sec.id='workspace-section-'+type+'-'+(i+1);
    sec.setAttribute('role','tabpanel');
    var btn=document.createElement('button');btn.type='button';btn.className='workspace-tab';btn.setAttribute('role','tab');
    btn.setAttribute('aria-controls',sec.id);btn.id='workspace-tab-'+type+'-'+(i+1);
    var label=(cfg[i]||[])[0]||'Section '+(i+1);
    var step=document.createElement('span');step.className='workspace-tab-number';step.textContent=String(i+1).padStart(2,'0');
    var text=document.createElement('span');text.textContent=label;
    btn.append(step,text);tabs.append(btn);buttons.push(btn);
    sec.setAttribute('aria-labelledby',btn.id);
    btn.addEventListener('click',function(){activate(i,true);});
    btn.addEventListener('keydown',function(e){if(e.key==='ArrowRight'||e.key==='ArrowLeft'){
      e.preventDefault();var next=(i+(e.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;buttons[next].focus();activate(next,true);
    }});
  });
  var intro=root.querySelector('.workspace-intro');if(intro)intro.insertAdjacentElement('afterend',tabs);else root.prepend(tabs);
  function activate(i,setHash){
    sections.forEach(function(sec,n){var active=n===i;sec.hidden=!active;buttons[n].setAttribute('aria-selected',String(active));buttons[n].tabIndex=active?0:-1;buttons[n].classList.toggle('is-active',active);});
    if(setHash&&history.replaceState){history.replaceState(null,'','#'+sections[i].id);}
  }
  var initial=sections.findIndex(function(s){return '#'+s.id===window.location.hash;});activate(initial>=0?initial:0,false);
}
function init(){document.querySelectorAll('.workspace-tabbed').forEach(initWorkspace);}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
