#!/usr/bin/env python3
from pathlib import Path
import json

R=Path(__file__).resolve().parents[1]
config=(R/'src/config.h').read_text()
logger_h=(R/'src/psram_logger.h').read_text()
logger=(R/'src/psram_logger.cpp').read_text()
web=(R/'src/web_ui.cpp').read_text()
manifest=json.loads((R/'site/manifest.json').read_text())
site=(R/'site/index.html').read_text()

assert 'RWLOG_DOWNLOAD_REVISION[] = "v46ar_prepared_rwlog_download_20260921"' in config
assert 'RWLOG_STORAGE_REVISION[] = "v46ap_compact_rwlog_20260921"' in config

for token in (
    'bool prepareRwLog();',
    'bool rwlogPrepared() const',
    'bool rwlogPrepareAttempted() const',
    'prepared_metadata_',
    'prepared_header_',
    'prepared_crc_',
    'prepared_total_size_',
    'rwlog_prepare_state_',
):
    assert token in logger_h, token

assert 'bool PsramLogger::prepareRwLog()' in logger
assert 'prepared_metadata_ = buildMetadataJson();' in logger
assert 'prepared_header_ = buildHeader(prepared_metadata_.length());' in logger
assert 'prepared_crc_ = calculateCrc(prepared_header_, prepared_metadata_);' in logger
assert 'rwlog_prepare_state_ = "ready";' in logger
assert 'RWLOG prepared metadata=' in logger
assert 'RWLOG prepare FAIL metadata' in logger

stream=logger[logger.index('bool PsramLogger::streamRwLog'): ]
stream=stream[:stream.index('\n}\n')+3]
assert 'buildMetadataJson()' not in stream
assert 'calculateCrc(' not in stream
assert 'prepared_header_' in stream
assert 'prepared_metadata_' in stream
assert 'prepared_crc_' in stream
assert 'server.setContentLength(prepared_total_size_)' in stream

assert 'return ready_ && run_start_us_ != 0 && sample_count_ > 0 && rwlog_prepared_;' in logger

assert 'logger_->lastMeasurementDone() && !logger_->rwlogPrepareAttempted()' in web
assert 'logger_->prepareRwLog();' in web
for token in (
    'rwlog_prepare_state',
    'rwlog_metadata_bytes',
    'rwlog_total_bytes',
    'rwlog_prepare_metadata_us',
    'rwlog_prepare_crc_us',
    'rwlog_prepare_total_us',
    'id="rwlogInfo"',
):
    assert token in web, token

# Transfer remains the V46al-style path restored in V46aq.
assert 'STREAM_CHUNK_BYTES = 4096' in logger
assert 'if (client.write(data, n) != n) return false;' in logger
assert 'rwlog_http_range' not in logger
assert 'rwlog_stream_transport' not in logger
assert 'beginNativeRwlogDownload' not in web
assert 'resumeUiAfterDownload' not in web

assert manifest['version']=='0.46.43'
assert 'V46ar' in manifest['name']
assert 'V46ar / 0.46.43' in site

for token in (
    'AMPLITUDE_CONTROL_REVISION[] = "v46al_previous_peak_active_control_20260921"',
    'ENERGY_CONTROL_AUTONOMOUS_TIMING_COMPENSATION_US = 3000UL',
    'ENERGY_CONTROL_AUTONOMOUS_CURRENT_MA = 300',
    'ENERGY_CONTROL_AUTONOMOUS_MAX_PULSE_MS = 100',
):
    assert token in config, token

print('V46ar PASS: RWLOG is prepared before download and V46al stream is retained')
