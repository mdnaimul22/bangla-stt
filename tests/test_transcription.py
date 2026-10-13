import base64
import io
import wave
import numpy as np
import pytest
from httpx import AsyncClient

TEST_API_KEY = "test-secret-key-12345"


def create_dummy_wav_bytes(duration_sec: float = 0.5) -> bytes:
    sample_rate = 16000
    num_samples = int(sample_rate * duration_sec)
    audio = np.zeros(num_samples, dtype=np.int16)
    bio = io.BytesIO()
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    return bio.getvalue()


@pytest.mark.asyncio
async def test_root_ui(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert "Whisper STT" in response.text
    assert "micBtn" in response.text


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "project" in data
    assert "device" in data


@pytest.mark.asyncio
async def test_transcribe_unauthorized(client: AsyncClient):
    wav_bytes = create_dummy_wav_bytes()
    response = await client.post(
        "/v1/audio/transcriptions",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
    )
    assert response.status_code == 401

    response_bad_key = await client.post(
        "/v1/audio/transcriptions",
        headers={"Authorization": "Bearer wrong-token"},
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
    )
    assert response_bad_key.status_code == 401


@pytest.mark.asyncio
async def test_transcribe_empty_file(client: AsyncClient):
    response = await client.post(
        "/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        files={"file": ("empty.wav", b"", "audio/wav")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_transcribe_multipart_success(client: AsyncClient):
    wav_bytes = create_dummy_wav_bytes()
    response = await client.post(
        "/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        files={"file": ("audio.wav", wav_bytes, "audio/wav")},
        data={"model": "shhossain/whisper-base-bn", "noise_reduction": "true"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert "language" in data
    assert data["model"] == "shhossain/whisper-base-bn"
    assert data["noise_reduction"] is True


@pytest.mark.asyncio
async def test_transcribe_json_success(client: AsyncClient):
    wav_bytes = create_dummy_wav_bytes()
    b64_audio = base64.b64encode(wav_bytes).decode("ascii")
    response = await client.post(
        "/v1/audio/transcriptions/json",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        json={
            "audio": b64_audio,
            "model": "shhossain/whisper-base-bn",
            "language": "bn",
            "noise_reduction": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert data["language"] == "bn"
    assert data["model"] == "shhossain/whisper-base-bn"


@pytest.mark.asyncio
async def test_transcribe_real_audio_file(client: AsyncClient):
    sample_path = "/home/naimul/.gemini/antigravity-ide/brain/62c6e560-2787-46e7-8c36-09c409ad1b98/.user_uploaded/uploaded_media_1789128466197.img"
    try:
        with open(sample_path, "rb") as f:
            audio_bytes = f.read()
    except FileNotFoundError:
        pytest.skip("User audio sample file not found")

    response = await client.post(
        "/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        files={"file": ("user_audio.webm", audio_bytes, "audio/webm")},
        data={"model": "shhossain/whisper-base-bn", "language": "bn", "noise_reduction": "true"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert len(data["text"]) > 0
    assert data["language"] == "bn"
