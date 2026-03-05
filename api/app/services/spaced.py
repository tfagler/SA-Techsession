def update_sm2(interval_days: int, ease_factor: float, repetition: int, quality: int) -> tuple[int, float, int]:
    ef = max(1.3, ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    if quality < 3:
        return 1, ef, 0
    if repetition == 0:
        return 1, ef, 1
    if repetition == 1:
        return 6, ef, 2
    next_interval = int(round(interval_days * ef))
    return max(1, next_interval), ef, repetition + 1
