"""Token usage aggregation and CNY price estimates for choreo agent runs."""
from __future__ import annotations

import math
from typing import Iterable, Mapping, Any


PRICE_CACHE_HIT_INPUT_CNY_PER_1M = 0.025
PRICE_CACHE_MISS_INPUT_CNY_PER_1M = 3.0
PRICE_OUTPUT_CNY_PER_1M = 6.0

# Conservative fallback for mixed Chinese/code text when provider usage is absent.
ESTIMATE_CHARS_PER_TOKEN = 2.0


def estimate_tokens_from_chars(chars: int | float | None) -> int | None:
    if chars is None:
        return None
    try:
        value = float(chars)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return 0
    return int(math.ceil(value / ESTIMATE_CHARS_PER_TOKEN))


def summarize_usage(items: Iterable[Mapping[str, Any]]) -> dict:
    """Aggregate exact token usage, falling back to char-based estimates."""
    exact_input_total = 0
    exact_output_total = 0
    cache_hit_total = 0
    cache_miss_total = 0
    estimated_input_total = 0
    estimated_output_total = 0
    rounds = 0
    missing_input_rounds = 0
    missing_output_rounds = 0
    missing_cache_rounds = 0

    for item in items:
        rounds += 1

        input_tokens = _int_or_none(item.get("input_tokens"))
        output_tokens = _int_or_none(item.get("output_tokens"))
        cache_hit_tokens = _int_or_none(item.get("prompt_cache_hit_tokens"))
        cache_miss_tokens = _int_or_none(item.get("prompt_cache_miss_tokens"))

        prompt_chars = _first_int(
            item.get("prompt_chars"),
            _sum_ints(item.get("system_prompt_chars"), item.get("user_prompt_chars")),
        )
        output_chars = _sum_ints(item.get("response_chars"), item.get("reasoning_chars"))

        estimated_input = _first_int(
            item.get("estimated_input_tokens"),
            input_tokens,
            estimate_tokens_from_chars(prompt_chars),
        ) or 0
        estimated_output = _first_int(
            item.get("estimated_output_tokens"),
            output_tokens,
            estimate_tokens_from_chars(output_chars),
        ) or 0

        if input_tokens is None:
            missing_input_rounds += 1
        else:
            exact_input_total += input_tokens
        if output_tokens is None:
            missing_output_rounds += 1
        else:
            exact_output_total += output_tokens
        if cache_hit_tokens is None or cache_miss_tokens is None:
            missing_cache_rounds += 1
        else:
            cache_hit_total += cache_hit_tokens
            cache_miss_total += cache_miss_tokens

        estimated_input_total += input_tokens if input_tokens is not None else estimated_input
        estimated_output_total += output_tokens if output_tokens is not None else estimated_output

    input_cache_hit = _price(estimated_input_total, PRICE_CACHE_HIT_INPUT_CNY_PER_1M)
    input_cache_miss = _price(estimated_input_total, PRICE_CACHE_MISS_INPUT_CNY_PER_1M)
    exact_input_mixed = (
        None if missing_cache_rounds
        else round(
            _price(cache_hit_total, PRICE_CACHE_HIT_INPUT_CNY_PER_1M)
            + _price(cache_miss_total, PRICE_CACHE_MISS_INPUT_CNY_PER_1M),
            6,
        )
    )
    output = _price(estimated_output_total, PRICE_OUTPUT_CNY_PER_1M)

    return {
        "rounds": rounds,
        "input_tokens": exact_input_total if missing_input_rounds == 0 else None,
        "output_tokens": exact_output_total if missing_output_rounds == 0 else None,
        "prompt_cache_hit_tokens": cache_hit_total if missing_cache_rounds == 0 else None,
        "prompt_cache_miss_tokens": cache_miss_total if missing_cache_rounds == 0 else None,
        "exact_input_tokens_available": exact_input_total,
        "exact_output_tokens_available": exact_output_total,
        "missing_input_token_rounds": missing_input_rounds,
        "missing_output_token_rounds": missing_output_rounds,
        "missing_cache_token_rounds": missing_cache_rounds,
        "estimated_input_tokens": estimated_input_total,
        "estimated_output_tokens": estimated_output_total,
        "pricing_cny": {
            "rates_per_1m_tokens": {
                "cache_hit_input": PRICE_CACHE_HIT_INPUT_CNY_PER_1M,
                "cache_miss_input": PRICE_CACHE_MISS_INPUT_CNY_PER_1M,
                "output": PRICE_OUTPUT_CNY_PER_1M,
            },
            "input_actual_cache_mix": exact_input_mixed,
            "input_cache_hit": input_cache_hit,
            "input_cache_miss": input_cache_miss,
            "output": output,
            "total_with_actual_cache_mix": (
                None if exact_input_mixed is None else round(exact_input_mixed + output, 6)
            ),
            "total_if_input_cached": round(input_cache_hit + output, 6),
            "total_if_input_uncached": round(input_cache_miss + output, 6),
            "input_cache_miss_delta": round(input_cache_miss - input_cache_hit, 6),
        },
        "estimate_note": (
            "When exact provider usage is absent, token counts use a conservative "
            f"{ESTIMATE_CHARS_PER_TOKEN:g} chars/token fallback for mixed Chinese/code text."
        ),
    }


def _price(tokens: int, cny_per_1m: float) -> float:
    return round(tokens / 1_000_000 * cny_per_1m, 6)


def _int_or_none(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _first_int(*values) -> int | None:
    for value in values:
        parsed = _int_or_none(value)
        if parsed is not None:
            return parsed
    return None


def _sum_ints(*values) -> int | None:
    total = 0
    seen = False
    for value in values:
        parsed = _int_or_none(value)
        if parsed is None:
            continue
        total += parsed
        seen = True
    return total if seen else None
