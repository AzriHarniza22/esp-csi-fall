#!/usr/bin/env node
/*
 * Uji logika rekam tanpa browser: ekstrak blok rekam dari web_serial_monitor.html
 * lalu jalankan dengan data sintetis.
 *
 * Berkas ini sengaja diletakkan di dalam repo, bukan /tmp, karenaVersi
 * sebelumnya hilang bersama isi /tmp dan kita sempat menjalankan harness
 * terhadap salinan HTML yang sudah basi tanpa disadari.
 *
 * Jalankan: node tools/test_recording.js
 */
"use strict";
const fs = require("fs");
const path = require("path");

const HTML = path.join(__dirname, "web_serial_monitor.html");
const src = fs.readFileSync(HTML, "utf8");

const start = src.indexOf('const REC_PEER = "AP";');
const end = src.indexOf("function recClear()", start);
if (start < 0 || end < 0) {
  console.error("GAGAL: blok rekam tidak ditemukan di", HTML);
  process.exit(1);
}
const endFull = src.indexOf("\n    }\n", end) + 7;
const block = src.slice(start, endFull);

console.log(`blok terekstrak: ${block.length} karakter`);

/* ---- stub lingkungan browser ---- */
const logs = [];
const t = (k) => {
  const m = src.match(new RegExp(`^\\s*${k}:\\s*"([^"]*)"`, "m"));
  return m ? m[1] : k;
};
const logEvent = (m) => logs.push(m);
const peers = new Map([["AP", { latest: { ts_ms: 100000 } }]]);

const document = {
  getElementById: () => null,
  createElement: () => ({ click() {}, style: {} }),
  body: { appendChild() {}, removeChild() {} },
  addEventListener() {},
};
const window = {
  setInterval: () => 1,
  clearInterval() {},
  confirm: () => true,
  AudioContext: function () {},
  webkitAudioContext: function () {},
};
const Blob = function () {};
const URL = { createObjectURL: () => "", revokeObjectURL: () => {} };

/* ---- elemen DOM yang dioper sebagai parameter ke blok rekam ---- */
const mkEl = (extra) =>
  Object.assign({ textContent: "", className: "", value: "30", disabled: false, focus() {} }, extra || {});

const els = {
  recBadge: mkEl(),
  recStateText: mkEl(),
  recCountdownText: mkEl(),
  recProgressText: mkEl(),
  recSegments: mkEl(),
  recStartBtn: mkEl(),
  recStopBtn: mkEl(),
  recMarkerBtn: mkEl(),
  recCsvBtn: mkEl(),
  recJsonBtn: mkEl(),
  recClearBtn: mkEl(),
  recCategoryInput: mkEl({ value: "lie" }),
  recDurationInput: mkEl({ value: "10" }),
  recCountdownInput: mkEl({ value: "3" }),
};

const KEYS = Object.keys(els);

/* ---- jam palsu supaya rekam bisa disimulasikan seiring waktu nyata ---- */
let clock = Date.parse("2026-10-19T00:00:00Z");
const RealDate = Date;
const FakeDate = function (...a) {
  return a.length ? new RealDate(...a) : new RealDate(clock);
};
FakeDate.now = () => clock;
FakeDate.parse = RealDate.parse;
FakeDate.prototype = RealDate.prototype;

/* ---- rakit blok menjadi fungsi yang mengembalikan API-nya ---- */
const EXPORTS = [
  "recording", "recStart", "recStop", "recAddMarker", "recCaptureSample",
  "recBuildCsv", "recBuildJson", "recExportJson", "recClear", "recTick",
  "renderRecording", "recSegmentsHtml", "REC_MAX_SAMPLES", "recSamplesCount",
  "recTotalStored", "recStamp", "recFull", "recLabeledSamples",
];

const factory = new Function(
  "logEvent", "peers", "window", "document", "Blob", "URL", "t", "console", "setTimeout", "Date",
  ...KEYS,
  block + "\nreturn { " + EXPORTS.join(", ") + " };"
);

const api = factory(logEvent, peers, window, document, Blob, URL, t, console, () => 0, FakeDate,
  ...KEYS.map((k) => els[k]));

const R = api.recording;

/* ---- kecilkan cetakan agar kegagalan enak dibaca ---- */
let failures = 0;
function check(name, actual, expected) {
  const ok = String(actual) === String(expected);
  if (!ok) failures++;
  console.log(`  ${ok ? "OK  " : "GAGAL"}  ${name}: ${actual}${ok ? "" : `  (harap ${expected})`}`);
}

console.log("\n=== 1. state awal ===");
console.log("phase:", R.phase, "| max:", api.REC_MAX_SAMPLES);

console.log("\n=== 2. rekam 10 detik pada 17,8 sampel/detik ===");
api.recStart();
check("phase setelah Start", R.phase, "counting");

clock += 3000;                 // countdown 3 detik selesai
api.recTick();
check("phase setelah countdown", R.phase, "recording");

const N = 177;
const PERIOD_MS = 56;          // ~17,8 Hz, sesuai laju device yang terukur
for (let i = 0; i < N; i++) {
  clock += PERIOD_MS;
  if (i === 50 || i === 120) api.recAddMarker();
  api.recCaptureSample({
    peer: "AP",
    ts_ms: 100000 + i * PERIOD_MS,
    wander_value: 0.05 + i / 10000,
    jitter_value: 0.001,
    motion_status: false,
    motion_state: 0,
    state_name: "IDLE",
    init_stage_name: "STABLE",
    presence_ready: true,
    presence_wander_average: 0.06,
    presence_someone_threshold: 0.0001,
    presence_someone_status: true,
    train_wander_threshold: 0.001,
    train_jitter_threshold: 0.05,
    train_thresholds_valid: true,
    train_background_avg: 0.001,
    train_last_basis_wander: 0.0005,
    smooth_scaled: 100,
    enter_level_scaled: 90,
    exit_level_scaled: 80,
  });
}

console.log("\n=== 3. hanya peer AP yang terekam ===");
clock += PERIOD_MS;
api.recCaptureSample({ peer: "MAC_1", ts_ms: 999999, wander_value: 1, jitter_value: 1 });
check("total tersimpan setelah sampel non-AP", api.recTotalStored(), N);

console.log("\n=== 4. marker ===");
check("jumlah event marker", R.markers.length, 2);

console.log("\n=== 5. auto-stop ===");
clock += 5000;
api.recTick();
check("phase setelah auto-stop", R.phase, "idle");
check("segmen complete", R.segments[0].incomplete, false);
check("Export CSV aktif setelah stop", els.recCsvBtn.disabled, false);
check("Export JSON aktif setelah stop", els.recJsonBtn.disabled, false);

/* Marker berlaku mulai waktunya, jadi jumlah sampel bertanda bisa dihitung
 * langsung dari data - bukan dari hasil ekspor yang sedang diuji. */
const seg = R.segments[0];
const firstMarkMs = seg.markers[0].elapsed_ms;
const expectMarked = seg.samples.filter((s) => s.elapsed_ms >= firstMarkMs).length;
console.log(`  (marker #1 pada ${firstMarkMs} ms -> ${expectMarked} sampel seharusnya bertanda)`);

console.log("\n=== 6. CSV ===");
/* Parser RFC-4180 sungguhan. Memecah baris dengan split(",") justru
 * mengulang bug yang diuji: kategori bebas bisa mengandung koma. */
function parseCsvLine(line) {
  const out = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inQuotes) {
      if (c === '"') {
        if (line[i + 1] === '"') { cur += '"'; i++; } else { inQuotes = false; }
      } else { cur += c; }
    } else if (c === '"') { inQuotes = true; }
    else if (c === ',') { out.push(cur); cur = ""; }
    else { cur += c; }
  }
  out.push(cur);
  return out;
}

const csv = api.recBuildCsv();
const clines = csv.trim().split("\n");
const hdrIdx = clines.findIndex((l) => !l.startsWith("#"));
const cols = clines[hdrIdx].split(",");
const rows = clines.slice(hdrIdx + 1).map(parseCsvLine);
check("baris data", rows.length, N);
check("semua baris punya jumlah kolom sama",
      rows.filter((r) => r.length !== cols.length).length, 0);

console.log("\n=== 7. JSON lewat jalur produksi ===");
const back = JSON.parse(JSON.stringify(api.recBuildJson()));
check("jumlah sampel", back.samples.length, N);
const missing = back.samples.filter(
  (x) => x.segment === undefined || x.category === undefined || x.marker_id === undefined
);
check("sampel tanpa label segment/category/marker_id", missing.length, 0);
check("sampel bertanda di JSON", back.samples.filter((x) => x.marker_id !== "").length, expectMarked);
check("kategori tiap sampel", JSON.stringify([...new Set(back.samples.map((x) => x.category))]),
      JSON.stringify([R.segments[0].category]));

console.log("\n=== 8. CSV dan JSON harus menghitung marker dengan aturan sama ===");
const markedCsv = rows.filter((r) => r[2] !== "").length;
check("jumlah marker CSV = JSON", markedCsv,
      back.samples.filter((x) => x.marker_id !== "").length);

console.log("\n=== 9. escaping CSV untuk kategori bebas ===");
R.segments[0].category = 'uji, "koma" & quote';
const escRows = api.recBuildCsv().trim().split("\n")
  .filter((l) => !l.startsWith("#") && !l.startsWith("segment,"))
  .map(parseCsvLine);
check("kategori utuh setelah di-parse ulang", escRows[0][1], 'uji, "koma" & quote');
check("jumlah kolom tidak berubah", escRows[0].length, cols.length);
check("bentuk mentah ter-escape", api.recBuildCsv().includes('"uji, ""koma"" & quote"'), true);
R.segments[0].category = "lie";

console.log("\n=== 10. guard buffer penuh ===");
check("recFull() saat kosong", api.recFull(), false);

console.log("\n=== 11. clear ===");
api.recClear();
check("sampel setelah clear", api.recTotalStored(), 0);
check("segmen setelah clear", R.segments.length, 0);
check("tombol Export CSV setelah clear", els.recCsvBtn.disabled, true);

console.log("\n=== log yang dihasilkan ===");
logs.forEach((l) => console.log("   ", l));

console.log(`\n=== HASIL: ${failures} kegagalan ===`);
process.exit(failures ? 1 : 0);
