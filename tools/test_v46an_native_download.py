#!/usr/bin/env python3
from pathlib import Path
import json

R=Path(__file__).resolve().parents[1]
config=(R/'src/config.h').read_text()
web=(R/'src/web_ui.cpp').read_text()
manifest=json.loads((R/'site/manifest.json').read_text())
site=(R/'site/index.html').read_text()

assert 'ATTITUDE_VALIDATION_REVISION[] = "v46aj_fixed_3ms_compensation_20260920"' in config
assert 'AMPLITUDE_CONTROL_REVISION[] = "v46al_previous_peak_active_control_20260921"' in config
assert 'RWLOG_DOWNLOAD_REVISION[] = "v46an_native_download_hold_20260921"' in config
assert manifest['version'] in ('0.46.39','0.46.40')
assert 'V46an / 0.46.39' in site or 'V46ao / 0.46.40' in site

# Native browser download begins directly from the user's click.
assert '<a id="rwlog" class="action" href="/download/rwlog" download onclick="return beginNativeRwlogDownload()">Download RWLOG</a>' in web
assert 'function beginNativeRwlogDownload()' in web
assert "return true;" in web[web.index('function beginNativeRwlogDownload()'):web.index('function resumeUiAfterDownload()')]
assert "fetch('/download/rwlog'" not in web
assert '.blob()' not in web
assert 'createObjectURL' not in web

# Status traffic remains suppressed for the entire native download hold.
assert 'if(refreshInFlight||downloading)return;' in web
assert 'resumeDownload.hidden=false;' in web
assert 'function resumeUiAfterDownload()' in web
assert 'downloading=false;' in web[web.index('function resumeUiAfterDownload()'):]
assert 'resumeDownload.hidden=true;' in web
assert 'setTimeout(()=>{downloading=false' not in web

# UI remains minimal.
for forbidden in ('Q1 direct next-peak shadow','Passive release capture','ZERO Current Roll','Target Current Roll'):
    assert forbidden not in web

print('V46an native RWLOG download hold guards PASS')
