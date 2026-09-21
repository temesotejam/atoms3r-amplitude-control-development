#!/usr/bin/env python3
from pathlib import Path
import subprocess
import tempfile

R=Path(__file__).resolve().parents[1]
config=(R/'src/config.h').read_text()
logger=(R/'src/psram_logger.cpp').read_text()
helper=(R/'src/rwlog_write_all.h').read_text()
web=(R/'src/web_ui.cpp').read_text()

assert 'RWLOG_DOWNLOAD_REVISION[] = "v46at_partial_write_safe_20260921"' in config
assert '#include "rwlog_write_all.h"' in logger
assert 'rwlog_write_all::writeAll' in logger
assert 'CHUNK_BYTES = 1460' in helper
assert 'STALL_TIMEOUT_MS = 15000UL' in helper
assert 'written > 0' in helper
assert 'data += written' in helper
assert 'len -= written' in helper
assert 'pause_ms(1)' in helper

# Keep the simple single HTTP 200 download: no Range/native-download machinery.
for forbidden in (
    'Accept-Ranges',
    'Content-Range',
    'X-RWLOG-Transport',
    'rwlog_http_range',
    'server.send(partial ? 206 : 200',
):
    assert forbidden not in logger, forbidden
assert 'server.send(200, "application/octet-stream", "");' in logger
assert '<a id="rwlog" class="action" href="/download/rwlog" onclick="beginDownload()">Download RWLOG</a>' in web
assert 'beginNativeRwlogDownload' not in web

source=r'''
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <vector>
#include "rwlog_write_all.h"

struct FakeClient {
  std::vector<size_t> plan;
  size_t call=0,total=0;
  bool connected_flag=true;
  bool connected() const { return connected_flag; }
  size_t write(const uint8_t*, size_t request) {
    if (!connected_flag) return 0;
    size_t n = call < plan.size() ? plan[call++] : request;
    n = std::min(n, request);
    total += n;
    return n;
  }
};

int main() {
  uint8_t data[10000]{};

  // Repeated partial writes must finish all bytes instead of failing.
  {
    FakeClient c; c.plan={500,300,1460,1,1459,700,0,900};
    uint32_t now=0;
    bool ok=rwlog_write_all::writeAll(c,data,sizeof(data),
      [&](){return now;},[&](uint32_t ms){now+=ms?ms:1;});
    assert(ok && c.total==sizeof(data));
  }

  // Zero-byte backpressure is retried if progress resumes before timeout.
  {
    FakeClient c; c.plan={0,0,0,100,0,1360,1460};
    uint32_t now=0;
    bool ok=rwlog_write_all::writeAll(c,data,2920,
      [&](){return now;},[&](uint32_t ms){now+=ms?5000:0;});
    assert(ok && c.total==2920);
  }

  // Permanent zero-byte stall fails after the bounded timeout.
  {
    FakeClient c; c.plan=std::vector<size_t>(20,0);
    uint32_t now=0;
    bool ok=rwlog_write_all::writeAll(c,data,100,
      [&](){return now;},[&](uint32_t){now+=1000;});
    assert(!ok);
  }

  // Disconnected client fails closed.
  {
    FakeClient c; c.connected_flag=false;
    uint32_t now=0;
    assert(!rwlog_write_all::writeAll(c,data,100,[&](){return now;},[&](uint32_t){}));
  }
}
'''
with tempfile.TemporaryDirectory() as d:
    cpp=Path(d)/'test.cpp'; exe=Path(d)/'test'
    cpp.write_text(source)
    subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror',
                    '-I'+str(R/'src'),str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

print('V46at PASS: partial TCP writes are completed, stalls bounded, direct HTTP 200 retained')
