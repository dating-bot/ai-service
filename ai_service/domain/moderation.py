from dataclasses import dataclass


@dataclass(slots=True)
class ModerationFlag:
    profile_id: int
    photo_id: int | None
    flag_type: str
    severity: str
    reason: str
    nsfw_score: float | None = None
