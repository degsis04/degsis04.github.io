/* Interactive editorial; all country scores copied from linked Freedom House annual reports, 2022–2026. */
(() => {
  'use strict';
  const N = 'http://www.w3.org/2000/svg';
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const country = {
    ru: {name:'Россия', scores:[23,21,20,17,16], color:'#dcfb62', link:'https://freedomhouse.org/country/russia/freedom-net/2026', title:'Падение оценки продолжается', text:'С 2022 по 2026 год оценка России снизилась с 23 до 16 баллов. По данным Freedom House, в последние годы усиливались ограничения сервисов, контента и онлайн-коммуникаций. Это характеристика условий свободы интернета, а не степени технологической независимости.'},
    cn: {name:'Китай', scores:[10,9,9,9,9], color:'#fa8b73', link:'https://freedomhouse.org/country/china/freedom-net/2026', title:'Долгое плато у нижней границы', text:'Оценка Китая в 2022 году — 10 баллов, в 2023–2026 годах — 9. Это не означает отсутствия изменений внутри системы: индекс обобщает разные ограничения и уже находится близко к минимуму шкалы.'},
    in: {name:'Индия', scores:[51,50,50,51,50], color:'#98c9e5', link:'https://freedomhouse.org/country/india/freedom-net/2026', title:'Почти горизонтальная траектория', text:'Оценка Индии колебалась между 50 и 51 баллами. Однако стабильная итоговая цифра не означает отсутствия существенных событий: в стране документировали региональные отключения и ограничения доступа к онлайн-контенту.'}
  };
  let current='ru', points=[], drawing=false, revealed=false;
  const svg=$('#drawChart');
  const plot={left:90,right:738,top:24,bottom:339};
  const fx=i=>plot.left+(plot.right-plot.left)*i/4;
  const fy=v=>plot.bottom-(Math.max(0,Math.min(60,v))/60)*(plot.bottom-plot.top);
  const val=y=>(plot.bottom-y)/(plot.bottom-plot.top)*60;
  const pathFor=arr=>arr.map((p,i)=>`${i?'L':'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const el=(tag,attributes={})=>{const n=document.createElementNS(N,tag);Object.entries(attributes).forEach(([k,v])=>n.setAttribute(k,v));return n;};
  function textNode(parent,x,y,label,size=12,anchor='end'){
    const t=el('text',{x,y,fill:'#b7c9bc','font-size':size,'font-family':'ui-monospace, monospace','text-anchor':anchor});t.textContent=label;parent.appendChild(t);
  }
  function buildAxes(){
    const g=$('#gridLines'), labels=$('#axisLabels'), yrs=$('#yearLabels');
    g.replaceChildren();labels.replaceChildren();yrs.replaceChildren();
    for(const v of [0,15,30,45,60]){
      const y=fy(v);g.appendChild(el('line',{x1:plot.left,y1:y,x2:plot.right,y2:y,stroke:'#5b7062','stroke-width':'1','stroke-dasharray':v===0?'0':'2 6'}));
      textNode(labels,61,y+5,v,12);
    }
    for(let i=0;i<5;i++){
      const x=fx(i);
      g.appendChild(el('line',{x1:x,y1:plot.top,x2:x,y2:plot.bottom,stroke:'#354c3f','stroke-width':'1'}));
      textNode(yrs,x,366,2022+i,13,'middle');
    }
    textNode(labels,60,15,'0—60 / 100',9);
  }
  function renderUser(){
    $('#userPath').setAttribute('d',pathFor(points));
    $('#userPath').setAttribute('stroke',country[current].color);
    const finished=points.length>1 && points[points.length-1][0] > plot.right-30;
    $('#graphStatus').textContent=revealed?'ДАННЫЕ ОТКРЫТЫ':finished?'ЛИНИЯ НАРИСОВАНА':points.length>1?'ПРОДОЛЖАЙТЕ ВПРАВО →':'ГИПОТЕЗА НЕ ГОТОВА';
    $('#graphPrompt').textContent=revealed?'Сравните свою кривую с опубликованными баллами.':'Нарисуйте прогноз с 2022 по 2026 год →';
  }
  function resetChart(){
    drawing=false;revealed=false;points=[[fx(0),fy(country[current].scores[0])]];
    $('#actualPath').setAttribute('opacity','0');$('#actualPath').setAttribute('d','');
    $('#actualDots').replaceChildren();$('#realArea').replaceChildren();
    $('#revealPanel').hidden=true;$('#realLegend').classList.add('ghost');
    const s=$('#startDot');s.replaceChildren();
    s.appendChild(el('circle',{cx:fx(0),cy:fy(country[current].scores[0]),r:10,fill:country[current].color,stroke:'#263629','stroke-width':4}));
    const tag=el('text',{x:fx(0)+12,y:fy(country[current].scores[0])-16,fill:'#f2f5e8','font-size':14,'font-weight':'700'});tag.textContent=`${country[current].scores[0]} / 100`;s.appendChild(tag);
    renderUser();
  }
  function svgPos(e){const pt=svg.createSVGPoint();pt.x=e.clientX;pt.y=e.clientY;const ctm=svg.getScreenCTM();return ctm?pt.matrixTransform(ctm.inverse()):{x:plot.left,y:plot.bottom};}
  function addPos(e){let p=svgPos(e);let x=Math.max(plot.left,Math.min(plot.right,p.x));let y=Math.max(plot.top,Math.min(plot.bottom,p.y));
    if(!points.length)points=[[fx(0),fy(country[current].scores[0])]];
    const last=points[points.length-1];if(x<last[0])return;
    if(x-last[0]>0.8){points.push([x,y]);renderUser();}
  }
  svg.addEventListener('pointerdown',e=>{if(revealed)return;drawing=true;svg.setPointerCapture(e.pointerId);addPos(e);});
  svg.addEventListener('pointermove',e=>{if(!drawing||revealed)return;addPos(e);});
  function stopDraw(){drawing=false;renderUser();}
  svg.addEventListener('pointerup',stopDraw);svg.addEventListener('pointercancel',stopDraw);
  svg.addEventListener('keydown',e=>{
    if(revealed)return;
    if(!['ArrowRight','ArrowUp','ArrowDown',' '].includes(e.key))return;
    e.preventDefault();let last=points[points.length-1];if(!last)return;
    if(e.key==='ArrowRight')points.push([Math.min(plot.right,last[0]+(plot.right-plot.left)/4),last[1]]);
    if(e.key==='ArrowUp')points.push([Math.min(plot.right,last[0]+8),Math.max(plot.top,last[1]-15)]);
    if(e.key==='ArrowDown')points.push([Math.min(plot.right,last[0]+8),Math.min(plot.bottom,last[1]+15)]);
    if(e.key===' ')revealChart(); else renderUser();
  });
  function revealChart(){
    if(revealed)return;revealed=true;
    const d=country[current];const coords=d.scores.map((v,i)=>[fx(i),fy(v)]);
    const area=$('#realArea');area.replaceChildren();
    const poly=el('path',{d:pathFor(coords)+` L${plot.right},${plot.bottom} L${plot.left},${plot.bottom} Z`,fill:d.color,opacity:'.09'});area.appendChild(poly);
    const actual=$('#actualPath');actual.setAttribute('d',pathFor(coords));actual.setAttribute('opacity','1');
    const dots=$('#actualDots');dots.replaceChildren();
    coords.forEach((pt,i)=>{dots.appendChild(el('circle',{cx:pt[0],cy:pt[1],r:6,fill:'#fff',stroke:'#213229','stroke-width':2}));const t=el('text',{x:pt[0]+(i===4?-12:12),y:pt[1]-16,fill:'#fff','font-size':13,'font-weight':'700','text-anchor':i===4?'end':'start'});t.textContent=d.scores[i];dots.appendChild(t)});
    $('#revealScore').textContent=d.scores[4];$('#revealTitle').textContent=d.title;$('#revealText').textContent=d.text;
    $('#revealSource').href=d.link;$('#revealPanel').hidden=false;$('#realLegend').classList.remove('ghost');renderUser();
  }
  buildAxes();resetChart();
  $$('.country-tab').forEach(btn=>btn.addEventListener('click',()=>{
    current=btn.dataset.country;$$('.country-tab').forEach(b=>{let on=b===btn;b.classList.toggle('is-active',on);b.setAttribute('aria-pressed',on);});resetChart();
  }));
  $('#resetDraw').addEventListener('click',resetChart);
  $('#revealDraw').addEventListener('click',revealChart);

  const layerContent={
    network:{code:'LAYER_01 / INFRA',title:'Провода не знают, где родина. Правила маршрутизации — знают.',ru:'Технические средства противодействия угрозам и регулирование операторов позволяют централизованно влиять на доступ.',cn:'Система сетевой фильтрации «Великий китайский файрвол» сочетает контроль соединений и доступного контента.',in:'Региональные прекращения доступа становятся инструментом властей при протестах и кризисах.',note:'Примеры описаны в национальных отчётах Freedom House 2026; речь идёт о разных механизмах, а не об одинаковых национальных «стенах».'},
    platform:{code:'LAYER_02 / PLATFORMS',title:'Можно контролировать сеть — а можно строить свои цифровые сервисы.',ru:'Существуют сильные локальные сервисы и платформы наряду с ограничениями отдельных зарубежных ресурсов.',cn:'Крупная экосистема национальных платформ существует вместе с ограниченным доступом к зарубежным сервисам.',in:'UPI и другие элементы India Stack позволяют разным приложениям работать через совместимую инфраструктуру.',note:'Индийская UPI — пример цифровой общественной инфраструктуры, а не показатель отсутствия интернет-ограничений. Источник: Правительство Индии / NPCI, 2026.'},
    rules:{code:'LAYER_03 / GOVERNANCE',title:'Юридические нормы действуют по территориям — цифровые сервисы проходят сквозь них.',ru:'Регулирование хранения данных, интернет-трафика и деятельности платформ усиливает роль национального регулятора.',cn:'Регулирование информационного пространства охватывает платформы, контент и трансграничные информационные потоки.',in:'Законодательство регулирует платформы и связь; власти используют предписания о блокировке контента.',note:'Правовые инструменты имеют разный масштаб и цели; сравнение не заменяет анализа отдельных законов и судебных решений.'},
    rights:{code:'LAYER_04 / USERS',title:'Настоящая цена цифровой границы видна со стороны пользователя.',ru:'Freedom House: 16/100 в 2026 году; раздел о правах пользователей — 3 из возможных 40.',cn:'Freedom House: 9/100; раздел о правах пользователей — 0 из возможных 40.',in:'Freedom House: 50/100; раздел о правах пользователей — 16 из возможных 40.',note:'В 2026 году компоненты A/B/C составляют RU: 10/3/3, CN: 7/2/0, IN: 16/18/16 (максимумы 25/35/40). Более высокий балл означает более благоприятную оценку свободы.'}
  };
  let layerNum=0;
  function setLayer(name){const d=layerContent[name];
    $('#layerCode').textContent=d.code;$('#layerTitle').textContent=d.title;$('#layerRu').textContent=d.ru;$('#layerCn').textContent=d.cn;$('#layerIn').textContent=d.in;$('#layerNote').textContent=d.note;
    layerNum=['network','platform','rules','rights'].indexOf(name);$('.layers-counter').innerHTML=`0${layerNum+1} <span>/ 04</span>`;
    $$('.layer-button').forEach(btn=>{let on=btn.dataset.layer===name;btn.classList.toggle('selected',on);btn.setAttribute('aria-pressed',on);});
  }
  $$('.layer-button').forEach(btn=>btn.addEventListener('click',()=>setLayer(btn.dataset.layer)));setLayer('network');

  const feedback={yes:{right:false,title:'ПОКА НЕЛЬЗЯ СДЕЛАТЬ ТАКОЙ ВЫВОД',text:'Одна аномалия — сигнал к проверке, но не доказательство блокировки. Нужны повторные измерения, анализ ошибок, контрольная точка и сведения о конкретной сети. Иначе это может быть сбой сайта или соединения.'},no:{right:true,title:'ВЕРНО: ПРОВЕРЯЕМ ИЗМЕРЕНИЯ',text:'OONI различает аномальные измерения и автоматически подтверждённые блокировки веб-сайтов. Даже подтверждение относится к определённому тесту, сети и моменту времени — не ко всей стране навсегда.'}};
  $$('.quiz-option').forEach(btn=>btn.addEventListener('click',()=>{
    const d=feedback[btn.dataset.quiz];$$('.quiz-option').forEach(b=>b.classList.toggle('selected',b===btn));const box=$('#quizFeedback');box.className='quiz-feedback '+(d.right?'good':'bad');box.replaceChildren();const tag=document.createElement('span');tag.textContent=d.title;const p=document.createElement('p');p.textContent=d.text;box.append(tag,p);
  }));

  const futures={
    walls:{tag:'01 — PERIMETERS',title:'Сеть с более высокими стенами',description:'Государства делают ставку на управление трафиком, локальные сервисы и ограничение трансграничных потоков. Потенциальное преимущество — управляемость; риск — меньше доступных источников и сложнее связи между экосистемами.',pills:['НАЦИОНАЛЬНЫЙ КОНТРОЛЬ','ФРАГМЕНТАЦИЯ','РИСК ДЛЯ ДОСТУПА']},
    bridges:{tag:'02 — INTEROPERABILITY',title:'Самостоятельность без изоляции',description:'Национальные цифровые платформы развиваются на совместимых стандартах, как платёжные интерфейсы. Потенциал — конкуренция и удобство; риск — правила обмена данными и доступ к инфраструктуре могут остаться неравными.',pills:['ОТКРЫТЫЕ ПРОТОКОЛЫ','СОВМЕСТИМОСТЬ','ЦИФРОВЫЕ ОБЩИЕ БЛАГА']},
    rights:{tag:'03 — ACCOUNTABILITY',title:'Границы с публичными правилами',description:'Ограничения и решения платформ требуют обоснования, прозрачности и независимой проверки. Потенциал — большая защищённость прав; препятствие — институциональная сложность и конфликт национальных интересов.',pills:['ЗАЩИТА ПОЛЬЗОВАТЕЛЕЙ','ПРОЗРАЧНОСТЬ','ПОДОТЧЁТНОСТЬ']}
  };
  let selectedFuture='walls';
  function createFutureArt(type){const edges=$('#futureEdges'),nodes=$('#futureNodes');edges.replaceChildren();nodes.replaceChildren();
    const clusters=[{x:106,y:116,name:'RU',color:'#dcfb62'},{x:246,y:85,name:'CN',color:'#fa8b73'},{x:370,y:162,name:'IN',color:'#98c9e5'}];
    const satelliteOffsets=[[0,-62],[56,20],[-53,29],[-41,-33],[43,-37]];
    clusters.forEach((c,idx)=>{
      satelliteOffsets.forEach(([ox,oy],j)=>{const x=c.x+ox*.82,y=c.y+oy*.82;
        edges.appendChild(el('line',{x1:c.x,y1:c.y,x2:x,y2:y,stroke:c.color,'stroke-width':1.3,opacity:'.7'}));
        nodes.appendChild(el('circle',{cx:x,cy:y,r:3.3,fill:c.color}));
      });
      nodes.appendChild(el('circle',{cx:c.x,cy:c.y,r:29,fill:c.color}));
      const label=el('text',{x:c.x,y:c.y+5,'text-anchor':'middle',fill:'#16241d','font-family':'ui-monospace,monospace','font-size':15,'font-weight':'700'});label.textContent=c.name;nodes.appendChild(label);
      if(type==='walls')nodes.appendChild(el('circle',{cx:c.x,cy:c.y,r:61,fill:'none',stroke:c.color,'stroke-width':2,'stroke-dasharray':'5 8',opacity:'.8'}));
    });
    if(type==='bridges')[[0,1],[1,2],[0,2]].forEach(([a,b])=>edges.appendChild(el('line',{x1:clusters[a].x,y1:clusters[a].y,x2:clusters[b].x,y2:clusters[b].y,stroke:'#e4fb87','stroke-width':3,'stroke-dasharray':'9 7',opacity:'.85'})));
    if(type==='rights'){
      nodes.appendChild(el('circle',{cx:245,cy:206,r:22,fill:'#f7f7ec',stroke:'#f7f7ec'}));const t=el('text',{x:245,y:211,'text-anchor':'middle','font-family':'ui-monospace,monospace','font-size':12,fill:'#17261f'});t.textContent='YOU';nodes.appendChild(t);
      clusters.forEach(c=>edges.appendChild(el('line',{x1:c.x,y1:c.y,x2:245,y2:206,stroke:'#f7f7ec','stroke-width':2,'stroke-dasharray':'4 5'})));
    }
  }
  function setFuture(type){selectedFuture=type;const d=futures[type];$('#futureBadge').textContent=d.tag;$('#futureName').textContent=d.title;$('#futureDesc').textContent=d.description;
    $('#futureCriteria').replaceChildren(...d.pills.map(s=>{const x=document.createElement('span');x.textContent=s;return x}));
    $$('.future-choice').forEach(btn=>{const selected=btn.dataset.future===type;btn.classList.toggle('active',selected);btn.setAttribute('aria-pressed',selected)});createFutureArt(type);
  }
  $$('.future-choice').forEach(btn=>btn.addEventListener('click',()=>setFuture(btn.dataset.future)));setFuture('walls');
  $('#copyFuture').addEventListener('click',async()=>{const d=futures[selectedFuture];const t=`Нарисуйте свой интернет — Ctrl + Alt + Граница. Сценарий: ${d.title}. ${d.description}\nЭто условный сценарий, не прогноз. Источники: Freedom House, Internet Society Pulse, OONI.`;
    try{await navigator.clipboard.writeText(t);$('#copyFuture').firstChild.textContent='СКОПИРОВАНО ✓ '}catch(e){$('#copyFuture').firstChild.textContent='КОПИРОВАНИЕ НЕДОСТУПНО '};setTimeout(()=>{if($('#copyFuture'))$('#copyFuture').firstChild.textContent='СКОПИРОВАТЬ ВЫВОД '},2500);
  });
  function progress(){const d=document.documentElement;const length=d.scrollHeight-d.clientHeight;$('#progress').style.width=(length?Math.max(0,Math.min(100,d.scrollTop/length*100)):0)+'%';}
  window.addEventListener('scroll',progress,{passive:true});window.addEventListener('resize',progress);progress();
})();
