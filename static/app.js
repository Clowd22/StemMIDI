/* StemMIDI フロントエンドロジック */
"use strict";

const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

const state = {
  file: null,
  objectUrl: null,
  audio: null,
  result: null,
  rafId: null,
};

const $ = (id) => document.getElementById(id);

const uploadSection = $("upload-section");
const dropZone = $("drop-zone");
const fileInput = $("file-input");
const fileInfo = $("file-info");
const loading = $("loading");
const results = $("results");
const resultMeta = $("result-meta");
const playBtn = $("play-btn");
const downloadBtn = $("download-btn");

/* ---------- ドラッグ＆ドロップ ---------- */
dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  const files = e.dataTransfer.files;
  if (files.length > 0) handleFile(files[0]);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length > 0) handleFile(fileInput.files[0]);
});

function handleFile(file) {
  state.file = file;
  fileInfo.textContent = `選択ファイル: ${file.name} (${formatSize(file.size)})`;
  fileInfo.classList.remove("hidden");
  analyze(file);
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

/* ---------- 解析 API 呼び出し ---------- */
async function analyze(file) {
  uploadSection.classList.add("hidden");
  loading.classList.remove("hidden");
  results.classList.add("hidden");

  const form = new FormData();
  form.append("file", file);

  try {
    const res = await fetch("/api/analyze", { method: "POST", body: form });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        detail = (await res.json()).detail || detail;
      } catch (_) {
        /* JSON 以外のエラーは無視 */
      }
      throw new Error(detail);
    }
    const data = await res.json();
    renderResult(data);
  } catch (err) {
    loading.classList.add("hidden");
    uploadSection.classList.remove("hidden");
    fileInfo.classList.add("hidden");
    showError(`解析に失敗しました: ${err.message}`);
  }
}

function showError(message) {
  const existing = document.querySelector(".error-message");
  if (existing) existing.remove();
  const div = document.createElement("div");
  div.className = "error-message";
  div.textContent = message;
  uploadSection.after(div);
}

/* ---------- 結果描画 ---------- */
function renderResult(data) {
  state.result = data;

  loading.classList.add("hidden");
  results.classList.remove("hidden");

  resultMeta.textContent =
    `BPM ${data.bpm} / コード ${data.chords.length} 個 / ` +
    `ベースノート ${data.bass_notes.length} ノート / ビート ${data.beat_count}`;

  renderChordTimeline(data.chords);
  renderPianoRoll(data.chords, data.bass_notes, data.bpm);
  setupAudio();

  downloadBtn.onclick = () => {
    const a = document.createElement("a");
    a.href = data.midi_url;
    a.download = "multitrack.mid";
    document.body.appendChild(a);
    a.click();
    a.remove();
  };
}

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
    container.appendChild(cell);
  });
}

function chordToNotes(chordName) {
  const name = chordName.trim();
  const isMinor = name.endsWith("m") && !name.endsWith("maj");
  const rootName = isMinor ? name.slice(0, -1) : name;
  const root = NOTE_NAMES.indexOf(rootName);
  const intervals = isMinor ? [0, 3, 7] : [0, 4, 7];
  return intervals.map((i) => 60 + root + i);
}

function renderPianoRoll(chords, bassNotes, bpm, currentTime = 0) {
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
  ctx.fillStyle = "#12151d";
  ctx.fillRect(0, 0, width, height);

  // ビートグリッド（縦線）
  const beatDur = 60 / (bpm || 120);
  ctx.strokeStyle = "rgba(255,255,255,0.06)";
  ctx.lineWidth = 1;
  for (let t = 0; t <= maxTime; t += beatDur) {
    ctx.beginPath();
    ctx.moveTo(x(t), padTop);
    ctx.lineTo(x(t), padTop + plotH);
    ctx.stroke();
  }

  // ノート行（横線）
  ctx.strokeStyle = "rgba(255,255,255,0.04)";
  for (let note = minNote; note <= maxNote; note++) {
    ctx.beginPath();
    ctx.moveTo(padLeft, y(note));
    ctx.lineTo(width - 8, y(note));
    ctx.stroke();
  }

  // ノート名ラベル（左側）
  ctx.fillStyle = "#9ca3af";
  ctx.font = "10px monospace";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let note = minNote; note <= maxNote; note += 2) {
    const octave = Math.floor(note / 12) - 1;
    ctx.fillText(`${NOTE_NAMES[note % 12]}${octave}`, padLeft - 6, y(note));
  }

  // ノート矩形
  notes.forEach((n) => {
    ctx.fillStyle = n.kind === "chord" ? "rgba(56, 189, 248, 0.75)" : "rgba(74, 222, 128, 0.8)";
    const rx = x(n.start);
    const ry = y(n.note);
    const rw = Math.max(x(n.end) - rx, 2);
    const rh = Math.max((plotH / noteRange) * 0.9, 2);
    ctx.fillRect(rx, ry - rh / 2, rw, rh);
  });

  // 再生カーソル
  ctx.strokeStyle = "#f472b6";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(x(currentTime), padTop);
  ctx.lineTo(x(currentTime), padTop + plotH);
  ctx.stroke();
}

/* ---------- 音声再生と同期表示 ---------- */
function setupAudio() {
  if (state.audio) {
    state.audio.pause();
    state.audio.src = "";
  }
  if (state.objectUrl) URL.revokeObjectURL(state.objectUrl);
  state.objectUrl = URL.createObjectURL(state.file);
  state.audio = new Audio(state.objectUrl);
  state.audio.onended = () => {
    playBtn.textContent = "▶ 再生";
    renderPianoRoll(state.result.chords, state.result.bass_notes, state.result.bpm);
  };
}

function highlightCurrentChord(t) {
  document.querySelectorAll(".chord-cell").forEach((cell) => {
    const start = parseFloat(cell.dataset.start);
    const end = parseFloat(cell.dataset.end);
    cell.classList.toggle("active", t >= start && t < end);
  });
}

function update() {
  if (!state.audio || !state.result) return;
  const t = state.audio.currentTime;
  highlightCurrentChord(t);
  renderPianoRoll(state.result.chords, state.result.bass_notes, state.result.bpm, t);
  if (!state.audio.paused && !state.audio.ended) {
    state.rafId = requestAnimationFrame(update);
  }
}

function togglePlay() {
  if (!state.audio || !state.result) return;
  if (state.audio.paused) {
    state.audio.play();
    playBtn.textContent = "⏸ 一時停止";
    update();
  } else {
    state.audio.pause();
    playBtn.textContent = "▶ 再生";
    if (state.rafId) cancelAnimationFrame(state.rafId);
  }
}

playBtn.addEventListener("click", togglePlay);
