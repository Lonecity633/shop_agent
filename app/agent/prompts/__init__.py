from pathlib import Path

_PROMPT_DIR = Path(__file__).parent


def _load(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8").strip()


def _load_lines(name: str) -> list[str]:
    return [
        line.strip()
        for line in (_PROMPT_DIR / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _load_fallbacks(name: str) -> dict[str, str]:
    raw = (_PROMPT_DIR / name).read_text(encoding="utf-8")
    result: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []
    for line in raw.splitlines():
        if line.startswith("[") and line.endswith("]"):
            if current_key is not None:
                result[current_key] = "\n".join(current_lines).strip()
            current_key = line[1:-1]
            current_lines = []
        else:
            current_lines.append(line)
    if current_key is not None:
        result[current_key] = "\n".join(current_lines).strip()
    return result


# System prompts
CHITCHAT = _load("chitchat.txt")
CLASSIFIER = _load("classifier.txt")
PRODUCT_INQUIRY = _load("product_inquiry.txt")
POLICY = _load("policy.txt")
ORDER_QUERY = _load("order_query.txt")

# Guardrail config
SENSITIVE_PATTERNS = _load_lines("sensitive_patterns.txt")

# Conversation summary prompt
SUMMARY = _load("summary.txt")

# Fallback reply templates
FALLBACKS = _load_fallbacks("fallbacks.txt")
