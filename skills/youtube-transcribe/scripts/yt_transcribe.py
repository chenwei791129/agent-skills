#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "numpy",
#   "mlx-whisper; sys_platform == 'darwin' and platform_machine == 'arm64'",
#   "faster-whisper; sys_platform != 'darwin' or platform_machine != 'arm64'",
# ]
# ///
"""Transcribe a YouTube video (or local audio/video file) into text.

Pipeline: yt-dlp downloads the audio track, the audio is normalized to a
16 kHz mono WAV (via ffmpeg if present, otherwise macOS `afconvert`), and the
decoded samples are fed to the whisper engine as a raw numpy array. Handing the
engine a decoded array means it never has to shell out to ffmpeg itself, which
is the usual reason transcription dies on a machine that has no ffmpeg.

The transcription engine is chosen by platform so the skill is portable:
  - Apple Silicon (Darwin + arm64) -> mlx-whisper (MLX/Metal, GPU-accelerated)
  - everything else                -> faster-whisper (CTranslate2, CPU/CUDA)

The PEP 723 dependency markers above mean `uv` installs ONLY the engine that
matches the current platform, so there is no wasted download.

Run with `uv run` so the right engine + numpy are provisioned automatically:

    uv run yt_transcribe.py "https://www.youtube.com/watch?v=ID"
    uv run yt_transcribe.py /path/to/local.m4a --language zh
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

# Each engine wants its model named in its own convention. mlx-whisper pulls
# from the mlx-community HF org; faster-whisper resolves short names to the
# Systran CTranslate2 repos. Users can override with --model (they own
# compatibility with whichever engine the platform selects).
DEFAULT_MODELS = {
    "mlx": "mlx-community/whisper-large-v3-turbo",
    "faster": "large-v3-turbo",
}

# Format 140 is YouTube's 128 kbps m4a audio-only stream. It downloads without
# solving the player JS "n" challenge, so we avoid --remote-components (which
# fetches and runs remote code, and is commonly blocked by sandboxes).
AUDIO_FORMAT = "bestaudio[ext=m4a]/bestaudio"


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _select_engine() -> str:
    """Pick the transcription engine that matches this platform."""
    if sys.platform == "darwin" and platform.machine() == "arm64":
        return "mlx"
    return "faster"


def _pick_js_runtime() -> str | None:
    """Return a `--js-runtimes` value for a runtime that is actually installed.

    Recent yt-dlp needs a JavaScript runtime to extract YouTube. Only Deno is
    enabled by default; if the user has node or bun instead we point yt-dlp at
    it explicitly so extraction does not silently fall back to broken formats.
    """
    for runtime in ("deno", "node", "bun"):
        if shutil.which(runtime):
            return runtime
    return None


def _download_audio(url: str, dest_dir: Path) -> tuple[Path, str | None]:
    """Download the audio track of `url` into `dest_dir`.

    Returns (audio_path, title). Title is None if the info JSON is unavailable.
    """
    yt_dlp = ["yt-dlp"] if shutil.which("yt-dlp") else ["uvx", "yt-dlp"]
    cmd = [
        *yt_dlp,
        "-f",
        AUDIO_FORMAT,
        "--write-info-json",
        "--no-playlist",
        "-o",
        str(dest_dir / "%(id)s.%(ext)s"),
    ]
    runtime = _pick_js_runtime()
    if runtime:
        cmd[len(yt_dlp) : len(yt_dlp)] = ["--js-runtimes", runtime]
    cmd.append(url)

    _eprint(f"[1/3] Downloading audio with {' '.join(yt_dlp)} ...")
    subprocess.run(cmd, check=True)

    info_files = list(dest_dir.glob("*.info.json"))
    title = None
    if info_files:
        try:
            info = json.loads(info_files[0].read_text())
            title = info.get("title")
        except (json.JSONDecodeError, OSError):
            pass

    audio_files = [
        p
        for p in dest_dir.iterdir()
        if p.is_file() and not p.name.endswith(".info.json")
    ]
    if not audio_files:
        raise RuntimeError("yt-dlp produced no audio file")
    return audio_files[0], title


def _to_wav(src: Path, dest_dir: Path) -> Path:
    """Convert `src` to a 16 kHz mono 16-bit WAV that whisper can read directly."""
    wav_path = dest_dir / (src.stem + ".16k.wav")
    if shutil.which("ffmpeg"):
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(wav_path),
        ]
    elif shutil.which("afconvert"):
        # macOS built-in; no extra install needed.
        cmd = [
            "afconvert",
            "-f",
            "WAVE",
            "-d",
            "LEI16@16000",
            "-c",
            "1",
            str(src),
            str(wav_path),
        ]
    else:
        raise RuntimeError(
            "Need ffmpeg or afconvert to convert audio. "
            "On macOS afconvert ships with the OS; otherwise install ffmpeg."
        )
    _eprint(f"[2/3] Converting to 16 kHz mono WAV via {cmd[0]} ...")
    subprocess.run(
        cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return wav_path


def _load_wav(wav_path: Path):
    import numpy as np

    with wave.open(str(wav_path)) as w:
        if w.getframerate() != 16000 or w.getnchannels() != 1:
            raise RuntimeError("WAV must be 16 kHz mono (conversion step failed)")
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def _transcribe_mlx(audio, model: str, language: str | None) -> dict:
    """Transcribe with mlx-whisper and normalize to the common result shape."""
    import mlx_whisper

    r = mlx_whisper.transcribe(
        audio, path_or_hf_repo=model, language=language, verbose=False
    )
    return {
        "text": r["text"],
        "language": r.get("language", "unknown"),
        "segments": [
            {"start": s["start"], "end": s["end"], "text": s["text"]}
            for s in r["segments"]
        ],
    }


def _transcribe_faster(audio, model: str, language: str | None) -> dict:
    """Transcribe with faster-whisper and normalize to the common result shape.

    device/compute_type "auto" lets CTranslate2 pick CUDA when available and
    fall back to an efficient int8 CPU path otherwise.
    """
    from faster_whisper import WhisperModel

    m = WhisperModel(model, device="auto", compute_type="auto")
    # `segments` is a lazy generator; iterating it is what actually runs inference.
    segments, info = m.transcribe(audio, language=language)
    seg_list = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
    return {
        "text": "".join(s["text"] for s in seg_list),
        "language": info.language,
        "segments": seg_list,
    }


def _format_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _write_outputs(result: dict, out_base: Path, formats: set[str]) -> list[Path]:
    written = []
    if "txt" in formats:
        p = out_base.with_suffix(".txt")
        p.write_text(result["text"].strip() + "\n")
        written.append(p)
    if "srt" in formats:
        p = out_base.with_suffix(".srt")
        with p.open("w") as f:
            for i, seg in enumerate(result["segments"], 1):
                f.write(
                    f"{i}\n"
                    f"{_format_timestamp(seg['start'])} --> {_format_timestamp(seg['end'])}\n"
                    f"{seg['text'].strip()}\n\n"
                )
        written.append(p)
    if "json" in formats:
        p = out_base.with_suffix(".json")
        p.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        written.append(p)
    return written


def transcribe(args: argparse.Namespace) -> int:
    source = args.source
    is_url = source.startswith(("http://", "https://"))
    out_dir = Path(args.output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    engine = _select_engine()
    model = args.model or DEFAULT_MODELS[engine]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        if is_url:
            audio_path, title = _download_audio(source, tmp_dir)
            default_name = audio_path.stem
        else:
            audio_path = Path(source).expanduser().resolve()
            if not audio_path.exists():
                _eprint(f"File not found: {audio_path}")
                return 1
            title = None
            default_name = audio_path.stem

        wav_path = _to_wav(audio_path, tmp_dir)
        audio = _load_wav(wav_path)

        _eprint(f"[3/3] Transcribing with {engine}-whisper ({model}) ...")
        if engine == "mlx":
            result = _transcribe_mlx(audio, model, args.language)
        else:
            result = _transcribe_faster(audio, model, args.language)

    out_base = out_dir / (args.output_name or default_name)
    formats = {f.strip() for f in args.formats.split(",") if f.strip()}
    written = _write_outputs(result, out_base, formats)

    if title:
        _eprint(f"Title: {title}")
    _eprint(f"Detected language: {result['language']}")
    _eprint(f"Segments: {len(result['segments'])}")
    _eprint("Wrote:")
    for p in written:
        _eprint(f"  {p}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Transcribe a YouTube video or local audio/video file. Uses "
            "mlx-whisper on Apple Silicon, faster-whisper elsewhere."
        ),
    )
    parser.add_argument(
        "source", help="YouTube URL or path to a local audio/video file"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Whisper model. Defaults to a turbo model appropriate for the "
        "selected engine. Must be compatible with the platform's engine.",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Language code to force (e.g. zh, en). Omit to auto-detect.",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Where to write outputs (default: current dir)",
    )
    parser.add_argument(
        "--output-name",
        default=None,
        help="Base filename for outputs (default: video id / source filename)",
    )
    parser.add_argument(
        "--formats",
        default="txt,srt,json",
        help="Comma-separated output formats: txt, srt, json (default: all three)",
    )
    args = parser.parse_args()
    return transcribe(args)


def _handle_sigterm(signum, frame):
    sys.exit(128 + signum)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except subprocess.CalledProcessError as exc:
        _eprint(f"Subprocess failed ({exc.returncode}): {' '.join(map(str, exc.cmd))}")
        sys.exit(1)
