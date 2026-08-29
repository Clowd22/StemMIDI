/* StemMIDI — DAW 風フロントエンド（Sync Player / 波形 / コードハイライト） */
"use strict";

const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

const state = {
  file: null,
  objectUrl: null,
  audio: null,
  audioCtx: null,
  result: null,
  rafId: null,
  isYouTube: false,
  wavePeaks: null,
};

const $ = (id) => document.getElementById(id);

const uploadSection = $("upload-section");
const dropZone = $("drop-zone");
const fileInput = $("file-input");
const fileInfo = $("file-info");
const loading = $("loading");
const results = $("results");
const playBtn = $("play-btn");
const downloadBtn = $("download-btn");
const youtubeUrlInput = $("youtube-url");
const youtubeBtn = $("youtube-btn");
const timeCurrent = $("time-current");
const timeTotal = $("time-total");
const waveformCanvas = $("waveform");

/* ---------- YouTube IFrame API ---------- */
let ytPlayer = null;
let ytReady = false;
let pendingVideoId = null;

function onYouTubeIframeAPIReady() {
  ytReady = true;
  if (pendingVideoId) {
    createYoutubePlayer(pendingVideoId);
    pendingVideoId = null;
  }
}

/* ---------- ファイルアップロード ---------- */
dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  if (e.dataTransfer.files.length > 0) handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length > 0) handleFile(fileInput.files[0]);
});

function handleFile(file) {
  state.file = file;
  fileInfo.textContent = `SELECTED: ${file.name} — ${formatSize(file.size)}`;
  fileInfo.classList.remove("hidden");
  const form = new FormData();
  form.append("file", file);
  runAnalyze("/api/analyze", form);
}

/* ---------- YouTube 解析 ---------- */
youtubeBtn.addEventListener("click", () => {
  const url = youtubeUrlInput.value.trim();
  if (!url) return;
  const form = new FormData();
  form.append("url", url);
  runAnalyze("/api/analyze-youtube", form);
});
youtubeUrlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") youtubeBtn.click();
});

/* ---------- 解析リクエスト ---------- */
async function runAnalyze(endpoint, form) {
  uploadSection.classList.add("hidden");
  loading.classList.remove("hidden");
  results.classList.add("hidden");

  try {
    const res = await fetch(endpoint, { method: "POST", body: form });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        detail = (await res.json()).detail || detail;
      } catch (_) {
        /* JSON 以外は無視 */
      }
      throw new Error(detail);
    }
    const data = await res.json();
    renderResult(data);
  } catch (err) {
    loading.classList.add("hidden");
    uploadSection.classList.remove("hidden");
    showError(`解析に失敗しました: ${err.message}`);
  }
}

/* ---------- 結果描画 ---------- */
async function renderResult(data) {
  state.result = data;
  loading.classList.add("hidden");
  results.classList.remove("hidden");

  $("meta-title").textContent = data.title || "アップロード音源";
  $("meta-bpm").textContent = data.bpm;
  $("meta-chords").textContent = data.chords.length;
  $("meta-beats").textContent = data.beat_count;

  renderChordTimeline(data.chords);
  renderPianoRoll(data.chords, data.bass_notes, data.bpm);

  downloadBtn.onclick = () => {
    const a = document.createElement("a");
    a.href = data.midi_url;
    a.download = "multitrack.mid";
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  if (data.youtube_id) {
    setupYoutube(data.youtube_id);
  } else {
    setupAudio();
  }
}

/* ---------- コードタイムライン ---------- */
function renderChordTimeline(chords) {
  const container = $("chord-timeline");
  container.innerHTML = "";
  if (chords.length === 0) return;
  const total = chords[chords.length - 1].end;
  chords.forEach((ch) => {
    const cell = document.createElement("div");
    cell.className = "chord-cell";
    cell.style.width = `${((ch.end - ch.start) / total) * 100}%`;
    cell.textContent = ch.chord;
    cell.dataset.start = ch.start;
    cell.dataset.end = ch.end;
    cell.addEventListener("click", () => seekTo((ch.start + ch.end) / 2));
    container.appendChild(cell);
  });
}

function highlightChord(t) {
  document.querySelectorAll(".chord-cell").forEach((cell) => {
    const start = parseFloat(cell.dataset.start);
    const end = parseFloat(cell.dataset.end);
    cell.classList.toggle("active", t >= start && t < end);
  });
}

/* ---------- ピアノロール ---------- */
function chordToNotes(chordName) {
  const name = chordName.trim();
  const isMinor = name.endsWith("m") && !name.endsWith("maj");
  const rootName = isMinor ? name.slice(0, -1) : name;
  const root = NOTE_NAMES.indexOf(rootName);
  const intervals = isMinor ? [0, 3, 7] : [0, 4, 7];
  return intervals.map((i) => 60 + root + i);
}

function renderPianoRoll(chords, bassNotes, bpm) {
  const canvas = $("piano-roll");
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.scale(dpr, dpr);

  const notes = [];
  chords.forEach((ch) => {
    chordToNotes(ch.chord).forEach((n) =>
      notes.push({ start: ch.start, end: ch.end, note: n, kind: "chord" })
    );
  });
  bassNotes.forEach((n) =>
    notes.push({ start: n.start, end: n.end, note: n.note, kind: "bass" })
  );

  const maxTime = Math.max(...notes.map((n) => n.end), 1);
  const minNote = Math.min(...notes.map((n) => n.note), 36) - 2;
  const maxNote = Math.max(...notes.map((n) => n.note), 72) + 2;
  const noteRange = Math.max(maxNote - minNote, 12);
  const padLeft = 40;
  const padTop = 16;
  const padBottom = 16;
  const plotW = width - padLeft - 8;
  const plotH = height - padTop - padBottom;

  const x = (t) => padLeft + (t / maxTime) * plotW;
  const y = (note) => padTop + (1 - (note - minNote) / noteRange) * plotH;

  // 背景
  ctx.fillStyle = "#121214";
  ctx.fillRect(0, 0, width, height);

  // ビートグリッド
  const beatDur = 60 / (bpm || 120);
  ctx.strokeStyle = "rgba(255,255,255,0.05)";
  ctx.lineWidth = 1;
  for (let t = 0; t <= maxTime; t += beatDur) {
    ctx.beginPath();
    ctx.moveTo(x(t), padTop);
    ctx.lineTo(x(t), padTop + plotH);
    ctx.stroke();
  }

  // ノート行
  ctx.strokeStyle = "rgba(255,255,255,0.04)";
  for (let note = minNote; note <= maxNote; note++) {
    ctx.beginPath();
    ctx.moveTo(padLeft, y(note));
    ctx.lineTo(width - 8, y(note));
    ctx.stroke();
  }

  // ノート名
  ctx.fillStyle = "#71717A";
  ctx.font = "10px monospace";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let note = minNote; note <= maxNote; note += 2) {
    const octave = Math.floor(note / 12) - 1;
    ctx.fillText(`${NOTE_NAMES[note % 12]}${octave}`, padLeft - 6, y(note));
  }

  // ノート矩形（コード=アンバー / ベース=グリーン）
  notes.forEach((n) => {
    ctx.fillStyle =
      n.kind === "chord" ? "rgba(245, 158, 11, 0.85)" : "rgba(34, 197, 94, 0.9)";
    const rx = x(n.start);
    const ry = y(n.note);
    const rw = Math.max(x(n.end) - rx, 2);
    const rh = Math.max((plotH / noteRange) * 0.9, 2);
    ctx.fillRect(rx, ry - rh / 2, rw, rh);
  });
}

/* ---------- 音源セットアップ（ファイル） ---------- */
function setupAudio() {
  state.isYouTube = false;
  $("youtube-player").classList.add("hidden");

  if (state.audio) {
    state.audio.pause();
    state.audio.src = "";
  }
  if (state.objectUrl) URL.revokeObjectURL(state.objectUrl);

  state.objectUrl = URL.createObjectURL(state.file);
  state.audio = new Audio(state.objectUrl);
  state.audio.addEventListener("ended", onPlaybackEnded);
  loadWaveform(state.objectUrl);
  playBtn.innerHTML = "▶";
}

/* ---------- 音源セットアップ（YouTube） ---------- */
function setupYoutube(videoId) {
  state.isYouTube = true;
  playBtn.innerHTML = "▶";
  const el = $("youtube-player");
  el.classList.remove("hidden");
  if (ytReady) {
    createYoutubePlayer(videoId);
  } else {
    pendingVideoId = videoId;
  }
}

function createYoutubePlayer(videoId) {
  if (ytPlayer) ytPlayer.destroy();
  ytPlayer = new YT.Player("youtube-player", {
    videoId: videoId,
    playerVars: { rel: 0, controls: 1 },
    events: {
      onReady: (event) => {
        const dur = event.target.getDuration();
        timeTotal.textContent = formatTime(dur);
        startSyncLoop();
      },
      onStateChange: (event) => {
        playBtn.innerHTML =
          event.data === YT.PlayerState.PLAYING ? "⏸" : "▶";
        if (event.data === YT.PlayerState.PLAYING) startSyncLoop();
      },
    },
  });
}

/* ---------- 波形表示（Web Audio API） ---------- */
async function loadWaveform(url) {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!state.audioCtx) state.audioCtx = new AudioCtx();
    const ctx = state.audioCtx;

    const resp = await fetch(url);
    const buf = await resp.arrayBuffer();
    const audioBuf = await ctx.decodeAudioData(buf);
    const channel = audioBuf.getChannelData(0);

    const width = waveformCanvas.clientWidth;
    const block = Math.floor(channel.length / width);
    const peaks = new Float32Array(width);
    for (let i = 0; i < width; i++) {
      let sum = 0;
      for (let j = 0; j < block; j++) sum += Math.abs(channel[i * block + j]);
      peaks[i] = sum / block;
    }
    const max = Math.max(...peaks) || 1;
    state.wavePeaks = peaks.map((p) => p / max);
    timeTotal.textContent = formatTime(audioBuf.duration);
    drawWaveform(0);
  } catch (err) {
    console.warn("waveform decode failed:", err);
  }
}

let lastWaveWidth = 0;
function drawWaveform(currentTime = 0) {
  const canvas = waveformCanvas;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;

  if (canvas.width !== Math.round(width * dpr)) {
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.scale(dpr, dpr);
  }

  ctx.fillStyle = "#121214";
  ctx.fillRect(0, 0, width, height);

  if (!state.wavePeaks || state.wavePeaks.length === 0) {
    ctx.fillStyle = "#3F3F46";
    ctx.font = "11px monospace";
    ctx.textAlign = "center";
    ctx.fillText("waveform unavailable", width / 2, height / 2);
    return;
  }

  const mid = height / 2;
  for (let i = 0; i < state.wavePeaks.length; i++) {
    const h = state.wavePeaks[i] * height * 0.85;
    ctx.fillStyle = "#3F3F46";
    ctx.fillRect(i, mid - h / 2, 1, h);
  }

  // 再生カーソル
  const total = getTotalDuration();
  if (currentTime > 0 && total > 0) {
    const cx = (currentTime / total) * width;
    ctx.fillStyle = "#F59E0B";
    ctx.fillRect(cx - 1, 0, 2, height);
  }
}

/* ---------- 再生制御 ---------- */
playBtn.addEventListener("click", togglePlay);

function togglePlay() {
  if (state.isYouTube) {
    if (!ytPlayer) return;
    if (state.audioCtx && state.audioCtx.state === "suspended") state.audioCtx.resume();
    if (ytPlayer.getPlayerState() === YT.PlayerState.PLAYING) {
      ytPlayer.pauseVideo();
    } else {
      ytPlayer.playVideo();
    }
  } else {
    if (!state.audio) return;
    if (state.audioCtx && state.audioCtx.state === "suspended") state.audioCtx.resume();
    if (state.audio.paused) {
      state.audio.play();
    } else {
      state.audio.pause();
    }
  }
}

function onPlaybackEnded() {
  playBtn.innerHTML = "▶";
  highlightChord(0);
  drawWaveform(0);
}

/* ---------- 同期ループ ---------- */
function startSyncLoop() {
  if (state.rafId) cancelAnimationFrame(state.rafId);
  const loop = () => {
    const t = getCurrentTime();
    updateTimeDisplay(t);
    highlightChord(t);
    drawWaveform(t);
    if (isPlaying()) {
      state.rafId = requestAnimationFrame(loop);
    } else {
      state.rafId = null;
    }
  };
  loop();
}

function getCurrentTime() {
  if (state.isYouTube) {
    return ytPlayer && ytPlayer.getCurrentTime ? ytPlayer.getCurrentTime() || 0 : 0;
  }
  return state.audio ? state.audio.currentTime : 0;
}

function getTotalDuration() {
  if (state.isYouTube) {
    return ytPlayer && ytPlayer.getDuration ? ytPlayer.getDuration() || 0 : 0;
  }
  return state.audio ? state.audio.duration || 0 : 0;
}

function isPlaying() {
  if (state.isYouTube) {
    return (
      ytPlayer &&
      ytPlayer.getPlayerState &&
      ytPlayer.getPlayerState() === YT.PlayerState.PLAYING
    );
  }
  return state.audio && !state.audio.paused && !state.audio.ended;
}

/* ---------- 時間表示 / シーク ---------- */
function updateTimeDisplay(t) {
  timeCurrent.textContent = formatTime(t);
  timeTotal.textContent = formatTime(getTotalDuration());
}

function formatTime(sec) {
  if (!isFinite(sec) || sec < 0) sec = 0;
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  const d = Math.floor((sec % 1) * 10);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${d}`;
}

function seekTo(t) {
  if (state.isYouTube) {
    if (ytPlayer) ytPlayer.seekTo(t, true);
  } else if (state.audio) {
    state.audio.currentTime = t;
    updateTimeDisplay(t);
    highlightChord(t);
    drawWaveform(t);
  }
}

waveformCanvas.addEventListener("click", (e) => {
  const rect = waveformCanvas.getBoundingClientRect();
  const total = getTotalDuration();
  if (total <= 0) return;
  const t = ((e.clientX - rect.left) / rect.width) * total;
  seekTo(t);
});

/* ---------- ユーティリティ ---------- */
function showError(message) {
  const existing = document.querySelector(".error-message");
  if (existing) existing.remove();
  const div = document.createElement("div");
  div.className = "error-message";
  div.textContent = message;
  uploadSection.after(div);
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}
