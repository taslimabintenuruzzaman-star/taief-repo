"""Runtime hardware profiling and environment-backed credentials."""

from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BackendName = Literal["cuda", "vulkan", "cpu"]


class HardwareProfile(BaseModel):
    """Snapshot of the active accelerator."""

    model_config = ConfigDict(frozen=True)

    backend: BackendName = "cpu"
    device_name: str = "cpu"
    vram_limit_gb: float = 0.0
    num_ctx: int = 2048
    cuda_available: bool = False


def _nvidia_smi_name() -> str | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [exe, "--query-gpu=name", "--format=csv,noheader"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    line = (proc.stdout or "").strip().splitlines()
    return line[0].strip() if line else None


def _looks_like_arc() -> bool:
    probes = (
        "vulkaninfo",
        "clinfo",
    )
    blob = ""
    for name in probes:
        exe = shutil.which(name)
        if not exe:
            continue
        try:
            proc = subprocess.run(
                [exe],
                check=False,
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            blob += (proc.stdout or "") + (proc.stderr or "")
        except (OSError, subprocess.TimeoutExpired):
            continue
    lowered = blob.lower()
    return "arc a750" in lowered or "intel" in lowered and "arc" in lowered


def detect_hardware() -> HardwareProfile:
    """Pick CUDA (RTX 3060 class) vs Vulkan (Arc A750 class) vs CPU."""
    cuda = False
    torch_name = ""
    try:
        import torch  # type: ignore

        cuda = bool(torch.cuda.is_available())
        if cuda:
            torch_name = torch.cuda.get_device_name(0)
    except Exception:
        cuda = False

    smi_name = _nvidia_smi_name() or ""
    name = torch_name or smi_name

    if cuda or smi_name:
        return HardwareProfile(
            backend="cuda",
            device_name=name or "NVIDIA CUDA GPU",
            vram_limit_gb=11.5,
            num_ctx=4096,
            cuda_available=True,
        )
    if _looks_like_arc() or os.environ.get("MOROS_FORCE_VULKAN") == "1":
        return HardwareProfile(
            backend="vulkan",
            device_name="Intel Arc A750 (Vulkan)",
            vram_limit_gb=7.5,
            num_ctx=2048,
            cuda_available=False,
        )
    return HardwareProfile(
        backend="cpu",
        device_name="cpu",
        vram_limit_gb=0.0,
        num_ctx=2048,
        cuda_available=False,
    )


ACTIVE_HW_PROFILE: HardwareProfile = detect_hardware()


class Settings(BaseSettings):
    """All secrets load from the environment. None are hardcoded."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    huggingface_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    hive_api_key: SecretStr | None = None
    hive_access_id: str = ""
    hive_base_url: str = "https://api.thehive.ai"
    openrouter_api_key: SecretStr | None = None
    openrouter_api_key_secondary: SecretStr | None = None
    groq_api_key: SecretStr | None = None

    ollama_host: str = "http://127.0.0.1:11434"
    ollama_persona_model: str = "llama3.1:8b"
    ollama_code_model: str = "qwen2.5:7b"
    ollama_keep_alive: str = "5m"

    hf_model: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    gemini_model: str = "gemini-2.5-flash"
    gemini_model_pro: str = "gemini-2.5-pro"
    hive_model: str = "hive/llama-3.1-8b-instruct"
    openrouter_model: str = "google/gemma-4-31b-it:free"
    openrouter_model_secondary: str = "google/gemma-4-26b-a4b-it:free"

    ws_host: str = "127.0.0.1"
    ws_port: int = 8765
    xtts_model: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    micro_pause_sec: float = Field(default=0.45, ge=0.05, le=2.0)
    sample_rate: int = 24000
    request_timeout_sec: float = 45.0

    operator_name: str = "Taief"

    def secret(self, value: SecretStr | None) -> str:
        if value is None:
            return ""
        return value.get_secret_value().strip()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
