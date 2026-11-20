# Wi-Fi CSI Fall Detection on ESP32-WROOM-32: Research Report

*Research-only deliverable, 15 November 2026. No firmware, model, dataset, threshold, label, or hardware capture was modified or performed.*

**Evidence tags used throughout:** **\[DOC\]** official Espressif documentation · **\[SRC\]** project docs or source text I read directly (not built or run) · **\[README\]** project self-claim, unverified · **\[PAPER-PC\]** published result on a PC, laptop, router or GPU · **\[PAPER-MCU\]** published result on a microcontroller · **\[FORUM\]** engineering discussion, not proof · **\[INFER\]** my reasoning from retrieved evidence · **\[HYP\]** hypothesis to test, not a finding.

## 1. Executive Summary

**Primary recommendation.** Do not try to make a single 24-frame window classifier carry the whole problem. Use a *gated, event-centered, time-based* pipeline: (1) a quality-controlled CSI stream admitted on elapsed time, (2) a gain-invariant motion detector with a state machine, (3) segmentation of a fall-like *event* (motion burst followed by a pause), (4) a small classifier on event-level features, and (5) an event-level decision with post-event confirmation and a refractory period. Training, calibration and evaluation stay offline.

**Simpler fallback.** The same acquisition and motion detector, plus a rule-based event gate (burst energy relative to an adaptive noise floor, short rise time, followed by stillness) and no machine learning on the device.

**Five findings that drive this recommendation**

1. **Published fall detectors classify events, not short windows.** RT-Fall and Anti-Fall use about 3 s of signal; SiFall segments average 5.1 s around activities that last about 2.6 s on average \[PAPER-PC\]. Your 24-frame window lasts 0.24 s at 100 packets/s and 1.2 s at 20 packets/s. Whether it spans a whole fall depends entirely on your real packet timing. \[INFER, HYP\]
2. **Motion detection and fall classification should be separate stages.** Motion detection on a classic ESP32 is well supported: Espressif's esp-radar and the ESPectre project both do it, and ESPectre's own report shows recall near 99.8% and idle false-positive rate near 0.2% on its classic-ESP32 column (a regression set, not a sealed test) \[SRC\]. Neither addresses falls. \[INFER\]
3. **I found no validated, subject-independent, real-time CSI fall detector running on an ESP32-WROOM-32.** The ESP32 fall results I found use the S3, are small, or run inference on a PC. \[PAPER-PC, PAPER-MCU\]
4. **Evaluation design can matter more than the classifier.** Random splits and overlapping windows leak information; published CSI work has shown large accuracy drops once subjects are separated \[PAPER-PC\]. With a 50% overlapping window, adjacent windows share half their samples. \[INFER\]
5. **AGC makes absolute amplitude unreliable.** Both SiFall and ESPectre normalise amplitude so that features do not depend on signal scale \[PAPER-PC, SRC\]. Features based on raw variance are exposed to this.

**Confidence.** High that motion and fall classification should be separated and that evaluation must be subject- and session-independent. Medium that event-centered segmentation beats sliding windows for CSI falls (strong precedent in CSI and accelerometer work, but no head-to-head CSI comparison on ESP32). Low on any claim about the absolute false-alarm rate achievable on ESP32-WROOM-32, because no one appears to have measured it.

**What I could not verify.** I did not have your project artifacts, so statements about your pipeline come from your brief only. I did not compile or run any external code. Several 2026 preprints were visible only as search snippets and are flagged where used.

## 2. Research Methodology and Sources

**Official Espressif.** ESP-IDF Wi-Fi CSI documentation (several chip variants), the esp-radar, esp\_radar\_motion\_dec and esp\_wifi\_sensing component pages, the esp-csi repository overview and issue list, and the ESP32-WROOM-32 datasheet.

**GitHub.** I read the raw ALGORITHMS.md, CSI.md, FEATURES.md and performance report of ESPectre; the text of a merged RuView pull request about CSI callback load; and README-level material for several smaller projects. I did *not* clone or compile esp-csi, so statements about esp-radar internals rest on component documentation, not source reading.

**Academic.** WiFall (2014 and 2017), Anti-Fall, RT-Fall (via later papers that report and reproduce it), SiFall (read in full), the WiFall ESP32-S3 dataset and KNN-MMD, two embedded Wi-Fi sensing papers, data-leakage critiques, and a cross-device CSI study. IEEE and ACM full texts were mostly unavailable, so some numbers come from abstracts or from papers that cite them. A PubMed Central page was blocked.

**Forums and discussions.** esp32.com, esp-csi issue titles, and project pull requests. Treated as engineering evidence only.

**Limits of this method.** Search was breadth-first, not a systematic review. Reported accuracies are not comparable across papers because datasets, splits and hardware differ. Where I give a number, it is from a retrieved source or is simple arithmetic I show.

## 3. Official Espressif Capabilities and Limitations

| Topic | What the documentation says | Implication |
| --- | --- | --- |
| CSI format | Each subcarrier is two signed bytes, imaginary part first, then real. Up to three fields: LLTF, HT-LTF, STBC-HT-LTF, in that order; which are present depends on channel and packet type. \[DOC\] | Layout changes with traffic type. Fix the traffic type so the layout is constant. |
| LLTF subcarriers | 802.11a/g: indices -26 to +26, 52 total, 48 usable plus pilots at ±7 and ±21. Native order on the original ESP32 is 0\~31 then -32\~-1. \[DOC\] | Re-order before any frequency-ordered feature. |
| Invalid first word | A `first_word_invalid` flag marks the first four bytes as unusable due to a hardware limitation. \[DOC\] ESPectre's docs state that in the classic layout this hits the DC bin and subcarrier +1. \[SRC\] | Four bytes is two subcarriers. Your 51 pairs is consistent with 53 LLTF bins minus DC and +1, but I cannot confirm that is how you arrive at 51. \[INFER\] |
| Callback | The CSI callback runs from the Wi-Fi task; do not do lengthy work there; post to a queue and process in a lower-priority task. \[DOC\] | Copy only what you need, then return. |
| Sniffer mode | A station only receives frames from its AP when connected; sniffer mode is suggested to receive more CSI. \[DOC\] | Packet rate depends on traffic generation, not on the radio alone. |
| Configuration | `lltf_en`, `htltf_en`, `stbc_htltf2_en`, `ltf_merge_en`, `channel_filter_en`, `manu_scale`, `shift`, `dump_ack_en`; all LTF options default to enabled. `channel_filter_en` smooths adjacent subcarriers; turning it off keeps them independent. `ltf_merge_en` averages LLTF and HT-LTF for HT packets. \[DOC, as mirrored in esp-radio and esp-csi-rs docs\] | `channel_filter_en` changes subcarrier correlation and therefore selection and correlation features. Worth an ablation. \[HYP\] |
| Receive time | The `rx_ctrl` field carries RSSI, noise floor, receive time and antenna. \[DOC\] | Use the hardware receive timestamp for time-based windowing. |
| Hardware | ESP32-WROOM-32: dual-core Xtensa LX6 up to 240 MHz, 520 KB SRAM, 4 MB flash. The v3.6 datasheet marks the part Not Recommended For New Designs. \[DOC\] | Plan for \~28 KB-scale ring buffers, not megabytes. Consider S3/C-series for any product. |

**Espressif's sensing components.**

- **esp-radar** provides human presence and motion detection; v0.3.x adds multi-peer reception by source MAC and per-peer calibration. \[DOC\]
- **esp\_radar\_motion\_dec** computes *waveform wander* (similarity between signal vectors, 0 to 1, smaller is more stable) and *waveform jitter* (motion intensity from changes within a sliding window). It lists the original ESP32 as supported and requires ESP-IDF 5.4 or later. \[DOC\]
- **esp\_wifi\_sensing** wraps these in a state machine with debounce, dynamic baseline tracking, on-site training of wander and jitter thresholds, event callbacks and router-ping-driven sampling. Presence uses waveform wander. \[DOC\]
- **None of the Espressif component pages I read describe fall detection or activity classification.** They target presence and motion. \[DOC\]

**Engineering signals about limits.**

- esp-csi issue titles include a mismatch between `local_timestamp` and real time (#182) and a report that the CSI ping interval is ignored when an MQTT publish runs inside the CSI callback (#169). I read titles only. \[FORUM\]
- ESPectre's docs treat classic ESP32 as a supported platform and set HT20 MCS0 (6.5 Mbps) as its default there. \[SRC\] A community wiki rates the original ESP32 as "limited" for CSI and describes it as amplitude-focused \[FORUM\]; a Dev.to overview ranks it lowest of the ESP32 family but still usable \[FORUM\]. Neither is authoritative.
- Classic ESP32 has a single antenna and reports one stream per frame. RT-Fall's two-antenna CSI phase difference therefore cannot be reproduced on this hardware. \[INFER\]

## 4. Relevant GitHub Implementations

| Project | What it is | Pipeline | Evidence quality |
| --- | --- | --- | --- |
| **ESPectre** (francescopace) | Motion detection on ESP32 families including classic ESP32 | Time-slot packet admission, gain-invariant spatial turbulence (std/mean of amplitudes over 12 fixed subcarriers), Hampel filter, moving-window detector, hit-count state machine. Two profiles: a logistic fusion of two features, and an 8-feature MLP (8-24-12-1, 529 parameters). \[SRC\] | Best documented. Public dataset, parity gates, and a performance report; the report itself says the holdout was inspected during development, so it is a regression set, not a sealed test. Motion only, no fall. |
| **esp-csi / esp-radar / esp\_wifi\_sensing** | Official examples and components | wander/jitter features, FSM, on-site training. \[DOC\] | Official, but documentation-level. Presence and motion only. |
| **RuView / WiFi-DensePose** | Large claim-heavy ESP32-S3 project | Edge tiers incl. phase-acceleration "fall" rule. \[README\] | **Low.** I could not find a validated fall evaluation. One merged PR is useful engineering evidence (below). |
| **wisense** (PyPI) | Host-side library for ESP32-CSI-Tool serial data | Fall module: sudden amplitude drop then stillness; statistical baseline, optional ONNX. \[README\] | Low. Host-side, no published results seen. |
| **Landa** | Hackathon-style fall alert | Variance spike (delta above 0.65) plus prolonged inactivity. \[README\] | Low. Illustrates the two-condition pattern only. |
| **swamphackxii** | Two-ESP32 fall detection | Threshold detector or random forest, then a stillness window and countdown. \[README\] | Low, but shows a post-fall confirmation flow. |
| **BhuvanB1405/wifi-csi-activity-fall-detection** | Single ESP32 + router ping at 100 Hz setting | Offline SVM / random forest, power save disabled. \[README\] | Low. Offline. |
| **Ken35943/SG\_106B07** | ESP32-S3 CNN-BiLSTM-attention fall demo | Host-side inference. Lists real falls n=5 and synthetic fall sets. \[README\] | Low. Very small real-fall count. |
| **WiFall dataset + KNN-MMD** (RS2002) | Public ESP32-S3 dataset and few-shot cross-domain code | 10 people; fall, jump, sit, stand, walk; 60 s CSV files; 52 subcarriers. \[README, PAPER-PC\] | Useful as external data; small (a related paper lists 45 min) and S3, not classic ESP32. |

**Engineering evidence worth keeping.** A merged RuView pull request reports that in promiscuous mode the CSI callback fires 100 to 500+ times per second; calling `sendto()` inside the callback exhausted lwIP buffers and crashed the device; the fix rate-limited sends to 50 Hz. \[FORUM, S3\] This supports the documented rule to keep the callback minimal.

## 5. Academic Literature Review

### 5.1 Classical CSI fall detection (PC, laptop, router)

| Work | Method | Reported result | Notes |
| --- | --- | --- | --- |
| WiFall, INFOCOM 2014 | Weighted moving average, anomaly detection, then activity classification | 87% detection precision, 18% false alarm \[PAPER-PC\] | Laptops with 802.11n NICs |
| WiFall, IEEE TMC 2017 | One-class SVM; random forest | 90% precision at 15% false alarm; 94% at 13% \[PAPER-PC\] | Desktops with 802.11n NICs, three indoor scenarios |
| Anti-Fall | Phase and amplitude features | 89% precision, 13% false alarm, as reported by a later paper \[PAPER-PC\]; optimum activity window 3000 ms \[PAPER-PC\] | Window chosen by analysis |
| RT-Fall | Phase difference between two antennas for segmentation, fixed 3 s segment, SVM | 91% true positive, 8% false alarm, as reported by a later paper \[PAPER-PC\] | Needs two antennas |
| RT-Fall reproduced inside SiFall | Same method, run live on SiFall's testbed | TPR 64.9%, FPR 49.2% \[PAPER-PC\] | Shows how far controlled results can fall in live operation |

### 5.2 SiFall (SenSys 2022), the closest design to what you need

SiFall argues falls are too varied to template and instead segments *fall-like* events, then flags those that a variational autoencoder trained on normal fall-like activities cannot reconstruct. \[PAPER-PC\]

- **Acquisition.** Two Atheros APs, 200 packets/s, 20 MHz, fixed MCS to reduce loss and noise.
- **Gain invariance.** It models AGC as a time-varying scale shared by all subcarriers and removes it with cosine similarity between consecutive amplitude vectors (later against a fixed reference vector, to avoid dependence on the sampling interval).
- **Motion detection.** Variance of that similarity over 0.1 s above a threshold.
- **Event segmentation.** It waits for the motion to *pause*, searches back up to 5 s for a high short-time-frequency "acceleration" descriptor (threshold 2.5 m/s²), keeps monitoring about 1 s after the pause with a change-point rule, and takes the segment from 3 s before the peak to the end. Average segment 5.1 s versus 2.6 s true activity.
- **Results.** In 19.3 h with 12 subjects and 123 falls, TPR rose from 83% to 100% over 4 h while false alarms fell from 6.7 per hour in the first two hours to below 1 per hour in the last two. Over a three-day home deployment it caught 94.1% of falls with 12 false alarms among 204 fall-like events, falling from 13.4% on day one to 1.4% on day three.
- **Limits.** Atheros hardware; FallNet runs on a GPU server and the front end on a laptop; single-room, single-occupant; no real falls from elderly people; coverage degraded with distance (TPR 40% at 7 m with a model moved to a new room). It adapts continuously, which is not available to a fixed ESP32 model.

### 5.3 Data on ESP32 hardware

- **WiFall dataset / KNN-MMD** \[PAPER-PC\]: ESP32-S3 receiver, home-router transmitter, 100 Hz, one antenna, 52 subcarriers. In one-shot cross-domain tests, KNN-MMD reports accuracies of 93.26%, 81.84%, 77.62% and 75.30% for the four tasks. If the abstract lists them in task order (gesture, person identification, fall detection, action recognition), fall detection is about 77.6%; check the paper's tables before relying on this.
- **Embedded Wi-Fi sensing, Sensors 2025** \[PAPER-MCU\]: a compact DenseNet variant reaches 92.43% accuracy at 232 ms inference on an ESP32-S3. This is activity recognition, not falls, and the S3 includes vector instructions that the classic ESP32 lacks.
- **STAR** \[PAPER-PC/embedded Linux\]: 3-layer GRU, 97,616 parameters, 93.52% on 7 activities and 99.11% presence; ESP32-S3 only acquires CSI at 100 Hz, and inference runs on a Rockchip RV1126 NPU. Preprocessing used median filtering, an 8th-order Butterworth low-pass and EMD. Not an MCU result.
- **ESP32 LSTM study** \[PAPER-PC?\]: a 2025 paper uses an ESP32-WROOM module and an LSTM with >93% accuracy under 5-fold cross-validation. The split is not described as subject-independent, and where inference runs is unclear. Treat as weak.
- **Thai student symposium paper (2026)** \[PAPER, low rigor\]: ESP32-S3, 4 boards, 91.53% accuracy, and two relevant observations: FALL is sometimes confused with EMPTY because the person lies still after falling, and CSI drifted as boards warmed up.
- **ESP32 fall preprint (arXiv 2611.15532, snippet only)**: reports 93.10% accuracy and 100% precision, with 14 of 16 falls correctly classified. At n=16 the confidence interval is wide. Verify before citing. \[PAPER-PC?\]

### 5.4 Evaluation and generalisation critiques

- **Data leakage.** Two 2024 *Sensors* papers re-analyse published CSI action-recognition work and show that without subject-based partitioning the reported accuracy is inflated, with significant drops when individuals are separated. \[PAPER-PC\]
- **Overlapping windows.** A 2026 study on sensor time series states that consecutive windows share (L−s)/L of their samples and that random splits then place near-duplicates in training; it recommends reporting overlap with every random-split figure. \[PAPER-PC, not CSI, snippet\]
- **Cross-device differences.** A 2026 platform comparison finds that most cross-device CSI differences come from AGC behaviour and consistent subcarrier nonlinearities, and a simple gain-alignment step recovers much of the lost cross-device accuracy. \[PAPER-PC, snippet\]
- **Illustration of magnitude.** A non-peer-reviewed project page on an FR3 (non-Wi-Fi) system reports near-100% random-split accuracy versus 13.5 to 35.9% leave-one-user-out. Different radio, so use only as an illustration that the gap can be extreme. \[README-level\]

## 6. CSI Acquisition Recommendations

1. **Use a dedicated transmitter on a fixed channel and rate.** esp-csi's own examples include an ESP32 sender and receiver, and a router-ping variant. A controlled sender gives you a known nominal rate; router replies depend on the router. SiFall fixed the MCS to reduce loss and noise \[PAPER-PC\]; ESPectre defaults to HT20 MCS0 on classic ESP32 \[SRC\]. Disable power save (`WIFI_PS_NONE`), as several repositories do. \[README, FORUM\]
2. **Aim for at least 100 packets/s and verify what you actually get.** SiFall used 200/s and says falls add high-frequency components \[PAPER-PC\]. As a physical check: at 2.4 GHz the wavelength is about 12.5 cm, so a reflecting body part moving at 2 m/s changes the path length at up to about 4 m/s, about 32 Hz, which needs a sampling rate above 64 Hz to avoid aliasing. \[INFER, calculation\] One RuView measurement on an S3 was 28.5 Hz \[FORUM\], which would alias such motion. Measure your own rate before choosing anything else.
3. **Admit packets by elapsed time, not by count.** ESPectre divides time into fixed slots from the target rate, admits at most one packet per slot, rejects duplicate, stale and out-of-order timestamps, leaves missing slots empty, and requires at least 70% valid slots before the detector is ready. \[SRC\] This is the strongest ESP32-specific precedent I found for your requirement that windows use real elapsed time.
4. **Use the LLTF consistently, and drop invalid bins explicitly.** Re-order from the native 0\~31, -32\~-1 layout, discard packets flagged with hardware errors, and treat DC and +1 as missing when `first_word_invalid` is set. \[DOC, SRC\] Run an ablation on `channel_filter_en` and `ltf_merge_en`. \[HYP\]
5. **Keep the callback minimal.** Copy a fixed-size record (receive timestamp, RSSI, noise floor, amplitudes) into a queue and return. No logging, UART or network calls. \[DOC, FORUM\]
6. **Monitor data quality continuously.** Log accepted and admitted packets per second, inter-arrival histogram with P50, P95, P99 and maximum gap, missing rate and the sampling coefficient of variation (metrics defined in the UniFi paper \[PAPER-PC\]), hardware-error drops, queue overflows, RSSI, noise floor and board temperature (given the drift reported above). Gate detection on a minimum valid-slot fraction.
7. **Leave AGC on and make features scale-invariant.** One esp32.com reply suggests fixing AGC values to test model stability \[FORUM\]; I did not verify a supported API for this on the classic ESP32, so the safer, better-evidenced route is invariance (cosine similarity as in SiFall, std/mean as in ESPectre). \[PAPER-PC, SRC\]
8. **Fix the geometry and report it.** Link distance, heights and orientation changed results in SiFall; record placement as a dataset variable so it can be a hold-out factor.

## 7. Preprocessing Comparison

**Evidence gap, stated up front.** I found no head-to-head comparison of Hampel, Butterworth, wavelet and moving-average preprocessing for *fall* detection on ESP32. The table combines design rationale from published systems with ESPectre's measured feature experiments, which concern motion rather than falls.

| Method | What the evidence shows | Cost and risk on ESP32 | Recommendation |
| --- | --- | --- | --- |
| **Amplitude extraction** | ESPectre's production features use amplitude only, no phase. \[SRC\] SiFall also works from amplitude. \[PAPER-PC\] | Cheap (magnitude of I/Q). | **Use.** |
| **Phase extraction / sanitisation** | ESPectre's offset-free phase-shape features scored at chance for motion (worst-pair AUC about 0.48 to 0.50) and were rejected for motion; they note phase might help stationary presence. \[SRC\] RT-Fall relied on a two-antenna phase difference. \[PAPER-PC\] | Needs sanitisation of CFO/STO; single antenna removes the best-evidenced phase signal. | **Not in the first pipeline.** Revisit only for the stationary-presence question. |
| **Gain-invariant normalisation** | SiFall: cosine similarity between amplitude vectors removes the shared AGC factor. ESPectre: std/mean per packet is invariant to a uniform scale. \[PAPER-PC, SRC\] A cross-device study attributes most device differences to AGC. \[PAPER-PC\] | Cheap. | **Mandatory.** |
| **Moving average / median** | WiFall used a weighted moving average; STAR a median filter. \[PAPER-PC\] | Cheap. | Use mild smoothing on *scalar* streams only. Smoothing raw subcarriers before computing motion variance can suppress the short high-frequency content that distinguishes falls. \[INFER\] |
| **Hampel filter** | ESPectre enables it by default on the turbulence stream (window 7, threshold 5 MAD). \[SRC\] Widely used elsewhere. | Cheap (running median). | **Use, but ablate.** A tight threshold could clip genuine impact spikes. Measure event recall with and without. \[HYP\] |
| **Butterworth low-pass** | ESPectre offers a first-order low-pass, disabled by default, whose coefficients assume a nominal 100 Hz cadence; irregular sampling changes the effective cutoff. \[SRC\] STAR used an 8th-order filter off-device. \[PAPER-PC\] | Low order is cheap; irregular timing breaks the fixed-rate assumption. | **Skip initially.** If used, first order and time-aware. |
| **Wavelet / EMD** | Used in several PC pipelines. No ESP32 fall evidence. | High. | **Offline analysis only.** |
| **Packet-level outlier rejection** | ESPectre drops hardware-error packets, duplicate and out-of-order timestamps. \[SRC\] | Cheap. | **Use.** |
| **Baseline / noise normalisation** | ESPectre's Lightweight profile calibrates at start-up using 10 s of quiet data, extended up to 30 s if a burst is detected, and applies only 50% of the observed offset. \[SRC\] A Thai study saw CSI drift as boards warmed. \[PAPER, low rigor\] | Cheap. | **Use**, with slow re-calibration. |
| **Subcarrier selection** | ESPectre moved from per-session selection (README claims F1 above 96% for its NBVI method \[README\]) to a *fixed 12-tone set spread across the band*, justified by measured coherence: motion perturbation stays coherent across about 10 subcarriers while quiet noise is nearly independent per tone. \[SRC\] Wital selects the highest-variance subcarrier. \[PAPER-PC\] | Fixed set is free; selection costs a calibration pass. | **Start with a spread-out fixed set**, then test calibration-time selection. |
| **Temporal differencing** | SiFall uses consecutive-vector similarity; ESPectre uses an L1 profile displacement at a 100 ms lag. \[PAPER-PC, SRC\] | Cheap. | **Core of the motion signal.** |

**Preferred preprocessing chain (first version).** Hardware-error and invalid-bin removal → time-slot admission → amplitude → per-packet gain-invariant scalars (std/mean, cosine similarity, lagged L1 displacement) → Hampel on scalars → baseline normalisation. Everything after the scalars runs on 3 to 4 streams, not 51 subcarriers.

## 8. Motion / Event Segmentation Comparison

### 8.1 Should segmentation precede classification?

**Yes, as a working hypothesis to confirm.** Every CSI fall system I read segments first: WiFall (anomaly detection then classification), RT-Fall (phase-based segmentation then SVM) and SiFall (motion detection, pause-based segmentation, then a neural network). \[PAPER-PC\] In wearable accelerometer work, an event-centered window performed as well as or better than sliding windows in two studies, and in one comparison the best results of both approaches were within 1% (99.66% sliding, 99.78% impact-defined) \[PAPER, different modality\]. Segmentation also solves your false-FALL-at-rest problem structurally: with no motion there is no candidate to classify. \[INFER\]

The counter-risk is that a missed motion trigger is a missed fall, and segmentation errors propagate. SiFall reports movement-detection error with median 0.5%, 1.1% and 1.8% for body-, torso- and limb-level movement. \[PAPER-PC\] Treat upstream recall as a measured quantity (Section 14), not an assumption.

### 8.2 Method comparison

| Method | Evidence | Fit for ESP32 |
| --- | --- | --- |
| Sliding-window variance of a gain-invariant scalar | SiFall: variance of cosine similarity over 0.1 s above a threshold. ESPectre: moving variance of spatial turbulence. \[PAPER-PC, SRC\] | **Best fit.** O(1) per packet with running sums. |
| Std / coefficient of variation | ESPectre turbulence. \[SRC\] | Cheap. |
| Dynamic threshold + adaptive noise estimate | ESPectre start-up calibration and settled-level recovery; esp\_wifi\_sensing on-site training and dynamic baseline. \[SRC, DOC\] | Cheap; drift handling is essential. |
| Hit-count state machine | ESPectre needs 4 consecutive MOTION readings to enter and 3 IDLE to leave (about 0.75 to 1.0 s and 0.5 to 0.75 s). \[SRC\] esp\_wifi\_sensing adds debounce. \[DOC\] | Cheap. The confirmation delay is a latency cost for falls. |
| Change-point detection | SiFall uses an online greedy change-point rule to find the end of an event for up to 1 s after the pause. \[PAPER-PC\] I found no CSI-fall evidence specifically for CUSUM. | O(1) per sample; **plausible, unverified for CSI falls**. |
| Energy / time-frequency segmentation | SiFall's acceleration-like descriptor from a short-time Fourier transform; threshold 2.5 m/s² separates most walking and running from falls and fall-like activity. \[PAPER-PC\] | An FFT per evaluation step; feasible if short and infrequent. Verify cost. |
| Statistical anomaly detection | WiFall one-class SVM; SiFall VAE. \[PAPER-PC\] | Not a segmenter on MCU. |

### 8.3 Separating the four situations

| Situation | Signal signature (from literature) | Detection mechanism |
| --- | --- | --- |
| Background, no movement | Low, stable motion metric near the noise floor | Motion FSM IDLE |
| Ordinary movement (walking, running) | Sustained energy, low acceleration descriptor, no abrupt stop | Motion FSM MOTION; acceleration below threshold. SiFall's threshold screens out most walk and run. \[PAPER-PC\] |
| Sudden non-fall movement (sit, jump, squat, bow, kneel) | High short-time frequency content, then a pause | Passes the gate; **must be rejected by the classifier**. These are the hard negatives. |
| Fall | High acceleration descriptor, then a pause; RT-Fall reports a sharp power-profile decline in the time-frequency domain. \[PAPER-PC\] | Event classifier plus post-event behaviour |

**Honest limit.** SiFall itself notes that falls and fall-like activities such as sitting on the floor or lying down can look similar, that slow falls are hard, and that a person who loses consciousness may stay in place. \[PAPER-PC\] No source I read shows this ambiguity solved with ESP32 CSI.

## 9. Window Duration and Stride Comparison

### 9.1 What published systems use

| System | Window | Notes |
| --- | --- | --- |
| RT-Fall | 3 s fixed segment (2 s before the end reference point, 1 s after, per a patent text) \[PAPER-PC\] | Segmentation triggered by antenna phase-difference transitions |
| Anti-Fall | 3000 ms chosen as optimum on two datasets \[PAPER-PC\] | Window selected by analysis |
| SiFall | Variable; average 5.1 s around events averaging 2.6 s; STFT-based \[PAPER-PC\] | 3 s before peak to the end of the pause |
| Physics-driven transformer (2026) | 5 s sliding buffer (5000 packets) \[PAPER-PC, snippet\] | Not an ESP32 system |
| ESPectre (motion only) | 1000 ms window, 250 ms evaluation interval, 100 pps target \[SRC\] | Not a fall detector |
| Wearable accelerometer studies | 0.5 s windows gave at least 94% accuracy with SVM and k-NN in one study; 1 s step in a streaming study \[PAPER, different modality\] | Do not transfer to CSI |

### 9.2 What your 24-frame / 12-frame window means in time

This is arithmetic, not a measurement. Substitute your real timestamps.

| Packet rate | 24-frame window | 12-frame stride | Frames in a 3 s window | 24 frames as share of 3 s |
| --- | --- | --- | --- | --- |
| 20 /s | 1.2 s | 0.6 s | 60 | 40% |
| 50 /s | 0.48 s | 0.24 s | 150 | 16% |
| 100 /s | 0.24 s | 0.12 s | 300 | 8% |
| 200 /s | 0.12 s | 0.06 s | 600 | 4% |

**\[HYP\]** If your effective rate is 50 to 100 packets/s, your window sees well under a fifth of the duration used by the published fall detectors. A window that short may capture only an impact fragment, which looks like many ordinary movements. If your rate is closer to 20/s, the window is more reasonable in duration but then Nyquist (Section 6) is the concern. In either case, **do not assume a frame count equals a duration.** Because 24/12 is a 50% overlap, window-level splits also leak (Section 14).

### 9.3 Strategy comparison

| Strategy | Advantages | Risks | Evidence |
| --- | --- | --- | --- |
| Fixed non-overlapping | Simple; no leakage between neighbours | Can split a fall across two windows | Common in offline work |
| Overlapping sliding | Low latency; no trigger needed | Redundant compute; near-duplicates leak in random splits; stationary windows constantly evaluated | WiFall-style and many DL papers |
| **Event-triggered** | Classifies once per event; no evaluation at rest; variable length possible | Depends on trigger recall | RT-Fall, SiFall \[PAPER-PC\] |
| Adaptive | Matches window to event duration | Variable-length inputs are hard for fixed-size models (SiFall uses a fully convolutional network for this) | SiFall |
| Multi-scale | Short scale for detection, long scale for classification | More state | Reasonable synthesis \[INFER\] |

### 9.4 What to investigate first

- **Primary:** event-centered segment, pre-event 2 s and post-event 1 s as in RT-Fall, with a grid of pre in {1, 2, 3} s and post in {1, 2, 3} s. Cut by elapsed time, not frame count.
- **Fallback comparison:** sliding 3 s windows with a 0.5 to 1 s hop, same features, same splits, for an apples-to-apples test against event-centered.
- **Multi-scale:** a 0.25 to 1 s scale for the motion gate, 3 s for classification.
- **Latency expectation:** alarm time is roughly the time to detect the pause plus any post-event monitoring. SiFall reports that its main delay is its 1 s monitoring step. \[PAPER-PC\] Measure yours.

### 9.5 Variable packet intervals

1. Timestamp every packet at the hardware receive time.
2. Admit packets into fixed time slots (ESPectre's model): at most one packet per slot, reject duplicates and out-of-order stamps, leave gaps empty. \[SRC\]
3. Require a minimum valid-slot fraction (ESPectre: 70%) and reset history when a gap reaches the window length. \[SRC\]
4. Compute lagged features using the exact slot offsets or the real timestamps, not packet indices. ESPectre's channel-trajectory features are explicitly physical-time based. \[SRC\]
5. Small gaps may be linearly interpolated, as a Wi-Fi sensing paper does for breathing estimation \[PAPER-PC\]; long gaps invalidate the window. A UniFi-style time-aware attention model avoids resampling but is far too heavy for the target. \[PAPER-PC\]
6. Report missing rate and sampling coefficient of variation per recording, and use them as dataset-quality gates.

## 10. Feature Extraction Comparison

| Family | Evidence | ESP32 cost | Verdict |
| --- | --- | --- | --- |
| **Time-domain statistics** (variance, MAD, IQR/mean, zero-crossing rate, peak-to-peak) | RT-Fall lists normalised standard deviation and median absolute deviation among eight features. ESPectre's MLP uses IQR/mean, zero-crossing rate and lag-1 autocorrelation. \[PAPER-PC, SRC\] | Low | **Use**, computed on gain-invariant scalars. |
| **Temporal derivatives / displacement** | ESPectre L1 profile displacement lag ratio; SiFall acceleration descriptor. \[SRC, PAPER-PC\] | Low to medium | **Use.** |
| **Frequency-domain / spectral energy** | SiFall classifies STFT segments; RT-Fall exploits the power-profile decline in time-frequency. \[PAPER-PC\] | Medium. Use a short FFT or a few Goertzel bands on one scalar stream. | **Use band energy ratios**; avoid full spectrograms on-device. |
| **Signal energy and shape of the burst** (peak, rise time, decay slope, duration, post-event residual) | Inferred from RT-Fall's power decline and SiFall's use of low-frequency and end-of-motion parts. \[PAPER-PC, INFER\] | Low | **Most promising for falls vs fall-like.** |
| **Subcarrier correlation / channel shape** | ESPectre retains four channel-shape features in its MLP, yet rejected several others for lacking cross-domain gain despite strong within-session ranking. \[SRC\] | Medium to high (full-band complex profile) | **Cautious.** Treat as optional. |
| **Wavelet features** | PC pipelines only | High | Offline only. |
| **Entropy** | No relevant evidence retrieved | Medium | Defer. |
| **PCA** | Used in several PC pipelines. | Medium if learned on-device | Offline; export a fixed projection if useful. |
| **Learned representations** | SiFall VAE encoder; KNN-MMD ResNet18. \[PAPER-PC\] | Not on this target | Offline reference only. |

**Which are most discriminative for falls?** The literature points to (a) the abrupt high-frequency burst, (b) the sharp decline in signal power afterward, and (c) the pause or stillness that follows. \[INFER from RT-Fall and SiFall\] These need ablation on your data. A cautionary lesson from ESPectre's records: features that rank strongly within a session often fail across environments, so judge features only by cross-subject and cross-session results. \[SRC\]

**Constraint on all features:** they must not depend on absolute amplitude.

## 11. Classification Algorithm Comparison

**Reading this table.** Where I found no CSI-fall evidence I say so instead of inventing figures. "Demonstrated on ESP32" means inference or data collection on an ESP32 for CSI, which I found for none of these *for falls*.

| Method | CSI fall evidence | Generalisation evidence | MCU suitability (flash/RAM/latency) |
| --- | --- | --- | --- |
| **Threshold rules** | RT-Fall and SiFall use thresholds for segmentation; hobby projects use variance spikes. \[PAPER-PC, README\] | Depends on per-site calibration | Excellent. |
| **Logistic regression** | ESPectre uses a fixed logistic fusion for motion on ESP32. \[SRC\] | Not measured for falls | Excellent. |
| **Linear SVM** | RT-Fall used an SVM; your current model. \[PAPER-PC\] | Your subject-holdout result already shows a gap | Excellent; same cost as logistic regression. |
| **RBF SVM** | WiFall one-class SVM: 90% precision at 15% false alarm on PCs. \[PAPER-PC\] | Not reported across subjects | Support vectors must be stored; cost grows with their number. \[INFER\] |
| **Random forest** | WiFall: 94% precision at 13% false alarm on PCs. \[PAPER-PC\] | In-domain only | Feasible if shallow and few trees. \[INFER\] |
| **Decision tree** | Used for feature selection in a student report. | High variance | Excellent but brittle. |
| **Gradient boosting** | None retrieved | None | Feasible if small. \[INFER\] |
| **k-NN** | Used inside KNN-MMD for cross-domain support sets. \[PAPER-PC\] | Few-shot adaptation context | Poor: needs stored prototypes and distance computation. A wearable paper makes the same point. \[PAPER\] |
| **Naive Bayes** | None | None | Cheap, weak assumptions. |
| **1D CNN** | CSI DenseNet-variant HAR at 232 ms on ESP32-S3 \[PAPER-MCU\]; a quantised 1D-CNN for IMU HAR used 304 kB flash, 86 kB RAM, 54 ms on S3 \[PAPER-MCU, different sensor\]. | Not shown for falls | **Untested on classic ESP32**; S3 has vector instructions classic lacks. \[INFER\] |
| **CNN-LSTM** | Accelerometer CNN-LSTM at 113.6 ms per 4 s window on S3 \[PAPER-MCU, different sensor\]; CSI CNN+LSTM+transformer on PCs. \[PAPER-PC\] | WiFall data cross-domain varies widely | Heavy for classic ESP32. |
| **LSTM / GRU** | ESP32 LSTM activity study (weak protocol); STAR GRU on an NPU. \[PAPER-PC\] | Not subject-independent | Not recommended on this target. |
| **TCN** | None retrieved | None | Plausible, unverified. |
| **Autoencoder / anomaly** | SiFall VAE gives the best real-world false-alarm trajectory I found: below 1 per hour after adaptation. \[PAPER-PC\] | Moved to a new room with about 78.3% average accuracy without fine-tuning; adapts online | GPU in the paper. On-device version is unproven. |
| **Hybrid rule + ML** | SiFall and RT-Fall are both of this form. \[PAPER-PC\] | Best precedent | Natural fit. |

**Generalisation reality check.** KNN-MMD's one-shot cross-domain fall figure of about 77.6% (if the abstract's task order holds) and SiFall's 78.3% on a new room show that cross-domain is the open problem, not the classifier family. \[PAPER-PC\]

**Selection rule.** Climb a ladder and stop at the first rung that meets the event-level targets under leave-one-subject-out: (1) rules, (2) logistic regression or linear SVM on event features, (3) a small tree ensemble, (4) a quantised 1D CNN only if rung 3 fails and the dataset is large enough. This honours your instruction not to favour deep learning by default.

## 12. Temporal Decision and False Alarm Reduction

### 12.1 Three separate layers

**Yes, these should be separate stages.** A fall is an *event* lasting a second or two; stabilisers such as majority voting and hysteresis were designed for *states*. Applying a state-style smoother to overlapping window scores trades missed or delayed falls for fewer flips. Your observation that stabilisation reduced transitions but also some metrics is consistent with this, though the cause is unproven. \[INFER, HYP\]

| Layer | Output | Purpose |
| --- | --- | --- |
| 1. Raw classifier output | Score or label per candidate (event, or window if kept) | Pure model quality; evaluate in isolation |
| 2. Stabilised prediction | Motion-gated, margin-thresholded label with an UNCERTAIN state | Remove flicker and low-confidence guesses |
| 3. Fall event decision | NONE, SUSPECT, FALL\_CONFIRMED | Merge positives into one event, apply a refractory period, post-event confirmation |

### 12.2 Techniques

| Technique | Evidence | Verdict |
| --- | --- | --- |
| Consecutive-window voting | A 2026 transformer system flags "wait" on one confident frame and alerts only after consecutive alarms exceed a history length. \[PAPER-PC, snippet\] A radar fall detector requires two models to agree. \[PAPER-MCU\] | Useful for sliding windows; less for event-triggered. |
| Majority voting | General practice | Weak for short events. |
| Hysteresis | esp\_wifi\_sensing debounce; ESPectre 4/3 hit counts. \[DOC, SRC\] | Use on the *motion* state and on SUSPECT. |
| Debounce / refractory | General practice | **Required** after an alarm. |
| Event-level classification | SiFall, RT-Fall | **Core.** |
| Multi-stage detection | SiFall front-end rules then a network | **Core.** |
| Confidence / margin thresholds with UNCERTAIN | ESPectre uses thresholds tuned on sequential replay because dense-window false-positive rates did not reflect the empty-room alarm budget. \[SRC\] | **Use**, and tune on alarms per hour, not per-window FP. |
| Post-event confirmation | Fall then stillness patterns in wisense, Landa and swamphackxii. \[README\] | Use as "no recovery motion within T", **not** as presence confirmation. A Thai study found post-fall lying still is confused with an empty room. \[PAPER, low rigor\] |

### 12.3 Preventing repeated FALL at rest

1. **Gate by motion state.** The event classifier runs only for a candidate created by a motion burst. No candidate means no FALL. This is the structural fix.
2. **Train on rest.** Include long empty-room and static-presence recordings as negatives, as ESPectre's dataset does. \[SRC\]
3. **Evaluate on alarms per hour** over long recordings (ESPectre reports idle alarms per hour per link). \[SRC\]
4. **Refractory period** after any alarm and a **minimum gap** between candidates.
5. **Drift handling:** adaptive baseline, and log temperature. \[PAPER, low rigor\]
6. **Rejection state:** if a candidate's features fall outside the training range, output UNCERTAIN rather than FALL.

**Confirmation window.** One accelerometer paper cites a literature figure of about 24.5 s without recovery as a marker of more serious falls. Treat the confirmation time as a product decision to tune against false alarms per hour and latency, not a constant to copy. \[PAPER, different modality\]

**Stability metrics to report:** transitions per hour, mean time in each state, and alarm count per hour at rest.

## 13. ESP32-WROOM-32 Feasibility Analysis

### 13.1 What has actually been demonstrated

| Category | Items | Caveat |
| --- | --- | --- |
| **1. Demonstrated on ESP32** (CSI, any task) | ESPectre motion detection on classic ESP32: a two-feature logistic profile and an 8-input MLP with 529 parameters; recall near 99.6 to 99.8% and idle false-positive rate near 0 to 0.2% on its classic-ESP32 column \[SRC\]. esp-radar / esp\_wifi\_sensing presence and motion \[DOC\]. CSI acquisition at about 100 Hz on ESP32 \[multiple\]. | Motion and presence only. ESPectre's holdout was inspected during development, so these are regression numbers. **No validated fall detector on ESP32-WROOM-32 found.** |
| **2. Comparable embedded hardware** | DenseNet-variant CSI activity recognition, 232 ms, ESP32-S3 \[PAPER-MCU\]. IMU CNN (304 kB flash, 86 kB RAM, 54 ms) and CNN-LSTM (113.6 ms per 4 s) on ESP32-S3 \[PAPER-MCU, accelerometer\]. GRU on a Rockchip RV1126 NPU with ESP32-S3 acquiring CSI \[PAPER, embedded Linux\]. | S3, not classic; different sensors or different SoC class. |
| **3. PC / laptop / GPU only** | WiFall, Anti-Fall, RT-Fall, SiFall (GPU back end), KNN-MMD (ResNet18), transformer fall detectors, the ESP32 LSTM studies where inference location is unclear. | Cannot be assumed to fit. |
| **4. Plausible, not verified on ESP32** | Event-feature logistic regression or linear SVM; shallow tree ensemble; short FFT or Goertzel bands on one scalar stream; small int8 1D CNN; encoder-only autoencoder score. | Needs hardware-in-the-loop measurement. |

### 13.2 Resource accounting (arithmetic, not measurement)

- Raw I/Q for 51 subcarriers at one byte each part = 102 bytes per packet. Five seconds at 100 packets/s = 500 packets = **51 KB**.
- The same as uint8 amplitudes = **25.5 KB**. As three float32 scalar streams = **6 KB**.
- The chip has 520 KB SRAM in total; the Wi-Fi stack, FreeRTOS and your other tasks use part of it, so measure free heap rather than assume.
- **Design target \[HYP\]:** keep the pipeline's own state well under about 50 KB, by computing scalars per packet and keeping a short raw ring only for debugging.
- I retrieved no CPU-per-packet figures for ESPectre or esp-radar on classic ESP32, so I cannot give CPU load. The per-packet work in the recommended chain (51 magnitudes, std/mean, one cosine similarity, a 7-sample median) is small, but it must be measured at your packet rate.

### 13.3 Concurrency and robustness

- The CSI callback runs in the Wi-Fi task and must only enqueue. \[DOC\] A merged RuView fix and an esp-csi issue title both show what happens when slow work sits in the callback. \[FORUM\]
- A tiered design that runs the callback on one core and DSP on the other with a ring buffer between them is documented for the S3 in RuView's architecture notes. \[README-level, S3\] Classic ESP32 is also dual-core, so the pattern transfers, but verify under load.
- Give the processing task a lower priority than the Wi-Fi task, allocate buffers statically, and record stack and heap high-water marks over multi-hour runs. \[INFER, general ESP-IDF practice\]
- **Packet loss is real.** ESPARGOS, a multi-ESP32 channel sounder, reports that receivers intermittently miss frames and that the underlying causes were unknown to its authors. \[PAPER-PC\] A Rust ESP32 CSI crate tracks per-transmitter sequence-number gaps to estimate loss on air. \[SRC-level, other chip family\] Design for loss: slot admission, valid-slot gating, and no reliance on every packet.
- **Product risk.** The v3.6 ESP32-WROOM-32 datasheet carries a Not Recommended For New Designs notice. ESPectre also lists S3 and C-series parts as recommended in its hardware guidance. Keep the pipeline portable. \[DOC, README\]

### 13.4 Feasibility verdicts

| Architecture element | Verdict | Basis |
| --- | --- | --- |
| Acquisition, admission, QC | Feasible | ESPectre precedent \[SRC\] |
| Gain-invariant scalars + motion FSM | Feasible | ESPectre runs this on classic ESP32 \[SRC\] |
| Event segmentation by pause detection | Feasible; unverified for falls | SiFall logic is O(1) per sample except an STFT step \[PAPER-PC\] |
| Event-level linear or small-tree classifier | Feasible by size; unverified | Arithmetic and general MCU practice \[INFER\] |
| Quantised 1D CNN | Uncertain on classic ESP32 | Only S3 evidence |
| LSTM / GRU / transformer | Not recommended | No classic-ESP32 evidence |
| VAE anomaly scoring | Offline | GPU in SiFall |

## 14. Evaluation Methodology

### 14.1 Why your previous results may disagree (to check, not assume)

You reported good take-level results, weaker per-window results under phase-aware labels, and many false FALL predictions in a subject hold-out. Several mechanisms could produce this pattern, and I cannot tell which applies without your evaluation scripts:

- **Take-level aggregation can hide window errors**, for example when one positive window marks a whole fall take as detected, or when stationary takes dilute false positives. \[HYP\]
- **Overlap leakage.** Your windows overlap by (24−12)/24 = 50%. Random window-level splits put near-duplicates in train and test. \[INFER from a published rule that overlap equals (L−s)/L\]
- **Subject leakage.** Published CSI work shows large accuracy drops once subjects are separated. \[PAPER-PC\]
- **Class imbalance and label phases.** A fall has few impact windows; pre-fall, impact and post-fall labels change the positive rate. \[HYP\]
- **Distribution shift.** New subjects and sessions change amplitude statistics, partly through AGC. \[PAPER-PC\]

### 14.2 Recommended protocol

1. **Group every split.** Never separate windows of the same take, session or subject across train and test.
2. **Three hold-out axes:** leave-one-subject-out, leave-one-session-out (different days, warm and cold boards) and leave-one-environment-or-placement-out.
3. **Sealed final test.** Tune on validation subjects only. ESPectre's own report acknowledges its holdout was inspected during development and calls it a regression set; adopt a genuinely sealed test and use it once. \[SRC\]
4. **Event as the primary unit.** Annotate impact time and event start and end. Count a detection as a true positive if the alarm falls within a tolerance window around the annotated event (an asymmetric window that favours early detection and counts any overlap is used in one streaming study \[PAPER, accelerometer\]). An alarm that matches no annotated fall is a false alarm; merge duplicates.
5. **Evaluate the two stages separately.** *Stage A:* the fraction of annotated falls that produce a motion detection. *Stage B:* classification accuracy conditional on events Stage A caught. End-to-end recall is bounded by Stage A.
6. **Long continuous negatives.** Hours of empty-room, static-presence and ordinary-activity recordings. Report alarms per hour and per 24 h. Because consecutive samples are strongly autocorrelated, treat each recording as one unit and bootstrap by recording.
7. **Report split details with every number**, including window overlap, as one published reporting rule recommends. \[PAPER-PC, snippet\]
8. **Confidence intervals always.** One radar study reports 13 of 14 falls detected (recall 92.9%) with a 95% interval of 68.5 to 98.7%; that is the width to expect with about 14 events. \[PAPER-MCU\]

### 14.3 Metrics

| Metric | Level | Why |
| --- | --- | --- |
| Fall precision and recall | Event | Primary outcome |
| Specificity | Window and segment | Diagnostic |
| F1 and confusion matrix | Event and window | Show where errors fall |
| False alarms per hour | Continuous recordings | The deployment-relevant cost. WiFall and SiFall both report false-alarm rates rather than accuracy. \[PAPER-PC\] |
| Missed fall events, event detection rate | Event | Safety outcome |
| Detection latency | Impact to alarm, median and 90th percentile | SiFall's main delay was its 1 s monitoring. \[PAPER-PC\] |
| Prediction stability | Transitions per hour, dwell time | Detect flicker |
| Per-subject and per-environment spread | Minimum, median, maximum | Hidden failures |
| Stage A recall | Event | Separates motion failure from classification failure |

**Why accuracy alone is insufficient.** Falls are rare relative to everything else. A detector that never alarms can score very high accuracy while missing every fall; a detector with a 1% window false-positive rate can still alarm many times an hour at 100 windows per second. Misses and false alarms have very different costs, and only event-level recall and alarms per hour express them.

## 15. Recommended End-to-End Architecture

### 15.1 Primary architecture: gated, event-centered, two-stage with event-level decision

| Stage | Runs on | Function | Key evidence |
| --- | --- | --- | --- |
| **S0 Acquisition and QC** | ESP32 | Dedicated transmitter at 100 packets/s or more, fixed channel and MCS, power save off; callback enqueues; hardware-error and invalid-bin removal; elapsed-time slot admission; valid-slot gate; quality counters | \[DOC, SRC, PAPER-PC\] |
| **S1 Gain-invariant scalars** | ESP32, per packet | Amplitude; std/mean turbulence over a spread-out fixed subcarrier set; cosine similarity to a reference vector; lagged L1 displacement; Hampel on scalars | ESPectre, SiFall |
| **S2 Motion detection** | ESP32 | Moving variance or small logistic fusion over a time window; adaptive noise floor from start-up calibration with slow recovery; hit-count state machine IDLE/MOTION | ESPectre, esp\_wifi\_sensing |
| **S3 Event segmentation** | ESP32 | When motion energy peaks and then pauses, cut an event segment by elapsed time (start: pre-event 2 s grid; end: pause plus a short post-event period) | SiFall, RT-Fall |
| **S4 Event classifier** | ESP32 | Gain-invariant event features (burst peak, rise time, decay slope, duration, band energy ratios, post-event residual, pre-event motion) into the first adequate rung of the classifier ladder | Section 11 |
| **S5 Event decision** | ESP32 | NONE → SUSPECT → FALL\_CONFIRMED with margin threshold, UNCERTAIN rejection, "no recovery motion within T" confirmation, refractory period | Section 12 |
| **Offline** | Host | Data management, grouped cross-validation, feature ablation, threshold selection by alarms per hour, export and C/Python parity tests, hard-negative mining, optional VAE as an analysis tool | SiFall, your parity harness |

**Why this addresses the problems you listed.** Rest cannot produce FALL because S4 is only reached via S3 and S3 only via a motion burst. Packet-interval variability is handled in S0. Ordinary movement is rejected by the acceleration-style gate and the classifier. Motion failure and classification failure become separately measurable.

### 15.2 Simpler fallback

S0 to S3 as above, then a rule gate: burst energy above a multiple of the calibrated noise floor, short rise time, a pause, and no motion resumption for T seconds, followed by the same S5 refractory logic. No machine learning on the device. Thresholds come from offline analysis of your data and are re-calibrated per site. This mirrors the structure of RT-Fall and SiFall's front end, and of the fall-then-stillness patterns in smaller projects. \[PAPER-PC, README\]

### 15.3 Expected benefits, trade-offs and confidence

| Recommendation | Expected benefit | Trade-off | Evidence | Confidence |
| --- | --- | --- | --- | --- |
| Separate motion detection from fall classification | Isolates failures; removes rest false alarms structurally | Extra stage; trigger recall caps recall | CSI literature \[PAPER-PC\] | High |
| Elapsed-time admission and windows | Defensible features at variable rates | Some packets discarded | ESPectre \[SRC\] | High |
| Gain-invariant features | Less drift across sessions and devices | May discard some amplitude cues | SiFall, ESPectre, cross-device study | High |
| Event-centered window about 3 s to start | Matches published fall durations | Latency of about the pause plus post-event time | RT-Fall, Anti-Fall, SiFall | Medium |
| Event-level decision layer | Fewer false alarms from flicker | Added latency | SiFall alarms per hour trend; smoothing precedent | Medium |
| Linear model first, then trees | Cheap; fits the MCU; easy to debug | Limited capacity | General; WiFall RF/SVM results on PCs | Medium |
| Subject- and session-grouped evaluation | Honest estimates | Lower reported numbers | Leakage papers | High |
| Any absolute false-alarm target on WROOM-32 | None claimed | Unknown until measured | No ESP32 measurement found | Low |

## 16. Dataset and Training Recommendations

**Scale and diversity.** SiFall used 16 volunteers aged 21 to 56, 42 to 100 kg and 155 to 186 cm; the WiFall ESP32-S3 dataset has 10 people. \[PAPER-PC\] Treat roughly 10 to 16 subjects as the minimum comparable to published work, with body-size and age spread, and more if budget allows. I did not find a published figure for how many subjects make a subject-independent estimate reliable, so do not treat this as a threshold.

**Fall taxonomy.** SiFall separates *walk falls* (slip, stumble), *stop falls* (loss of balance or consciousness) and *slow falls* (dizziness, weakness), with random orientation and a safety mattress. The WiFall dataset includes forward, left, right, seated and backward falls. \[PAPER-PC\] Cover direction, posture before the fall, and surface.

**Hard negatives (essential).** Sit to chair, sit to floor, kneel, squat, bow, jump, lying down, dropping an object, pets, diving onto a sofa. In SiFall's home deployment the false alarms came from sitting on a sofa, an object falling from a wardrobe, jumping onto a sofa and a handstand. \[PAPER-PC\] Include variants at different locations and orientations relative to the link.

**Rest negatives (essential).** Hours of empty-room recordings, static presence (sitting or lying quietly), other occupants, appliances, router-traffic changes, and warm-up periods, because CSI drift with board temperature has been reported. \[PAPER, low rigor\] ESPectre's dataset separates empty, static-presence and motion recordings and includes long quiet recordings scored in alarms per hour. \[SRC\]

**Environments and placements.** At least three rooms or link geometries, recorded on different days. SiFall's coverage dropped with distance and when a model moved rooms. \[PAPER-PC\] Record placement as metadata.

**Annotation.** Mark event start, impact and end on a synchronised timeline (SiFall used 30 fps video synchronised by NTP). \[PAPER-PC\] Derive window or phase labels from events, not the other way round. Keep the original receive timestamps in every file.

**Splits.** Group by subject, then by session and environment. Keep a sealed test set untouched until the end. Never split by window.

**Quality gates.** Missing rate, sampling coefficient of variation, minimum valid-slot fraction, temperature and RSSI per recording, with a documented rule for excluding bad recordings.

**Augmentation, training folds only.** SiFall used noise and time-shift augmentation to multiply its training data 24 times; ESPectre uses base, drift and burst-loss augmentation. \[PAPER-PC, SRC\] Augmentation does not replace subject diversity.

**Check your labelling.** Because phase-aware labelling gave weaker per-window results, count how many windows per fall are labelled positive and how the positive rate changes between labelling schemes. \[HYP\]

**Ethics and safety.** Informed consent, a safety mattress, and no claim of validation on real falls by older adults; SiFall lists the lack of such falls as a limitation. \[PAPER-PC\]

## 17. Implementation Roadmap

This roadmap describes later work. Nothing in it has been done.

| Priority | Phase | Experiment | Output and decision gate |
| --- | --- | --- | --- |
| 1 | 0 · Audit (offline, existing recordings) | **E0.1** Measure real inter-arrival distribution, missing rate and sampling coefficient of variation per recording. **E0.2** Convert 24/12 frames to elapsed seconds for each recording. | Is the effective rate stable? Does 24 frames equal a useful duration? |
| 2 | 0 | **E0.3** Re-score existing results with grouped splits and event-level metrics, including overlap reported. | A trustworthy baseline for the current SVM. |
| 3 | 0 | **E0.4** Stage A recall: for each annotated fall, does the motion signal exceed noise, and when? | If Stage A recall is poor, fix signal processing before any classifier work. |
| 4 | 1 · Offline experiments | **E1** Segment and window grid: pre in {1, 2, 3} s, post in {1, 2, 3} s, and sliding 3 s with 0.5 to 1 s hop. | Choose the segment definition by leave-one-subject-out event metrics. |
| 5 | 1 | **E2** Event-centered versus sliding classification with identical features and splits. | Confirms or rejects the central hypothesis. |
| 6 | 1 | **E3** Feature ablation: existing 16 features, gain-invariant scalars, burst-shape features, band energy ratios, post-event residual. | Smallest sufficient feature set. |
| 7 | 1 | **E4** Classifier ladder: rules, logistic or linear SVM, shallow trees, optional small 1D CNN. | Stop at the first rung that meets pre-agreed targets. |
| 8 | 1 | **E5** Decision logic: margin thresholds, UNCERTAIN, refractory period, confirmation time T, on long negatives. | Alarms per hour versus latency curve. |
| 9 | 1 | **E6** Preprocessing ablation: Hampel on or off and its threshold; `channel_filter_en` and `ltf_merge_en`; fixed versus selected subcarriers; first-order low-pass. | Effects on event recall. |
| 10 | 1 | **E7** Cross-session and cross-environment test with and without gain-invariant normalisation. | Quantifies drift sensitivity. |
| 11 | 2 · Firmware | **E8** Hardware-in-the-loop on ESP32-WROOM-32: sustained packet rate, CPU, free heap, stack high-water marks, end-to-end latency, packet loss, with the chosen pipeline running. Keep the existing C/Python parity gates. | Go or no-go for the architecture on this chip. |
| 12 | 3 · Pilot | Multi-day free-living recording with the device running, scored in alarms per hour and by a sealed fall test. | Release criteria. |

**Define targets before running anything.** Event recall, alarms per hour and latency targets are product decisions; I have not invented them.

**Most efficient path from where you are.**

1. Keep the C/Python parity and feature tooling you already have.
2. Run E0.1 to E0.4. These need no new hardware work and may explain the weak window-level and subject-holdout results.
3. Re-express windows in elapsed time and add an event-level evaluation harness.
4. Add the motion gate and the event decision layer around the existing classifier, and measure.
5. Only then change the classifier or features, guided by E1 to E5.

## 18. References and Evidence

Tags show how I used each source. URLs are the pages I retrieved.

**Official Espressif \[DOC\]**

- ESP-IDF Wi-Fi Vendor Features, CSI section: https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-guides/wifi-driver/wifi-vendor-features.html (S2 variant: https://docs.espressif.com/projects/esp-idf/en/latest/esp32s2/api-guides/wifi-driver/wifi-vendor-features.html; Chinese ESP32 page: https://docs.espressif.com/projects/esp-idf/zh\_CN/latest/esp32/api-guides/wifi-driver/wifi-vendor-features.html)
- esp-radar: https://components.espressif.com/components/espressif/esp-radar/versions/0.3.4/readme
- esp\_wifi\_sensing: https://components.espressif.com/components/espressif/esp\_wifi\_sensing/versions/0.1.1\~2/readme
- esp\_radar\_motion\_dec: https://components.espressif.com/components/espressif/esp\_radar\_motion\_dec/versions/0.1.1/readme
- esp-csi repository and issues: https://github.com/espressif/esp-csi and https://github.com/espressif/esp-csi/issues (titles only)
- ESP32-WROOM-32 datasheet v3.6: https://documentation.espressif.com/esp32-wroom-32\_datasheet\_en.html
- CSI configuration fields (mirrored in esp-radio docs): https://docs.espressif.com/projects/rust/esp-radio/1.0.0-beta.0/esp32c3/esp\_radio/wifi/csi/struct.CsiConfig.html

**Project documents I read directly \[SRC\]**

- ESPectre: https://github.com/francescopace/espectre . I read docs/ALGORITHMS.md, docs/CSI.md, docs/FEATURES.md (headings and decision summaries) and docs/performance/README.md from raw.githubusercontent.com. Not built or run.
- RuView pull request on callback load: https://github.com/ruvnet/RuView/pull/132

**Project READMEs and community pages \[README, FORUM\]**

- wisense: https://pypi.org/project/wisense/0.1.0/ · Landa: https://github.com/anneryeo/landa · swamphackxii: https://github.com/vinc3ntl1n/swamphackxii · wifi-csi-activity-fall-detection: https://github.com/BhuvanB1405/wifi-csi-activity-fall-detection · SG\_106B07: https://github.com/Ken35943/SG\_106B07
- WiFall dataset: https://huggingface.co/datasets/RS2002/WiFall · KNN-MMD code: https://github.com/RS2002/KNN-MMD
- esp-csi-rs statistics source: https://docs.rs/crate/esp-csi-rs/0.13.0/source/src/lib/stats.rs
- CSIght chip notes: https://github.com/joelewis012/CSIght/wiki
- esp32.com discussion on AGC: https://esp32.com/viewtopic.php?p=149973

**Fall-detection papers \[PAPER-PC unless noted\]**

- WiFall, IEEE TMC 2017: https://doi.org/10.1109/tmc.2016.2557792 · INFOCOM 2014: https://doi.org/10.1109/INFOCOM.2014.6847948
- Anti-Fall: https://arxiv.org/pdf/1507.01057
- RT-Fall (numbers as reported by later papers): https://www.arxiv.org/pdf/2005.11932 ; 3 s window described in patent text: https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10531817
- SiFall, SenSys 2022 (read in full): https://arxiv.org/pdf/2301.03773 , https://doi.org/10.1145/3560905.3568517
- KNN-MMD: https://arxiv.org/abs/2412.04783 · CSI-BERT2 (dataset description): https://arxiv.org/pdf/2412.06861
- Physics-driven transformer fall detection (snippet): https://arxiv.org/pdf/2605.00869
- ESP32 CSI fall detection preprint (snippet): https://arxiv.org/pdf/2611.15532
- ESP32 LSTM activity study: https://www.atlantis-press.com/article/126021002.pdf
- Thai symposium paper on ESP32-S3 falls: https://symposium2026.pcshstrg.ac.th/uploads/projects/83/paper\_pdf\_20260716\_162028.pdf

**Embedded and acquisition papers**

- Tools and Methods for Achieving Wi-Fi Sensing in Embedded Devices (Sensors 2025, \[PAPER-MCU\]): https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12526573/ (abstract-level; full page was blocked)
- STAR: https://arxiv.org/abs/2510.26148
- UniFi (irregular CSI sampling): https://arxiv.org/pdf/2512.22143
- ESPARGOS frame loss: https://arxiv.org/pdf/2502.09405
- CSI interpolation example: https://arxiv.org/pdf/2301.00269
- Cross-device CSI and AGC (snippet): https://arxiv.org/pdf/2605.26836

**Evaluation and leakage**

- Varga 2024: https://doi.org/10.3390/s24103159 and https://doi.org/10.3390/s24248201 · a further subject-independent reimplementation: https://www.mdpi.com/2624-6120/6/4/59
- Window-overlap leakage (sensor time series, snippet): https://arxiv.org/pdf/2609.09257
- FR3 leakage illustration (non-peer-reviewed): https://alhussni-aa.github.io/en/projects/fr3-sensing/

**Other modalities used only for analogy \[PAPER-MCU or accelerometer\]**

- CNN-LSTM on ESP32-S3 (accelerometer): https://ijtech.eng.ui.ac.id/download/article/8445
- 1D CNN on ESP32-S3 (insole IMU): https://www.imis.uni-luebeck.de/sites/default/files/2026-06/Schlonsak2025\_No\_Cloud\_No\_Problem.pdf
- FMCW radar fall detection with confidence interval: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC13667659/
- Streaming accelerometer evaluation with tolerance window: https://arxiv.org/pdf/2509.11789
- Wearable segmentation and window-size analysis (IEEE Sensors Journal record titled "An Analysis of Segmentation Approaches and Window Sizes in Wearable-Based Critical Fall Detection Systems With Machine Learning Models")

**Evidence quality summary.** Strong: ESP-IDF documentation, SiFall (read in full), ESPectre documentation (read directly). Moderate: WiFall, Anti-Fall and RT-Fall figures (abstract level or reported by other papers). Weak: student, hackathon and preprint-snippet material, which I used only to illustrate patterns.

## Final Answers to the Fifteen Questions

1. **Best overall architecture.** A gated, event-centered pipeline: quality-controlled, time-slot-admitted CSI → gain-invariant scalars → motion detector with state machine → pause-based event segmentation → small event classifier → event-level decision with refractory and confirmation. Offline: training and evaluation. *Confidence: medium. No ESP32-WROOM-32 fall evaluation exists to confirm it.*
2. **Separate motion detection and fall classification?** Yes. They fail for different reasons, and motion detection on classic ESP32 is already supported. *High.*
3. **Event segmentation before classification?** Yes, as the primary design, to be confirmed by experiment E2 against a sliding-window baseline. *Medium.*
4. **Preprocessing.** Remove hardware-error packets and invalid bins; admit by elapsed time; use amplitude only; compute gain-invariant per-packet scalars; Hampel on the scalars; calibrated baseline with slow recovery; spread-out fixed subcarriers. Skip Butterworth, wavelet and EMD at first. *Medium; no fall-specific preprocessing comparison exists.*
5. **Most useful features.** Event-level burst peak and energy, rise time, decay slope, duration, low-versus-high band energy ratios, post-event residual and stillness, pre-event motion level, plus scale-invariant statistics such as IQR/mean and autocorrelation. *Medium-low; needs ablation.*
6. **Best classifier balance.** Logistic regression or linear SVM on event features first, then a shallow tree ensemble, within a hybrid rule-plus-ML design. Deep models only if they are shown necessary and fit on-device. *Medium.*
7. **Window and stride to investigate first.** Event-centered segment with 2 s before and 1 s after the event end (3 s), with a grid of 1 to 3 s on each side; sliding 3 s windows with a 0.5 to 1 s hop as the baseline; a 0.25 to 1 s scale for the motion gate. Cut by elapsed time. *Medium.*
8. **Variable packet intervals.** Hardware receive timestamps, fixed time slots, at most one packet per slot, a minimum valid-slot fraction (ESPectre uses 70%), lagged features by real offsets, interpolation only for small gaps, windows discarded across long gaps, and missing rate and sampling coefficient of variation logged per recording. *High.*
9. **Ordinary movement versus falls.** An acceleration-style, high-frequency-burst gate that screens out walking, a classifier trained on hard negatives such as sit-to-floor, jump, squat and kneel, and post-event behaviour. Expect residual confusion with sit-to-floor and slow falls. *Medium-low.*
10. **False FALL at rest.** Gate classification behind a motion burst, train on long rest recordings, tune on alarms per hour, add a refractory period, handle drift, and allow an UNCERTAIN output. *High for the gating, medium for the rest.*
11. **Temporal decision strategy.** Three layers: raw classifier output, motion-gated margin-thresholded prediction with UNCERTAIN, and an event decision with merging, refractory period and a no-recovery confirmation window. Do not rely on state-style smoothing of overlapped windows as the fall decision. *Medium.*
12. **What runs where.** On the ESP32: acquisition, admission, scalars, motion state machine, segmentation, event features, the chosen small model, and the event decision. Offline: data management, grouped evaluation, feature and model selection, threshold selection, any deep or anomaly models, and export with parity tests. *Medium.*
13. **Essential dataset improvements.** More subjects with body-size and age spread, multiple environments, placements and days, a fall taxonomy, hard negatives, hours of rest recordings, event-level annotations with synchronised time, preserved timestamps, grouped splits and a sealed test set. *High.*
14. **Experiments required.** E0.1 to E0.4 (timing audit, window-in-seconds, grouped re-scoring, Stage A recall), then E1 to E7 offline and E8 on hardware. *High.*
15. **Most efficient path.** Audit timing and re-score existing results under grouped, event-level evaluation; re-express windows in elapsed time; wrap the existing classifier with a motion gate and event decision; measure; and change the classifier or features only if the measurements demand it. *High for the sequence, which is cheap and informative regardless of the outcome.*


Saya cek dulu langsung ke repositori agar jawabannya akurat, bukan dari ingatan.

Saya sedang memeriksa skrip training di repositori terakhir, lalu merangkum jawabannya.

Ya, ada pembahasan training yang cukup detail. Tapi dalam bentuk skrip Python dan dokumen, bukan notebook. Saya tidak menemukan satu pun file `.ipynb` di empat repositori yang saya periksa. Kali ini saya clone struktur repo dan membaca file-nya langsung, bukan hanya README.

**1. ESPectre (yang paling detail)**
- **Dokumen:** `docs/ML_TRAINING.md` dan `docs/ML_DATA_COLLECTION.md`. Training dijalankan lewat `python tools/train_ml_model.py` dengan PyTorch, scikit-learn, dan SHAP.
- **Peran data:** tiap rekaman diberi peran manual (`train`, `selection`, `holdout`, `exclude`). Rekaman diam yang panjang tidak pernah dipakai untuk melatih.
- **Validasi:** cross-validation berkelompok per "lineage", sehingga rekaman yang saling berkaitan tidak bocor antar fold.
- **Augmentasi:** jitter fitur, noise, paket hilang, perubahan laju paket (0,7–1,0 dengan batas bawah 70 pps), drift lambat, dan burst packet-loss. Augmentasi hanya dipakai untuk fitting.
- **Gerbang promosi:** model hanya diekspor ke firmware jika lolos replay, misalnya recall di atas 95% pada link normal, false positive mentah di bawah 5%, dan nol alarm pada rekaman kosong pendek.
- **Parity:** fitur dihitung persis seperti di perangkat. Mengubah fitur berarti memperbarui Python dan C++ bersamaan, lalu retrain.
- **Catatan jujur dari dokumennya:** early stopping memakai split acak 10% yang tidak mengukur generalisasi. Holdout-nya sudah pernah dilihat saat pengembangan, jadi hanya "regression set", bukan tes buta.
- **Batasan:** ini untuk deteksi gerak (IDLE vs MOTION), bukan jatuh. Metodologinya tetap layak ditiru.

**2. KNN-MMD / WiFall (RS2002)**
- File `train_fall.py`, `train.py`, `dataset.py`, `model.py`, dan contoh pemrosesan data di `WiFall/data_process_example/`.
- Hyperparameter default: batch 256, hidden 64, lr 0,001, 30 epoch.
- Pemisahan lintas orang lewat argumen `--test_list` (leave-person-out). Tugas cross-domain few-shot dengan jumlah shot `--k`.
- Data di Hugging Face, perangkat ESP32-S3. Cocok sebagai referensi, bukan untuk WROOM-32.

**3. SG_106B07 (ESP32-S3, CNN-LSTM)**
- `model/train.py`, `dataset.py`, `evaluate.py`, plus `scripts/preprocess.py` dan skrip pengumpulan data.
- Ada early stopping dan class weights. Split-nya per rekaman (`GroupShuffleSplit`) untuk menghindari kebocoran window. Kalau file grup tidak ada, kode jatuh ke split level window dengan peringatan.
- Itu pola yang tepat. Tapi per rekaman belum berarti per subjek, jadi tetap perlu dicek. Jumlah jatuh nyatanya sangat kecil (5).

**4. wifi-csi-activity-fall-detection (BhuvanB1405)**
- `train_classifier.py` melatih SVM RBF dan Random Forest dengan `train_test_split` acak 75/25. Ini rawan kebocoran, jadi angkanya jangan dipercaya sebagai performa lintas subjek.

**Untuk proyek Anda:** acuan terbaik adalah ESPectre, terutama aturan pembagian data, gerbang promosi, dan uji parity-nya. Anda sudah punya parity C/Python, jadi bagian itu paling mudah diadopsi. Jangan tiru contoh nomor 4.
