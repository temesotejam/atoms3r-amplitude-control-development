"""Invert the V46ap logging/storage-only delta for retained historical hash guards."""
import re

OLD_LOG_SAMPLE_IF_DUE = """void ExperimentRunner::logSampleIfDue() {
  const uint32_t now_us = micros();
  // Preserve the normal 20 ms time series. While an already-authorized pulse
  // is live, add rows at the current-audit period so fresh-read gaps can be
  // evaluated offline. Logging rate cannot alter the motor command.
  const uint32_t period_us = status_.pulse_active
      ? Config::CURRENT_AUDIT_LOG_PERIOD_US : Config::LOG_PERIOD_MS * 1000UL;
  if (last_log_us_ != 0 && static_cast<uint32_t>(now_us - last_log_us_) < period_us) return;
  const bool probe_log = timing_probe_pending_ && !timing_probe_log_captured_ &&
      status_.pulse_active && status_.pulse_id == timing_probe_event_.pulse_id;
  const uint32_t log_start_us = probe_log ? micros() : 0;
  logSampleNow();
  if (probe_log) {
    timing_probe_event_.first_audit_log_offset_us =
        static_cast<uint32_t>(log_start_us - timing_probe_event_.pulse_start_us);
    timing_probe_event_.first_audit_log_us = static_cast<uint32_t>(micros() - log_start_us);
    timing_probe_log_captured_ = true;
    maybeFinalizeTimingProbe();
  }
}

"""

def normalize_file(path: str, text: str) -> str:
    if path == "src/experiment_runner.cpp":
        text = text.replace("  last_pulse_audit_us_ = 0;\n", "")
        compact_start = text.find("  if (energy_control_autonomous_mode_) {\n    auto ageToU16")
        compact_end = text.find("  LogSample row{};", compact_start)
        if compact_start >= 0 and compact_end >= 0:
            text = text[:compact_start] + text[compact_end:]
        start = text.find("void ExperimentRunner::logSampleIfDue() {")
        end = text.find("void ExperimentRunner::logSampleNow() {", start)
        if start >= 0 and end >= 0 and "addPulseAuditSample" in text[start:end]:
            text = text[:start] + OLD_LOG_SAMPLE_IF_DUE + text[end:]
    elif path == "src/experiment_runner.h":
        text = text.replace("  uint32_t last_pulse_audit_us_ = 0;\n", "")
    elif path == "src/config.h":
        text = text.replace("static constexpr size_t AUTONOMOUS_LOG_BUFFER_BYTES = 128UL * 1024UL;\n", "")
        text = text.replace(
            'static constexpr char RWLOG_STORAGE_REVISION[] = "v46as_autonomous_compact_v52_20260921";',
            'static constexpr char RWLOG_STORAGE_REVISION[] = "v46ap_compact_rwlog_20260921";')
        new = """// V46ap: the 258-byte full time-series row is now kept at the normal 50 Hz only.
// 1 MiB holds >80 s at 50 Hz, comfortably above the fixed 30 s Autonomous run.
// High-rate pulse current/wheel observations have their own compact PSRAM buffer.
static constexpr size_t LOG_BUFFER_BYTES = 1UL * 1024UL * 1024UL;
static constexpr size_t PULSE_AUDIT_BUFFER_BYTES = 512UL * 1024UL;
static constexpr uint8_t BUFFER_WARNING_PERCENT = 90;"""
        old = """static constexpr size_t LOG_BUFFER_BYTES = 6UL * 1024UL * 1024UL;
static constexpr uint8_t BUFFER_WARNING_PERCENT = 90;"""
        text = text.replace(new, old)
        text = text.replace('static constexpr char RWLOG_STORAGE_REVISION[] = "v46ap_compact_rwlog_20260921";\n', "")
    elif path == "src/log_types.h":
        compact_marker = "\n// V46as: current Autonomous amplitude-control time series only."
        pulse_marker = "\n// V46ap: compact 2 ms pulse-only observation record."
        compact_pos = text.find(compact_marker)
        pulse_pos = text.find(pulse_marker)
        if compact_pos >= 0 and pulse_pos > compact_pos:
            text = text[:compact_pos] + text[pulse_pos:]
        marker = "\n// V46ap: compact 2 ms pulse-only observation record."
        pos = text.find(marker)
        if pos >= 0:
            text = text[:pos]
            text += '\nstatic_assert(sizeof(RwLogFileHeader) == 110, "RwLogFileHeader binary size changed");\n'
            text += 'static_assert(sizeof(LogSample) == 258, "LogSample binary size changed");\n'
    return text
