"""模型配置。优先使用 Cielo 里的火山方舟，其次 DeepSeek，再次百炼。"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    label: str
    api_key: str
    base_url: str
    model: str


def current_model() -> ModelConfig | None:
    ark_key = _first("ARK_API_KEY", "CIELO_API_KEY")
    if ark_key:
        return ModelConfig(
            provider="ark",
            label="火山方舟（Cielo）",
            api_key=ark_key,
            base_url=_first("ARK_BASE_URL", "CIELO_BASE_URL")
            or "https://ark.cn-beijing.volces.com/api/v3",
            model=_first("ARK_MODEL", "CIELO_MODEL") or "doubao-seed-2-1-pro-260915",
        )
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if deepseek_key:
        return ModelConfig(
            provider="deepseek",
            label="DeepSeek",
            api_key=deepseek_key,
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "").strip() or "https://api.deepseek.com",
            model=os.environ.get("DEEPSEEK_MODEL", "").strip() or "deepseek-chat",
        )
    dashscope_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if dashscope_key:
        return ModelConfig(
            provider="dashscope",
            label="百炼",
            api_key=dashscope_key,
            base_url=os.environ.get("DASHSCOPE_BASE_URL", "").strip()
            or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            model=os.environ.get("DASHSCOPE_MODEL", "").strip() or "qwen3.5-122b-a10b",
        )
    return None


def provider_label() -> str:
    config = current_model()
    if config is None:
        return "未配置密钥，使用本地匹配"
    return f"{config.label} · {config.model}"


def _first(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""
