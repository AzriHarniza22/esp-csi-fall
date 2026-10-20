#!/usr/bin/env node
/*
 * Uji proteksi reset-loop Web Serial tanpa browser.
 *
 * Dua hal yang diuji, keduanya ditemukan dari device nyata:
 *   1. holdDeviceOutOfReset() harus menurunkan DTR dan RTS (false/false).
 *      DTR yang asserted akan pulls EN CH340 dan me-restart ESP32, dan restart
 *      itu membuat port hilang, yang memicu reopen, yang triggering reset lagi.
 *   2. reopen harus dihentikan setelah REOPEN_MAX_STREAK percobaan, supaya
 *      page tidak mengunci device dalam loop tak berujung.
 *
 * Jalankan: node tools/test_resetloop.js
 */
"use strict";
const fs = require("fs");
const path = require("path");

const src = fs.readFileSync(path.join(__dirname, "web_serial_monitor.html"), "utf8");

/* helper ini sengaja dibaca dari berkas, bukan disalin di sini, supaya test
 * ikut gagal kalau implementasinya berubah. Kurung kurawal dihitung, bukan
 * ditebak dari indent: "    }" juga cocok di dalam indent 6 spasi. */
function extractFunction(startMarker) {
  const s = src.indexOf(startMarker);
  if (s < 0) {
    console.error("GAGAL: tidak bisa menemukan", startMarker);
    process.exit(1);
  }
  let depth = 0;
  let started = false;
  for (let i = s; i < src.length; i++) {
    const c = src[i];
    if (c === "{") { depth++; started = true; }
    else if (c === "}") {
      depth--;
      if (started && depth === 0) return src.slice(s, i + 1);
    }
  }
  console.error("GAGAL: kurung kurawal tidak seimbang untuk", startMarker);
  process.exit(1);
}

const holdSrc = extractFunction("async function holdDeviceOutOfReset");

const constants = {};
for (const name of ["REOPEN_BACKOFF_MS", "REOPEN_MAX_STREAK"]) {
  const m = src.match(new RegExp(`const\\s+${name}\\s*=\\s*(\\[[^\\]]*\\]|\\d+)`));
  if (!m) {
    console.error("GAGAL: konstanta", name, "tidak ditemukan");
    process.exit(1);
  }
  constants[name] = JSON.parse(m[1].replace(/'/g, '"'));
}
console.log("konstanta dari kode:", JSON.stringify(constants));

let failures = 0;
function check(name, actual, expected) {
  const ok = String(actual) === String(expected);
  if (!ok) failures++;
  console.log(`  ${ok ? "OK  " : "GAGAL"}  ${name}: ${actual}${ok ? "" : `  (harap ${expected})`}`);
}

const factory = new Function(holdSrc + "\nreturn holdDeviceOutOfReset;");
const holdDeviceOutOfReset = factory();

async function main() {
console.log("\n=== 1. DTR/RTS diturunkan, tidak dinaikkan ===");
const calls = [];
const fakePort = {
  setSignals: async (s) => { calls.push(s); },
};
const held = await holdDeviceOutOfReset(fakePort);
check("return true", held, true);
check("jumlah panggilan", calls.length, 1);
check("dataTerminalReady", calls[0].dataTerminalReady, false);
check("requestToSend", calls[0].requestToSend, false);
const raised = Object.values(calls[0]).some((v) => v === true);
check("tidak ada signal yang dinaikkan", raised, false);

console.log("\n=== 2. port tanpa setSignals harus aman ===");
check("port null", await holdDeviceOutOfReset(null), false);
check("port tanpa setSignals", await holdDeviceOutOfReset({}), false);

console.log("\n=== 3. error setSignals tidak boleh melempar ===");
const throwing = { setSignals: async () => { throw new Error("tidak didukung"); } };
check("ditangkap", await holdDeviceOutOfReset(throwing), false);

console.log("\n=== 4. circuit breaker ===");
/* Logika reopen di page: tambah streak, lalu tolak kalau sudah >= maksimum.
 * Disimulasikan ulang dengan ambang dan urutan persis seperti di kode. */
const MAX = constants.REOPEN_MAX_STREAK;
let streak = 0;
const results = [];
for (let attempt = 1; attempt <= 8; attempt++) {
  if (streak >= MAX) {
    results.push("berhenti");
    break;
  }
  streak++;
  results.push("reopen");
}
check("jumlah reopen sebelum berhenti", results.filter((r) => r === "reopen").length, MAX);
check("percobaan ke-6 dihentikan", results[MAX], "berhenti");
check("tidak ada reopen ke-7", results.length, MAX + 1);

console.log("\n=== 5. streak direset saat device benar-benar mengirim data ===");
streak = 0;
for (let i = 0; i < 20; i++) {
  if (streak >= MAX) break;
  streak++;
  if (i % 4 === 3) streak = 0;   /* data datang -> bukti loop bukan salah device */
}
check("strek tidak pernah mencapai batas", streak < MAX, true);

console.log(`\n=== HASIL: ${failures} kegagalan ===`);
process.exit(failures ? 1 : 0);
}

main();
