// Execute the firmware's current minimal embedded UI with delayed network responses.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const page=fs.readFileSync(path.join(__dirname,'../src/web_ui.cpp'),'utf8');
const source=page.match(/<script>([\s\S]*?)<\/script>/)[1];
const html=page.split('<script>')[0],elements=new Map(),requests=[],downloads=[];
for(const match of html.matchAll(/<(\w+)\b([^>]*\bid="([^"]+)"[^>]*)>/g)){
  const tag=match[1].toUpperCase(),attrs=match[2];
  elements.set(match[3],{tagName:tag,disabled:/\bdisabled\b/.test(attrs),value:match[3]==='energyTarget'?'8':'',textContent:'',options:[]});
}
const get=id=>{assert(elements.has(id),'Missing DOM element: '+id);return elements.get(id);};
for(const id of ['summary','startupInfo','errorInfo','energyTarget','energy','stop','rwlog','clear'])get(id);
for(const removed of ['passive','shadowTarget','zero','target','abs','current','rate','targetError'])assert(!elements.has(removed),removed);
assert(html.includes('V46am / 0.46.38'));
assert(html.includes('ZEROクロス補償3 ms固定'));
assert(!html.includes('Q1 direct next-peak shadow'));
assert(!html.includes('Passive release capture'));
assert(!source.includes('setTimingCompensation'));assert(!source.includes('timing_ms'));
assert(!source.includes('beginDownload'));
assert(source.includes("if(refreshInFlight||downloading)return;"));

const body={appendChild(){}};
const documentMock={
  getElementById:get,activeElement:null,body,
  createElement:()=>({href:'',download:'',click(){downloads.push(this.download);},remove(){}})
};
const URLMock={createObjectURL:()=> 'blob:test',revokeObjectURL(){}};
const context=vm.createContext({
  document:documentMock,
  fetch:(url,options)=>new Promise(resolve=>requests.push({url,options,resolve})),
  setTimeout:(fn)=>{fn();return 1;},clearTimeout(){},setInterval(){},
  AbortController,URL:URLMock,alert(){},confirm:()=>true,console
});
const run=code=>vm.runInContext(code,context);
const tick=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
async function replyJson(req,data,ok=true){
  assert(req);req.resolve({ok,json:async()=>data,text:async()=>String(data),headers:{get:()=>null}});
  await tick();
}
async function replyDownload(req,bytes=1024,filename='test.rwlog'){
  assert(req);assert.strictEqual(req.url,'/download/rwlog');
  req.resolve({
    ok:true,
    text:async()=>'',json:async()=>({}),
    blob:async()=>({size:bytes}),
    headers:{get:name=>name==='Content-Disposition'?('attachment; filename="'+filename+'"'):null}
  });
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
  assert(!get('energy').disabled);assert(!get('rwlog').disabled);assert(get('stop').disabled);

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

  // Download owns the connection: status refresh is suppressed until blob completion.
  run('downloadRwLog()');const dl=requests.shift();assert(dl);
  const before=requests.length;run('refresh()');assert.strictEqual(requests.length,before);
  await replyDownload(dl,4096,'energy_control_test.rwlog');
  assert.deepStrictEqual(downloads,['energy_control_test.rwlog']);
  const postDownloadStatus=requests.shift();assert(postDownloadStatus&&postDownloadStatus.url==='/status.json');
  await replyJson(postDownloadStatus,ready);
  assert(!get('rwlog').disabled);

  console.log('V46am minimal UI PASS: current controls only; start race guard; ESTOP; download owns connection; status resumes after completion');
})().catch(error=>{console.error(error);process.exitCode=1;});
