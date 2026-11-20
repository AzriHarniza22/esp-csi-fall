/*
 * Host-side protocol helpers for the bounded diagnostic exporter.
 *
 * Wire format: one JSON object per HMS: line. The payload is Base64 encoded
 * and CRC32 is the standard reflected IEEE 802.3 polynomial (0xedb88320),
 * represented as eight uppercase hexadecimal digits.
 */
"use strict";

const PROTOCOL_VERSION = 1;
const MAX_PAYLOAD_BYTES = 1536;
const DIAG_WIRE_MAGIC = 0x33574d48;
const DIAG_WIRE_VERSION = 1;
const DIAG_WIRE_RECORD = 1;
const DIAG_WIRE_CHECKPOINT = 2;

function crc32(input) {
  const bytes = Buffer.isBuffer(input) ? input : Buffer.from(input);
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function crcHex(input) {
  return crc32(input).toString(16).padStart(8, "0").toUpperCase();
}

function decodeDiagnosticWireAt(bytes, start) {
  if (start + 12 > bytes.length || bytes.readUInt32LE(start) !== DIAG_WIRE_MAGIC ||
      bytes.readUInt16LE(start + 4) !== DIAG_WIRE_VERSION) {
    throw new Error("invalid diagnostic wire header");
  }
  const type = bytes[start + 6];
  const payloadLength = bytes.readUInt32LE(start + 8);
  const end = start + 12 + payloadLength;
  if (end > bytes.length) throw new Error("wire length mismatch");
  const view = new DataView(bytes.buffer, bytes.byteOffset + start + 12, payloadLength);
  let offset = 0;
  const u8 = () => view.getUint8(offset++);
  const u16 = () => { const v = view.getUint16(offset, true); offset += 2; return v; };
  const u32 = () => { const v = view.getUint32(offset, true); offset += 4; return v; };
  const i32 = () => { const v = view.getInt32(offset, true); offset += 4; return v; };
  const u64 = () => { const v = view.getBigUint64(offset, true); offset += 8; return v; };
  const i64 = () => BigInt.asIntN(64, u64());
  const f32 = () => { const v = view.getFloat32(offset, true); offset += 4; return v; };
  const mac = () => {
    const value = Array.from(bytes.subarray(start + 12 + offset, start + 12 + offset + 6));
    offset += 6;
    return value;
  };
  if (type === DIAG_WIRE_RECORD) {
    const record = {};
    for (const name of ["boot_id", "capture_id", "record_seq", "frame_seq",
      "feature_seq", "fsm_seq", "rx_timestamp_ms"]) record[name] = u32();
    for (const name of ["radar_timestamp_us", "enqueue_timestamp_us",
      "dequeue_timestamp_us", "process_timestamp_us"]) record[name] = i64();
    record.raw_feature = u32();
    record.waveform_jitter = f32();
    record.feature_status = u8();
    record.stage = u8();
    record.peer_mac = mac();
    for (const name of ["first_frame_seq", "last_frame_seq", "frame_count",
      "first_rx_timestamp_ms", "last_rx_timestamp_ms", "rx_timestamp_span_ms",
      "frame_gap_count"]) record[name] = u32();
    record.window_status = u8();
    record.lifecycle_seq = u32();
    for (const name of ["lifecycle_event", "lifecycle_reason",
      "lifecycle_reset_type", "lifecycle_state_before",
      "lifecycle_state_after"]) record[name] = u8();
    record.lifecycle_pending_count = u32();
    record.lifecycle_timestamp_us = i64();
    record.discard_reason = u8();
    record.batch_id = u32();
    record.batch_index = u16();
    record.batch_size = u16();
    for (const name of ["before_smooth_scaled", "before_baseline_scaled",
      "before_gold_baseline_scaled", "before_noise_scaled"]) record[name] = u32();
    for (const name of ["before_diff_scaled", "before_enter_threshold",
      "before_exit_threshold"]) record[name] = i32();
    record.before_debounce_counter = u32();
    record.before_init_stage = u8();
    record.before_process_state = u8();
    for (const name of ["after_smooth_scaled", "after_baseline_scaled",
      "after_gold_baseline_scaled", "after_noise_scaled"]) record[name] = u32();
    for (const name of ["after_diff_scaled", "after_enter_threshold",
      "after_exit_threshold"]) record[name] = i32();
    record.after_debounce_counter = u32();
    record.after_init_stage = u8();
    record.after_process_state = u8();
    record.transition_reason = u8();
    if (offset !== payloadLength) throw new Error("record field length mismatch");
    return { message: { type: "record", schema: DIAG_WIRE_VERSION, record }, end };
  }
  if (type === DIAG_WIRE_CHECKPOINT) {
    const checkpoint = {
      checkpoint_version: u32(), boot_id: u32(), capture_id: u32(),
      lifecycle_seq: u32(), batch_seq: u32(), channel_count: u32(),
      required_size: u32(), timestamp_us: i64(), channels: [],
    };
    for (let channelIndex = 0; channelIndex < checkpoint.channel_count; channelIndex += 1) {
      const channel = { peer_mac: mac() };
      channel.process_state = u8();
      channel.init_stage = u8();
      for (const name of ["raw_feature", "smooth_scaled", "baseline_scaled",
        "gold_baseline_scaled", "noise_level_scaled", "init_counter"]) channel[name] = u32();
      channel.init_avg_sum = u64();
      channel.init_avg_count = u32();
      channel.init_avg_start_us = i64();
      for (const name of ["debounce_counter", "reset_counter", "gold_stable_counter"]) channel[name] = u32();
      channel.last_diff = i32();
      for (const name of ["jitter_value", "wander_value", "train_wander_thr",
        "train_jitter_thr"]) channel[name] = f32();
      channel.train_thresholds_valid = u8();
      /* Wire order comes from diag_wire_checkpoint() in
       * main/web_serial_monitor.c, which differs from the struct order: the
       * 25-sample presence history is emitted after user_config, and
       * pending_offset is not transmitted. */
      channel.presence_total_samples = u32();
      channel.presence_write_index = u32();
      channel.presence_wander_average = f32();
      channel.presence_someone_threshold = f32();
      channel.presence_ready = u8();
      channel.presence_someone_status = u8();
      for (const name of ["diff_scaled", "enter_threshold", "exit_threshold"]) channel[name] = i32();
      channel.active_hold_until_us = i64();
      channel.last_event = u8();
      for (const name of ["raw_capacity", "raw_read_index", "raw_write_index",
        "raw_count", "fsm_seq"]) channel[name] = u32();
      channel.transition_reason = u8();
      channel.pending_count = u32();
      channel.user_config = {
        sensitivity: f32(), presence_sensitivity: f32(),
        active_jitter_min: f32(), active_filter_ms: u32(),
      };
      channel.presence_wander_history = Array.from({ length: 25 }, f32);
      channel.runtime_config = Array.from({ length: 16 }, f32);
      channel.runtime_uint_config = Array.from({ length: 6 }, u32);
      channel.pending = [];
      for (let itemIndex = 0; itemIndex < channel.pending_count; itemIndex += 1) {
        const item = {};
        for (const name of ["raw_feature", "feature_seq", "frame_seq",
          "rx_timestamp_ms"]) item[name] = u32();
        for (const name of ["radar_timestamp_us", "enqueue_timestamp_us"]) item[name] = i64();
        item.lifecycle_seq = u32();
        item.fsm_seq = u32();
        item.feature_status = u8();
        item.waveform_jitter = f32();
        for (const name of ["first_frame_seq", "last_frame_seq", "frame_count",
          "first_rx_timestamp_ms", "last_rx_timestamp_ms", "rx_timestamp_span_ms",
          "frame_gap_count"]) item[name] = u32();
        item.window_status = u8();
        channel.pending.push(item);
      }
      checkpoint.channels.push(channel);
    }
    if (offset !== payloadLength) throw new Error("checkpoint field length mismatch");
    return { message: { type: "checkpoint", schema: DIAG_WIRE_VERSION, checkpoint }, end };
  }
  throw new Error("unknown diagnostic wire type");
}

function decodeDiagnosticWireMessages(input) {
  const bytes = Buffer.isBuffer(input) ? input : Buffer.from(input);
  const messages = [];
  let offset = 0;
  while (offset < bytes.length) {
    const decoded = decodeDiagnosticWireAt(bytes, offset);
    messages.push(decoded.message);
    offset = decoded.end;
  }
  if (messages.length === 0) throw new Error("invalid diagnostic wire header");
  return messages;
}

function decodeDiagnosticWire(input) {
  const messages = decodeDiagnosticWireMessages(input);
  if (messages.length !== 1) throw new Error("wire length mismatch");
  return messages[0];
}

function encodeChunk({ bootId, captureId, chunkSeq, chunkType, payload,
  firstRecordSeq = null, lastRecordSeq = null, recordCount = null }) {
  const bytes = Buffer.isBuffer(payload) ? payload : Buffer.from(payload);
  if (bytes.length > MAX_PAYLOAD_BYTES) {
    throw new RangeError("diagnostic chunk payload exceeds bounded size");
  }
  if (!Number.isInteger(bootId) || !Number.isInteger(captureId) ||
      !Number.isInteger(chunkSeq) || typeof chunkType !== "string") {
    throw new TypeError("invalid diagnostic chunk identity");
  }
  const count = Number.isInteger(recordCount)
    ? (recordCount >>> 0)
    : (firstRecordSeq === null ? 0 : 1);
  return {
    type: "diag_chunk",
    protocol_version: PROTOCOL_VERSION,
    boot_id: bootId >>> 0,
    capture_id: captureId >>> 0,
    chunk_seq: chunkSeq >>> 0,
    chunk_type: chunkType,
    record_count: count,
    payload_length: bytes.length,
    first_record_seq: firstRecordSeq,
    last_record_seq: lastRecordSeq,
    crc32: crcHex(bytes),
    payload: bytes.toString("base64"),
  };
}

function validateChunk(chunk) {
  if (!chunk || chunk.type !== "diag_chunk" ||
      chunk.protocol_version !== PROTOCOL_VERSION ||
      !Number.isInteger(chunk.boot_id) ||
      !Number.isInteger(chunk.capture_id) ||
      !Number.isInteger(chunk.chunk_seq) ||
      typeof chunk.chunk_type !== "string" ||
      typeof chunk.payload !== "string" ||
      !Number.isInteger(chunk.payload_length) ||
      !/^[0-9A-Fa-f]{8}$/.test(String(chunk.crc32))) {
    return { ok: false, reason: "invalid_header" };
  }
  if (chunk.payload_length < 0 || chunk.payload_length > MAX_PAYLOAD_BYTES ||
      chunk.chunk_type.length === 0 || chunk.chunk_type.length > 32 ||
      chunk.chunk_seq < 0 || chunk.boot_id < 0 || chunk.capture_id < 0) {
    return { ok: false, reason: "invalid_header" };
  }
  let payload;
  try {
    if (!/^[A-Za-z0-9+/]*={0,2}$/.test(chunk.payload) ||
        chunk.payload.length % 4 !== 0) {
      return { ok: false, reason: "invalid_base64" };
    }
    payload = Buffer.from(chunk.payload, "base64");
  } catch (_error) {
    return { ok: false, reason: "invalid_base64" };
  }
  if (payload.length !== chunk.payload_length || payload.length > MAX_PAYLOAD_BYTES) {
    return { ok: false, reason: "invalid_length" };
  }
  if (crcHex(payload) !== String(chunk.crc32).toUpperCase()) {
    return { ok: false, reason: "crc_mismatch" };
  }
  if (chunk.first_record_seq !== null &&
      (!Number.isInteger(chunk.first_record_seq) || chunk.first_record_seq < 0) ||
      chunk.last_record_seq !== null &&
      (!Number.isInteger(chunk.last_record_seq) || chunk.last_record_seq < 0)) {
    return { ok: false, reason: "invalid_record_range" };
  }
  if (chunk.first_record_seq !== null && chunk.last_record_seq !== null &&
      chunk.first_record_seq > chunk.last_record_seq) {
    return { ok: false, reason: "invalid_record_range" };
  }
  return { ok: true, payload };
}

class ChunkAssembler {
  constructor(identity) {
    this.identity = identity;
    this.chunks = new Map();
    this.duplicates = 0;
    this.rejected = 0;
  }

  accept(chunk) {
    const checked = validateChunk(chunk);
    if (!checked.ok) {
      this.rejected += 1;
      return { accepted: false, reason: checked.reason };
    }
    if (chunk.boot_id !== this.identity.bootId ||
        chunk.capture_id !== this.identity.captureId) {
      this.rejected += 1;
      return { accepted: false, reason: "identity_mismatch" };
    }
    const previous = this.chunks.get(chunk.chunk_seq);
    if (previous) {
      if (previous.header.crc32 === chunk.crc32 &&
          previous.header.payload === chunk.payload) {
        this.duplicates += 1;
        return { accepted: false, duplicate: true, reason: "duplicate" };
      }
      this.rejected += 1;
      return { accepted: false, reason: "chunk_conflict" };
    }
    this.chunks.set(chunk.chunk_seq, {
      header: chunk,
      payload: checked.payload,
    });
    return { accepted: true, duplicate: false };
  }

  missingThrough(lastChunkSeq) {
    const missing = [];
    for (let seq = 0; seq <= lastChunkSeq; seq += 1) {
      if (!this.chunks.has(seq)) missing.push(seq);
    }
    return missing;
  }

  orderedPayload() {
    return Array.from(this.chunks.keys()).sort((a, b) => a - b)
      .map((seq) => this.chunks.get(seq).payload);
  }
}

module.exports = {
  PROTOCOL_VERSION,
  MAX_PAYLOAD_BYTES,
  crc32,
  crcHex,
  decodeDiagnosticWire,
  decodeDiagnosticWireMessages,
  encodeChunk,
  validateChunk,
  ChunkAssembler,
};
