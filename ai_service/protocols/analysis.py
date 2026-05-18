from abc import ABC, abstractmethod

from ai_service.domain.analysis import BioAnalysisResult


class BioAnalyzerProtocol(ABC):
    @abstractmethod
    async def analyze_bio(self, *, profile_id: int, bio: str | None) -> BioAnalysisResult: ...
