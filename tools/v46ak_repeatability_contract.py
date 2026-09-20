"""Normalize V46ak observation-only additions back to the frozen V46aj source.

These helpers are used only by retained regression/hash tests. They intentionally
remove observation/logging code while leaving controller/estimator code untouched,
so the historical protected hashes remain the acceptance criterion.
"""
from __future__ import annotations


def normalize_config(data: str) -> str:
    data = data.replace(
        'static constexpr char AMPLITUDE_CONTROL_DEVELOPMENT_REVISION[] = '
        '"v46ak_repeatability_observation_20260920";\n',
        '',
    )
    return data


def normalize_roller_h(data: str) -> str:
    start = data.find('  // V46ak observation-only wheel-speed telemetry. Never used by control.\n')
    if start >= 0:
        end_marker = '  bool pulse_end_wheel_speed_valid = false;\n'
        end = data.find(end_marker, start)
        if end < 0:
            raise ValueError('V46ak RollerTelemetry block changed')
        end += len(end_marker)
        data = data[:start] + data[end:]
    data = data.replace('  bool readSpeedFresh(bool pulse_end_capture);\n', '')
    return data


def normalize_roller_cpp(data: str) -> str:
    data = data.replace(
        '// Official Unit Roller485 I2C speed readback register; signed value is RPM * 100.\n'
        'static constexpr uint8_t REG_SPEED_READBACK = 0x60;\n',
        '',
    )
    data = data.replace(
        '\n\n  // V46ak: observation only. Do not add speed-read success to the mandatory\n'
        '  // Roller health gate, and do not perform this extra I2C read during a pulse.\n'
        '  if (command_mA_ == 0) readSpeedFresh(false);',
        '',
    )

    new_apply = '''  if (!was_commanded && cmd.current_mA != 0) {
    beginCurrentAuditPulse();
  } else if (was_commanded && cmd.current_mA == 0) {
    endCurrentAuditPulse();
    // Capture one post-pulse speed sample only after the stop command has
    // already been applied. Failure is diagnostic-only and cannot fail stop.
    if (readSpeedFresh(true) && telemetry_.pulse_end_wheel_speed_sample_time_us != 0) {
      telemetry_.pulse_end_wheel_speed_capture_delay_us =
          static_cast<uint32_t>(telemetry_.pulse_end_wheel_speed_sample_time_us - applied_us);
    }
  }
'''
    old_apply = '''  if (!was_commanded && cmd.current_mA != 0) beginCurrentAuditPulse();
  else if (was_commanded && cmd.current_mA == 0) endCurrentAuditPulse();
'''
    if new_apply in data:
        data = data.replace(new_apply, old_apply, 1)

    start = data.find('bool Roller485Manager::readSpeedFresh(bool pulse_end_capture) {\n')
    if start >= 0:
        end = data.find('void Roller485Manager::recordFreshCurrent(', start)
        if end < 0:
            raise ValueError('V46ak readSpeedFresh boundary changed')
        data = data[:start] + data[end:]
    return data


def normalize_runner(data: str) -> str:
    start = data.find(
        '  // V46ak: copy the already-published Core0 snapshot once per control update.\n'
    )
    if start >= 0:
        end = data.find('  const ImuReading& r = imu_->reading();\n', start)
        if end < 0:
            raise ValueError('V46ak runner snapshot boundary changed')
        data = data[:start] + data[end:]

    data = data.replace(
        '  energy_control_autonomous_pending_output_executed_ = false;\n',
        '',
        1,
    )

    start = data.find(
        '  // V46ak repeatability audit: snapshot only. All values were published by\n'
    )
    if start >= 0:
        end = data.find('  const uint32_t v46l_free_model_t0_us = micros();\n', start)
        if end < 0:
            raise ValueError('V46ak zero-cross observation boundary changed')
        data = data[:start] + data[end:]

    data = data.replace(
        '  energy_control_autonomous_pending_zero_event_index_ = 0;\n'
        '  energy_control_autonomous_pending_output_executed_ = false;\n'
        '  if (selected_width_ms == 0) {',
        '  if (selected_width_ms == 0) {',
        1,
    )

    data = data.replace(
        '    energy_control_autonomous_pending_zero_event_index_ =\n'
        '        logger_->nextEnergyControlAutonomousZeroCrossEventIndex();\n'
        '    energy_control_autonomous_pending_output_executed_ = false;\n',
        '',
        1,
    )
    data = data.replace(
        '  energy_control_autonomous_pending_zero_event_index_ =\n'
        '      logger_->nextEnergyControlAutonomousZeroCrossEventIndex();\n'
        '  energy_control_autonomous_pending_output_executed_ = true;\n',
        '',
        1,
    )

    start = data.find(
        '  event.source_zero_cross_event_index = event.pending_command_matched\n'
    )
    if start >= 0:
        end = data.find('  event.antiwindup_upper_hold = event.pending_command_matched &&\n', start)
        if end < 0:
            raise ValueError('V46ak peak outcome boundary changed')
        data = data[:start] + data[end:]
    return data
