"""
state_io.py — 원자적 JSON 쓰기 + filelock 헬퍼
- write_json(path, data): 임시파일 → os.replace 원자적 쓰기 (파일 손상 방지)
- lock(path): filelock.FileLock 컨텍스트; filelock 미설치 시 no-op 폴백
"""
import contextlib
import json
import os
import tempfile

try:
    import filelock as _filelock
    _FILELOCK_AVAILABLE = True
except ImportError:
    _FILELOCK_AVAILABLE = False

import config


def write_json(path, data):
    """data를 path에 원자적으로 저장 (임시파일→os.replace)."""
    dir_ = os.path.dirname(path)
    os.makedirs(dir_, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=None)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


@contextlib.contextmanager
def lock(path):
    """공유 자원용 파일 락. filelock 미설치 시 no-op."""
    if _FILELOCK_AVAILABLE:
        lk = _filelock.FileLock(path + ".lock", timeout=getattr(config, "LOCK_TIMEOUT", 5))
        with lk:
            yield
    else:
        yield
