#!/usr/bin/env python3
"""Local ASR CLI built on faster-whisper (no API key, runs on CPU).

Usage:
    python transcribe.py AUDIO [--language zh] [--model DIR] [--out DIR]
                                [--format srt,json,txt] [--compute-type int8]

Outputs land next to the input by default: <stem>.srt / <stem>.json / <stem>.txt
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def fmt_ts(seconds: float, sep: str = ",") -> str:
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def write_srt(segments: list[dict], path: Path) -> None:
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{fmt_ts(seg['start'])} --> {fmt_ts(seg['end'])}")
        lines.append(seg["text"].strip())
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Transcribe audio/video with faster-whisper")
    ap.add_argument("audio", help="input audio or video file")
    ap.add_argument("--model", default=os.environ.get("ASR_MODEL_DIR", ""),
                    help="local model directory (default: $ASR_MODEL_DIR)")
    ap.add_argument("--language", default=None,
                    help="force language code (zh/en/...); default auto-detect")
    ap.add_argument("--out", default=None, help="output directory (default: alongside input)")
    ap.add_argument("--format", default="srt,json", help="comma list of srt,json,txt")
    ap.add_argument("--compute-type", default="int8", help="int8 / int8_float32 / float32")
    ap.add_argument("--threads", type=int, default=0, help="cpu threads (0 = auto)")
    ap.add_argument("--beam-size", type=int, default=5)
    ap.add_argument("--no-vad", action="store_true", help="disable VAD silence filtering")
    args = ap.parse_args()

    src = Path(args.audio).expanduser()
    if not src.exists():
        print(f"[error] input not found: {src}", file=sys.stderr)
        return 2
    if not args.model:
        print("[error] no model directory given (use --model or $ASR_MODEL_DIR)", file=sys.stderr)
        return 2
    model_dir = Path(args.model).expanduser()
    if not model_dir.is_dir():
        print(f"[error] model dir missing: {model_dir}", file=sys.stderr)
        return 2

    from faster_whisper import WhisperModel  # imported late so --help stays fast

    t0 = time.time()
    model = WhisperModel(
        str(model_dir),
        device="cpu",
        compute_type=args.compute_type,
        cpu_threads=args.threads or (os.cpu_count() or 4),
    )
    segments_iter, info = model.transcribe(
        str(src),
        language=args.language,
        beam_size=args.beam_size,
        vad_filter=not args.no_vad,
        word_timestamps=False,
    )

    segments: list[dict] = []
    for seg in segments_iter:
        segments.append({
            "id": len(segments) + 1,
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
            "avg_logprob": round(getattr(seg, "avg_logprob", 0.0) or 0.0, 4),
            "no_speech_prob": round(getattr(seg, "no_speech_prob", 0.0) or 0.0, 4),
        })

    out_dir = Path(args.out).expanduser() if args.out else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = src.stem
    wanted = {f.strip().lower() for f in args.format.split(",") if f.strip()}
    written = []

    if "srt" in wanted:
        p = out_dir / f"{stem}.srt"
        write_srt(segments, p)
        written.append(p)
    if "txt" in wanted:
        p = out_dir / f"{stem}.txt"
        p.write_text("\n".join(s["text"] for s in segments), encoding="utf-8")
        written.append(p)
    if "json" in wanted:
        p = out_dir / f"{stem}.json"
        p.write_text(json.dumps({
            "source": str(src),
            "model": str(model_dir),
            "language": info.language,
            "language_probability": round(info.language_probability, 4),
            "duration": round(info.duration, 3),
            "elapsed_sec": round(time.time() - t0, 2),
            "segment_count": len(segments),
            "segments": segments,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(p)

    for p in written:
        print(f"[out] {p}")
    print(f"[done] {len(segments)} segments · lang={info.language} "
          f"({info.language_probability:.2f}) · audio={info.duration:.1f}s · "
          f"elapsed={time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
