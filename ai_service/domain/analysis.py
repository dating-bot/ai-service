from dataclasses import dataclass


@dataclass(slots=True)
class BioAnalysisResult:
    quality_score: float
    issues: list[str]
    suggestions: list[str]
    safe: bool
    contact_detected: bool
    confidence: float
