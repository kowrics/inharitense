
/* Inventory Reports: search and pagination on already-filtered server records. */
(function(){'use strict';function ready(){
 document.querySelectorAll('[data-report-table]').forEach(function(root){
  var rows=Array.from(root.querySelectorAll('[data-record-row]'));
  var query=root.querySelector('.report-table-search'), previous=root.querySelector('.report-prev'),next=root.querySelector('.report-next'), count=root.querySelector('.report-page-count');
  var page=0,size=12,matched=rows;
  function paint(){matched=rows.filter(function(r){return r.textContent.toLocaleLowerCase().includes(query.value.trim().toLocaleLowerCase());});
   var pages=Math.max(1,Math.ceil(matched.length/size));page=Math.min(page,pages-1);
   rows.forEach(function(r){r.hidden=true;});matched.slice(page*size,(page+1)*size).forEach(function(r){r.hidden=false;});
   count.textContent=matched.length?(page*size+1)+'–'+Math.min((page+1)*size,matched.length)+' of '+matched.length+' records':'No matching records';
   previous.disabled=page===0;next.disabled=page>=pages-1;
  }
  query.addEventListener('input',function(){page=0;paint();});previous.addEventListener('click',function(){page--;paint();});next.addEventListener('click',function(){page++;paint();});paint();
 });}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ready);else ready();
})();
