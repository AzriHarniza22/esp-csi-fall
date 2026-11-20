## **1. Executive summary**

The strongest finding from this review is that **dataset construction and validation protocol can matter more than the choice between SVM, Random Forest, CNN, or LSTM**.

Wi-Fi CSI fall-detection research does not follow one universal recording format. At least four distinct strategies appear in the primary literature:

1. **Continuous mixed-activity recording:** one long recording contains ordinary activities, fall-like actions, and real falls. The system must identify the event boundaries within the stream. RT-Fall and Anti-Fall use this general approach.
2. **Repeated single-activity recording:** a raw file contains repeated instances of the same activity; researchers extract individual activity segments afterward. Chu et al. (2023) use this approach.
3. **Fixed-duration activity takes:** each capture is a defined action trial, often with stationary context before or after it. FallDeFi and the StanWiFi dataset are examples.
4. **Hybrid single-action and continuous datasets:** both isolated actions and continuous sequences are retained to train and test separate detection capabilities. TCS-Fall (2024) is a particularly useful example.

These strategies create different training samples, labeling requirements, and leakage risks. A paper's reported “dataset size” may mean original recordings, physical events, extracted segments, overlapping windows, or augmented images. These quantities must not be treated as interchangeable.

### **Most important findings**

- **One file does not necessarily equal one activity.** RT-Fall uses continuous mixed-activity streams; Chu uses 1–2-minute files containing repetitions of one activity and then extracts individual 5-second segments.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://shengjieli-pku.github.io\&sz=32)

  shengjieli-pku.github.io+1

- **A training window is not automatically a physical event.** A 5-second window can contain only the fall transition, or it can contain pre-fall, transition, impact, and post-fall periods. Those are not equivalent labels.

- **Video-based timing is among the strongest annotation practices.** Chu et al. correlate CSI timestamps with a GoPro video timestamp overlay to select 5-second activity segments. RT-Fall and Anti-Fall use room video and human observation, although their exact frame-by-frame annotation procedures are not fully specified.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://eprints.whiterose.ac.uk\&sz=32)

  eprints.whiterose.ac.uk+2

- **Window overlap can create serious leakage.** TCS-Fall uses 8-second windows with a 1-second stride, equivalent to 87.5% overlap, but avoids subject leakage by assigning all data from each volunteer to one partition.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://journals.sagepub.com\&sz=32)

  journals.sagepub.com+1

- **Random window splitting is not evidence of subject-independent performance.** A 2024 critical analysis demonstrated that a CSI-HAR study's reported 99.9% precision was inflated by mixing subjects across training and test sets. A 2025 follow-up analysis reported that improper partitioning overestimated F1 by approximately 32% in its examined case.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://www.mdpi.com\&sz=32)

  mdpi.com+1

- **Raw CSI and handcrafted features serve different research objectives.** Classical SVM studies often reduce CSI into statistical, temporal, or frequency features. CNN/LSTM studies commonly retain temporal sequences or convert CSI into image-like representations. A large tensor is not automatically a better training sample.

- **The project’s current take-level labeling issue is directly relevant.** Its previous audit found that labeling every window from a `fall` take as `FALL` incorrectly labels stationary and post-fall windows. In that dataset, some of those windows are not part of the fall transition at all.&#x20;

  Pasted markdown(6).md



The practical implication is that the next meaningful improvement should start with a well-defined recording and annotation protocol, not with a more complex classifier.

## **2. Literature selection and evidence quality**

I included more than 12 original fall-detection or CSI-HAR studies, with additional studies specifically examining dataset leakage. The literature spans 2014–2025, including the papers explicitly requested.

The evidence labels used below are:

| Label              | Meaning                                                                                 |
| ------------------ | --------------------------------------------------------------------------------------- |
| **Reported**       | Explicitly stated in the paper or its supplementary source                              |
| **Derived**        | Calculated directly from reported parameters, such as overlap percentage or tensor size |
| **NOT REPORTED**   | The paper does not describe the requested detail in the accessible methodology          |
| **UNKNOWN**        | Available material does not permit a reliable conclusion                                |
| **Interpretation** | Methodological implication inferred from the reported procedure                         |

A distinction is also made between the primary research artifact and the way it is accessed. For example, the original FallDeFi work is a doctoral dissertation, not a peer-reviewed journal article. The IntechOpen 2025 study is an original book chapter. Both are useful technical evidence but should not be presented as equivalent publication types.

### **Selected primary literature**

| Study                                                           | Year | Publication / DOI                                                                                                                      | Evidence available                                                   |
| --------------------------------------------------------------- | ---- | -------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| WiFall — Han et al.                                             | 2014 | IEEE INFOCOM, [10.1109/INFOCOM.2014.6847948](https://doi.org/10.1109/INFOCOM.2014.6847948?utm_source=chatgpt.com)                      | Original IEEE record and methodological comparisons                  |
| Anti-Fall — Zhang et al.                                        | 2015 | ICOST, [10.1007/978-3-319-19312-0_15](https://doi.org/10.1007/978-3-319-19312-0_15?utm_source=chatgpt.com)                             | Full paper                                                           |
| RT-Fall — Wang et al.                                           | 2017 | IEEE TMC, [10.1109/TMC.2016.2557795](https://doi.org/10.1109/TMC.2016.2557795?utm_source=chatgpt.com)                                  | Full paper                                                           |
| FallDeFi — Palipana                                             | 2019 | PhD dissertation, Cork Institute of Technology                                                                                         | Full dissertation                                                    |
| Damodaran et al.                                                | 2020 | [10.1007/s42486-020-00027-1](https://doi.org/10.1007/s42486-020-00027-1?utm_source=chatgpt.com)                                        | Full article                                                         |
| Nakamura et al.                                                 | 2022 | IEEE IoT Journal, [10.1109/JIOT.2022.3152315](https://doi.org/10.1109/JIOT.2022.3152315?utm_source=chatgpt.com)                        | Original publisher record; methodological details partly unavailable |
| Surasakhon et al.                                               | 2022 | IJSNET, [10.1504/IJSNET.2022.127111](https://doi.org/10.1504/IJSNET.2022.127111?utm_source=chatgpt.com)                                | Publisher metadata and abstract                                      |
| El-Sayed et al.                                                 | 2022 | Neural Computing and Applications, [10.1007/s00521-021-06787-w](https://doi.org/10.1007/s00521-021-06787-w?utm_source=chatgpt.com)     | Full open article                                                    |
| Mattela et al.                                                  | 2022 | SN Computer Science, [10.1007/s42979-022-01111-2](https://doi.org/10.1007/s42979-022-01111-2?utm_source=chatgpt.com)                   | Publisher metadata and abstract                                      |
| Chu et al.                                                      | 2023 | IEEE Access, [10.1109/ACCESS.2023.3300726](https://doi.org/10.1109/ACCESS.2023.3300726?utm_source=chatgpt.com)                         | Full open paper                                                      |
| STC-NLSTMNet — Islam et al.                                     | 2023 | Sensors, [10.3390/s23010356](https://doi.org/10.3390/s23010356?utm_source=chatgpt.com)                                                 | Full open paper                                                      |
| TCS-Fall — Zhou et al.                                          | 2024 | Digital Health, [10.1177/20552076241259047](https://doi.org/10.1177/20552076241259047?utm_source=chatgpt.com)                          | Full open paper                                                      |
| DapFall — Chen et al.                                           | 2025 | IEEE Sensors Journal, [10.1109/JSEN.2025.3544552](https://doi.org/10.1109/JSEN.2025.3544552?utm_source=chatgpt.com)                    | Publisher paper record and implementation repository                 |
| AmFall — Kim et al.                                             | 2025 | IEEE IoT Journal, [10.1109/JIOT.2025.3585401](https://doi.org/10.1109/JIOT.2025.3585401?utm_source=chatgpt.com)                        | Publisher paper record and author repository                         |
| Mobile-receiver construction-worker fall detection              | 2025 | Developments in the Built Environment, [10.1016/j.dibe.2025.100745](https://doi.org/10.1016/j.dibe.2025.100745?utm_source=chatgpt.com) | Publisher/author manuscript                                          |
| Adaptive fall detection for unseen environments and individuals | 2025 | IEEE MeMeA, [10.1109/MeMeA65319.2025.11068083](https://doi.org/10.1109/MeMeA65319.2025.11068083?utm_source=chatgpt.com)                | Publisher record                                                     |
| Real-Time Fall Detection via CNN-LSTM, GNN, and Transformer     | 2025 | IntechOpen, [10.5772/acrt20250099](https://doi.org/10.5772/acrt20250099?utm_source=chatgpt.com)                                        | Full chapter                                                         |

The 2024 and 2025 leakage analyses are not counted as fall-detection datasets, but are essential methodological evidence for interpreting CSI-HAR results.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www.mdpi.com\&sz=32)

mdpi.com+1



## **3. Dataset acquisition and recording structure**

### **3.1 The unit of recording is not the unit of training**

This distinction is fundamental:

- **Session:** a broader collection period under a particular radio, room, and participant configuration.
- **Raw recording:** a stored interval of CSI packets.
- **Activity occurrence:** one physical action or event.
- **Segment:** a selected interval inside the raw recording.
- **Window:** a fixed-duration portion of a segment or continuous recording.
- **Training sample:** the final representation presented to the model.
- **Event:** a physically meaningful occurrence, such as one fall, which may generate several overlapping windows.

For example, a 150-second recording containing daily activities and one fall is one raw recording, one session-level observation, and potentially many window-level training samples. It does not represent 150 seconds of one activity.

### **3.2 Comparison matrix: hardware, participants, and recording design**

The following matrix emphasizes the path from physical activity to raw recording. “Samples” refers to the unit explicitly described by the source, not an assumed number of independent falls.

| Study                                                | CSI hardware and configuration                                                                                                                                             | Participants / activity repetitions                                                                                                                                                    | Recording structure                                                                                                                                                                                     | Ground-truth method                                                                                                                                   |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **WiFall (2014)**                                    | Commodity laptop and 802.11n NIC; two indoor scenarios. Exact accessible details of bandwidth, antenna count, and sampling rate: **UNKNOWN**                               | Participant count and repetition totals: **NOT REPORTED** in the accessible original record                                                                                            | Exact recording duration and whether one or multiple activities were stored together: **UNKNOWN**                                                                                                       | **NOT REPORTED** in the accessible source                                                                                                             |
| **Anti-Fall (2015)**                                 | Intel 5300; 5 GHz; about 100 packets/s; one transmitting AP and two receiving antenna links; 30 CSI subcarrier groups                                                      | Six university volunteers; activities included falls and fall-like actions; repetitions per activity: **NOT REPORTED**                                                                 | Continuous experiment streams containing different activities. The system segments candidate events automatically rather than treating every file as one isolated activity                              | Video available in each room and human observation; detailed frame-by-frame annotation procedure: **NOT REPORTED**                                    |
| **RT-Fall (2017)**                                   | Intel IWL5300; 5 GHz; approximately 100 packets/s; one AP transmitter and two receive-antenna links                                                                        | Six subjects, five male and one female, aged 21–32; falls and ADLs including walking, running, jumping, sitting, standing, lying down and object pickup                                | **Continuous mixed-activity streams**; activity and fall-like movement occur in the same stream                                                                                                         | Room video and a human observer recording experiment results; exact timestamp annotation granularity: **NOT REPORTED**                                |
| **FallDeFi (2019)**                                  | Intel 5300-based CSI; 5.2 GHz; 30 subcarrier groups per receive antenna; amplitude and derived time-frequency representations                                              | Three volunteers; falls, fall-like activities, daily activities and empty-room records; Dataset A: 177 falls and 394 non-falls; Dataset B: 149 falls and 350 non-falls                 | Mostly defined 10-second activity recordings, with distinct sessions, rooms and link conditions. The event detector also processes a temporal signal stream                                             | Falls were manually assessed/annotated; precise video-based onset and impact procedure: **NOT REPORTED**                                              |
| **Damodaran et al. (2020)**                          | Two Intel 5300 laptops; 802.11n; 20 MHz; one transmitting antenna and three receive antennas; 30 subcarrier groups per link; 90 amplitude streams                          | Five activity classes, 140 samples each in the fall dataset; the fall class contains 80 cases remaining down and 60 cases standing up after the fall                                   | Defined activity takes. General activity samples contain 2,500 packets; non-fall samples in the fall experiment contain 500 packets over about 5 seconds; falls include an extended post-fall recording | Activity instructions and packet/file separation are reported; independently verified exact fall onset/impact timestamps: **NOT REPORTED**            |
| **Nakamura et al. (2022)**                           | Commodity Wi-Fi CSI, two rooms                                                                                                                                             | Exact participant and repetition counts: **UNKNOWN** from accessible source                                                                                                            | CSI converted into spectrogram images using sliding time windows; exact original file layout: **NOT REPORTED**                                                                                          | **NOT REPORTED** in accessible source                                                                                                                 |
| **Surasakhon et al. (2022)**                         | Exact chipset, antennas and CSI dimensions: **NOT REPORTED** in accessible source                                                                                          | **NOT REPORTED**                                                                                                                                                                       | Detailed recording structure and duration: **NOT REPORTED**                                                                                                                                             | **NOT REPORTED**                                                                                                                                      |
| **El-Sayed et al. (2022)**                           | Public UT-HAR/Intel 5300 data; three receive antennas; 30 subcarriers per antenna; 90 CSI amplitude streams; around 1 kHz                                                  | Six office participants; six activities used by the study; each activity repeated 20 times                                                                                             | The source dataset files contain **multiple samples**, some stationary and some active; the authors selectively extract activity samples from the dataset                                               | Camera recording and MATLAB packet log; the paper describes camera-assisted labeling, but does not give exact event-onset annotation rules            |
| **Mattela et al. (2022)**                            | Full detailed CSI acquisition specifications: **NOT REPORTED** in accessible source                                                                                        | **NOT REPORTED**                                                                                                                                                                       | Recording length and whether files contain mixed activities: **NOT REPORTED**                                                                                                                           | **NOT REPORTED**                                                                                                                                      |
| **Chu et al. (2023)**                                | Intel 5300; one transmitting antenna and three receive antennas; 30 subcarriers per link; approximately 1 kHz; 90 CSI amplitude streams                                    | 22 volunteers, 7 female and 15 male, aged 24–43; falls in four directions, ordinary ADLs, and fall-like negatives                                                                      | Raw CSI files are typically **1–2 minutes**, each containing repeated instances of one particular activity. Individual activity instances are extracted afterward                                       | GoPro video with timestamp overlay synchronized to CSI timestamps; 5-second activity intervals selected by comparing the two                          |
| **STC-NLSTMNet (2023)**                              | Intel 5300; one transmitting antenna, three receive antennas; 30 subcarriers per receive link; 90 amplitude streams                                                        | Multi-environment dataset: 30 volunteers; five predefined experiments, 20 repetitions per environment; also uses StanWiFi data from six participants, with 20 repetitions per activity | Multi-environment trials contain sequences of different actions. StanWiFi uses 20-second activity samples with stationary pre/post portions                                                             | Activity protocols and class segments are described; exact independent video timestamp annotation of every boundary: **NOT REPORTED**                 |
| **TCS-Fall (2024)**                                  | Intel 5300; 3×3 MIMO links; 30 subcarrier groups per TX/RX link; 90 selected amplitude streams                                                                             | 20 volunteers, 10 male and 10 female, aged 19–26; 30 repetitions per single-action condition; continuous recordings also collected                                                     | Two formats: isolated **8-second single-action samples**, and **150-second continuous recordings** containing 120 seconds of ADLs and one fall in the final 30 seconds                                  | Fall time recorded for each continuous sample; whether the timestamp came from video, operator marking, or an embedded event marker: **NOT REPORTED** |
| **DapFall (2025)**                                   | CSI amplitude transformed into dynamic amplitude probability-density profiles; exact chipset, antenna count and packet dimensions: **NOT REPORTED** in accessible source   | Exact subject and event counts: **NOT REPORTED** in accessible source                                                                                                                  | 3D DAPD representations; detailed raw recording structure and physical event annotation: **NOT REPORTED**                                                                                               | **NOT REPORTED** in accessible source                                                                                                                 |
| **AmFall (2025)**                                    | CSI amplitude; selected subcarriers/PCA; exact source hardware and raw CSI dimensions vary or are not fully identified in accessible repository summary                    | Exact participant and repetition counts: **NOT REPORTED** in accessible repository summary                                                                                             | CSI is segmented using a speed-based method and transformed into denoised scalograms. Author repository organizes data by environment, user, and fall/non-fall folders                                  | Folder-level class labels are visible in the repository; exact physical onset/impact annotation mechanism: **NOT REPORTED**                           |
| **Mobile-receiver construction-worker study (2025)** | TP-Link router, 2.4 GHz channel 13, 20 MHz; Nexus 6P smartphone using Broadcom BCM4358/Nexmon; 64 reported subcarriers; nominal CSI rate around 100 packets/s but variable | Six participants; 120 trials each, consisting of 50 falls and 70 fall-like activities; total 720 trials                                                                                | Each trial is a self-contained activity capture of approximately 5 seconds and 500 CSI packets. Subsequent Doppler processing uses overlapping 140-packet windows with a 2-packet stride                | Researcher-recorded video and experiment protocol; precise frame-level event-boundary rules: **NOT REPORTED**                                         |
| **Adaptive fall detection (2025)**                   | Detailed hardware and CSI dimensions: **NOT REPORTED** in accessible publisher record                                                                                      | **NOT REPORTED**                                                                                                                                                                       | Detailed recording structure: **NOT REPORTED**                                                                                                                                                          | **NOT REPORTED**                                                                                                                                      |
| **CNN-LSTM/GNN/Transformer comparison (2025)**       | TP-Link Archer AX23, 5 GHz/80 MHz; Raspberry Pi 4 with Nexmon CSI; 256 received subcarrier values per CSI frame before filtering                                           | Two/three participants are described inconsistently across the accessible study sections; exact independent subject count is therefore **UNKNOWN**                                     | Continuous CSI batches of 100 frames, approximately 5 seconds at the stated beacon interval; samples represent fall, lying down, stillness, transition, and walking                                     | Scheduled capture offsets and class instructions; independent video-based onset/impact annotation: **NOT REPORTED**                                   |

Sources: Anti-Fall and RT-Fall acquisition/participant protocols; FallDeFi dissertation; Damodaran's dataset description; Chu's CSI/video extraction method; UT-HAR source dataset; STC-NLSTMNet; TCS-Fall; and the later studies.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www-public.imtbs-tsp.eu\&sz=32)

www-public.imtbs-tsp.eu+15



**Important:** the table intentionally leaves some fields unknown, even where the chipset family makes a likely value seem obvious. The goal is to report what the paper establishes, not what the hardware normally supports.

### **3.3 Concrete examples of recording design**

**RT-Fall and Anti-Fall: continuous stream**

Subjects perform ordinary activities and fall-like activities, with true falls occurring during the experiment. The system observes the sequence and tries to identify events from the changing CSI signal.

A raw continuous capture can therefore look conceptually like:

```
| stand | walk | sit | stand | bend | fall | lie still | get up | walk |
```

This is an explanatory sequence, not a published exact timeline. Its significance is that event segmentation is part of the algorithm. If a fall classifier is trained only on pre-cut activity snippets, it does not automatically solve the problem of discovering where the event starts in a continuous stream.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://shengjieli-pku.github.io\&sz=32)

shengjieli-pku.github.io+2



**Chu et al. (2023): repeated single-activity files**

A raw file lasts approximately 1–2 minutes but contains several repetitions of the same activity. The researchers use the video timestamp overlay to locate individual actions, then extract individual 5-second CSI segments. Thus, a single raw file can generate multiple labeled samples.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://eprints.whiterose.ac.uk\&sz=32)

eprints.whiterose.ac.uk+1



**TCS-Fall (2024): both isolated and mixed recordings**

TCS-Fall deliberately has two data sources:

- Single-action data: 8-second clips, 30 repetitions per condition.
- Time-continuous data: 150-second sequences, with 120 seconds of daily activity and one fall in the final 30 seconds.

This is particularly useful because it separates the classification problem—recognizing a pre-isolated action—from the detection problem—finding a fall in a longer mixed stream.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://journals.sagepub.com\&sz=32)

journals.sagepub.com+1



**Damodaran et al. (2020): defined activity takes with post-fall distinction**

The fall dataset contains 140 samples per category for walking, standing up, sitting down, falling, and empty-room data. The fall category is further divided into 80 cases where the participant remains lying down and 60 where the participant stands up after falling. This is valuable because it distinguishes a fall transition from the subsequent body state. However, the paper does not give a sufficiently detailed independent annotation procedure for exact fall onset and impact times.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://link.springer.com\&sz=32)

Springer Nature Link+1



### **3.4 Participants and independent observations**

The number of windows is not the number of independent people or physical falls.

For example:

- Chu et al. report 321 fall events and 436 non-fall events across four environments, while using 22 participants.
- TCS-Fall uses 20 volunteers and separates them by volunteer ID for its train/test partition.
- The FallDeFi dissertation reports two datasets with a combined 326 fall takes and 744 non-fall takes, but these are generated by only three volunteers.
- The project’s prior dataset analysis covers 89 takes but only one person and one room.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://eprints.whiterose.ac.uk\&sz=32)

  eprints.whiterose.ac.uk+3



These have very different statistical strength. More repeated actions from one subject increase the amount of data but do not create more independent subject-level variation.

## **4. Activity boundaries and ground truth**

### **4.1 Boundary types must not be conflated**

Fall detection has several possible timestamps:

| Boundary              | Meaning                                                        |
| --------------------- | -------------------------------------------------------------- |
| Instruction time      | When the participant is told to perform the fall               |
| Instruction/cue onset | When the verbal or visual cue is given                         |
| Actual movement onset | When physical motion begins                                    |
| Loss-of-balance onset | When the participant begins uncontrolled descent               |
| Impact                | When the body contacts the landing surface                     |
| Post-fall start       | When the fall transition has ended                             |
| Recovery onset        | When the participant begins getting up                         |
| Recovery completion   | When the participant returns to a standing or normal condition |

These timestamps are not interchangeable. A verbal cue can precede actual movement by a variable amount. A scheduled 5-second interval can include substantial stationary time. Impact may occur after several hundred milliseconds of descent, and post-fall stillness can continue for seconds or minutes.

A paper that labels a sample by the experiment instruction may still be useful for coarse activity classification. It is weaker evidence for exact fall-transition timing and latency measurement.

### **4.2 What the papers actually report**

| Study                     | Boundary identification                                                                | What can be established                                                                                                       |
| ------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Anti-Fall                 | CSI phase-difference variance and transition to stable signal; video/human observation | Algorithmically segments candidate events, but detailed human annotation timestamps are **NOT REPORTED**                      |
| RT-Fall                   | CSI segmentation based on signal transitions; room camera and observer records         | Continuous event identification is demonstrated; exact annotation frame procedure is **NOT REPORTED**                         |
| FallDeFi                  | CSI spectrogram event detector and manually assessed falls                             | Event detector and manual event judgments are described; exact synchronized onset/impact labels are **NOT REPORTED**          |
| Damodaran                 | Protocol-driven samples and packet/time separation                                     | Samples have known activity categories; exact physical event markers are **NOT REPORTED**                                     |
| Chu                       | Video timestamp overlay correlated with CSI time                                       | Clear method for extracting individual activity segments; precise fall-onset and impact annotation scheme is **NOT REPORTED** |
| UT-HAR / El-Sayed         | Video used to label actions; MATLAB packet log retained                                | Activity labels are supported by video, but exact boundary conventions are **NOT REPORTED**                                   |
| STC-NLSTMNet              | Predefined activity protocols and segmented labels                                     | Activity classes are established; exact independent per-frame ground truth procedure is **NOT REPORTED**                      |
| TCS-Fall                  | Fall time recorded in continuous takes                                                 | Continuous fall presence/time is represented, but the source of the precise timestamp is **NOT REPORTED**                     |
| Construction-worker study | Video and controlled trial protocol                                                    | One activity per take is described; exact movement-onset/impact timestamp rules are **NOT REPORTED**                          |
| AmFall                    | Environment/user/class directory organization and CSI-speed segmentation               | Class identity is available; exact human annotation of fall phases is **NOT REPORTED**                                        |

Sources:&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www-public.imtbs-tsp.eu\&sz=32)

www-public.imtbs-tsp.eu+9



### **4.3 Why event timing is especially important**

Suppose one physical fall produces CSI changes over a 3-second interval. A model trained on a 5-second window could receive any of the following:

- 2 seconds of PRE + 3 seconds of falling.
- 1 second of PRE + 3 seconds of falling + 1 second of post-fall.
- 3 seconds of falling + 2 seconds of post-fall.
- 5 seconds of post-fall stillness.

All four windows may come from the same physical fall, but they do not contain the same evidence. Assigning all four the label `FALL` teaches the classifier that stationary post-event behavior is itself the fall transition.

A better labeling scheme retains multiple temporal states:

`PRE_NORMAL → FALL_TRANSITION → POST_FALL → RECOVERY`

The external output may still be binary `FALL`/`NON_FALL`, but the training and event logic should preserve these distinctions.

This is not only a theoretical concern. The earlier project audit found that roughly 55% of windows generated from fall takes were not fully within the annotated fall-action phase under its conservative rule. Labeling all of those windows `FALL` therefore introduces structured label noise.&#x20;

Pasted markdown(6).md



### **4.4 What to do when researchers do not report annotation**

Do not silently assume that a fixed trial boundary is the physical fall boundary.

Use one of these evidence levels:

- **Video-confirmed event annotation:** strongest for physical onset and impact if frame timing is synchronized.
- **Observer-marked event annotation:** useful, but timing precision depends on observer protocol.
- **Experiment schedule / activity cue:** establishes intended action, not necessarily actual onset.
- **CSI-based segmentation:** useful for event discovery, but cannot independently establish the ground-truth class without some external reference.
- **Filename or take label:** establishes the intended class only; it does not establish the temporal position of the action within the take.

In the project dataset, the best next annotation artifact would be a per-recording event timeline containing separate timestamps for actual movement onset, impact, post-fall start, and recovery. An action-level label alone is insufficient to train or evaluate the transition detector.

## **5. Segmentation and training-sample construction**

### **5.1 How published studies turn recordings into samples**

| Study                      | Segmentation method                                                                                      | Window length / stride                                                                                                                                                  | Overlap                                                             | Treatment of stationary or boundary data                                                                                                                                                      |
| -------------------------- | -------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| WiFall                     | Event segmentation/classification architecture; detailed fixed window protocol **UNKNOWN**               | **NOT REPORTED**                                                                                                                                                        | **UNKNOWN**                                                         | **NOT REPORTED**                                                                                                                                                                              |
| Anti-Fall                  | Two-stage segmentation using phase-difference variance and an optimum event window                       | Best activity window approximately 2.9–3.0 s; CSI rate \~100 packets/s                                                                                                  | Not a fixed sliding overlap protocol                                | Event boundaries are detected from transitions in CSI behavior; PRE/POST labeling rules are **NOT REPORTED**                                                                                  |
| RT-Fall                    | Continuous CSI event segmentation using signal stability and movement transitions                        | Activity window around 3 s is discussed in the associated segmentation literature; exact universal frame-window/stride: **NOT REPORTED**                                | **UNKNOWN**                                                         | The system detects events in mixed streams rather than relying exclusively on pre-segmented activity clips                                                                                    |
| FallDeFi                   | STFT-based event detection and extraction from spectrogram                                               | STFT: 512-point window, 256-point hop at 1 kHz                                                                                                                          | 50% in STFT                                                         | Event detection is followed by classification; exact labeling of overlapping PRE/POST windows is **NOT REPORTED**                                                                             |
| Damodaran (traditional ML) | Fixed activity takes; denoising/PCA followed by statistical and frequency features                       | General activity examples: 2,500 packets; fall/non-fall examples include 500-packet action portions                                                                     | No overlapping training-window stride reported                      | Includes empty-room and post-fall standing/lying distinctions; exact window-boundary rules: **NOT REPORTED**                                                                                  |
| Damodaran (LSTM)           | CSI temporal vectors, with activity sequences represented as ordered samples                             | 90 values per time step; exact fall-specific sequence length in accessible description: **NOT REPORTED**                                                                | **UNKNOWN**                                                         | **NOT REPORTED**                                                                                                                                                                              |
| Chu                        | Extract individual 5-second actions from longer raw files using video timestamps; then downsample        | 5 s = 5,000 packets at 1 kHz; downsampling by 8 gives 625 time steps                                                                                                    | Sliding-window overlap is described; exact stride: **NOT REPORTED** | Each extracted segment is selected to contain one activity; treatment of mixed boundary windows beyond this selection: **NOT REPORTED**                                                       |
| El-Sayed / UT-HAR          | Selectively extracts activity samples from source files containing both activity and no-activity periods | Source collection described as 20-second actions; the deep model uses temporal CSI sequences; exact input window length in the accessible description: **NOT REPORTED** | **UNKNOWN**                                                         | Static periods exist in the source files; exact use of all static data as separate model samples is not fully established                                                                     |
| STC-NLSTMNet               | Fixed packet windows generated with sliding segmentation                                                 | 512 packets; stride 128 packets                                                                                                                                         | 75%                                                                 | Labels are associated with activity segments; exact exclusion/labeling policy for cross-boundary windows: **NOT REPORTED**                                                                    |
| TCS-Fall                   | Single-action samples plus sliding windows from continuous recordings                                    | 8 s = 8,000 packets; continuous recording stride = 1 s                                                                                                                  | 87.5%                                                               | Training uses isolated fall samples as positives and samples from the initial 120 seconds of continuous ADLs as negatives; the final 30 seconds are reserved for continuous detection testing |
| Construction-worker study  | Each 500-packet take is processed into Doppler representations using a sliding window                    | 140 packets; stride 2 packets                                                                                                                                           | 98.57%                                                              | Each raw take is a defined fall or fall-like activity. Whether windows derived from one take are kept together in the split is **UNKNOWN**                                                    |
| IntechOpen comparison      | Continuous capture in batches of 100 CSI frames; selected offsets produce overlapping examples           | 100 frames, about 5 s at stated 20 Hz; additional capture offsets at +1 and +4 s                                                                                        | Capture intervals overlap by design                                 | Distinct activity classes include still and transition periods; per-frame boundary annotations are **NOT REPORTED**                                                                           |
| AmFall                     | Speed-based event segmentation followed by CWT/scalogram generation                                      | Exact duration and stride: **NOT REPORTED**                                                                                                                             | **UNKNOWN**                                                         | Fall/non-fall folder labels and speed-based segmentation are reported; ambiguous windows not described                                                                                        |

Sources:&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www-public.imtbs-tsp.eu\&sz=32)

www-public.imtbs-tsp.eu+9



This table illustrates a critical point: “uses sliding windows” is incomplete information. A reproducible method requires at least the duration, stride, CSI sampling behavior, timestamp policy, label rule, and split unit.

### **5.2 Numerical reconstruction from published methods**

**Chu et al. (2023)**

- CSI acquisition: approximately 1,000 packets/s.
- Extracted action interval: 5 seconds.
- Raw interval: \\(5 \times 1000 = 5000\\) CSI packets.
- Downsampling factor: 8.
- Final time dimension: \\(5000/8 = 625\\).
- Final representation: 3 receive-antenna channels × 625 time points × 30 subcarriers.

The model therefore receives a 3D image-like tensor:

\\[ 3 \times 625 \times 30 = 56{,}250 \\]

values per sample, before any internal CNN feature maps. This is not a 56,250-dimensional handcrafted statistical vector; it is a structured amplitude tensor.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://eprints.whiterose.ac.uk\&sz=32)

eprints.whiterose.ac.uk+2



**STC-NLSTMNet**

- Window: 512 packets.
- Stride: 128 packets.
- Overlap: \\((512-128)/512 = 75\\%\\).
- At 1,000 packets/s: 0.512-second window and 0.128-second stride.
- At 320 packets/s: 1.6-second window and 0.4-second stride.
- With 90 CSI amplitude streams: \\(512 \times 90 = 46{,}080\\) values per sample.

A 512-frame window therefore does not have one universal duration. It changes by more than a factor of three between the two reported acquisition rates. This is one reason packet timestamps and actual elapsed duration matter.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www.mdpi.com\&sz=32)

mdpi.com+1



**TCS-Fall**

- Window duration: 8 seconds.
- CSI rate: 1,000 packets/s.
- Frames per window: 8,000.
- Stride: 1 second.
- Overlap: \\(1 - 1/8 = 87.5\\%\\).
- Input after grouped coefficient of variation: \\(400 \times 90 = 36{,}000\\) values.

This is a striking example of the difference between temporal raw CSI and the final training input: the system processes 8,000 time points per antenna/subcarrier channel, but compresses groups of 20 packets into a 400×90 representation before the CNN.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://journals.sagepub.com\&sz=32)

journals.sagepub.com+2



**Construction-worker fall detection**

- Original take: about 500 packets.
- Doppler window: 140 packets.
- Stride: 2 packets.
- Overlap: \\((140-2)/140 \approx 98.57\\%\\).
- Theoretical full windows per 500-packet take, without padding:\
  \\[\
  \left\lfloor \frac{500-140}{2} \right\rfloor + 1 = 181\
  \\]

That is up to 181 highly correlated windows generated from one physical trial. These are not 181 independent falls. The paper's random pooled split makes the exact split unit important; the accessible methodology does not establish a subject- or original-take-grouped split.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://doi.org\&sz=32)

doi.org



### **5.3 Hypothetical example: labeling a continuous 12-second recording**

The following is a methodological illustration, **not a claim about any particular paper**.

Suppose a 12-second recording contains:

- PRE: 0–2 s.
- FALL transition: 2–6 s.
- POST-FALL: 6–12 s.

Generate 2-second windows with a 1-second stride:

| Window | Time interval | Physical contents           | Suggested label   |
| ------ | ------------- | --------------------------- | ----------------- |
| 1      | 0–2 s         | Entirely PRE                | `NORMAL`          |
| 2      | 1–3 s         | PRE + fall transition       | `AMBIGUOUS`       |
| 3      | 2–4 s         | Entirely fall transition    | `FALL_TRANSITION` |
| 4      | 3–5 s         | Entirely fall transition    | `FALL_TRANSITION` |
| 5      | 4–6 s         | Entirely fall transition    | `FALL_TRANSITION` |
| 6      | 5–7 s         | Fall transition + post-fall | `AMBIGUOUS`       |
| 7      | 6–8 s         | Entirely post-fall          | `POST_FALL`       |
| 8      | 7–9 s         | Entirely post-fall          | `POST_FALL`       |
| 9      | 8–10 s        | Entirely post-fall          | `POST_FALL`       |
| 10     | 9–11 s        | Entirely post-fall          | `POST_FALL`       |
| 11     | 10–12 s       | Entirely post-fall          | `POST_FALL`       |

This produces 11 windows, but only three windows are fully inside the defined fall transition.

There are two legitimate model-training choices:

**Binary transition classifier:** use the three fully in-transition windows as `FALL`, use pre-event and properly defined negative activities as `NON_FALL`, and exclude or separately handle boundary-crossing windows. Post-fall can be retained as a distinct evaluation state.

**Temporal-state classifier:** use `NORMAL`, `FALL_TRANSITION`, `POST_FALL`, and `RECOVERY` internally, then map the episode state to the required external fall alarm.

The second option preserves richer temporal information. The first is simpler for an initial binary classifier. Neither justifies labeling every window from a fall take as `FALL`.

### **5.4 Fixed windows versus event-based extraction**

There are two distinct operations:

1. **Candidate segmentation:** determine where a potentially meaningful activity event occurs.
2. **Classifier windowing:** convert that candidate event into a standard tensor or feature vector.

RT-Fall and Anti-Fall are important because segmentation is part of the detector's continuous operation. Chu and TCS-Fall show how pre-cut activity segments can be converted into classifier inputs. These are complementary capabilities, not mutually exclusive alternatives.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www-public.imtbs-tsp.eu\&sz=32)

www-public.imtbs-tsp.eu+3



For a system intended to detect a fall without a human first selecting the relevant segment, candidate event detection must be evaluated as part of the complete pipeline.

## **6. CSI preprocessing**

### **6.1 Signal preprocessing versus feature extraction**

These operations should be reported separately:

- **Signal preprocessing** transforms or cleans the measured CSI signal.
- **Representation transformation** changes its mathematical form, such as converting amplitude into a spectrogram.
- **Feature extraction** reduces the signal to explanatory quantities such as entropy, variance, band energy, or temporal derivatives.

For example, applying a Butterworth filter is signal preprocessing; calculating standard deviation is feature extraction; arranging time-frequency energy into an image is a representation transformation.

### **6.2 Methods found in the papers**

| Method                           | How it is used in the literature                                                       | Input → output                                            | Timing in pipeline                                     | Important limitation                                                                           |
| -------------------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| CSI interpolation                | Anti-Fall, RT-Fall and FallDeFi handle non-uniform packet timing through interpolation | Irregular CSI time points → regularly sampled sequence    | Before filtering and temporal segmentation             | Long gaps should not be treated as ordinary samples; interpolation can create synthetic motion |
| Amplitude extraction             | Used by Damodaran, Chu, STC-NLSTMNet and TCS-Fall                                      | Complex CSI \\(H=I+jQ\\) → \\(\|H\|=\sqrt{I^2+Q^2}\\)     | Early, before amplitude-domain filtering               | Discards phase information                                                                     |
| Phase-difference processing      | Anti-Fall and RT-Fall exploit differences between receive antennas                     | Phase of two receive links → relative phase series        | Early, before segmentation/features                    | Requires reliable multi-antenna phase measurements                                             |
| Low-pass / band-pass filtering   | Anti-Fall, RT-Fall and STC-NLSTMNet                                                    | CSI amplitude/phase time series → filtered time series    | Before segmentation or feature extraction              | A filter can suppress useful fast transients if its cutoff is poorly selected                  |
| DWT denoising                    | Damodaran and FallDeFi                                                                 | CSI amplitude/PCA series → denoised coefficients/signals  | Before time-frequency or feature extraction            | Wavelet and threshold choices influence the output and may be dataset-specific                 |
| PCA                              | Damodaran and FallDeFi; also used in modern CSI pipelines                              | Multiple subcarrier series → lower-dimensional components | After signal cleanup, before final feature/model input | Must be fitted using training data only in a valid held-out evaluation                         |
| Gaussian smoothing               | STC-NLSTMNet                                                                           | Filtered amplitude → smoothed amplitude                   | Before windowing                                       | Can reduce short transient peaks                                                               |
| Grouped coefficient of variation | TCS-Fall                                                                               | Groups of 20 temporal CSI amplitudes → variation sequence | Before CNN window input                                | It is a derived representation, not raw CSI                                                    |
| Downsampling                     | Chu et al.                                                                             | 5,000 time points → 625                                   | Before CNN input                                       | Must preserve the event dynamics needed for fall recognition                                   |
| Hampel outlier removal           | IntechOpen CNN-LSTM/GNN/Transformer study                                              | Per-subcarrier series → outlier-corrected series          | Before smoothing/PCA                                   | Window size and threshold influence transient preservation                                     |
| Savitzky–Golay smoothing         | IntechOpen study                                                                       | Outlier-treated series → smoothed signal                  | Before normalization/PCA                               | Smoothing can distort short or high-frequency impacts                                          |
| CWT / scalogram generation       | AmFall                                                                                 | Selected CSI signal → time-frequency image                | After segmentation/selection                           | One physical event can generate several highly related derived images                          |
| Normalization                    | Chu, TCS-Fall, IntechOpen and other deep-learning studies                              | Raw/filtered CSI values → scaled values                   | Before model input                                     | Must avoid fitting global statistics using held-out test subjects                              |

Sources:&#x20;

[image](https://www.google.com/s2/favicons?domain=https://shengjieli-pku.github.io\&sz=32)

shengjieli-pku.github.io+8



### **6.3 Examples of reported preprocessing parameters**

**Damodaran et al. (2020)**

The paper describes wavelet denoising using a Symlet-6 wavelet with a heuristic SURE threshold and soft thresholding, followed by PCA. In the general activity analysis, the first three principal components account for roughly 70–80% of the variance; the paper generally drops the first component and analyzes the next components. It then applies Haar wavelet processing at level 5 and extracts statistics and spectral descriptors. The fall-specific experiment makes different choices, retaining information that was useful for its fall/post-fall distinction.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://link.springer.com\&sz=32)

Springer Nature Link+1



This matters because preprocessing is not automatically portable between tasks. A PCA component that appears to represent static channel structure in one dataset may carry useful discriminatory information in another.

**FallDeFi**

The dissertation describes interpolation to a uniform sampling grid, wavelet denoising, PCA, and short-time Fourier transform. The STFT uses a 512-sample analysis window and a 256-sample hop at the stated 1 kHz rate. PCA retains a small number of principal components explaining about 95% of the variance. The resulting time-frequency representation is then used for event and feature analysis.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://files.core.ac.uk\&sz=32)

files.core.ac.uk+3



**TCS-Fall**

The method scales CSI using RSS-related information, applies a bidirectional Butterworth low-pass filter to remove high-frequency noise, and calculates grouped coefficient of variation across 20 adjacent amplitude packets. This transforms an 8,000×90 sample into a 400×90 feature matrix.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://journals.sagepub.com\&sz=32)

journals.sagepub.com+1



**Chu et al.**

The authors test wavelet denoising but report that the no-denoising variant performs similarly or better in their comparison. Their principal CNN input path uses downsampling and reshaping rather than an extensive handcrafted feature pipeline.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://eprints.whiterose.ac.uk\&sz=32)

eprints.whiterose.ac.uk+2



**IntechOpen 2025**

The study applies null/pilot and low-value subcarrier removal, Hampel filtering with a window of five and a three-sigma threshold, Savitzky–Golay smoothing with window seven and polynomial order three, normalization, and PCA retaining ten principal components. This is a relatively elaborate preprocessing chain, but it is based on Raspberry Pi/Nexmon CSI rather than ESP32-WROOM CSI.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www.intechopen.com\&sz=32)

IntechOpen+1



### **6.4 Should preprocessing parameters be trained or fitted?**

The correct rule is:

- Parameters that are fixed physical definitions can be applied consistently to every split.
- Parameters estimated from data—normalization means/standard deviations, PCA bases, feature-selection rankings, data-driven thresholds, or learned denoising parameters—must be fitted on training data only.
- Validation data can be used for model selection and threshold calibration only within the training partition.
- Test data must remain untouched until the final evaluation.

The cited papers vary in how explicitly they document these controls. If the article does not state whether PCA or normalization is estimated only from the training fold, classify that point as **UNKNOWN**, not as leakage-free.

### **6.5 Practical implications for the ESP32 project**

The highest-priority preprocessing candidates for a small MCU are:

1. Consistent CSI layout and validity handling.
2. I/Q decoding and amplitude extraction.
3. Lightweight timestamp-aware gap checking.
4. Modest causal smoothing or robust outlier handling.
5. Causal baseline-relative normalization.
6. Compact time-domain features.

The more expensive transforms—large wavelet decompositions, full spectrogram images, or PCA matrix transformations—should first be explored offline. If they demonstrate a material generalization benefit, a lower-cost equivalent can be evaluated for the firmware.

A further limitation is that **zero-phase or bidirectional filtering is not causal**: it uses future samples to filter past samples. This is acceptable for offline analysis, but a real-time ESP32 implementation needs a causal filter or a bounded delayed implementation. A reported offline result using `filtfilt`-type processing should not be assumed to have the same latency or output as an online causal filter.

## **7. Subcarrier selection and feature engineering**

### **7.1 Quantitative comparison of CSI dimensions**

The total number of received subcarrier streams, selected subcarriers, feature types, and final model dimensions are different quantities. A paper reporting “seven features” does not necessarily mean a seven-dimensional model input.

| Study                                     | CSI representation                                          | Subcarriers / links                                                                                       | Feature or model input dimensions                                                                                                                                                                           |
| ----------------------------------------- | ----------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| WiFall                                    | CSI variability and spatial diversity                       | Exact selected subcarrier count: **UNKNOWN** in accessible source                                         | One-class SVM with activity-related CSI features; exact flattened input dimension: **NOT REPORTED**                                                                                                         |
| Anti-Fall                                 | Amplitude and phase                                         | Intel 5300; 30 groups per link; four evenly spaced subcarriers selected                                   | Seven feature types × 4 subcarriers × 2 representations = **56 dimensions per link**. If both receive links are concatenated, that would be 112; explicit flattened total: **NOT REPORTED**                 |
| RT-Fall                                   | Amplitude and phase difference between two receive antennas | 30 subcarrier groups per link; one transmitter and two receive links                                      | Eight named feature types are described: six general amplitude/phase features and two additional phase-derived features. Total flattened feature dimension: **NOT REPORTED**                                |
| FallDeFi                                  | Amplitude → PCA/time-frequency representation               | 30 groups per receive link; 2–3 PCs after dimensionality reduction                                        | Initial selected feature set includes about eight feature categories; a reduced set of three—spectral entropy, fractal dimension, and event duration—was reported as effective in cross-environment testing |
| Damodaran (classical ML)                  | Amplitude, DWT/PCA, time-frequency and statistical features | 30 subcarrier groups × 3 receive antennas = 90 amplitude streams                                          | Eight statistical feature types are described for components; additional row-wise PSD and center-energy features are reported. Final fixed vector length is **NOT REPORTED**                                |
| Damodaran (LSTM)                          | CSI amplitude temporal sequence                             | 90 streams per time step                                                                                  | Input vector length **90** per time step; the model uses a 128-unit LSTM hidden layer                                                                                                                       |
| Chu et al.                                | Amplitude image-like sequence                               | 30 subcarriers × 3 receive antenna streams                                                                | Tensor **3×625×30 = 56,250 values** per sample after 8× downsampling of a 5-second segment                                                                                                                  |
| El-Sayed / UT-HAR                         | Raw CSI amplitude sequence                                  | 30 subcarriers × 3 receive antennas = 90                                                                  | 90 amplitude values per time step; exact sequence length presented to every model is **NOT REPORTED** in the accessible methodology                                                                         |
| STC-NLSTMNet                              | Raw amplitude temporal matrix                               | 30 groups × 3 receive antennas = 90                                                                       | 512×90 = **46,080 values** per input window                                                                                                                                                                 |
| TCS-Fall                                  | Amplitude-derived grouped coefficient of variation          | 30×3 = 90 channels                                                                                        | 400×90 = **36,000 values** per 8-second window                                                                                                                                                              |
| Mobile-receiver construction-worker study | Amplitude/phase-derived Doppler representation              | 64 reported subcarriers; later processing retains 58 after filtering                                      | 140×58×2 = **16,240 values** per Doppler input window, if both reported CSI components are retained in the two-channel representation                                                                       |
| IntechOpen comparison                     | Temporal CSI sequence and PCA representation                | 256 initial subcarriers at 80 MHz; top 10 PCA components retained                                         | 100×10 = **1,000 values** per 100-frame/10-component input                                                                                                                                                  |
| DapFall                                   | Dynamic amplitude probability-density profile               | Exact retained subcarrier and image dimensions: **NOT REPORTED** in accessible source                     | 3D DAPD representation; exact tensor dimensions: **NOT REPORTED**                                                                                                                                           |
| AmFall                                    | Selected amplitude signals converted into CWT scalograms    | Subcarrier/PCA selection is used; exact selected count: **NOT REPORTED** in accessible repository summary | Image/scalogram input; exact dimensions and flattened size: **NOT REPORTED**                                                                                                                                |
| IntechOpen/other recent deep methods      | Multi-channel temporal or graph representations             | Varies by model and preprocessing                                                                         | Must be reported as tensor shape, not only the number of subcarriers                                                                                                                                        |

Sources:&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www-public.imtbs-tsp.eu\&sz=32)

www-public.imtbs-tsp.eu+14



For the Anti-Fall feature count, the per-link calculation is explicit from the described operation: four selected subcarriers, seven feature types, two CSI representations. The total two-link vector size depends on the concatenation procedure and is therefore not asserted as a reported value.

### **7.2 What feature types are actually used?**

| Feature family         | Examples reported in the literature                            | Why it may be useful                                                   |
| ---------------------- | -------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Central tendency       | Mean, median                                                   | Captures level and baseline changes                                    |
| Dispersion             | Variance, standard deviation, IQR, MAD                         | Captures movement-induced fluctuation                                  |
| Amplitude range        | Maximum, minimum, peak-to-peak                                 | Captures transient magnitude                                           |
| Distribution shape     | Skewness, kurtosis, entropy                                    | Captures changes in the distribution of signal variation               |
| Temporal dynamics      | Velocity, temporal difference, event duration, time lag        | Captures how quickly the signal changes and how long activity persists |
| Frequency domain       | PSD, spectral entropy, dominant/central frequency, band energy | Captures periodic movement and transient frequency structure           |
| Time-frequency         | STFT, CWT, scalograms                                          | Preserves both temporal and spectral characteristics                   |
| CSI relationships      | Phase difference, subcarrier mutual information, DAPD          | Captures relationships among multiple CSI components                   |
| Reduced representation | PCA components                                                 | Reduces dimension and may suppress redundant variation                 |

Anti-Fall reports normalized standard deviation, MAD, activity duration, signal strength offset, IQR, entropy, and velocity. RT-Fall extends the feature set with time lag and power decline ratio.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www-public.imtbs-tsp.eu\&sz=32)

www-public.imtbs-tsp.eu+1



FallDeFi selects spectral entropy, fractal dimension, and event duration from a broader feature set. Damodaran combines statistical features with spectral and central-frequency information, while also testing an LSTM over 90-dimensional CSI time steps.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://files.core.ac.uk\&sz=32)

files.core.ac.uk+2



### **7.3 Handcrafted features versus raw CSI**

The literature can be separated into five practical families:

| Input approach                    | Representative studies                    | Classifier input                                            | Strength                                                        | Weakness                                                                     |
| --------------------------------- | ----------------------------------------- | ----------------------------------------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Statistical handcrafted features  | Anti-Fall, RT-Fall, Damodaran, FallDeFi   | Small vector of summary statistics and spectral descriptors | Low computational cost, interpretable                           | Depends on feature design and event segmentation                             |
| Temporal handcrafted features     | RT-Fall, FallDeFi, TCS-Fall               | Duration, velocity, temporal variation, grouped statistics  | Captures event dynamics while reducing data size                | Feature design may not transfer across layouts                               |
| Frequency/time-frequency features | Damodaran, FallDeFi, AmFall, Chu variants | PSD, STFT, CWT/scalogram, image tensor                      | Captures non-stationary movement patterns                       | More compute and sensitivity to timing/filtering                             |
| Raw CSI temporal sequence         | El-Sayed, STC-NLSTMNet                    | Time×subcarrier/antenna matrix                              | Learns temporal/spatial patterns automatically                  | High sample demand and greater overfitting risk                              |
| Image/3D CSI representation       | Chu, Nakamura, DapFall, AmFall            | CNN-ready image/tensor                                      | Can exploit pretrained visual backbones and structured patterns | Tensor size, representation choices, and split leakage can dominate outcomes |

### **7.4 Is phase consistently useful?**

No. Phase is used in some classical WiFall/Anti-Fall/RT-Fall approaches, especially where two receive antennas provide relative phase information. However, the amplitude-oriented approaches in Chu, STC-NLSTMNet, and TCS-Fall do not require phase as a model input.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www-public.imtbs-tsp.eu\&sz=32)

www-public.imtbs-tsp.eu+4



The literature therefore does not support a universal claim that phase is always necessary or always superior. Its value depends on the chipset, antenna arrangement, phase calibration, and preprocessing method.

For a one-antenna ESP32-WROOM-32 target, amplitude should remain the initial baseline. A phase branch should be evaluated separately and only retained if the actual WROOM recordings demonstrate reliable phase behavior across sessions.

## **8. Machine-learning training methodology**

### **8.1 Classical ML versus deep learning**

**Traditional machine learning**

The common sequence is:

```
CSI recording
→ cleaning / filtering
→ event or activity segmentation
→ handcrafted feature vector
→ labeled training table
→ SVM / Random Forest / Logistic Regression
→ validation and test
```

Anti-Fall uses a one-class SVM trained to distinguish fall behavior from fall-like behavior. RT-Fall uses a multi-stage process with feature extraction and SVM classification. Damodaran compares statistical and spectral features with SVM methods. FallDeFi selects a compact feature subset for SVM classification.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www-public.imtbs-tsp.eu\&sz=32)

www-public.imtbs-tsp.eu+3



**Deep learning**

The training path instead commonly becomes:

```
CSI recording
→ signal cleaning
→ event/segment extraction
→ fixed-length tensor / spectrogram / image
→ training augmentation
→ CNN / recurrent / hybrid model
→ validation and test
```

The model receives either temporal CSI matrices or transformed visual representations. It learns filters and temporal features internally rather than receiving manually selected summary statistics.

Examples:

- Chu et al. use a CNN image-classification approach on a reshaped CSI tensor.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://eprints.whiterose.ac.uk\&sz=32)

  eprints.whiterose.ac.uk+1

- El-Sayed et al. compare CNN-GRU, CNN-GRU with attention, CNN-GRU-CNN and CNN-LSTM-CNN architectures.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://pmc.ncbi.nlm.nih.gov\&sz=32)

  pmc.ncbi.nlm.nih.gov+1

- STC-NLSTMNet combines spatial-temporal convolution with a nonlinear LSTM structure.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://www.mdpi.com\&sz=32)

  mdpi.com+1

- TCS-Fall uses a CNN on its grouped coefficient-of-variation representation.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://journals.sagepub.com\&sz=32)

  journals.sagepub.com+1

- DapFall converts CSI amplitude into a dynamic amplitude probability-density profile and applies a pretrained R(2+1)D architecture.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://ieeexplore.ieee.org\&sz=32)

  IEEE Xplore+1

- AmFall uses wavelet-denoised scalograms and CNN-based image classification.&#x20;

  [image](https://www.google.com/s2/favicons?domain=https://snu.elsevierpure.com\&sz=32)

  snu.elsevierpure.com+1



### **8.2 Examples of reported training settings**

| Study                                     | Model                                                                  | Reported training details                                                                                                | Validation / selection                                                                                            |
| ----------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| Anti-Fall                                 | One-class SVM                                                          | LibSVM; training examples generated from segmented activity examples                                                     | Exact tuning and subject-group split: **NOT REPORTED**                                                            |
| RT-Fall                                   | SVM-based classification stages                                        | Progressive model personalization with an initial subject's falls/fall-like samples and subsequent user-specific testing | Not a conventional single LOSO result; details below                                                              |
| Damodaran                                 | Linear one-vs-all SVM; LSTM                                            | SVM regularization \\(C=0.01\\); LSTM hidden units 128, softmax, cross-entropy, Adam, batch 128, learning rate 0.001     | Exact fall-dataset split: **NOT REPORTED**                                                                        |
| Chu                                       | CNN image classifier and baseline comparisons                          | PyTorch; Adam, initial learning rate 0.001, weight decay 0.0001, batch 50, 40 epochs; learning-rate step schedule        | 80/20 train/validation dataset split; additional cross-room/subject combinations                                  |
| El-Sayed                                  | CNN-GRU and CNN-LSTM hybrid architectures                              | Deep models trained on raw CSI amplitude temporal data                                                                   | Random 70/30 sample split and k-fold experiments; no clear subject-only partition in accessible description       |
| STC-NLSTMNet                              | CNN + attention + NLSTM                                                | Adam, learning rate 0.001, batch size 128, up to 100 epochs, categorical cross-entropy, early stopping                   | Ten-fold CV after window generation                                                                               |
| TCS-Fall                                  | CNN                                                                    | Five convolutional layers, max-pooling, ReLU, dropout 0.6                                                                | Subject-ID grouped folds; multiple train/test subject ratios                                                      |
| DapFall                                   | Pretrained R(2+1)D                                                     | Transfer learning and amplitude-based augmentation                                                                       | Original/cross-environment evaluations; detailed optimizer/split procedure: **NOT REPORTED** in accessible source |
| AmFall                                    | Lightweight CNN / ResNet variants                                      | MATLAB scalogram generation and Colab CNN/ResNet repository                                                              | Exact split unit, augmentation ordering, and fold assignment: **UNKNOWN** in accessible repository                |
| Mobile-receiver construction-worker study | Deep-learning fall/fall-like classifier on CSI Doppler representations | CSI preprocessing and highly overlapping Doppler windows                                                                 | Pooled 6:2:2 random split; whether the split occurs at original take or derived-window level is **UNKNOWN**       |

Sources:&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www-public.imtbs-tsp.eu\&sz=32)

www-public.imtbs-tsp.eu+9



The important difference is not merely model type. It is what the model is trained to recognize:

- Anti-Fall and RT-Fall emphasize segmented activity events.
- Damodaran distinguishes falling from the post-fall consequence of standing up.
- Chu trains on extracted activity windows.
- TCS-Fall separates isolated action examples from continuous activity streams.
- Deep HAR approaches often classify fixed windows rather than detecting a complete event with a single onset and alarm.

A high multi-class HAR score does not automatically demonstrate a reliable binary fall alarm.

### **8.3 Does deep learning require more data?**

The answer depends on representation and model capacity. A CNN using a compact 2D spectrogram may have fewer parameters than a large raw temporal network; a compact recurrent model can also be relatively small. However, deep models still need sufficient independent variation to learn robust patterns.

In the six-participant UT-HAR use case, El-Sayed reports 8,959 extracted activity samples from 20 repeated activities per participant/activity. Those 8,959 samples are not 8,959 independently recruited people or independently varied environments.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://pmc.ncbi.nlm.nih.gov\&sz=32)

pmc.ncbi.nlm.nih.gov



Similarly, TCS-Fall can generate many heavily overlapping windows from a smaller number of continuous recordings. Its cross-subject split is methodologically more informative than the sheer number of resulting windows.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://journals.sagepub.com\&sz=32)

journals.sagepub.com+1



For the ESP32 project, model capacity should be selected based on **independent subjects, sessions, events and environments**, not merely the total number of windows.

## **9. Dataset splitting and leakage prevention**

This is one of the most consequential parts of the review.

### **9.1 A split is only meaningful when its grouping unit is known**

A dataset can be split at several levels:

1. Random CSI frame.
2. Random window.
3. Random activity segment.
4. Random original recording/take.
5. Random recording session.
6. Random subject.
7. Random environment.

Each tests a different generalization problem.

| Split method                  | What it tests                                                  | Main weakness                                                             |
| ----------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Random frame split            | Nearly none for event recognition                              | Adjacent frames from the same physical event can occur in both partitions |
| Random window split           | Performance on randomly selected windows from a pooled dataset | Highly overlapping or same-recording windows can leak                     |
| Random take split             | Generalization to different takes                              | Same subject, room and recording session may remain in both               |
| Random session split          | Generalization to a separate recording occasion                | Same subject and room characteristics may remain                          |
| Subject-independent split     | Generalization to unseen people                                | May still use the same environment                                        |
| Environment-independent split | Generalization to a different room or link layout              | May still use people seen during training                                 |
| Subject + environment holdout | Stronger evidence for deployment to new users and locations    | Requires a larger and more diverse dataset                                |

### **9.2 What the literature actually does**

| Study                     | Reported split                                                                              | Does it prevent windows from the same original recording crossing train/test?      | Subject/environment independence                                                                                        |
| ------------------------- | ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| WiFall                    | Details **UNKNOWN** in accessible original record                                           | **UNKNOWN**                                                                        | **UNKNOWN**                                                                                                             |
| Anti-Fall                 | Split details **NOT REPORTED** sufficiently                                                 | **UNKNOWN**                                                                        | **UNKNOWN**                                                                                                             |
| RT-Fall                   | Progressive personalization and testing of additional people                                | Not a clean conventional grouped-fold protocol                                     | Some cross-user testing, but personalization means this is not equivalent to zero-shot LOSO                             |
| FallDeFi                  | Within-environment 70/30 and cross-environment/cross-subject testing are described          | Original sample/take grouping needs separate confirmation                          | Explicit room/person transfer experiments                                                                               |
| Damodaran                 | Fall dataset training/test split not reported clearly                                       | **UNKNOWN**                                                                        | **UNKNOWN**                                                                                                             |
| Chu                       | 80/20 data split; also additional room/participant combinations                             | **UNKNOWN** whether original 1–2 minute source files were kept intact in the split | Additional cross-room and participant testing is reported, but primary random split is not a guaranteed subject holdout |
| El-Sayed                  | Random 70/30 and k-fold sample partitioning                                                 | **UNKNOWN** at original-recording level                                            | Not established as LOSO in accessible method                                                                            |
| STC-NLSTMNet              | Ten-fold cross-validation after sliding-window generation                                   | **UNKNOWN**; overlapping windows may cross folds                                   | Subject-group separation is **NOT REPORTED**                                                                            |
| TCS-Fall                  | Fold assignment by volunteer ID                                                             | All windows from one volunteer remain in one partition                             | **Yes, subject-independent**; cross-room generalization not established                                                 |
| Construction-worker study | Pooled 6:2:2 split                                                                          | **UNKNOWN** whether splitting occurs before or after derived-window generation     | Subject grouping **NOT REPORTED**                                                                                       |
| IntechOpen                | Stratified 80/20 sample-level split is described; subject count information is inconsistent | **UNKNOWN**                                                                        | Claimed participant testing does not resolve this inconsistency                                                         |
| AmFall                    | Exact split procedure not established by accessible repository                              | **UNKNOWN**                                                                        | **UNKNOWN**                                                                                                             |
| DapFall                   | Cross-environment/no-retraining results reported                                            | Exact train/test grouping procedure: **UNKNOWN** in accessible source              | Cross-environment evaluation reported; subject split details not available                                              |

Sources:&#x20;

[image](https://www.google.com/s2/favicons?domain=https://shengjieli-pku.github.io\&sz=32)

shengjieli-pku.github.io+9



### **9.3 The overlapping-window leakage problem**

Consider a time series split into windows of 8 seconds with a 1-second stride. Each adjacent window shares 7 seconds of CSI, or 87.5% of its raw temporal content.

If one window enters training and its adjacent window enters testing, the test sample is not truly independent. It contains almost the same physical signal.

This issue becomes even more severe at 140-packet windows with a 2-packet stride, where approximately 98.6% of adjacent windows overlap. The resulting samples may be numerous, but many carry nearly identical signal content.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://journals.sagepub.com\&sz=32)

journals.sagepub.com+1



**Correct ordering:**

```
Original data
     ↓
Assign group IDs
(subject / session / take / event)
     ↓
Split groups into train / validation / test
     ↓
Generate windows separately within each partition
     ↓
Fit transformations on training data only
     ↓
Train / tune / evaluate
```

Do not generate all overlapping windows and randomly split them as independent samples.

### **9.4 Subject-identity leakage is not theoretical**

Varga's 2024 analysis of a CSI-HAR CNN study found that the original protocol mixed individuals across training and test sets. The critical analysis reported that enforcing subject-based separation reduced precision compared with the original 99.9% claim.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www.mdpi.com\&sz=32)

mdpi.com



The 2025 follow-up, *Why Partitioning Matters*, quantified an approximately 32% F1 overestimation in its examined case when subjects were mixed between training and test. The paper also notes that its example does not establish the prevalence of leakage across every CSI-HAR publication; doing so would require systematic reimplementation and inspection.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www.mdpi.com\&sz=32)

mdpi.com



This is a major warning for fall detection: absolute CSI amplitude, room geometry, device placement, and person-specific movement characteristics can become fingerprints. A classifier can appear to recognize activities while largely recognizing the recording conditions or subjects.

### **9.5 Other leakage pathways**

| Leakage source       | How it happens                                                                | Correct control                                                                  |
| -------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Overlapping windows  | Adjacent windows share most CSI samples                                       | Group by original take/event before window generation                            |
| Subject identity     | Same person's CSI patterns occur in both train and test                       | Subject-exclusive evaluation                                                     |
| Environment identity | Same room/layout appears in all partitions                                    | Leave-one-environment-out testing                                                |
| Normalization        | Global mean/standard deviation includes test data                             | Fit scale parameters on training split only                                      |
| PCA                  | Principal components are learned using all data                               | Fit PCA inside each training fold                                                |
| Feature selection    | Features chosen after observing test performance                              | Feature selection inside nested training folds                                   |
| Augmentation         | Transformed copies of one physical event appear across partitions             | Split original events before augmentation                                        |
| Repeated recordings  | Several takes from one session occur in different partitions                  | Group by session and subject                                                     |
| Temporal neighbors   | Nearby windows inherit nearly identical channel state                         | Time-block or take-level separation                                              |
| Recording metadata   | Subject ID, time, filename or capture order becomes an accidental model input | Exclude non-deployment identifiers and test under independent capture conditions |

**Project-specific implication:** the earlier project experiment found that absolute amplitude profiles achieved very high scores but encoded session-specific characteristics. This is a direct warning against trusting absolute-profile performance unless the model is validated on new sessions and environments.&#x20;

Pasted markdown(6).md



### **9.6 Recommended validation hierarchy**

For the eventual project evaluation, use:

- **Group-by-take validation:** minimum safeguard against neighboring-window leakage.
- **Group-by-session validation:** checks variation between separate recording sessions.
- **Leave-one-subject-out (LOSO):** the principal subject-generalization test.
- **Leave-one-environment-out:** separate test for room/layout robustness.
- **Subject-and-environment holdout:** strongest practical deployment test once enough data exist.

Model/feature selection should occur inside the training data using grouped cross-validation. The outer test subject/environment must not influence window settings, feature selection, PCA, normalization, thresholds, or hyperparameters.

## **10. Evaluation methodology**

### **10.1 The published studies measure different outcomes**

| Study                     | Main reported metrics                                                 | Metric level                           | Event latency / false alarms per hour                                                                              |
| ------------------------- | --------------------------------------------------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| WiFall                    | Precision and false-alarm rate                                        | Fall detection classification          | Exact latency / FA per hour: **NOT REPORTED** in accessible source                                                 |
| Anti-Fall                 | Fall detection ratio and false-positive rate                          | Detected events/segments               | Latency: **NOT REPORTED**; FPR is not equivalent to FA/hour                                                        |
| RT-Fall                   | Sensitivity and specificity                                           | Activity/fall detection                | FA/hour and event latency: **NOT REPORTED**                                                                        |
| FallDeFi                  | Accuracy, precision, recall, F1 and environment-transfer measures     | Segmented event/classification level   | FA/hour: **NOT REPORTED**                                                                                          |
| Damodaran                 | Sensitivity, precision and specificity                                | Activity-sample classification         | Event latency and FA/hour: **NOT REPORTED**                                                                        |
| Chu                       | Accuracy, precision and recall                                        | Extracted 5-second activity windows    | Event latency and FA/hour: **NOT REPORTED**                                                                        |
| El-Sayed                  | Accuracy and class-based classification scores                        | HAR sample/window level                | Event latency and FA/hour: **NOT REPORTED**                                                                        |
| STC-NLSTMNet              | Accuracy, precision, recall and F1                                    | Sliding-window class classification    | Event-level latency and FA/hour: **NOT REPORTED**                                                                  |
| TCS-Fall                  | AUC, NEWR and CWR                                                     | Continuous-recording detection metrics | Provides continuous fall/false-positive-oriented evaluation, but no conventional FA/hour or physical onset latency |
| DapFall                   | Recall/TPR 94.3%, FPR 6.25% in original environments                  | Fall-detection classification          | Event latency / FA/hour: **NOT REPORTED** in accessible source                                                     |
| Construction-worker study | Accuracy, class scores and confusion matrix                           | Derived window/classification set      | Event latency / FA/hour: **NOT REPORTED**                                                                          |
| IntechOpen study          | Offline model classification metrics and live hospital-test detection | Offline windows and live event trials  | Live event outcomes reported; no standardized FA/hour measurement                                                  |

Sources:&#x20;

[image](https://www.google.com/s2/favicons?domain=https://ieeexplore.ieee.org\&sz=32)

IEEE Xplore+10



### **10.2 Window-level accuracy is not event-level reliability**

Suppose one real fall generates 15 overlapping windows. A classifier correctly recognizes only one of those windows, and the alarm logic triggers if at least one window is positive.

The window-level recall might be poor, yet the event may still be detected.

Conversely, a classifier may correctly classify many fall windows from a single take, but miss several other physical falls entirely.

These are different outcomes:

- **Window-level recall:** proportion of labeled FALL windows classified as FALL.
- **Event recall:** proportion of independent physical falls detected at least once within the required time window.
- **Event precision:** proportion of confirmed alarm events that correspond to actual falls.
- **False alarms per hour:** false alarm events divided by observed non-fall monitoring hours.
- **Latency:** time from a defined physical onset/impact reference to the first valid alarm.

The number of overlapping positive windows must not inflate the count of correctly detected physical falls.

### **10.3 False-positive rate versus false alarms per hour**

These should not be treated as equivalent.

\\[ FPR = \frac{FP}{FP+TN} \\]

This is a classification metric over the set of negative samples.

\\[ FA/h = \frac{\text{number of false alarm events}}{\text{observed non-fall hours}} \\]

This is a deployment-oriented event rate.

A system can have an apparently modest window-level FPR but still generate repeated alarms during long periods of ordinary activity, especially if positive predictions flicker and the system has no event latch.

A meaningful false-alarm evaluation requires sufficiently long, representative negative recordings. A few seconds of empty-room CSI cannot establish a useful false-alarms-per-hour rate.

### **10.4 Recommended evaluation protocol**

The future project evaluation should report two groups of metrics.

**A. Window-level classification**

- FALL precision, recall and F1.
- NON-FALL specificity.
- Macro-F1.
- Balanced accuracy.
- Confusion matrix.
- False-positive rate.
- Performance by subject, session, environment and activity subtype.

**B. Event-level detection**

- Number of physical fall events.
- Event detection rate.
- Missed event count.
- False alarms per hour.
- Median and 95th-percentile latency.
- Time from actual movement onset to first candidate.
- Time from impact to confirmed alarm.
- Duplicate alarms per physical event.
- Detection rate by fall direction and fall speed.
- False alarm rate for individual hard-negative activities.

The denominator must be reported. For example, a result based on 10 falls and 20 minutes of negative monitoring is not statistically equivalent to one based on 200 falls and 100 hours of negative monitoring.

### **10.5 What makes a strong evaluation?**

A stronger scientific study:

1. Defines the independent physical unit—subject, session, take, and event.
2. Establishes real movement and impact timestamps.
3. Holds out complete subjects or environments.
4. Prevents windows and augmented copies from crossing splits.
5. Fits normalization and feature transformations inside training folds.
6. Reports both window and event performance.
7. Records long enough negative periods to calculate false alarms per hour.
8. Tests continuous recordings containing both ordinary activities and falls.
9. Separately reports offline test accuracy and actual real-time detection latency.

TCS-Fall demonstrates several of these principles through subject-ID grouped splitting and a continuous-stream test set. The 2024 and 2025 leakage studies demonstrate why grouping must be explicit rather than assumed.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://journals.sagepub.com\&sz=32)

journals.sagepub.com+2



## **11. Cross-paper scientific findings**

The following answers distinguish what is common in the reviewed literature from what can actually be established by the individual papers.

### **11.1 Do most CSI fall-detection projects use one activity per recording?**

**No universal practice exists.** Both continuous mixed-activity recording and isolated activity recording are established approaches.

- RT-Fall and Anti-Fall use continuous streams containing multiple activity types.
- Chu uses repeated instances of one activity inside longer raw files and extracts individual activity segments.
- FallDeFi and Damodaran use mostly predefined activity takes.
- TCS-Fall deliberately supports both isolated actions and continuous mixed recordings.

[image](https://www.google.com/s2/favicons?domain=https://shengjieli-pku.github.io\&sz=32)

shengjieli-pku.github.io+4

### **11.2 Do researchers normally preserve the entire recording?**

They often preserve the raw CSI recording, but do not necessarily present the entire recording to the classifier.

The distinction is important:

- Chu retains a longer raw file but selects 5-second activity samples.
- TCS-Fall preserves continuous recordings but generates 8-second sliding windows for the classifier.
- UT-HAR source files can contain several activity and no-activity samples; downstream studies selectively extract activity samples.
- Continuous-stream methods use the data for event detection rather than necessarily using the entire stream as one ML sample.

[image](https://www.google.com/s2/favicons?domain=https://eprints.whiterose.ac.uk\&sz=32)

eprints.whiterose.ac.uk+2

### **11.3 How common is sliding-window segmentation?**

It is common in CSI-HAR and in more recent continuous fall-detection pipelines.

Examples include:

- STC-NLSTMNet: 512 packets, stride 128.
- TCS-Fall: 8 seconds, stride 1 second.
- FallDeFi: STFT window 512, hop 256.
- Construction-worker fall detection: 140 packets, stride 2.
- Chu: 5-second segments with overlap, but exact stride not reported.

The specific window/stride is highly study-dependent. There is no universal CSI fall window length.

[image](https://www.google.com/s2/favicons?domain=https://www.mdpi.com\&sz=32)

mdpi.com+4

### **11.4 Are PRE and POST periods used for training?**

**Sometimes, but the usage differs.**

- Damodaran explicitly differentiates post-fall behavior by whether the participant remains lying down or stands up.
- StanWiFi captures stationary context around activity samples.
- TCS-Fall uses continuous daily activity and reserves the final 30 seconds for fall-containing sequences, while its training negatives include the earlier ADL period.
- Many other studies do not fully report whether every PRE/POST window is kept, removed, or assigned a separate label.

[image](https://www.google.com/s2/favicons?domain=https://link.springer.com\&sz=32)

Springer Nature Link+3

### **11.5 How are fall boundaries normally defined?**

The literature uses a mixture of CSI-based event segmentation, video-supported activity extraction, and scheduled activity trials. There is no universal ground-truth convention.

The distinction between activity cue, actual movement onset, and physical impact is rarely documented with sufficient precision across all studies. Papers that use predefined 5-second or 8-second trials should not automatically be interpreted as having frame-accurate fall onset labels.

### **11.6 Are manual annotations common?**

Video observation and human assessment appear in several studies, particularly Anti-Fall, RT-Fall, Chu and UT-HAR. However, the precise procedure for assigning movement-onset, impact, and recovery timestamps is often **NOT REPORTED**.

The strongest reported synchronization example in this review is Chu's use of GoPro timestamp overlays to identify activity segments within CSI files. That method supports segment extraction but does not automatically establish a precise impact timestamp.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://shengjieli-pku.github.io\&sz=32)

shengjieli-pku.github.io+2



### **11.7 How many subcarriers are typically selected?**

There is no consistent number.

- Anti-Fall uses four selected subcarriers from the Intel 5300 representation for its handcrafted feature calculation.
- Many Intel 5300 deep HAR datasets use 30 CSI groups per link, often over three receive antennas, producing 90 temporal streams.
- Chu reshapes the three-receive-stream data into an image-like tensor with 30 subcarriers.
- The IntechOpen study starts with 256 CSI subcarriers and reduces the representation to ten PCA components.

[image](https://www.google.com/s2/favicons?domain=https://www-public.imtbs-tsp.eu\&sz=32)

www-public.imtbs-tsp.eu+4

### **11.8 Do most traditional ML papers use handcrafted features?**

Among the classical methods reviewed, **yes**. Anti-Fall, RT-Fall, Damodaran's statistical pipeline and FallDeFi all construct engineered features.

Common feature families are dispersion, distribution, temporal activity duration, signal change, entropy, and spectral descriptors.

The deep-learning studies instead use temporal CSI tensors, spectrograms, scalograms, or other structured representations.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www-public.imtbs-tsp.eu\&sz=32)

www-public.imtbs-tsp.eu+4



### **11.9 How many feature types and dimensions are commonly used?**

There is no meaningful single standard.

The reviewed papers range from three selected event features in FallDeFi to much larger representations such as a 56,250-value Chu tensor or a 46,080-value STC-NLSTMNet window. These counts describe different input types and should not be ranked as though they were equivalent feature vectors.

For compact classical classifiers, the important question is whether a small set of features preserves the discriminative information across independent people and rooms.

### **11.10 How common is raw CSI input for deep learning?**

Raw or lightly processed CSI temporal sequences are used in studies such as El-Sayed and STC-NLSTMNet. Other deep methods use image representations such as spectrograms, scalograms, DAPD profiles, or grouped variation maps.

The evidence does not imply that raw input is always best. It implies that the representation must be evaluated with valid independent splits.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://pmc.ncbi.nlm.nih.gov\&sz=32)

PubMed Central (PMC)+4



### **11.11 Is phase information consistently useful?**

No. Some classical methods rely on relative phase across two receive antennas. Numerous other systems use amplitude-only representations. The findings are hardware- and representation-dependent.

The single-antenna ESP32-WROOM-32 does not directly replicate the two-receive-antenna phase-difference setup in Anti-Fall/RT-Fall. This is an important reason to begin with amplitude for the target project.

### **11.12 What preprocessing is most common?**

The most recurring operations are:

- CSI decoding and packet cleaning.
- Amplitude extraction.
- Filtering/smoothing.
- Interpolation when packet times are irregular.
- Windowing and subcarrier selection.
- Normalization.
- Optional PCA or frequency/time-frequency transforms.

The exact algorithm varies substantially. A paper should report not only the name of a filter but also its parameters, causality, and placement in the pipeline.

### **11.13 What evaluation methodology is scientifically most reliable?**

Subject-independent and environment-independent tests, combined with event-level evaluation, provide stronger evidence than a random window split.

For real-time fall detection, the final test should include long continuous streams and should report false alarms per hour and event detection latency, not only accuracy and window-level recall.

### **11.14 What practices are most likely to produce leakage?**

The highest-risk practices are:

- Randomly splitting overlapping windows.
- Mixing the same subjects across train and test while claiming generalization to unseen people.
- Creating scalogram or augmented copies before splitting the original events.
- Computing normalization or PCA using all samples.
- Selecting features based on test performance.
- Allowing multiple takes from the same session to appear in separate partitions without accounting for their correlation.

These risks are not merely hypothetical: the 2024 and 2025 CSI-HAR leakage analyses document substantial overestimation associated with non-subject-independent splitting.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www.mdpi.com\&sz=32)

mdpi.com+1



### **11.15 What distinguishes stronger research from weaker research?**

The strongest methodological examples in this review have several characteristics:

- Clear raw-recording structure.
- Explicit participant and activity protocol.
- A reproducible explanation of segmentation and windowing.
- A known labeling source.
- A defined independent split unit.
- Evaluation on continuous recordings, not only random windows.
- Separate results for subject and environment generalization.
- Transparent reporting of limitations.

Among the reviewed studies, TCS-Fall is particularly useful for understanding subject-based splitting and continuous fall-containing recordings. Chu is particularly useful for reconstructing how video-timed activities are extracted from longer CSI files. RT-Fall and Anti-Fall are valuable for understanding continuous event segmentation. None should be treated as a universal template for every dataset.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://journals.sagepub.com\&sz=32)

Sage Journals+3



# **12. Proposed experimental pipeline for a small ESP32 fall-detection dataset**

The purpose of this section is to translate the literature into an experimental plan, not to prescribe an unverified final model.

## **12.1 Recommended original recording format**

The project should retain continuous raw data as the primary research artifact and generate labeled windows as derived training artifacts.

Each raw recording should include at least:

| Field                             | Purpose                                   |
| --------------------------------- | ----------------------------------------- |
| `session_id`                      | Identifies one collection session         |
| `take_id`                         | Identifies one original recorded interval |
| `subject_id`                      | Allows subject-independent splitting      |
| `environment_id`                  | Separates rooms/layouts                   |
| `recording_start`                 | Establishes temporal origin               |
| `receiver_id` / hardware ID       | Identifies CSI receiver                   |
| `transmitter_id` / peer MAC alias | Identifies link                           |
| `channel` / `bandwidth`           | Records RF configuration                  |
| `ltf_type` / CSI layout           | Ensures compatible data representation    |
| `sequence_number`                 | Identifies received packet order          |
| `rx_timestamp`                    | Actual packet timing                      |
| `callback_timestamp`              | Firmware callback timing                  |
| `I/Q` or complex CSI              | Preserves the primary measured data       |
| `RSSI` / noise floor              | RF quality context                        |
| `packet_validity`                 | Marks malformed or rejected records       |
| `gap/overflow counters`           | Identifies incomplete segments            |

The annotation should be stored separately from the CSI payload, linked by `session_id`, `take_id` and a common time origin.

Example annotation structure:

| Event ID | Start     | Impact    | Post-fall start | Recovery start | Recovery end | Class    |
| -------- | --------- | --------- | --------------- | -------------- | ------------ | -------- |
| E001     | Timestamp | Timestamp | Timestamp       | Timestamp      | Timestamp    | FALL     |
| E002     | Timestamp | N/A       | N/A             | N/A            | N/A          | FAST_SIT |
| E003     | Timestamp | N/A       | N/A             | N/A            | N/A          | BEND     |

Actual timestamps must be observed and annotated; they should not be filled with the activity instruction time.

### **Should one recording contain one activity or multiple activities?**

I recommend using **both formats**, for different purposes:

**Isolated activity takes**

Useful for controlled feature comparison and initial classifier development. Examples include a defined sit, bend, fast sit, intentional lie-down, and fall.

**Continuous mixed-activity recordings**

Useful for testing whether the system can find falls in the presence of ordinary movement, stationary periods, and activity transitions.

A dataset made exclusively from isolated falls and isolated normal activities may train a good event classifier but does not adequately validate real-time event discovery.

## **12.2 Comparison of the eight proposed pipelines**

The following ranking is for a compact microcontroller-oriented project. It is an experimental priority ranking, not a claim that one method is universally more accurate.

| Pipeline                                                        | Input representation                                                         | Training approach                                | Dataset requirements                                             | MCU feasibility                                                             | Main risk                                                          |
| --------------------------------------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------ | ---------------------------------------------------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| **A. Selected subcarriers + handcrafted features + Linear SVM** | Selected amplitude bands, temporal statistics and baseline-relative features | Feature matrix → Linear SVM                      | Moderate, but requires diverse physical events and subjects      | Very high                                                                   | Manual feature design may miss complex temporal patterns           |
| **B. Full amplitude subcarrier representation + Linear SVM**    | Full amplitude per selected time window, summarized or flattened             | Linear SVM                                       | More samples needed than a compact feature set                   | High if the vector is reduced; large raw vectors need more RAM              | High dimensionality and session fingerprinting                     |
| **C. Amplitude + temporal difference features**                 | Amplitude, first differences, motion energy and temporal change              | Linear SVM / Logistic Regression                 | Moderate; useful hard negatives are essential                    | Very high                                                                   | Difference features amplify noise and packet irregularity          |
| **D. Amplitude statistical features**                           | Mean, variance, MAD, IQR, range, entropy, RMS                                | Logistic Regression / Linear SVM / shallow tree  | Moderate                                                         | Very high                                                                   | May discard temporal order                                         |
| **E. Amplitude + phase features**                               | Amplitude plus sanitized phase or relative phase                             | Classical ML                                     | Requires repeatable phase measurements and configuration control | Medium, but reliability unproven on this receiver                           | Phase calibration and hardware dependence                          |
| **F. Time-frequency representation**                            | STFT, wavelet coefficients or compact band-energy vector                     | SVM / shallow classifier; optionally CNN offline | More falls and varied movement speeds                            | Medium if reduced to compact band statistics; full images lower feasibility | Computational cost, filtering delay and representation sensitivity |
| **G. Raw CSI temporal matrix + 1D CNN**                         | Time × subcarrier × amplitude channels                                       | CNN with regularization and augmentation         | High; independent subjects and events required                   | Low-to-medium, architecture-dependent; must profile memory and latency      | Overfitting with small correlated datasets                         |
| **H. Raw CSI temporal matrix + GRU**                            | Ordered temporal CSI sequence                                                | GRU classifier                                   | High; varied event timing and sufficient independent sequences   | Low-to-medium; depends strongly on hidden size/sequence length              | Recurrent activation memory and temporal overfitting               |

### **Experimental ranking**



Recommended first

**A — Selected subcarriers + handcrafted features + Linear SVM**



It offers the best balance of interpretability, manageable dataset size and embedded feasibility. It should be the control candidate for the next experiment.

**B — Full amplitude representation + Linear SVM** should be a controlled challenger. It tests whether selecting only a small number of subcarriers discards useful information.

**C — Amplitude + temporal difference** is a high-value ablation because fall transitions are fundamentally temporal events, not merely abnormal absolute amplitudes.

**D — Amplitude statistics** provides a simpler baseline and helps reveal whether the performance comes from actual temporal dynamics or just changes in average signal distribution.

**E — Amplitude + phase** is valuable scientifically but should not be prioritized for deployment before phase stability is demonstrated on the specific WROOM hardware.

**F — Time-frequency representation** is a useful offline comparison, especially for fast transients, but the first MCU candidate should be compact band-energy or entropy features rather than a full image pipeline.

**G and H** are worthwhile exploratory models after the dataset is much larger and more diverse. They should not become deployment candidates merely because their offline training accuracy is higher.

### **12.3 Required experiment design for each pipeline**

| Pipeline | Preprocessing                                                                            | Windowing                                            | Input dimension                                                 | Primary evaluation                              |
| -------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------- | --------------------------------------------------------------- | ----------------------------------------------- |
| A        | LLTF decoding, amplitude, robust noise filtering, causal baseline-relative normalization | Time-defined event windows                           | Small feature vector, e.g. motion and relative subcarrier bands | LOSO grouped by physical event                  |
| B        | Consistent amplitude calibration, missing-packet/gap handling, per-channel scaling       | Fixed-duration time windows                          | Time×subcarrier, or derived compact subcarrier vector           | Compare to A using identical groups             |
| C        | A plus first difference, energy and temporal shape                                       | Multi-scale event context                            | Amplitude + delta/dynamic descriptors                           | Fall versus fast-sit/bend/jump hard negatives   |
| D        | Amplitude normalization, robust statistics                                               | Same window as A                                     | Statistical vector                                              | Measure whether temporal features add value     |
| E        | Amplitude and phase sanitization                                                         | Same event boundary and time windows                 | Combined amplitude/phase features                               | Same sessions plus phase repeatability test     |
| F        | Denoising + STFT/CWT or compact spectral energy                                          | Same event intervals                                 | Frequency/time-frequency matrix or vector                       | Compare full transform vs reduced band features |
| G        | Standardized raw amplitude tensor                                                        | Fixed time length and elapsed-time resampling policy | Time×subcarrier matrix                                          | Subject-held-out CNN vs A                       |
| H        | Same raw temporal matrix                                                                 | Fixed-length sequence                                | Time×feature sequence                                           | LOSO with macro-F1 and event metrics            |

The comparison must hold the recording and split strategy constant. Otherwise, it becomes impossible to conclude whether an improvement comes from the classifier, representation, preprocessing, or easier test data.

## **12.4 Recommended initial window experiment**

Do not select one duration from the literature and treat it as universally correct. Research uses windows from fractions of a second to multiple seconds, with different packet rates and sensor arrangements.

I recommend a deliberately small but informative grid:

| Window duration | Hop / stride | Question being tested                                                  |
| --------------- | ------------ | ---------------------------------------------------------------------- |
| 1 s             | 0.2 s        | Can a short transient be recognized quickly?                           |
| 2 s             | 0.2–0.5 s    | Does additional descent/impact context improve discrimination?         |
| 3 s             | 0.2–0.5 s    | Does a broader activity shape improve fall versus fast-sit separation? |
| 4 s             | 0.5 s        | Does a longer context reduce false alarms enough to justify latency?   |

These are **experimental candidates**, not literature-proven optimal parameters.

The window should be defined by elapsed packet time. A window with 24 frames can have different duration under a variable reception rate. Store both its actual start/end timestamps and its packet count. Exclude or explicitly mark a window whose acquisition gap makes its temporal content unreliable.

## **12.5 Correct labeling strategy for the project**

The project should preserve phase labels while training a binary output classifier.

Recommended internal data labels:

| Label             | Meaning                                                | Primary use                                                                     |
| ----------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------- |
| `NORMAL_STILL`    | Stationary ordinary state before an event              | Negative examples                                                               |
| `NORMAL_ACTIVITY` | Walking, turning, bending, sitting, etc.               | Hard-negative examples                                                          |
| `FALL_TRANSITION` | Actual uncontrolled descent/impact interval            | Positive training examples                                                      |
| `POST_FALL`       | Person remains down after the fall                     | Separate state/confirmation evaluation                                          |
| `RECOVERY`        | Person gets up or returns to normal                    | Recovery-state evaluation                                                       |
| `AMBIGUOUS`       | Window crosses a boundary or ground truth is uncertain | Exclude from primary supervised classifier or use as a separate rejection class |

For the binary classifier, `FALL_TRANSITION` is the principal positive class.

`POST_FALL` should not automatically be relabeled as `FALL_TRANSITION`. It may be used for event persistence or state verification, but it is not proof that the current window contains a fall.

This recommendation aligns with the earlier project analysis showing that post-fall state and fall-transition recognition are distinct tasks.&#x20;

Pasted markdown(6).md



# **13. Recommended training and validation pipeline**

The following pipeline is the most scientifically defensible starting point for a small dataset intended for WROOM-32 deployment.

**1. Record raw continuous CSI**

Preserve packet timestamps, sequence IDs, RF metadata, and original take/session identity.

**2. Annotate physical events**

Mark actual onset, impact, post-fall, recovery and activity labels using synchronized reference evidence.

**3. Assign independent group IDs**

Subject → environment → session → take → event. Prevent related takes from crossing the final test boundary.

**4. Split before derived samples**

Create train/validation/test groups before windowing, feature selection, PCA, or augmentation.

**5. Generate time-aware windows**

Build fixed elapsed-time windows; keep boundary-crossing samples marked ambiguous.

**6. Fit preprocessing on training data**

Fit normalization, PCA, feature selection and calibration only inside each training fold.

**7. Train candidate models**

Start with Logistic Regression and Linear SVM; add small nonlinear challengers.

**8. Evaluate windows and physical events separately**

Report grouped classification metrics, event recall, missed falls, false alarms per hour and latency.

### **13.1 Dataset splitting protocol**

For a dataset that is still small, use nested grouped evaluation:

- Outer split: hold out an entire subject, or an entire environment if that is the target question.
- Inner training validation: grouped cross-validation by session/take.
- Final test: run once after the candidate is selected.
- Keep the held-out subject/environment completely outside feature and threshold selection.

If there is currently only one subject, do not label a take-level split as subject-independent. State explicitly that the evaluation only tests generalization across takes within that person and room.

### **13.2 Training sample balancing**

The training set may use class weighting or controlled negative downsampling. But the test set should preserve a realistic distribution of ordinary activity and quiet monitoring periods.

Avoid SMOTE on overlapping windows from a handful of falls. It increases the number of synthetic feature vectors, not the number of independent physical fall events.

For a small MCU classifier, regularized Logistic Regression and Linear SVM are particularly appropriate baselines because their inference is a small number of weighted sums and comparisons. The choice between them should be decided by grouped validation, not by one random window test.

### **13.3 Model selection criteria**

Do not select the model by accuracy alone.

Use a selection objective that balances:

1. Fall-event recall.
2. False alarms per hour.
3. Fall-event precision.
4. Event latency.
5. Subject and environment stability.
6. Model size and measured MCU inference cost.

A model that detects every fall but raises several false alarms during ordinary activity may be unsuitable. A model that almost never alarms may report excellent specificity but miss serious events.

The practical goal is not to maximize one metric; it is to find an acceptable operating point for the intended environment.

# **14. Research gaps and limitations**

### **14.1 Weakly documented temporal ground truth**

Many CSI studies report how an activity was performed but not exactly how movement onset and impact timestamps were measured. The gap is particularly important for event-latency research.

### **14.2 Insufficient recording-level documentation**

Some studies report the number of samples and windows but not the mapping back to their original CSI files. This limits the ability to audit independent sample counts and prevent correlated-window leakage.

### **14.3 Insufficient reporting of split units**

A statement such as “random 80/20 split” is not enough. Authors should report whether the split happened by frame, window, recording, session, participant, or environment.

### **14.4 Insufficient real-time event metrics**

Window-level accuracy and recall are common. False alarms per hour, actual fall-event detection rates, latency measured from a physical onset, and long-duration monitoring are less consistently reported.

### **14.5 Hardware mismatch**

Most detailed CSI studies use Intel 5300 or Nexmon-capable platforms and multi-antenna configurations. Their subcarrier layout, sampling behavior, phase quality, and spatial diversity differ from a single-antenna ESP32-WROOM-32.

### **14.6 Deep-learning performance and dataset leakage**

Several high-performing deep CSI-HAR systems rely on sample-level partitions. The 2024 and 2025 analyses demonstrate how subject mixing can exaggerate results. This makes subject-independent validation a research requirement, not an optional enhancement.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www.mdpi.com\&sz=32)

mdpi.com+1



### **14.7 Specific gap in the current project**

The earlier project audit provides particularly relevant evidence:

- 89 takes, but only one subject and one room.
- Phase-aware labeling materially changes the count of valid fall-transition windows.
- All-window take-level `FALL` labels introduce substantial label noise.
- Baseline-relative features improve selected within-dataset comparisons, but absolute profiles can encode session fingerprints.
- Subject-independent validation is not possible without additional participants.

These results strongly support improving dataset structure before expanding model complexity.&#x20;

Pasted markdown(6).md



# **15. Final practical recommendations**

## **15.1 Recommended recording strategy**

Use a hybrid dataset:

**Controlled isolated takes** to collect sufficient repetitions of fall directions, ordinary movements and difficult negatives.

**Continuous mixed-activity takes** to establish whether event segmentation works and to calculate false alarms per hour.

Keep the original CSI recording intact. Store each annotated event as a timeline over that source recording. Do not destroy the pre-event or post-event data by keeping only the action segment.

## **15.2 Recommended sample-generation strategy**

For the first controlled comparison:

- Use elapsed-time windows rather than frame-count-only windows.
- Compare 1, 2, 3 and 4-second durations.
- Test 0.2–0.5-second hops.
- Generate windows separately after the original recording groups are split.
- Keep PRE, FALL_TRANSITION, POST_FALL, RECOVERY and AMBIGUOUS distinctions.
- Exclude ambiguous boundary windows from the primary binary model until a specific boundary-labeling strategy has been validated.

## **15.3 Recommended model experiments**

Prioritize:

1. Existing selected-amplitude handcrafted features + Linear SVM.
2. Same data plus causal baseline-relative features.
3. Amplitude and temporal-difference feature ablation.
4. Statistical-only control.
5. Full amplitude versus selected subcarrier comparison.
6. Phase branch as a separately validated experiment.
7. Compact frequency-domain features.
8. CNN/GRU only after the dataset grows.

This preserves scientific continuity with the existing project while permitting objective comparison of alternatives.

## **15.4 Prioritized roadmap**

| Priority | Work                                                          | Why it comes first                                                      | Completion evidence                                                      |
| -------- | ------------------------------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| 1        | Define dataset schema and IDs                                 | Needed to trace every sample back to its original recording and subject | Every CSI record has session/take/subject/environment IDs and timestamps |
| 2        | Establish physical event annotation                           | Prevents incorrect fall labels and enables latency measurement          | Onset/impact/post-fall/recovery annotations                              |
| 3        | Define controlled and continuous capture protocols            | Gives both isolated samples and realistic streams                       | Raw mixed stream plus annotated event takes                              |
| 4        | Verify data quality and temporal consistency                  | Avoids training on artificial timing or malformed CSI                   | Packet-gap, valid-frame and acquisition-rate report                      |
| 5        | Implement group-aware train/validation/test splitting offline | Prevents leakage                                                        | No take/event/subject group crosses the intended partition               |
| 6        | Generate and audit windows                                    | Ensures each sample has a defensible label                              | Window timeline, label distribution and boundary audit                   |
| 7        | Run feature and window ablations                              | Identifies useful information with small models                         | Same grouped folds across experiments                                    |
| 8        | Compare classical classifiers                                 | Establishes the simplest adequate model                                 | Event-level and window-level metrics                                     |
| 9        | Evaluate false alarms on continuous negative data             | Tests practical reliability                                             | False alarms per hour across hard negatives and stationary periods       |
| 10       | Profile candidate on WROOM-32                                 | Establishes whether research results transfer to target hardware        | Actual firmware inference timing and resource measurements               |

The first three steps have the highest research value. Changing a classifier before those are reliable risks optimizing the wrong training target.

# **16. Direct answers to the principal research questions**

| #  | Research question                                | Conclusion                                                                                                                                                                                              |
| -- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1  | How do researchers collect CSI?                  | Through controlled transmitter/receiver links, typically with repeated activity protocols or longer continuous recordings; some work uses Intel 5300, while newer work uses Nexmon and other platforms. |
| 2  | Does one recording contain one activity or many? | Both formats exist. RT-Fall and Anti-Fall use mixed continuous streams; Chu uses longer files with repeated instances of one activity; TCS-Fall uses both isolated and continuous recordings.           |
| 3  | How are boundaries identified?                   | CSI segmentation, video synchronization, observer assessment, activity protocols and recording markers. Exact frame-level physical boundaries are often NOT REPORTED.                                   |
| 4  | Are entire recordings used?                      | Raw recordings may be retained, but classifiers commonly receive extracted segments, fixed windows, or derived tensors.                                                                                 |
| 5  | How are training samples generated?              | Through fixed-time windows, activity-specific segments, STFT/scalogram representations or statistical feature aggregation.                                                                              |
| 6  | What preprocessing is applied?                   | Amplitude extraction, filtering, interpolation, denoising, normalization, PCA, downsampling and time-frequency transforms. Exact choices vary.                                                          |
| 7  | How many subcarriers are used?                   | From four selected subcarriers in Anti-Fall to 30 CSI groups across multiple antennas in Intel 5300 studies, or 256 initial subcarriers in an 80 MHz Nexmon study.                                      |
| 8  | Handcrafted features or raw CSI?                 | Classical ML typically uses handcrafted features; deep systems commonly use temporal matrices, images or 3D representations.                                                                            |
| 9  | How are datasets split?                          | Practices vary. Subject-ID grouping is documented in TCS-Fall; several other studies use random sample/window folds or insufficiently documented splits.                                                |
| 10 | Are their evaluations reliable?                  | Not uniformly. Subject and event independence, original-record grouping, long-duration false alarms and latency are often insufficiently reported.                                                      |
| 11 | Most important risk?                             | Labeling every window from a fall take as FALL, and random splitting correlated overlapping windows.                                                                                                    |
| 12 | Best pipeline for a small MCU dataset?           | Preserve raw continuous CSI and annotations; generate time-aware labeled windows; use compact amplitude/delta/baseline-relative features; train regularized linear classifiers with grouped validation. |

# **17. Final conclusion**

The literature does not support the idea that a Wi-Fi CSI fall-detection dataset should simply consist of one file per class, one label per file, and an arbitrary number of sliding windows. Some successful systems record continuous activity and detect events inside the stream; others capture repeated isolated actions and cut activity segments afterward. A scientifically defensible project should preserve both the original recording and the mapping between every generated sample and its physical event.

For the ESP32-WROOM-32 project, the most important decisions are:

1. **Record continuous raw CSI with timestamps and stable identifiers.**
2. **Annotate actual physical phases rather than relying only on the activity instruction or take name.**
3. **Separate FALL_TRANSITION from POST_FALL and RECOVERY.**
4. **Split at the original recording/event/subject level before generating overlapping windows or augmented representations.**
5. **Compare time-aware windows and feature sets on identical grouped splits.**
6. **Retain simple classical ML as the deployment baseline and evaluate it using event-level outcomes.**

The earlier project dataset audit already shows why these choices matter: take-level labels produced misleading FALL windows, baseline-relative features gave a promising within-dataset improvement, and absolute profiles were vulnerable to session identity effects. Those results justify a better dataset protocol, but do not yet demonstrate unseen-subject or unseen-room performance.&#x20;

Pasted markdown(6).md



**My strongest recommendation is therefore to treat the original CSI recording and event timeline as the authoritative dataset, with every feature vector, image, and training window stored as a reproducible derivative.** This creates a defensible foundation for comparing Linear SVM, Logistic Regression, Random Forest, CNN and GRU approaches without confounding their results with differences in recording, labels or split methodology.

# **18. Bibliography and source links**

### **Original fall-detection studies**

1. Han et al. (2014), *WiFall: Device-Free Fall Detection by Wireless Networks*. IEEE INFOCOM. [DOI](https://doi.org/10.1109/INFOCOM.2014.6847948?utm_source=chatgpt.com).
2. Zhang et al. (2015), *Anti-Fall: A Non-intrusive and Real-time Fall Detector Leveraging CSI from Commodity WiFi Devices*. [DOI](https://doi.org/10.1007/978-3-319-19312-0_15?utm_source=chatgpt.com).
3. Wang et al. (2017), *RT-Fall: A Real-Time and Contactless Fall Detection System with Commodity WiFi Devices*. IEEE Transactions on Mobile Computing. [DOI](https://doi.org/10.1109/TMC.2016.2557795?utm_source=chatgpt.com).
4. Palipana (2019), *Fall Detection Using Channel State Information from WiFi Devices*. Cork Institute of Technology doctoral dissertation.
5. Damodaran et al. (2020), *Device Free Human Activity and Fall Recognition Using WiFi Channel State Information (CSI)*. [DOI](https://doi.org/10.1007/s42486-020-00027-1?utm_source=chatgpt.com).
6. Nakamura et al. (2022), *Wi-Fi-Based Fall Detection Using Spectrogram Image of CSI*. IEEE Internet of Things Journal. [DOI](https://doi.org/10.1109/JIOT.2022.3152315?utm_source=chatgpt.com).
7. Surasakhon et al. (2022), *Early Detection of a Fall Using Wi-Fi and Deep Learning*. International Journal of Sensor Networks. [DOI](https://doi.org/10.1504/IJSNET.2022.127111?utm_source=chatgpt.com).
8. El-Sayed et al. (2022), *Utilizing Deep Learning Models in CSI-Based Human Activity Recognition*. Neural Computing and Applications. [DOI](https://doi.org/10.1007/s00521-021-06787-w?utm_source=chatgpt.com).
9. Mattela et al. (2022), *A Novel Approach in WiFi CSI-Based Fall Detection*. SN Computer Science. [DOI](https://doi.org/10.1007/s42979-022-01111-2?utm_source=chatgpt.com).
10. Chu et al. (2023), *Deep Learning-Based Fall Detection Using WiFi Channel State Information*. IEEE Access. [DOI](https://doi.org/10.1109/ACCESS.2023.3300726?utm_source=chatgpt.com). [Open manuscript](https://eprints.whiterose.ac.uk/id/eprint/202278/?utm_source=chatgpt.com).
11. Islam et al. (2023), *STC-NLSTMNet: An Improved Human Activity Recognition Method Using Convolutional Neural Network with NLSTM from WiFi CSI*. Sensors. [DOI](https://doi.org/10.3390/s23010356?utm_source=chatgpt.com).
12. Zhou et al. (2024), *TCS-Fall: Cross-Individual Fall Detection System Based on Channel State Information and Time-Continuous Stack Method*. Digital Health. [DOI](https://doi.org/10.1177/20552076241259047?utm_source=chatgpt.com).
13. Chen et al. (2025), *DapFall: Dynamic Amplitude Probability Density Profile-Based Wi-Fi CSI Sensing for Fall Detection*. IEEE Sensors Journal. [DOI](https://doi.org/10.1109/JSEN.2025.3544552?utm_source=chatgpt.com).
14. Kim et al. (2025), *AmFall: WiFi CSI Amplitude-Based Fall Detection Using Denoised Scalograms*. IEEE Internet of Things Journal. [DOI](https://doi.org/10.1109/JIOT.2025.3585401?utm_source=chatgpt.com).
15. *A Mobile Receiver WiFi-CSI Approach for Fall Detection of Construction Workers* (2025). Developments in the Built Environment. [DOI](https://doi.org/10.1016/j.dibe.2025.100745?utm_source=chatgpt.com).
16. *Adaptive Fall Detection Using WiFi CSI for Unseen Environments and New Individuals* (2025). IEEE MeMeA. [DOI](https://doi.org/10.1109/MeMeA65319.2025.11068083?utm_source=chatgpt.com).
17. *Real-Time, Non-Intrusive Fall Detection via Wi-Fi CSI: A Comparative Study of CNN-LSTM, GNN, and Transformer Models* (2025). IntechOpen. [DOI](https://doi.org/10.5772/acrt20250099?utm_source=chatgpt.com).

### **Dataset methodology and leakage studies**

18. Varga (2024), *Critical Analysis of Data Leakage in WiFi CSI-Based Human Action Recognition Using CNNs*. Sensors. [DOI](https://doi.org/10.3390/s24103159?utm_source=chatgpt.com).
19. Varga and Cao (2025), *Why Partitioning Matters: Revealing Overestimated Performance in WiFi-CSI-Based Human Action Recognition*. Signals. [DOI](https://doi.org/10.3390/signals6040059?utm_source=chatgpt.com).

### **Project-specific prior evidence**

20\. Previous project dataset audit and feature/labeling evaluation, November 2026.&#x20;

Pasted markdown(6).md



**Evidence limitation:** the papers listed as having inaccessible or incomplete method details have been included to document the research landscape, but their missing recording, segmentation, or split information has deliberately been marked NOT REPORTED or UNKNOWN. They should not be used as reproducible implementation templates without obtaining and examining the full methods and, where possible, source datasets.

The most valuable next research artifact for the project is a **dataset specification and annotation protocol** that fixes the recording IDs, physical event timestamps, window labels, and group-based split rules before any additional model training is performed.