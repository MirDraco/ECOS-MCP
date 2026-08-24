from typing import Any


class EcosError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        return {"success": False, "error": {"code": self.code, "message": self.message, "details": self.details}}


class AmbiguousIndicatorError(EcosError):
    def __init__(self, candidates: list[dict[str, Any]]):
        super().__init__("AMBIGUOUS_INDICATOR", "지표가 여러 통계항목과 일치합니다. 후보를 선택해 주세요.", {"candidates": candidates})
