#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def make_plots(analysis: dict[str, Any], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = [
        _bar_svg(output_dir / "pass_rate_baseline_vs_treatment.svg", analysis, "pass_rate", "Pass rate"),
        _multi_bar_svg(
            output_dir / "cost_tokens_time_comparison.svg",
            analysis,
            [("mean_cost_usd", "Cost"), ("mean_total_tokens", "Tokens"), ("mean_agent_time_sec", "Agent time")],
        ),
        _heatmap_svg(output_dir / "per_task_delta_heatmap.svg", analysis["per_task"]),
        _scatter_svg(output_dir / "command_buffer_usage_scatter.svg", analysis["per_task"]),
        _syntax_svg(output_dir / "syntax_error_recovery.svg", analysis["per_task"]),
        _pareto_svg(output_dir / "pareto_pass_rate_cost_time.svg", analysis),
    ]
    return files


def _bar_svg(path: Path, analysis: dict[str, Any], key: str, title: str) -> Path:
    labels = list(analysis["aggregate"])
    values = [analysis["aggregate"][label].get(key, 0) for label in labels]
    return _write_simple_bars(path, title, labels, values)


def _multi_bar_svg(path: Path, analysis: dict[str, Any], specs: list[tuple[str, str]]) -> Path:
    labels = []
    values = []
    for condition, metrics in analysis["aggregate"].items():
        for key, label in specs:
            labels.append(f"{condition}\n{label}")
            values.append(metrics.get(key, 0) or 0)
    return _write_simple_bars(path, "Cost / tokens / time per trial", labels, values)


def _heatmap_svg(path: Path, rows: list[dict[str, Any]]) -> Path:
    labels = [row["task_name"][:26] for row in rows[:30]]
    values = [row.get("delta_success", 0) for row in rows[:30]]
    return _write_simple_bars(path, "Per-task delta success", labels, values, allow_negative=True)


def _scatter_svg(path: Path, rows: list[dict[str, Any]]) -> Path:
    points = [
        (row.get("estimated_saved_chars", 0) or 0, row.get("delta_tokens", 0) or 0)
        for row in rows
    ]
    return _write_scatter(path, "Command-buffer usage vs delta tokens", points)


def _syntax_svg(path: Path, rows: list[dict[str, Any]]) -> Path:
    labels = [row["task_name"][:26] for row in rows[:30]]
    values = [
        (row.get("failed_syntax_treatment", 0) or 0) - (row.get("failed_syntax_baseline", 0) or 0)
        for row in rows[:30]
    ]
    return _write_simple_bars(path, "Syntax/quoting error delta", labels, values, allow_negative=True)


def _pareto_svg(path: Path, analysis: dict[str, Any]) -> Path:
    labels = []
    values = []
    for condition, metrics in analysis["aggregate"].items():
        labels.extend([f"{condition}\npass", f"{condition}\ncost", f"{condition}\ntime"])
        values.extend([
            metrics.get("pass_rate", 0) or 0,
            metrics.get("mean_cost_usd", 0) or 0,
            metrics.get("mean_agent_time_sec", 0) or 0,
        ])
    return _write_simple_bars(path, "Pareto: pass rate vs cost/time", labels, values)


def _write_simple_bars(
    path: Path,
    title: str,
    labels: list[str],
    values: list[float],
    allow_negative: bool = False,
) -> Path:
    width = max(720, 90 * max(1, len(labels)))
    height = 420
    top = 48
    bottom = 110
    max_abs = max([abs(float(value)) for value in values] + [1.0])
    zero_y = top + (height - top - bottom) / 2 if allow_negative else height - bottom
    scale = (height - top - bottom) / (2 * max_abs if allow_negative else max_abs)
    bar_w = max(18, (width - 80) / max(1, len(labels)) * 0.55)
    parts = [_svg_header(width, height), f'<text x="24" y="30" font-size="18">{_esc(title)}</text>']
    parts.append(f'<line x1="50" y1="{zero_y:.1f}" x2="{width-20}" y2="{zero_y:.1f}" stroke="#888"/>')
    for i, (label, value) in enumerate(zip(labels, values)):
        x = 60 + i * ((width - 100) / max(1, len(labels)))
        bar_h = abs(float(value)) * scale
        y = zero_y - bar_h if value >= 0 else zero_y
        color = "#2f6f9f" if value >= 0 else "#b94e48"
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{color}"/>')
        parts.append(f'<text x="{x:.1f}" y="{height-72}" font-size="10" transform="rotate(45 {x:.1f},{height-72})">{_esc(label)}</text>')
        parts.append(f'<text x="{x:.1f}" y="{max(42, y-4):.1f}" font-size="10">{float(value):.3g}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


def _write_scatter(path: Path, title: str, points: list[tuple[float, float]]) -> Path:
    width, height = 720, 420
    max_x = max([abs(x) for x, _ in points] + [1.0])
    max_y = max([abs(y) for _, y in points] + [1.0])
    parts = [_svg_header(width, height), f'<text x="24" y="30" font-size="18">{_esc(title)}</text>']
    parts.append('<line x1="60" y1="360" x2="690" y2="360" stroke="#888"/>')
    parts.append('<line x1="60" y1="50" x2="60" y2="360" stroke="#888"/>')
    for x_value, y_value in points:
        x = 60 + (x_value / max_x) * 620
        y = 360 - ((y_value + max_y) / (2 * max_y)) * 300
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#2f6f9f"/>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


def _svg_header(width: int, height: int) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="white"/>'


def _esc(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-json", type=Path, default=Path("results/terminal_bench/analysis.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/figures"))
    args = parser.parse_args()
    files = make_plots(json.loads(args.analysis_json.read_text(encoding="utf-8")), args.output_dir)
    for file in files:
        print(file)


if __name__ == "__main__":
    main()
