#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import math
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

config = (ROOT / "src/config.h").read_text(encoding="utf-8")
roller_h = (ROOT / "src/roller485_manager.h").read_text(encoding="utf-8")
roller = (ROOT / "src/roller485_manager.cpp").read_text(encoding="utf-8")
runner_h = (ROOT / "src/experiment_runner.h").read_text(encoding="utf-8")
runner = (ROOT / "src/experiment_runner.cpp").read_text(encoding="utf-8")
logger_h = (ROOT / "src/psram_logger.h").read_text(encoding="utf-8")
logger = (ROOT / "src/psram_logger.cpp").read_text(encoding="utf-8")

# Frozen estimator/timing identity must remain unchanged.
assert 'ATTITUDE_VALIDATION_REVISION[] = "v46aj_fixed_3ms_compensation_20260920"' in config
assert 'ENERGY_CONTROL_AUTONOMOUS_TIMING_COMPENSATION_US = 3000UL' in config
assert 'ENERGY_CONTROL_AUTONOMOUS_INTEGRAL_KI_MAS_PER_DEG = 0.10f' in config
assert 'AMPLITUDE_CONTROL_DEVELOPMENT_REVISION[] = "v46ak_repeatability_observation_20260920"' in config

# Official Roller speed readback is observational only.
assert 'REG_SPEED_READBACK = 0x60' in roller
assert 'if (command_mA_ == 0) readSpeedFresh(false);' in roller
stop_region = roller[roller.index('bool Roller485Manager::applyCurrentMa'):
                     roller.index('RollerTelemetry Roller485Manager::telemetrySnapshot')]
assert stop_region.index('endCurrentAuditPulse();') < stop_region.index('readSpeedFresh(true)')
speed_region = roller[roller.index('bool Roller485Manager::readSpeedFresh'):
                      roller.index('void Roller485Manager::recordFreshCurrent')]
assert 'recordIo(' not in speed_region
assert 'roller_ok' not in speed_region
assert 'wheel_speed_rpm = static_cast<float>(speed_raw) / 100.0f' in speed_region

# No extra Roller snapshot/I2C read is introduced inside the accepted zero-cross decision.
zero_region = runner[runner.index('void ExperimentRunner::updateEnergyControlAutonomousAtZeroCross'):
                     runner.index('void ExperimentRunner::runEnergyControlAutonomousSolverShadow')]
assert 'telemetrySnapshot()' not in zero_region
assert 'readSpeedFresh' not in zero_region
assert 'pre_wheel_speed_rpm' in zero_region
assert 'pre_measured_current_mA' in zero_region

# Observation fields are logged, not used to calculate the selected command.
for forbidden in (
    'selected_q_mA_s = event.pre_',
    'corrected_q_target_mA_s = event.pre_',
    'fast_signed_target_current_mA = event.pre_',
    'baseline = rate_baseline::evaluate(event.pre_',
):
    assert forbidden not in zero_region

assert 'source_zero_cross_event_index' in logger_h
assert 'post_pulse_wheel_speed_rpm' in logger_h
assert 'pre_wheel_speed_age_us' in logger_h
assert 'pre_current_age_us' in logger_h
assert 'v46ak_repeatability_observation_policy' in logger

zero_struct = logger_h.split(
    'struct EnergyControlAutonomousZeroCrossEvent', 1
)[1].split('};', 1)[0]
for field in (
    'pre_measured_current_mA',
    'pre_current_sample_time_us',
    'pre_current_age_us',
    'pre_current_sequence',
    'pre_current_valid',
    'pre_wheel_speed_rpm',
    'pre_wheel_speed_sample_time_us',
    'pre_wheel_speed_age_us',
    'pre_wheel_speed_sequence',
    'pre_wheel_speed_valid',
):
    assert field in zero_struct, field

# Converter must produce a one-row input -> next-peak joined table.
spec = importlib.util.spec_from_file_location(
    "rwlog_converter", ROOT / "tools/convert_rwlog_to_csv.py"
)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

metadata = {
    "energy_control_autonomous_zero_cross_events": [{
        "event_index": 7,
        "zero_cross_time_ms": 1234,
        "zero_cross_abs_rate_dps": 61.2,
        "physical_next_peak_side": 1,
        "previous_peak_amplitude_deg": 7.8,
        "target_peak_deg": 8.0,
        "predicted_next_peak_amplitude_deg": 8.1,
        "q_command_mA_s": 0.8,
        "q_effective_pred_mA_s": 0.79,
        "q_command_direction": 1,
        "vbat_mV": 7600,
        "i0_estimated_mA": -12.0,
        "pre_measured_current_mA": -18.0,
        "pre_current_age_us": 4000,
        "pre_current_valid": True,
        "pre_wheel_speed_rpm": -820.0,
        "pre_wheel_speed_age_us": 6000,
        "pre_wheel_speed_valid": True,
        "pulse_width_ms": 20,
        "output_executed": True,
    }],
    "energy_control_autonomous_peak_events": [{
        "peak_index": 8,
        "peak_time_ms": 1450,
        "peak_amplitude_deg": 8.24,
        "pending_command_matched": True,
        "source_zero_cross_event_index": 7,
        "q_meas_observed_mA_s": 0.77,
        "q_meas_observed_valid": True,
        "post_pulse_wheel_speed_rpm": -610.0,
        "post_pulse_wheel_speed_valid": True,
        "post_pulse_wheel_speed_capture_delay_us": 850,
    }],
}

with tempfile.TemporaryDirectory() as td:
    out = Path(td)
    count = module.write_energy_control_repeatability_events(metadata, out)
    assert count == 1
    with (out / "energy_control_repeatability_events.csv").open(
        newline="", encoding="utf-8"
    ) as f:
        row = next(csv.DictReader(f))
    assert int(row["event_index"]) == 7
    assert math.isclose(float(row["prediction_error_deg"]), 0.14, abs_tol=1e-9)
    assert math.isclose(float(row["pre_current_minus_i0_mA"]), -6.0, abs_tol=1e-9)
    assert math.isclose(float(row["pre_wheel_speed_aligned_rpm"]), -820.0, abs_tol=1e-9)
    assert math.isclose(float(row["delta_wheel_speed_rpm"]), 210.0, abs_tol=1e-9)

print("V46ak repeatability observation guards: PASS")
