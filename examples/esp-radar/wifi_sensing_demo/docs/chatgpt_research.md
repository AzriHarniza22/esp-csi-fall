# **Deep Research Report: Wi-Fi CSI Fall Detection on ESP32-WROOM-32**

Research scope: ESP32-D0WD-V3 / ESP32-WROOM-32 · ESP-IDF 5.5.3 · real-time, single-device fall detection · evidence reviewed against November 15, 2026

## **1. Executive summary**

The strongest technical direction is a **quality-aware, multi-stage CSI processing pipeline combining motion/event segmentation, supervised fall classification, and event-level temporal verification**.

The central finding is that fall detection should not be treated as an ordinary binary classification problem operating continuously on arbitrary CSI windows. It is an event-detection problem involving three separate questions:

1. Is the CSI measurement sufficiently reliable to analyze?
2. Has a meaningful physical movement event occurred?
3. Does that event have the temporal and signal characteristics of a fall?

These questions should be evaluated separately. A system can achieve high window-level classification accuracy while producing unacceptable false alarms during long periods of inactivity.

There is also an important hardware distinction: the original ESP32-WROOM-32 does not provide the same CSI capabilities as newer ESP32-C5/C6 devices. Results from newer Espressif hardware, multi-antenna platforms, laptops, and PC-based machine-learning implementations cannot automatically be transferred to the target board.

**An initial hardware-supported fact:** Espressif documents that the ESP32 CSI reception callback executes in the Wi-Fi task, that received CSI memory is only valid during the callback, and that lengthy processing should be moved to another task using a queue. This makes acquisition and processing separation a fundamental architectural requirement, not merely a software-style preference.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.espressif.com\&sz=32)

— ESP-IDF Programming Guide v5.5.6 documentation+1



The recommendations below distinguish established evidence from promising but unverified engineering choices. In particular, I will not treat the current 16-feature Linear SVM as either optimal or inadequate without a properly controlled comparison.

## **2. Methodology, evidence hierarchy, and scope**

I used four evidence categories:

| Evidence class                        | What it can establish                                                      | What it cannot establish                                    |
| ------------------------------------- | -------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Official documentation and datasheets | Supported hardware/API behavior, memory limits, callback semantics         | Fall-detection accuracy                                     |
| Source-code inspection                | What an implementation actually computes, buffers, exports, and classifies | That it performs reliably in a new room or on unseen people |
| Academic experiments                  | Measured performance under the authors’ test protocol                      | Equivalent performance on ESP32-WROOM-32                    |
| Project and engineering measurements  | Behavior under the specific board, firmware, router, and dataset tested    | Generalization beyond those conditions                      |

The most important evidence is not necessarily the paper with the highest reported accuracy. It is evidence whose hardware, dataset split, labels, and evaluation protocol are close enough to the intended deployment to make its result transferable.

### **Evidence quality warning**

Fall-detection papers commonly report window-level accuracy or precision, while a deployed alarm system must detect an entire fall event and avoid alarming during hours of ordinary activity. These are different outcomes.

For example:

- WiFall reported 90% precision and a 15% false-alarm rate with a one-class SVM, or 94% precision and 13% false alarms with Random Forest. It used desktop PCs with commercial 802.11n NICs, not an ESP32.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://xplorestaging.ieee.org\&sz=32)

  IEEE Xplore+1

- RT-Fall reported higher sensitivity and specificity than WiFall, but its important phase-difference technique uses two antennas. Its results cannot be directly assigned to a single-antenna WROOM-32.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://researchportal.ip-paris.fr\&sz=32)

  researchportal.ip-paris.fr

- FallDar reported 5.7% false alarms and 3.4% missed alarms over six months of home and office experiments using commercial Wi-Fi devices. This is useful evidence for the importance of user diversity and long-term evaluation, but it is not an ESP32-WROOM benchmark.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://ieeexplore.ieee.org\&sz=32)

  IEEE Xplore+1



A more recent open-source experiment illustrates why event-level assessment matters. It used six subjects and two ESP32-S3 receivers, with model inference on a laptop. Its leave-one-subject-out experiment detected only 21 of 42 simulated falls after temporal calibration, with 8 of 109 look-alike takes producing an alarm, 30.3 walking alarms per hour, and a median alarm latency of 1.99 seconds. On a subsequent live session, the system did not alarm on the fall. The authors explicitly identify the one-room, one-layout, simulated-fall dataset and lack of video ground truth as limitations. This is not a WROOM-32 result; it is a useful warning that promising offline scores and a working demonstration do not establish dependable deployment.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+2



The report therefore prioritizes **event-level detection, false alarms per hour, unseen-subject testing, and actual target-board verification** over headline accuracy.

## **3. Official Espressif capabilities and limitations**

### **3.1 What the ESP32-WROOM-32 can actually provide**

The ESP32-WROOM-32 is based on the classic ESP32 architecture: dual-core Xtensa LX6 up to 240 MHz, 520 KB on-chip SRAM, 4 MB SPI flash on the standard module, 2.4 GHz 802.11b/g/n, and an onboard PCB antenna. The standard WROOM-32 module has no PSRAM specified. Espressif currently marks the original WROOM-32 as *Not Recommended for New Designs*; this is a lifecycle consideration, not evidence that an existing board is unsuitable for research.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://documentation.espressif.com\&sz=32)

documentation.espressif.com+1



| Capability                    | ESP32-WROOM-32 implication                                                                         |
| ----------------------------- | -------------------------------------------------------------------------------------------------- |
| Wi-Fi                         | 2.4 GHz 802.11b/g/n CSI reception                                                                  |
| Processing                    | Enough for lightweight signal processing and compact classical ML, subject to measurement          |
| SRAM                          | Constrained once Wi-Fi, FreeRTOS, queues, task stacks, and buffers are accounted for               |
| Flash                         | Suitable for firmware and compact model parameters; does not make a large model inexpensive to run |
| Antenna                       | Standard WROOM-32 uses one onboard PCB antenna                                                     |
| Multi-antenna phase diversity | Do not assume the two-antenna phase-difference method in RT-Fall is available                      |
| PSRAM                         | Not specified on the standard WROOM-32 module                                                      |

A single antenna does not mean that CSI is useless. It means that techniques relying on simultaneous phase differences between spatially separated antennas are not directly available. The system must extract useful temporal and frequency structure from the channel response measured by its one receive chain.

### **3.2 CSI format, LTFs, and valid subcarriers**

ESP-IDF 5.5.3 documents the following:

- CSI is returned as data associated with Long Training Fields (LTFs), ordered LLTF, HT-LTF, then STBC-HT-LTF when those fields are present.
- Each complex CSI value is stored as two bytes: **imaginary first, real second**.
- The received packet metadata is in `rx_ctrl`; it includes information such as RSSI, noise floor, receive time, channel, and antenna.
- `first_word_invalid` means the first four bytes of the CSI buffer are invalid because of an ESP32 hardware limitation. This is a per-record flag and must be handled according to its value.
- The documented occupied subcarrier counts vary by PHY/bandwidth: 802.11a/g has 52 total and 48 usable; 802.11n HT20 has 56 total and 52 usable; HT40 has 114 total and 108 usable.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://docs.espressif.com\&sz=32)

  — ESP-IDF Programming Guide v5.5.3 documentation+1



**Implication for the current 51-pair representation:** 51 I/Q pairs should be treated as the project's post-filtered layout, not as a universal ESP32 LLTF format. The exact mapping needs to be tied to the current capture configuration, the packet's PHY and bandwidth metadata, and the `first_word_invalid` handling. It is not safe to assume that every received CSI record has the same length or that 51 values always represent the same subcarrier indices.

In particular, avoid training against a feature layout that silently changes when the received PHY mode or LTF composition changes. The classifier's expected subcarrier count, firmware filtering, and training input must agree exactly.

### **3.3 LLTF versus HT-LTF**

For the WROOM-32, LLTF is a sensible primary signal because it gives a simpler, legacy-compatible representation and is already the basis of the current project. It is not proven to be the most informative LTF for falls.

| Choice             | Potential advantage                                     | Main risk                                                                 | Recommendation                                                     |
| ------------------ | ------------------------------------------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| LLTF               | Simpler and often more consistent packet representation | May contain less fine-grained information than an HT configuration        | Keep as the primary baseline                                       |
| HT-LTF             | Additional CSI structure when HT packets are received   | Depends on packet type, bandwidth, router behavior, and LTF configuration | Evaluate separately after LLTF is characterized                    |
| Merged LLTF/HT-LTF | Can combine information from multiple LTF components    | Changes signal composition and may complicate parity with trained data    | Avoid mixing configurations within one training/deployment profile |
| STBC-HT-LTF        | Additional field for STBC packets                       | Not guaranteed to appear on every packet                                  | Do not depend on it for the primary detector                       |

Espressif's own classic-ESP32 CSI receiver example enables LLTF, HT-LTF, and STBC-HT-LTF and uses LTF merging and channel filtering. That example demonstrates configurable acquisition; it does **not** establish that all three components are optimal for fall detection or that they should be mixed in a production classifier.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+1



**Recommendation:** retain a fixed LLTF-only configuration as the controlled baseline. Compare HT-LTF only as a separate experiment with its own metadata validation, feature mapping, training, and evaluation. Do not combine LLTF-only training takes with different LTF layouts unless the transformation is explicit and validated.

### **3.4 Callback behavior and acquisition architecture**

The ESP-IDF 5.5.3 guide explicitly states that the CSI receive callback runs in the Wi-Fi task. It warns against lengthy work in the callback and recommends placing necessary data in a queue for a lower-priority task. It also explains that a station receives packets from its AP when connected, and that promiscuous/sniffer mode can increase the available CSI packet stream.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.espressif.com\&sz=32)

— ESP-IDF Programming Guide v5.5.3 documentation



That leads to a clear architecture:

**Wi-Fi driver / CSI callback**

Validate minimal metadata · assign sequence and timestamp · copy CSI into bounded storage

**Bounded queue or ring buffer**

Track enqueue/dequeue counts, overflows, and packet gaps

**Signal-processing task**

Decode I/Q · quality checks · amplitude · filtering · time-aware windows · features

**Detection task**

Motion candidate · classifier · temporal/event state

Do not retain the callback's CSI buffer pointer for later use: its lifetime is tied to the callback. Copy the relevant buffer and metadata before returning. Avoid doing FFTs, model inference, large allocations, serial output, or blocking work in the callback. Track queue overflow and callback-to-processing latency rather than assuming the queue is lossless.

A further detail matters for the current project: the latest project-context artifact explicitly distinguishes CSI callback frequency, detector/FSM processing frequency, and GUI telemetry update frequency. A graph that updates slowly does not prove the CSI acquisition rate is slow, and a high CSI callback rate does not prove that every frame reached the classifier or FSM. These signals need their own counters and timestamps.&#x20;

PROJECT_CONTEXT_MOTION_INVESTIGATION.md



### **3.5 Packet rate is not a sampling clock**

The CSI callback is invoked when qualifying packets arrive. It is not a periodic timer that guarantees, for example, 100 CSI samples per second.

The receive metadata includes a local packet timestamp in microseconds. Older Espressif documentation specifies that its precision depends on modem sleep and light sleep being disabled; the timestamp is 32-bit, so long-running time arithmetic must handle wraparound. The official CSI receiver example logs this timestamp alongside channel, signal length, antenna, and other receive metadata.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+2



For this project:

- Preserve the receive timestamp and a monotonic software timestamp at callback entry.
- Assign a monotonically increasing packet sequence number.
- Calculate each inter-packet interval from timestamps; record its median, spread, upper percentiles, and largest gaps.
- Count rejected packets, queue drops, and packets with inconsistent CSI layouts.
- Reject or mark windows that contain long acquisition gaps rather than filling them with artificial zero-valued CSI.
- If filtering requires a regular sample grid, resample using real timestamps and only interpolate short gaps under a defined policy. A long gap should split or invalidate a window.

The key consequence is that **24 frames are not necessarily a fixed-duration window**. The current 24-frame/12-frame-stride configuration can be retained as a comparison baseline, but the research alternative should define windows and strides in elapsed time. The timestamps must decide which samples belong to the window.

### **3.6 Espressif's own sensing components**

Two Espressif components are relevant, although neither is a ready-made fall classifier:

- `esp_radar_motion_dec` supplies low-level CSI motion features. Its documented functions include waveform wander, which measures signal-vector stability, and waveform jitter, which measures motion intensity across a sliding history. The component supports the original ESP32 as well as newer targets.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://components.espressif.com\&sz=32)

  ESP Component Registry+1

- `esp_wifi_sensing` builds a motion/presence FSM around those features. It documents dynamic baseline tracking, smoothing, adaptive noise estimation, hysteresis, debounce, an active hold interval, on-site calibration, and router-ping-driven sampling. It supports ESP32 and requires ESP-IDF 5.4 or later.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://components.espressif.com\&sz=32)

  ESP Component Registry+2



These are useful engineering precedents for the motion-detection stage. However, neither component establishes that waveform jitter or wander can discriminate a fall from a fast sit, bend, kneel, jump, or intentional lie-down. They are motion/presence primitives—not fall classifiers.

**Important project-specific constraint:** the most recent project-context artifact says the active investigation is still about locating where physical movement first fails to appear strongly enough in the Motion path. It records prior CSI-to-FSM audits and a short diagnostic capture, but also identifies remaining evidence gaps around archive persistence, field completeness, timestamp correlation, and GUI mapping. This is a real prerequisite for evaluating a new fall classifier: the upstream motion representation must be understood before poor fall recall is attributed to the classifier.&#x20;

PROJECT_CONTEXT_MOTION_INVESTIGATION.md



## **4. Relevant GitHub implementations**

The source-code review reveals a useful distinction: some repositories demonstrate ESP32 CSI capture, some demonstrate fall-related ML on a PC, and some combine ESP32 boards with a PC-based classifier. Very few establish a validated, single-WROOM-32, fully on-device fall detector.

| Project                                                                                                                        | Hardware and execution path                                                                                 | What is useful                                                                                                                                                   | Evidence limitations                                                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Espressif / esp-csi](https://github.com/espressif/esp-csi?utm_source=chatgpt.com)                                             | Official ESP CSI examples; ESP32-family acquisition and host-side visualisation                             | Reference implementation for CSI callback, CSI configuration, metadata, and parsing                                                                              | Acquisition framework, not a fall-detection benchmark                                                                                                                                                                   |
| [Espressif / esp-radar](https://github.com/espressif/esp-radar?utm_source=chatgpt.com)                                         | Espressif CSI radar examples and motion features                                                            | Motion/presence processing reference and integration patterns                                                                                                    | Not proof of fall-versus-sit discrimination                                                                                                                                                                             |
| [farisnasser / wifisensing](https://github.com/farisnasser/wifisensing?utm_source=chatgpt.com)                                 | CSI captured with ESP32 modules; classification scripts run in Python                                       | Includes Logistic Regression, Decision Tree, Random Forest, SVM, CNN, and LSTM alternatives, plus segmentation utilities                                         | Repository has only a small amount of source history and no adequately documented external validation or WROOM on-device inference result                                                                               |
| [md-asaduzzaman-shahin / esp32_csi_sensing](https://github.com/md-asaduzzaman-shahin/esp32_csi_sensing?utm_source=chatgpt.com) | Two generic ESP32-WROOM-type boards: one transmitter and one receiver; Python application performs analysis | Relevant WROOM CSI acquisition and a practical dedicated-TX/CSI-RX arrangement                                                                                   | Its architecture is not a single sensing board; fall analysis and ML reside in a Python application. The README's “spike then flat-line” description is a hypothesis/signature, not an independently validated detector |
| [collabray / wisense](https://github.com/collabray/wisense?utm_source=chatgpt.com)                                             | Python Wi-Fi sensing library                                                                                | Useful modular examples of amplitude-variance motion detection, calibration, and simple sudden-change/after-stillness fall heuristics                            | Its tests are synthetic; it does not demonstrate real WROOM CSI fall detection                                                                                                                                          |
| [mohithgowdam7 / Major_Project](https://github.com/mohithgowdam7/Major_Project?utm_source=chatgpt.com)                         | One transmitter and two ESP32-S3 receivers; laptop-side training/inference                                  | Detailed, recent negative as well as positive evidence: subject-independent evaluation, event-level alarm chain, window-length comparison, and live-test caveats | Different hardware and multi-receiver topology; not transferable as direct WROOM performance                                                                                                                            |

The Faris Nasser repository is useful as a model-family survey, not as a deployment reference. Its README identifies ESP32-captured CSI and lists several classical and neural classifiers, but the public repository does not provide enough evidence to establish that its classifier generalizes to unseen subjects or runs on the ESP32.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+1



The WROOM-oriented `esp32_csi_sensing` repository is more relevant to RF acquisition. It explicitly uses two ESP32 development boards, a forced-HT transmitter and a CSI receiver, and runs the fall-analysis engine in a Python application. It extracts entropy, velocity, and MAD and describes a large jitter spike followed by a stable interval as a possible fall signature. This supports experimenting with transient-plus-aftermath features, but it does not establish that the pattern is unique to falls or that its classifier runs on a single WROOM.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+2



The most informative GitHub implementation for evaluating classifier complexity is the recent six-subject ESP32-S3 project. Its authors found that the best deep model performed worse than the better classical models on their small dataset. Their best five-class event macro-F1 was 0.572 for MiniRocket, while SVM-RBF achieved 0.539 and XGBoost 0.523. The best reported deep alternatives were around 0.33; the rest were lower. Crucially, these were laptop-side results on a two-receiver setup, not ESP32 inference.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+1



**GitHub conclusion:** use Espressif's code as the acquisition and motion-processing reference; use the WROOM projects to understand controlled CSI illumination and capture; use PC research pipelines to compare models offline. None of these repositories is sufficient evidence that a single ESP32-WROOM-32 already has a reliable end-to-end fall detector.

## **5. Academic literature review**

### **5.1 What established fall-detection research contributes**

| Study                                 | Main contribution                                                                                                         | Reported result                                                                                                                                                      | Transfer limitation                                                                                        |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| WiFall (2014; journal extension 2017) | CSI temporal/spatial variability; one-class SVM and Random Forest                                                         | 2014: 87% detection precision and 18% false-alarm rate. Journal extension: 90% precision/15% false alarms with one-class SVM; 94% precision/13% false alarms with RF | Commercial 802.11n NICs on desktop/laptop platforms; false-alarm levels remain substantial                 |
| RT-Fall (2017)                        | Two-antenna phase difference for segmentation; time-frequency power-profile decline                                       | 14 percentage points higher sensitivity and 10 points higher specificity than WiFall on average across four indoor scenarios                                         | Its two-antenna phase-difference feature is not directly available on standard single-antenna WROOM-32     |
| FallDar (2023)                        | Synthetic fall diversity and user-independent representation                                                              | 5.7% false-alarm rate and 3.4% missed-alarm rate in six months of home/office experiments                                                                            | Commercial Wi-Fi devices and a much longer evaluation than the current ESP32 dataset                       |
| DapFall (2025)                        | Dynamic Amplitude Probability Density (DAPD), retaining subcarrier mutual information while suppressing static components | 94.3% TPR and 6.25% FPR in its original environments; reported cross-environment robustness without retraining                                                       | Uses a 2+1D deep-learning model and an image-like representation; not a lightweight WROOM inference result |
| AmFall (2025)                         | Selective subcarriers/PCA, denoised CWT scalograms, speed-based segmentation, CNN classification                          | Reported 95.28–99.67% accuracy in through-the-wall and cross-domain settings                                                                                         | Commercial Wi-Fi CSI and a MATLAB/Colab CNN workflow, not ESP32-WROOM deployment                           |

Sources: WiFall's original and journal results; RT-Fall's two-antenna approach; FallDar's long-duration home/office study; and the DapFall and AmFall publications.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://ieeexplore.ieee.org\&sz=32)

IEEE Xplore+5



These studies provide several valuable design lessons:

1. **Fall segmentation is a first-class problem.** RT-Fall's key contribution was not merely choosing a better classifier; it identified a phase-based signal and a sharp time-frequency power decline pattern that helped separate falls from fall-like activity.
2. **Generalization is a major challenge.** FallDar explicitly addressed differences in fall style and users, and conducted a six-month home/office evaluation. Static channel fingerprints are not sufficient evidence of user-independent behavior.
3. **Subcarrier relationships can matter.** DapFall's central argument is that relationships among subcarriers carry useful activity characteristics and can be more robust than treating each amplitude stream independently.
4. **Time-frequency analysis is useful for transients.** AmFall uses continuous wavelet transforms to represent non-stationary fall signals. Its reported results are strong, but its representation and CNN should be considered an offline research benchmark rather than a default MCU pipeline.

### **5.2 Why the highest reported accuracy is not the target architecture**

DapFall and AmFall show that deep representations can be effective when the hardware, training corpus, and preprocessing pipeline support them. Neither proves that a similar network will outperform a small classical model on a WROOM-32.

The newer ESP32-S3 multi-receiver experiment provides a sobering counterexample: even with 4-second windows and a sizeable feature set, fall-window sensitivity remained limited, deep models overfit, and the calibrated event alarm missed half the simulated falls. The live follow-up was weaker than offline evaluation.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+1



That is why the recommendation is not to copy the most complex model from the literature. The objective is to recover enough fall-specific signal information with a model small enough to deploy, then verify it using a strict event-level protocol.

### **5.3 What the literature does not establish for this target**

The cited high-performance systems use different radio hardware, more spatial diversity, longer recording campaigns, PC/GPU processing, or some combination of these. Their percentages should not be presented as expected WROOM-32 accuracy.

I found no sufficiently documented public result proving that a **single ESP32-WROOM-32, one CSI receive chain, and fully on-device inference** achieves those literature-level event detection and false-alarm rates. That is an important research gap, not a reason to dismiss the platform.

# **15–18. Recommended architecture, project roadmap, and conclusions**

## **15. Recommended end-to-end architecture**

### **15.1 Primary recommendation**

Primary recommendation

Use a **quality-aware, amplitude-first, event-segmented pipeline with causal baseline-relative features, a compact linear fall classifier, and event-level temporal state management**.

The key is not to make the motion gate itself more complicated. It is to ensure that the system reliably captures movement, classifies the event using its temporal structure, and makes only one stable decision for that event.

```
                ESP32-WROOM-32
┌────────────────────────────────────────────────────┐
│ 1. CSI acquisition                                 │
│    • Target peer / packet validation               │
│    • LLTF configuration                            │
│    • Timestamp, sequence, metadata                 │
│    • Bounded queue; loss / gap counters            │
└──────────────────────────┬─────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────┐
│ 2. Signal-quality gate                              │
│    • CSI layout and packet validity                │
│    • Time-gap and consistency checks                │
│    • Quality = valid / degraded / unknown           │
└──────────────────────────┬─────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────┐
│ 3. Signal conditioning                              │
│    • I/Q → amplitude per subcarrier                │
│    • Lightweight causal noise treatment             │
│    • Time-aware signal history                      │
│    • Causal baseline-relative representation        │
└──────────────────────────┬─────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────┐
│ 4. Sensitive motion/event candidate detector        │
│    • Robust motion energy / MAD                     │
│    • Adaptive noise threshold                       │
│    • Hysteresis                                     │
│    • Pre-event and post-event buffer                │
│                                                    │
│    Motion detected ≠ fall detected                  │
└──────────────────────────┬─────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────┐
│ 5. Event feature extraction                         │
│    • Dynamic amplitude features                     │
│    • Band-wise motion features                      │
│    • Baseline-relative band features                │
│    • Transient and temporal-shape features          │
│    • Optional compact frequency features           │
└──────────────────────────┬─────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────┐
│ 6. Fall-event classifier                            │
│    • Regularized Logistic Regression                │
│      or Linear SVM                                  │
│    • Fall vs hard-negative event classification     │
│    • Confidence / reject region                     │
└──────────────────────────┬─────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────┐
│ 7. Temporal/event decision                          │
│    NORMAL → CANDIDATE → FALL CONFIRMED              │
│                    → LATCHED / RECOVERED             │
│    • Calibrated evidence threshold                  │
│    • Hysteresis and k-of-N comparator                │
│    • Duplicate event suppression                    │
│    • Baseline frozen during candidate/event         │
└──────────────────────────┬─────────────────────────┘
                           │
                           ▼
                  FALL / NON-FALL
```

The laptop should remain responsible for dataset management, feature experiments, model training, cross-validation, calibration, event-level analysis, and model export. The WROOM-32 should run only the selected compact signal-processing, classification, and event-decision pipeline.

### **15.2 Which features should be the main candidate?**

The strongest project-specific evidence supports testing **dynamic motion features plus causal baseline-relative features**.

| Feature configuration                          | Role in evaluation                               |
| ---------------------------------------------- | ------------------------------------------------ |
| Current 16-feature motion representation       | Existing baseline                                |
| 16 motion + 16 baseline-relative band features | Main experimental challenger                     |
| Compact subset of motion + relative features   | Embedded optimisation challenger                 |
| Absolute amplitude profile                     | Negative-control/ablation feature, not preferred |
| Phase-derived features                         | Separate experimental branch                     |
| Wavelet/scalogram representation               | Offline research comparison only                 |

In the earlier 89-take project analysis, the combination of motion and baseline-relative features performed better than motion-only on both the falling-transition and fallen-still comparison tasks. But the absolute profile appeared to encode session identity, and post-fall stillness did not independently identify the preceding event as a fall. This supports the combined feature representation as a **candidate**, not as an already proven cross-subject model.&#x20;

Pasted markdown(6).md



### **15.3 How the post-fall stage should be used**

The post-event state should help decide whether the detected episode remains unresolved or has recovered. It should **not independently generate a fall alarm** just because the person is now still or because their profile differs from the initial baseline.

The earlier project experiment found that fallen-still and normal-still could be separated better with baseline-relative features than with motion-only features, but a three-way classification that included other post-activity stillness remained much less reliable. This means post-fall state can help confirm *persistence of an event*, but the classifier must identify the fall from the transition itself.&#x20;

Pasted markdown(6).md



### **15.4 Simpler fallback architecture**

Fallback

If the richer pipeline proves too difficult to validate or too costly to run, use:

- LLTF amplitude only.
- Existing 16 dynamic features.
- Robust adaptive motion gate.
- Linear SVM or Logistic Regression.
- Time-defined sliding windows.
- Hysteresis and calibrated event-level voting.
- One-event/one-alarm latch.

This is less expressive because it omits the additional baseline-relative representation, but its software and model complexity are lower. It is a better fallback than replacing the existing model with a deep network before the dataset supports that change.

## **16. Dataset and training recommendations**

### **16.1 Essential dataset improvements**

The biggest constraint is not currently the number of algorithms available. It is the lack of independent people, recording sessions, environments, and well-annotated fall events.

The earlier project audit reported an 89-take dataset from one subject and one room, with missing subject-identification information. That dataset can support within-person exploratory analysis, but it cannot establish subject-independent generalization.&#x20;

Pasted markdown(6).md



The next dataset should include:

| Dimension             | Required variation                                                                       |
| --------------------- | ---------------------------------------------------------------------------------------- |
| Subjects              | Multiple independent participants; use anonymous consistent IDs                          |
| Sessions              | Different days and times                                                                 |
| Environments          | More than one room and layout                                                            |
| Link geometry         | Different body positions relative to the router–ESP32 path                               |
| Fall direction        | Forward, backward, left, and right                                                       |
| Fall dynamics         | Different descent speeds and controlled simulated falls                                  |
| Ordinary activity     | Walking, turning, sitting, standing, bending, kneeling, reaching                         |
| Hard negatives        | Intentional lying down, fast toilet sitting, dropping objects, jump, stumble-and-recover |
| Post-event behavior   | Remain down, move while down, get up, recover                                            |
| Environmental effects | Router activity, interference, furniture movement, and changes in the room               |
| RF metadata           | Channel, bandwidth, PHY mode, RSSI, noise floor, LTF layout, CSI length                  |
| Ground truth          | Event onset, impact, post-event, recovery timestamps                                     |

### **16.2 Hard negatives are particularly important**

The negative dataset should not consist mainly of an empty room or quiet standing.

Prioritize:

- Fast sitting and toilet sitting.
- Intentional lying down and getting up.
- Bending to pick up an object.
- Kneeling and crouching.
- Jumping.
- Sudden standing and turning.
- Stumbling without falling.
- Dropping an object.
- Moving furniture or slamming a door.
- Ordinary walking at different distances and directions.

These activities generate movement or transients but should not become fall alarms.

### **16.3 Ground-truth annotation**

Use synchronized video or a reliable independent reference to establish:

- Start of uncontrolled descent.
- Impact/landing.
- Beginning and end of post-fall stillness.
- Recovery or getting up.

Privacy-sensitive locations such as a bathroom require an appropriate, privacy-preserving test arrangement. For experimental work, video can be used locally for annotation without becoming an operational sensing input.

### **16.4 Dataset balance and labeling**

Do not try to solve class imbalance by manufacturing thousands of overlapping fall windows from a small number of physical falls. Those windows remain correlated observations of the same events.

Better practices:

- Keep all windows from one event in the same split.
- Cap excessive windows per take when training.
- Apply class weighting where appropriate.
- Preserve a separate, realistically imbalanced test set.
- Train using phase-aware labels.
- Retain stationary and hard-negative recordings.
- Keep ambiguous transition windows separate or exclude them from the primary binary classifier.

## **17. Prioritized experiment plan and implementation roadmap**

This is a research roadmap only. None of the following experiments were executed as part of this report.

The order is important: **do not compare fall classifiers before establishing that the upstream CSI signal and event representation are sufficiently reliable.**

| Priority | Experiment                        | Main question                                                                       | Comparison / acceptance evidence                                                  |
| -------- | --------------------------------- | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| 1        | Acquisition and runtime integrity | Does each valid CSI packet produce the intended downstream sample?                  | Sequence accounting, timestamps, packet gaps, rejected frames, queue losses       |
| 2        | Motion observability              | Does physical movement reliably appear in amplitude and motion features?            | CSI → amplitude → feature/jitter response across ordinary and fall-like movements |
| 3        | Event-label audit                 | Are windows labelled according to their actual physical phase?                      | Onset, impact, post-fall, recovery annotation and boundary handling               |
| 4        | Feature ablation                  | Does baseline-relative information generalize beyond the current motion features?   | 16 motion versus 16 motion + 16 relative, grouped splits                          |
| 5        | Time-aware windowing              | Which temporal scale captures an event without unacceptable latency?                | 1, 2, 3, and 4-second windows; 0.2–0.5-second time hops                           |
| 6        | Classifier comparison             | Is a linear classifier sufficient, or is a small nonlinear model materially better? | Logistic Regression, Linear SVM, shallow tree/forest, RBF SVM                     |
| 7        | Temporal decision study           | How much recall is lost for each false-alarm reduction?                             | Raw predictions versus hysteresis, k-of-N, and event state logic                  |
| 8        | Subject/session holdout           | Does the candidate generalize to unseen people and sessions?                        | Nested LOSO and held-out-session tests                                            |
| 9        | Environment holdout               | Does the system work outside the training room/layout?                              | Whole-environment holdout                                                         |
| 10       | WROOM runtime profiling           | Does the locked candidate run within hardware resources and latency targets?        | Timing, heap, stack, queue loss, and event detection on actual hardware           |

### **17.1 Highest-priority questions**

**First: verify the signal path, not just the classifier.**

The current project context identifies the Motion path as a separate investigation: physical movement may fail to appear in the raw CSI representation, in the derived jitter feature, at the FSM input, or only in the GUI output. It also records previous audits of this chain and identifies outstanding evidence questions around diagnostic-archive persistence, field completeness, and timestamp correlation.&#x20;

PROJECT_CONTEXT_MOTION_INVESTIGATION.md



There is another historical point to keep in view: an earlier project audit reported a mismatch between the classifier's expected LLTF input layout and the 51-pair device representation, causing frames to be skipped in that audited version. That is a **historical finding**, not proof that the latest firmware still has the defect. Given the current status—successful build and offline parity but no latest real-time hardware validation—the first runtime acceptance test must confirm that the current firmware actually invokes the intended classifier on valid live CSI frames.&#x20;

Pasted markdown(6).md



**Second: establish correct event labels.**

The model should be trained to recognize the fall transition, not the entire take containing a fall. This is a prerequisite for meaningful model comparisons.

**Third: run feature/window/model comparisons using identical grouped splits.**

If each feature set or classifier is tested on a different split, the comparison will be unreliable.

**Fourth: select the temporal decision only after examining raw classifier behavior.**

A stabilizer cannot repair missing signal information or a classifier that systematically confuses ordinary movements with falls. It can only make decisions over the evidence it receives.

### **17.2 Expected benefits and trade-offs**

| Recommendation                            | Expected benefit                                               | Main trade-off                                              | Confidence                                                 |
| ----------------------------------------- | -------------------------------------------------------------- | ----------------------------------------------------------- | ---------------------------------------------------------- |
| Timestamp-based windows                   | Correct duration and timing under variable packet rate         | Needs more complete time metadata and gap policy            | High                                                       |
| Lightweight amplitude-first preprocessing | Stable, simple embedded signal                                 | May omit useful phase information                           | High for feasibility; medium for discrimination            |
| Adaptive motion/event segmentation        | Reduces unnecessary classification and defines event context   | A strict gate can miss weak falls                           | Medium–high                                                |
| Baseline-relative features                | Reduces dependence on absolute channel amplitude               | Can absorb an event if baseline adapts too quickly          | Medium; supported by limited project data                  |
| Linear classifier                         | Small, predictable inference cost                              | May not model complex nonlinear boundaries                  | High for embedded feasibility                              |
| Shallow nonlinear challenger              | Tests whether feature interactions improve fall discrimination | More model complexity and overfitting risk                  | Medium                                                     |
| Event-level temporal state machine        | Suppresses repeated alarms and flicker                         | Can increase latency and miss short events                  | High for architecture; threshold tuning remains unverified |
| Subject/environment holdout               | Reveals real generalization failures                           | Requires more independent data                              | Very high                                                  |
| Quantized deep learning                   | Potentially learns richer representations                      | Requires stronger data and measured memory/inference budget | Low for present project                                    |

## **18. Final answers to the 15 research questions**

| #  | Question                                             | Direct answer                                                                                                                                                                                                                                          |
| -- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1  | Best overall architecture?                           | Quality-aware CSI acquisition → amplitude preprocessing → sensitive motion/event segmentation → time-aware event features → compact linear fall classifier → calibrated event-level state machine.                                                     |
| 2  | Separate motion detection and fall classification?   | **Yes.** Motion detection identifies a candidate event; the classifier determines whether it resembles a fall.                                                                                                                                         |
| 3  | Event segmentation before classification?            | **Yes, as a permissive candidate-generation stage.** Do not make it an inflexible gate that can suppress weak falls.                                                                                                                                   |
| 4  | Best preprocessing?                                  | Consistent CSI layout, per-packet validity checks, amplitude extraction, light causal outlier/noise handling, time-aware processing, and causal baseline-relative normalization.                                                                       |
| 5  | Most useful CSI features?                            | Dynamic amplitude variation, derivative/energy, transient shape, band energy, and baseline-relative subcarrier/band features. Phase is optional and must be sanitized and independently validated.                                                     |
| 6  | Best classifier balance?                             | Regularized Logistic Regression or Linear SVM. Retain a shallow tree/forest or RBF SVM as an offline challenger only if it improves grouped event-level results materially.                                                                            |
| 7  | Initial window and stride?                           | Compare 1, 2, 3, and 4-second windows with 0.2–0.5-second elapsed-time hops. Use a short motion-trigger window and a longer event-context window.                                                                                                      |
| 8  | Handle variable packet intervals?                    | Timestamp every packet; define windows by elapsed time; measure packet gaps; resample only where justified; mark windows invalid when gaps compromise temporal interpretation.                                                                         |
| 9  | Distinguish ordinary movement from falls?            | Learn the complete event transition and use hard negatives: fast sitting, bending, kneeling, intentional lying down, jumping, and stumble/recovery. A large jitter peak alone is insufficient.                                                         |
| 10 | Prevent false FALL at rest?                          | Use a motion candidate gate, stationary training examples, an uncertain/reject state, baseline freeze, and one-event/one-alarm latching.                                                                                                               |
| 11 | Best temporal strategy?                              | Separate raw score, stabilized window prediction, and event decision. Test calibrated thresholds with hysteresis and k-of-N, recognizing that overlapping windows are correlated.                                                                      |
| 12 | What runs on the ESP32?                              | CSI acquisition, quality checks, amplitude preprocessing, compact feature extraction, motion gating, linear inference, and event-state logic. Model training, cross-validation, tuning, and extensive analysis remain offline.                         |
| 13 | Essential dataset improvements?                      | Independent subjects, sessions, rooms, link positions, phase-aware labels, accurate onset/impact timestamps, long stationary negatives, and hard-negative activities.                                                                                  |
| 14 | Required experiments before selection?               | Verify acquisition/runtime integrity, validate motion observability, audit labels, compare features/windows/classifiers, evaluate event-level stabilization, then test subject/environment generalization and actual WROOM performance.                |
| 15 | Most efficient path from the current implementation? | Verify the current live data path first; then fix/confirm event labels; compare the current 16 features against baseline-relative extensions; run time-aware window/model ablations; calibrate event logic; finally profile and validate on the WROOM. |

## **19. Final recommendation**

### **Primary architecture**

**Amplitude-first, time-aware, quality-gated event detection with dynamic plus baseline-relative features, a regularized linear classifier, and event-level temporal verification.**

This is the strongest practical candidate because it:

- Respects the acquisition behavior of ESP32 CSI.
- Avoids depending on unavailable multi-antenna phase differences.
- Separates motion observability from fall discrimination.
- Uses features that are inexpensive to compute.
- Has relevant project-specific evidence for baseline-relative features.
- Keeps inference compatible with the WROOM-32's constrained SRAM.
- Makes false alarms and event latency explicit evaluation targets.

### **Simpler fallback**

**LLTF amplitude + existing 16 dynamic features + adaptive motion segmentation + Linear SVM/Logistic Regression + hysteresis and event latch.**

It has lower feature and baseline-management complexity. Retain it as the control system for every feature/model comparison.

### **What is not recommended now**

Do not prioritize CNN-LSTM, GRU, large TCN, large RBF SVM, or complex wavelet/scalogram pipelines before the dataset has enough independent falls, subjects, sessions, and environments. Do not treat post-event stillness, a high jitter peak, or a stabilized classifier output as proof of a fall.

### **Confidence summary**

- **High confidence:** CSI callback/queue requirements; packet-time variability; need for time-aware windows; separation of motion detection and fall classification; event-level evaluation; need for subject/session/environment-independent testing.
- **Medium confidence:** amplitude-first preprocessing; causal baseline-relative features; a linear model as the initial deployment classifier; multi-scale event segmentation.
- **Low confidence until tested:** exact filter type/cutoff, optimal window duration/stride, phase usefulness on the target WROOM, final motion thresholds, and the exact temporal confirmation rule.

**The most efficient next step is not to replace the current Linear SVM. It is to establish that the current live CSI path reliably captures physical movement, correct the event-level training/evaluation representation, and then run controlled feature and window ablations.** If the upstream signal does not preserve the fall transition, no classifier—linear or deep—can reliably recover the missing information.

## **20. Selected references**

**Official Espressif documentation**

1. [ESP-IDF v5.5.3 — Wi-Fi Driver and CSI documentation](https://docs.espressif.com/projects/esp-idf/en/v5.5.3/esp32/api-guides/wifi.html?utm_source=chatgpt.com).
2. [Espressif — esp-csi repository](https://github.com/espressif/esp-csi?utm_source=chatgpt.com).
3. [Espressif Component Registry — esp_radar_motion_dec](https://components.espressif.com/components/espressif/esp_radar_motion_dec?utm_source=chatgpt.com).
4. [Espressif Component Registry — esp_wifi_sensing](https://components.espressif.com/components/espressif/esp_wifi_sensing?utm_source=chatgpt.com).
5. [ESP32-WROOM-32 datasheet](https://documentation.espressif.com/esp32-wroom-32_datasheet_en.html?utm_source=chatgpt.com).

**Academic research**

6. Han et al., *WiFall: Device-Free Fall Detection by Wireless Networks*, IEEE INFOCOM 2014, DOI: 10.1109/INFOCOM.2014.6847948.
7. Wang et al., *RT-Fall: A Real-Time and Contactless Fall Detection System with Commodity WiFi Devices*, IEEE Transactions on Mobile Computing, 2017, DOI: 10.1109/TMC.2016.2557795.
8. Zheng et al., *Rethinking Fall Detection With Wi-Fi*, IEEE Transactions on Mobile Computing, 2023, DOI: 10.1109/TMC.2022.3188779.
9. Chen et al., *DapFall: Dynamic Amplitude Probability Density Profile-Based Wi-Fi CSI Sensing for Fall Detection*, IEEE Sensors Journal, 2025, DOI: 10.1109/JSEN.2025.3544552.
10. Kim et al., *AmFall: WiFi CSI Amplitude-Based Fall Detection Using Denoised Scalograms*, IEEE Internet of Things Journal, 2025, DOI: 10.1109/JIOT.2025.3585401.

**Open-source implementation evidence**

11. [Faris Nasser — ESP32 CSI fall-detection ML scripts](https://github.com/farisnasser/wifisensing?utm_source=chatgpt.com).
12. [ESP32 CSI sensing with transmitter/receiver boards](https://github.com/md-asaduzzaman-shahin/esp32_csi_sensing?utm_source=chatgpt.com).
13. [ESP32-S3 multi-receiver CSI HAR evaluation and fall-alarm report](https://github.com/mohithgowdam7/Major_Project?utm_source=chatgpt.com).
14. [AmFall preprocessing and CNN implementation](https://github.com/yk2019kim/AmFall?utm_source=chatgpt.com).

**Overall conclusion:** the best defensible solution for the target is not a direct port of a high-accuracy PC-based deep-learning paper. It is a carefully measured, timestamp-aware, event-based amplitude pipeline with lightweight features and a compact classifier. The current project is already close to the right class of embedded architecture; the remaining risk is whether the RF signal, labels, event segmentation, and subject-independent evaluation support a reliable fall decision in real conditions.

# **Riset: Bagaimana penelitian Wi-Fi CSI memperoleh dataset dan melatih model fall detection?**

Saya menemukan beberapa penelitian yang menjelaskan proses tersebut secara cukup rinci. Hal menariknya, cara memperoleh dataset antarpenelitian ternyata berbeda: ada yang merekam setiap aktivitas secara berulang, ada yang merekam aktivitas sehari-hari secara kontinu lalu menyisipkan kejadian jatuh, dan ada yang mengumpulkan CSI di lingkungan rumah nyata.

Untuk proyek ESP32-WROOM-32, perbedaan ini penting karena menentukan kualitas label, distribusi data training, dan kemampuan model mengenali subjek yang belum pernah dilihat.

Berikut hasil penelusuran sumber primer.

## **1. TCS-Fall (2024) — pengumpulan dataset dan training paling rinci**

Sangat direkomendasikan

**Paper:** *TCS-Fall: Cross-individual fall detection system based on channel state information and time-continuous stack method.*

[Baca paper lengkap (open access)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11151769/?utm_source=chatgpt.com) · [DOI](https://doi.org/10.1177/20552076241259047?utm_source=chatgpt.com)

Ini salah satu paper paling berguna untuk mempelajari bagaimana dataset fall detection disusun secara sistematis.

### **A. Bagaimana mereka memperoleh dataset?**

[Influence of the Antenna Orientation on WiFi-Based Fall Detection Systems | MDPI](https://images.openai.com/static-rsc-4/uo7VfEUE29QhOxeWyIm3nbbysf4wBVkyeKB_zhfVo3wlvXaJdVyf44wUMOADQYSWh6ZAUqIsitTIYrAaeriULDMgSzOKEwW8SvPpnREhq0RYzDwRGgJ7dU--5koyqxm76DZTZU1i4EqUnbR4Aqmnb7Xi8xEybYSk_WehMmtwZ-I?purpose=inline)

[mdpi.com](https://www.mdpi.com/1424-8220/21/15/5121?utm_source=chatgpt.com)

Mereka merekrut 20 relawan:

| Karakteristik | Jumlah      |
| ------------- | ----------- |
| Pria          | 10          |
| Wanita        | 10          |
| Usia          | 19–26 tahun |
| Tinggi        | 153–181 cm  |
| Berat         | 40–80 kg    |

Hardware menggunakan dua komputer dengan Intel 5300 NIC: satu transmitter dan satu receiver. Ini bukan ESP32.

Eksperimen dilakukan di sebuah ruangan yang dilengkapi dua kursi, meja, kasur keselamatan, buku, gelas, dan telepon.

Mereka mengumpulkan dua jenis data:

**1. SA (Single Action) — aktivitas terisolasi**

- 1.800 kejadian jatuh.
- 2.400 aktivitas yang berpotensi membingungkan classifier.
- Setiap rekaman berdurasi 8 detik.
- Setiap aktivitas diulang 30 kali.

**2. TCS (Time-Continuous Sampling) — aktivitas kontinu**

- Sekitar 36.000 detik rekaman.
- Setiap rekaman berdurasi 150 detik.
- 120 detik pertama berisi aktivitas sehari-hari.
- 30 detik terakhir berisi satu kejadian jatuh yang waktunya diacak.

Dengan demikian, mereka tidak hanya mengumpulkan contoh jatuh yang terisolasi, tetapi juga aktivitas normal yang panjang dengan kejadian jatuh di dalamnya.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://pmc.ncbi.nlm.nih.gov\&sz=32)

PMC+2



### **B. Bagaimana label dibuat?**

Peneliti mengidentifikasi subjek, jenis aktivitas, dan nomor pengulangan. Untuk rekaman kontinu, waktu jatuh juga dicatat.

Aplikasi pengumpulan berbasis PyQt menyediakan mekanisme anotasi melalui keyboard. Operator menekan tombol untuk mencatat jenis kejadian beserta waktunya. Data CSI dan event disimpan secara terpisah tetapi memiliki hubungan waktu.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://pmc.ncbi.nlm.nih.gov\&sz=32)

PMC+1



Ini menarik karena label bukan sekadar nama file untuk keseluruhan rekaman, melainkan juga dapat dikaitkan dengan posisi kejadian di dalam rekaman kontinu.

### **C. Bagaimana dataset diproses untuk training?**

Setiap sample distandarkan menjadi delapan detik, dengan 1.000 paket per detik:

\\[ 8 \times 1000 = 8000\text{ paket} \\]

Untuk data kontinu, digunakan sliding window 8 detik dengan stride 1 detik.

Peneliti menggunakan CSI amplitudo dari Intel 5300, kemudian membentuk fitur Grouped Coefficient of Variation (GCV) untuk CNN classifier.

Yang penting, pembagian train/test dilakukan berdasarkan **volunteer ID**, bukan secara acak berdasarkan sample.

Tiga konfigurasi evaluasinya:

| Mode | Subjek training | Subjek testing |
| ---- | --------------- | -------------- |
| 1    | 2               | 18             |
| 2    | 10              | 10             |
| 3    | 18              | 2              |

Semua sampel dari subjek yang sama dipertahankan dalam kelompok yang sama.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://pmc.ncbi.nlm.nih.gov\&sz=32)

PMC+2



### **D. Bagaimana hasil training?**

| Mode               | AUC   | NEWR  | CWR   |
| ------------------ | ----- | ----- | ----- |
| 2 subjek training  | 0,999 | 0,955 | 0,975 |
| 10 subjek training | 0,999 | 1,000 | 0,992 |
| 18 subjek training | 0,999 | 1,000 | 1,000 |

Mereka juga membandingkan beberapa pilihan preprocessing, termasuk Butterworth, Hampel, Gaussian, dan tanpa filter. Hasilnya menunjukkan bahwa filter yang berbeda dapat mengubah NEWR dan CWR meskipun AUC hampir sama.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://pmc.ncbi.nlm.nih.gov\&sz=32)

PMC



**Keterbatasan:** seluruh akuisisi menggunakan Intel 5300 dengan konfigurasi 3×3 MIMO. Dataset tidak tersedia sebagai unduhan publik langsung; paper menyebutkan bahwa data dapat diminta kepada corresponding author.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://pmc.ncbi.nlm.nih.gov\&sz=32)

PMC



**Pelajaran untuk proyek Anda:** format rekaman kontinu 150 detik dengan kejadian jatuh yang diberi timestamp adalah model pengumpulan data yang sangat layak dipelajari. Jangan hanya mengumpulkan rekaman 5 detik yang sudah diberi satu label.

## **2. Damodaran et al. (2020) — dataset dan training menggunakan SVM serta LSTM**

**Paper:** *Device free human activity and fall recognition using WiFi channel state information (CSI).*

[Baca paper lengkap (open access)](https://link.springer.com/article/10.1007/s42486-020-00027-1?utm_source=chatgpt.com).

### **A. Pengumpulan dataset**

Mereka mengumpulkan lima jenis aktivitas:

- Walking
- Standing up
- Sitting down
- Fall
- Empty

Setiap aktivitas dikumpulkan sebanyak 140 sampel.

Jadi, total awalnya 700 aktivitas.

Namun, yang menarik adalah mereka membedakan dua jenis kejadian setelah jatuh:

| Kejadian                       | Label       |
| ------------------------------ | ----------- |
| Jatuh dan tetap berbaring      | Fall        |
| Jatuh kemudian berdiri kembali | False Alarm |

Dari 140 aktivitas fall, 80 diberi label Fall dan 60 diberi label False Alarm.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://link.springer.com\&sz=32)

Springer Nature Link



### **B. Training yang digunakan**

Mereka menguji dua pendekatan.

**Pendekatan pertama: fitur statistik + Linear SVM**

Fitur meliputi:

- Mean
- Median
- Standard deviation
- IQR
- Central moments
- Skewness
- Kurtosis
- Power spectral density
- Center of energy

Classifier menggunakan One-vs-All Linear SVM dengan parameter \\(C=0.01\\).&#x20;

[image](https://www.google.com/s2/favicons?domain=https://link.springer.com\&sz=32)

Springer Nature Link



**Pendekatan kedua: LSTM**

Konfigurasi model:

- Input: 90 dimensi CSI amplitude.
- LSTM: 128 hidden units.
- Output: Softmax multi-class classifier.
- Framework: TensorFlow.

Pendekatan LSTM tidak memerlukan feature engineering statistik manual seperti pendekatan SVM.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://link.springer.com\&sz=32)

Springer Nature Link



Mereka kemudian menggunakan dua SVM secara berurutan: classifier aktivitas umum terlebih dahulu, kemudian classifier khusus fall untuk mengurangi false alarm.

**Pelajaran untuk proyek Anda:** membedakan Fall dengan False Alarm berdasarkan perilaku setelah jatuh merupakan pendekatan labeling yang menarik. Namun, ini bukan berarti semua kejadian jatuh yang diikuti bangkit harus dianggap bukan jatuh untuk sistem keselamatan; definisi target klinis dan produk harus ditentukan terlebih dahulu.

Keterbatasannya adalah eksperimen dilakukan dengan hardware Wi-Fi berbasis PC dan dataset hanya di satu ruangan.

Selain TCS-Fall dan Damodaran yang sudah dibahas, ada empat referensi lain yang sangat menarik. Khususnya, **FallAware menjelaskan bagaimana memperoleh data negatif dari lingkungan rumah nyata**, sedangkan **AmFall menyediakan notebook training dan dataset yang bisa dipelajari langsung**.

## **3. FallAware (2025) — pengumpulan data jangka panjang di rumah nyata**

Sangat penting untuk metodologi dataset

**Paper:** *FallAware: An Explainable Learning Approach to Robust Fall Detection With WiFi.*

[Paper IEEE](https://doi.org/10.1109/JSAS.2024.3520517?utm_source=chatgpt.com) · [Versi paper yang dapat dibaca](https://www.researchgate.net/publication/388348926_FallAware_An_Explainable_Learning_Approach_to_Robust_Fall_Detection_With_WiFi?utm_source=chatgpt.com)

FallAware menarik karena peneliti tidak hanya mengumpulkan aktivitas dari relawan yang diminta melakukan simulasi jatuh. Mereka juga mengumpulkan data dari lingkungan nyata dalam periode panjang.

### **A. Bagaimana dataset diperoleh?**

Mereka mengembangkan dataset melalui dua kelompok pengumpulan data.

**Kelompok pertama: simulated falls dan hard negatives**

Mengumpulkan rekaman jatuh dan aktivitas yang berpotensi menimbulkan false alarm, antara lain:

- Jatuh ke depan, belakang, dan samping.
- Jatuh ketika mencoba berdiri dari kursi.
- Jatuh ketika sedang berdiri.
- Duduk di sofa.
- Berlari kemudian berhenti.
- Pintu tertutup.
- Benda jatuh.
- Mengambil benda dari lantai.
- Berjalan keluar dari area jangkauan CSI.

Kejadian negatif ini dikumpulkan untuk mengajarkan model membedakan jatuh dari aktivitas lain yang menghasilkan perubahan CSI serupa.

**Kelompok kedua: naturalistic negative recordings**

Ini bagian yang paling menarik.

Mereka mengumpulkan CSI jangka panjang di rumah dan lingkungan lain, dengan konfigurasi motion-triggered recording:

- Menyimpan 15 detik sebelum pemicu gerakan.
- Menyimpan 60 detik sesudah pemicu.
- Rekaman ditinjau untuk menemukan false alarm.
- Mencakup perilaku sehari-hari orang berusia di atas 65 tahun.
- Pengumpulan berlangsung pada enam lingkungan selama total 21 bulan.

Dengan demikian, sistem memperoleh contoh negatif dari aktivitas nyata, bukan hanya dari aktivitas yang sengaja dipraktikkan relawan. Namun, ini bukan bukti validasi jatuh nyata pada lansia.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www.researchgate.net\&sz=32)

researchgate.net+1



### **B. Bagaimana training dilakukan?**

| Parameter         | Metode                                |
| ----------------- | ------------------------------------- |
| Framework         | PyTorch                               |
| Model             | CNN/recurrent-based architecture      |
| Optimizer         | Adam                                  |
| Learning rate     | 0.0005                                |
| Epoch maksimum    | 50                                    |
| Loss              | Class-weighted loss ketika diperlukan |
| Model selection   | Validation loss minimum               |
| Training hardware | PC dengan NVIDIA RTX 3080             |

Mereka juga menggunakan augmentasi:

1. Permutasi kombinasi antena pada konfigurasi 2×2 MIMO.
2. Pergeseran temporal untuk menghasilkan variasi posisi kejadian jatuh di dalam input.

Model menganalisis input sekitar delapan detik dan diperbarui setiap satu detik.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www.researchgate.net\&sz=32)

researchgate.net+1



Hasil yang dilaporkan mencakup sekitar 94,1% average detection rate pada lingkungan yang tidak digunakan dalam training. Dalam rumah dengan satu penghuni tanpa hewan peliharaan, mereka melaporkan rata-rata 4,2 false alerts per bulan.

**Batasan:** CSI diperoleh menggunakan NXP 88W8997, bukan ESP32-WROOM-32. Inference dijalankan pada komputer GPU. Dataset dan kode training lengkap tidak tersedia sebagai repository publik yang dapat saya verifikasi.

**Pelajaran:** memisahkan hard negatives dan naturalistic negatives merupakan strategi dataset yang sangat penting. Keduanya menguji jenis kegagalan yang berbeda.

## **4. CSI-Bench (NeurIPS 2025) — benchmark dengan proses akuisisi dan pengolahan data terstruktur**

Sumber metodologi dataset yang kuat

- [Official GitHub](https://github.com/guozhen-jenn-zhu/CSI-Bench-Real-WiFi-Sensing-Benchmark?utm_source=chatgpt.com)
- [Paper NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/file/f7c68372b3d39e8d7a093eb2edaaad87-Paper-Datasets_and_Benchmarks_Track.pdf?utm_source=chatgpt.com)

CSI-Bench adalah benchmark Wi-Fi sensing berskala besar, bukan khusus fall detection.

Secara keseluruhan, dataset mencakup lebih dari 461 jam CSI, 35 pengguna, 26 lingkungan, dan 16 jenis perangkat. Yang membuatnya relevan adalah terdapat task Fall Detection dan sebagian akuisisinya menggunakan ESP32-S3.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://proceedings.nips.cc\&sz=32)

proceedings.nips.cc+1



### **A. Bagaimana dataset fall dikumpulkan?**

[Собираем любительскую Wi-Fi Sensing лабораторию: от ESP32 до детектора падений за 9290 рублей / Хабр](https://images.openai.com/static-rsc-4/sDKxEdLbpluOOTl3C2W1OyBQlw5I9YU7trIlUJVLILqP5VCfAvl4mb4XoLjxbFGrsFGx5F3jgznphec1vBflz3KfXqxTKu0egr_ue9ZZs6wQ-kU-08AYkizHh-hOA1rU0jYNqUOJnlOEmQjXK511VHBlKHmDLrS_ZnETQKq7AIw?purpose=inline)

[habr.com](https://habr.com/ru/articles/940098/?utm_source=chatgpt.com)

| Komponen            | Keterangan                       |
| ------------------- | -------------------------------- |
| Partisipan          | 17 orang                         |
| Lingkungan          | 6 lokasi indoor                  |
| Aktivitas           | Walking, sitting, lying, falling |
| Variasi             | LoS, NLoS dan fan interference   |
| Durasi sesi         | Sekitar 1–5 menit                |
| Fall events         | 2.770                            |
| Non-fall activities | 3.930                            |
| Total               | 6.700 sampel                     |

Perangkat utama task fall detection adalah NXP 88W8997 2×2 pada 5,18 GHz. Sebagian kecil data diperoleh menggunakan ESP32-S3 pada 2,4 GHz.

Video tersinkronisasi digunakan sebagai acuan anotasi kejadian jatuh. Ini memungkinkan peneliti menghubungkan aktivitas yang terlihat pada video dengan CSI pada waktu yang sama.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://proceedings.nips.cc\&sz=32)

proceedings.nips.cc+2



### **B. Bagaimana data dipersiapkan untuk training?**

Alurnya cukup jelas:

```
CSI capture
    |
    v
Packet-level CSI records
    |
    v
Timestamp alignment
    |
    v
Activity annotation
    |
    v
5-second segmentation
    |
    v
Amplitude extraction
    |
    v
Normalization
    |
    v
Train / Validation / Test
```

Mereka menggunakan data amplitudo dan membuang phase karena distorsi fase antarperangkat.

Kemudian:

- Memakai segmen lima detik yang tidak saling overlap untuk task fall detection.
- Melakukan normalisasi amplitudo per sampel.
- Menyesuaikan jumlah subcarrier dengan padding atau clipping.
- Membagi data dengan rasio 70% training, 15% validation, dan 15% testing.
- Mempertahankan distribusi kelas dan lingkungan sesuai protokol benchmark.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://proceedings.nips.cc\&sz=32)

  proceedings.nips.cc+2



**Catatan evaluasi:** pembagian 70/15/15 ini tidak otomatis berarti leave-one-subject-out. Jangan menganggap seluruh hasil benchmark merupakan pengujian pada subjek yang sama sekali tidak terlihat ketika training.

### **C. Training configuration**

| Parameter      | Konfigurasi   |
| -------------- | ------------- |
| Framework      | PyTorch       |
| Optimizer      | AdamW         |
| Batch size     | 128           |
| Learning rate  | 0.001         |
| Weight decay   | 0.00001       |
| Warm-up        | 5 epoch       |
| Maksimum epoch | 100           |
| Early stopping | Patience 15   |
| Loss           | Cross Entropy |
| Random seeds   | 3             |

Model yang diuji mencakup MLP, BiLSTM, ResNet18, ViT, Transformer, dan beberapa model time-series lainnya.

Training dilakukan menggunakan GPU RTX 4090 atau NVIDIA A10G di AWS SageMaker, bukan ESP32.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://proceedings.nips.cc\&sz=32)

proceedings.nips.cc+2



**Pelajaran:** CSI-Bench memberikan contoh yang baik tentang bagaimana mengelola dataset multi-perangkat, menyinkronkan anotasi, dan menyediakan protokol perbandingan model.

## **5. WiFall + KNN-MMD — dataset yang direkam menggunakan ESP32-S3**

Paling dekat dengan platform ESP32

- [WiFall dataset](https://huggingface.co/datasets/RS2002/WiFall?utm_source=chatgpt.com)
- [Training source code](https://github.com/RS2002/KNN-MMD?utm_source=chatgpt.com)
- [Paper KNN-MMD](https://arxiv.org/abs/2412.04783?utm_source=chatgpt.com)

Ini sangat layak dipelajari karena CSI direkam menggunakan ESP32-S3, walaupun bukan WROOM-32.

### **A. Bagaimana dataset dikumpulkan?**

Dataset mencakup sepuluh subjek dengan aktivitas:

- Fall
- Jump
- Sit
- Stand
- Walk

Karakteristik data yang didokumentasikan:

| Parameter             | Nilai          |
| --------------------- | -------------- |
| Receiver              | ESP32-S3       |
| Frekuensi             | 2,4 GHz        |
| Bandwidth             | 20 MHz         |
| Antena                | 1              |
| Subcarrier            | 52             |
| Sampling rate target  | Sekitar 100 Hz |
| Durasi setiap rekaman | 60 detik       |

Setiap file CSV memuat informasi timestamp dan CSI. Data dipisahkan berdasarkan subjek dan jenis aktivitas.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://arxiv.org\&sz=32)

arXiv+2



### **B. Bagaimana training dilakukan?**

Ini bukan training konvensional dengan hanya melatih sebuah CNN dan menguji pada random split.

KNN-MMD menggunakan:

1. ResNet18 sebagai feature extractor.
2. KNN untuk membentuk support set dari target domain.
3. Maximum Mean Discrepancy (MMD) untuk menyelaraskan distribusi source dan target.
4. Few-shot learning untuk membantu generalisasi terhadap domain yang berbeda.

Beberapa parameter yang terdapat dalam `train_fall.py`:

| Parameter        | Nilai default |
| ---------------- | ------------- |
| Batch size       | 256           |
| Hidden dimension | 64            |
| Learning rate    | 0.001         |
| Epoch            | 30            |
| K-shot           | 5             |

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+1

**Apa manfaatnya untuk proyek Anda?**

Penelitian ini menarik untuk memahami masalah ketika model dilatih pada satu kondisi ruangan, lalu digunakan di ruangan lain.

Tetapi ResNet18 dan mekanisme domain adaptation-nya merupakan pipeline PC, bukan classifier ringan yang sudah terbukti berjalan pada WROOM.

Satu keterbatasan lain: dataset hanya terdiri dari sepuluh subjek, sehingga hasil generalisasinya perlu dibaca dengan mempertimbangkan ukuran cohort tersebut.

## **6. AmFall (2025) — proyek dengan notebook training dan dataset publik**

Rekomendasi untuk mempelajari notebook

**Paper:** *AmFall: WiFi CSI Amplitude-Based Fall Detection Using Denoised Scalograms.*

- [Repository AmFall](https://github.com/yk2019kim/AmFall?utm_source=chatgpt.com)
- [Notebook training](https://github.com/yk2019kim/AmFall/blob/main/AmFall_Colab_Github.ipynb?utm_source=chatgpt.com)
- [Dataset Google Drive](https://drive.google.com/drive/folders/1I8ooo6GJj-PWMX3htHeVnYhV5U9EoRf-?usp=sharing\&utm_source=chatgpt.com)

Ini salah satu proyek yang secara eksplisit menyediakan notebook Google Colab.

### **A. Bagaimana dataset disusun?**

README menyediakan struktur direktori:

```
CSI-dir/
├── Environment-1/
│   ├── User-1/
│   │   ├── fall/
│   │   └── nonfall/
│   └── User-2/
│       ├── fall/
│       └── nonfall/
└── Environment-2/
    ├── User-1/
    └── User-2/
```

File asli disimpan dalam format `.log` dari Linux 802.11n CSI Tool.

Dengan begitu, dataset mempertahankan identitas lingkungan, subjek, dan kelas aktivitas.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+2



### **B. Bagaimana training dilakukan?**

Pipeline yang didokumentasikan:

```
Raw CSI .log
     |
     v
MATLAB preprocessing
     |
     v
CSI amplitude extraction
     |
     v
Subcarrier selection
     |
     v
Denoising
     |
     v
Continuous Wavelet Transform
     |
     v
Scalogram images
     |
     v
Google Colab notebook
     |
     v
CNN classification
```

Notebook menguji beberapa arsitektur:

- CNN_SNU1, model CNN ringan.
- ResNet18.
- ResNet34.

Kode MATLAB yang tersedia memperlihatkan penggunaan Continuous Wavelet Transform, pemilihan subcarrier, denoising, dan segmentasi empat detik.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+3



Satu keterbatasan verifikasi: file notebook memang tersedia di repository, tetapi saya belum berhasil membaca seluruh isi sel notebook secara langsung. Jadi, detail training di atas mengikuti dokumentasi repository, bukan audit lengkap terhadap setiap sel.

AmFall menggunakan format CSI dari platform Linux CSI Tool, bukan ESP32 CSI. Scalogram dan CNN-nya juga bukan jalur yang langsung cocok untuk inference di WROOM-32.

## **7. SiFall — training tanpa harus menjadikan FALL sebagai kelas positif**

Ada perbedaan mendasar antara SiFall dan paper-paper sebelumnya.

[SiFall, ACM SenSys 2022](https://dl.acm.org/doi/10.1145/3560905.3568517?utm_source=chatgpt.com) · [Full paper PDF](https://arxiv.org/pdf/2301.03773?utm_source=chatgpt.com)

SiFall menggunakan Variational Autoencoder (VAE).

### **Bagaimana training-nya?**

```
Normal activities
       |
       v
CSI processing
       |
       v
Fall-like event segmentation
       |
       v
STFT segments
       |
       v
Noise / time-shift augmentation
       |
       v
VAE training
       |
       v
Reconstruction error
       |
       v
Anomaly detection
```

Mereka menggunakan 1.447 segmen STFT aktivitas normal, kemudian augmentasi hingga 34.728 sampel. VAE belajar merekonstruksi aktivitas normal.

Ketika terjadi aktivitas yang berbeda secara signifikan dari distribusi normal, reconstruction error meningkat dan kejadian tersebut dapat dianggap sebagai anomali.

Training menggunakan Adam, dengan GPU NVIDIA RTX 2080 Ti. Ini bukan model yang dilatih dan dijalankan pada ESP32.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://wands.hk\&sz=32)

wands.hk+2



**Pelajaran:** ada alternatif selain supervised FALL/NO-FALL classification. Namun, anomaly detection masih harus diuji terhadap aktivitas normal yang sangat bervariasi, terutama duduk di lantai, berbaring, melompat, dan menjatuhkan benda.

## **8. Perbandingan: bagaimana setiap penelitian memperoleh dataset dan melakukan training?**

Berikut ringkasan seluruh penelitian yang telah dibahas.

| Penelitian     | Cara mendapatkan data                                          | Metode training                        | Akses dataset/kode        |
| -------------- | -------------------------------------------------------------- | -------------------------------------- | ------------------------- |
| TCS-Fall       | 20 relawan, aktivitas berulang + continuous recording          | CNN, GCV, subject-based folds          | Dataset dan kode tersedia |
| Damodaran 2020 | Aktivitas terisolasi, 140 sampel per kelas                     | SVM dan LSTM                           | Paper                     |
| FallAware      | Simulated falls + naturalistic negatives selama berbulan-bulan | CNN/recurrent model, augmentation      | Paper                     |
| CSI-Bench      | Pengumpulan CSI multi-user, multi-device, multi-environment    | Benchmark berbagai deep learning model | Paper, kode, dataset      |
| WiFall         | Rekaman 10 subjek menggunakan ESP32-S3                         | ResNet18 + KNN-MMD                     | Dataset dan kode          |
| AmFall         | Raw CSI `.log`, terpisah berdasarkan lingkungan dan pengguna   | Scalogram + CNN                        | Notebook dan dataset      |
| SiFall         | Aktivitas normal berulang + aktivitas fall-like                | VAE anomaly detection                  | Paper                     |

## **9. Pola pengumpulan data yang paling sering digunakan**

Dari sumber-sumber tersebut, terdapat empat pola utama.

[The real experiments configuration: (a) an adult sitting on a chair,... | Download Scientific Diagram](https://images.openai.com/static-rsc-4/PlLGvwvTtRxdB-WRYqPZQmwxGKb1lHGIGq2tTmzdr8GwizL_OQ_JhwCqhmHtvXpuRBxT4aqc9c1Ud7w_Jas7qZJfCnnqy221N700Fuetem1WkkK3CopT27nMtcr0Euvw_UMUC0oDkUNOTh-rGb_4XKGirynK5xu1sGPcBmhP6cU?purpose=inline)

**A. Scripted activity collection**

Relawan diminta melakukan aktivitas tertentu berkali-kali. Contohnya TCS-Fall dan Damodaran.

Kelebihan: label jelas dan mudah menghitung jumlah pengulangan.

Kekurangan: perilaku mungkin terlalu terkontrol.

[Frontiers | Radio frequency sensing and its innovative applications in diverse sectors: A comprehensive study](https://images.openai.com/static-rsc-4/uGQSYoegyMZm5LrzIDeJ-7m3GpJOziJJKsgfxTJRuRfRWY8-oBiDNwnJk1cHsTMytnrjYJNwNN3cJ6-w91y7kIt_HkTlmAlpMjGE3YXUIqTAWSIp2gpHA1iYaICXLLoJ1TmtwhvKt_AkJIsIQY5jnERBS_g_PPfVVE_cZNi-cBU?purpose=inline)

**B. Continuous activity collection**

Relawan melakukan aktivitas normal dan kejadian jatuh dimasukkan pada waktu tertentu. Contohnya TCS-Fall.

Kelebihan: menguji model dalam konteks gerakan sehari-hari.

[Wi-Gitation: Replica Wi-Fi CSI Dataset for Physical Agitation Activity Recognition](https://images.openai.com/static-rsc-4/hZHGYmQx6eOR3D60xruhU-Yh79mulPovTZxETzc279dYNkG38hySrxmp_omEeuRiONcqHqjfO1_f55-RN89Ty0iZZsqtRQ7B9d2iFntb1uhW3BAI5J5JEiAxlAgMH6xgUQKf6px1rWpSuSoCF55PuDjSm8AiGdbgr4JGRoxxCr4?purpose=inline)

**C. Long-term naturalistic collection**

Data dikumpulkan berhari-hari atau berbulan-bulan di rumah nyata. Contohnya FallAware.

Kelebihan: mendapatkan hard negatives dan false alarms yang lebih realistis.

[Wifi CSI | PDF](https://images.openai.com/static-rsc-4/FW4DwpJ5zPu3wLDgrKc7zXSqdwYVFPWzGrxk5w7dKETrtRRTv5GXmtrd2Yp0csqJXAhLFBwPoqgUhIwettmW33xk0E4GLbjNn0wUQ68TTrhXdsbvi-tJY1mnq7k7P0DquZqK5GbJm9gGXjLgKZRSiKKtyktv4GP_U3XJk14-oxE?purpose=inline)

**D. Public device-specific datasets**

Dataset yang diperoleh menggunakan perangkat tertentu dan dibagikan ke peneliti lain. Contohnya WiFall dan CSI-Bench.

Kelebihan: memungkinkan perbandingan dan replikasi.

## **10. Mana yang paling relevan untuk proyek WROOM-32?**

Penilaian saya berdasarkan tujuan penelitian Anda:

| Prioritas | Referensi | Apa yang perlu dipelajari                                      |
| --------- | --------- | -------------------------------------------------------------- |
| 1         | TCS-Fall  | Continuous recording, timestamp labeling, subject splits       |
| 2         | FallAware | Hard negatives dan long-term false-alarm dataset               |
| 3         | WiFall    | Pengumpulan CSI menggunakan ESP32-S3 dan cross-domain training |
| 4         | ESPectre  | Kualitas dataset motion dan training-to-firmware               |
| 5         | CSI-Bench | Standardisasi data, metadata, dan benchmark                    |
| 6         | AmFall    | Struktur notebook training dan preprocessing                   |
| 7         | SiFall    | Anomaly detection dan normal-only training                     |

## **11. Rekomendasi desain dataset untuk penelitian Anda**

Berdasarkan metodologi penelitian tersebut, saya menyarankan dataset proyek Anda memiliki dua jenis pengumpulan yang berbeda.

**Dataset A — Controlled event collection**

Rekam aktivitas dalam take yang terstruktur: forward/backward/left/right fall, walking, sitting, bending, squat, jump, sit-to-floor, dan kegiatan negatif lainnya.

Simpan:

- `subject_id`
- `session_id`
- `take_id`
- `activity_label`
- `event_start_timestamp`
- `impact_timestamp`
- `event_end_timestamp`
- `environment_id`
- `device_position`
- CSI RX timestamp dan amplitudo mentah.

**Dataset B — Continuous negative collection**

Rekam kondisi ruangan kosong, orang duduk, berbaring, bergerak biasa, dan aktivitas sehari-hari dalam sesi kontinu yang lebih panjang.

Data ini penting untuk menghitung false alarms per hour. Jangan hanya mengandalkan jumlah window negatif dalam dataset tersegmentasi.

**Training dan validasi:**

1. Pisahkan subject/session sebelum membuat window.
2. Gunakan training dan validation untuk memilih model.
3. Simpan test set yang benar-benar tidak disentuh selama pengembangan.
4. Uji event-level recall, false alarms/hour dan detection latency.
5. Pastikan fitur Python sama dengan fitur C di WROOM-32.

Ini menggabungkan praktik TCS-Fall, FallAware, dan CSI-Bench tanpa mengasumsikan hardware mereka setara dengan ESP32-WROOM-32.

## **Kesimpulan**

Ada tiga referensi yang menurut saya paling penting untuk dibaca lebih lanjut:

- **TCS-Fall:** paling jelas untuk memahami bagaimana membuat dataset jatuh yang memiliki aktivitas terisolasi sekaligus rekaman kontinu.
- **FallAware:** paling menarik untuk mempelajari bagaimana mengumpulkan data negatif jangka panjang agar false alarm turun.
- **WiFall:** paling relevan untuk mempelajari pengumpulan CSI dengan keluarga perangkat ESP32, meskipun menggunakan ESP32-S3.

Untuk notebook training, **AmFall** merupakan referensi praktis yang menarik. Untuk code training dan evaluasi yang bisa diperiksa, **TCS-Fall dan KNN-MMD** lebih cocok.

Satu kesimpulan penting dari seluruh penelitian ini: model yang bagus bukan hanya hasil dari pemilihan algoritma. Kualitas dataset, metode anotasi kejadian, pemisahan subjek, variasi aktivitas negatif, dan evaluasi jangka panjang sering kali sama pentingnya dengan arsitektur classifier.