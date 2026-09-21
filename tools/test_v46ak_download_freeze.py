#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
web = (ROOT / "src/web_ui.cpp").read_text(encoding="utf-8").replace("\r\n", "\n")
logger = (ROOT / "src/psram_logger.cpp").read_text(encoding="utf-8").replace("\r\n", "\n")


def extract_function(text: str, signature: str) -> str:
    start = text.index(signature)
    brace = text.index("{", start)
    depth = 0
    for i in range(brace, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise AssertionError(f"unterminated function: {signature}")


expected_handle = """void WebUi::handleRwLog() {
  if (run_control.active()) { server_->send(409, "text/plain", "run_in_progress"); return; }
  if (runner_->running()) {
    server_->send(409, "text/plain", "measurement_running");
    return;
  }
  logger_->streamRwLog(*server_);
}"""

expected_write = """bool PsramLogger::writeBytes(WebServer& server, const uint8_t* data, size_t len) {
  WiFiClient client = server.client();
  while (len > 0) {
    const size_t n = len > STREAM_CHUNK_BYTES ? STREAM_CHUNK_BYTES : len;
    if (client.write(data, n) != n) return false;
    data += n;
    len -= n;
    delay(0);
  }
  return true;
}"""

expected_stream = """bool PsramLogger::streamRwLog(WebServer& server) {
  if (!rwlogDownloadable()) {
    last_error_ = "rwlog_not_ready";
    server.send(409, "text/plain", last_error_);
    return false;
  }

  downloading_ = true;
  const String metadata = buildMetadataJson();
  const RwLogFileHeader header = buildHeader(metadata.length());
  const uint32_t crc = calculateCrc(header, metadata);
  char filename[72];
  downloadFilename(filename, sizeof(filename));

  server.sendHeader("Content-Disposition", String("attachment; filename=\\\"") + filename + "\\\"");
  server.sendHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
  server.setContentLength(header.crc_offset + sizeof(crc));
  server.send(200, "application/octet-stream", "");

  bool ok = true;
  ok = ok && writeBytes(server, reinterpret_cast<const uint8_t*>(&header), sizeof(header));
  ok = ok && writeBytes(server, reinterpret_cast<const uint8_t*>(metadata.c_str()), metadata.length());
  ok = ok && writeBytes(server, reinterpret_cast<const uint8_t*>(samples_), sample_count_ * sizeof(LogSample));
  ok = ok && writeBytes(server, reinterpret_cast<const uint8_t*>(&crc), sizeof(crc));

  downloading_ = false;
  last_error_ = ok ? "" : "rwlog_stream_failed";
  return ok;
}"""

assert 'server_->on("/download/rwlog", HTTP_GET, [this]() { handleRwLog(); });' in web
assert "static constexpr size_t STREAM_CHUNK_BYTES = 4096;" in logger
assert extract_function(web, "void WebUi::handleRwLog()") == expected_handle
assert extract_function(logger, "bool PsramLogger::writeBytes(") == expected_write
assert extract_function(logger, "bool PsramLogger::streamRwLog(") == expected_stream

print("RWLOG download freeze PASS: route, 4096-byte direct writer and stream path are unchanged")
