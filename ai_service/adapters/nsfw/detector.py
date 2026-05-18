from hashlib import sha256
from typing import final

from ai_service.protocols import NSFWDetectorProtocol


@final
class HeuristicNSFWDetectorAdapter(NSFWDetectorProtocol):
    async def detect(self, *, minio_key: str) -> float:
        key = minio_key.lower()
        if "nsfw" in key or "adult" in key:
            return 0.95

        digest = sha256(minio_key.encode()).digest()
        return (digest[0] / 255.0) * 0.25
