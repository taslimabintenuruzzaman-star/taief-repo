"""Live/offline diagnostic suite for MOROS AGI core."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from moros_agi_core.config.settings import ACTIVE_HW_PROFILE, HardwareProfile, get_settings
from moros_agi_core.src.avatar_sync import FaceTelemetry, phonemes_for, telemetry_from
from moros_agi_core.src.core_brain import split_tags
from moros_agi_core.src.smart_router import TaskClassifier, TaskKind
from moros_agi_core.src.voice_synthesis import FRAME_BYTES, MICRO_PAUSE_SEC, VoiceSynthesis


def _ok(name: str) -> None:
    print(f"\033[32mPASS\033[0m  {name}")


def _fail(name: str, err: str) -> None:
    print(f"\033[31mFAIL\033[0m  {name} :: {err}")
    raise AssertionError(f"{name}: {err}")


def test_hardware_profile() -> None:
    assert isinstance(ACTIVE_HW_PROFILE, HardwareProfile)
    assert ACTIVE_HW_PROFILE.backend in {"cuda", "vulkan", "cpu"}
    if ACTIVE_HW_PROFILE.backend == "cuda":
        assert ACTIVE_HW_PROFILE.vram_limit_gb <= 11.5
        assert ACTIVE_HW_PROFILE.num_ctx == 4096
    if ACTIVE_HW_PROFILE.backend == "vulkan":
        assert ACTIVE_HW_PROFILE.vram_limit_gb <= 7.5
        assert ACTIVE_HW_PROFILE.num_ctx == 2048
    settings = get_settings()
    assert settings.ws_port == 8765
    assert settings.micro_pause_sec == 0.45
    _ok("hardware + settings")


def test_classifier() -> None:
    clf = TaskClassifier()
    assert clf.classify("```python\nprint(1)\n```") is TaskKind.CODE
    assert clf.classify("debug this JSON payload") is TaskKind.CODE
    assert clf.classify("You woke me again, Taief") is TaskKind.PERSONA
    _ok("task classifier")


def test_tag_parser() -> None:
    clean, tags = split_tags("[breath] Hello [micro-pause] world [dark chuckle]")
    assert "Hello" in clean and "world" in clean
    assert "breath" in tags and "micro-pause" in tags and "dark chuckle" in tags
    assert "[" not in clean
    _ok("core brain tag parser")


def test_voice_frames() -> None:
    voice = VoiceSynthesis()
    assert abs(MICRO_PAUSE_SEC - 0.45) < 1e-9
    pause = voice.silence_pcm(0.45)
    assert len(pause) == int(voice.sample_rate * 0.45) * 2
    assert len(voice.align_ratecv_frame(b"\x00" * 398)) == FRAME_BYTES
    assert len(voice.align_ratecv_frame(b"\x00" * 400)) == FRAME_BYTES
    whispered = voice.apply_whisper(b"\x00\x10\x00\x20")
    assert len(whispered) == 4
    _ok("voice frames / micro-pause 0.45s")


def test_avatar_schema() -> None:
    face = telemetry_from("aeiou m f", ["whisper", "glitch"])
    FaceTelemetry.model_validate(face.model_dump())
    assert face.lip_sync_phonemes
    assert phonemes_for("map") == ["M", "A", "M"]
    _ok("avatar pydantic schema")


async def test_router_offline_chain() -> None:
    from moros_agi_core.src.smart_router import ProviderError, SmartRouter

    router = SmartRouter()
    try:
        await router.complete("ping")
        _ok("router completed via a live provider")
    except ProviderError:
        _ok("router failover exhausted cleanly (no keys/ollama in this environment)")
    finally:
        await router.aclose()


def test_no_hardcoded_secrets() -> None:
    text = (ROOT / "moros_agi_core" / "config" / "settings.py").read_text(encoding="utf-8")
    banned = ("sk-or-v1-", "hf_Q", "AIzaSy")
    for token in banned:
        if token in text:
            _fail("secret leak", f"found {token} in settings.py")
    _ok("no hardcoded credentials")


def main() -> int:
    print("MOROS live diagnostic")
    tests = [
        test_hardware_profile,
        test_classifier,
        test_tag_parser,
        test_voice_frames,
        test_avatar_schema,
        test_no_hardcoded_secrets,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
        except Exception as exc:
            failed += 1
            print(f"\033[31mFAIL\033[0m  {fn.__name__} :: {exc}")
    try:
        asyncio.run(test_router_offline_chain())
    except Exception as exc:
        failed += 1
        print(f"\033[31mFAIL\033[0m  router :: {exc}")
    print(f"\n{len(tests) + 1 - failed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
