import tiktoken
from config import AVAILABLE_TOKEN_BUDGET, MAX_TOKENS_RESPONSE

enc = tiktoken.get_encoding("cl100k_base")


def estimate_tokens(text: str) -> int:
    return len(enc.encode(text))


# Priority order (highest first). Items earlier in the list are kept when budget is tight.
# Each entry: (display_name, priority_rank)
PROMPT_PART_PRIORITY = {
    "system_rules": 1,
    "teaching_instruction": 2,
    "teacher_persona": 3,
    "textbook_chapter": 4,
    "chat_history": 5,
    "wechat_diary_summary": 6,
    "learner_profile": 7,
}


def budget_check(parts: dict[str, str]) -> dict[str, str]:
    """
    Given prompt parts keyed by name, return a truncated copy that fits within budget.
    Truncation drops lowest-priority parts first, then truncates chat_history if needed.
    """
    total = estimate_tokens("".join(parts.values()))
    if total + MAX_TOKENS_RESPONSE <= AVAILABLE_TOKEN_BUDGET:
        return parts  # fits comfortably

    # Sort parts by priority (lowest number = highest priority = drop last)
    ordered = sorted(parts.items(), key=lambda kv: PROMPT_PART_PRIORITY.get(kv[0], 99))

    result = dict(parts)
    # Drop lowest-priority parts until we fit
    for name, _ in reversed(ordered):
        if estimate_tokens("".join(result.values())) + MAX_TOKENS_RESPONSE <= AVAILABLE_TOKEN_BUDGET:
            break
        if name != "system_rules" and name != "teaching_instruction":
            result.pop(name, None)

    # If still over budget, truncate chat_history (keep last N exchanges)
    if "chat_history" in result:
        while estimate_tokens("".join(result.values())) + MAX_TOKENS_RESPONSE > AVAILABLE_TOKEN_BUDGET:
            lines = result["chat_history"].split("\n")
            if len(lines) <= 2:
                result.pop("chat_history", None)
                break
            # Remove oldest exchange (first user+assistant pair)
            result["chat_history"] = "\n".join(lines[4:]) if len(lines) > 4 else ""

    return result


def estimate_message_tokens(messages: list[dict]) -> int:
    total = 0
    for m in messages:
        total += estimate_tokens(m.get("content", ""))
        total += 4  # role overhead
    return total
