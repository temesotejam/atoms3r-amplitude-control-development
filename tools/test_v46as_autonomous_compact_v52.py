#!/usr/bin/env python3
from pathlib import Path
import csv
import importlib.util
import json
import struct
import tempfile
import zlib

R=Path(__file__).resolve().parents[1]
config=(R/'src/config.h').read_text()
types=(R/'src/log_types.h').read_text()
logger_h=(R/'src/psram_logger.h').read_text()
logger=(R/'src/psram_logger.cpp').read_text()
runner=(R/'src/experiment_runner.cpp').read_text()
converter_src=(R/'tools/convert_rwlog_to_csv.py').read_text()
manifest=json.loads((R/'site/manifest.json').read_text())
site=(R/'site/index.html').read_text()

assert 'RWLOG_STORAGE_REVISION[] = "v46as_autonomous_compact_v52_20260921"' in config
assert 'AUTONOMOUS_LOG_BUFFER_BYTES = 128UL * 1024UL' in config
assert 'struct AutonomousCompactSample' in types
assert 'sizeof(AutonomousCompactSample) == 40' in types
assert struct.calcsize('<IIIhhhhhHHHHBBbBBBhh') == 40

assert 'AutonomousCompactSample* autonomous_samples_' in logger_h
assert 'const size_t active_sample_count =' in logger
assert 'active_sample_count == 0' in logger
assert 'bool addAutonomousSample(const AutonomousCompactSample& row);' in logger_h
assert 'autonomous_sample_count_' in logger_h
assert 'autonomous_sample_capacity_' in logger_h

for token in (
    'RWLOG_FORMAT_VERSION_AUTONOMOUS_COMPACT = 52',
    'Config::AUTONOMOUS_LOG_BUFFER_BYTES / sizeof(AutonomousCompactSample)',
    'metadata_profile\\":\\\"v46as_autonomous_v52',
    'kCompactMetadataReserveBytes = 64U * 1024U',
    'header.sample_count = compact_autonomous ? autonomous_sample_count_ : sample_count_',
    'header.log_sample_size = compact_autonomous ? sizeof(AutonomousCompactSample) : sizeof(LogSample)',
    'autonomous_sample_count_ * sizeof(AutonomousCompactSample)',
    'reinterpret_cast<const uint8_t*>(autonomous_samples_)',
):
    assert token in logger, token

log_now=runner[runner.index('void ExperimentRunner::logSampleNow()'):]
assert 'if (energy_control_autonomous_mode_) {' in log_now
assert 'AutonomousCompactSample row{};' in log_now
assert 'logger_->addAutonomousSample(row)' in log_now
assert 'pitch_mekf_measurement_relative_cdeg' in log_now
assert 'roller_current_age_us' in log_now
assert 'return;' in log_now[log_now.index('if (energy_control_autonomous_mode_) {'):log_now.index('LogSample row{};')]

# 30 s at 50 Hz is only 60 kB of primary time-series data.
assert 30 * 50 * 40 == 60000
assert (128 * 1024) // 40 > 30 * 50

assert 'SAMPLE_FORMAT_V52 = "<IIIhhhhhHHHHBBbBBBhh"' in converter_src
assert 'CSV_COLUMNS_V52' in converter_src
assert 'convert_sample_v52' in converter_src

spec=importlib.util.spec_from_file_location('rwconv', R/'tools/convert_rwlog_to_csv.py')
conv=importlib.util.module_from_spec(spec); spec.loader.exec_module(conv)
assert struct.calcsize(conv.SAMPLE_FORMAT_V52)==40

with tempfile.TemporaryDirectory(prefix='rwlog_v52_') as temp:
    root=Path(temp); source=root/'compact.rwlog'; out=root/'out'
    values=(1_000_000,1_000,7,812,801,-5534,300,287,7420,18,120,900,3,1,-1,5,1,1,9300,21)
    sample=struct.pack(conv.SAMPLE_FORMAT_V52,*values)
    metadata=b'{}'
    hs=struct.calcsize(conv.HEADER_FORMAT)
    samples_offset=hs+len(metadata)
    crc_offset=samples_offset+len(sample)
    hv=[b'RWLOG01\0',52,hs,1,123456789,len(metadata),1,0,0,
        len(sample),0,0,20,2,20,500,1,32,1,
        samples_offset,crc_offset,crc_offset,crc_offset]+[0]*8
    header=struct.pack(conv.HEADER_FORMAT,*hv)
    payload=header+metadata+sample
    source.write_bytes(payload+struct.pack('<I',zlib.crc32(payload)&0xffffffff))
    conv.convert(source,out)
    with (out/'timeseries.csv').open(newline='',encoding='utf-8') as f:
        row=next(csv.DictReader(f))
    assert row['pitch_mekf_measurement_relative_deg']=='8.120'
    assert row['pitch_mekf_control_deg']=='8.010'
    assert row['gyro_pitch_rate_dps']=='-55.340'
    assert row['motor_cmd_mA']=='300'
    assert row['roller_actual_current_mA']=='287'
    assert row['roller_battery_mV']=='7420'
    assert row['pulse_width_ms']=='18'
    assert row['pulse_direction']=='-1'
    assert row['mekf_accel_confidence']=='0.9300'

assert manifest['version']=='0.46.44'
assert 'V46as' in manifest['name']
assert 'V46as / 0.46.44' in site

for token in (
    'AMPLITUDE_CONTROL_REVISION[] = "v46al_previous_peak_active_control_20260921"',
    'ENERGY_CONTROL_AUTONOMOUS_TIMING_COMPENSATION_US = 3000UL',
    'ENERGY_CONTROL_AUTONOMOUS_CURRENT_MA = 300',
    'ENERGY_CONTROL_AUTONOMOUS_MAX_PULSE_MS = 100',
):
    assert token in config, token

print('V46as PASS: 40-byte Autonomous v52 time series, converter and frozen control/safety')
