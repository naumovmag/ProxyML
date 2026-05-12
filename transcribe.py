#!/usr/bin/env python3
"""
Транскрибация аудио через мультимодальный chat completions endpoint (Gemma 4).

Gemma 4 обрабатывает ~30 секунд аудио за один запрос, поэтому длинные файлы
автоматически нарезаются на чанки через ffmpeg, транскрибируются по отдельности
и склеиваются.

Usage:
    python transcribe.py path/to/audio.mp3
    python transcribe.py audio.wav --chunk-seconds 30
"""
import argparse
import base64
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

PROXY_URL = "https://proxy-ml.adata.kz/proxy/gemma-4-e4b-it/v1/chat/completions"
API_KEY = os.environ.get("PROXYML_API_KEY", "")

DEFAULT_PROMPT = (
    "Transcribe the following audio verbatim. "
    "Return only the transcription text in the original spoken language, "
    "without any commentary or formatting."
)

TRANSCRIBE_FOR_DIARIZE_PROMPT = (
    "Transcribe the following audio verbatim in the original spoken language. "
    "Start a new line EVERY time the speaker changes. "
    "Do not add any labels, names, comments, or quote marks — just the text, "
    "with line breaks on speaker changes."
)

DIARIZE_PROMPT = (
    "Это фрагмент телефонного разговора двух людей. "
    "Дословно транскрибируй речь на русском и раздели реплики по спикерам. "
    "Используй строго формат:\n"
    "Спикер 1: <реплика>\n"
    "Спикер 2: <реплика>\n"
    "Каждая реплика — на отдельной строке."
    "Не добавляй пояснений, заголовков, комментариев. Верни только расшифровку."
    "Если транскрибация не смогла извлечь корректный текст, нужно корректно восстановить текст."
)


def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"{tool} не найден в PATH. Установи: sudo apt install ffmpeg")


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


MIN_CHUNK_BYTES = 2000


def cut_chunk(src: Path, dst: Path, start: float, duration: float) -> None:
    # -ss после -i даёт точный seek (медленнее, но не ломает хвостовые чанки)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-ss", f"{start:.2f}", "-t", f"{duration:.2f}",
         "-ar", "16000", "-ac", "1", "-c:a", "libmp3lame",
         "-q:a", "4", str(dst), "-loglevel", "error"],
        check=True,
    )


def request_transcription(
    client: httpx.Client,
    audio_path: Path,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
) -> str:
    b64 = base64.b64encode(audio_path.read_bytes()).decode("ascii")
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "audio_url", "audio_url": {"url": f"data:audio/mpeg;base64,{b64}"}},
            ],
        }],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    response = client.post(
        PROXY_URL,
        headers={"X-Api-Key": API_KEY, "Content-Type": "application/json"},
        json=payload,
    )
    response.raise_for_status()
    body = response.json()
    return body["choices"][0]["message"]["content"].strip()


def build_diarize_prompt(role1: str = "Спикер 1", role2: str = "Спикер 2") -> str:
    return (
        _DIARIZE_TEXT_PROMPT_TEMPLATE
        .replace("__R1__", role1)
        .replace("__R2__", role2)
    )


_DIARIZE_TEXT_PROMPT_TEMPLATE = (
    "Ты размечаешь транскрипцию телефонного разговора двух людей.\n"
    "В исходной транскрипции реплики обоих спикеров идут СПЛОШНЫМ потоком, "
    "без разметки — в одном предложении или даже в одной фразе могут быть "
    "слиты слова разных говорящих. Твоя задача — АКТИВНО и ВНИМАТЕЛЬНО разбить "
    "поток на отдельные реплики по смене говорящего.\n"
    "\n"
    "КЛЮЧЕВОЕ ПРАВИЛО ДРОБЛЕНИЯ:\n"
    "Если в одной строке ты видишь короткое подтверждение/приветствие "
    "(алло, да, слушаю, ага, хорошо, угу, понятно) СРАЗУ за которым идёт "
    "ДЛИННАЯ содержательная реплика — это 99% смена говорящего. Разбивай.\n"
    "\n"
    "ПРАВИЛО НАЧАЛА РАЗГОВОРА:\n"
    "Это телефонный звонок. Первые реплики 'Алло', 'Да, алло', 'Здравствуйте', "
    "'Слушаю', произнесение своего имени/отчества — это ВСЕГДА тот, кому звонят "
    "(отвечающий, т.е. __R2__). Звонящий (инициатор, т.е. __R1__) начинает "
    "говорить позже и ПРЕДСТАВЛЯЕТСЯ длинной фразой: 'Вас беспокоит...', "
    "'Это Карина из службы доставки', 'Звоню вам по поводу...'. "
    "Первое 'Алло' НЕ принадлежит __R1__.\n"
    "Правильно (при входящем звонке):\n"
    "  __R2__: Алло, здравствуйте.\n"
    "  __R1__: Здравствуйте, Иван Иванович? Вас беспокоит <...>.\n"
    "  __R2__: Да, слушаю.\n"
    "  __R1__: <длинная реплика по делу>\n"
    "Пример: 'Да, слушаю. Вас беспокоит менеджер курьерской доставки Карина, поступило письмо...'\n"
    "  → __R1__: Да, слушаю.\n"
    "  → __R2__: Вас беспокоит менеджер курьерской доставки Карина, поступило письмо...\n"
    "\n"
    "ОСТАЛЬНЫЕ ПРАВИЛА:\n"
    "1. Каждая смена говорящего = новая строка.\n"
    "2. Формат: '__R1__: <реплика>' или '__R2__: <реплика>'.\n"
    "3. Один и тот же человек во всём разговоре — одна и та же метка. Не переименовывай.\n"
    "4. Вопрос и ответ — РАЗНЫЕ спикеры.\n"
    "5. Одобрения ('да', 'угу', 'ага', 'хорошо', 'алло') в начале фразы — это реакция на слова другого, это отдельная реплика.\n"
    "6. Сохраняй оригинальные слова, не перефразируй, не сокращай, не добавляй новых. Искажённые слова бережно восстанавливай по смыслу.\n"
    "7. Не добавляй пояснений, заголовков, комментариев — верни ТОЛЬКО размеченную расшифровку.\n"
    "\n"
    "ПРИМЕР 1 (короткое подтверждение + длинная реплика = смена):\n"
    "Вход: Алло здравствуйте Алмазгалиевич да слушаю вас беспокоит менеджер курьерской доставки Карина нам поступило письмо\n"
    "Выход:\n"
    "__R1__: Алло, здравствуйте.\n"
    "__R2__: Алмазгалиевич?\n"
    "__R1__: Да, слушаю.\n"
    "__R2__: Вас беспокоит менеджер курьерской доставки Карина. Нам поступило письмо.\n"
    "\n"
    "ПРИМЕР 2 (вопрос-ответ):\n"
    "Вход: Когда сможете встретить курьера через час хорошо давайте через час\n"
    "Выход:\n"
    "__R2__: Когда сможете встретить курьера?\n"
    "__R1__: Через час.\n"
    "__R2__: Хорошо, давайте через час.\n"
    "\n"
    "Теперь размести этот разговор:\n"
    "{transcript}"
)


def request_text_completion(
    client: httpx.Client,
    user_text: str,
    model: str,
    max_tokens: int,
    temperature: float,
) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": user_text}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    response = client.post(
        PROXY_URL,
        headers={"X-Api-Key": API_KEY, "Content-Type": "application/json"},
        json=payload,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


DIARIZE_CHUNK_CHARS = 500
DIARIZE_TAIL_LINES = 2


def split_for_diarize(raw: str, max_chars: int) -> list[str]:
    """Нарезает raw-транскрипт на куски ~max_chars по границам предложений/строк."""
    pieces = re.split(r"(?<=[.!?])\s+|\n+", raw.strip())
    pieces = [p.strip() for p in pieces if p.strip()]

    chunks: list[str] = []
    buf: list[str] = []
    buf_len = 0
    for p in pieces:
        if buf and buf_len + len(p) + 1 > max_chars:
            chunks.append(" ".join(buf))
            buf = []
            buf_len = 0
        buf.append(p)
        buf_len += len(p) + 1
    if buf:
        chunks.append(" ".join(buf))
    return chunks


def diarize_chunked(
    client: httpx.Client,
    raw: str,
    model: str,
    temperature: float,
    role1: str = "Спикер 1",
    role2: str = "Спикер 2",
    verbose: bool = False,
) -> str:
    pieces = split_for_diarize(raw, DIARIZE_CHUNK_CHARS)
    if verbose:
        print(f"[diarize] pieces={len(pieces)} (~{DIARIZE_CHUNK_CHARS} chars each), roles={role1}/{role2}",
              file=sys.stderr)
    base_prompt = build_diarize_prompt(role1, role2)
    results: list[str] = []
    tail = ""
    for i, piece in enumerate(pieces):
        user_text = base_prompt.replace("{transcript}", piece)
        if tail:
            user_text += (
                "\n\nДля сохранения ролей — последние реплики предыдущего куска (их НЕ повторяй в ответе):\n"
                + tail
            )
        out = request_text_completion(
            client, user_text, model, max_tokens=1500, temperature=temperature
        )
        if verbose:
            print(f"[diarize piece {i}] in={len(piece)} -> out={len(out)} chars",
                  file=sys.stderr)
        results.append(out)
        lines = [ln for ln in out.splitlines() if ln.strip()]
        tail = "\n".join(lines[-DIARIZE_TAIL_LINES:])
    return "\n".join(results)


def transcribe(
    audio_path: Path,
    model: str = "gemma-4-e4b-it",
    prompt: str = DEFAULT_PROMPT,
    chunk_seconds: float = 30.0,
    max_tokens: int = 3000,
    temperature: float = 0.0,
    verbose: bool = False,
    diarize: bool = False,
    role1: str = "Спикер 1",
    role2: str = "Спикер 2",
) -> str:
    if not audio_path.exists():
        raise FileNotFoundError(f"Файл не найден: {audio_path}")
    require_ffmpeg()

    duration = probe_duration(audio_path)
    if verbose:
        print(f"[info] duration={duration:.1f}s, chunk={chunk_seconds}s", file=sys.stderr)

    # Если diarize — при аудио-транскрипции просим модель ставить переносы
    # на смене говорящего, а потом отдельным text-only запросом расставляем роли.
    transcription_prompt = TRANSCRIBE_FOR_DIARIZE_PROMPT if diarize else prompt

    with httpx.Client(timeout=300.0) as client:
        if duration <= chunk_seconds + 1.0:
            raw = request_transcription(
                client, audio_path, model, transcription_prompt, max_tokens, temperature
            )
        else:
            parts: list[str] = []
            with tempfile.TemporaryDirectory(prefix="transcribe_") as tmp:
                tmp_dir = Path(tmp)
                start = 0.0
                idx = 0
                while start < duration:
                    dur = min(chunk_seconds, duration - start)
                    chunk = tmp_dir / f"chunk_{idx:03d}.mp3"
                    cut_chunk(audio_path, chunk, start, dur)
                    size = chunk.stat().st_size
                    if verbose:
                        print(f"[chunk {idx}] {start:.1f}..{start+dur:.1f}s size={size}B",
                              file=sys.stderr)
                    if size < MIN_CHUNK_BYTES:
                        if verbose:
                            print(f"[chunk {idx}] too small, skipped", file=sys.stderr)
                        start += chunk_seconds
                        idx += 1
                        continue
                    text = request_transcription(
                        client, chunk, model, transcription_prompt, max_tokens, temperature
                    )
                    if verbose:
                        print(f"[chunk {idx}] -> {len(text)} chars", file=sys.stderr)
                    parts.append(text)
                    start += chunk_seconds
                    idx += 1
            raw = "\n".join(parts) if diarize else " ".join(parts)

        if not diarize:
            return raw

        if verbose:
            print(f"[diarize] 2-pass text postprocessing, input={len(raw)} chars",
                  file=sys.stderr)
        return diarize_chunked(
            client, raw, model, temperature,
            role1=role1, role2=role2, verbose=verbose,
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Транскрибация аудио через Gemma 4 (chat completions + автоматический chunking)"
    )
    parser.add_argument("audio", type=Path, help="Путь к аудиофайлу")
    parser.add_argument("--model", default="gemma-4-e4b-it", help="ID модели")
    parser.add_argument("--prompt", default=None, help="Свой промпт (перекрывает --diarize)")
    parser.add_argument("--diarize", action="store_true",
                        help="Разделять реплики по спикерам (Спикер 1/Спикер 2)")
    parser.add_argument("--roles", default=None,
                        help="Имена двух ролей через запятую (например: 'Оператор,Клиент'). "
                             "По умолчанию: 'Спикер 1,Спикер 2'. Работает с --diarize.")
    parser.add_argument("--chunk-seconds", type=float, default=30.0,
                        help="Длительность чанка в секундах (Gemma 4 обрабатывает ~30s за раз)")
    parser.add_argument("--max-tokens", type=int, default=3000, help="Максимум токенов в ответе на чанк")
    parser.add_argument("--temperature", type=float, default=0.0, help="Температура семплирования")
    parser.add_argument("-v", "--verbose", action="store_true", help="Логировать прогресс в stderr")
    args = parser.parse_args()

    if args.prompt is not None:
        prompt = args.prompt
    elif args.diarize:
        prompt = DIARIZE_PROMPT
    else:
        prompt = DEFAULT_PROMPT

    role1, role2 = "Спикер 1", "Спикер 2"
    if args.roles:
        parts = [p.strip() for p in args.roles.split(",")]
        if len(parts) != 2 or not all(parts):
            print("Ошибка: --roles должен содержать две роли через запятую, "
                  "например: --roles 'Оператор,Клиент'", file=sys.stderr)
            return 2
        role1, role2 = parts

    try:
        text = transcribe(
            audio_path=args.audio,
            model=args.model,
            prompt=prompt,
            chunk_seconds=args.chunk_seconds,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            verbose=args.verbose,
            diarize=args.diarize,
            role1=role1,
            role2=role2,
        )
    except httpx.HTTPStatusError as e:
        print(f"HTTP {e.response.status_code}: {e.response.text}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1

    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
