"""Vmake AI SDK - Core algorithm execution library."""

__version__ = "1.3.0"

# 설치 파이썬에 부품이 없는 옛 설치본 — 엔진 업데이트에 같이 온 _vendor 를 쓴다(재설치 없이 VMake 동작, 관제 290)
import importlib.util as _iu
import pathlib as _pl
import sys as _sys

_vendor = _pl.Path(__file__).resolve().parents[2] / "_vendor"
if _vendor.is_dir() and _iu.find_spec("alibabacloud_oss_v2") is None:
    _sys.path.append(str(_vendor))

from .core.api import AiApi
from .core.client import SkillClient, WapiClient, WapiApiError, ConsumeDeniedError
from .core.models import TaskResult, UploadResult, TaskStatus
from .cli.runner import TaskRunner
from .utils.cache import GidCache

__all__ = [
    "AiApi",
    "SkillClient",
    "WapiClient",
    "WapiApiError",
    "ConsumeDeniedError",
    "TaskRunner",
    "TaskResult",
    "UploadResult",
    "TaskStatus",
    "GidCache",
]
