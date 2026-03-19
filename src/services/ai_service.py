import json
import logging
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.system_settings import SystemSettings
from src.services.service_registry import get_service_by_slug

logger = logging.getLogger(__name__)


class AINotConfiguredError(Exception):
    pass


class AICallError(Exception):
    pass


async def get_system_settings(session: AsyncSession) -> SystemSettings | None:
    result = await session.execute(select(SystemSettings).where(SystemSettings.id == 1))
    return result.scalar_one_or_none()


async def call_llm(
    session: AsyncSession,
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> str:
    settings = await get_system_settings(session)
    if not settings or not settings.ai_enabled or not settings.llm_service_slug:
        raise AINotConfiguredError("AI assistant is not configured. Go to Settings to set up LLM service.")

    service = await get_service_by_slug(session, settings.llm_service_slug)
    if not service:
        raise AINotConfiguredError(f"LLM service '{settings.llm_service_slug}' not found")

    url = f"{service.base_url.rstrip('/')}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}

    if service.auth_type == "bearer":
        headers["Authorization"] = f"Bearer {service.auth_token}"
    elif service.auth_type == "header":
        headers[service.auth_header_name or "Authorization"] = service.auth_token or ""

    if service.extra_headers:
        headers.update(service.extra_headers)

    model = settings.llm_model or service.default_model
    if not model:
        raise AINotConfiguredError("No LLM model configured. Set model in Settings or in the LLM service config.")

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=body, headers=headers, timeout=60.0)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            if content is None:
                raise AICallError("LLM returned empty content")
            return content
    except httpx.HTTPStatusError as e:
        logger.error(f"LLM call failed: {e.response.status_code} {e.response.text[:500]}")
        raise AICallError(f"LLM returned {e.response.status_code}")
    except Exception as e:
        logger.error(f"LLM call error: {e}")
        raise AICallError(f"Failed to call LLM: {str(e)}")


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, stripping markdown code blocks if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # remove ```json
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


# ─── High-level AI functions ───


async def ai_parse_curl(session: AsyncSession, curl_command: str) -> dict:
    messages = [
        {"role": "system", "content": """You are a service configuration parser for a proxy system.
Given a cURL command, extract the proxy service configuration.

Return ONLY a valid JSON object with these fields:
- name: string, human-readable service name (infer from URL/domain)
- slug: string, URL-safe lowercase identifier with hyphens
- base_url: string, base URL only (protocol + host + port, WITHOUT the path)
- service_type: one of "llm_chat", "embedding", "stt", "tts", "custom"
- auth_type: one of "none", "bearer", "header", "query_param"
- auth_token: string or null, the auth token/key value
- auth_header_name: string, header name (default "Authorization")
- default_model: string or null, model name if found in body
- supports_streaming: boolean, true if "stream": true in body
- extra_headers: object or null, any non-standard headers (exclude Content-Type, Authorization, Host)
- health_check_path: string or null, suggested health check (e.g. "/v1/models" for OpenAI-compatible)
- description: string, brief description
- timeout_seconds: integer, suggested timeout (default 120, longer for LLM)
- tags: array of strings, relevant tags

Rules:
- For OpenAI-compatible APIs (v1/chat/completions, v1/embeddings), set appropriate service_type
- base_url should NOT include the API path (e.g., "http://host:8080" not "http://host:8080/v1/chat/completions")
- Extract Bearer token from -H "Authorization: Bearer ..." headers
- Return ONLY JSON, no markdown, no explanation"""},
        {"role": "user", "content": curl_command},
    ]
    result = await call_llm(session, messages, temperature=0.1)
    data = _extract_json(result)

    if "slug" in data and isinstance(data["slug"], str):
        data["slug"] = data["slug"].lower()

    return data


async def ai_analyze_error(session: AsyncSession, log_entry: dict) -> str:
    messages = [
        {"role": "system", "content": """Ты — DevOps-инженер, анализируешь ошибку прокси-сервиса. Отвечай на русском языке.
Дай краткий анализ (2-3 предложения): что скорее всего пошло не так и как исправить.
Без markdown-разметки, просто текст."""},
        {"role": "user", "content": f"""Request log:
- Service: {log_entry.get('service_slug')}
- Method: {log_entry.get('method')} {log_entry.get('path')}
- Status Code: {log_entry.get('status_code')}
- Duration: {log_entry.get('duration_ms')}ms
- Error: {log_entry.get('error', 'none')}
- Is Streaming: {log_entry.get('is_streaming')}
- Is Fallback: {log_entry.get('is_fallback')}"""},
    ]
    return await call_llm(session, messages, temperature=0.3, max_tokens=500)


async def ai_diagnose_health(session: AsyncSession, service_info: dict, health_result: dict) -> str:
    messages = [
        {"role": "system", "content": """Ты — инженер, диагностируешь сбой проверки здоровья ML-сервиса. Отвечай на русском языке.
Дай краткую диагностику (2-3 предложения): вероятная причина и конкретные шаги для исправления.
Без markdown-разметки, просто текст."""},
        {"role": "user", "content": f"""Service:
- Name: {service_info.get('name')}
- Type: {service_info.get('service_type')}
- Base URL: {service_info.get('base_url')}
- Health Check: {service_info.get('health_check_method', 'GET')} {service_info.get('health_check_path', 'not configured')}

Health Check Result:
- Status: {health_result.get('status')}
- Detail: {health_result.get('detail')}
- Response Time: {health_result.get('response_time_ms')}ms"""},
    ]
    return await call_llm(session, messages, temperature=0.3, max_tokens=500)


async def ai_summarize_dashboard(session: AsyncSession, stats: dict) -> str:
    messages = [
        {"role": "system", "content": """Ты — аналитик платформы проксирования ML-сервисов. Отвечай ТОЛЬКО на русском языке.
Проанализируй статистику и дай 3-5 коротких инсайтов (2-3 предложения каждый).
Формат: каждый инсайт с новой строки, без markdown-разметки (без **, без #, без списков с -).
Просто текст абзацами. Будь конкретен и лаконичен."""},
        {"role": "user", "content": f"""Statistics for the last {stats.get('period_hours')} hours:
- Total requests: {stats.get('total_requests')}
- Errors: {stats.get('total_errors')} ({stats.get('error_rate', 0):.1f}% error rate)
- Average latency: {stats.get('avg_duration_ms')}ms
- Traffic: {stats.get('total_request_bytes')} bytes in, {stats.get('total_response_bytes')} bytes out

By service:
{json.dumps(stats.get('by_service', []), indent=2)}

By API key:
{json.dumps(stats.get('by_key', []), indent=2)}"""},
    ]
    return await call_llm(session, messages, temperature=0.4, max_tokens=800)


async def ai_generate_description(session: AsyncSession, service_info: dict) -> str:
    messages = [
        {"role": "system", "content": """Generate a very short description (max 15 words) for a proxy service.
Return ONLY the description text. No quotes, no formatting. One sentence max."""},
        {"role": "user", "content": f"""Service:
- Name: {service_info.get('name')}
- Type: {service_info.get('service_type')}
- Base URL: {service_info.get('base_url')}
- Model: {service_info.get('default_model', 'not set')}
- Streaming: {service_info.get('supports_streaming', False)}"""},
    ]
    return await call_llm(session, messages, temperature=0.5, max_tokens=500)


async def ai_generate_test_params(session: AsyncSession, service_info: dict) -> dict:
    """Generate sample request parameters for playground testing."""
    messages = [
        {"role": "system", "content": """You generate sample test request data for ML service APIs.
Return ONLY a valid JSON object with these fields:
- path: string, the API endpoint path (e.g. "v1/chat/completions")
- body: object, a sample request body appropriate for this service type
- description: string, one sentence explaining what this test does (in Russian)

Rules by service_type:
- llm_chat: path "v1/chat/completions", body with model, messages (include a creative sample prompt), temperature, max_tokens
- embedding: path "v1/embeddings", body with model, input (a sample text to embed)
- stt: path "v1/audio/transcriptions", body with model only (file is uploaded separately)
- tts: path "v1/audio/speech", body with model, input (a short sample text in Russian), voice
- custom: path "", body with a sample JSON payload

Use the provided model name if available. Be creative with sample prompts/texts.
Return ONLY JSON, no markdown, no explanation."""},
        {"role": "user", "content": f"""Service:
- Name: {service_info.get('name')}
- Type: {service_info.get('service_type')}
- Model: {service_info.get('default_model', 'not set')}
- Streaming: {service_info.get('supports_streaming', False)}"""},
    ]
    result = await call_llm(session, messages, temperature=0.8, max_tokens=1000)
    return _extract_json(result)
