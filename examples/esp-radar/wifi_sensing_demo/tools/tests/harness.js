#!/usr/bin/env node
/*
 * Kerangka bersama untuk harness web_serial_monitor.html.
 *
 * Mengekstrak satu blok JS dari HTML dan menjalankannya di Node dengan stub
 * DOM, sehingga logika rekam bisa diuji tanpa browser.
 *
 * Penting: file ini membaca HTML repo secara langsung. Versi sebelumnya
 * membaca salinan di __dirname, yang membuat harness bisa menguji kode basi
 * tanpa memberi tanda apa pun.
 */
const fs = require("fs");
const path = require("path");

const REPO = path.join(__dirname, "..", "web_serial_monitor.html");
const HTML_PATH = process.env.WSM_HTML || REPO;

function extractBlock(src, startNeedle, endNeedle) {
  const start = src.indexOf(startNeedle);
  if (start < 0) {
    throw new Error(`GAGAL: tidak menemukan ${JSON.stringify(startNeedle)}`);
  }
  const end = src.indexOf(endNeedle, start);
  if (end < 0) {
    throw new Error(`GAGAL: tidak menemukan ${JSON.stringify(endNeedle)}`);
  }
  /* Majukan sampai kurung penutup fungsi endNeedle. */
  const endFull = src.indexOf("\n    }\n", end) + 7;
  if (endFull <= 0) {
    throw new Error(`GAGAL: blok tidak tertutup untuk ${JSON.stringify(endNeedle)}`);
  }
  return src.slice(start, endFull);
}

/* Jam palsu supaya simulasi bisaunjur majuWITHOUT menunggu waktu nyata. */
function makeClock(startIso) {
  let clock = Date.parse(startIso);
  const RealDate = Date;
  const FakeDate = function (...a) {
    return a.length ? new RealDate(...a) : new RealDate(clock);
  };
  FakeDate.now = () => clock;
  FakeDate.parse = RealDate.parse;
  FakeDate.UTC = RealDate.UTC;
  FakeDate.prototype = RealDate.prototype;
  return { FakeDate, advance: (ms) => { clock += ms; }, now: () => clock };
}

function makeEl(extra) {
  return Object.assign(
    { textContent: "", className: "", value: "30", disabled: false, focus() {} },
    extra || {}
  );
}

/* Stub DOM yang cukup untuk blok rekam. */
function makeDom(elements) {
  const created = [];
  return {
    created,
    getElementById: (id) => (id in elements ? elements[id] : null),
    createElement: () => {
      const el = { click() {}, style: {}, setAttribute() {}, appendChild() {} };
      created.push(el);
      return el;
    },
    body: { appendChild() {}, removeChild() {} },
    addEventListener() {},
  };
}

/* Ambil string i18n asli dari HTML supaya pengujian memakai teks yang tampil. */
function makeTranslator(src) {
  return (key) => {
    const m = src.match(new RegExp(`^\\s*${key}:\\s*"([^"]*)"`, "m"));
    return m ? m[1] : key;
  };
}

function report(title, ok, detail) {
  const tag = ok ? "PASS" : "GAGAL";
  console.log(`  [${tag}] ${title}${detail !== undefined ? ` -> ${detail}` : ""}`);
  if (!ok) process.exitCode = 1;
  return ok;
}

module.exports = {
  HTML_PATH,
  extractBlock,
  makeClock,
  makeEl,
  makeDom,
  makeTranslator,
  report,
};