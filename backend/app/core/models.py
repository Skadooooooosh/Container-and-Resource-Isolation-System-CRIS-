from __future__ import annotations
import os
import re
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from app.core.compat import get_euid

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,38}$")


class Limits(BaseModel):
    cpu_quota_percent: Optional[float] = Field(None, ge=1, le=400, description="100 = one full CPU of bandwidth")
    memory_mb: Optional[int] = Field(None, ge=8, le=2048)
    pids_max: Optional[int] = Field(None, ge=2, le=512)

    def any(self) -> bool:
        return any(v is not None for v in (self.cpu_quota_percent, self.memory_mb, self.pids_max))


class Namespaces(BaseModel):
    pid: bool = True
    mnt: bool = True
    uts: bool = True
    ipc: bool = True
    net: bool = True
    user: bool = Field(default_factory=lambda: get_euid() != 0 if get_euid() is not None else False)

    def to_arg(self) -> str:
        return ",".join(n for n in ("pid", "mnt", "uts", "ipc", "net", "user") if getattr(self, n))


class ContainerCreate(BaseModel):
    name: str
    limits: Limits = Field(default_factory=Limits)
    namespaces: Namespaces = Field(default_factory=Namespaces)

    @model_validator(mode="after")
    def _name(self):
        if not NAME_RE.match(self.name):
            raise ValueError("name must match [A-Za-z0-9][A-Za-z0-9_-]{0,38}")
        return self


class WorkloadType(str, Enum):
    cpu = "cpu"
    memory = "memory"
    process = "process"
    mixed = "mixed"
    idle = "idle"
    nsinfo = "nsinfo"


class WorkloadSpec(BaseModel):
    type: WorkloadType
    seconds: int = Field(10, ge=1, le=120, description="wall-clock cap / hold time")
    iterations: int = Field(300_000_000, ge=1000, le=4_000_000_000)
    memory_mb: int = Field(64, ge=1, le=512)
    procs: int = Field(8, ge=1, le=64)


class LimitsUpdate(Limits):
    pass
