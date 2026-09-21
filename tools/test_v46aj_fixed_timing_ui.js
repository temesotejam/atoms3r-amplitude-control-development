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
for(const id of ['summary','startupInfo','errorInfo','energyTarget','energy','stop','rwlog','resumeDownload','clear'])get(id);
for(const removed of ['passive','shadowTarget','zero','target','abs','current','rate','targetError'])assert(!elements.has(removed),removed);
assert(html.includes('V46ao / 0.46.40')||html.includes('V46ap / 0.46.41'));
assert(html.includes('ZEROクロス補償3 ms固定'));
assert(!html.includes('Q1 direct next-peak shadow'));
assert(!html.includes('Passive release capture'));
assert(html.includes('href="/download/rwlog"'));
assert(html.includes('download onclick="return beginNativeRwlogDownload()"'));
assert(!source.includes("fetch('/download/rwlog'"));
assert(source.includes("if(refreshInFlight||downloading)return;"));
assert(source.includes('resumeUiAfterDownload'));

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
  assert(get('resumeDownload').hidden);

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

  // Native download begins directly; no fetch request is created by JS.
  const before=requests.length;
  assert.strictEqual(run('beginNativeRwlogDownload()'),true);
  assert.strictEqual(requests.length,before);
  assert.strictEqual(get('resumeDownload').hidden,false);
  assert.strictEqual(get('rwlog').textContent,'RWLOG download active');
  assert(isDisabled(get('rwlog')));

  // No status polling resumes by itself while the download hold is active.
  run('refresh()');assert.strictEqual(requests.length,before);

  // Explicit resume re-enables status traffic after the browser download is done.
  run('resumeUiAfterDownload()');
  assert.strictEqual(get('resumeDownload').hidden,true);
  const postDownloadStatus=requests.shift();assert(postDownloadStatus&&postDownloadStatus.url==='/status.json');
  await replyJson(postDownloadStatus,ready);
  assert(!isDisabled(get('rwlog')));

  console.log('V46ao minimal UI PASS: native RWLOG download retained; polling stays paused until explicit resume');
})().catch(error=>{console.error(error);process.exitCode=1;});
