"""Portable change witnesses for memoized file hashes; stdlib only."""
import os
import time
from functools import lru_cache

#: 바뀐 시각이 잰 시각보다 이만큼 앞서야 «가라앉은» 증거로 믿는다(10-23 · git 의 racy-clean 과 같은 까닭).
#:   파일 시각은 시계 눈금 단위로 찍힌다(NTFS 는 시스템 시계 눈금 약 15.6ms · HFS+ 1초 · FAT 2초). 잰 그 눈금 안에서 같은 크기로
#:   다시 쓰고 수정 시각을 되돌리면 바뀐 시각까지 같아 증거가 못 가른다 — win-main 에서 시험이 실제로 그렇게 한 번 놓쳤다.
#:   가장 굵은 눈금(FAT 2초)보다 길게 둔다. 그 안에 바뀐 파일은 다음에도 해시를 다시 잰다.
SETTLE_NS = 3_000_000_000
#: 윈도우 FILETIME(1601-01-01 부터 100ns) → 1970 부터 ns
_FILETIME_EPOCH = 116444736000000000


def now_ns():
    return time.time_ns()


@lru_cache(maxsize=1)
def _windows_metadata_api():
    """Real metadata ChangeTime, never Python's Windows creation-time ctime.

    https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_basic_info
    https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex
    Unsupported filesystems/API failures return None: hashes cannot be memoized.
    """
    import ctypes
    from ctypes import wintypes
    class BasicInfo(ctypes.Structure):
        _fields_=[('CreationTime',ctypes.c_longlong),('LastAccessTime',ctypes.c_longlong),
                  ('LastWriteTime',ctypes.c_longlong),('ChangeTime',ctypes.c_longlong),
                  ('FileAttributes',wintypes.DWORD)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype=wintypes.HANDLE
    kernel.GetFileInformationByHandleEx.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    kernel.GetFileInformationByHandleEx.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    return kernel,BasicInfo


def _windows_change_time(path):
    import ctypes
    try:kernel,BasicInfo=_windows_metadata_api()
    except (AttributeError,OSError):return None
    handle=kernel.CreateFileW(str(path),0x80,7,None,3,0x02000000,None)
    if handle==ctypes.c_void_p(-1).value:return None
    try:
        value=BasicInfo()
        if not kernel.GetFileInformationByHandleEx(handle,0,ctypes.byref(value),ctypes.sizeof(value)):return None
        return (value.ChangeTime-_FILETIME_EPOCH)*100 if value.ChangeTime>0 else None
    finally:kernel.CloseHandle(handle)


def stamp(path):
    value=path.stat()
    changed=_windows_change_time(path) if os.name=='nt' else value.st_ctime_ns
    return [value.st_size,value.st_mtime_ns,value.st_ctime_ns,value.st_ino,value.st_dev,changed]


def memoizable(value):
    """이 증거로 해시를 건너뛰어도 되나 — 바뀐 시각이 있고, 잰 지금보다 SETTLE_NS 넘게 앞서야(같은 눈금 안 변경을 못 가른다)."""
    return value[-1] is not None and now_ns()-value[-1] > SETTLE_NS
