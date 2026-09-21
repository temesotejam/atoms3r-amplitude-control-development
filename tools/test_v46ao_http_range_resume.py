#!/usr/bin/env python3
from pathlib import Path
import json, subprocess, tempfile

R=Path(__file__).resolve().parents[1]
config=(R/'src/config.h').read_text()
logger=(R/'src/psram_logger.cpp').read_text()
web=(R/'src/web_ui.cpp').read_text()
manifest=json.loads((R/'site/manifest.json').read_text())
site=(R/'site/index.html').read_text()

assert 'RWLOG_DOWNLOAD_REVISION[] = "v46ao_http_range_resume_20260921"' in config
assert manifest['version'] in ('0.46.40','0.46.41')
assert 'V46ao' in manifest['name'] or 'V46ap' in manifest['name']
assert 'V46ao / 0.46.40' in site or 'V46ap / 0.46.41' in site

# WebServer must collect Range before begin and the RWLOG endpoint must advertise/resume bytes.
assert 'const char* collected_headers[] = {"Range"};' in web
assert 'server_->collectHeaders(collected_headers, 1);' in web
for token in (
    'server.sendHeader("Accept-Ranges", "bytes")',
    'server.sendHeader("Content-Range"',
    'server.send(partial ? 206 : 200, "application/octet-stream", "")',
    'server.send(416, "text/plain", last_error_)',
    'rwlog_http_range::parse(',
    'X-RWLOG-Transport", "v46ao-range-resume"',
):
    assert token in logger, token

# Range serving stays virtual; there must be no full-file staging allocation.
assert 'write_segment(reinterpret_cast<const uint8_t*>(&header)' in logger
assert 'write_segment(reinterpret_cast<const uint8_t*>(metadata.c_str())' in logger
assert 'write_segment(reinterpret_cast<const uint8_t*>(samples_)' in logger
assert 'write_segment(reinterpret_cast<const uint8_t*>(pulse_audit_samples_)' in logger
assert 'write_segment(reinterpret_cast<const uint8_t*>(&crc)' in logger
assert 'RWLOG_FORMAT_VERSION = 51' in logger
assert 'sizeof(LogSample) == 258' in (R/'src/log_types.h').read_text()

code=r'''
#include <cassert>
#include "rwlog_http_range.h"
using namespace rwlog_http_range;
int main(){
  const size_t total=1000;
  auto none=parse("",total);assert(none.status==NONE);
  auto a=parse("bytes=728-",total);assert(a.status==VALID&&a.start==728&&a.end==999);
  auto b=parse("bytes=100-199",total);assert(b.status==VALID&&b.start==100&&b.end==199);
  auto c=parse("bytes=900-2000",total);assert(c.status==VALID&&c.start==900&&c.end==999);
  auto d=parse("bytes=-50",total);assert(d.status==VALID&&d.start==950&&d.end==999);
  auto e=parse("bytes=-2000",total);assert(e.status==VALID&&e.start==0&&e.end==999);
  assert(parse("bytes=1000-",total).status==UNSATISFIABLE);
  assert(parse("items=1-2",total).status==INVALID);
  assert(parse("bytes=2-1",total).status==INVALID);
  assert(parse("bytes=1-2,4-5",total).status==INVALID);
  assert(parse("bytes=-0",total).status==INVALID);
}
'''
with tempfile.TemporaryDirectory() as d:
    p=Path(d);(p/'t.cpp').write_text(code);exe=p/'t'
    subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'src'),str(p/'t.cpp'),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

print('V46ao HTTP Range resume guards PASS')
