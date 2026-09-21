#!/usr/bin/env python3
from pathlib import Path
import json
import struct

R = Path(__file__).resolve().parents[1]
config = (R / "src/config.h").read_text(encoding="utf-8")
types = (R / "src/log_types.h").read_text(encoding="utf-8")
logger = (R / "src/psram_logger.cpp").read_text(encoding="utf-8")
runner = (R / "src/experiment_runner.cpp").read_text(encoding="utf-8")
converter = (R / "tools/convert_rwlog_to_csv.py").read_text(encoding="utf-8")
manifest = json.loads((R / "site/manifest.json").read_text(encoding="utf-8"))
site = (R / "site/index.html").read_text(encoding="utf-8")

assert 'RWLOG_STORAGE_REVISION[] = "v46ap_compact_rwlog_20260921"' in config
assert "LOG_BUFFER_BYTES = 1UL * 1024UL * 1024UL" in config
assert "PULSE_AUDIT_BUFFER_BYTES = 512UL * 1024UL" in config
assert "LOG_PERIOD_MS = 20" in config
assert "CURRENT_AUDIT_LOG_PERIOD_US = 2000UL" in config

assert "struct PulseAuditSample" in types
assert 'sizeof(PulseAuditSample) == 26' in types
assert 'sizeof(LogSample) == 258' in types
assert struct.calcsize("<IIhhiIIBB") == 26

start = runner.index("void ExperimentRunner::logSampleIfDue()")
end = runner.index("void ExperimentRunner::logSampleNow()", start)
logging = runner[start:end]
assert "addPulseAuditSample" in logging
assert "status_.pulse_active" in logging
assert "Config::CURRENT_AUDIT_LOG_PERIOD_US" in logging
assert "Config::LOG_PERIOD_MS * 1000UL" in logging
assert "PulseAuditSample audit{}" in logging
assert "wheel_speed_x100_rpm" in logging
assert "status_.pulse_active\n      ? Config::CURRENT_AUDIT_LOG_PERIOD_US" not in logging

for token in (
    "header.summary_count = pulse_audit_count_",
    "header.summary_row_size = sizeof(PulseAuditSample)",
    "pulse_audit_count_ * sizeof(PulseAuditSample)",
    "reinterpret_cast<const uint8_t*>(pulse_audit_samples_)",
    'metadata_profile\\":\\\"v46ap_compact',
    "kCompactMetadataReserveBytes = 192U * 1024U",
    'energy_control_autonomous_peak_events',
    'energy_control_autonomous_zero_cross_events',
):
    assert token in logger, token

assert 'PULSE_AUDIT_FORMAT_V46AP = "<IIhhiIIBB"' in converter
assert '"pulse_audit.csv"' in converter
assert "write_pulse_audit_samples" in converter

main_capacity = (1 * 1024 * 1024) // 258
pulse_capacity = (512 * 1024) // 26
assert main_capacity * 0.020 > 30.0
assert pulse_capacity * 0.002 > 30.0

assert manifest["version"] in ("0.46.41","0.46.42","0.46.43")
assert "V46ap" in manifest["name"] or "V46aq" in manifest["name"] or "V46ar" in manifest["name"]
assert "V46ap / 0.46.41" in site or "V46aq / 0.46.42" in site or "V46ar / 0.46.43" in site

# V46ap is logging/storage only. Physical output and timing limits remain frozen.
for token in (
    "ENERGY_CONTROL_AUTONOMOUS_CURRENT_MA = 300",
    "ENERGY_CONTROL_AUTONOMOUS_MAX_PULSE_MS = 100",
    "ENERGY_CONTROL_AUTONOMOUS_TIMING_COMPENSATION_US = 3000UL",
):
    assert token in config, token

print("V46ap compact RWLOG guards PASS")
