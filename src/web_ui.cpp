#include "web_ui.h"

#include <WiFi.h>

#include "config.h"
#include "upright_pose_guide.h"
#include "run_control_worker.h"
extern RunControlWorker run_control;

static const char INDEX_HTML[] PROGMEM = R"HTML(
<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AtomS3R Amplitude Control</title>
<style>
:root{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#17202a;background:#f4f6f8}
*{box-sizing:border-box}
body{margin:0;background:#f4f6f8}
header{background:#202a35;color:#fff;padding:18px 18px 16px}
header h1{font-size:1.25rem;margin:0 0 4px}
header p{margin:0;color:#c9d1d9;font-size:.86rem}
main{max-width:680px;margin:0 auto;padding:14px}
.card{background:#fff;border:1px solid #d9dee5;border-radius:10px;padding:15px;margin-bottom:12px}
.card h2{font-size:1rem;margin:0 0 12px}
.state{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}
.state strong{font-size:1.08rem}
.pill{display:inline-block;padding:5px 9px;border-radius:999px;background:#eef2f6;font-size:.78rem;font-weight:700}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.metric{background:#f6f8fa;border-radius:8px;padding:10px}
.metric span{display:block;color:#66717d;font-size:.76rem;margin-bottom:3px}
.metric b{font-size:1.03rem}
.note{color:#66717d;font-size:.86rem;line-height:1.55;margin:8px 0 0}
.error{color:#b42318;font-size:.86rem;min-height:1.2em;margin:8px 0 0}
button,a.action{display:block;width:100%;border:0;border-radius:8px;padding:12px 14px;margin-top:10px;font-size:1rem;font-weight:700;text-align:center;text-decoration:none;cursor:pointer}
.primary{background:#1769e0;color:#fff}
.secondary,a.action{background:#eef2f6;color:#17202a}
.danger{background:#c4262e;color:#fff}
button:disabled,a.disabled{opacity:.4;pointer-events:none;cursor:default}
.row{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.fixed{padding:10px 12px;border-radius:8px;background:#f6f8fa;font-size:.9rem;line-height:1.55}
footer{text-align:center;color:#87919c;font-size:.76rem;padding:4px 0 14px}
@media(max-width:480px){.row{grid-template-columns:1fr}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
</head>
<body>
<header>
  <h1>AtomS3R Amplitude Control</h1>
  <p>V46ak / 0.46.36 — Web UI cleanup only</p>
</header>
<main>
  <div class="card">
    <div class="state">
      <div>
        <h2 style="margin-bottom:4px">現在の状態</h2>
        <strong id="stateText">接続中...</strong>
      </div>
      <span id="readyBadge" class="pill">--</span>
    </div>
    <div class="grid">
      <div class="metric"><span>MEKF角度</span><b id="angle">--</b></div>
      <div class="metric"><span>角速度</span><b id="rate">--</b></div>
      <div class="metric"><span>Motor command</span><b id="motor">--</b></div>
      <div class="metric"><span>実電流</span><b id="actual">--</b></div>
      <div class="metric"><span>バッテリー</span><b id="battery">--</b></div>
      <div class="metric"><span>残り時間</span><b id="remaining">--</b></div>
    </div>
    <p id="systemInfo" class="note">状態を取得しています。</p>
    <p id="errorInfo" class="error"></p>
  </div>

  <div class="card">
    <h2>8° 振幅制御測定</h2>
    <div class="fixed">
      目標ピーク <b>8.0°</b> ／ 測定 <b>30秒</b> ／ 遅延補償 <b>3 ms固定</b><br>
      測定中はWeb表示の更新を最小限にし、制御処理を優先します。
    </div>
    <button id="energy" class="primary" disabled onclick="startEnergy()">8°測定を開始</button>
    <button id="stop" class="danger" disabled onclick="postStop()">EMERGENCY STOP</button>
  </div>

  <div class="card">
    <h2>測定データ</h2>
    <p id="logInfo" class="note">RWLOGの状態を確認しています。</p>
    <a id="rwlog" class="action disabled" href="/download/rwlog" onclick="beginDownload()">RWLOGをダウンロード</a>
    <button id="clear" class="secondary" disabled onclick="postClear()">測定データを消去</button>
  </div>
</main>
<footer>V46ak control / estimator / RWLOG logic unchanged</footer>
<script>
let downloading=false,lastStatus={},displayFrozen=false,refreshInFlight=false,startPending=false,controlEpoch=0;
const energy=document.getElementById('energy');
const stop=document.getElementById('stop');
const clear=document.getElementById('clear');
const rwlog=document.getElementById('rwlog');

function lock(e,v){
  if(e.tagName==='A')e.classList.toggle('disabled',v);
  else e.disabled=v;
}
const num=v=>Number.isFinite(Number(v))?Number(v):null;
const angle=v=>num(v)===null?'--':num(v).toFixed(2)+'°';
const rate=v=>num(v)===null?'--':num(v).toFixed(2)+'°/s';
const current=v=>num(v)===null?'--':Math.round(num(v))+' mA';
const voltage=v=>num(v)===null?'--':(num(v)/1000).toFixed(2)+' V';

async function post(path){
  const r=await fetch(path,{method:'POST'});
  if(!r.ok)alert(await r.text());
  await refresh();
  return r.ok;
}

async function startEnergy(){
  if(startPending||energy.disabled)return;
  startPending=true;
  controlEpoch++;
  apply(lastStatus);
  try{
    const r=await fetch('/start-energy-control-autonomous',{method:'POST'});
    if(!r.ok)alert(await r.text());
    else{
      displayFrozen=true;
      applyFrozenState();
    }
  }catch(e){
    alert('開始結果を確認できません。状態の再取得を待ってください。');
  }finally{
    startPending=false;
    controlEpoch++;
    refresh();
  }
}

async function postStop(){
  displayFrozen=false;
  await post('/stop');
}

async function postClear(){
  if(confirm('現在の測定データを消去しますか？'))await post('/clear');
}

function beginDownload(){
  downloading=true;
  apply(lastStatus);
  setTimeout(()=>{
    downloading=false;
    refresh();
  },3000);
}

function stateLabel(j){
  if(j.running)return '測定中';
  if(j.state==='READY_TO_MEASURE')return '測定可能';
  if(j.state==='FINISHED')return '測定完了';
  if(j.state==='ESTOP')return '非常停止';
  return j.state||'UNKNOWN';
}

function apply(j){
  const running=!!j.running;
  const busy=downloading||!!j.downloading||startPending;
  const canStart=j.state==='READY_TO_MEASURE'||j.state==='FINISHED';

  lock(energy,busy||running||!canStart);
  lock(stop,!running);
  lock(clear,busy||running);
  lock(rwlog,busy||running||j.rwlog_downloadable!=='yes');

  document.getElementById('stateText').textContent=stateLabel(j);
  const badge=document.getElementById('readyBadge');
  badge.textContent=j.ready?'READY':'NOT READY';

  document.getElementById('angle').textContent=angle(j.pitch_mekf_control_deg);
  document.getElementById('rate').textContent=rate(j.physical_roll_rate_dps);
  document.getElementById('motor').textContent=current(j.motor_cmd_mA);
  document.getElementById('actual').textContent=current(j.roller_actual_current_mA);
  document.getElementById('battery').textContent=voltage(j.battery_mV);
  document.getElementById('remaining').textContent=num(j.remaining_s)===null?'--':num(j.remaining_s).toFixed(1)+' s';

  const imu=j.imu_ok?'IMU OK':'IMU NG';
  const roller=j.roller_ok?'Roller OK':'Roller NG';
  document.getElementById('systemInfo').textContent=
    imu+' / '+roller+' / 目標 '+Number(j.energy_control_autonomous_target_peak_deg||8).toFixed(1)+'° / 遅延補償 3 ms';
  document.getElementById('errorInfo').textContent=j.last_error||'';

  if(j.rwlog_downloadable==='yes'){
    document.getElementById('logInfo').textContent='RWLOG準備完了'+(j.download_filename?'：'+j.download_filename:'');
  }else if(running){
    document.getElementById('logInfo').textContent='測定中です。終了後にRWLOGを保存できます。';
  }else{
    document.getElementById('logInfo').textContent='保存できるRWLOGはまだありません。';
  }
}

function applyFrozenState(){
  [energy,clear,rwlog].forEach(x=>lock(x,true));
  lock(stop,false);
  document.getElementById('stateText').textContent='測定中';
  document.getElementById('readyBadge').textContent='RUNNING';
  document.getElementById('systemInfo').textContent='測定処理を優先しています。';
  document.getElementById('logInfo').textContent='測定終了後にRWLOGを保存できます。';
}

async function refresh(){
  if(refreshInFlight)return;
  refreshInFlight=true;
  const epoch=controlEpoch;
  let timer;
  try{
    const controller=new AbortController();
    timer=setTimeout(()=>controller.abort(),1500);
    const r=await fetch('/status.json',{cache:'no-store',signal:controller.signal});
    clearTimeout(timer);
    if(!r.ok)throw new Error('status_failed');
    const status=await r.json();
    if(epoch!==controlEpoch)return;
    lastStatus=status;
    if(lastStatus.running){
      displayFrozen=true;
      applyFrozenState();
      return;
    }
    if(displayFrozen)displayFrozen=false;
    apply(lastStatus);
  }catch(e){
    if(!displayFrozen){
      [energy,stop,clear,rwlog].forEach(x=>lock(x,true));
      document.getElementById('stateText').textContent='通信待ち';
    }
  }finally{
    if(timer)clearTimeout(timer);
    refreshInFlight=false;
  }
}

setInterval(refresh,1000);
refresh();
</script>
</body>
</html>
)HTML";

void WebUi::begin(WebServer& server, ExperimentRunner& runner, ImuManager& imu, Roller485Manager& roller, PsramLogger& logger) {
  server_ = &server;
  runner_ = &runner;
  imu_ = &imu;
  roller_ = &roller;
  logger_ = &logger;

  WiFi.mode(WIFI_AP);
  WiFi.softAP(Config::AP_SSID, Config::AP_PASS, Config::AP_CHANNEL);

  server_->on("/", HTTP_GET, [this]() { handleRoot(); });
  server_->on("/status.json", HTTP_GET, [this]() { handleStatus(); });
  server_->on("/imu-acquisition.json", HTTP_GET, [this]() {
    if (run_control.active() || runner_->running()) { server_->send(409, "text/plain", "read_after_run"); return; }
    server_->sendHeader("Cache-Control", "no-store");
    server_->send(200, "application/json", imu_->acquisitionDiagnosticsJson());
  });
  server_->on("/start-passive", HTTP_POST, [this]() { handleStartPassive(); });
  server_->on("/start-energy-control-v0", HTTP_POST, [this]() { handleStartEnergyControlV0(); });
  server_->on("/start-energy-control-autonomous", HTTP_POST, [this]() { handleStartEnergyControlAutonomous(); });
  server_->on("/energy-control-autonomous/target", HTTP_POST, [this]() { handleSetEnergyControlAutonomousTarget(); });
  server_->on("/stop", HTTP_POST, [this]() { handleStop(); });
  server_->on("/clear", HTTP_POST, [this]() { handleClear(); });
  server_->on("/settings", HTTP_POST, [this]() { handleSettings(); });
  server_->on("/current-roll/zero", HTTP_POST, [this]() { handleCurrentRollZero(); });
  server_->on("/current-roll/target", HTTP_POST, [this]() { handleSetCurrentRollTarget(); });
  server_->on("/q1-shadow/target", HTTP_POST, [this]() { handleSetQ1ShadowTargetPeakAbs(); });
  server_->on("/download/rwlog", HTTP_GET, [this]() { handleRwLog(); });
  server_->enableDelay(false);  // Empty HTTP polls must not add sleeps to idle acquisition.
  server_->begin();
}

void WebUi::update() {
  if (server_) server_->handleClient();
}

void WebUi::handleRoot() {
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  if (run_control.active() || runner_->running()) { server_->send(409, "text/plain", "read_after_run"); return; }
  server_->sendHeader("Cache-Control", "no-store, no-cache, must-revalidate");
  server_->sendHeader("Pragma", "no-cache");
  server_->send_P(200, "text/html; charset=utf-8", INDEX_HTML);
}

void WebUi::handleStatus() {
  if (run_control.active()) {
    // Copy only immutable POD status; do not read runner/logger/imu.reading
    // while the higher-priority worker owns them. No network I/O in a lock.
    const RunControlSnapshot st = run_control.snapshot();
    char body[192];
    snprintf(body, sizeof(body),
        "{\"running\":%s,\"state\":\"%s\",\"motor_cmd_mA\":%d,\"roller_actual_current_mA\":%d,\"remaining_ms\":%lu}",
        st.running ? "true" : "false", st.state_name,
        static_cast<int>(st.motor_cmd_mA), static_cast<int>(st.actual_current_mA),
        static_cast<unsigned long>(st.remaining_ms));
    server_->send(200, "application/json", body);
    return;
  }
  server_->send(200, "application/json", statusJson());
}

void WebUi::handleStartPassive() {
  if (!run_control.ready()) { server_->send(503, "text/plain", "run_control_worker_not_ready"); return; }
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  if (logger_->downloading()) {
    server_->send(409, "text/plain", "download_in_progress");
    return;
  }
  const bool ok = runner_->startPassiveCapture();
  server_->send(ok ? 200 : 409, "text/plain", ok ? "passive_capture_started" : "start_failed");
}

void WebUi::handleStartEnergyControlV0() {
  if (!run_control.ready()) { server_->send(503, "text/plain", "run_control_worker_not_ready"); return; }
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  if (logger_->downloading()) {
    server_->send(409, "text/plain", "download_in_progress");
    return;
  }
  const bool ok = runner_->startEnergyControlV0Capture();
  server_->send(ok ? 200 : 409, "text/plain",
                ok ? "energy_control_v0_started" : runner_->status().last_error);
}

void WebUi::handleStartEnergyControlAutonomous() {
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  if (logger_->downloading()) { server_->send(409, "text/plain", "download_in_progress"); return; }
  if (!run_control.ready()) { server_->send(503, "text/plain", "run_control_worker_not_ready"); return; }
  if (server_->hasArg("timing_ms")) {
    // Old cached pages must refresh instead of silently requesting another delay.
    server_->send(400, "text/plain", "timing_selection_removed_fixed_3ms_reload_page"); return;
  }
  // Refresh from the idle mailbox before the unchanged physical start gate.
  // The run boundary is established by main AFTER this HTTP response returns.
  imu_->update();
  const bool ok = runner_->startEnergyControlAutonomousCapture();
  server_->send(ok ? 200 : 409, "text/plain", ok ? "energy_control_autonomous_started" : runner_->status().last_error);
}

void WebUi::handleSetEnergyControlAutonomousTarget() {
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  if (!server_->hasArg("deg")) { server_->send(400, "text/plain", "target_deg_required"); return; }
  if (runner_->running()) { server_->send(409, "text/plain", "running"); return; }
  const bool ok = runner_->setEnergyControlAutonomousTarget(server_->arg("deg").toFloat());
  server_->send(ok ? 200 : 400, "text/plain", ok ? "energy_target_set" : runner_->status().last_error);
}

void WebUi::handleStartQIdent() {
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  server_->send(409, "text/plain", "q_ident_frozen_use_energy_control_v0");
}void WebUi::handleStart() {
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  if (logger_->downloading()) {
    server_->send(409, "text/plain", "download_in_progress");
    return;
  }
  if (!server_->hasArg("trial")) {
    server_->send(400, "text/plain", "trial_required");
    return;
  }
  const uint8_t trial_number = static_cast<uint8_t>(server_->arg("trial").toInt());
  const bool ok = runner_->startSingleTrialTest(trial_number);
  server_->send(ok ? 200 : 409, "text/plain", ok ? "started" : "start_failed");
}

void WebUi::handleStartZeroCross() {
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  if (logger_->downloading()) {
    server_->send(409, "text/plain", "download_in_progress");
    return;
  }
  if (!server_->hasArg("pulse_width_ms")) {
    server_->send(400, "text/plain", "pulse_width_ms_required");
    return;
  }
  const int16_t current_mA = Config::ZERO_CROSS_OPERATING_CURRENT_MA;
  const int pulse_width_ms = server_->arg("pulse_width_ms").toInt();
  const bool pulse_ok = pulse_width_ms >= Config::ZERO_CROSS_TIME_SWEEP_MIN_PULSE_MS &&
                        pulse_width_ms <= Config::ZERO_CROSS_TIME_SWEEP_MAX_PULSE_MS;
  if (!pulse_ok) {
    server_->send(400, "text/plain", "invalid_zero_cross_condition");
    return;
  }
  const bool ok = runner_->startZeroCrossTest(static_cast<int16_t>(current_mA),
                                              static_cast<uint16_t>(pulse_width_ms));
  server_->send(ok ? 200 : 409, "text/plain", ok ? "zero_cross_started" : "start_failed");
}
void WebUi::handleStartIdentification() {
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  if (logger_->downloading()) { server_->send(409, "text/plain", "download_in_progress"); return; }
  const bool ok = runner_->startZeroCrossIdentificationTest();
  server_->send(ok ? 200 : 409, "text/plain", ok ? "validation_started" : "start_failed");
}

void WebUi::handleStartControl() {
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  if (logger_->downloading()) { server_->send(409, "text/plain", "download_in_progress"); return; }
  if (!server_->hasArg("target_peak_deg")) { server_->send(400, "text/plain", "target_peak_deg_required"); return; }
  const float target_peak_deg = server_->arg("target_peak_deg").toFloat();
  const int schedule_arg = server_->hasArg("q_probe_schedule_id") ?
      server_->arg("q_probe_schedule_id").toInt() : Config::ZERO_CROSS_CALIBRATION_Q_PROBE_SCHEDULE_A;
  if (schedule_arg < Config::ZERO_CROSS_CALIBRATION_Q_PROBE_SCHEDULE_A ||
      schedule_arg >= Config::ZERO_CROSS_CALIBRATION_Q_PROBE_SCHEDULE_COUNT) {
    server_->send(400, "text/plain", "invalid_q_probe_schedule");
    return;
  }
  const bool ok = runner_->startZeroCrossControlTest(
      target_peak_deg, static_cast<uint8_t>(schedule_arg));
  server_->send(ok ? 200 : 409, "text/plain", ok ? "control_started" : "start_failed");
}
void WebUi::handleZero() {
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  if (runner_->running()) {
    server_->send(409, "text/plain", "running");
    return;
  }
  runner_->zeroAngleNow();
  server_->send(200, "text/plain", "zeroed");
}

void WebUi::handleCurrentRollZero() {
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  const bool ok = runner_->zeroCurrentRollDisplay();
  server_->send(ok ? 200 : 409, "text/plain", ok ? "current_roll_zeroed" : runner_->status().last_error);
}

void WebUi::handleSetCurrentRollTarget() {
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  if (!server_->hasArg("deg")) {
    server_->send(400, "text/plain", "target_deg_required");
    return;
  }
  if (runner_->running()) {
    server_->send(409, "text/plain", "running");
    return;
  }
  const bool ok = runner_->setCurrentRollTarget(server_->arg("deg").toFloat());
  server_->send(ok ? 200 : 400, "text/plain", ok ? "current_roll_target_set" : runner_->status().last_error);
}

void WebUi::handleSetQ1ShadowTargetPeakAbs() {
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  if (!server_->hasArg("deg")) {
    server_->send(400, "text/plain", "target_deg_required");
    return;
  }
  if (runner_->running()) {
    server_->send(409, "text/plain", "running");
    return;
  }
  const bool ok = runner_->setQ1ShadowTargetPeakAbs(server_->arg("deg").toFloat());
  server_->send(ok ? 200 : 400, "text/plain", ok ? "q1_shadow_target_set" : runner_->status().last_error);
}

void WebUi::handleStop() {
  if (run_control.requestStop()) {
    server_->send(202, "text/plain", "stop_requested");
    return;
  }
  runner_->requestEmergencyStop("web_estop");
  server_->send(200, "text/plain", "stopped");
}

void WebUi::handleClear() {
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  if (runner_->running() || logger_->downloading()) {
    server_->send(409, "text/plain", "busy");
    return;
  }
  runner_->clearFinishedOrEstop();
  server_->send(200, "text/plain", "cleared");
}

void WebUi::handleSettings() {
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  if (runner_->running()) {
    server_->send(409, "text/plain", "running");
    return;
  }
  const int16_t current_mA = server_->hasArg("current_mA") ? static_cast<int16_t>(server_->arg("current_mA").toInt())
                                                           : Config::DEFAULT_INPUT_CURRENT_MA;
  const uint16_t pulse_width_ms =
      server_->hasArg("pulse_width_ms") ? static_cast<uint16_t>(server_->arg("pulse_width_ms").toInt())
                                        : Config::DEFAULT_PULSE_WIDTH_MS;
  const uint16_t input_interval_ms =
      server_->hasArg("input_interval_ms") ? static_cast<uint16_t>(server_->arg("input_interval_ms").toInt())
                                           : Config::DEFAULT_INPUT_INTERVAL_MS;
  runner_->setInputSettings(current_mA, pulse_width_ms, input_interval_ms);
  server_->send(200, "text/plain", "settings_applied");
}

void WebUi::handleRwLog() {
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  if (runner_->running()) {
    server_->send(409, "text/plain", "measurement_running");
    return;
  }
  logger_->streamRwLog(*server_);
}

void WebUi::appendJsonUint64(String& json, uint64_t value) {
  char buf[24];
  snprintf(buf, sizeof(buf), "%llu", static_cast<unsigned long long>(value));
  json += buf;
}

String WebUi::statusJson() const {
  const auto& st = runner_->status();
  const RollerTelemetry roller = roller_->telemetrySnapshot();
  char filename[72];
  logger_->downloadFilename(filename, sizeof(filename));
  String json;
  json.reserve(3200);
  json += "{";
  json += "\"running\":" + String(runner_->running() ? "true" : "false");
  json += ",\"downloading\":" + String(logger_->downloading() ? "true" : "false");
  json += ",\"zero_cross_mode\":" + String(runner_->zeroCrossMode() ? "true" : "false");
  json += ",\"identification_mode\":" + String(runner_->identificationMode() ? "true" : "false");
  json += ",\"q_run_mode\":\"" + String(runner_->qRunModeName()) + "\"";
  json += ",\"passive_capture_mode\":" + String(runner_->passiveCaptureMode() ? "true" : "false");
  json += ",\"q_ident_mode\":" + String(runner_->qIdentMode() ? "true" : "false");
  json += ",\"energy_control_v0_mode\":" + String(runner_->energyControlV0Mode() ? "true" : "false");
  json += ",\"energy_control_autonomous_mode\":" + String(runner_->energyControlAutonomousMode() ? "true" : "false");
  json += ",\"energy_control_autonomous_target_peak_deg\":" + String(runner_->energyControlAutonomousTargetPeakDeg(), 2);
  json += ",\"autonomous_timing_compensation_ms\":" + String(Config::ENERGY_CONTROL_AUTONOMOUS_TIMING_COMPENSATION_US / 1000);
  json += ",\"autonomous_timing_compensation_selectable\":false";
  json += ",\"energy_control_autonomous_phase\":\"" + String(runner_->energyControlAutonomousPhaseName()) + "\"";
  json += ",\"energy_control_v0_target_peak_deg\":" + String(Config::ENERGY_CONTROL_V0_TARGET_PEAK_DEG, 2);
  json += ",\"q_ident_armed\":" + String(runner_->qIdentArmed() ? "true" : "false");
  json += ",\"q_ident_run_schedule_id\":" + String(runner_->qIdentRunScheduleId());
  json += ",\"q_ident_plus_occurrences\":" + String(runner_->qIdentPlusOccurrenceCount());
  json += ",\"q_ident_minus_occurrences\":" + String(runner_->qIdentMinusOccurrenceCount());
  json += ",\"passive_static_window_s\":" + String(static_cast<float>(Config::PASSIVE_STATIC_WINDOW_MS) / 1000.0f, 1);
  json += ",\"q_probe_schedule_id\":" + String(runner_->qProbeScheduleId());
  json += ",\"q_probe_schedule_name\":\"" + String(runner_->qProbeScheduleName()) + "\"";
  json += ",\"q_control_target_peak_deg\":" + String(runner_->controlTargetPeakDeg(), 2);
  json += ",\"zero_cross_fixed_current_mA\":" + String(runner_->zeroCrossFixedCurrentMa());
  json += ",\"state\":\"" + String(runner_->stateName()) + "\"";
  json += ",\"state_id\":" + String(static_cast<uint8_t>(st.state));
  json += ",\"boot_elapsed_s\":" + String(static_cast<float>(st.boot_elapsed_ms) / 1000.0f, 1);
  json += ",\"measure_elapsed_s\":" + String(static_cast<float>(st.measure_elapsed_ms) / 1000.0f, 1);
  json += ",\"remaining_s\":" + String(static_cast<float>(st.remaining_ms) / 1000.0f, 1);
  json += ",\"trial_index\":" + String(st.trial_index);
  json += ",\"trial_count\":" + String(st.trial_count);
  json += ",\"trial_elapsed_s\":" + String(static_cast<float>(st.trial_elapsed_ms) / 1000.0f, 1);
  json += ",\"trial_duration_s\":" + String(static_cast<float>(st.trial_duration_ms) / 1000.0f, 1);
  json += ",\"pulse_id\":" + String(st.pulse_id);
  json += ",\"pulse_active\":" + String(st.pulse_active ? "true" : "false");
  json += ",\"pulse_direction\":" + String(st.pulse_direction);
  json += ",\"current_mA_setting\":" + String(st.current_mA_setting);
  json += ",\"pulse_width_ms_setting\":" + String(st.pulse_width_ms_setting);
  json += ",\"input_interval_ms\":" + String(st.input_interval_ms);
  json += ",\"predicted_beta_min\":" + String(st.predicted_beta_min, 5);
  json += ",\"beta_hold_after_input_ms\":" + String(st.beta_hold_after_input_ms_setting);
  json += ",\"beta_recovery_tau_s_setting\":" + String(st.beta_recovery_tau_s_setting, 3);
  json += ",\"beta_model_vbat_mV\":" + String(st.beta_model_vbat_mV);
  json += ",\"predicted_i_goal_mA\":" + String(st.predicted_i_goal_mA);
  json += ",\"predicted_peak_current_mA\":" + String(st.predicted_peak_current_mA);
  json += ",\"beta_model_vbat_status\":" + String(st.beta_model_vbat_status);
  json += ",\"led_state\":" + String(st.led_state ? "true" : "false");
  json += ",\"sync_event_id\":" + String(st.sync_event_id);
  json += ",\"led_sync_pattern_id\":\"" + String(Config::LED_SYNC_PATTERN_ID) + "\"";
  json += ",\"gyro_bias_x_dps\":" + String(st.gyro_bias_x_dps, 5);
  json += ",\"gyro_bias_y_dps\":" + String(st.gyro_bias_y_dps, 5);
  json += ",\"gyro_bias_z_dps\":" + String(st.gyro_bias_z_dps, 5);
  json += ",\"attitude_filter_adopted\":\"MEKF\"";
  json += ",\"pitch_mekf_control_deg\":" + String(st.pitch_mekf_deg, 3);
  json += ",\"pitch_mekf_abs_deg\":" + String(st.pitch_mekf_abs_deg, 3);
  json += ",\"pitch_mekf_predicted_abs_deg\":" + String(st.pitch_mekf_predicted_abs_deg, 3);
  json += ",\"pitch_mekf_detector_relative_deg\":" + String(st.pitch_mekf_detector_relative_deg, 3);
  json += ",\"mekf_detector_zero_predicted_abs_deg\":" + String(st.mekf_detector_zero_predicted_abs_deg, 3);
  json += ",\"mekf_detector_zero_sample_us\":" + String(st.mekf_detector_zero_sample_us);
  json += ",\"mekf_prediction_horizon_us\":" + String(st.mekf_prediction_horizon_us);
  json += ",\"pitch_madgwick_dynamic_abs_deg\":" + String(st.pitch_madgwick_dynamic_abs_deg, 3);
  json += ",\"mekf_accel_confidence\":" + String(st.mekf_accel_confidence, 4);
  json += ",\"mekf_accel_residual_deg\":" + String(st.mekf_accel_residual_deg, 3);
  json += ",\"mekf_accel_used\":" + String(st.mekf_accel_used ? "true" : "false");
  json += ",\"pitch_madgwick_beta1_raw_deg\":" + String(st.pitch_madgwick_beta1_raw_deg, 3);
  json += ",\"pitch_madgwick_dynamic_raw_deg\":" + String(st.pitch_madgwick_dynamic_raw_deg, 3);
  json += ",\"pitch_madgwick_beta1_bias_deg\":" + String(st.pitch_madgwick_beta1_bias_deg, 3);
  json += ",\"pitch_madgwick_dynamic_bias_deg\":" + String(st.pitch_madgwick_dynamic_bias_deg, 3);
  for (uint8_t i = 0; i < Config::DYNAMIC_BETA_COUNT; ++i) {
    json += ",\"pitch_beta_series_" + String(i) + "\":" + String(st.pitch_dynamic_beta_deg[i], 3);
    json += ",\"beta_applied_series_" + String(i) + "\":" + String(st.beta_smooth_series[i], 5);
  }
  json += ",\"pitch_gyro_raw_deg\":" + String(st.pitch_gyro_raw_deg, 3);
  json += ",\"pitch_gyro_bias_corrected_deg\":" + String(st.pitch_gyro_bias_corrected_deg, 3);
  json += ",\"pitch_accel_only_deg\":" + String(st.pitch_accel_only_deg, 3);
  json += ",\"gyro_pitch_rate_dps\":" + String(st.gyro_pitch_rate_dps, 4);
  json += ",\"beta_target\":" + String(st.beta_target, 5);
  json += ",\"beta_smooth\":" + String(st.beta_smooth, 5);
  json += ",\"ax_g\":" + String(st.ax_g, 4);
  json += ",\"ay_g\":" + String(st.ay_g, 4);
  json += ",\"az_g\":" + String(st.az_g, 4);
  json += ",\"gx_dps\":" + String(st.gx_dps, 4);
  json += ",\"gy_dps\":" + String(st.gy_dps, 4);
  json += ",\"gz_dps\":" + String(st.gz_dps, 4);
  json += ",\"acc_norm_g\":" + String(st.acc_norm_g, 4);
  json += ",\"physical_roll_candidate_deg\":" + String(st.physical_roll_candidate_deg, 3);
  json += ",\"physical_roll_abs_deg\":" + String(st.physical_roll_abs_deg, 3);
  json += ",\"current_roll_deg\":" + String(st.current_roll_deg, 3);
  json += ",\"physical_roll_rate_raw_dps\":" + String(st.physical_roll_rate_raw_dps, 4);
  json += ",\"physical_roll_rate_dps\":" + String(st.physical_roll_rate_dps, 4);
  json += ",\"display_zero_offset_deg\":" + String(st.display_zero_offset_deg, 3);
  json += ",\"target_roll_deg\":" + String(st.target_roll_deg, 3);
  json += ",\"q1_shadow_target_peak_abs_deg\":" + String(runner_->q1ShadowTargetPeakAbsDeg(), 3);
  json += ",\"q1_shadow_active_target_peak_abs_deg\":" + String(runner_->q1ShadowActiveTargetPeakAbsDeg(), 3);  json += ",\"target_error_deg\":" + String(st.target_error_deg, 3);
  json += ",\"static_confirmed\":" + String(st.static_confirmed ? "true" : "false");
  json += ",\"ready\":" + String(st.ready ? "true" : "false");
  json += ",\"static_rate_threshold_dps\":" + String(Config::STATIC_RATE_THRESHOLD_DPS, 3);
  json += ",\"static_hold_time_ms\":" + String(Config::STATIC_HOLD_TIME_MS);
  json += ",\"target_tolerance_deg\":" + String(Config::TARGET_TOLERANCE_DEG, 3);
  json += ",\"motor_cmd_mA\":" + String(st.motor_cmd_mA);
  json += ",\"sample_count\":" + String(logger_->sampleCount());
  json += ",\"psram_usage_percent\":" + String(logger_->usagePercent());
  json += ",\"log_capacity\":" + String(logger_->sampleCapacity());
  json += ",\"rwlog_downloadable\":\"" + String(logger_->rwlogDownloadable() ? "yes" : "no") + "\"";
  json += ",\"download_filename\":\"" + String(filename) + "\"";
  json += ",\"run_id\":" + String(logger_->currentRunId());
  json += ",\"run_start_us\":";
  appendJsonUint64(json, logger_->runStartUs());
  json += ",\"last_measurement_done\":\"" + String(logger_->lastMeasurementDone() ? "yes" : "no") + "\"";
  json += ",\"calibration_sample_count\":" + String(st.calibration_sample_count);
  json += ",\"startup\":" + imu_->startupDiagnosticsJson();
  json += ",\"imu_ok\":" + String(imu_->ok() ? "true" : "false");
  json += ",\"roller_ok\":" + String(roller_->ok() ? "true" : "false");
  json += ",\"roller_actual_current_mA\":" + String(roller.actual_current_mA);
  json += ",\"roller_io_task_running\":" + String(roller.io_task_running ? "true" : "false");
  json += ",\"roller_io_task_ready\":" + String(roller.io_task_ready ? "true" : "false");
  json += ",\"roller_io_task_init_failed\":" + String(roller.io_task_init_failed ? "true" : "false");
  json += ",\"roller_io_init_attempt_count\":" + String(roller.io_init_attempt_count);
  json += ",\"roller_io_recovery_count\":" + String(roller.io_recovery_count);
  json += ",\"roller_command_latency_us\":" + String(roller.last_command_latency_us);
  json += ",\"roller_command_latency_max_us\":" + String(roller.max_command_latency_us);
  json += ",\"battery_mV\":" + String(roller.battery_mV);
  json += ",\"loop_dt_us\":" + String(st.loop_dt_us);
  json += ",\"log_dt_us\":" + String(st.log_dt_us);
  json += ",\"imu_dt_us\":" + String(imu_->reading().update_dt_us);
  json += ",\"last_error\":\"" + String(st.last_error && st.last_error[0] ? st.last_error : logger_->lastError()) + "\"";
  json += "}";

  // Arduino String renders non-finite floats as `nan`/`inf`, which is not valid
  // JSON. V46 intentionally uses NaN for comparison series that are disabled
  // during the autonomous run, so normalize those tokens before sending the
  // status document. This lets the browser keep polling while its visible
  // display remains frozen by design, then resume immediately at FINISHED.
  json.replace(":-Infinity", ":null");
  json.replace(":Infinity", ":null");
  json.replace(":-inf", ":null");
  json.replace(":inf", ":null");
  json.replace(":NaN", ":null");
  json.replace(":nan", ":null");
  return json;
}
