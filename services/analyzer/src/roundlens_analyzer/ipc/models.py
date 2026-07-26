from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from roundlens_analyzer import PROTOCOL_VERSION


class RpcRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: int = Field(default=PROTOCOL_VERSION)
    id: str = Field(min_length=1, max_length=100)
    method: str = Field(min_length=1, max_length=100)
    params: dict[str, Any] = Field(default_factory=dict)


class RpcError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
