#!/usr/bin/env python3
from pathlib import Path
import json

R=Path(__file__).resolve().parents[1]
config=(R/'src/config.h').read_text()
logger=(R/'src/psram_logger.cpp').read_text()
web=(R/'src/web_ui.cpp').read_text()
manifest=json.loads((R/'site/manifest.json').read_text())
site=(R/'site/index.html').read_text()

assert 'RWLOG_DOWNLOAD_REVISION[] = "v46ar_prepared_rwlog_download_20260921"' in config
assert 'RWLOG_STORAGE_REVISION[] = "v46ap_compact_rwlog_20260921"' in config

# Exact V46al-style server transport.
assert 'STREAM_CHUNK_BYTES = 4096' in logger
assert 'WiFiClient client = server.client();' in logger
assert 'if (client.write(data, n) != n) return false;' in logger
assert ('server.setContentLength(header.crc_offset + sizeof(crc));' in logger or
        'server.setContentLength(prepared_total_size_);' in logger)
assert 'server.send(200, "application/octet-stream", "");' in logger
assert 'rwlog_stream_transport' not in logger
assert 'rwlog_http_range' not in logger
for forbidden in (
    'Accept-Ranges',
    'Content-Range',
    'X-RWLOG-Transport',
    'server.send(partial ? 206 : 200',
    'rwlog_range_invalid',
):
    assert forbidden not in logger, forbidden

# V46ap compact sections are still sent before CRC.
assert 'writeBytes(server, reinterpret_cast<const uint8_t*>(samples_)' in logger
assert 'writeBytes(server, reinterpret_cast<const uint8_t*>(pulse_audit_samples_)' in logger
assert 'pulse_audit_count_ * sizeof(PulseAuditSample)' in logger
assert 'metadata_profile\\":\\\"v46ap_compact' in logger

# Exact old-style browser behavior: plain anchor + short local hold.
assert '<a id="rwlog" class="action" href="/download/rwlog" onclick="beginDownload()">Download RWLOG</a>' in web
assert 'function beginDownload()' in web
assert "setTimeout(()=>{downloading=false;refresh();},3000)" in web
assert 'beginNativeRwlogDownload' not in web
assert 'resumeUiAfterDownload' not in web
assert 'resumeDownload' not in web
assert 'collectHeaders' not in web
assert '"Range"' not in web
assert "fetch('/download/rwlog'" not in web

assert manifest['version'] in ('0.46.42','0.46.43')
assert 'V46aq' in manifest['name'] or 'V46ar' in manifest['name']
assert 'V46aq / 0.46.42' in site or 'V46ar / 0.46.43' in site

# Control/safety are not part of this rollback.
for token in (
    'AMPLITUDE_CONTROL_REVISION[] = "v46al_previous_peak_active_control_20260921"',
    'ENERGY_CONTROL_AUTONOMOUS_TIMING_COMPENSATION_US = 3000UL',
    'ENERGY_CONTROL_AUTONOMOUS_CURRENT_MA = 300',
    'ENERGY_CONTROL_AUTONOMOUS_MAX_PULSE_MS = 100',
):
    assert token in config, token

print('V46aq PASS: V46al download path restored on top of V46ap compact RWLOG')
