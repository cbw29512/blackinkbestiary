from __future__ import annotations

MIDTONE_LOW = 20
MIDTONE_HIGH = 235
MAX_MIDTONE_RATIO = 0.08
MAX_CHROMATIC_RATIO = 0.005
CHROMA_TOLERANCE = 8


def classify_sample(r: int, g: int, b: int) -> tuple[bool, bool]:
    """Return (is_midtone, is_chromatic) for one sampled pixel."""
    luma = (299 * r + 587 * g + 114 * b) // 1000
    midtone = MIDTONE_LOW < luma < MIDTONE_HIGH
    chromatic = max(r, g, b) - min(r, g, b) > CHROMA_TOLERANCE
    return midtone, chromatic


def purity_reasons(midtone: int, chromatic: int, total: int) -> tuple[float, float, list[str]]:
    """Convert sampled purity counts into stable QA ratios and failure reasons."""
    if total <= 0:
        return 0.0, 0.0, ["no_pixel_samples"]

    midtone_ratio = midtone / total
    chromatic_ratio = chromatic / total
    reasons: list[str] = []
    if midtone_ratio > MAX_MIDTONE_RATIO:
        reasons.append("excessive_grayscale_or_shading")
    if chromatic_ratio > MAX_CHROMATIC_RATIO:
        reasons.append("color_pixels_detected")
    return midtone_ratio, chromatic_ratio, reasons
