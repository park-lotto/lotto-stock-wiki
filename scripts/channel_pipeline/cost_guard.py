from __future__ import annotations

TOKENS_PER_FILE = 2_000
SONNET_INPUT_TOKENS = 8_000
HAIKU_INPUT_TOKENS = 4_000

PRICE_GEMINI_FLASH_PER_1M = 0.15
PRICE_SONNET_PER_1M = 5.0
PRICE_HAIKU_PER_1M = 1.0

DAILY_CAP_USD = 0.06


def estimate(manifest: dict[str, list[str]]) -> tuple[float, str]:
    n_files = sum(len(v) for v in manifest.values())
    cost_a = n_files * TOKENS_PER_FILE * PRICE_GEMINI_FLASH_PER_1M / 1_000_000
    cost_b = SONNET_INPUT_TOKENS * PRICE_SONNET_PER_1M / 1_000_000
    cost_d = HAIKU_INPUT_TOKENS * PRICE_HAIKU_PER_1M / 1_000_000
    total = cost_a + cost_b + cost_d
    detail = (
        f"A(Gemini×{n_files}파일)=${cost_a:.4f} + "
        f"B(Sonnet)=${cost_b:.4f} + "
        f"D(Haiku)=${cost_d:.4f} = ${total:.4f}"
    )
    return total, detail


def can_run(manifest: dict[str, list[str]]) -> tuple[bool, float, str]:
    cost, detail = estimate(manifest)
    return cost <= DAILY_CAP_USD, cost, detail


def reduce_scope(manifest: dict[str, list[str]], cap: int = 10) -> dict[str, list[str]]:
    return {ch: files[-cap:] for ch, files in manifest.items()}
