---
name: youtube-transcribe
description: 'Transcribe a YouTube video (or any local audio/video file) into a text transcript, SRT subtitles, and JSON using whisper locally. Use this whenever the user shares a YouTube URL and wants its subtitles, captions, transcript, 字幕, or 逐字稿 — especially when the video has no captions to download — or wants to transcribe / 轉錄 an audio or video file. Triggers on requests like "幫我抓這部 YouTube 的字幕/逐字稿", "transcribe this video", "把這段音檔轉成文字". Runs locally and is cross-platform: mlx-whisper on Apple Silicon, faster-whisper elsewhere.'
---

# YouTube / Audio Transcription

Turn a YouTube video — or any local audio/video file — into a transcript without relying on YouTube-provided captions. Many videos (especially re-uploads and some Chinese-language uploads) have **no** subtitles and **no** auto-captions, so downloading captions with `yt-dlp --write-subs` returns nothing. This skill sidesteps that by downloading the audio and transcribing it locally with a whisper engine chosen by platform.

## When to reach for this

- The user gives a YouTube URL and wants the 字幕 / 逐字稿 / transcript / captions.
- `yt-dlp --list-subs` reports `has no subtitles` / `has no automatic captions`.
- The user has a local `.m4a`/`.mp3`/`.mp4`/etc. file to transcribe.

## Prerequisites

- `uv` installed (used to run `yt-dlp` and the transcription script without polluting the global env). The script auto-selects the whisper engine and `uv` installs only the one your platform needs:
  - **Apple Silicon Mac** → `mlx-whisper` (MLX/Metal, GPU-accelerated).
  - **Intel Mac / Linux / Windows** → `faster-whisper` (CTranslate2, CPU or NVIDIA CUDA).
- A JavaScript runtime — `node`, `bun`, or `deno` — on PATH. Recent yt-dlp needs one to extract YouTube; the script auto-detects whichever is present.
- ffmpeg recommended but **not** required: if absent, the script falls back to macOS's built-in `afconvert` (so on non-macOS, install ffmpeg).

## Usage

The whole pipeline is one self-contained script. Run it with `uv run` so dependencies are provisioned automatically:

```bash
uv run ~/.claude/skills/youtube-transcribe/scripts/yt_transcribe.py \
  "https://www.youtube.com/watch?v=VIDEO_ID" \
  --output-dir /tmp/whisper_out
```

Common options:

- `--language zh` — force a language instead of auto-detecting (faster, avoids mis-detection on bilingual intros).
- `--model mlx-community/whisper-large-v3-turbo` — the default; good speed/quality on Apple Silicon. Swap for `mlx-community/whisper-large-v3` for max quality or a smaller model for speed.
- `--output-name my-video` — base filename for outputs (defaults to the video id).
- `--formats txt,srt` — pick which outputs to write (default `txt,srt,json`).

A local file works the same way — just pass a path instead of a URL:

```bash
uv run ~/.claude/skills/youtube-transcribe/scripts/yt_transcribe.py /path/to/talk.m4a --language en
```

The first run downloads the whisper model (~1.6 GB for turbo) into the Hugging Face cache; later runs reuse it.

## Outputs

Written to `--output-dir` (default: current directory), named after the video id (or `--output-name`):

- `<name>.txt` — plain-text transcript (one blob).
- `<name>.srt` — subtitles with timestamps.
- `<name>.json` — full result incl. per-segment timestamps and detected language.

## After transcribing

The raw whisper output reflects the spoken language verbatim. If the audio is Mandarin, whisper emits **Simplified** Chinese. Per the user's global rule, when presenting the transcript in chat, convert it to **正體中文 (Traditional)** and clean up obvious mis-hearings of proper nouns / technical terms (model names, CVE ids, tool names). Offer a tidied, sectioned summary rather than dumping the full wall of text, and tell the user where the full files live.

## How it works (and why)

1. **Download audio** — `yt-dlp -f "bestaudio[ext=m4a]/bestaudio"`. Format 140 (128 kbps m4a) downloads without solving YouTube's player JS "n" challenge, so we **avoid** `--remote-components ejs:github` (it fetches+runs remote code and is typically blocked by the sandbox). The script prefixes `uvx` if `yt-dlp` isn't installed, and adds `--js-runtimes <node|bun|deno>` for whichever runtime exists.
2. **Normalize audio** — convert to 16 kHz mono 16-bit WAV with ffmpeg, or macOS `afconvert` if ffmpeg is missing.
3. **Transcribe** — read the WAV into a numpy float32 array and pass it straight to the engine (`mlx_whisper.transcribe(...)` on Apple Silicon, `faster_whisper.WhisperModel.transcribe(...)` elsewhere). Both produce the same normalized result shape (`text` / `language` / `segments`). Handing whisper a decoded array means it never shells out to ffmpeg internally — which is the usual cause of `FileNotFoundError: ffmpeg` on machines without it.

## Troubleshooting

- **`has no subtitles` but you still want text** — that's exactly this skill's job; proceed to transcribe the audio.
- **`FileNotFoundError: ffmpeg`** — shouldn't happen via this script (it converts first), but if you call the whisper engine directly on an m4a, convert to WAV first.
- **On non-Apple-Silicon and conversion fails** — `afconvert` is macOS-only, so install `ffmpeg` (Linux/Windows have no built-in fallback).
- **yt-dlp warns about JS challenge / "Only images are available"** — ensure `node`/`bun`/`deno` is on PATH; the script needs one for extraction. Do **not** reach for `--remote-components ejs:github` to fix it.
- **Garbled / wrong-language output** — pass `--language` explicitly.
