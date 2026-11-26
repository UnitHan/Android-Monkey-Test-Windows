"""SVG presentation data. Preserve gaps and extrema when reducing large series."""

import math

from monkey_api.domain.analysis import MAX_OBSERVED_GAP_S, metric_stats
from monkey_api.domain.models import PerfSample


def _groups(samples: list[PerfSample], metric: str) -> list[list[tuple[float, float]]]:
    groups = []
    current = []
    previous = None
    for sample in samples:
        value = getattr(sample, metric)
        valid = sample.running is not False and value is not None and math.isfinite(value) and value >= 0
        connected = previous is not None and sample.run == previous.run and sample.source == previous.source
        connected = connected and 0 < (sample.at - previous.at).total_seconds() <= MAX_OBSERVED_GAP_S
        if not valid or not connected:
            if current:
                groups.append(current)
            current = []
        if valid:
            current.append((sample.at.timestamp(), value))
        previous = sample if valid else None
    if current:
        groups.append(current)
    return groups


def _reduce(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) <= 400:
        return points
    indices = {0, len(points) - 1}
    step = math.ceil(len(points) / 180)
    for start in range(0, len(points), step):
        bucket = range(start, min(start + step, len(points)))
        indices.add(min(bucket, key=lambda i: points[i][1]))
        indices.add(max(bucket, key=lambda i: points[i][1]))
    return [points[i] for i in sorted(indices)]


def chart_data(samples: list[PerfSample], metric: str, title: str, unit: str, color: str) -> dict:
    ordered = sorted(samples, key=lambda s: s.at)
    groups = _groups(ordered, metric)
    stats = metric_stats(v for group in groups for _, v in group)
    start = ordered[0].at.timestamp() if ordered else 0
    span = max(1, ordered[-1].at.timestamp() - start) if ordered else 1
    ceiling = max(1, math.ceil((stats.max or 0) * 1.12 / 5) * 5)
    paths, dots = [], []
    for group in groups:
        coords = [(52 + (t - start) / span * 572, 202 - v / ceiling * 186) for t, v in _reduce(group)]
        if len(coords) == 1:
            dots.extend(coords)
        else:
            paths.append(" ".join(f"{'M' if i == 0 else 'L'}{x:.2f},{y:.2f}" for i, (x, y) in enumerate(coords)))
    return {
        "title": title,
        "unit": unit,
        "color": color,
        "stats": stats,
        "paths": paths,
        "dots": dots,
        "y_ticks": [(202 - i * 46.5, ceiling * i / 4) for i in range(5)],
        "x_ticks": [(52 + i * 143, f"{int(span * i / 4) // 60}:{int(span * i / 4) % 60:02d}") for i in range(5)],
    }
