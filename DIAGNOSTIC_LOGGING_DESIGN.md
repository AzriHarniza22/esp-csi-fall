# Diagnostic logging design

## Stage 2: FSM checkpoint and state instrumentation

Stage 2 adds an in-memory checkpoint API and state fields to the existing
bounded diagnostic records. It does not add serial export, acknowledgements,
or a new detector path.

### Atomic checkpoint

`esp_wifi_sensing_fsm_diag_checkpoint_size()` obtains the FSM mutex and
returns the exact caller-buffer size. The caller allocates the buffer outside
the mutex, then calls `esp_wifi_sensing_fsm_diag_checkpoint_write()`. The
writer holds the existing FSM mutex while copying the header, every active
channel, and each pending raw item in logical dequeue order:

```text
header
channel snapshot
pending item [read_index + 0]
pending item [read_index + 1]
...
```

The snapshot contains checkpoint version, boot/capture identity, lifecycle and
batch sequence, monotonic timestamp, ring capacity/index/count, all mutable
detector state, runtime configuration, presence/training state, and pending
item metadata including `feature_seq`, `raw_feature`, enqueue timestamp, and
lifecycle sequence. The API performs no allocation, detector reset, queue
operation, or serial I/O.

### State records

Dequeue and process records include batch ID, batch index/size, state-before
fields, state-after fields, and a transition-reason code. Batch metadata is
assigned after dequeue and before preprocessing. The existing FSM formulas and
FIFO/overwrite behavior are unchanged.

### Lifecycle

Reset helpers emit one lifecycle record per reset invocation. Records include
peer, lifecycle sequence, reset reason, state before/after, pending count, and
monotonic timestamp. START, STOP, explicit baseline reset, automatic baseline
reset, low-jitter reset, runtime-center recovery, and channel removal remain
separate lifecycle boundaries.

### Verification boundary

The checkpoint is source-level atomic with respect to the existing FSM mutex.
It has not been validated on hardware. Checkpoint duration grows with channel
count and pending ring contents; callers must allocate the reported size
before entering the write call and must not invoke it from the radar callback.

## Stage 3: diagnostic export

The existing Web Serial connection carries one JSON object per line with the
`HMS:` prefix. Diagnostic chunks use protocol version `1` and contain
`boot_id`, `capture_id`, monotonically increasing `chunk_seq`, `chunk_type`,
`record_count`, payload length, record range, CRC32, and Base64 payload. CRC32
uses the reflected IEEE polynomial `0xedb88320`; the host fixture verifies the
standard `123456789` vector as `CBF43926`.

The firmware uses stop-and-wait transfer: one chunk remains in flight until the
browser or host recorder validates and persists it, then sends
`HMSCMD DIAG_ACK <boot_id> <capture_id> <chunk_seq> <crc32>`. A chunk is retried
at most three times with a 500 ms ACK wait. Records are peeked and dropped only
after their matching ACK, so an interrupted export leaves them available for a
later retry. The bounded payload is 1536 bytes on firmware and 2048 bytes on
the host validator.

Chunk types are `CHECKPOINT`, `DIAGNOSTIC_RECORDS`, and
`CAPTURE_MANIFEST`. The manifest is required for a host transfer to be marked
complete and carries capture status, integrity, overflow count, and diagnostic
record count. Browser ACK validation uses the same Web Serial writer as all
other commands; it never opens a second serial port.

The exported payload is an explicit binary wire format, independent of C
struct padding:

```text
magic:u32 = 0x33574d48 ("HMW3" in little-endian)
schema:u16 = 1
record_type:u8 (1=diagnostic record, 2=checkpoint)
flags:u8
payload_length:u32
payload
```

All integers are unsigned/signed fixed-width little-endian values. Floats are
IEEE-754 binary32 values written as their little-endian uint32 bit pattern;
the format never sends a C `float` object or pointer. Record payload fields
follow the public diagnostic-record declaration order, including peer MAC,
window metadata, lifecycle fields, and before/after FSM state. Checkpoint
payloads contain the checkpoint header, then each channel and pending item in
logical order, with every field written individually. The host decoder checks
the envelope length and consumes every field, rejecting trailing or missing
bytes.

### Verification boundary

Host protocol tests cover CRC, malformed chunks, identity mismatch, duplicate
chunks, missing chunks, manifest validation, wire-record round-trip decoding,
and ordered reconstruction. The ESP-IDF v5.5.3 application builds
successfully after the exporter integration. No flash or hardware transfer
test was performed, so serial timing, ACK retry behavior, and runtime queue
contention remain unverified.

The original per-reply ping hook is not part of the source-override public API
or the ESP-IDF 5.5.3 `esp_wifi_sensing` component available in this checkout.
The exporter therefore does not claim per-reply ping rows; existing aggregate
ping success/timeout counters and GUI telemetry remain unchanged.

### Hardware smoke-test corrective patch

The first hardware smoke test exposed two integration faults. The exporter
passed strings beginning with `HMS:` to `write_line()`, while
`write_line_core()` already prepends the single protocol prefix. Exporter
messages now pass JSON only, so every emitted diagnostic message has exactly
one `HMS:` prefix.

The monitor's random boot identifier and the FSM's random boot identifier were
also different generators. The FSM identity returned by
`esp_wifi_sensing_fsm_diag_get_identity()` is now authoritative: accepted
`TAKE_BEGIN`, chunk, and manifest messages use that same boot identity.
Capture identity validation remains bound to `(boot_id, capture_id)`.
