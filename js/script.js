const DATA_URL="output/data.json", GEO_URL="output/merged_kabkota.geojson";
const fmt=d3.format(","), fmtPct=d3.format(".2f");
const tooltip=d3.select("#tooltip");
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function tip(event,html){tooltip.style("opacity",1).html(html).style("left",Math.min(event.clientX+14,window.innerWidth-315)+"px").style("top",Math.min(event.clientY+14,window.innerHeight-120)+"px")}
function hideTip(){tooltip.style("opacity",0)}
function fmtNum(v){return Number.isFinite(+v)?fmt(Math.round(+v)):"Data tidak tersedia"}
function normalizeCode(v){const n=Number(v);return Number.isFinite(n)?n.toFixed(2):String(v)}
function colorTPT(c){return ["#fff1df","#ffd0a7","#f6a16e","#d96843","#9f2f28"][Math.max(0,Math.min(4,(+c||1)-1))]}
function duration(base=220){return window.matchMedia("(prefers-reduced-motion: reduce)").matches?0:base}

Promise.all([d3.json(DATA_URL),d3.json(GEO_URL)]).then(([data,geo])=>init(data,geo)).catch(err=>{
  const box=document.createElement("div");box.style.cssText="margin:24px;padding:18px;border:1px solid #d7a79a;background:#fff4ef;color:#8d2d1c;border-radius:14px;font-weight:700";
  box.textContent=`Visualisasi gagal dimuat: ${err.message}. Pastikan output/data.json dan output/merged_kabkota.geojson tersedia dan jalankan index.html melalui Live Server.`;document.body.appendChild(box);console.error(err)
});

function init(data,geo){
  const spatial=data.spatial||[], pca=data.pca||{}, moran=data.moran||{}, root=data.hierarchy?.root, story=data.story||{};
  const hierarchyStory=story.hierarchy||{};

  document.querySelector("#spatial-stats").innerHTML=[
    ["4,18%","Rata-rata TPT"],["11,37%","TPT tertinggi"],["148 / 514","Kab/kota TPT ≥ 5%"],["7,46 juta","Total penganggur"]
  ].map(x=>`<div class="stat"><div class="num">${x[0]}</div><div class="lab">${x[1]}</div></div>`).join("");
  document.querySelector("#moran-stats").innerHTML=[[moran.moran_i.toFixed(3),"Moran's I"],[moran.z_score.toFixed(2),"z-score"],[moran.p_value.toFixed(3),"p-value"],[`${moran.clusters.HH} / ${moran.clusters.LL}`,"HH / LL"]].map(x=>`<div class="stat"><div class="num">${x[0]}</div><div class="lab">${x[1]}</div></div>`).join("");
  document.querySelector("#pca-stats").innerHTML=[["38","Provinsi"],["9","Variabel"],[pca.pc1_percent.toFixed(2)+"%","PC1"],[pca.pc12_percent.toFixed(2)+"%","PC1 + PC2"]].map(x=>`<div class="stat"><div class="num">${x[0]}</div><div class="lab">${x[1]}</div></div>`).join("");
  document.querySelector("#hier-stats").innerHTML=[["98,65 jt","Pekerja Penuh"],["64,27%","Bagian pekerja penuh"],["92,56 jt","Laki-laki"],["7,58%","Pengangguran Terbuka SMA/SMK"]].map(x=>`<div class="stat"><div class="num">${x[0]}</div><div class="lab">${x[1]}</div></div>`).join("");

  const geoFeatures=[]; const seen=new Set();
  for(const f of (geo.features||[])){if(f.properties?.matched===false)continue;const code=normalizeCode(f.properties?.kode);if(seen.has(code))continue;seen.add(code);geoFeatures.push(f)}
  const geoByCode=new Map(spatial.map(d=>[normalizeCode(d.geo_code),d]));
  const centroidByCode=new Map();
  function fitMap(m,layer){try{const b=layer.getBounds();if(b.isValid())m.fitBounds(b,{padding:[12,12],maxZoom:6})}catch(e){console.warn(e)}}

  const map=L.map("map",{scrollWheelZoom:false,zoomControl:true});
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{attribution:"© OpenStreetMap contributors",maxZoom:18}).addTo(map);
  function tptStyle(f){const d=geoByCode.get(normalizeCode(f.properties?.kode));return {fillColor:d?colorTPT(d.tpt_class):"#d8d2cc",weight:.6,color:"#fff",fillOpacity:.84}}
  const choropleth=L.geoJSON(geoFeatures,{style:tptStyle,onEachFeature:(f,l)=>{
    const d=geoByCode.get(normalizeCode(f.properties?.kode));if(!d)return;
    l.bindTooltip(`<b>${d.name}</b><br>${d.province}<br>TPT: <b>${fmtPct(d.tpt)}%</b><br>Pengangguran: ${fmtNum(d.unemployed)}`,{sticky:true});
    l.on("mouseover",e=>e.target.setStyle({weight:2,color:"#3b2418",fillOpacity:1}));
    l.on("mouseout",e=>choropleth.resetStyle(e.target));
  }}).addTo(map);
  fitMap(map,choropleth);

  const symbolLayer=L.layerGroup();
  const centroids=[];
  for(const d of spatial){if(!Number.isFinite(d.unemployed))continue;const f=geoFeatures.find(x=>normalizeCode(x.properties?.kode)===normalizeCode(d.geo_code));if(!f)continue;const c=L.geoJSON(f).getBounds().getCenter();centroidByCode.set(normalizeCode(d.geo_code),c);const r=3+Math.sqrt(d.unemployed)/22;const marker=L.circleMarker(c,{radius:r,fillColor:"#b84632",color:"#fff",weight:1,fillOpacity:.74});marker.bindTooltip(`<b>${d.name}</b><br>${d.province}<br>Jumlah penganggur: <b>${fmtNum(d.unemployed)}</b><br>TPT: ${fmtPct(d.tpt)}%`);marker.on("mouseover",e=>e.target.setStyle({weight:2,fillOpacity:.95})).on("mouseout",e=>e.target.setStyle({weight:1,fillOpacity:.74}));marker.addTo(symbolLayer)}

  const mapLayers=L.control.layers(null,{"TPT (Choropleth)":choropleth,"Jumlah Penganggur (Proportional Symbol)":symbolLayer},{collapsed:true,position:"topleft"}).addTo(map);
  function updateMapLegend(){const br=data.meta.spatial_classification.breaks;document.querySelector("#map-legend").innerHTML=[0,1,2,3,4].map(i=>{const label=i===0?`≤ ${fmtPct(br[1])}%`:i===4?`> ${fmtPct(br[4])}%`:`${fmtPct(br[i])}% – ${fmtPct(br[i+1])}%`;return `<div class="legend-item" title="Kelas TPT ${i+1}: ${label}"><span class="swatch" style="background:${colorTPT(i+1)}"></span>${label}</div>`}).join("")}
  function setMapMode(mode){
    if(mode==="choropleth"){if(map.hasLayer(symbolLayer))map.removeLayer(symbolLayer);if(!map.hasLayer(choropleth))choropleth.addTo(map);document.querySelector("#btn-choropleth").classList.add("active");document.querySelector("#btn-symbol").classList.remove("active");updateMapLegend()}
    else{if(map.hasLayer(choropleth))map.removeLayer(choropleth);if(!map.hasLayer(symbolLayer))symbolLayer.addTo(map);document.querySelector("#btn-symbol").classList.add("active");document.querySelector("#btn-choropleth").classList.remove("active");document.querySelector("#map-legend").innerHTML=`<div class="legend-item" title="Ukuran lingkaran mengikuti jumlah penganggur absolut"><span class="swatch" style="background:#b84632"></span> Ukuran simbol ∝ jumlah penganggur absolut</div>`}
  }
  document.querySelector("#btn-choropleth").onclick=()=>setMapMode("choropleth");document.querySelector("#btn-symbol").onclick=()=>setMapMode("symbol");document.querySelector("#map-reset").onclick=()=>fitMap(map,choropleth);setMapMode("choropleth");
  document.querySelector("#top-tpt").innerHTML=(story.spatial?.top_tpt||[]).slice(0,5).map(d=>`<span class="chip"><b>${d.name}</b> · ${fmtPct(d.tpt)}%</span>`).join("");

  const lisaByCode=new Map((moran.local||[]).map(d=>[String(d.bps_code),d]));
  const lisaColors={HH:"#D55E00",LL:"#0072B2",HL:"#E69F00",LH:"#CC79A7",NS:"#BDBDBD"};
  const lisaDescriptions={HH:"TPT tinggi berdekatan dengan TPT tinggi",LL:"TPT rendah berdekatan dengan TPT rendah",HL:"TPT tinggi dikelilingi TPT rendah",LH:"TPT rendah dikelilingi TPT tinggi",NS:"Tidak signifikan"};
  const lisaMap=L.map("lisa-map",{scrollWheelZoom:false,zoomControl:true});
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{attribution:"© OpenStreetMap contributors",maxZoom:18}).addTo(lisaMap);
  const lisaLayer=L.geoJSON(geoFeatures,{style:f=>{const d=geoByCode.get(normalizeCode(f.properties?.kode));const l=d?lisaByCode.get(String(d.bps_code)):null;return {fillColor:lisaColors[l?.cluster||"NS"],color:"#fff",weight:.6,fillOpacity:.85}},onEachFeature:(f,l)=>{const d=geoByCode.get(normalizeCode(f.properties?.kode));const x=d?lisaByCode.get(String(d.bps_code)):null;if(d&&x){l.bindTooltip(`<b>${d.name}</b><br>TPT: ${fmtPct(d.tpt)}%<br>Klaster LISA: <b>${x.cluster}</b><br>p: ${Number(x.p_value).toFixed(3)}`,{sticky:true});l.on("mouseover",e=>e.target.setStyle({weight:2,color:"#3b2418",fillOpacity:1}));l.on("mouseout",e=>lisaLayer.resetStyle(e.target))}}}).addTo(lisaMap);
  fitMap(lisaMap,lisaLayer);
  document.querySelector("#lisa-legend").innerHTML=Object.entries(lisaColors).map(([k,v])=>`<div class="legend-item" title="${lisaDescriptions[k]}"><span class="swatch" style="background:${v}"></span>${k}</div>`).join("");
  document.querySelector("#lisa-reset").onclick=()=>fitMap(lisaMap,lisaLayer);
  setTimeout(()=>{map.invalidateSize();lisaMap.invalidateSize();fitMap(map,choropleth);fitMap(lisaMap,lisaLayer)},250);
  window.addEventListener("resize",()=>{map.invalidateSize();lisaMap.invalidateSize()});

  const pcaVarHost=document.querySelector("#variable-bubbles");
  pcaVarHost.innerHTML=(pca.variables||[]).map(v=>`<span class="variable-bubble" title="Variabel PCA: ${v.source_column||v.label}">${v.label}</span>`).join("");
  const vars=(pca.variables||[]).map(v=>({...v,label:({pct_urban:'Persentase Penduduk Perkotaan',rasio_ketergantungan:'Rasio Ketergantungan',pct_miskin:'Persentase Penduduk Miskin',upah_rerata:'Rata-rata Upah',pmtb_per_kapita:'PMTB per Kapita',pdrb_non_agri:'PDRB non-agri'}[v.key]||v.label)}));
  const tptByProvince=new Map((pca.scores||[]).map(d=>[d.province,+d.tpt_prov]));
  const ps=(pca.parallel_scores||[]).map(d=>({...d,tpt_prov:Number.isFinite(+d.tpt_prov)?+d.tpt_prov:(tptByProvince.get(d.province)??NaN)}));
  const pcaHost=d3.select("#pca-chart"), W=820,H=430,m={t:26,r:34,b:56,l:60};
  const svg=pcaHost.append("svg").attr("viewBox",`0 0 ${W} ${H}`);
  const x=d3.scaleLinear().domain(d3.extent(pca.scores,d=>d.pc1)).nice().range([m.l,W-m.r]), y=d3.scaleLinear().domain(d3.extent(pca.scores,d=>d.pc2)).nice().range([H-m.b,m.t]);
  svg.append("g").attr("transform",`translate(0,${H-m.b})`).call(d3.axisBottom(x));svg.append("g").attr("transform",`translate(${m.l},0)`).call(d3.axisLeft(y));
  svg.append("text").attr("x",W/2).attr("y",H-12).attr("text-anchor","middle").text(`PC1 (${pca.pc1_percent.toFixed(2)}%)`);
  svg.append("text").attr("transform","rotate(-90)").attr("x",-H/2).attr("y",17).attr("text-anchor","middle").text(`PC2 (${pca.pc2_percent.toFixed(2)}%)`);
  svg.append("line").attr("x1",x(0)).attr("x2",x(0)).attr("y1",m.t).attr("y2",H-m.b).attr("stroke","#ddd");svg.append("line").attr("x1",m.l).attr("x2",W-m.r).attr("y1",y(0)).attr("y2",y(0)).attr("stroke","#ddd");
  const points=svg.selectAll(".pca-point").data(pca.scores).join("circle").attr("class","pca-point").attr("cx",d=>x(d.pc1)).attr("cy",d=>y(d.pc2)).attr("r",5).attr("fill",d=>d3.interpolateOranges(Math.max(0,Math.min(1,(d.tpt_prov||0)/8)))).attr("stroke","#fff").attr("stroke-width",1.4).style("transition","r .18s ease,opacity .18s ease");
  const labels=svg.selectAll(".pca-label").data(pca.scores).join("text").attr("class","pca-label").attr("x",d=>x(d.pc1)+7).attr("y",d=>y(d.pc2)-7).attr("font-size",9).attr("fill","#6f665f").text(d=>d.province);
  const brushLayer=svg.append("g").attr("class","pca-brush");
  const pcaBrush=d3.brush().extent([[m.l,m.t],[W-m.r,H-m.b]]).on("end",({selection})=>{if(!selection){clearSelection();return;}const [[x0,y0],[x1,y1]]=selection;const chosen=pca.scores.filter(d=>{const cx=x(d.pc1),cy=y(d.pc2);return cx>=x0&&cx<=x1&&cy>=y0&&cy<=y1;}).map(d=>d.province);selectProvinces(chosen);});
  brushLayer.call(pcaBrush).lower();

  const pw=980,ph=370,pm={t:28,r:30,b:65,l:42}, px=d3.scalePoint().domain(vars.map(v=>v.key)).range([pm.l,pw-pm.r]), pscales={};
  vars.forEach(v=>pscales[v.key]=d3.scaleLinear().domain(d3.extent(ps,d=>d[v.key])).range([ph-pm.b,pm.t]));
  const psvg=d3.select("#parallel").append("svg").attr("viewBox",`0 0 ${pw} ${ph}`);
  psvg.selectAll(".pc-axis").data(vars).join("g").attr("class","pc-axis").attr("transform",v=>`translate(${px(v.key)},0)`).each(function(v){d3.select(this).call(d3.axisLeft(pscales[v.key]).ticks(4).tickSize(-4))});
  psvg.selectAll(".pc-label").data(vars).join("text").attr("x",v=>px(v.key)).attr("y",ph-18).attr("text-anchor","middle").attr("font-size",8.6).attr("font-weight",760).text(v=>({pct_urban:"% Penduduk Perkotaan",rasio_ketergantungan:"Ketergantungan",pct_miskin:"% Penduduk Miskin",upah_rerata:"Rata-rata Upah",pdrb_non_agri:"PDRB non-agri",pmtb_per_kapita:"PMTB per Kapita",ip_tik:"IP-TIK",apm_sma:"APM SMA",rls:"RLS"}[v.key]||v.label));
  const ptColor=d3.scaleLinear().domain(d3.extent(ps,d=>d.tpt_prov??0)).range([0,1]);
  const linePath=d=>d3.line()(vars.map(v=>[px(v.key),pscales[v.key](d[v.key])]));
  const lines=psvg.selectAll(".pc-line").data(ps).join("path").attr("class","pc-line").attr("d",linePath).attr("fill","none").attr("stroke",d=>d3.interpolateOranges(.25+.65*ptColor(d.tpt_prov??0))).attr("stroke-width",1.1).attr("opacity",.28).style("transition","opacity .18s ease,stroke-width .18s ease");
  function selectProvinces(names){
    const chosen=new Set(names);
    points.attr("r",d=>chosen.has(d.province)?8:4).attr("opacity",d=>chosen.has(d.province)?1:.3).attr("stroke",d=>chosen.has(d.province)?"#241f1c":"#fff").attr("stroke-width",d=>chosen.has(d.province)?2.4:1.2);
    labels.attr("font-weight",d=>chosen.has(d.province)?900:400).attr("fill",d=>chosen.has(d.province)?"#b84632":"#6f665f");
    lines.attr("stroke-width",d=>chosen.has(d.province)?3.6:1).attr("opacity",d=>chosen.has(d.province)?1:.09);
    msvg.selectAll(".matrix-point").attr("r",d=>chosen.has(d.province)?4.5:2).attr("opacity",d=>chosen.has(d.province)?1:.18).attr("stroke",d=>chosen.has(d.province)?"#241f1c":"none").attr("stroke-width",d=>chosen.has(d.province)?1.5:0);
  }
  function selectProvince(name){selectProvinces([name]);}
  function clearSelection(){points.attr("r",5).attr("opacity",1).attr("stroke","#fff").attr("stroke-width",1.4);labels.attr("font-weight",400).attr("fill","#6f665f");lines.attr("stroke-width",1.1).attr("opacity",.28);msvg.selectAll(".matrix-point").attr("r",2.5).attr("opacity",.5).attr("stroke","none")}
  lines.on("mouseenter",(e,d)=>{selectProvince(d.province);tip(e,`<b>${d.province}</b><br>TPT provinsi: ${fmtPct(d.tpt_prov)}%`) }).on("mousemove",(e)=>tooltip.style("left",Math.min(e.clientX+14,window.innerWidth-315)+"px").style("top",Math.min(e.clientY+14,window.innerHeight-120)+"px")).on("mouseleave",(e)=>{hideTip();clearSelection()}).on("click",(e,d)=>selectProvince(d.province));
  points.on("mouseenter",(e,d)=>{selectProvince(d.province);tip(e,`<b>${d.province}</b><br>PC1: ${d.pc1.toFixed(2)}<br>PC2: ${d.pc2.toFixed(2)}<br>TPT: ${fmtPct(d.tpt_prov)}%`)}).on("mousemove",(e)=>tooltip.style("left",Math.min(e.clientX+14,window.innerWidth-315)+"px").style("top",Math.min(e.clientY+14,window.innerHeight-120)+"px")).on("mouseleave",()=>{hideTip();clearSelection()}).on("click",(e,d)=>selectProvince(d.province));

  const correlation=pca.correlation_matrix||[]; const hw=560,hh=560,hm={t:86,r:14,b:14,l:106}, n=vars.length, cell=(hw-hm.l-hm.r)/n, cscale=d3.scaleLinear().domain([-1,0,1]).range(["#c0392b","#fffaf5","#0072B2"]);
  const displayLabel=k=>({pct_urban:'% Penduduk Perkotaan',pct_miskin:'% Penduduk Miskin',rasio_ketergantungan:'Rasio Ketergantungan'}[k]||vars.find(v=>v.key===k)?.label||k);
  function addSvgLabel(g,text,x,y,opts={}){const lines=text==='Rasio Ketergantungan'?['Rasio','Ketergantungan']:[text];lines.forEach((line,i)=>g.append('tspan').attr('x',x).attr('dy',i?11:0).text(line));g.attr('x',x).attr('y',y).attr('font-size',opts.fontSize||8.1).attr('font-weight',opts.fontWeight||400);}
  const hsvg=d3.select("#heatmap").append("svg").attr("viewBox",`0 0 ${hw} ${hh}`);
  vars.forEach((v,i)=>{const top=hsvg.append("text").attr("text-anchor","start").attr("transform",`rotate(-38,${hm.l+i*cell+cell/2},${hm.t-12})`);addSvgLabel(top,displayLabel(v.key),hm.l+i*cell+cell/2,hm.t-12,{fontSize:8.1});const left=hsvg.append("text").attr("text-anchor","end");addSvgLabel(left,displayLabel(v.key),hm.l-7,hm.t+i*cell+cell/2+3,{fontSize:8.5});});
  const cells=[];correlation.forEach((row,i)=>row.forEach((r,j)=>cells.push({i,j,r})));
  hsvg.selectAll(".heat").data(cells).join("rect").attr("class","heat").attr("x",d=>hm.l+d.j*cell).attr("y",d=>hm.t+d.i*cell).attr("width",cell-1).attr("height",cell-1).attr("rx",3).attr("fill",d=>cscale(d.r)).style("transition","filter .15s ease,stroke-width .15s ease").on("mouseenter",(e,d)=>{d3.select(e.currentTarget).attr("stroke","#241f1c").attr("stroke-width",2).style("filter","brightness(1.08)");tip(e,`<b>${vars[d.i].label}</b> × <b>${vars[d.j].label}</b><br>Korelasi Pearson: r = ${d.r.toFixed(2)}`)}).on("mousemove",(e)=>tooltip.style("left",Math.min(e.clientX+14,window.innerWidth-315)+"px").style("top",Math.min(e.clientY+14,window.innerHeight-120)+"px")).on("mouseleave",(e)=>{d3.select(e.currentTarget).attr("stroke","none").style("filter","none");hideTip()});

  const keyList=vars.map(v=>v.key), labelsMap=Object.fromEntries(vars.map(v=>[v.key,displayLabel(v.key)])), mw=650,mh=710,mm={t:8,r:8,b:132,l:62}, cell2=62;
  const msvg=d3.select("#matrix").append("svg").attr("viewBox",`0 0 ${mw} ${mh}`);
  keyList.forEach((ky,i)=>keyList.forEach((kx,j)=>{const gx=mm.l+j*cell2,gy=mm.t+i*cell2,g=msvg.append("g").attr("transform",`translate(${gx},${gy})`);if(i===j){g.append("rect").attr("width",cell2-2).attr("height",cell2-2).attr("fill","#f4e9df");const tt=g.append("text").attr("x",cell2/2).attr("y",cell2/2-(labelsMap[ky]==='Rasio Ketergantungan'?5:0)).attr("text-anchor","middle").attr("font-size",8.4).attr("font-weight",800);(labelsMap[ky]==='Rasio Ketergantungan'?['Rasio','Ketergantungan']:[labelsMap[ky]]).forEach((line,ii)=>tt.append("tspan").attr("x",cell2/2).attr("dy",ii?10:0).text(line))}else{const ex=d3.extent(ps,d=>d[kx]),ey=d3.extent(ps,d=>d[ky]),sx=d3.scaleLinear().domain(ex).range([5,cell2-7]),sy=d3.scaleLinear().domain(ey).range([cell2-7,5]);g.selectAll("circle").data(ps).join("circle").attr("class","matrix-point").attr("data-province",d=>d.province).attr("cx",d=>sx(d[kx])).attr("cy",d=>sy(d[ky])).attr("r",2.5).attr("fill","#d95f02").attr("opacity",.5).style("transition","r .15s ease,opacity .15s ease").on("mouseenter",(e,d)=>{selectProvince(d.province);tip(e,`<b>${d.province}</b><br>${labelsMap[kx]}: ${d[kx].toFixed(2)}<br>${labelsMap[ky]}: ${d[ky].toFixed(2)}`)}).on("mousemove",(e)=>tooltip.style("left",Math.min(e.clientX+14,window.innerWidth-315)+"px").style("top",Math.min(e.clientY+14,window.innerHeight-120)+"px")).on("mouseleave",()=>{hideTip();clearSelection()}).on("click",(e,d)=>selectProvince(d.province))}}));
  
  keyList.forEach((kx,j)=>{const lx=mm.l+j*cell2+cell2/2,ly=mh-58;const tx=msvg.append("text").attr("x",lx).attr("y",ly).attr("text-anchor","end").attr("font-size",8.1).attr("transform",`rotate(-45,${lx},${ly})`);(labelsMap[kx]==='Rasio Ketergantungan'?['Rasio','Ketergantungan']:[labelsMap[kx]]).forEach((line,ii)=>tx.append("tspan").attr("x",lx).attr("dy",ii?9:0).text(line));});

  const statusColors={"Pekerja Penuh":"#D55E00","Pekerja Paruh Waktu":"#0072B2","Setengah Penganggur":"#009E73","Pengangguran Terbuka":"#CC79A7"};
  const statusOrder=["Pekerja Penuh","Pekerja Paruh Waktu","Setengah Penganggur","Pengangguran Terbuka"];
  const educationOrder=["SD ke Bawah","SMP","SMA / SMK","Perguruan Tinggi (Dip/PT)"];
  const hierarchyData={
    name:"Angkatan Kerja",type:"root",
    children:statusOrder.map(name=>{
      const sNode=(root.children||[]).find(x=>x.name===name);
      return {name,color:statusColors[name],children:educationOrder.map(edName=>{
        const eNode=(sNode?.children||[]).find(x=>x.name===edName);
        return eNode?{name:eNode.name,color:statusColors[name],children:(eNode.children||[]).map(g=>({...g,value:+g.value||0,color:statusColors[name]}))}:null;
      }).filter(Boolean)};
    })
  };
  const sbW=680,sbH=680,radius=Math.min(sbW,sbH)/2-22;
  const sbsvg=d3.select("#sunburst").append("svg").attr("viewBox",`0 0 ${sbW} ${sbH}`).append("g").attr("transform",`translate(${sbW/2},${sbH/2})`);
  const sbroot=d3.hierarchy(hierarchyData).sum(d=>d.children?0:(d.value||0)).sort((a,b)=>b.value-a.value);d3.partition().size([2*Math.PI,radius])(sbroot);
  function hcolor(d){const status=d.depth===1?d.data.name:(d.ancestors().find(a=>a.depth===1)?.data.name||"");const base=d3.color(statusColors[status]||"#777");if(d.depth===1)return base.formatHex();if(d.depth===2)return base.brighter(.55).formatHex();if(d.depth===3)return base.brighter(1.05).formatHex();return "#fff"}
  const arc=d3.arc().startAngle(d=>d.x0).endAngle(d=>d.x1).innerRadius(d=>d.y0).outerRadius(d=>Math.max(d.y1-2,d.y0+1));
  const sbPaths=sbsvg.selectAll("path").data(sbroot.descendants().filter(d=>d.depth>0)).join("path").attr("d",arc).attr("fill",hcolor).attr("stroke","#fffaf5").attr("stroke-width",1).style("cursor","pointer");
  const center=sbsvg.append("circle").attr("r",48).attr("fill","#fff").attr("stroke","none").style("cursor","pointer");
  const centerTitle=sbsvg.append("text").attr("text-anchor","middle").attr("dy","-3").attr("font-size",12).attr("font-weight",850);const centerValue=sbsvg.append("text").attr("text-anchor","middle").attr("dy","16").attr("font-size",11).attr("fill","#6d625a");
  function setCenter(d=sbroot){centerTitle.text(d===sbroot?"Angkatan Kerja":d.data.name);centerValue.text(fmtNum(d.value)+" orang");const bc=document.querySelector("#sun-breadcrumb");bc.innerHTML="";d.ancestors().reverse().forEach((node,i,arr)=>{const b=document.createElement("button");b.className="crumb-btn";b.textContent=node===sbroot?"Angkatan Kerja":node.data.name;b.type="button";b.onclick=()=>zoomSun(node);bc.appendChild(b);if(i<arr.length-1){const sep=document.createElement("span");sep.className="crumb-sep";sep.textContent="›";bc.appendChild(sep)}})}
  function zoomSun(target){const xx=d3.scaleLinear().domain([target.x0,target.x1]).range([0,2*Math.PI]), yy=d3.scaleLinear().domain([target.y0,radius]).range([target.depth?20:0,radius]);const tr=sbsvg.transition().duration(duration(650));sbPaths.transition(tr).attrTween("d",function(d){const a0=d3.interpolate(d.x0,Math.max(target.x0,Math.min(target.x1,d.x0))),a1=d3.interpolate(d.x1,Math.max(target.x0,Math.min(target.x1,d.x1))),r0=d3.interpolate(d.y0,Math.max(target.y0,d.y0)),r1=d3.interpolate(d.y1,Math.max(target.y0,d.y1));return t=>d3.arc().startAngle(xx(a0(t))).endAngle(xx(a1(t))).innerRadius(yy(r0(t))).outerRadius(Math.max(yy(r1(t))-2,yy(r0(t))+1))()});setCenter(target)}
  sbPaths.on("mouseenter",(e,d)=>{d3.select(e.currentTarget).attr("stroke","#241f1c").attr("stroke-width",2);tip(e,`<b>${d.ancestors().reverse().slice(1).map(x=>x.data.name).join(" · ")}</b><br>${fmtNum(d.value)} orang<br>${(100*d.value/sbroot.value).toFixed(2)}% dari total`)}).on("mousemove",(e)=>tooltip.style("left",Math.min(e.clientX+14,window.innerWidth-315)+"px").style("top",Math.min(e.clientY+14,window.innerHeight-120)+"px")).on("mouseleave",e=>{d3.select(e.currentTarget).attr("stroke","#fffaf5").attr("stroke-width",1);hideTip()}).on("click",(e,d)=>zoomSun(d));center.on("click",()=>zoomSun(sbroot));setCenter(sbroot);

  const tmW=1180,tmH=600,tmsvg=d3.select("#treemap").append("svg").attr("viewBox",`0 0 ${tmW} ${tmH}`),tmroot=d3.hierarchy(hierarchyData).sum(d=>d.children?0:(d.value||0)).sort((a,b)=>b.value-a.value);
  d3.treemap().size([tmW,tmH]).paddingOuter(7).paddingInner(2).paddingTop(d=>d.depth===1?24:0)(tmroot);
  const tmGroups=tmsvg.selectAll(".tm-group").data(tmroot.descendants().filter(d=>d.depth>0)).join("g").attr("class","tm-group").attr("transform",d=>`translate(${d.x0},${d.y0})`);
  tmGroups.append("rect").attr("width",d=>Math.max(0,d.x1-d.x0)).attr("height",d=>Math.max(0,d.y1-d.y0)).attr("fill",hcolor).attr("fill-opacity",d=>d.depth===1?.96:d.depth===2?.58:.86).attr("stroke","#fffaf5").attr("stroke-width",d=>d.depth===1?2:1).style("cursor","pointer");
  const tmTextLayer=tmsvg.append("g").attr("class","tm-text-layer").style("pointer-events","none");
  tmGroups.filter(d=>d.depth===1).each(function(d){tmTextLayer.append("text").attr("class","tm-label").attr("x",d.x0+6).attr("y",d.y0+17).attr("font-size",12).attr("font-weight",850).attr("fill","#fff").text(d.data.name);});
  tmGroups.filter(d=>d.depth===3 && ((d.x1-d.x0)*(d.y1-d.y0)>5200)).each(function(d){const status=d.ancestors().find(a=>a.depth===1)?.data.name||"";const ed=(d.ancestors().find(a=>a.depth===2)?.data.name||"").replace(" (Dip/PT)","");const g=d.data.name;const t=tmTextLayer.append("text").attr("class","tm-label").attr("x",d.x0+6).attr("y",d.y0+16).attr("font-size",9).attr("font-weight",780).attr("fill","#241f1c");[status,ed,g].forEach((txt,i)=>t.append("tspan").attr("x",d.x0+6).attr("dy",i===0?0:11).text(txt));});
  tmGroups.on("mouseenter",(e,d)=>{tmGroups.select("rect").attr("fill-opacity",x=>x===d?1:(x.depth===1?.86:x.depth===2?.45:.45));tip(e,`<b>${d.ancestors().reverse().slice(1).map(x=>x.data.name).join(" · ")}</b><br>${fmtNum(d.value)} orang<br>${(100*d.value/tmroot.value).toFixed(2)}% dari total`)}).on("mousemove",(e)=>tooltip.style("left",Math.min(e.clientX+14,window.innerWidth-315)+"px").style("top",Math.min(e.clientY+14,window.innerHeight-120)+"px")).on("mouseleave",()=>{tmGroups.select("rect").attr("fill-opacity",d=>d.depth===1?.96:d.depth===2?.58:.86);hideTip()});
  const hleg=document.createElement("div");hleg.className="legend hierarchy-legend";hleg.innerHTML=statusOrder.map(s=>`<div class="legend-item" title="Status pekerjaan: ${s}"><span class="swatch" style="background:${statusColors[s]}"></span>${s}</div>`).join("");document.querySelector("#treemap").parentElement.appendChild(hleg);

  const education=(hierarchyStory.education_by_open_rate||[]).slice().sort((a,b)=>b.open_rate-a.open_rate);const er=d3.select("#education-rate"),ew=820,eh=270,em={t:18,r:24,b:46,l:180},esvg=er.append("svg").attr("viewBox",`0 0 ${ew} ${eh}`);const ex=d3.scaleLinear().domain([0,d3.max(education,d=>d.open_rate)*1.15]).range([em.l,ew-em.r]),ey=d3.scaleBand().domain(education.map(d=>d.education)).range([em.t,eh-em.b]).padding(.28);esvg.append("g").attr("transform",`translate(0,${eh-em.b})`).call(d3.axisBottom(ex).ticks(5).tickFormat(d=>d+"%"));esvg.append("g").attr("transform",`translate(${em.l},0)`).call(d3.axisLeft(ey).tickSize(0).tickFormat(d=>String(d).replace(" (Dip/PT)","")));esvg.selectAll("rect").data(education).join("rect").attr("x",em.l).attr("y",d=>ey(d.education)).attr("width",0).attr("height",ey.bandwidth()).attr("fill",d=>d.education==="SMA / SMK"?"#D55E00":"#e6a15b").attr("rx",5).on("mouseenter",(e,d)=>{d3.select(e.currentTarget).style("filter","brightness(1.08)");tip(e,`<b>${d.education}</b><br>Proporsi Pengangguran Terbuka: ${d.open_rate.toFixed(2)}%<br>Jumlah pengangguran terbuka: ${fmtNum(d.unemployed_open)}`)}).on("mousemove",(e)=>tooltip.style("left",Math.min(e.clientX+14,window.innerWidth-315)+"px").style("top",Math.min(e.clientY+14,window.innerHeight-120)+"px")).on("mouseleave",e=>{d3.select(e.currentTarget).style("filter","none");hideTip()}).transition().duration(duration(600)).attr("width",d=>ex(d.open_rate)-em.l);esvg.selectAll(".bar-label").data(education).join("text").attr("class","bar-label").attr("x",d=>ex(d.open_rate)+7).attr("y",d=>ey(d.education)+ey.bandwidth()/2+4).attr("font-size",10.5).attr("font-weight",800).text(d=>d.open_rate.toFixed(2)+"%");
}
