import base64

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from src.config import Settings, setup_logger
from src.helpers.auth import verify_api_key
from src.schema.transcription import TranscriptionJsonRequest, TranscriptionResponse
from src.services.transcriber import transcriber_service

logger = setup_logger(Settings.LOG_DIR / "router.log", name="whisper.routers.transcription")

router = APIRouter(prefix="/v1/audio", tags=["Audio Transcription"])


@router.post(
    "/transcriptions",
    response_model=TranscriptionResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def transcribe_audio_file(
    file: UploadFile = File(...),
    model: str | None = Form(None),
    language: str | None = Form(None),
    noise_reduction: bool = Form(True),
) -> TranscriptionResponse:
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file is empty",
        )

    try:
        return await transcriber_service.transcribe(
            audio_bytes=audio_bytes,
            model_name=model,
            language=language,
            noise_reduction=noise_reduction,
        )
    except Exception as e:
        logger.error(f"File transcription failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {str(e)}",
        )


@router.post(
    "/transcriptions/json",
    response_model=TranscriptionResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def transcribe_audio_json(
    payload: TranscriptionJsonRequest,
) -> TranscriptionResponse:
    if not payload.audio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'audio' field in payload",
        )

    try:
        raw_b64 = payload.audio.split(",")[-1]
        audio_bytes = base64.b64decode(raw_b64)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid base64 audio encoding: {str(e)}",
        )

    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decoded audio content is empty",
        )

    try:
        return await transcriber_service.transcribe(
            audio_bytes=audio_bytes,
            model_name=payload.model,
            language=payload.language,
            noise_reduction=payload.noise_reduction,
        )
    except Exception as e:
        logger.error(f"JSON transcription failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {str(e)}",
        )


@router.get("/status", tags=["Audio Transcription"])
async def get_transcription_status() -> dict[str, str | None]:
    return {
        "status": "ready",
        "default_model": Settings.DEFAULT_MODEL,
        "default_language": Settings.DEFAULT_LANGUAGE,
        "loaded_model": transcriber_service.loaded_model_name,
        "device": transcriber_service.device_name,
    }
