#!/usr/bin/env python3
from pathlib import Path
import json, subprocess, tempfile

R=Path(__file__).resolve().parents[1]
config=(R/'src/config.h').read_text()
logger=(R/'src/psram_logger.cpp').read_text()
transport=(R/'src/rwlog_stream_transport.h').read_text()

assert 'ATTITUDE_VALIDATION_REVISION[] = "v46aj_fixed_3ms_compensation_20260920"' in config
assert 'AMPLITUDE_CONTROL_REVISION[] = "v46al_previous_peak_active_control_20260921"' in config

# Server transport handles short writes instead of treating them as fatal.
assert 'CHUNK_BYTES = 1460' in transport
assert 'STALL_TIMEOUT_MS = 15000UL' in transport
assert 'written > 0' in transport
assert 'data += accepted' in transport and 'len -= accepted' in transport
assert 'client.write(data, n) != n' not in logger
assert 'rwlog_stream_transport::writeAll' in logger
assert 'server.sendHeader("Connection", "close")' in logger
assert 'X-RWLOG-Transport' in logger

# The RWLOG measurement format stays unchanged.
assert 'RWLOG_FORMAT_VERSION = 51' in logger
assert 'sizeof(LogSample) == 258' in (R/'src/log_types.h').read_text()

code=r'''
#include <cassert>
#include <cstdint>
#include <vector>
#include "rwlog_stream_transport.h"
struct FakeClient {
  bool up=true; std::vector<size_t> limits; size_t call=0; std::vector<uint8_t> out;
  bool connected() const { return up; }
  size_t write(const uint8_t* p,size_t n) {
    size_t cap = call<limits.size()?limits[call++]:n;
    size_t w = cap<n?cap:n;
    out.insert(out.end(),p,p+w); return w;
  }
};
int main(){
  std::vector<uint8_t> src(5000);for(size_t i=0;i<src.size();++i)src[i]=uint8_t(i);
  uint32_t t=0;FakeClient partial;partial.limits={200,0,37,1460,10,0,900};
  assert(rwlog_stream_transport::writeAll(partial,src.data(),src.size(),[&](){return t;},[&](uint32_t ms){t+=ms;}));
  assert(partial.out==src);
  FakeClient stall;stall.limits.assign(20000,0);t=0;
  assert(!rwlog_stream_transport::writeAll(stall,src.data(),20,[&](){return t;},[&](uint32_t ms){t+=ms;}));
  assert(t>=rwlog_stream_transport::STALL_TIMEOUT_MS);
  FakeClient down;down.up=false;t=0;
  assert(!rwlog_stream_transport::writeAll(down,src.data(),20,[&](){return t;},[&](uint32_t ms){t+=ms;}));
}
'''
with tempfile.TemporaryDirectory() as d:
    p=Path(d);(p/'t.cpp').write_text(code);exe=p/'t'
    subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'src'),str(p/'t.cpp'),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
print('V46am server-side RWLOG transport guards PASS')
