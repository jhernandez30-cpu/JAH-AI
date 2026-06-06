from __future__ import annotations

import os
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


JARVIS_FALLBACK_MESSAGE = "Jarvis avanzado no esta configurado todavia. Se usara voz del navegador."
MARK_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
MARK_VOICE = "Charon"
_mark_process: subprocess.Popen | None = None
_audio_devices_cache: tuple[float, dict[str, Any]] | None = None


def _mark_log_file(path: Path) -> Path:
    return path / "logs" / "mark_xxxix.log"


def _mark_python(path: Path) -> Path:
    venv_python = path / "venv" / "Scripts" / "python.exe"
    return venv_python if venv_python.exists() else Path(sys.executable)


def _mark_system_processes(path: Path) -> list[dict[str, Any]]:
    if not sys.platform.startswith("win"):
        return []
    needle = str(path).replace("'", "''")
    script = (
        "Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.CommandLine -like '*{needle}*' -and $_.CommandLine -like '*main.py*' "
        "-and $_.Name -notlike '*powershell*' -and $_.Name -notlike '*pwsh*' }} | "
        "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        parsed = json.loads(result.stdout)
    except Exception:
        return []
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return []
    processes = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        processes.append(
            {
                "pid": item.get("ProcessId"),
                "command": item.get("CommandLine", ""),
            }
        )
    return processes


def mark_audio_devices() -> dict[str, Any]:
    global _audio_devices_cache
    now = time.monotonic()
    if _audio_devices_cache and now - _audio_devices_cache[0] < 30:
        return _audio_devices_cache[1]
    path = jarvis_project_paths()["mark_xxxix"]
    python_exe = _mark_python(path)
    code = r"""
import json
import sounddevice as sd

devices = []
for index, device in enumerate(sd.query_devices()):
    devices.append({
        "id": index,
        "name": device.get("name"),
        "input_channels": int(device.get("max_input_channels", 0)),
        "output_channels": int(device.get("max_output_channels", 0)),
        "default_samplerate": int(device.get("default_samplerate", 0)),
    })

default_device = [int(sd.default.device[0]), int(sd.default.device[1])]
print(json.dumps({
    "ok": True,
    "default": default_device,
    "devices": devices,
}, ensure_ascii=False))
"""
    try:
        result = subprocess.run(
            [str(python_exe), "-c", code],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=4,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    except Exception as exc:
        data = {"ok": False, "error": str(exc), "devices": []}
        _audio_devices_cache = (now, data)
        return data
    if result.returncode != 0:
        data = {"ok": False, "error": result.stderr.strip() or result.stdout.strip(), "devices": []}
        _audio_devices_cache = (now, data)
        return data
    try:
        data = json.loads(result.stdout)
        _audio_devices_cache = (now, data)
        return data
    except Exception as exc:
        data = {"ok": False, "error": f"No se pudo leer sounddevice: {exc}", "devices": []}
        _audio_devices_cache = (now, data)
        return data


def _default_documents_dir() -> Path:
    return Path(os.getenv("USERPROFILE", str(Path.home()))) / "Documents"


def _path_from_env(name: str, fallback: Path) -> Path:
    return Path(os.getenv(name, str(fallback))).expanduser()


def jarvis_project_paths() -> dict[str, Path]:
    documents = _default_documents_dir()
    return {
        "jarvis_mlx": _path_from_env("JARVIS_MLX_PATH", documents / "jarvis-mlx-main"),
        "openjarvis": _path_from_env("OPENJARVIS_PATH", documents / "OpenJarvis-main"),
        "mark_xxxix": _path_from_env("MARK_XXXIX_PATH", documents / "Mark-XXXIX-main"),
    }


def _exists(path: Path, *parts: str) -> bool:
    return (path.joinpath(*parts) if parts else path).exists()


def _mark_api_key_configured(path: Path) -> bool:
    api_file = path / "config" / "api_keys.json"
    if not api_file.exists():
        return False
    try:
        data = json.loads(api_file.read_text(encoding="utf-8-sig"))
    except Exception:
        return False
    return bool(str(data.get("gemini_api_key") or "").strip())


def mark_xxxix_status(include_audio: bool = False) -> dict[str, Any]:
    path = jarvis_project_paths()["mark_xxxix"]
    exists = path.exists()
    api_file = path / "config" / "api_keys.json"
    main_file = path / "main.py"
    face_file = path / "face.png"
    requirements_file = path / "requirements.txt"
    venv_python = path / "venv" / "Scripts" / "python.exe"
    processes = _mark_system_processes(path)
    api_configured = _mark_api_key_configured(path)
    ready = exists and main_file.exists() and api_configured and venv_python.exists()
    backend_running = bool(_mark_process and _mark_process.poll() is None)
    running = backend_running or bool(processes)
    notes: list[str] = []
    if not exists:
        notes.append("Carpeta Mark-XXXIX-main no encontrada.")
    if exists and not api_file.exists():
        notes.append("Falta config/api_keys.json con gemini_api_key.")
    if exists and api_file.exists() and not api_configured:
        notes.append("config/api_keys.json existe, pero gemini_api_key esta vacia o no se pudo leer.")
    if exists and not face_file.exists():
        notes.append("Falta face.png; la UI de Mark puede requerirlo al iniciar.")
    if exists and not venv_python.exists():
        notes.append("Falta venv de Mark. Crea el entorno e instala dependencies con requirements.txt.")

    return {
        "key": "mark_xxxix",
        "name": "Mark XXXIX",
        "path": str(path),
        "exists": exists,
        "main_py": str(main_file),
        "main_exists": main_file.exists(),
        "requirements": str(requirements_file),
        "requirements_exists": requirements_file.exists(),
        "python_exe": str(venv_python if venv_python.exists() else Path(sys.executable)),
        "venv_ready": venv_python.exists(),
        "api_keys_file": str(api_file),
        "api_key_configured": api_configured,
        "face_png": str(face_file),
        "face_exists": face_file.exists(),
        "model": MARK_MODEL,
        "voice": MARK_VOICE,
        "stt": exists and main_file.exists(),
        "tts": exists and main_file.exists(),
        "launch_ready": ready,
        "running": running,
        "pid": _mark_process.pid if backend_running and _mark_process else (processes[0]["pid"] if processes else None),
        "processes": processes,
        "log_file": str(_mark_log_file(path)),
        "audio": mark_audio_devices() if include_audio and exists and venv_python.exists() else {"ok": None, "message": "Consulta /api/jarvis/mark/status para ver dispositivos de audio.", "devices": []},
        "notes": notes,
    }


def _project_status(key: str, path: Path) -> dict[str, Any]:
    exists = path.exists()
    status: dict[str, Any] = {
        "key": key,
        "path": str(path),
        "exists": exists,
        "usable_now": False,
        "stt": False,
        "tts": False,
        "notes": [],
    }
    if not exists:
        status["notes"].append("Carpeta no encontrada.")
        return status

    if key == "jarvis_mlx":
        status["stt"] = _exists(path, "stt", "whisper") or _exists(path, "stt", "VoiceActivityDetection.py")
        status["tts"] = _exists(path, "melo", "api.py")
        status["notes"].append("Orientado a Apple Silicon/MLX; no se activa automaticamente en Windows.")
    elif key == "openjarvis":
        status["stt"] = _exists(path, "frontend", "src", "hooks", "useSpeech.ts")
        status["tts"] = _exists(path, "tests", "tools", "test_text_to_speech.py") or _exists(path, "tests", "speech")
        status["notes"].append("Tiene arquitectura de speech propia; se deja como integracion futura.")
    elif key == "mark_xxxix":
        mark = mark_xxxix_status()
        status["stt"] = bool(mark["stt"])
        status["tts"] = bool(mark["tts"])
        status["usable_now"] = bool(mark["launch_ready"])
        status["model"] = mark["model"]
        status["voice"] = mark["voice"]
        status["running"] = mark["running"]
        status["notes"].extend(mark["notes"] or ["Gemini native audio con voz Charon."])
    if key != "mark_xxxix":
        status["usable_now"] = False
    return status


def is_mark_xxxix_running() -> bool:
    if _mark_process and _mark_process.poll() is None:
        return True
    path = jarvis_project_paths()["mark_xxxix"]
    return bool(path.exists() and _mark_system_processes(path))


def launch_mark_xxxix() -> dict[str, Any]:
    global _mark_process
    status = mark_xxxix_status()
    if is_mark_xxxix_running():
        return {"ok": True, "launched": False, "already_running": True, "status": status}
    if not status["launch_ready"]:
        return {
            "ok": False,
            "launched": False,
            "message": "Mark XXXIX no esta listo para iniciar. Configura gemini_api_key en config/api_keys.json.",
            "status": status,
        }

    mark_path = Path(status["path"])
    mark_python = mark_path / "venv" / "Scripts" / "python.exe"
    python_exe = os.getenv("MARK_XXXIX_PYTHON", str(mark_python if mark_python.exists() else sys.executable))
    command = [python_exe, "main.py"]
    log_file = _mark_log_file(mark_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    audio = mark_audio_devices()
    default_devices = audio.get("default") if isinstance(audio, dict) else None
    default_input = str(default_devices[0]) if isinstance(default_devices, list) and default_devices else "1"
    default_output = str(default_devices[1]) if isinstance(default_devices, list) and len(default_devices) > 1 else "3"
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "MARK_XXXIX_INPUT_DEVICE": os.getenv("MARK_XXXIX_INPUT_DEVICE", default_input),
        "MARK_XXXIX_OUTPUT_DEVICE": os.getenv("MARK_XXXIX_OUTPUT_DEVICE", default_output),
        "JARVIS_FULL_COMPUTER_ACCESS": os.getenv("JARVIS_FULL_COMPUTER_ACCESS", "1"),
        "JARVIS_ALWAYS_ON": os.getenv("JARVIS_ALWAYS_ON", "1"),
    }
    try:
        log_handle = log_file.open("ab", buffering=0)
        _mark_process = subprocess.Popen(
            command,
            cwd=str(mark_path),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            close_fds=False,
        )
        log_handle.close()
    except Exception as exc:
        return {
            "ok": False,
            "launched": False,
            "message": f"No se pudo iniciar Mark XXXIX: {exc}",
            "status": mark_xxxix_status(),
        }

    return {
        "ok": True,
        "launched": True,
        "already_running": False,
        "pid": _mark_process.pid,
        "message": "Mark XXXIX iniciado con Gemini Live Audio y voz Charon.",
        "log_file": str(log_file),
        "status": mark_xxxix_status(),
    }


def read_mark_log(max_lines: int = 120) -> dict[str, Any]:
    path = jarvis_project_paths()["mark_xxxix"]
    log_file = _mark_log_file(path)
    if not log_file.exists():
        return {"ok": True, "log_file": str(log_file), "lines": []}
    try:
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:
        return {"ok": False, "log_file": str(log_file), "error": str(exc), "lines": []}
    return {"ok": True, "log_file": str(log_file), "lines": lines[-max(1, min(max_lines, 300)):]}


def get_jarvis_status() -> dict[str, Any]:
    projects = [_project_status(key, path) for key, path in jarvis_project_paths().items()]
    mark = mark_xxxix_status()
    return {
        "ok": True,
        "browser_voice": True,
        "advanced_configured": bool(mark["launch_ready"]),
        "message": "Mark XXXIX listo como voz avanzada." if mark["launch_ready"] else JARVIS_FALLBACK_MESSAGE,
        "projects": projects,
        "recommended_provider": "mark_xxxix" if mark["launch_ready"] else "browser",
        "mark_xxxix": mark,
        "frontend": {
            "stt": "SpeechRecognition/webkitSpeechRecognition",
            "tts": "speechSynthesis",
        },
    }
