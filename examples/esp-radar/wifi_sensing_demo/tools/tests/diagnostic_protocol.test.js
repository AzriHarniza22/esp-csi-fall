#!/usr/bin/env node
"use strict";

const assert = require("assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const {
  crcHex, encodeChunk, validateChunk, decodeDiagnosticWire, decodeDiagnosticWireMessages, ChunkAssembler,
} = require("../diagnostic_protocol.js");
const { createRecorder } = require("../diagnostic_recorder.js");

function makeRecordWire(bootId, captureId, recordSeq, payloadLen = 204) {
  const wire = Buffer.alloc(12 + payloadLen);
  wire.writeUInt32LE(0x33574d48, 0);
  wire.writeUInt16LE(1, 4);
  wire[6] = 1;
  wire.writeUInt32LE(payloadLen, 8);
  wire.writeUInt32LE(bootId, 12);
  wire.writeUInt32LE(captureId, 16);
  wire.writeUInt32LE(recordSeq, 20);
  return wire;
}

assert.strictEqual(crcHex(Buffer.from("123456789")), "CBF43926");
const chunk = encodeChunk({
  bootId: 7, captureId: 3, chunkSeq: 0, chunkType: "CHECKPOINT",
  payload: Buffer.from("checkpoint"),
});
assert.strictEqual(validateChunk(chunk).ok, true);
const corrupt = { ...chunk, crc32: "00000000" };
assert.strictEqual(validateChunk(corrupt).reason, "crc_mismatch");

const wirePayload = Buffer.alloc(12 + 204);
wirePayload.writeUInt32LE(0x33574d48, 0);
wirePayload.writeUInt16LE(1, 4);
wirePayload[6] = 1;
wirePayload.writeUInt32LE(204, 8);
wirePayload.writeUInt32LE(42, 12);
wirePayload.writeUInt32LE(9, 16);
wirePayload.writeUInt32LE(3, 20);
wirePayload.writeUInt32LE(4, 24);
wirePayload.writeUInt32LE(5, 28);
assert.deepStrictEqual(decodeDiagnosticWire(wirePayload), {
  type: "record",
  schema: 1,
  record: {
    boot_id: 42, capture_id: 9, record_seq: 3, frame_seq: 4, feature_seq: 5,
    fsm_seq: 0, rx_timestamp_ms: 0, radar_timestamp_us: 0n,
    enqueue_timestamp_us: 0n, dequeue_timestamp_us: 0n, process_timestamp_us: 0n,
    raw_feature: 0, waveform_jitter: 0, feature_status: 0, stage: 0,
    peer_mac: [0, 0, 0, 0, 0, 0], first_frame_seq: 0, last_frame_seq: 0,
    frame_count: 0, first_rx_timestamp_ms: 0, last_rx_timestamp_ms: 0,
    rx_timestamp_span_ms: 0, frame_gap_count: 0, window_status: 0,
    lifecycle_seq: 0, lifecycle_event: 0, lifecycle_reason: 0,
    lifecycle_reset_type: 0, lifecycle_state_before: 0,
    lifecycle_state_after: 0, lifecycle_pending_count: 0,
    lifecycle_timestamp_us: 0n, discard_reason: 0, batch_id: 0, batch_index: 0,
    batch_size: 0, before_smooth_scaled: 0, before_baseline_scaled: 0,
    before_gold_baseline_scaled: 0, before_noise_scaled: 0, before_diff_scaled: 0,
    before_enter_threshold: 0, before_exit_threshold: 0,
    before_debounce_counter: 0, before_init_stage: 0, before_process_state: 0,
    after_smooth_scaled: 0, after_baseline_scaled: 0,
    after_gold_baseline_scaled: 0, after_noise_scaled: 0, after_diff_scaled: 0,
    after_enter_threshold: 0, after_exit_threshold: 0,
    after_debounce_counter: 0, after_init_stage: 0, after_process_state: 0,
    transition_reason: 0,
  },
});
const checkpointWire = Buffer.alloc(12 + 36);
checkpointWire.writeUInt32LE(0x33574d48, 0);
checkpointWire.writeUInt16LE(1, 4);
checkpointWire[6] = 2;
checkpointWire.writeUInt32LE(36, 8);
checkpointWire.writeUInt32LE(1, 12);
checkpointWire.writeUInt32LE(42, 16);
checkpointWire.writeUInt32LE(9, 20);
checkpointWire.writeUInt32LE(7, 24);
checkpointWire.writeUInt32LE(8, 28);
checkpointWire.writeUInt32LE(0, 32);
checkpointWire.writeUInt32LE(36, 36);
assert.strictEqual(decodeDiagnosticWire(checkpointWire).checkpoint.boot_id, 42);

const assembler = new ChunkAssembler({ bootId: 7, captureId: 3 });
assert.strictEqual(assembler.accept(chunk).accepted, true);
assert.strictEqual(assembler.accept(chunk).duplicate, true);
assert.strictEqual(assembler.accept({ ...chunk, capture_id: 4 }).reason, "identity_mismatch");
assert.deepStrictEqual(assembler.missingThrough(2), [1, 2]);

const dir = fs.mkdtempSync(path.join(os.tmpdir(), "diag-recorder-"));
const recordWire = Buffer.alloc(216);
recordWire.writeUInt32LE(0x33574d48, 0);
recordWire.writeUInt16LE(1, 4);
recordWire[6] = 1;
recordWire.writeUInt32LE(204, 8);
recordWire.writeUInt32LE(42, 12);
recordWire.writeUInt32LE(9, 16);
recordWire.writeUInt32LE(3, 20);
recordWire.writeUInt32LE(4, 24);
recordWire.writeUInt32LE(5, 28);
const recordChunk = encodeChunk({
  bootId: 7, captureId: 3, chunkSeq: 0, chunkType: "DIAGNOSTIC_RECORDS",
  payload: recordWire,
});
const recorder = createRecorder(dir, { bootId: 7, captureId: 3 });
assert.strictEqual(recorder.accept(recordChunk).accepted, true);
const manifest = encodeChunk({
  bootId: 7, captureId: 3, chunkSeq: 1, chunkType: "CAPTURE_MANIFEST",
  payload: Buffer.from(JSON.stringify({
    protocol_version: 1, boot_id: 7, capture_id: 3,
    record_count: 1, overflow_count: 0,
  })),
});
assert.strictEqual(recorder.accept(manifest).accepted, true);
const report = recorder.finalize(1);
assert.strictEqual(report.export_status, "complete");
assert.deepStrictEqual(
  fs.readFileSync(path.join(dir, "capture.diag")),
  recordWire,
);

fs.rmSync(dir, { recursive: true, force: true });

// 11. 1 record in 1 chunk (explicit batch metadata)
const oneWire = makeRecordWire(7, 3, 0);
const oneChunk = encodeChunk({
  bootId: 7, captureId: 3, chunkSeq: 10, chunkType: "DIAGNOSTIC_RECORDS",
  payload: oneWire, firstRecordSeq: 0, lastRecordSeq: 0, recordCount: 1,
});
assert.strictEqual(oneChunk.record_count, 1);
assert.strictEqual(validateChunk(oneChunk).ok, true);
const oneDecoded = decodeDiagnosticWireMessages(Buffer.from(oneChunk.payload, "base64"));
assert.strictEqual(oneDecoded.length, 1);
assert.strictEqual(oneDecoded[0].record.record_seq, 0);

// 12. 4 records in 1 chunk
const batch4 = Buffer.concat([0,1,2,3].map((seq) => makeRecordWire(7, 3, seq)));
const chunk4 = encodeChunk({
  bootId: 7, captureId: 3, chunkSeq: 11, chunkType: "DIAGNOSTIC_RECORDS",
  payload: batch4, firstRecordSeq: 0, lastRecordSeq: 3, recordCount: 4,
});
assert.strictEqual(chunk4.record_count, 4);
assert.strictEqual(validateChunk(chunk4).ok, true);
const decoded4 = decodeDiagnosticWireMessages(Buffer.from(chunk4.payload, "base64"));
assert.strictEqual(decoded4.length, 4);
assert.deepStrictEqual(decoded4.map((m) => m.record.record_seq), [0,1,2,3]);

// 13. variable-count batch within payload limit (2 and 3 records)
for (const count of [2, 3]) {
  const seqs = Array.from({length: count}, (_, i) => i + 10);
  const payload = Buffer.concat(seqs.map((seq) => makeRecordWire(7, 3, seq)));
  assert.ok(payload.length <= 1536);
  const c = encodeChunk({
    bootId: 7, captureId: 3, chunkSeq: 20 + count, chunkType: "DIAGNOSTIC_RECORDS",
    payload, firstRecordSeq: seqs[0], lastRecordSeq: seqs[seqs.length - 1], recordCount: count,
  });
  assert.strictEqual(c.record_count, count);
  assert.strictEqual(validateChunk(c).ok, true);
  const d = decodeDiagnosticWireMessages(Buffer.from(c.payload, "base64"));
  assert.deepStrictEqual(d.map((m) => m.record.record_seq), seqs);
}

// 14. payload > 1536 bytes must be safely rejected by encoder/bounded contract
assert.throws(() => encodeChunk({
  bootId: 7, captureId: 3, chunkSeq: 30, chunkType: "DIAGNOSTIC_RECORDS",
  payload: Buffer.alloc(1537), firstRecordSeq: 0, lastRecordSeq: 0, recordCount: 1,
}), /bounded size/);

// 15. wrong CRC on batched chunk
const badCrcBatch = { ...chunk4, crc32: "00000000" };
assert.strictEqual(validateChunk(badCrcBatch).reason, "crc_mismatch");

// 16. truncated/invalid framing (truncated payload and invalid wire framing)
const truncatedBatch = { ...chunk4, payload_length: chunk4.payload_length - 1 };
assert.strictEqual(validateChunk(truncatedBatch).reason, "invalid_length");
const badWire = Buffer.from(batch4);
badWire.writeUInt32LE(0x12345678, 0); // corrupt first record magic
assert.throws(() => decodeDiagnosticWireMessages(badWire), /invalid diagnostic wire header/);
const truncatedWire = batch4.subarray(0, batch4.length - 4);
assert.throws(() => decodeDiagnosticWireMessages(truncatedWire), /wire length mismatch/);

// 17. duplicate batch and duplicate ACK semantics (idempotent duplicate, conflict rejected)
const batchAsm = new ChunkAssembler({ bootId: 7, captureId: 3 });
assert.strictEqual(batchAsm.accept(chunk4).accepted, true);
const dup = batchAsm.accept(chunk4);
assert.strictEqual(dup.duplicate, true);
assert.strictEqual(batchAsm.duplicates, 1);
const conflict = batchAsm.accept({ ...chunk4, crc32: crcHex(makeRecordWire(7,3,99)) , payload: makeRecordWire(7,3,99).toString("base64"), payload_length: 216, first_record_seq: 99, last_record_seq: 99, record_count: 1 });
assert.strictEqual(conflict.accepted, false);
assert.strictEqual(conflict.reason, "chunk_conflict");

// 18. retry must resend identical batch payload/CRC/identity/chunk_seq
const retryChunk = encodeChunk({
  bootId: 7, captureId: 3, chunkSeq: 11, chunkType: "DIAGNOSTIC_RECORDS",
  payload: batch4, firstRecordSeq: 0, lastRecordSeq: 3, recordCount: 4,
});
assert.deepStrictEqual(retryChunk, chunk4);
const retryAsm = new ChunkAssembler({ bootId: 7, captureId: 3 });
assert.strictEqual(retryAsm.accept(chunk4).accepted, true);
assert.strictEqual(retryAsm.accept(retryChunk).duplicate, true);
assert.strictEqual(retryAsm.chunks.get(11).payload.equals(batch4), true);

// 19. record_seq correct and non-duplicated across batched chunks
const seqAsm = new ChunkAssembler({ bootId: 7, captureId: 3 });
const batchA = Buffer.concat([10,11].map((s) => makeRecordWire(7,3,s)));
const batchB = Buffer.concat([12,13,14].map((s) => makeRecordWire(7,3,s)));
const chunkA = encodeChunk({ bootId:7,captureId:3,chunkSeq:0,chunkType:"DIAGNOSTIC_RECORDS",payload:batchA,firstRecordSeq:10,lastRecordSeq:11,recordCount:2 });
const chunkB = encodeChunk({ bootId:7,captureId:3,chunkSeq:1,chunkType:"DIAGNOSTIC_RECORDS",payload:batchB,firstRecordSeq:12,lastRecordSeq:14,recordCount:3 });
seqAsm.accept(chunkA); seqAsm.accept(chunkB);
const ordered = Array.from(seqAsm.chunks.values()).sort((a,b)=>a.header.chunk_seq-b.header.chunk_seq)
  .flatMap((e)=>decodeDiagnosticWireMessages(e.payload).map((m)=>m.record.record_seq));
assert.deepStrictEqual(ordered, [10,11,12,13,14]);
assert.strictEqual(new Set(ordered).size, ordered.length);

// 20. manifest.record_count matches all received records (complete)
const dirBatch = fs.mkdtempSync(path.join(os.tmpdir(), "diag-recorder-batch-"));
const recBatch = createRecorder(dirBatch, { bootId: 7, captureId: 3 });
assert.strictEqual(recBatch.accept(chunkA).accepted, true);
assert.strictEqual(recBatch.accept(chunkB).accepted, true);
const manifestBatch = encodeChunk({
  bootId: 7, captureId: 3, chunkSeq: 2, chunkType: "CAPTURE_MANIFEST",
  payload: Buffer.from(JSON.stringify({ protocol_version: 1, boot_id: 7, capture_id: 3, record_count: 5, overflow_count: 0 })),
});
assert.strictEqual(recBatch.accept(manifestBatch).accepted, true);
const reportBatch = recBatch.finalize(2);
assert.strictEqual(reportBatch.export_status, "complete");
assert.strictEqual(reportBatch.decoded_record_count, 5);
const saved = JSON.parse(fs.readFileSync(path.join(dirBatch, "diagnostic_records.json"), "utf8"));
assert.deepStrictEqual(saved.map((r)=>r.record_seq), [10,11,12,13,14]);
fs.rmSync(dirBatch, { recursive: true, force: true });

// 21. export incomplete if batch not ACKed/persisted (missing/unacked chunk)
const dirInc = fs.mkdtempSync(path.join(os.tmpdir(), "diag-recorder-inc-"));
const recInc = createRecorder(dirInc, { bootId: 7, captureId: 3 });
assert.strictEqual(recInc.accept(chunkA).accepted, true);
// chunkB never accepted/ACKed
const manifestInc = encodeChunk({
  bootId: 7, captureId: 3, chunkSeq: 2, chunkType: "CAPTURE_MANIFEST",
  payload: Buffer.from(JSON.stringify({ protocol_version: 1, boot_id: 7, capture_id: 3, record_count: 5, overflow_count: 0 })),
});
recInc.accept(manifestInc);
const reportInc = recInc.finalize(2);
assert.strictEqual(reportInc.export_status, "incomplete");
assert.deepStrictEqual(reportInc.missing_chunks, [1]);
fs.rmSync(dirInc, { recursive: true, force: true });

console.log("diagnostic_protocol: 21 PASS");
