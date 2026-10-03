"""Heuristic paint-tinting formula calculator.

There is no real spectrophotometer/color-matching hardware behind this POS,
so this module approximates a plausible pigment mix for a target RGB color
using a small fixed pigment set (Lamp Black, Yellow Oxide, Phthalo Blue,
Thalo Green, Titanium White). It is a functional, editable starting point
for staff — not a scientifically certified color match.

The dispenser ratio (9.6 ml per "shot") matches the values used throughout
the seeded demo formulas (see core.management.commands.seed_demo_data).
"""
from decimal import Decimal, ROUND_HALF_UP

from catalog.models import Pigment

CAPACITY_ML = {"1L": 30.0, "4L": 120.0, "20L": 600.0}
DISPENSER_ML_PER_SHOT = Decimal("9.6")
WARNING_FRACTION = 0.9
MIN_LINE_ML = 0.5

# Deficit-from-white (255,255,255) vector for each chromatic/dark pigment's
# own color. Used to approximate the target color as a non-negative
# combination of these pigments.
_CHROMATIC_VECTORS = {
    "B": (255.0, 255.0, 255.0),    # Lamp Black
    "C": (26.0, 47.0, 191.0),      # Yellow Oxide
    "E": (255.0, 170.0, 91.0),     # Phthalo Blue
    "TG": (244.0, 145.0, 176.0),   # Thalo Green
}


def _nnls_weights(target, vectors, iterations=80):
    """Multiplicative-update (Lee-Seung) non-negative least squares."""
    codes = list(vectors.keys())
    w = {code: 0.2 for code in codes}
    for _ in range(iterations):
        for code in codes:
            v = vectors[code]
            numerator = sum(v[k] * target[k] for k in range(3))
            denom = sum(
                v[k] * sum(w[c2] * vectors[c2][k] for c2 in codes) for k in range(3)
            )
            w[code] = max(0.0, w[code] * numerator / denom) if denom > 1e-9 else 0.0
    return w


def calculate_formula(r, g, b, base_size):
    """Return a dict describing an approximate pigment formula for RGB(r,g,b)."""
    r, g, b = float(r), float(g), float(b)
    capacity_ml = CAPACITY_ML.get(base_size, CAPACITY_ML["4L"])

    if r >= 253 and g >= 253 and b >= 253:
        return {"lines": [], "total_volume_ml": Decimal("0"), "capacity_ml": Decimal(str(capacity_ml)), "warning": False}

    target = (255.0 - r, 255.0 - g, 255.0 - b)
    weights = _nnls_weights(target, _CHROMATIC_VECTORS)
    weight_sum = sum(weights.values())

    tint_strength = max(0.0, min(1.0, sum(target) / (3 * 255.0)))
    chromatic_budget_ml = tint_strength * capacity_ml * 0.97

    avg_rgb = (r + g + b) / 3
    lightness_extra = max(0.0, (avg_rgb / 255.0) - 0.5) * 2  # 0..1
    kx_ml = lightness_extra * capacity_ml * 0.35

    candidate_ml = {}
    if weight_sum > 1e-6:
        for code, w in weights.items():
            ml = (w / weight_sum) * chromatic_budget_ml
            if ml >= MIN_LINE_ML:
                candidate_ml[code] = ml
    if kx_ml >= MIN_LINE_ML:
        candidate_ml["KX"] = kx_ml

    pigments = {p.code: p for p in Pigment.objects.filter(code__in=candidate_ml.keys())}

    formula_lines = []
    total_ml = Decimal("0")
    for code in sorted(candidate_ml.keys()):
        pigment = pigments.get(code)
        if not pigment:
            continue
        shots = (Decimal(str(candidate_ml[code])) / DISPENSER_ML_PER_SHOT).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if shots <= 0:
            continue
        volume_ml = (shots * DISPENSER_ML_PER_SHOT).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        total_ml += volume_ml
        formula_lines.append({"pigment": pigment, "shots": shots, "volume_ml": volume_ml})

    capacity_decimal = Decimal(str(capacity_ml))
    warning = total_ml > capacity_decimal * Decimal(str(WARNING_FRACTION))

    return {
        "lines": formula_lines,
        "total_volume_ml": total_ml,
        "capacity_ml": capacity_decimal,
        "warning": warning,
    }
