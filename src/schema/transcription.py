from pydantic import BaseModel


class TranscriptionResponse(BaseModel):
    text: str
    language: str
    model: str
    noise_reduction: bool
    duration_seconds: float | None = None


class TranscriptionJsonRequest(BaseModel):
    audio: str
    model: str | None = None
    language: str | None = None
    noise_reduction: bool | None = None


class HealthResponse(BaseModel):
    status: str
    project: str
    environment: str
    version: str
    loaded_model: str | None = None
    device: str
