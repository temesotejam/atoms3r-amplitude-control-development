#pragma once
#include <cstddef>
#include <cstdint>

namespace rwlog_stream_transport {
static constexpr size_t CHUNK_BYTES = 1460;  // one TCP MSS-sized write
static constexpr uint32_t STALL_TIMEOUT_MS = 15000UL;

template <typename Client, typename NowFn, typename PauseFn>
bool writeAll(Client& client, const uint8_t* data, size_t len, NowFn now_ms, PauseFn pause_ms) {
  uint32_t last_progress_ms = now_ms();
  while (len > 0) {
    if (!client.connected()) return false;
    const size_t request = len > CHUNK_BYTES ? CHUNK_BYTES : len;
    const size_t written = client.write(data, request);
    if (written > 0) {
      const size_t accepted = written > request ? request : written;
      data += accepted;
      len -= accepted;
      last_progress_ms = now_ms();
      pause_ms(0);
      continue;
    }
    if (static_cast<uint32_t>(now_ms() - last_progress_ms) >= STALL_TIMEOUT_MS) return false;
    pause_ms(1);
  }
  return true;
}
}  // namespace rwlog_stream_transport
