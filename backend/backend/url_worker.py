import json
import os
import re
import sys
import tempfile
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import imageio_ffmpeg
import requests
import trafilatura
import yt_dlp
from faster_whisper import WhisperModel

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:
    YouTubeTranscriptApi = None


WHISPER_MODEL = os.getenv("TUTOR_IA_WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("TUTOR_IA_WHISPER_DEVICE", "cpu")
VIDEO_AUDIO_FALLBACK = os.getenv("TUTOR_IA_VIDEO_AUDIO_FALLBACK", "0").lower() in {"1", "true", "yes", "si"}
VIDEO_MAX_SECONDS = int(os.getenv("TUTOR_IA_VIDEO_MAX_SECONDS", "1800"))

VIDEO_HOSTS = ("youtube.com", "youtu.be", "tiktok.com", "vimeo.com")
CAPTION_LANG_ORDER = ("es", "es-419", "es-mx", "en", "en-us")
CAPTION_EXT_ORDER = ("json3", "vtt", "srt", "srv3", "ttml")


def is_video_url(url):
    host = urlparse(url).netloc.lower()
    return any(video_host in host for video_host in VIDEO_HOSTS)


def extract_youtube_video_id(url):
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if host.endswith("youtu.be") and path_parts:
        return path_parts[0]

    if "youtube.com" not in host:
        return None

    video_id = parse_qs(parsed.query).get("v", [None])[0]
    if video_id:
        return video_id

    if len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live"}:
        return path_parts[1]
    return None


def compact_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def parse_timestamp(value):
    value = value.strip().replace(",", ".")
    parts = value.split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
    except ValueError:
        return 0.0
    return 0.0


def chunk_segments(segments, source, title, source_type="video", max_chars=1800):
    chunks = []
    current = []
    start_at = None
    end_at = None
    char_count = 0

    for segment in segments:
        text = compact_text(segment.get("text", ""))
        if not text:
            continue
        segment_start = float(segment.get("start", 0.0) or 0.0)
        segment_end = float(segment.get("end", segment_start) or segment_start)
        line = f"[{segment_start:.1f}s - {segment_end:.1f}s] {text}"

        if current and char_count + len(line) > max_chars:
            chunks.append({
                "text": "\n".join(current),
                "metadata": {
                    "source": source,
                    "type": source_type,
                    "title": title,
                    "start": start_at,
                    "end": end_at,
                },
            })
            current = []
            start_at = None
            end_at = None
            char_count = 0

        if start_at is None:
            start_at = segment_start
        end_at = segment_end
        current.append(line)
        char_count += len(line)

    if current:
        chunks.append({
            "text": "\n".join(current),
            "metadata": {
                "source": source,
                "type": source_type,
                "title": title,
                "start": start_at,
                "end": end_at,
            },
        })
    return chunks


def parse_json3_captions(payload):
    data = json.loads(payload)
    segments = []
    for event in data.get("events", []):
        texts = [seg.get("utf8", "") for seg in event.get("segs", [])]
        text = compact_text("".join(texts))
        if not text:
            continue
        start = float(event.get("tStartMs", 0) or 0) / 1000
        duration = float(event.get("dDurationMs", 0) or 0) / 1000
        segments.append({"start": start, "end": start + duration, "text": text})
    return segments


def parse_vtt_or_srt_captions(payload):
    payload = payload.replace("\r\n", "\n").replace("\r", "\n")
    payload = re.sub(r"^\ufeff?WEBVTT.*?\n", "", payload, flags=re.IGNORECASE)
    segments = []

    for block in re.split(r"\n\s*\n", payload):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        timing_idx = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_idx is None:
            continue

        timing = lines[timing_idx]
        left, right = timing.split("-->", 1)
        start = parse_timestamp(left)
        end = parse_timestamp(right.split()[0])
        text = " ".join(lines[timing_idx + 1:])
        text = re.sub(r"<[^>]+>", " ", text)
        text = compact_text(unescape(text))
        if text:
            segments.append({"start": start, "end": end, "text": text})
    return segments


def parse_srv_or_ttml_captions(payload):
    segments = []
    for match in re.finditer(r'<text[^>]*?start="([^"]+)"[^>]*?(?:dur="([^"]+)")?[^>]*>(.*?)</text>', payload, re.DOTALL):
        start = float(match.group(1) or 0)
        duration = float(match.group(2) or 0)
        text = re.sub(r"<[^>]+>", " ", match.group(3))
        text = compact_text(unescape(text))
        if text:
            segments.append({"start": start, "end": start + duration, "text": text})
    if segments:
        return segments

    for match in re.finditer(r"<p[^>]*?begin=\"([^\"]+)\"[^>]*?(?:end=\"([^\"]+)\")?[^>]*>(.*?)</p>", payload, re.DOTALL):
        start = parse_timestamp(match.group(1))
        end = parse_timestamp(match.group(2)) if match.group(2) else start
        text = re.sub(r"<[^>]+>", " ", match.group(3))
        text = compact_text(unescape(text))
        if text:
            segments.append({"start": start, "end": end, "text": text})
    return segments


def caption_rank(lang):
    lang = (lang or "").lower()
    for idx, preferred in enumerate(CAPTION_LANG_ORDER):
        if lang == preferred:
            return idx
    for idx, preferred in enumerate(CAPTION_LANG_ORDER):
        if lang.startswith(preferred.split("-")[0]):
            return idx + 20
    return 999


def choose_caption_track(info):
    candidates = []
    for caption_kind, caption_map in (
        ("subtitulos", info.get("subtitles") or {}),
        ("subtitulos automaticos", info.get("automatic_captions") or {}),
    ):
        for lang, tracks in caption_map.items():
            for track in tracks or []:
                url = track.get("url")
                ext = (track.get("ext") or "").lower()
                if not url:
                    continue
                ext_rank = CAPTION_EXT_ORDER.index(ext) if ext in CAPTION_EXT_ORDER else 999
                candidates.append((caption_rank(lang), 0 if caption_kind == "subtitulos" else 1, ext_rank, lang, ext, url, caption_kind))

    if not candidates:
        return None
    return sorted(candidates)[0]


def extract_video_captions(url, info):
    track = choose_caption_track(info)
    if not track:
        return []

    _, _, _, lang, ext, caption_url, caption_kind = track
    response = requests.get(caption_url, timeout=30, headers={"User-Agent": "TutorIA/1.0"})
    response.raise_for_status()
    payload = response.content.decode("utf-8", errors="replace")

    if ext == "json3":
        segments = parse_json3_captions(payload)
    elif ext in {"vtt", "srt"}:
        segments = parse_vtt_or_srt_captions(payload)
    else:
        segments = parse_srv_or_ttml_captions(payload)

    title = info.get("title") or url
    chunks = chunk_segments(segments, url, title)
    for chunk in chunks:
        chunk["metadata"]["caption_language"] = lang
        chunk["metadata"]["caption_kind"] = caption_kind
    return chunks


def extract_youtube_transcript(url):
    if YouTubeTranscriptApi is None:
        return []

    video_id = extract_youtube_video_id(url)
    if not video_id:
        return []

    api = YouTubeTranscriptApi()
    languages = ["es", "es-419", "es-mx", "en", "en-us"]
    try:
        transcript = api.fetch(video_id, languages=languages)
    except Exception:
        try:
            transcript_list = api.list(video_id)
            try:
                transcript = transcript_list.find_manually_created_transcript(languages).fetch()
            except Exception:
                transcript = transcript_list.find_generated_transcript(languages).fetch()
        except Exception:
            return []

    raw_segments = []
    for item in transcript:
        text = compact_text(getattr(item, "text", ""))
        start = float(getattr(item, "start", 0.0) or 0.0)
        duration = float(getattr(item, "duration", 0.0) or 0.0)
        if text:
            raw_segments.append({"start": start, "end": start + duration, "text": text})

    chunks = chunk_segments(raw_segments, url, url)
    for chunk in chunks:
        chunk["metadata"]["caption_language"] = getattr(transcript, "language_code", "auto")
        chunk["metadata"]["caption_kind"] = "youtube transcript"
    return chunks


def transcribe_video_audio(url, info):
    duration = info.get("duration")
    if duration and float(duration) > VIDEO_MAX_SECONDS:
        raise TimeoutError(
            f"El video dura {float(duration) / 60:.1f} minutos. "
            f"Para transcribir audio localmente el limite es {VIDEO_MAX_SECONDS // 60} minutos."
        )

    if not VIDEO_AUDIO_FALLBACK:
        raise ValueError("El video no tiene subtitulos disponibles y la transcripcion de audio esta desactivada.")

    title = info.get("title") or url
    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_template = str(Path(tmp_dir) / "audio.%(ext)s")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": audio_template,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
            "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 20,
            "retries": 1,
            "fragment_retries": 1,
            "extractor_retries": 1,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        audio_files = list(Path(tmp_dir).glob("*.mp3"))
        if not audio_files:
            raise FileNotFoundError("No se pudo generar el audio para transcribir.")

        device = WHISPER_DEVICE
        compute_type = "float16" if device == "cuda" else "int8"
        model = WhisperModel(WHISPER_MODEL, device=device, compute_type=compute_type)
        segments, _ = model.transcribe(str(audio_files[0]), language="es")
        raw_segments = [
            {"start": seg.start, "end": seg.end, "text": seg.text}
            for seg in segments
        ]
    return chunk_segments(raw_segments, url, title)


def extract_video(url):
    youtube_chunks = extract_youtube_transcript(url)
    if youtube_chunks:
        return youtube_chunks

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 20,
        "retries": 1,
        "fragment_retries": 1,
        "extractor_retries": 1,
        "http_headers": {"User-Agent": "TutorIA/1.0"},
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    caption_chunks = extract_video_captions(url, info)
    if caption_chunks:
        return caption_chunks
    return transcribe_video_audio(url, info)


def extract_article(url):
    response = requests.get(url, timeout=20, headers={"User-Agent": "TutorIA/1.0"})
    response.raise_for_status()
    html = response.text
    text = trafilatura.extract(html, include_comments=False, include_tables=False)
    if text is None:
        raise ValueError("No se pudo extraer texto del articulo.")
    meta = trafilatura.extract_metadata(html)
    title = meta.title if meta and meta.title else url
    return [{"text": text, "metadata": {"source": url, "type": "article", "title": title}}]


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Uso: url_worker.py <url> <salida_json>")

    url = sys.argv[1].strip()
    out_path = Path(sys.argv[2])
    chunks = extract_video(url) if is_video_url(url) else extract_article(url)
    out_path.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
