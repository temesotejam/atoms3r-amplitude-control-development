// Execute the firmware's current minimal embedded UI with delayed network responses.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const page=fs.readFileSync(path.join(__dirname,'../src/web_ui.cpp'),'utf8');
const source=page.match(/<script>([\s\S]*?)<\/script>/)[1];
const html=page.split('<script>')[0],elements=new Map(),requests=[];
for(const match of html.matchAll(/<(\w+)\b([^>]*\bid="([^"]+)"[^>]*)>/g)){
  const tag=match[1].toUpperCase(),attrs=match[2],classes=new Set();
  if(/\bclass="[^"]*disabled[^"]*"/.test(attrs))classes.add('disabled');
  elements.set(match[3],{
    tagName:tag,disabled:/\bdisabled\b/.test(attrs),hidden:/\bhidden\b/.test(attrs),
    value:match[3]==='energyTarget'?'8':'',textContent:'',options:[],
    classList:{toggle(name,on){if(on)classes.add(name);else classes.delete(name);},contains(name){return classes.has(name);}}
  });
}
const get=id=>{assert(elements.has(id),'Missing DOM element: '+id);return elements.get(id);};
const isDisabled=e=>e.tagName==='A'?e.classList.contains('disabled'):e.disabled;
for(const id of ['summary','startupInfo','errorInfo','energyTarget','energy','stop','rwlog','clear'])get(id);
for(const removed of ['passive','shadowTarget','zero','target','abs','current','rate','targetError'])assert(!elements.has(removed),removed);
assert(html.includes('V46ao / 0.46.40')||html.includes('V46ap / 0.46.41')||html.includes('V46aq / 0.46.42')||html.includes('V46ar / 0.46.43'));
assert(html.includes('ZEROクロス補償3 ms固定'));
assert(!html.includes('Q1 direct next-peak shadow'));
assert(!html.includes('Passive release capture'));
assert(html.includes('href="/download/rwlog"'));
assert(html.includes('href="/download/rwlog" onclick="beginDownload()"'));
assert(!html.includes('download onclick="return beginNativeRwlogDownload()"'));
assert(!source.includes("fetch('/download/rwlog'"));
assert(source.includes("if(refreshInFlight||downloading)return;"));
assert(source.includes('function beginDownload()'));
assert(source.includes('setTimeout(()=>{downloading=false;refresh();},3000)'));
assert(!source.includes('beginNativeRwlogDownload'));
assert(!source.includes('resumeUiAfterDownload'));

const context=vm.createContext({
  document:{getElementById:get,activeElement:null},
  fetch:(url,options)=>new Promise(resolve=>requests.push({url,options,resolve})),
  setTimeout:()=>1,clearTimeout(){},setInterval(){},
  AbortController,alert(){},confirm:()=>true,console
});
const run=code=>vm.runInContext(code,context);
const tick=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
async function replyJson(req,data,ok=true){
  assert(req);req.resolve({ok,json:async()=>data,text:async()=>String(data),headers:{get:()=>null}});
  await tick();
}
const ready={
  state:'FINISHED',running:false,rwlog_downloadable:'yes',
  energy_control_autonomous_target_peak_deg:8,motor_cmd_mA:0,roller_actual_current_mA:0,remaining_s:0,
  startup:{guide_reason:'upright_ready',direction_error_deg:0.1,gyro_norm_dps:0.2,imu_error:'OK'}
};

(async()=>{
  vm.runInContext(source,context);
  assert(get('energy').disabled);
  await replyJson(requests.shift(),ready);
  assert(!get('energy').disabled);assert(!isDisabled(get('rwlog')));assert(get('stop').disabled);

  // Stale status must not unlock a concurrent start.
  run('refresh()');const stale=requests.shift();
  run('startEnergy()');const start=requests.shift();
  assert.strictEqual(start.url,'/start-energy-control-autonomous');
  assert.strictEqual(start.options.method,'POST');assert(get('energy').disabled);
  run('startEnergy()');assert.strictEqual(requests.length,0);
  await replyJson(stale,ready);assert(get('energy').disabled);
  await replyJson(start,'ok');
  const runningStatus=requests.shift();
  await replyJson(runningStatus,{running:true,state:'START_SYNC'});
  assert(get('energy').disabled);assert(!get('stop').disabled);

  // Emergency stop stays reachable.
  run('postStop()');const stop=requests.shift();assert.strictEqual(stop.url,'/stop');
  await replyJson(stop,'ok');await replyJson(requests.shift(),ready);
  assert(!get('energy').disabled);

  // V46aq restores the V46al plain-anchor download; JS creates no fetch request.
  const before=requests.length;
  assert.strictEqual(run('beginDownload()'),true);
  assert.strictEqual(requests.length,before);
  assert(isDisabled(get('rwlog')));
  run('refresh()');assert.strictEqual(requests.length,before);

  // The historical V46al behavior resumes normal UI polling after a short local hold.
  run('downloading=false;refresh()');
  const postDownloadStatus=requests.shift();assert(postDownloadStatus&&postDownloadStatus.url==='/status.json');
  await replyJson(postDownloadStatus,ready);
  assert(!isDisabled(get('rwlog')));

  console.log('V46ar minimal UI PASS: prepared RWLOG UI retains V46al plain-anchor download');
})().catch(error=>{console.error(error);process.exitCode=1;});
