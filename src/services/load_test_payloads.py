DEFAULT_PAYLOADS: dict[str, dict] = {
    "llm_chat": {
        "path": "v1/chat/completions",
        "method": "POST",
        "body": {
            "messages": [{"role": "user", "content": "Say ok"}],
            "max_tokens": 800,
        },
    },
    "embedding": {
        "path": "v1/embeddings",
        "method": "POST",
        "body": {
            "input": "test",
        },
    },
}


def get_default_payload(service_type: str) -> dict:
    default = DEFAULT_PAYLOADS.get(service_type, {"path": "", "method": "POST", "body": {}})
    return {
        "path": default["path"],
        "method": default["method"],
        "body": default["body"],
    }
