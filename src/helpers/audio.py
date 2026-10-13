import io
import wave

import noisereduce as nr
import numpy as np
import whisper

from src.config import Settings, setup_logger

logger = setup_logger(Settings.LOG_DIR / "helper.log", name="whisper.helpers.audio")


def decode_audio_bytes(audio_bytes: bytes, temp_wav_path: str) -> np.ndarray:
    if audio_bytes.startswith(b"RIFF") and b"WAVE" in audio_bytes[:16]:
        try:
            with io.BytesIO(audio_bytes) as bio:
                with wave.open(bio, "rb") as wf:
                    if wf.getnchannels() == 1 and wf.getframerate() == 16000 and wf.getsampwidth() == 2:
                        frames = wf.readframes(wf.getnframes())
                        return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        except Exception as e:
            logger.warning(f"Fast wave parsing skipped, falling back to whisper.load_audio: {e}")
    return whisper.load_audio(temp_wav_path)


def apply_noise_reduction(audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    try:
        return nr.reduce_noise(
            y=audio,
            sr=sample_rate,
            stationary=True,
            prop_decrease=0.75,
        )
    except Exception as e:
        logger.error(f"Noise reduction failed: {e}")
        return audio


def save_pcm_wav(audio_data: np.ndarray, target_wav_path: str, sample_rate: int = 16000) -> None:
    int_data = np.clip(audio_data * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(target_wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int_data.tobytes())
