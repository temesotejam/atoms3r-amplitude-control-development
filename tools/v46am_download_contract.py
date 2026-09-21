"""Reverse V46am download-only config identity before retained baseline hashes."""
def normalize_config(text: str) -> str:
    return text.replace(
        '\nstatic constexpr char RWLOG_DOWNLOAD_REVISION[] = "v46am_fetch_backpressure_20260921";',
        '',
    )

def normalize_file(path: str, text: str) -> str:
    if path == "src/config.h":
        return normalize_config(text)
    return text
