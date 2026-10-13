from __future__ import annotations

import asyncio
import time
import uuid

import numpy as np
import torch
from transformers import Pipeline, pipeline
import whisper

from src.config import (
    Settings,
    delete,
    ensure_dir,
    exists,
    get_abs_path,
    setup_logger,
    write_bytes,
)
from src.helpers.audio import apply_noise_reduction, decode_audio_bytes, save_pcm_wav
from src.schema.transcription import TranscriptionResponse

logger = setup_logger(Settings.LOG_DIR / "service.log", name="whisper.services.transcriber")

STANDARD_WHISPER_MODELS = {"tiny", "base", "small", "medium", "large", "turbo"}


class TranscriberService:
    def __init__(self) -> None:
        self._current_model: Pipeline | whisper.Whisper | None = None
        self._current_model_name: str = ""
        self._current_model_type: str = ""
        self._hf_supports_language: dict[str, bool] = {}
        self._device: str = "cuda:0" if torch.cuda.is_available() else "cpu"
        self._torch_dtype: torch.dtype = torch.float16 if torch.cuda.is_available() else torch.float32

    @property
    def loaded_model_name(self) -> str | None:
        return self._current_model_name or None

    @property
    def device_name(self) -> str:
        return self._device

    def is_hf_model(self, model_name: str) -> bool:
        clean = model_name.strip()
        if "/" in clean:
            return True
        if clean.lower() in STANDARD_WHISPER_MODELS:
            return False
        return False

    def load_model_sync(self, model_name: str) -> None:
        if self._current_model is not None and self._current_model_name == model_name:
            return

        logger.info(f"Loading model '{model_name}' on device '{self._device}'")
        if self.is_hf_model(model_name):
            self._current_model = pipeline(
                "automatic-speech-recognition",
                model=model_name,
                torch_dtype=self._torch_dtype,
                device=self._device,
            )
            self._current_model_type = "hf"
        else:
            self._current_model = whisper.load_model(
                name=model_name,
                device="cuda" if torch.cuda.is_available() else "cpu",
            )
            self._current_model_type = "whisper"

        self._current_model_name = model_name
        logger.info(f"Successfully loaded model '{model_name}' ({self._current_model_type})")

    async def ensure_model_loaded(self, model_name: str) -> None:
        if self._current_model is not None and self._current_model_name == model_name:
            return
        await asyncio.to_thread(self.load_model_sync, model_name)

    def _execute_hf_inference(
        self,
        audio_input: np.ndarray,
        model_name: str,
        language: str | None,
    ) -> str:
        with torch.inference_mode():
            if not isinstance(self._current_model, Pipeline):
                raise RuntimeError("Loaded model is not a Hugging Face Pipeline")

            use_lang = self._hf_supports_language.get(model_name, True)
            if language and use_lang:
                try:
                    res = self._current_model(audio_input, generate_kwargs={"language": language})
                    self._hf_supports_language[model_name] = True
                    if isinstance(res, dict):
                        return str(res.get("text", "")).strip()
                    return str(res).strip()
                except Exception as e:
                    logger.warning(f"Model '{model_name}' failed with generate_kwargs language='{language}': {e}")
                    self._hf_supports_language[model_name] = False

            res = self._current_model(audio_input)
            if isinstance(res, dict):
                return str(res.get("text", "")).strip()
            return str(res).strip()

    def _execute_whisper_inference(
        self,
        wav_path: str,
        language: str | None,
    ) -> tuple[str, str]:
        with torch.inference_mode():
            if not isinstance(self._current_model, whisper.Whisper):
                raise RuntimeError("Loaded model is not a Whisper model")

            use_fp16 = torch.cuda.is_available() and str(self._current_model.device).startswith("cuda")
            kwargs: dict[str, bool | str] = {"fp16": use_fp16}
            if language:
                kwargs["language"] = language

            result = self._current_model.transcribe(wav_path, **kwargs)
            text = str(result.get("text", "")).strip()
            detected_lang = str(result.get("language", language or "")).strip()
            return text, detected_lang

    async def transcribe(
        self,
        audio_bytes: bytes,
        model_name: str | None = None,
        language: str | None = None,
        noise_reduction: bool | None = None,
    ) -> TranscriptionResponse:
        start_time = time.perf_counter()

        target_model = (model_name or Settings.DEFAULT_MODEL).strip()
        target_lang = (language or Settings.DEFAULT_LANGUAGE).strip().lower()
        if not target_lang or target_lang == "auto":
            target_lang = None

        apply_nr = Settings.NOISE_REDUCTION_DEFAULT if noise_reduction is None else noise_reduction

        await self.ensure_model_loaded(target_model)

        ensure_dir("data/tmp")
        temp_rel = f"data/tmp/{uuid.uuid4().hex}.wav"
        write_bytes(temp_rel, audio_bytes)
        abs_path = get_abs_path(temp_rel)

        try:
            raw_audio = await asyncio.to_thread(decode_audio_bytes, audio_bytes, abs_path)

            if apply_nr:
                processed_audio = await asyncio.to_thread(apply_noise_reduction, raw_audio, 16000)
                await asyncio.to_thread(save_pcm_wav, processed_audio, abs_path, 16000)
            else:
                processed_audio = raw_audio

            if self._current_model_type == "hf":
                text = await asyncio.to_thread(
                    self._execute_hf_inference,
                    processed_audio,
                    target_model,
                    target_lang,
                )
                final_lang = target_lang or "bn"
            else:
                text, detected_lang = await asyncio.to_thread(
                    self._execute_whisper_inference,
                    abs_path,
                    target_lang,
                )
                final_lang = detected_lang or target_lang or "en"

            duration = round(time.perf_counter() - start_time, 3)

            return TranscriptionResponse(
                text=text.strip(),
                language=final_lang,
                model=target_model,
                noise_reduction=apply_nr,
                duration_seconds=duration,
            )
        finally:
            if exists(temp_rel):
                try:
                    delete(temp_rel)
                except Exception as e:
                    logger.warning(f"Could not purge temporary audio file: {e}")


transcriber_service = TranscriberService()
