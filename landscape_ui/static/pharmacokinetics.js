(() => {
  const source = document.getElementById("pk-chart-data");
  const canvas = document.getElementById("pk-chart");
  if (!source || !canvas) return;
  if (typeof Chart === "undefined") return;
  canvas.hidden = false;
  canvas.parentElement.classList.add("pk-chart-ready");
  document.getElementById("pk-chart-fallback").hidden = true;
  const model = JSON.parse(source.textContent);
  const series = (key, label, color, dashed) => ({label,
    data: model.points.map(row => ({x:row.time_h,y:row[key]})),
    borderColor:color, borderWidth:2, borderDash:dashed?[6,4]:[],
    pointRadius:0, pointHitRadius:8, tension:0, fill:false});
  new Chart(canvas, {type:"line",data:{datasets:[
    series("reference_ng_ml","Fixed reference","#176b71",false),
    series("comparison_ng_ml",`Clearance × ${model.inputs.clearance_scale}`,"#b47b2b",true)]},
    options:{responsive:true,maintainAspectRatio:false,animation:false,
      interaction:{mode:"nearest",axis:"x",intersect:false},
      plugins:{legend:{display:false},tooltip:{callbacks:{
        title:items=>`${items[0].parsed.x.toFixed(3)} hours after dose`,
        label:item=>`${item.dataset.label}: ${item.parsed.y.toFixed(3)} ng/mL`}}},
      scales:{x:{type:"linear",min:0,max:48,title:{display:true,text:"Hours after dose"},
        ticks:{stepSize:6},grid:{color:"#edf1f2"}},
        y:{beginAtZero:true,title:{display:true,text:"Simulated concentration (ng/mL)"},grid:{color:"#edf1f2"}}}}});
})();
