"""IELTS 写作 AI 批改系统 — 核心模块"""

__version__ = "1.0.0"

from .core import (
    IELTS_BAND_PROFILES, IELTS_WRITING_STRATEGIES, WRITING_ROADMAPS,
    heuristic_score, build_enriched_report, build_combined_report,
    map_score_to_band_key,
)
from .grader import grade_essay
from .report import print_report, render_html, print_combined_report
