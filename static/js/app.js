(function () {
  const apiKeyInput = document.getElementById("apiKeyInput");
  const modelSelect = document.getElementById("modelSelect");
  const languageSelect = document.getElementById("languageSelect");
  const noiseToggle = document.getElementById("noiseToggle");

  const micBtn = document.getElementById("micBtn");
  const micIcon = micBtn.querySelector(".mic-icon");
  const stopIcon = micBtn.querySelector(".stop-icon");

  const waveformCanvas = document.getElementById("waveformCanvas");
  const canvasCtx = waveformCanvas.getContext("2d");
  const timerDisplay = document.getElementById("timerDisplay");
  const statusHint = document.getElementById("statusHint");

  const playbackZone = document.getElementById("playbackZone");
  const audioPlayer = document.getElementById("audioPlayer");
  const discardBtn = document.getElementById("discardBtn");
  const sendBtn = document.getElementById("sendBtn");
  const sendSpinner = document.getElementById("sendSpinner");
  const btnText = sendBtn.querySelector(".btn-text");

  const resultText = document.getElementById("resultText");
  const resultMeta = document.getElementById("resultMeta");
  const metaLang = document.getElementById("metaLang");
  const metaModel = document.getElementById("metaModel");
  const metaNoise = document.getElementById("metaNoise");
  const metaDuration = document.getElementById("metaDuration");
  const copyBtn = document.getElementById("copyBtn");
  const copyBtnText = document.getElementById("copyBtnText");

  const serverStatusBadge = document.getElementById("serverStatusBadge");
  const serverStatusText = document.getElementById("serverStatusText");

  let mediaRecorder = null;
  let audioChunks = [];
  let audioBlob = null;
  let audioStream = null;
  let audioContext = null;
  let analyser = null;
  let dataArray = null;
  let animationFrameId = null;

  let timerInterval = null;
  let recordingSeconds = 0;

  const SAVED_KEY = "whisper_stt_api_key";
  const DEFAULT_KEY = "8801758838322";

  function initApiKey() {
    const saved = localStorage.getItem(SAVED_KEY);
    apiKeyInput.value = saved || DEFAULT_KEY;
    apiKeyInput.addEventListener("input", () => {
      localStorage.setItem(SAVED_KEY, apiKeyInput.value.trim());
    });
  }

  async function checkServerHealth() {
    try {
      const res = await fetch("/health");
      if (res.ok) {
        const data = await res.json();
        serverStatusBadge.className = "server-status online";
        serverStatusText.textContent = `সার্ভার অনলাইন (${data.loaded_model || "রেডি"})`;
      } else {
        serverStatusBadge.className = "server-status error";
        serverStatusText.textContent = "সার্ভার এরর";
      }
    } catch {
      serverStatusBadge.className = "server-status error";
      serverStatusText.textContent = "সার্ভার অফলাইন";
    }
  }

  function formatTime(totalSeconds) {
    const m = Math.floor(totalSeconds / 60).toString().padStart(2, "0");
    const s = (totalSeconds % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  }

  function startTimer() {
    recordingSeconds = 0;
    timerDisplay.textContent = "00:00";
    timerInterval = setInterval(() => {
      recordingSeconds += 1;
      timerDisplay.textContent = formatTime(recordingSeconds);
    }, 1000);
  }

  function stopTimer() {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  function drawEmptyWaveform() {
    canvasCtx.clearRect(0, 0, waveformCanvas.width, waveformCanvas.height);
    canvasCtx.lineWidth = 2;
    canvasCtx.strokeStyle = "rgba(255, 255, 255, 0.1)";
    canvasCtx.beginPath();
    const sliceWidth = waveformCanvas.width / 40;
    let x = 0;
    for (let i = 0; i < 40; i++) {
      const y = waveformCanvas.height / 2;
      if (i === 0) canvasCtx.moveTo(x, y);
      else canvasCtx.lineTo(x, y);
      x += sliceWidth;
    }
    canvasCtx.stroke();
  }

  function drawLiveWaveform() {
    if (!analyser || !dataArray) return;
    analyser.getByteFrequencyData(dataArray);

    canvasCtx.clearRect(0, 0, waveformCanvas.width, waveformCanvas.height);

    const barCount = 48;
    const barWidth = Math.floor(waveformCanvas.width / barCount) - 3;
    let x = 4;

    for (let i = 0; i < barCount; i++) {
      const idx = Math.floor((i / barCount) * dataArray.length);
      const val = dataArray[idx];
      const percent = val / 255;
      const barHeight = Math.max(percent * (waveformCanvas.height - 12), 4);
      const y = (waveformCanvas.height - barHeight) / 2;

      const gradient = canvasCtx.createLinearGradient(0, y, 0, y + barHeight);
      gradient.addColorStop(0, "#ec4899");
      gradient.addColorStop(0.5, "#8b5cf6");
      gradient.addColorStop(1, "#6366f1");

      canvasCtx.fillStyle = gradient;
      canvasCtx.beginPath();
      canvasCtx.roundRect(x, y, barWidth, barHeight, 3);
      canvasCtx.fill();

      x += barWidth + 3;
    }

    animationFrameId = requestAnimationFrame(drawLiveWaveform);
  }

  async function startRecording() {
    try {
      audioChunks = [];
      audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          channelCount: 1,
        },
      });

      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioContext.createMediaStreamSource(audioStream);
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 128;
      source.connect(analyser);
      dataArray = new Uint8Array(analyser.frequencyBinCount);

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

      mediaRecorder = new MediaRecorder(audioStream, { mimeType });
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = () => {
        audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || "audio/webm" });
        const audioUrl = URL.createObjectURL(audioBlob);
        audioPlayer.src = audioUrl;
        playbackZone.classList.remove("hidden");
        statusHint.textContent = "রেকর্ডিং সম্পন্ন! অডিও শুনুন অথবা সেন্ড করুন";
      };

      mediaRecorder.start(100);

      micBtn.classList.add("recording");
      micIcon.classList.add("hidden");
      stopIcon.classList.remove("hidden");
      playbackZone.classList.add("hidden");
      statusHint.textContent = "রেকর্ডিং চলছে... কথা বলুন (বন্ধ করতে আবার চাপুন)";

      startTimer();
      drawLiveWaveform();
    } catch (err) {
      statusHint.textContent = "মাইক্রোফোন এক্সেস পাওয়া যায়নি: " + err.message;
    }
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
    if (audioStream) {
      audioStream.getTracks().forEach((track) => track.stop());
      audioStream = null;
    }
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId);
      animationFrameId = null;
    }
    if (audioContext) {
      audioContext.close();
      audioContext = null;
    }

    micBtn.classList.remove("recording");
    micIcon.classList.remove("hidden");
    stopIcon.classList.add("hidden");

    stopTimer();
    drawEmptyWaveform();
  }

  function discardRecording() {
    audioBlob = null;
    audioChunks = [];
    audioPlayer.src = "";
    playbackZone.classList.add("hidden");
    timerDisplay.textContent = "00:00";
    statusHint.textContent = "রেকর্ড করতে মাউথ অডিও বাটনে ক্লিক করুন";
    drawEmptyWaveform();
  }

  async function sendAudio() {
    if (!audioBlob) return;

    const apiKey = (apiKeyInput.value || "").trim();
    const model = modelSelect.value;
    const language = languageSelect.value;
    const noiseReduction = noiseToggle.checked ? "true" : "false";

    sendBtn.disabled = true;
    sendSpinner.classList.remove("hidden");
    btnText.classList.add("hidden");
    statusHint.textContent = "অডিও ট্রান্সক্রিপশন প্রসেস হচ্ছে, অনুগ্রহ করে অপেক্ষা করুন...";

    resultText.textContent = "প্রসেসিং হচ্ছে...";

    const formData = new FormData();
    formData.append("file", audioBlob, "recording.webm");
    formData.append("model", model);
    formData.append("language", language);
    formData.append("noise_reduction", noiseReduction);

    try {
      const res = await fetch("/v1/audio/transcriptions", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
        },
        body: formData,
      });

      if (!res.ok) {
        let errDetail = `HTTP ${res.status}`;
        try {
          const errData = await res.json();
          errDetail = errData.detail || errDetail;
        } catch {}
        throw new Error(errDetail);
      }

      const data = await res.json();
      resultText.textContent = data.text || "(কোন কথা সনাক্ত করা যায়নি)";

      metaLang.textContent = `ভাষা: ${data.language || language}`;
      metaModel.textContent = `মডেল: ${data.model || model}`;
      metaNoise.textContent = `নয়েজ রিডাকশন: ${data.noise_reduction ? "চালু" : "বন্ধ"}`;
      metaDuration.textContent = `সময়: ${data.duration_seconds || 0}s`;
      resultMeta.classList.remove("hidden");

      statusHint.textContent = "ট্রান্সক্রিপশন সফলভাবে সম্পন্ন হয়েছে!";
    } catch (err) {
      resultText.textContent = "ত্রুটি: " + err.message;
      statusHint.textContent = "রিকোয়েস্ট ব্যর্থ হয়েছে: " + err.message;
      resultMeta.classList.add("hidden");
    } finally {
      sendBtn.disabled = false;
      sendSpinner.classList.add("hidden");
      btnText.classList.remove("hidden");
    }
  }

  function copyResult() {
    const text = resultText.textContent;
    if (!text || text.startsWith("এখানে আপনার") || text.startsWith("ত্রুটি:")) return;

    navigator.clipboard.writeText(text).then(() => {
      copyBtnText.textContent = "কপি হয়েছে!";
      setTimeout(() => {
        copyBtnText.textContent = "কপি";
      }, 2000);
    });
  }

  micBtn.addEventListener("click", () => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      stopRecording();
    } else {
      startRecording();
    }
  });

  discardBtn.addEventListener("click", discardRecording);
  sendBtn.addEventListener("click", sendAudio);
  copyBtn.addEventListener("click", copyResult);

  initApiKey();
  drawEmptyWaveform();
  checkServerHealth();
  setInterval(checkServerHealth, 15000);
})();
