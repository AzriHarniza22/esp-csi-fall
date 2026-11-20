# Deep Research: Wi‑Fi CSI Fall Detection — Literature vs Project Codebase

**Executive summary:** Literatur CSI fall detection umumnya memakai recording per aktivitas, memotongnya menjadi window tetap (sering 1–3 detik), mengekstrak fitur amplitude/phase per subcarrier atau per link, lalu melatih SVM/CNN/LSTM dengan split yang menjaga recording atau subjek agar tidak bocor. Namun, **codebase proyek tidak tersedia di lingkungan kerja saat ini** (`/home/user` hanya berisi `workspace/` kosong dan `output/`), sehingga seluruh bagian audit kode, jumlah recording, label, windowing, preprocessing, dan artefak model harus ditandai **TIDAK DIKETAHUI** sampai file proyek diunggah atau repositori dihubungkan. [dl.acm](https://dl.acm.org/doi/abs/10.1109/TMC.2016.2557795)

## Batasan audit codebase

Saya melakukan pemeriksaan read-only terhadap direktori kerja dan tidak menemukan source code, dataset, metadata, script training, artefak model, maupun laporan eksperimen. Tidak ada connector GitHub/filesystem yang tersedia, sehingga saya tidak dapat memverifikasi jalur file, nama fungsi, nomor baris, jumlah sampel, distribusi kelas, maupun implementasi 16 fitur.

Untuk menyelesaikan Bagian 2–4 secara faktual, diperlukan salah satu dari berikut:

- Upload arsip proyek (`zip`/`tar.gz`) atau folder proyek.
- Hubungkan repositori GitHub/GitLab.
- Sediakan minimal: `README`, training scripts, dataset CSV/NPY/JSON, metadata annotation, model artifacts, firmware inference source, dan laporan eksperimen.

Semua klaim tentang pipeline proyek di bawah ini bersifat **belum terverifikasi**, bukan fakta audit.

## Paper yang ditinjau

| Paper | Fokus | Sumber |
|---|---|---|
| **WiFall** — Wang et al., 2017 | Fall detection berbasis anomali CSI dan fitur statistik + one-class SVM | DOI/rujukan tersedia melalui tinjauan literatur; detail asli perlu PDF penuh.  [link.springer](https://link.springer.com/article/10.1007/s42486-020-00027-1) |
| **RT-Fall** — Wang et al., 2017 | Segmentasi dan deteksi jatuh real-time memakai phase difference dan time-frequency CSI | ACM/IEEE, DOI tersedia pada hasil pencarian.  [dl.acm](https://dl.acm.org/doi/abs/10.1109/TMC.2016.2557795) |
| **Anti-Fall** — 2015 | Deteksi jatuh non-intrusive memakai CSI commodity Wi‑Fi; memilih 4 subcarrier dari 30 | PDF paper tersedia.  [www-public.imtbs-tsp](https://www-public.imtbs-tsp.eu/~zhang_da/pub/Daqing%202015%20ICOST%20Anti-fall.pdf) |
| **SiFall** — 2023 | Fall detection online; denoising, dynamic component, STFT | arXiv.  [arxiv](https://arxiv.org/html/2301.03773) |
| **Damodaran et al., 2020** | Device-free HAR/fall recognition berbasis CSI | Springer, DOI tersedia.  [link.springer](https://link.springer.com/article/10.1007/s42486-020-00027-1) |
| **Chu et al., 2023** | Deep learning CSI fall detection | Perlu PDF penuh untuk verifikasi detail; tidak ditemukan pada hasil terbatas ini. |
| **WiBFall** — 2021 | Fall detection bathroom; membandingkan SVM dan Random Forest | PDF EUDL.  [eudl](https://eudl.eu/pdf/10.1007/978-3-030-94763-7_14) |
| **CSI fall detection dengan adversarial augmentation** — 2020 | Weighted moving average, 7 fitur manual, SVM biner | arXiv.  [arxiv](https://arxiv.org/html/2005.11932v1) |
| **Self-supervised CSI HAR** — 2025 | Intel 5300 NIC, 30 subcarrier, phase conjugate multiplication, mean pooling | ACM.  [dl.acm](https://dl.acm.org/doi/10.1145/3715130) |
| **Proof-of-concept CSI fall detection** — 2026 | Amplitude, DWT Symlet-10, z-score, fixed segmentation, window 5 s | arXiv.  [arxiv](https://arxiv.org/html/2611.15532v1) |
| **CSI HAR dengan Butterworth filter** | Low-pass 100 Hz, window optimization \(w=20\) | PMC PDF.  [pmc.ncbi.nlm.nih](https://pmc.ncbi.nlm.nih.gov/articles/PMC11151769/pdf/10.1177_20552076241259047.pdf) |
| **CSI HAR dengan 15 subcarrier acak** | Weighted moving average, 15 dari 30 subcarrier, SVM | Semantic Scholar PDF.  [pdfs.semanticscholar](https://pdfs.semanticscholar.org/e66d/36c8203376ba7b801eb453b54806ea03f96b.pdf) |

## Pengambilan dataset

### Pola umum

Sebagian besar sistem menggunakan **satu recording per aktivitas**: subjek diberi instruksi untuk melakukan satu aktivitas—misalnya berjalan, duduk, berdiri, atau jatuh—lalu perekaman dihentikan. Beberapa sistem juga merekam kondisi ruangan kosong sebagai baseline/non-activity. [arxiv](https://arxiv.org/html/2611.15532v1)

Protokol yang paling umum adalah:

1. Subjek memasuki area monitoring atau sudah berada dalam posisi awal.
2. Terdapat jeda diam sebelum gerakan, meskipun tidak semua paper menyebut durasi PRE secara eksplisit.
3. Subjek melakukan aktivitas sesuai instruksi.
4. Perekaman berhenti setelah aktivitas selesai atau setelah jeda POST.
5. Aktivitas diberi label berdasarkan protokol eksperimen, kadang dibantu video atau observasi manual.

**Fakta:** RT-Fall menekankan segmentasi otomatis agar pengguna dapat melakukan aktivitas harian secara kontinu, tetapi ini berarti sistemnya tidak bergantung pada satu recording yang berisi tepat satu aktivitas. [dl.acm](https://dl.acm.org/doi/abs/10.1109/TMC.2016.2557795)

**TIDAK DIKETAHUI untuk sebagian besar paper:** apakah timestamp instruksi disimpan, apakah event marker ditulis ke file CSI, dan apakah batas PRE/POST dicatat manual. Informasi ini sering tidak muncul pada abstrak maupun cuplikan paper; harus diverifikasi dari bagian eksperimen, supplementary material, atau repository resmi.

### Hardware dan subcarrier

| Paper | Hardware/chipset | Subcarrier | Link/antenna | Catatan |
|---|---|---:|---:|---|
| RT-Fall | Commodity Wi‑Fi CSI | TIDAK DIKETAHUI dari cuplikan | Memakai phase difference antar dua Rx antenna | Phase difference dipakai sebagai sinyal dasar segmentasi.  [dl.acm](https://dl.acm.org/doi/abs/10.1109/TMC.2016.2557795) |
| Anti-Fall | Commodity Wi‑Fi CSI | 30 tersedia; 4 dipilih | TIDAK DIKETAHUI | Empat subcarrier dipilih merata dari 30 subcarrier.  [www-public.imtbs-tsp](https://www-public.imtbs-tsp.eu/~zhang_da/pub/Daqing%202015%20ICOST%20Anti-fall.pdf) |
| Self-supervised HAR | Intel 5300 NIC | 30 per packet | Tiga pasang antenna | Phase dikoreksi dengan conjugate multiplication.  [dl.acm](https://dl.acm.org/doi/10.1145/3715130) |
| Proof-of-concept 2026 | TIDAK DIKETAHUI | TIDAK DIKETAHUI | TIDAK DIKETAHUI | Menggunakan amplitude, DWT, z-score, window 5 detik.  [arxiv](https://arxiv.org/html/2611.15532v1) |
| CSI HAR 15-subcarrier | TIDAK DIKETAHUI | 30 tersedia; 15 dipilih acak | TIDAK DIKETAHUI | 15 subcarrier dipilih untuk mencocokkan 15 joint Kinect.  [pdfs.semanticscholar](https://pdfs.semanticscholar.org/e66d/36c8203376ba7b801eb453b54806ea03f96b.pdf) |

**Interpretasi:** banyak paper tidak memakai seluruh 30 subcarrier. Anti-Fall memilih hanya 4 subcarrier, sedangkan paper HAR lain memilih 15. Pemilihan subcarrier dapat mengurangi noise dan dimensi, tetapi juga membuang informasi spasial/frekuensi jika dilakukan terlalu agresif. [www-public.imtbs-tsp](https://www-public.imtbs-tsp.eu/~zhang_da/pub/Daqing%202015%20ICOST%20Anti-fall.pdf)

## Batas aktivitas dan anotasi

### Bagaimana paper menentukan onset dan akhir aktivitas

- **RT-Fall** tidak bergantung pada batas manual per recording: sistem melakukan segmentasi otomatis secara real-time. Ia memakai phase difference dua antenna sebagai sinyal segmentasi dan pola penurunan power profile di domain time-frequency untuk mendeteksi segmen jatuh. [dl.acm](https://dl.acm.org/doi/abs/10.1109/TMC.2016.2557795)
- **SiFall** mengekstrak komponen dinamis CSI, lalu mengambil sinyal \(S(t)\) pada interval \([t_{\max}-3s, t_{\text{end}}^*]\) dan menerapkan STFT untuk menemukan segmen mirip jatuh. Ini menunjukkan bahwa onset dan akhir event dideteksi dari sinyal, bukan semata dari label recording. [arxiv](https://arxiv.org/html/2301.03773)
- **Proof-of-concept 2026** memakai window tetap 5 detik per sampel jatuh/berjalan; ini mengimplikasikan label per window atau per sampel, bukan hanya label per recording. [arxiv](https://arxiv.org/html/2611.15532v1)
- **Paper lain** umumnya menggunakan label per recording ketika satu recording memang hanya memuat satu aktivitas. Dalam kasus itu, seluruh isi recording dapat diberi label aktivitas tersebut, atau bagian tertentu dipotong menjadi window dengan label yang sama.

**Fakta:** RT-Fall dan SiFall memakai deteksi/segmentasi berbasis sinyal. **TIDAK DIKETAHUI** apakah mereka menyimpan video ground truth, cue timestamp, atau event marker dalam file CSI berdasarkan bukti yang tersedia.

### PRE, GERAKAN, IMPACT, POST

Tidak ada bukti dari cuplikan yang menunjukkan skema label empat fase—PRE, GERAKAN, IMPACT, POST—sebagai standar di paper-paper tersebut. RT-Fall memisahkan **fall-like segment** dari aktivitas lain melalui segmentasi otomatis; SiFall juga mencari segmen fall-like, tetapi tidak terlihat adanya label formal PRE/POST. [dl.acm](https://dl.acm.org/doi/abs/10.1109/TMC.2016.2557795)

**Interpretasi:** pipeline yang memaksa setiap recording memiliki fase PRE/GERAKAN/POST dapat lebih ketat daripada banyak paper. Jika annotation fase tidak lengkap atau tidak konsisten, sistem berisiko menghasilkan label window yang tidak merepresentasikan event jatuh secara akurat.

## Pembentukan sampel training

### Fixed window vs full recording

| Pendekatan | Paper/contoh | Window | Stride/overlap | Konsekuensi |
|---|---|---:|---:|---|
| Full recording sebagai satu sampel | Umum pada klasifikasi aktivitas tunggal | Satu recording | Tidak berlaku | Jumlah sampel sangat kecil; sensitif terhadap durasi dan noise |
| Fixed-length window | RT-Fall, SiFall, proof-of-concept | RT-Fall 3 s; SiFall 3 s; proof-of-concept 5 s | TIDAK DIKETAHUI untuk stride | Memungkinkan banyak sampel per recording dan evaluasi event-level.  [dl.acm](https://dl.acm.org/doi/abs/10.1109/TMC.2016.2557795) |
| Window berbasis event | SiFall | Sekitar 3 detik sekitar event | TIDAK DIKETAHUI | Lebih sesuai untuk deteksi jatuh karena memusatkan perhatian pada onset/impact.  [arxiv](https://arxiv.org/html/2301.03773) |
| Mean pooling ke panjang tetap | Self-supervised HAR | Panjang target tetap | TIDAK DIKETAHUI | Menyeragamkan panjang sequence tanpa membuang seluruh recording.  [dl.acm](https://dl.acm.org/doi/10.1145/3715130) |

**Fakta:** RT-Fall memakai fixed 3-second window untuk segmentasi dan deteksi.  Proof-of-concept menggunakan activity window 5 detik. [arxiv](https://arxiv.org/html/2301.03773)

**Contoh transformasi recording:**

Misalkan sebuah recording jatuh berdurasi 10 detik dengan sampling efektif 100 packet/detik:

- Full recording: 1 sampel, 1.000 frame.
- Window 3 detik tanpa overlap: 3 window penuh, masing-masing 300 frame; 100 frame terakhir mungkin dibuang.
- Window 3 detik, stride 1 detik: 8 window; label masing-masing ditentukan oleh fase dominan atau event yang tercakup.
- Window event-centered: satu window 3 detik dipusatkan pada onset/impact; window sebelum dan sesudah dapat menjadi negative atau dibuang.

**TIDAK DIKETAHUI:** bagaimana paper menangani window yang melintasi batas dua aktivitas. Beberapa kemungkinan yang umum adalah memberi label mayoritas, membuang window ambigu, atau hanya menggunakan window yang sepenuhnya berada dalam satu segmen; ini harus diverifikasi dari kode atau supplementary masing-masing paper.

## Preprocessing CSI

### Tahapan yang lazim

| Tahap | Tujuan | Rumus/operasi umum | Posisi terhadap windowing |
|---|---|---|---|
| CSI decoding | Mengubah packet CSI mentah menjadi amplitude dan phase | \(A_{k,t}=|H_{k,t}|\), \(\phi_{k,t}=\arg(H_{k,t})\) | Biasanya sebelum windowing |
| Invalid frame removal | Membuang packet rusak, timestamp tidak valid, atau CSI nol | Filter berbasis validitas header/timestamp | Sebelum windowing |
| Phase sanitization | Menghilangkan offset dan unwrap | Regresi linear phase terhadap subcarrier/time; unwrap | Sebelum windowing |
| Denoising | Menekan noise high-frequency | Moving average, Butterworth, wavelet | Bisa sebelum atau sesudah windowing |
| Outlier removal | Menghapus spike lokal | Hampel filter, median absolute deviation | Umumnya sebelum windowing |
| Normalization | Menyeragamkan skala antar subjek/link | Z-score: \((x-\mu)/\sigma\) | Harus fit hanya dari training |
| Baseline subtraction | Menghilangkan komponen statis ruangan | \(x' = x - \text{baseline}\) | Sebelum windowing |
| PCA | Mereduksi dimensi dan noise | Proyeksi ke komponen utama | Setelah ekstraksi fitur/window |
| Subcarrier selection | Memilih subcarrier informatif | Variance, energy, atau pemilihan merata | Sebelum feature extraction |
| Temporal smoothing | Menstabilkan sinyal | Weighted moving average | Sebelum/sesudah windowing |
| Time-frequency | Menangkap pola jatuh | STFT/DWT | Setelah segmentasi/windowing |

### Bukti spesifik

- **RT-Fall** memakai phase difference antar dua antenna dan fitur statistik phase/amplitude dari segmen CSI; sistem juga mengeksploitasi pola time-frequency. [dl.acm](https://dl.acm.org/doi/abs/10.1109/TMC.2016.2557795)
- **Anti-Fall** memilih 4 dari 30 subcarrier yang tersebar merata. [www-public.imtbs-tsp](https://www-public.imtbs-tsp.eu/~zhang_da/pub/Daqing%202015%20ICOST%20Anti-fall.pdf)
- **Adversarial augmentation paper** memakai weighted moving average untuk meredam noise, lalu 7 fitur manual dan SVM biner. [arxiv](https://arxiv.org/html/2005.11932v1)
- **Proof-of-concept 2026** memakai amplitude, second-level discrete wavelet transform dengan Symlet-10, z-score normalization, dan fixed-length segmentation. [arxiv](https://arxiv.org/html/2611.15532v1)
- **Paper HAR** memakai Butterworth low-pass 100 Hz dan mengoptimasi window \(w=20\). [pmc.ncbi.nlm.nih](https://pmc.ncbi.nlm.nih.gov/articles/PMC11151769/pdf/10.1177_20552076241259047.pdf)
- **Paper 15-subcarrier** memakai weighted moving average sebagaimana WiFall, lalu memilih 15 subcarrier. [pdfs.semanticscholar](https://pdfs.semanticscholar.org/e66d/36c8203376ba7b801eb453b54806ea03f96b.pdf)

**Prinsip anti-leakage:** mean, standard deviation, PCA, feature selection, dan threshold yang dihitung dari seluruh dataset akan menyebabkan preprocessing leakage bila diterapkan sebelum train/test split. Parameter harus di-fit pada training fold saja, lalu diterapkan tanpa refit ke validation/test.

## Fitur dan dimensi input

### Pembedaan yang penting

- **Jumlah subcarrier**: misalnya 30.
- **Jumlah jenis fitur**: misalnya mean, variance, entropy, dsb.
- **Jumlah dimensi input**: jumlah jenis fitur dikalikan jumlah subcarrier dan/atau link.

Contoh: jika terdapat 30 subcarrier, 2 link, dan 7 jenis fitur, maka dimensi fitur adalah:

\[
D = 30 \times 2 \times 7 = 420
\]

Bukan 7 fitur.

### Contoh dari literatur

| Paper | Jenis fitur | Subcarrier | Dimensi final | Catatan |
|---|---:|---:|---:|---|
| WiFall | 7 jenis fitur statistik | TIDAK DIKETAHUI dari cuplikan | TIDAK DIKETAHUI | Normalized std, offset signal strength, motion period, MAD, IQR, signal entropy, velocity of signal change; one-class SVM.  [link.springer](https://link.springer.com/article/10.1007/s42486-020-00027-1) |
| RT-Fall | Statistik phase dan amplitude; fitur time-frequency | TIDAK DIKETAHUI | TIDAK DIKETAHUI | Phase difference dua antenna; segmentasi 3 detik.  [dl.acm](https://dl.acm.org/doi/abs/10.1109/TMC.2016.2557795) |
| Anti-Fall | TIDAK DIKETAHUI dari cuplikan | 4 dari 30 | TIDAK DIKETAHUI | Seleksi merata 4 subcarrier.  [www-public.imtbs-tsp](https://www-public.imtbs-tsp.eu/~zhang_da/pub/Daqing%202015%20ICOST%20Anti-fall.pdf) |
| Adversarial augmentation | 7 jenis fitur manual | TIDAK DIKETAHUI | TIDAK DIKETAHUI | SVM biner.  [arxiv](https://arxiv.org/html/2005.11932v1) |
| Self-supervised HAR | Raw CSI amplitude dan phase | 30 | TIDAK DIKETAHUI | Mean pooling untuk panjang tetap.  [dl.acm](https://dl.acm.org/doi/10.1145/3715130) |
| Proof-of-concept 2026 | Amplitude + DWT | TIDAK DIKETAHUI | TIDAK DIKETAHUI | Window 5 detik.  [arxiv](https://arxiv.org/html/2611.15532v1) |

**Fakta:** RT-Fall menggunakan amplitude **dan** phase, dengan phase difference yang disebut lebih sensitif untuk segmentasi.  **Interpretasi:** model yang hanya memakai amplitude berpotensi kehilangan informasi gerakan, terutama bila amplitude dipadatkan menjadi sangat sedikit fitur. [dl.acm](https://dl.acm.org/doi/abs/10.1109/TMC.2016.2557795)

## Training dan evaluasi

### Algoritma

- **WiFall**: one-class SVM berbasis anomali. [link.springer](https://link.springer.com/article/10.1007/s42486-020-00027-1)
- **RT-Fall**: SVM dengan fitur phase/amplitude hasil segmentasi. [arxiv](https://arxiv.org/html/2301.03773)
- **WiBFall**: SVM dan Random Forest. [eudl](https://eudl.eu/pdf/10.1007/978-3-030-94763-7_14)
- **Adversarial augmentation**: SVM biner. [arxiv](https://arxiv.org/html/2005.11932v1)
- **Deep learning CSI**: CNN/LSTM/GRU/hybrid umumnya menerima matrix raw CSI atau fitur time-frequency; detail Chu et al. 2023 belum terverifikasi dari hasil terbatas ini.

### Split dan leakage

Praktik yang baik dalam paper CSI adalah split berdasarkan **recording** atau **subjek**, bukan hanya window. Jika window dari recording yang sama masuk ke train dan test, model dapat mengenali noise, posisi perangkat, dan pola environment spesifik recording tersebut.

**Fakta:** tidak ada bukti pada cuplikan bahwa semua paper memakai leave-one-subject-out. **TIDAK DIKETAHUI** untuk detail split masing-masing paper tanpa membaca bagian eksperimen lengkap.

### Metrik

Metrik yang relevan untuk fall detection meliputi:

- Window-level accuracy, precision, recall, F1.
- Fall recall: proporsi window/event jatuh yang terdeteksi.
- Specificity dan false-positive rate pada NON_FALL.
- Macro-F1 bila kelas tidak seimbang.
- Event-level detection rate: satu jatuh dihitung benar bila minimal satu window terdeteksi.
- Detection latency: selisih waktu antara onset/impact jatuh dan alarm pertama.

**Interpretasi:** akurasi window-level saja dapat menyesatkan. Pada dataset dengan banyak NON_FALL, model yang jarang memprediksi FALL dapat memiliki akurasi tinggi tetapi recall jatuh rendah.

## Audit aktual codebase

### Status

**TIDAK DIKETAHUI.** Codebase tidak ditemukan pada workspace aktif. Oleh karena itu, saya tidak dapat memverifikasi:

- Jumlah recording FALL dan NON_FALL.
- Jenis aktivitas dan durasi recording.
- Format CSI serta timestamp.
- Keberadaan `fall_start`, `fall_impact`, cue timestamp, atau manual annotation.
- Window length, stride, overlap, dan jumlah frame per window.
- Implementasi 16 fitur.
- Normalisasi, scaling, feature selection, dan split.
- Artefak Linear SVM, Phase-Aware Linear SVM, model label 4–8 atau 4–9.
- Firmware compatibility dan kesesuaian preprocessing training vs firmware.

### Pertanyaan audit yang harus dijawab dari kode

| Pertanyaan | Bukti yang diperlukan |
|---|---|
| Berapa recording dan distribusi kelas? | Dataset manifest, folder raw, metadata CSV/JSON |
| Apakah PRE/GERAKAN/POST lengkap? | Annotation file dan timestamp |
| Bagaimana FALL window dibentuk? | Fungsi windowing/training script |
| Bagaimana NON_FALL window dibentuk? | Fungsi windowing/training script |
| Apakah window melintasi fase? | Logika label assignment |
| Bagaimana 16 fitur dibentuk? | Fungsi feature extraction |
| Apakah memakai amplitude, phase, atau difference? | Fungsi feature extraction |
| Apakah scaler di-fit dari train saja? | Pipeline/scaler serialization |
| Apakah split grouped by recording/subjek? | Split logic dan fold IDs |
| Apakah evaluasi event-level? | Evaluation script dan confusion matrix |
| Apakah preprocessing firmware sama? | Firmware inference source dan model metadata |

## Perbandingan paper vs codebase

| Aspek | Metodologi paper | Codebase kita | Perbedaan | Dampak potensial |
|---|---|---|---|---|
| CSI hardware | Intel 5300, Atheros, atau perangkat commodity; sering 30 subcarrier | TIDAK DIKETAHUI | Perlu verifikasi chipset, bandwidth, antenna, dan format CSI | Perbedaan noise floor, jumlah subcarrier, dan phase quality dapat mengubah performa |
| Recording | Umumnya satu aktivitas per recording; beberapa sistem continuous | TIDAK DIKETAHUI | Perlu tahu apakah satu file memuat banyak aktivitas | Multi-activity per file menuntut segmentasi dan label temporal |
| Activity marker | RT-Fall/SiFall mendeteksi event dari sinyal; lainnya sering memakai protokol/manual | TIDAK DIKETAHUI | Perlu cek cue timestamp dan manual annotation | Label salah menyebabkan window FALL/NON_FALL tidak representatif |
| Segmentasi | Fixed window 3–5 detik atau event-centered | TIDAK DIKETAHUI | Perlu cek window length/stride | Window terlalu panjang dapat mencampur PRE/POST; terlalu pendek dapat kehilangan konteks |
| Labeling | Per recording atau per window | TIDAK DIKETAHUI | Perlu cek label per window | Window ambigu harus dibuang atau diberi aturan eksplisit |
| Preprocessing | Denoise, phase sanitize, normalize, filter, PCA | TIDAK DIKETAHUI | Perlu cek urutan dan parameter | Preprocessing berbeda antara training dan firmware menyebabkan distribution shift |
| Subcarrier | 4–30 subcarrier | TIDAK DIKETAHUI | Perlu cek jumlah dan metode seleksi | Reduksi terlalu agresif dapat membuang informasi gerakan |
| Amplitude/phase | Banyak paper memakai keduanya; RT-Fall menonjolkan phase difference | TIDAK DIKETAHUI | Perlu cek fitur | Tanpa phase, informasi motion dapat berkurang |
| Feature extraction | Manual statistical, time-frequency, atau raw CSI | TIDAK DIKETAHUI | Perlu cek 16 fitur | Reduksi seluruh window ke 16 angka dapat membuang pola temporal |
| Algoritma | SVM, RF, CNN, LSTM/GRU | TIDAK DIKETAHUI | Perlu inventaris artefak | Model tidak dapat dibandingkan bila dataset/split/label berbeda |
| Class balancing | TIDAK DIKETAHUI secara seragam | TIDAK DIKETAHUI | Perlu cek class weight/oversampling | FALL minoritas berisiko memiliki recall rendah |
| Split | Recording/subject-aware ideal | TIDAK DIKETAHUI | Perlu cek grouped split | Window leakage dapat membuat metrik terlalu optimis |
| Evaluation | Window dan event-level | TIDAK DIKETAHUI | Perlu cek metrik | Akurasi window tidak menjamin deteksi event jatuh |
| Deployment | Real-time segmentasi pada RT-Fall/SiFall | TIDAK DIKETAHUI | Perlu cek firmware pipeline | Ketidakcocokan preprocessing menyebabkan performa runtime turun |

## Kelemahan potensial pipeline

### Fakta yang terbukti dari literatur

- Fixed window 3 detik dipakai RT-Fall untuk segmentasi dan deteksi. [arxiv](https://arxiv.org/html/2301.03773)
- Phase difference antar antenna merupakan sinyal penting pada RT-Fall. [dl.acm](https://dl.acm.org/doi/abs/10.1109/TMC.2016.2557795)
- Anti-Fall hanya memakai 4 subcarrier dari 30. [www-public.imtbs-tsp](https://www-public.imtbs-tsp.eu/~zhang_da/pub/Daqing%202015%20ICOST%20Anti-fall.pdf)
- Weighted moving average dan fitur statistik manual masih umum pada SVM-based CSI fall detection. [arxiv](https://arxiv.org/html/2005.11932v1)
- Time-frequency representation seperti STFT/DWT dipakai untuk menangkap pola jatuh. [dl.acm](https://dl.acm.org/doi/abs/10.1109/TMC.2016.2557795)
- Normalisasi harus dihitung dari training set untuk mencegah leakage; ini merupakan prinsip metodologis, bukan klaim bahwa semua paper melakukannya dengan benar.

### Interpretasi

- Jika pipeline proyek mereduksi seluruh window menjadi 16 angka, informasi temporal dan frekuensi kemungkinan besar berkurang dibandingkan raw CSI matrix atau fitur time-frequency.
- Jika phase tidak dipakai, pipeline kehilangan salah satu modalitas yang secara eksplisit dipakai RT-Fall untuk segmentasi jatuh. [dl.acm](https://dl.acm.org/doi/abs/10.1109/TMC.2016.2557795)
- Jika split dilakukan per window tanpa grouping recording, metrik validation/test berpotensi terlalu optimis.
- Jika FALL hanya berupa beberapa recording, jumlah event jatuh yang efektif bisa jauh lebih kecil daripada jumlah window FALL karena window dalam satu recording berkorelasi.

### Hipotesis

- Performa rendah mungkin bukan hanya karena arsitektur classifier, tetapi karena label window tidak selaras dengan event jatuh.
- 16 fitur mungkin cukup untuk membedakan aktivitas kasar, tetapi kurang representatif untuk membedakan jenis jatuh, arah jatuh, atau fall-like activity.
- Ketidakseimbangan window FALL/NON_FALL dapat membuat threshold default menghasilkan false negative.
- Perbedaan preprocessing training versus firmware dapat menjadi penyebab degradation pada deployment, meskipun ini belum dapat dibuktikan tanpa kode firmware.

### Belum diketahui

- Jumlah recording dan event jatuh.
- Apakah recording memiliki timestamp annotation.
- Apakah 16 fitur benar-benar dihitung per window.
- Apakah split grouped.
- Apakah preprocessing firmware identik dengan training.
- Apakah evaluasi membedakan PRE, GERAKAN, dan POST.
- Apakah detection latency diukur.

## Alternatif pipeline

| Alternatif | Data | Preprocessing | Window | Input | Algoritma | Risiko overfitting | Kebutuhan data | Biaya | Kelayakan ESP32 |
|---|---|---|---|---:|---|---|---|---|---|
| A. Current 16-feature Linear SVM | Existing CSI | Existing pipeline | Existing | 16 | Linear SVM | Rendah | Rendah | Sangat rendah | Sangat baik |
| B. Full amplitude subcarrier | Semua subcarrier amplitude | Denoise + scaling | 1–3 s | \(T \times K\) atau flattened | SVM/RF/logistic | Sedang | Sedang | Rendah | Sedang |
| C. Amplitude + temporal difference | Amplitude dan \(\Delta x_t=x_t-x_{t-1}\) | Denoise + scaling | 1–3 s | \(2T \times K\) atau fitur statistik | SVM/RF | Sedang | Sedang | Rendah | Sedang |
| D. Amplitude statistical features | Mean, std, MAD, IQR, entropy, slope per subcarrier | Denoise + scaling | 1–3 s | \(K \times F\) | SVM/RF | Sedang | Sedang | Rendah | Baik |
| E. Amplitude + phase | Amplitude dan sanitized phase/phase difference | Phase unwrap + denoise | 1–3 s | \(2T \times K\) atau fitur | SVM/RF/CNN | Sedang-tinggi | Sedang-tinggi | Sedang | Sedang |
| F. Time-frequency features | STFT/DWT amplitude | Denoise + normalization | 2–3 s | Spectrogram/wavelet coefficient | SVM/CNN | Tinggi | Tinggi | Sedang | Terbatas |
| G. Raw CSI temporal matrix | Amplitude dan/atau phase matrix | Denoise + scaling | 1–3 s | \(T \times K\) | 1D-CNN atau GRU | Tinggi | Tinggi | Tinggi | Terbatas |

### Prioritas eksperimen

1. **Audit dan perbaiki label/windowing**, tanpa mengubah model: pastikan FALL window benar-benar mencakup onset hingga impact, dan NON_FALL window benar-benar bebas aktivitas jatuh.
2. **Grouped split by recording/subjek**, dengan scaler dan feature selection fit hanya dari training.
3. **Amplitude + temporal difference**, mempertahankan classifier ringan dan kompatibel dengan ESP32.
4. **Amplitude statistical features per subcarrier**, bukan hanya 16 angka global; ini memperluas informasi tanpa langsung beralih ke deep learning.
5. **Amplitude + phase difference**, terutama bila hardware menyediakan lebih dari satu antenna.
6. **Time-frequency atau raw CSI CNN/GRU** hanya setelah jumlah recording/event cukup dan split subject/recording-aware tersedia.

## Kesimpulan dan roadmap

Literatur menunjukkan bahwa keberhasilan CSI fall detection lebih banyak ditentukan oleh **kualitas annotation, segmentasi event, preprocessing yang konsisten, pencegahan leakage, dan evaluasi event-level** daripada oleh penggantian classifier secara langsung. RT-Fall dan SiFall mencontohkan segmentasi berbasis sinyal dan window sekitar 3 detik, sementara Anti-Fall menunjukkan bahwa seleksi subcarrier dapat sangat agresif. [dl.acm](https://dl.acm.org/doi/abs/10.1109/TMC.2016.2557795)

Roadmap prioritas:

1. Unggah atau hubungkan codebase dan dataset.
2. Audit jumlah recording, FALL/NON_FALL, annotation, timestamp, dan event marker.
3. Verifikasi pembentukan window dan aturan label untuk window ambigu.
4. Audit 16 fitur: rumus, subcarrier, amplitude/phase, dan informasi yang hilang.
5. Periksa scaler, PCA, feature selection, dan split untuk leakage.
6. Bangun evaluasi grouped by recording/subjek, disertai event-level detection rate dan latency.
7. Bandingkan current 16-feature SVM dengan amplitude + temporal difference dan amplitude statistical features menggunakan dataset, split, dan label yang identik.
8. Baru pertimbangkan phase, time-frequency, atau CNN/GRU bila jumlah event dan recording memadai.