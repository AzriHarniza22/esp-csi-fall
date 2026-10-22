/*
 * Shared CSI dataset helpers for the web monitor and Node tests.
 * Browser: global CsiRecorder. Node: module.exports.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.CsiRecorder = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const PRESET_LABELS = ["kosong", "duduk", "berdiri", "jongkok", "jatuh", "berjalan"];

  const CSI_DATA_HEADER =
    "type,sequence,timestamp,taget_seq,target,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,not_sounding,aggregation,stbc,fec_coding,sgi,noise_floor,ampdu_cnt,channel,secondary_channel,local_timestamp,ant,sig_len,rx_state,agc_gain,fft_gain,len,first_word,data";

  const INDEX_HEADER =
    "id,label,started_at_utc,duration_s,frames,complete,csi_data,iq,meta";

  function slugLabel(label) {
    const slug = String(label || "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "_")
      .replace(/_+/g, "_")
      .replace(/^_|_$/g, "");
    return slug.slice(0, 48);
  }

  function resolveLabel(preset, custom) {
    const customText = String(custom || "").trim();
    if (customText) {
      return customText;
    }
    const presetText = String(preset || "").trim();
    if (presetText && presetText !== "__custom__") {
      return presetText;
    }
    return "";
  }

  function isSafeRecordingId(id) {
    return typeof id === "string" && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,120}$/.test(id);
  }

  function csvEscape(value) {
    const text = String(value ?? "");
    if (/[",\n\r]/.test(text)) {
      return `"${text.replace(/"/g, '""')}"`;
    }
    return text;
  }

  function decodePairs(bytes, dataType) {
    const sampleBytes = Number(dataType) === 1 ? 2 : 1;
    const pairs = [];
    if (!bytes || bytes.length < sampleBytes * 2) {
      return pairs;
    }
    const view = bytes.buffer
      ? new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
      : new DataView(Uint8Array.from(bytes).buffer);
    for (let index = 0; index + sampleBytes * 2 <= bytes.length; index += sampleBytes * 2) {
      const real = sampleBytes === 2 ? view.getInt16(index, true) : view.getInt8(index);
      const imag = sampleBytes === 2 ? view.getInt16(index + sampleBytes, true) : view.getInt8(index + 1);
      pairs.push([real, imag]);
    }
    return pairs;
  }

  function bytesToCsvList(bytes) {
    if (!bytes || !bytes.length) {
      return "\"[]\"";
    }
    let inner = String(bytes[0]);
    for (let i = 1; i < bytes.length; i++) {
      inner += `,${bytes[i]}`;
    }
    return `"${inner}"`;
  }

  function framePayloadBytes(frame) {
    if (frame.validBytes && frame.validBytes.length) {
      return { bytes: frame.validBytes, source: "valid_data" };
    }
    return { bytes: frame.rawBytes || [], source: "raw_data" };
  }

  function iqHeader(subcarriers) {
    const cols = ["timestamp_us", "seq", "mac", "rssi", "data_type", "dropped"];
    for (let i = 0; i < subcarriers; i++) {
      const n = String(i).padStart(3, "0");
      cols.push(`sc${n}_i`, `sc${n}_q`);
    }
    return cols.join(",");
  }

  function buildCsiDataCsv(frames, options) {
    const label = (options && options.label) || "unknown";
    const takeSeq = (options && options.takeSeq) || 1;
    const lines = [CSI_DATA_HEADER];
    for (const frame of frames) {
      const payload = framePayloadBytes(frame);
      lines.push([
        "CSI_DATA",
        Number(frame.seq || 0),
        Number(frame.ts_us || frame.local_timestamp || 0),
        takeSeq,
        csvEscape(label),
        frame.mac || "",
        Number(frame.rssi || 0),
        Number(frame.rate || 0),
        Number(frame.sig_mode || 0),
        Number(frame.mcs || 0),
        Number(frame.bandwidth || 0),
        0,
        0,
        0,
        Number(frame.stbc || 0),
        0,
        0,
        Number(frame.noise_floor || 0),
        0,
        Number(frame.channel || 0),
        Number(frame.secondary_channel || 0),
        Number(frame.local_timestamp || 0),
        0,
        0,
        0,
        Number(frame.agc_gain || 0),
        Number(frame.fft_gain || 0),
        payload.bytes.length,
        0,
        bytesToCsvList(payload.bytes),
      ].join(","));
    }
    return lines.join("\n") + "\n";
  }

  function buildIqCsv(frames) {
    let subcarriers = 0;
    const decoded = frames.map((frame) => {
      const payload = framePayloadBytes(frame);
      const pairs = frame.iq && frame.iq.length
        ? frame.iq
        : decodePairs(payload.bytes, frame.data_type);
      if (pairs.length > subcarriers) {
        subcarriers = pairs.length;
      }
      return { frame, pairs };
    });
    const lines = [iqHeader(subcarriers)];
    for (const row of decoded) {
      const cols = [
        Number(row.frame.ts_us || 0),
        Number(row.frame.seq || 0),
        row.frame.mac || "",
        Number(row.frame.rssi || 0),
        Number(row.frame.data_type || 0),
        Number(row.frame.dropped || 0),
      ];
      for (let i = 0; i < subcarriers; i++) {
        const pair = row.pairs[i] || [0, 0];
        cols.push(pair[0], pair[1]);
      }
      lines.push(cols.join(","));
    }
    return lines.join("\n") + "\n";
  }

  function recordingCompleteness({ frames, droppedStart, droppedEnd, disconnected, stimulusOn }) {
    const count = Array.isArray(frames) ? frames.length : Number(frames || 0);
    const droppedDelta = Math.max(0, Number(droppedEnd || 0) - Number(droppedStart || 0));
    const complete = count > 0 && !disconnected && droppedDelta === 0 && stimulusOn !== false;
    return { complete, frames: count, dropped_delta: droppedDelta };
  }

  function utcStamp(date) {
    const d = date instanceof Date ? date : new Date(date);
    return d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
  }

  function makeRecordingId(label, date, seq) {
    const slug = slugLabel(label) || "unlabeled";
    const nnn = String(seq || 1).padStart(3, "0");
    return `${utcStamp(date)}_${slug}_${nnn}`;
  }

  function parseIqCsv(text) {
    const lines = String(text || "").split(/\r?\n/).filter((line) => line && !line.startsWith("#"));
    if (lines.length < 2) {
      return { frames: [], subcarriers: 0 };
    }
    const header = lines[0].split(",");
    const firstIq = header.findIndex((name) => name.startsWith("sc") && name.endsWith("_i"));
    const subcarriers = firstIq >= 0 ? Math.floor((header.length - firstIq) / 2) : 0;
    const frames = [];
    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split(",");
      const iq = [];
      for (let sc = 0; sc < subcarriers; sc++) {
        const base = firstIq + sc * 2;
        iq.push([Number(cols[base]), Number(cols[base + 1])]);
      }
      frames.push({
        ts_us: Number(cols[0]),
        seq: Number(cols[1]),
        mac: cols[2],
        rssi: Number(cols[3]),
        iq,
      });
    }
    return { frames, subcarriers };
  }

  function downsampleHeatmap(iqFrames, maxCols) {
    const limit = Math.max(1, maxCols || 400);
    if (!iqFrames.length) {
      return [];
    }
    const step = Math.max(1, Math.ceil(iqFrames.length / limit));
    const out = [];
    for (let i = 0; i < iqFrames.length; i += step) {
      const frame = iqFrames[i];
      out.push((frame.iq || []).map((pair) => Math.hypot(pair[0] || 0, pair[1] || 0)));
    }
    return out;
  }

  function buildMeta(fields) {
    return Object.assign({
      format: "wifi_sensing_demo_csi_v1",
      data_source: "valid_data_preferred_else_raw_data",
    }, fields);
  }

  return {
    PRESET_LABELS,
    CSI_DATA_HEADER,
    INDEX_HEADER,
    slugLabel,
    resolveLabel,
    isSafeRecordingId,
    csvEscape,
    decodePairs,
    buildCsiDataCsv,
    buildIqCsv,
    recordingCompleteness,
    utcStamp,
    makeRecordingId,
    parseIqCsv,
    downsampleHeatmap,
    buildMeta,
    framePayloadBytes,
  };
});
