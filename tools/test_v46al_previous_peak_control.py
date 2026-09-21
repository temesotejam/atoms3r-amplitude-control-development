#!/usr/bin/env python3
from pathlib import Path
import json, subprocess, tempfile

R=Path(__file__).resolve().parents[1]
config=(R/'src/config.h').read_text()
runner=(R/'src/experiment_runner.cpp').read_text()
logger=(R/'src/psram_logger.cpp').read_text()
logger_h=(R/'src/psram_logger.h').read_text()
converter=(R/'tools/convert_rwlog_to_csv.py').read_text()
manifest=json.loads((R/'site/manifest.json').read_text())
site=(R/'site/index.html').read_text()

assert 'ATTITUDE_VALIDATION_REVISION[] = "v46aj_fixed_3ms_compensation_20260920"' in config
assert 'AMPLITUDE_CONTROL_OBSERVATION_REVISION[] = "v46ak_pre_input_state_observation_20260920"' in config
assert 'AMPLITUDE_CONTROL_REVISION[] = "v46al_previous_peak_active_control_20260921"' in config
assert manifest['version']=='0.46.37' and 'V46al' in manifest['name']
assert 'V46al / 0.46.37' in site

for token in (
 'ENERGY_CONTROL_AUTONOMOUS_CURRENT_MA = 300',
 'ENERGY_CONTROL_AUTONOMOUS_MAX_PULSE_MS = 100',
 'ENERGY_CONTROL_AUTONOMOUS_TIMING_COMPENSATION_US = 3000UL',
 'ENERGY_CONTROL_AUTONOMOUS_INTEGRAL_KI_MAS_PER_DEG = 0.10f',
):
    assert token in config, token

start=runner.index('// V46al previous-peak active control begin')
end=runner.index('// V46al previous-peak active control end',start)
block=runner[start:end]
assert 'previous_peak_control::evaluate(' in block
assert 'event.previous_peak_amplitude_deg' in block
assert 'event.zero_cross_abs_rate_dps' not in block
assert 'pre_input_' not in block
assert runner.index('const auto baseline = rate_baseline::evaluate(') < start
assert end < runner.index('event.passive_energy_j = energyControlPotentialJ',end)

for token in (
 'free_next_peak_before_previous_peak_correction_deg',
 'previous_peak_control_raw_correction_deg',
 'previous_peak_control_correction_deg',
 'previous_peak_control_reason',
 'previous_peak_control_applied',
 'previous_peak_control_clamped',
):
    assert token in logger_h and token in logger and token in converter

assert 'RWLOG_FORMAT_VERSION = 51' in logger
assert 'sizeof(LogSample) == 258' in (R/'src/log_types.h').read_text()

code=r'''
#include <cassert>
#include <cmath>
#include "previous_peak_control_correction.h"
int main(){
 using namespace previous_peak_control;
 auto early=evaluate(7.5f,8.0f,1,8.0f,9999);assert(!early.applied&&early.reason==BEFORE_ENABLE_TIME&&early.corrected_free_peak_deg==7.5f);
 auto other=evaluate(7.5f,8.0f,1,10.0f,15000);assert(!other.applied&&other.reason==TARGET_UNSUPPORTED);
 auto outside=evaluate(7.5f,6.0f,1,8.0f,15000);assert(!outside.applied&&outside.reason==PREVIOUS_PEAK_OUTSIDE_SUPPORT);
 auto plus=evaluate(7.5f,8.0f,1,8.0f,15000);assert(plus.applied&&std::fabs(plus.applied_correction_deg-0.591392151f)<1e-5f);
 auto minus=evaluate(8.5f,8.0f,-1,8.0f,15000);assert(minus.applied&&std::fabs(minus.applied_correction_deg+0.157912422f)<1e-5f);
 auto cap=evaluate(7.0f,7.19424f,1,8.0f,15000);assert(cap.applied&&cap.clamped&&std::fabs(cap.applied_correction_deg-0.70f)<1e-6f);
 auto bad=evaluate(NAN,8.0f,1,8.0f,15000);assert(!bad.applied&&bad.reason==INVALID_INPUT&&std::isnan(bad.corrected_free_peak_deg));
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'t.cpp').write_text(code);exe=p/'t'
 subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'src'),str(p/'t.cpp'),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
print('V46al previous-peak active control guards PASS')
