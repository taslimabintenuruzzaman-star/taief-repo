"""Async orchestrator: classifier → router → brain → voice → avatar."""

from __future__ import annotations

import argparse
import asyncio
import signal
from pathlib import Path

from moros_agi_core.config.settings import ACTIVE_HW_PROFILE, get_settings
from moros_agi_core.src.avatar_sync import AvatarSync, telemetry_from
from moros_agi_core.src.core_brain import CoreBrain, split_tags
from moros_agi_core.src.smart_router import SmartRouter
from moros_agi_core.src.utils import empty_cuda_cache
from moros_agi_core.src.voice_synthesis import VoiceSynthesis


async def run_once(prompt: str, speak: bool) -> str:
    settings = get_settings()
    router = SmartRouter(settings)
    brain = CoreBrain(router)
    voice = VoiceSynthesis()
    avatar = AvatarSync()
    try:
        await avatar.start()
        result = await brain.reply(prompt)
        _, tags = split_tags(result.text)
        await avatar.publish(telemetry_from(result.text, tags))
        if speak:
            pcm = await voice.render(result.text, tags)
            out = Path("audio_output") / "last.wav"
            voice.write_wav(pcm, out)
        return result.text
    finally:
        await avatar.stop()
        await router.aclose()
        empty_cuda_cache()


async def repl() -> None:
    settings = get_settings()
    router = SmartRouter(settings)
    brain = CoreBrain(router)
    voice = VoiceSynthesis()
    avatar = AvatarSync()
    await avatar.start()
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _halt() -> None:
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _halt)
        except NotImplementedError:
            pass

    print(
        f"MOROS core online  backend={ACTIVE_HW_PROFILE.backend} "
        f"ctx={ACTIVE_HW_PROFILE.num_ctx} vram_cap={ACTIVE_HW_PROFILE.vram_limit_gb}GB"
    )
    print("Type a prompt. Ctrl+C to exit.")
    try:
        while not stop.is_set():
            try:
                line = await asyncio.to_thread(input, "taief> ")
            except EOFError:
                break
            if not line.strip():
                continue
            result = await brain.reply(line)
            print(f"[{result.provider.value}/{result.model}] {result.text}")
            tags = []
            await avatar.publish(telemetry_from(result.text, tags))
            await voice.render(result.text, tags)
    finally:
        await avatar.stop()
        await router.aclose()
        empty_cuda_cache()


def main() -> None:
    parser = argparse.ArgumentParser(description="MOROS AGI core")
    parser.add_argument("--prompt", default="", help="single-shot prompt")
    parser.add_argument("--speak", action="store_true")
    args = parser.parse_args()
    if args.prompt:
        text = asyncio.run(run_once(args.prompt, args.speak))
        print(text)
        return
    asyncio.run(repl())


if __name__ == "__main__":
    main()
