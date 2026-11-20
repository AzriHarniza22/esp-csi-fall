#!/usr/bin/env node
/*
 * Bounded host recorder for HMS diagnostic chunks.
 *
 * The transport adapter is deliberately stdin/stdout based so it can be used
 * with the existing Web Serial reader without opening a second port:
 *   cat serial.log | node diagnostic_recorder.js <output-directory>
 *
 * Each input line may be an HMS: JSON line or a raw JSON object. ACK lines are
 * written to stdout only after the chunk has been validated and persisted.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const { ChunkAssembler, decodeDiagnosticWire, decodeDiagnosticWireMessages } = require("./diagnostic_protocol.js");

function parseLine(line) {
  const text = line.trim();
  if (!text) return null;
  const json = text.startsWith("HMS:") ? text.slice(4) : text;
  return JSON.parse(json);
}

function createRecorder(directory, identity) {
  fs.mkdirSync(directory, { recursive: true });
  const assembler = new ChunkAssembler(identity);
  const report = {
    protocol_version: 1,
    boot_id: identity.bootId,
    capture_id: identity.captureId,
    chunks_received: 0,
    chunks_acknowledged: 0,
    retransmissions: 0,
    crc_failures: 0,
    duplicates: 0,
    rejected: 0,
    manifest_received: false,
    export_status: "in_progress",
  };
  const chunkDir = path.join(directory, "chunks");
  fs.mkdirSync(chunkDir, { recursive: true });

  function accept(chunk) {
    const result = assembler.accept(chunk);
    report.chunks_received += 1;
    if (result.duplicate) {
      report.duplicates += 1;
      report.retransmissions += 1;
    } else if (!result.accepted) {
      report.rejected += 1;
      if (result.reason === "crc_mismatch") report.crc_failures += 1;
    } else {
      fs.writeFileSync(
        path.join(chunkDir, `${chunk.chunk_seq}.json`),
        `${JSON.stringify(chunk)}\n`,
      );
      report.chunks_acknowledged += 1;
      if (chunk.chunk_type === "CAPTURE_MANIFEST") {
        try {
          const manifest = JSON.parse(checkedPayloadText(chunk));
          if (manifest.protocol_version !== 1 ||
              manifest.boot_id !== identity.bootId ||
              manifest.capture_id !== identity.captureId ||
              !Number.isInteger(manifest.record_count) ||
              !Number.isInteger(manifest.overflow_count)) {
            throw new Error("manifest identity or accounting is invalid");
          }
          fs.writeFileSync(path.join(directory, "manifest.json"),
            `${JSON.stringify(manifest, null, 2)}\n`);
          report.manifest_received = true;
        } catch (_error) {
          report.rejected += 1;
          return { accepted: false, reason: "invalid_manifest" };
        }
      }
    }
    return result;
  }

  function finalize(lastChunkSeq) {
    const missing = assembler.missingThrough(lastChunkSeq);
    report.missing_chunks = missing;
    let decoded = false;
    try {
      const chunks = Array.from(assembler.chunks.values())
        .sort((a, b) => a.header.chunk_seq - b.header.chunk_seq);
      const checkpoint = Buffer.concat(chunks
        .filter((entry) => entry.header.chunk_type === "CHECKPOINT")
        .map((entry) => entry.payload));
      const records = chunks.filter((entry) => entry.header.chunk_type === "DIAGNOSTIC_RECORDS");
      if (checkpoint.length > 0) {
        const decodedCheckpoint = decodeDiagnosticWire(checkpoint);
        if (decodedCheckpoint.type !== "checkpoint") throw new Error("invalid checkpoint type");
        fs.writeFileSync(path.join(directory, "checkpoint.wire"), checkpoint);
        fs.writeFileSync(path.join(directory, "checkpoint.json"),
          `${JSON.stringify(decodedCheckpoint.checkpoint, bigintReplacer, 2)}\n`);
      }
      const decodedRecords = records.flatMap((entry) => decodeDiagnosticWireMessages(entry.payload));
      if (decodedRecords.some((entry) => entry.type !== "record")) {
        throw new Error("invalid diagnostic record type");
      }
      fs.writeFileSync(path.join(directory, "diagnostic_records.json"),
        `${JSON.stringify(decodedRecords.map((entry) => entry.record), bigintReplacer, 2)}\n`);
      fs.writeFileSync(path.join(directory, "capture.diag"),
        Buffer.concat(records.map((entry) => entry.payload)));
      report.decoded_checkpoint = checkpoint.length > 0;
      report.decoded_record_count = decodedRecords.length;
      decoded = true;
    } catch (error) {
      report.decode_error = error.message;
    }
    report.export_status = missing.length === 0 && report.rejected === 0 &&
      report.manifest_received && decoded ? "complete" : "incomplete";
    fs.writeFileSync(path.join(directory, "transfer_report.json"),
      `${JSON.stringify(report, bigintReplacer, 2)}\n`);
    return report;
  }

  return { accept, finalize, report };
}

function bigintReplacer(_key, value) {
  return typeof value === "bigint" ? Number(value) : value;
}

function checkedPayloadText(chunk) {
  return Buffer.from(chunk.payload, "base64").toString("utf8");
}

function main() {
  const directory = process.argv[2];
  if (!directory) {
    process.stderr.write("usage: diagnostic_recorder.js OUTPUT_DIRECTORY\n");
    process.exitCode = 2;
    return;
  }
  process.stdin.setEncoding("utf8");
  let pending = "";
  let recorder = null;
  let lastChunkSeq = -1;
  const processLine = (line) => {
    if (!line.trim()) return;
    try {
      const message = parseLine(line);
      if (!message || message.type !== "diag_chunk") return;
      if (!recorder) {
        recorder = createRecorder(directory, {
          bootId: message.boot_id,
          captureId: message.capture_id,
        });
      }
      const result = recorder.accept(message);
      if (result.accepted || result.duplicate) {
        process.stdout.write(`HMSCMD DIAG_ACK ${message.boot_id} ${message.capture_id} ${message.chunk_seq} ${message.crc32}\n`);
        lastChunkSeq = Math.max(lastChunkSeq, message.chunk_seq);
      }
    } catch (error) {
      process.stderr.write(`diagnostic recorder: ${error.message}\n`);
    }
  };
  process.stdin.on("data", (data) => {
    pending += data;
    const lines = pending.split(/\r?\n/);
    pending = lines.pop();
    for (const line of lines) processLine(line);
  });
  process.stdin.on("end", () => {
    processLine(pending);
    if (recorder) recorder.finalize(lastChunkSeq);
  });
}

if (require.main === module) main();

module.exports = { createRecorder, parseLine };
