#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace rwlog_http_range {
enum Status : uint8_t { NONE = 0, VALID = 1, INVALID = 2, UNSATISFIABLE = 3 };
struct Result {
  Status status = NONE;
  size_t start = 0;
  size_t end = 0;  // inclusive
};

inline bool parseUnsigned(const char* begin, const char* end, size_t* out) {
  if (!begin || !end || begin >= end || !out) return false;
  size_t value = 0;
  for (const char* p = begin; p < end; ++p) {
    if (*p < '0' || *p > '9') return false;
    const size_t digit = static_cast<size_t>(*p - '0');
    if (value > (static_cast<size_t>(-1) - digit) / 10U) return false;
    value = value * 10U + digit;
  }
  *out = value;
  return true;
}

inline Result parse(const char* raw, size_t total_size) {
  Result r;
  if (!raw || !*raw) return r;
  if (total_size == 0) { r.status = UNSATISFIABLE; return r; }
  static constexpr char kPrefix[] = "bytes=";
  if (std::strncmp(raw, kPrefix, sizeof(kPrefix) - 1) != 0) {
    r.status = INVALID; return r;
  }
  const char* spec = raw + sizeof(kPrefix) - 1;
  if (std::strchr(spec, ',')) { r.status = INVALID; return r; }
  const char* dash = std::strchr(spec, '-');
  if (!dash) { r.status = INVALID; return r; }
  const char* endp = spec + std::strlen(spec);

  // Suffix range: bytes=-N
  if (dash == spec) {
    size_t suffix = 0;
    if (!parseUnsigned(dash + 1, endp, &suffix) || suffix == 0) {
      r.status = INVALID; return r;
    }
    r.start = suffix >= total_size ? 0 : total_size - suffix;
    r.end = total_size - 1;
    r.status = VALID;
    return r;
  }

  size_t start = 0;
  if (!parseUnsigned(spec, dash, &start)) { r.status = INVALID; return r; }
  if (start >= total_size) { r.status = UNSATISFIABLE; return r; }

  size_t end = total_size - 1;
  if (dash + 1 < endp) {
    if (!parseUnsigned(dash + 1, endp, &end) || end < start) {
      r.status = INVALID; return r;
    }
    if (end >= total_size) end = total_size - 1;
  }

  r.start = start;
  r.end = end;
  r.status = VALID;
  return r;
}
}  // namespace rwlog_http_range
