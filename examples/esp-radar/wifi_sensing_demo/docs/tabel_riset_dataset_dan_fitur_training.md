# **Matriks sintesis penelitian Wi-Fi CSI Fall Detection**

Matriks ini menyintesis tiga dokumen riset lokal: [riset_chatgpt.md](./riset_chatgpt.md), [riset_opencode.md](./riset_opencode.md), dan [riset_perplexity.md](./riset_perplexity.md), lalu membandingkannya dengan source dan recording proyek. Studi tambahan dari dua dokumen terakhir ditambahkan pada §12.

Dokumen riset tersebut adalah sumber sekunder untuk matriks ini, bukan pengganti pemeriksaan paper primer. Klaim yang hanya didukung abstrak, cuplikan, repository, atau rujukan yang belum dipastikan harus tetap ditandai `UNKNOWN`/`NOT VERIFIED`; metrik lintas-paper tidak boleh diperingkat seolah-olah tugas dan unitnya sama.

**Catatan pembacaan:** `NR` berarti *Not Reported* pada sumber yang tersedia; `Unknown` berarti informasinya belum dapat dipastikan. Angka jumlah recording, event, segment, window, dan sampel model akan saya bedakan karena semuanya bukan unit yang sama. Saya tidak akan mengisi informasi yang tidak tersedia dengan perkiraan.

## **1. Tabel utama — referensi dan karakteristik dataset**

| No. | Penelitian                                                          | Tahun / publikasi                           | Perangkat dan konfigurasi CSI                                                             | Subjek dan aktivitas                                                                  | Cara recording                                                                                               |
| --- | ------------------------------------------------------------------- | ------------------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| 1   | **WiFall — Han et al.**                                             | 2014, IEEE INFOCOM                          | Laptop, NIC 802.11n; detail antena, bandwidth dan rate tidak pasti                        | Jumlah subjek dan repetisi NR                                                         | Detail struktur recording tidak tersedia pada sumber yang diakses                                            |
| 2   | **Anti-Fall — Zhang et al.**                                        | 2015, ICOST                                 | Intel 5300, 5 GHz, sekitar 100 packet/s, 1 TX dan 2 RX link                               | 6 relawan; fall dan fall-like activities                                              | Continuous stream berisi berbagai aktivitas                                                                  |
| 3   | **RT-Fall — Wang et al.**                                           | 2017, IEEE TMC                              | Intel IWL5300, 5 GHz, sekitar 100 packet/s, 1 TX dan 2 RX link                            | 6 subjek; walking, running, jumping, sitting, standing, lying, object pickup dan fall | Continuous mixed-activity recording                                                                          |
| 4   | **FallDeFi — Palipana**                                             | 2019, disertasi doktoral                    | Intel 5300, 5.2 GHz, 30 subcarrier groups per RX antenna                                  | 3 relawan; fall, fall-like, ADL dan empty room                                        | Umumnya recording aktivitas berdurasi 10 detik; beberapa sesi dan kondisi link                               |
| 5   | **Damodaran et al.**                                                | 2020, artikel jurnal                        | 2 laptop Intel 5300, 20 MHz, 1 TX dan 3 RX, 90 amplitude streams                          | 5 kelas aktivitas; fall dan aktivitas non-fall                                        | Defined activity takes; beberapa sampel fall memiliki rekaman post-fall lebih panjang                        |
| 6   | **Nakamura et al.**                                                 | 2022, IEEE IoT Journal                      | Commodity Wi-Fi CSI, 2 ruangan                                                            | Detail subjek dan repetisi tidak pasti                                                | CSI diubah menjadi spectrogram melalui sliding time windows                                                  |
| 7   | **Surasakhon et al.**                                               | 2022, IJSNET                                | Detail chipset dan antena NR                                                              | NR                                                                                    | Struktur recording NR                                                                                        |
| 8   | **El-Sayed et al.**                                                 | 2022, Neural Computing and Applications     | Intel 5300 / UT-HAR, 3 RX × 30 subcarrier = 90 streams, sekitar 1 kHz                     | 6 peserta kantor, 6 aktivitas, masing-masing 20 repetisi                              | File sumber dapat mengandung beberapa periode aktivitas dan stationary; segmen dipilih dari recording sumber |
| 9   | **Mattela et al.**                                                  | 2022, SN Computer Science                   | Detail perangkat NR                                                                       | NR                                                                                    | Durasi dan struktur recording NR                                                                             |
| 10  | **Chu et al.**                                                      | 2023, IEEE Access                           | Intel 5300, 1 TX dan 3 RX, 30 subcarrier/link, sekitar 1 kHz                              | 22 relawan; 4 arah fall, ADL dan fall-like negatives                                  | File mentah sekitar 1–2 menit berisi repetisi dari satu jenis aktivitas; kemudian dipotong menjadi segmen    |
| 11  | **STC-NLSTMNet — Islam et al.**                                     | 2023, Sensors                               | Intel 5300, 3 RX × 30 subcarrier = 90 amplitude streams                                   | Dataset multi-environment 30 relawan; juga memakai StanWiFi                           | Ada trial berisi urutan beberapa aksi; StanWiFi memiliki sampel aktivitas 20 detik                           |
| 12  | **TCS-Fall — Zhou et al.**                                          | 2024, Digital Health                        | Intel 5300, 3×3 MIMO, 90 amplitude streams                                                | 20 relawan; 30 repetisi per kondisi single-action                                     | Dua format: isolated 8 detik dan continuous 150 detik                                                        |
| 13  | **DapFall — Chen et al.**                                           | 2025, IEEE Sensors Journal                  | CSI amplitude menjadi dynamic amplitude probability-density profiles; detail perangkat NR | Jumlah subjek/event NR                                                                | Representasi 3D DAPD; detail recording mentah NR                                                             |
| 14  | **AmFall — Kim et al.**                                             | 2025, IEEE IoT Journal                      | CSI amplitude, selected subcarriers/PCA                                                   | Jumlah subjek dan repetisi NR                                                         | Segmentasi berdasarkan kecepatan sinyal; scalogram                                                           |
| 15  | **Mobile-receiver construction-worker study**                       | 2025, Developments in the Built Environment | TP-Link router 2.4 GHz; Nexus 6P/Broadcom BCM4358/Nexmon; 64 subcarrier dilaporkan        | 6 peserta; 120 trial per peserta, 50 fall dan 70 fall-like                            | Satu trial aktivitas sekitar 5 detik atau 500 CSI packets                                                    |
| 16  | **Adaptive fall detection for unseen environments and individuals** | 2025, IEEE MeMeA                            | Detail perangkat NR                                                                       | Detail peserta NR                                                                     | Detail recording NR                                                                                          |
| 17  | **CNN-LSTM, GNN dan Transformer comparison**                        | 2025, IntechOpen                            | TP-Link Archer AX23 5 GHz/80 MHz; Raspberry Pi 4/Nexmon; 256 nilai subcarrier awal        | Jumlah subjek tidak konsisten pada sumber yang tersedia                               | Continuous CSI batches 100 frame, sekitar 5 detik pada rate yang dilaporkan                                  |

**Referensi DOI dan sumber publikasi**

| No. | Referensi                                                                                                                                 |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | [WiFall — DOI 10.1109/INFOCOM.2014.6847948](https://doi.org/10.1109/INFOCOM.2014.6847948?utm_source=chatgpt.com)                          |
| 2   | [Anti-Fall — DOI 10.1007/978-3-319-19312-0_15](https://doi.org/10.1007/978-3-319-19312-0_15?utm_source=chatgpt.com)                       |
| 3   | [RT-Fall — DOI 10.1109/TMC.2016.2557795](https://doi.org/10.1109/TMC.2016.2557795?utm_source=chatgpt.com)                                 |
| 4   | FallDeFi — Palipana, 2019, disertasi doktoral Cork Institute of Technology                                                                |
| 5   | [Damodaran et al. — DOI 10.1007/s42486-020-00027-1](https://doi.org/10.1007/s42486-020-00027-1?utm_source=chatgpt.com)                    |
| 6   | [Nakamura et al. — DOI 10.1109/JIOT.2022.3152315](https://doi.org/10.1109/JIOT.2022.3152315?utm_source=chatgpt.com)                       |
| 7   | [Surasakhon et al. — DOI 10.1504/IJSNET.2022.127111](https://doi.org/10.1504/IJSNET.2022.127111?utm_source=chatgpt.com)                   |
| 8   | [El-Sayed et al. — DOI 10.1007/s00521-021-06787-w](https://doi.org/10.1007/s00521-021-06787-w?utm_source=chatgpt.com)                     |
| 9   | [Mattela et al. — DOI 10.1007/s42979-022-01111-2](https://doi.org/10.1007/s42979-022-01111-2?utm_source=chatgpt.com)                      |
| 10  | [Chu et al. — DOI 10.1109/ACCESS.2023.3300726](https://doi.org/10.1109/ACCESS.2023.3300726?utm_source=chatgpt.com)                        |
| 11  | [STC-NLSTMNet — DOI 10.3390/s23010356](https://doi.org/10.3390/s23010356?utm_source=chatgpt.com)                                          |
| 12  | [TCS-Fall — DOI 10.1177/20552076241259047](https://doi.org/10.1177/20552076241259047?utm_source=chatgpt.com)                              |
| 13  | [DapFall — DOI 10.1109/JSEN.2025.3544552](https://doi.org/10.1109/JSEN.2025.3544552?utm_source=chatgpt.com)                               |
| 14  | [AmFall — DOI 10.1109/JIOT.2025.3585401](https://doi.org/10.1109/JIOT.2025.3585401?utm_source=chatgpt.com)                                |
| 15  | [Construction-worker study — DOI 10.1016/j.dibe.2025.100745](https://doi.org/10.1016/j.dibe.2025.100745?utm_source=chatgpt.com)           |
| 16  | [Adaptive fall detection — DOI 10.1109/MeMeA65319.2025.11068083](https://doi.org/10.1109/MeMeA65319.2025.11068083?utm_source=chatgpt.com) |
| 17  | [IntechOpen — DOI 10.5772/acrt20250099](https://doi.org/10.5772/acrt20250099?utm_source=chatgpt.com)                                      |

## **2. Tabel recording, ground truth, dan segmentasi**

Bagian ini penting karena dua penelitian bisa sama-sama memakai SVM, tetapi sebenarnya melatih model untuk tugas yang berbeda: mengenali aktivitas yang sudah dipotong atau menemukan fall di dalam aliran CSI yang panjang.

| Penelitian                | Ground truth / penentuan aktivitas                                                             | Cara segmentasi                                             | Window dan stride                                                                | Overlap                                            |
| ------------------------- | ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------- | -------------------------------------------------- |
| WiFall                    | Detail anotasi NR                                                                              | Event segmentation/classification                           | NR                                                                               | Unknown                                            |
| Anti-Fall                 | Video ruangan dan observasi manusia; CSI phase-difference variance membantu menemukan transisi | Two-stage event segmentation                                | Window aktivitas terbaik sekitar 2,9–3,0 detik                                   | Bukan sliding overlap tetap                        |
| RT-Fall                   | Video ruangan dan observer; CSI transition/stability                                           | Segmentasi event pada continuous stream                     | Sekitar 3 detik dibahas dalam literatur terkait; parameter window universal NR   | Unknown                                            |
| FallDeFi                  | Penilaian manual; detail onset/impact video NR                                                 | STFT dan event detection                                    | STFT 512 sampel, hop 256 pada 1 kHz                                              | 50%                                                |
| Damodaran                 | Instruksi aktivitas dan pemisahan packet/file; timestamp onset/impact independen NR            | Defined activity takes                                      | General activity: 2.500 packet; contoh non-fall pada fall experiment: 500 packet | Tidak dilaporkan                                   |
| Nakamura                  | Detail ground truth NR                                                                         | CSI spectrogram dengan sliding window                       | NR                                                                               | Unknown                                            |
| El-Sayed / UT-HAR         | Video dan MATLAB packet log; aturan onset detail NR                                            | Memilih aktivitas dari file sumber                          | Durasi sumber sekitar 20 detik; input window spesifik NR                         | Unknown                                            |
| STC-NLSTMNet              | Protocol aktivitas; timestamp video independen NR                                              | Sliding packet windows                                      | 512 packet, stride 128                                                           | 75%                                                |
| Chu                       | GoPro dengan timestamp overlay yang dikorelasikan dengan CSI                                   | Memotong aktivitas individual dari file panjang             | 5 detik; sekitar 5.000 packet, downsample menjadi 625 time steps                 | Sliding-window overlap disebutkan, stride pasti NR |
| TCS-Fall                  | Fall time dicatat pada continuous recording; asal timestamp detail NR                          | Single-action dan sliding windows pada continuous recording | 8 detik, stride 1 detik                                                          | 87,5%                                              |
| Construction-worker study | Video dan protokol trial                                                                       | Doppler processing dengan sliding windows                   | 140 packet, stride 2 packet                                                      | 98,57%                                             |
| IntechOpen                | Scheduled capture offsets dan instruksi aktivitas; anotasi fisik independen NR                 | Batch CSI dan overlapping examples                          | 100 frame sekitar 5 detik; offset tambahan +1 dan +4 detik                       | Overlap berdasarkan offset                         |
| AmFall                    | Label folder dan CSI-speed segmentation; onset/impact manual NR                                | Speed-based event segmentation dan CWT                      | Durasi/stride NR                                                                 | Unknown                                            |
| DapFall                   | Detail anotasi fisik NR                                                                        | DAPD transformation                                         | NR                                                                               | Unknown                                            |

**Catatan numerik penting:**

- Chu: \\(5\\,s \times 1.000\\) packet/s = 5.000 packet; downsampling 8× menghasilkan 625 time steps.
- STC-NLSTMNet: \\(512\\) packet dengan stride \\(128\\) berarti overlap \\(75\\%\\). Durasi aktual bergantung pada packet rate.
- TCS-Fall: 8 detik dengan stride 1 detik berarti overlap \\(87,5\\%\\).
- Construction-worker study: 140 packet dengan stride 2 berarti overlap sekitar \\(98,57\\%\\). Secara teoritis satu take 500 packet dapat menghasilkan hingga 181 window tanpa padding.

Angka-angka tersebut menjelaskan mengapa jumlah window tidak boleh dianggap sebagai jumlah fall independen.&#x20;

riset fitur csi chatgpt.md



## **3. Tabel preprocessing CSI**

Preprocessing harus dipisahkan dari feature extraction. Filtering membersihkan sinyal, transformasi mengubah representasinya, sedangkan feature extraction menghitung informasi yang diberikan ke classifier.

| Metode                           | Penelitian                             | Input → output                                          | Posisi dalam pipeline            | Catatan teknis                                                  |
| -------------------------------- | -------------------------------------- | ------------------------------------------------------- | -------------------------------- | --------------------------------------------------------------- |
| CSI interpolation                | Anti-Fall, RT-Fall, FallDeFi           | CSI dengan timestamp tidak teratur → grid waktu teratur | Sebelum filtering dan segmentasi | Interpolasi dapat menciptakan perubahan buatan pada gap panjang |
| Amplitude extraction             | Damodaran, Chu, STC-NLSTMNet, TCS-Fall | Complex CSI \\(I+jQ\\) → \\(\sqrt{I^2+Q^2}\\)           | Awal pipeline                    | Menghilangkan informasi fase                                    |
| Phase-difference                 | Anti-Fall, RT-Fall                     | Fase antar-RX → relative phase series                   | Sebelum segmentasi/fitur         | Membutuhkan pengukuran fase multi-antena yang reliabel          |
| Low-pass / band-pass             | Anti-Fall, RT-Fall, STC-NLSTMNet       | CSI series → filtered series                            | Sebelum segmentasi/fitur         | Cutoff buruk dapat menghilangkan transient                      |
| DWT denoising                    | Damodaran, FallDeFi                    | Amplitude/PCA series → denoised signal                  | Sebelum fitur/time-frequency     | Pemilihan wavelet dan threshold berpengaruh                     |
| PCA                              | Damodaran, FallDeFi, IntechOpen        | Banyak subcarrier → komponen utama                      | Setelah cleanup                  | PCA harus di-fit hanya dengan data training                     |
| Gaussian smoothing               | STC-NLSTMNet                           | Amplitude → smoothed amplitude                          | Sebelum windowing                | Dapat meredam transient pendek                                  |
| Grouped coefficient of variation | TCS-Fall                               | Kelompok 20 packet → variation sequence                 | Sebelum CNN                      | Representasi turunan, bukan raw CSI                             |
| Downsampling                     | Chu                                    | 5.000 → 625 time points                                 | Sebelum CNN                      | Harus mempertahankan dinamika fall                              |
| Hampel outlier removal           | IntechOpen                             | CSI per subcarrier → outlier-corrected                  | Sebelum smoothing/PCA            | Bergantung window dan sigma                                     |
| Savitzky–Golay                   | IntechOpen                             | Sinyal → smoothed signal                                | Sebelum normalisasi/PCA          | Dapat mengubah transient impact                                 |
| CWT / scalogram                  | AmFall                                 | CSI terpilih → time-frequency image                     | Setelah segmentasi               | Banyak gambar dapat berasal dari satu event                     |
| Normalization                    | Chu, TCS-Fall, IntechOpen              | Nilai CSI → scaled values                               | Sebelum model                    | Statistik scaling tidak boleh memakai data test                 |

### **Parameter preprocessing spesifik yang dilaporkan**

| Penelitian | Detail parameter                                                                                                                                                                                        |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Damodaran  | Symlet-6 wavelet, heuristic SURE threshold, soft thresholding, kemudian PCA; pada analisis aktivitas umum tiga PC pertama menjelaskan sekitar 70–80% variasi; Haar wavelet level 5 untuk fitur lanjutan |
| FallDeFi   | Interpolasi ke uniform sampling grid, wavelet denoising, PCA, STFT 512 sampel dengan hop 256 pada 1 kHz; PCA mempertahankan komponen yang menjelaskan sekitar 95% variasi                               |
| TCS-Fall   | RSS-related scaling, bidirectional Butterworth low-pass filter, grouped coefficient of variation setiap 20 amplitude packet; 8.000×90 menjadi 400×90                                                    |
| Chu        | Menguji wavelet denoising; varian tanpa denoising dilaporkan memiliki performa serupa atau lebih baik; jalur utama memakai downsampling dan reshaping                                                   |
| IntechOpen | Penghapusan null/pilot dan subcarrier bernilai rendah; Hampel window 5 dan threshold 3-sigma; Savitzky–Golay window 7, polynomial order 3; normalization; PCA 10 komponen                               |

**Peringatan untuk implementasi realtime:** bidirectional filtering atau zero-phase filtering menggunakan informasi masa depan. Hasil offline-nya tidak otomatis dapat direplikasi oleh filter causal di ESP32 tanpa perubahan latency dan respons sinyal.&#x20;

riset fitur csi chatgpt.md



## **4. Tabel representasi CSI dan jumlah fitur**

Ini bagian yang paling relevan untuk membandingkan model kita. Perhatikan perbedaan antara jumlah subcarrier, jumlah channel, jumlah jenis fitur, dan ukuran akhir input model.

| Penelitian                | Representasi CSI                                     | Subcarrier / channel                   | Input model / dimensi                                                                                           |
| ------------------------- | ---------------------------------------------------- | -------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| WiFall                    | CSI variability dan spatial diversity                | Detail selected subcarrier NR          | Dimensi akhir NR                                                                                                |
| Anti-Fall                 | Amplitude + phase                                    | 4 subcarrier terpilih; 2 receive links | 7 jenis fitur × 4 SC × 2 representasi = 56 dimensi per link; total gabungan kedua link bergantung concatenation |
| RT-Fall                   | Amplitude + phase difference                         | 30 subcarrier groups/link; 2 RX links  | 8 jenis fitur yang disebutkan; dimensi akhir NR                                                                 |
| FallDeFi                  | Amplitude → PCA/time-frequency                       | 30 groups/link; 2–3 PC                 | Fitur terpilih: spectral entropy, fractal dimension, event duration                                             |
| Damodaran — classical ML  | Amplitude, DWT/PCA, statistik dan frequency features | 30×3 = 90 streams                      | 8 kategori statistik ditambah PSD dan center-energy; dimensi final NR                                           |
| Damodaran — LSTM          | Amplitude temporal sequence                          | 90 nilai per time step                 | Input 90 dimensi per timestep; hidden layer 128 unit                                                            |
| Chu                       | Amplitude tensor                                     | 3 RX × 30 SC                           | \\(3×625×30=56.250\\) nilai per sampel                                                                          |
| El-Sayed / UT-HAR         | Raw amplitude sequence                               | 3 RX × 30 SC = 90                      | 90 nilai per time step; panjang sequence final NR                                                               |
| STC-NLSTMNet              | Raw amplitude temporal matrix                        | 90 streams                             | \\(512×90=46.080\\) nilai per window                                                                            |
| TCS-Fall                  | Grouped coefficient of variation                     | 90 channels                            | \\(400×90=36.000\\) nilai per window                                                                            |
| Construction-worker study | Amplitude/phase-derived Doppler                      | 64 awal, 58 setelah filtering          | \\(140×58×2=16.240\\) nilai jika dua komponen dipertahankan                                                     |
| IntechOpen                | Temporal CSI + PCA                                   | 256 awal, 10 PC                        | \\(100×10=1.000\\) nilai                                                                                        |
| DapFall                   | Dynamic amplitude probability-density profile        | Detail NR                              | 3D DAPD; ukuran tensor NR                                                                                       |
| AmFall                    | Selected amplitude + CWT scalogram                   | Jumlah terpilih NR                     | Image/scalogram; dimensi NR                                                                                     |

### **Jenis fitur yang digunakan dalam literatur**

| Keluarga fitur         | Contoh                                                 | Informasi yang ditangkap            |
| ---------------------- | ------------------------------------------------------ | ----------------------------------- |
| Central tendency       | Mean, median                                           | Level dan perubahan baseline        |
| Dispersion             | Variance, standard deviation, IQR, MAD                 | Intensitas fluktuasi                |
| Amplitude range        | Maximum, minimum, peak-to-peak                         | Magnitudo perubahan                 |
| Distribution shape     | Skewness, kurtosis, entropy                            | Bentuk distribusi variasi sinyal    |
| Temporal dynamics      | Velocity, temporal difference, duration, time lag      | Kecepatan dan durasi perubahan      |
| Frequency domain       | PSD, spectral entropy, dominant frequency, band energy | Periodisitas dan struktur frekuensi |
| Time-frequency         | STFT, CWT, scalogram                                   | Perubahan spektral sepanjang waktu  |
| CSI relationships      | Phase difference, mutual information, DAPD             | Hubungan antar-channel CSI          |
| Reduced representation | PCA components                                         | Kompresi dan reduksi redundansi     |

Secara khusus, Anti-Fall melaporkan normalized standard deviation, MAD, activity duration, signal-strength offset, IQR, entropy dan velocity. RT-Fall menambahkan time lag serta power decline ratio. FallDeFi memilih spectral entropy, fractal dimension dan event duration dari fitur yang lebih luas.&#x20;

riset fitur csi chatgpt.md



## **5. Tabel model machine learning dan training**

| Penelitian                | Model                          | Input utama                             | Training / konfigurasi yang dilaporkan                                                    | Validasi                                                                  |
| ------------------------- | ------------------------------ | --------------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Anti-Fall                 | One-Class SVM                  | Fitur aktivitas dari CSI                | LibSVM                                                                                    | Tuning dan subject-group split NR                                         |
| RT-Fall                   | SVM multi-stage                | Fitur amplitude/phase dan segmentasi    | Progressive personalization; memakai data awal pengguna dan pengujian pengguna berikutnya | Bukan LOSO zero-shot biasa                                                |
| Damodaran                 | Linear one-vs-all SVM dan LSTM | Statistik/spektral; sequence 90 dimensi | SVM \\(C=0.01\\); LSTM hidden 128, Adam, batch 128, LR 0.001                              | Split fall dataset tidak dijelaskan cukup lengkap                         |
| Chu                       | CNN image classifier           | Tensor 3×625×30                         | PyTorch, Adam, LR 0.001, weight decay 0.0001, batch 50, 40 epoch                          | 80/20 dan pengujian tambahan room/participant                             |
| El-Sayed                  | CNN-GRU dan CNN-LSTM hybrids   | Raw CSI amplitude temporal data         | Berbagai arsitektur CNN-recurrent                                                         | Random 70/30 dan k-fold; subject-exclusive belum terbukti                 |
| STC-NLSTMNet              | CNN + attention + NLSTM        | Window 512×90                           | Adam, LR 0.001, batch 128, hingga 100 epoch, early stopping                               | 10-fold setelah window generation                                         |
| TCS-Fall                  | CNN                            | Grouped coefficient of variation        | 5 convolutional layers, max-pooling, ReLU, dropout 0.6                                    | Fold berdasarkan volunteer ID                                             |
| DapFall                   | Pretrained R(2+1)D             | DAPD 3D representation                  | Transfer learning dan amplitude-based augmentation                                        | Cross-environment dilaporkan                                              |
| AmFall                    | Lightweight CNN / ResNet       | Denoised scalograms                     | MATLAB scalogram dan Colab CNN/ResNet                                                     | Split unit dan augmentation ordering tidak pasti                          |
| Construction-worker study | Deep-learning classifier       | CSI Doppler representations             | Windowed CSI Doppler                                                                      | Pooled 6:2:2; split unit take/window belum pasti                          |
| IntechOpen                | CNN-LSTM, GNN, Transformer     | Temporal CSI / PCA                      | Model deep-learning untuk perbandingan                                                    | Stratified 80/20 sample-level; detail independensi subjek tidak konsisten |

### **Perbedaan penting: apa yang dipelajari model?**

- Anti-Fall dan RT-Fall menekankan pengenalan event setelah segmentasi.
- Damodaran membedakan falling dan konsekuensi setelah fall, termasuk tetap berbaring atau bangkit.
- Chu menggunakan activity segments yang sudah diekstrak.
- TCS-Fall memisahkan isolated action samples dari continuous-stream detection.
- Banyak model HAR mengklasifikasikan fixed windows, bukan mendeteksi keseluruhan event dengan onset dan alarm.

Jadi, akurasi tinggi pada klasifikasi window multi-kelas tidak otomatis berarti sistem mampu mendeteksi kejadian jatuh secara realtime.&#x20;

riset fitur csi chatgpt.md



## **6. Tabel pembagian dataset dan risiko data leakage**

| Penelitian                | Metode pembagian                                             | Unit split yang diketahui                                  | Subject-independent?           | Catatan                                               |
| ------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------- | ------------------------------ | ----------------------------------------------------- |
| WiFall                    | Unknown                                                      | NR                                                         | Unknown                        | Tidak cukup informasi                                 |
| Anti-Fall                 | NR                                                           | NR                                                         | Unknown                        | Tidak cukup informasi                                 |
| RT-Fall                   | Progressive personalization                                  | Pengguna dan tahap pengujian                               | Sebagian, dengan personalisasi | Bukan pengujian unseen subject tanpa adaptasi         |
| FallDeFi                  | Within-environment 70/30 dan cross-environment/cross-subject | Sampel dan kondisi lingkungan                              | Ada pengujian transfer         | Grouping original take perlu verifikasi               |
| Damodaran                 | NR                                                           | NR                                                         | Unknown                        | Split fall dataset tidak jelas                        |
| Chu                       | 80/20 dan kombinasi room/participant                         | Split utama belum jelas apakah source recording tetap utuh | Ada pengujian tambahan         | Split utama belum membuktikan subject holdout         |
| El-Sayed                  | Random 70/30 dan k-fold                                      | Sampel                                                     | Tidak terbukti                 | Risiko korelasi sampel satu recording                 |
| STC-NLSTMNet              | 10-fold                                                      | Window setelah sliding segmentation                        | Tidak dilaporkan               | Potensi window yang saling overlap masuk fold berbeda |
| TCS-Fall                  | Group by volunteer ID                                        | Subjek                                                     | **Ya**                         | Salah satu contoh validasi paling relevan             |
| Construction-worker study | Pooled 6:2:2                                                 | Take/window tidak pasti                                    | Tidak dilaporkan               | Overlap sangat tinggi                                 |
| IntechOpen                | Stratified 80/20                                             | Sampel                                                     | Tidak terbukti                 | Jumlah subjek sendiri tidak konsisten                 |
| AmFall                    | Tidak pasti                                                  | NR                                                         | Unknown                        | Repository tidak cukup menjelaskan                    |
| DapFall                   | Cross-environment/no-retraining dilaporkan                   | Detail grouping NR                                         | Cross-environment diuji        | Detail subject split belum pasti                      |

### **Risiko leakage yang perlu dibedakan**

| Jenis leakage              | Bagaimana terjadi                                               | Pengendalian                                            |
| -------------------------- | --------------------------------------------------------------- | ------------------------------------------------------- |
| Overlapping-window leakage | Window berdekatan berbagi sebagian besar packet CSI             | Split berdasarkan recording/take sebelum membuat window |
| Subject leakage            | CSI orang yang sama muncul di train dan test                    | Subject-exclusive split                                 |
| Environment leakage        | Ruangan dan konfigurasi link sama pada kedua bagian             | Leave-one-environment-out                               |
| Normalization leakage      | Mean/std dihitung menggunakan test data                         | Fit hanya pada training fold                            |
| PCA leakage                | PCA dihitung menggunakan seluruh dataset                        | Fit PCA di dalam training fold                          |
| Feature-selection leakage  | Fitur dipilih berdasarkan hasil test                            | Nested validation                                       |
| Augmentation leakage       | Salinan hasil augmentasi dari satu event tersebar ke train/test | Split original event terlebih dahulu                    |
| Session leakage            | Beberapa recording satu sesi tersebar ke train/test             | Group by session                                        |

**Referensi khusus tentang leakage:**

| Penelitian                                                                                        | Tahun | Temuan                                                                                      |
| ------------------------------------------------------------------------------------------------- | ----- | ------------------------------------------------------------------------------------------- |
| Varga — *Critical Analysis of Data Leakage in WiFi CSI-Based Human Action Recognition Using CNNs* | 2024  | Menunjukkan bagaimana pencampuran subjek antara train dan test dapat menggelembungkan hasil |
| Varga & Cao — *Why Partitioning Matters*                                                          | 2025  | Melaporkan overestimation F1 sekitar 32% pada kasus yang dianalisis                         |

Angka 32% tersebut merupakan hasil kasus yang diteliti, bukan bukti bahwa seluruh penelitian CSI mengalami leakage sebesar itu.&#x20;

riset fitur csi chatgpt.md



## **7. Tabel evaluasi dan metrik**

| Penelitian                | Metrik utama                                          | Level evaluasi                 | Event latency                                          | False alarm/hour                         |
| ------------------------- | ----------------------------------------------------- | ------------------------------ | ------------------------------------------------------ | ---------------------------------------- |
| WiFall                    | Precision, false-alarm rate                           | Fall detection                 | NR                                                     | NR                                       |
| Anti-Fall                 | Fall detection ratio, FPR                             | Event/segment                  | NR                                                     | NR                                       |
| RT-Fall                   | Sensitivity, specificity                              | Activity/fall detection        | NR                                                     | NR                                       |
| FallDeFi                  | Accuracy, precision, recall, F1, environment transfer | Segment/event classification   | NR                                                     | NR                                       |
| Damodaran                 | Sensitivity, precision, specificity                   | Activity sample                | NR                                                     | NR                                       |
| Chu                       | Accuracy, precision, recall                           | 5-second activity window       | NR                                                     | NR                                       |
| El-Sayed                  | Accuracy dan class metrics                            | HAR window                     | NR                                                     | NR                                       |
| STC-NLSTMNet              | Accuracy, precision, recall, F1                       | Sliding window                 | NR                                                     | NR                                       |
| TCS-Fall                  | AUC, NEWR, CWR                                        | Continuous-recording detection | Tidak ada metrik latency onset standar yang dilaporkan | Tidak dilaporkan sebagai FA/hour standar |
| DapFall                   | TPR 94,3%, FPR 6,25%                                  | Fall classification            | NR                                                     | NR                                       |
| Construction-worker study | Accuracy, class metrics, confusion matrix             | Derived window                 | NR                                                     | NR                                       |
| IntechOpen                | Offline classification dan live detection             | Window dan live event          | Live event dilaporkan                                  | Tidak ada FA/hour standar                |

Metrik yang perlu dibedakan:

\\[ FPR=\frac{FP}{FP+TN} \\]

\\[ FA/h=\frac{\text{jumlah false alarm events}} {\text{durasi pemantauan non-fall dalam jam}} \\]

FPR bukan FA/hour. FPR dihitung dari kumpulan sampel negatif, sedangkan FA/hour menghitung kejadian alarm palsu dalam durasi pemantauan nyata.

Untuk proyek kita, kedua jenis metrik harus dilaporkan. Selain itu, window recall tidak boleh menggantikan event recall.

## **8. Rekonsiliasi hasil OpenCode, Perplexity, dan riset ChatGPT**

Berikut perbandingan kesimpulan ketiga sumber, bukan sekadar penggabungan daftar paper.

| Topik              | OpenCode                                                                     | Perplexity                                                                       | Riset ChatGPT                                                                  | Kesimpulan gabungan                                                           |
| ------------------ | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| Recording          | Berbagai format; satu recording dapat menghasilkan banyak sampel             | Banyak pendekatan menggunakan single-activity recordings, tetapi tidak universal | Empat pola: continuous, repeated single-activity, fixed-duration takes, hybrid | Tidak ada format recording universal                                          |
| Aktivitas per file | Tidak boleh menyimpulkan semua recording berisi banyak aktivitas             | Single-activity lebih umum pada beberapa contoh, tetapi tidak universal          | RT-Fall mixed stream; Chu repeated same activity; TCS-Fall hybrid              | Struktur recording harus diperiksa per dataset                                |
| Ground truth       | Sumber timestamp harus dibedakan                                             | Video, marker dan protokol aktivitas                                             | Video timestamp, observer, cue, CSI segmentation                               | Video-synchronized physical annotation paling kuat untuk onset dan impact     |
| Segmentasi         | Harus dipetakan dari recording ke window                                     | Window tetap dan event-based sama-sama ditemukan                                 | Ada fixed window, STFT, sliding window dan event detection                     | Event segmentation dan classifier windowing adalah dua proses berbeda         |
| Label              | Label seluruh take dapat menghasilkan label yang salah untuk window tertentu | Phase PRE/POST tidak selalu dipisahkan                                           | PRE, FALL_TRANSITION, POST_FALL dan RECOVERY perlu dibedakan                   | Label harus mengikuti isi temporal window                                     |
| Fitur              | Perbandingan fitur harus dilakukan secara terkontrol                         | Amplitude, delta, statistik dan phase merupakan alternatif                       | Handcrafted, raw CSI, time-frequency, PCA dan amplitude/phase                  | Lebih banyak fitur tidak otomatis lebih baik                                  |
| Preprocessing      | Perlu memastikan parameter sesuai pipeline                                   | Filtering, normalization, PCA dan transformasi bervariasi                        | Menunjukkan contoh parameter spesifik dari beberapa paper                      | Parameter harus dicatat dan fit hanya dari training fold bila data-derived    |
| Model              | Linear SVM masih relevan                                                     | Tidak ada alasan otomatis berpindah ke deep learning                             | Classical ML dan deep learning memiliki tujuan serta kebutuhan data berbeda    | Pilih model setelah dataset dan validasi benar                                |
| Split              | Window bukan observasi independen                                            | Grouped split disarankan                                                         | TCS-Fall memberi contoh split subject ID; banyak paper tidak cukup jelas       | Group by recording sebagai minimum, subject split untuk generalisasi pengguna |
| Evaluasi           | Window dan event harus dibedakan                                             | Event-level dan latency penting                                                  | FPR tidak sama dengan FA/hour                                                  | Evaluasi harus mencakup window, event, latency dan monitoring duration        |

**Tiga koreksi penting agar tidak salah membaca literatur:**

1. Random split tidak otomatis membuktikan adjacent-window leakage. Harus diperiksa apakah split dilakukan sebelum atau setelah window generation.
2. Jumlah sampel ribuan tidak berarti ribuan kejadian independen. Satu recording bisa menghasilkan ratusan window yang sangat berkorelasi.
3. Skor 99–100% dari suatu penelitian tidak dapat dijadikan target langsung tanpa menyamakan unit data, subjek, environment, split dan metrik.

## **9. Perbandingan langsung dengan proyek ESP32-WROOM-32**

Sekarang kita hubungkan literatur dengan kondisi proyek kita.

| Aspek | Temuan literatur | Keadaan proyek pada snapshot 2026-11-17 | Implikasi |
|---|---|---|---|
| Hardware/CSI | Intel 5300, Nexmon, dan perangkat lain memiliki format, antena, sampling, dan kualitas fase berbeda. | Target ESP32-WROOM-32; 55.744 frame valid yang diperiksa semuanya berisi 51 pasangan LLTF int8 (102 byte). Firmware model juga mengunci lebar 51. | Jangan memindahkan jumlah subcarrier, urutan kanal, filter, atau fitur paper tanpa adaptasi dan parity terhadap ESP32. |
| Recording | Literatur memakai isolated takes, file berulang satu aktivitas, dan continuous mixed streams. | Ada 183 take complete, satu label aktivitas utama per take, dengan timeline cue/fase; ini bukan korpus monitoring kontinu naturalistik yang berisi aktivitas bebas. | Pertahankan take asli dan timeline; uji continuous detection terpisah dari klasifikasi window terpotong. |
| Subjek/sesi | Jumlah window tidak sama dengan variasi subjek atau event. | Ada 3 nilai `subject_id` terisi (88 take `1`, 9 take `2`, 1 `TEST01`); 85 take tidak memiliki ID. Ke-40 fall yang punya anotasi event berasal dari satu sesi dan dua ID subjek (31 dan 9). | Validasi lintas-take ada, tetapi bukti lintas-sesi/lingkungan lemah; subject holdout sangat terbatas dan metadata room tidak cukup untuk mengklaim generalisasi ruangan. |
| Ground truth | Video tersinkron paling kuat untuk onset/impact; cue, instruksi, onset gerak, impact, dan recovery bukan timestamp yang sama. | 40 dari 60 take fall memiliki `fall_start`/`fall_impact` lengkap; 20 take fall lain tidak. Timeline protokol tersedia, namun bukan observasi video frame-per-frame. | Bedakan sumber dan tingkat kepastian label; jangan menyamakan cue dengan event timestamp atau mengasumsikan post-fall sebagai transition. |
| Window | Paper memakai banyak panjang dan stride; packet/frame count tidak otomatis menyatakan durasi. | Model memakai 24 frame, stride 12. Durasi terukur satu window: median 0,772 s, P5–P95 0,656–0,974 s, maksimum 2,393 s. | Window 24 frame bukan window berdurasi tetap; uji durasi berdasarkan timestamp dan tandai gap panjang. |
| Label | Per-recording, per-window, event extraction, dan detector segmentation adalah tugas berbeda. | Policy training aktif memberi FALL pada window utuh mulai offset 4 s hingga akhir take jatuh; firmware memilih model yang namanya `fall-start-to-impact`. | Policy terbaru dan artifact aktif belum selaras; hasil label-tail tidak boleh disebut hasil model firmware aktif. |
| Fitur | Literatur memakai fitur statistik, amplitude, phase, spektral, dan tensor; jumlah fitur tidak sebanding dengan dimensi tensor mentah. | 16 fitur adalah band `log1p(mean(abs(A[t]-A[t-1])))` selama window, pada 51 pasangan LLTF. | Delta amplitude sudah menjadi baseline. Yang belum ada di fitur itu termasuk peak/peak-to-peak CSI per band, level absolut, dan statistik distribusi. |
| Model | Linear dan deep models mengerjakan tugas serta input yang berbeda. | Firmware memilih binary Linear SVM, class order `fall`, `non_fall`, dengan standardisasi dari artifact. | Model sederhana sesuai target MCU, tetapi perlu validasi yang lebih independen sebelum klaim generalisasi. |
| Evaluasi | Window metrics tidak sama dengan event detection; FPR tidak sama dengan false alarms/hour. | Ada OOF 5-fold per take historis. Belum ada hasil terverifikasi yang memberi event latency dan false alarms/hour pada monitoring non-fall kontinu yang panjang. | Pertahankan metrik window, tambahkan evaluasi event, latency, dan denominator jam negatif. |
| Runtime | Causal/embedded pipeline harus konsisten dengan preprocessing offline dan diukur pada hardware. | Firmware memakai stabilisasi 2/3 vote FALL, release setelah 3 NON_FALL, serta gate Motion terpisah: veto di bawah 3.850.000 dan marker di atas 5.000.000 `smooth_scaled` units. Gate membaca sampel terbaru, bukan peak CSI satu event. | Evaluasi model, stabilisasi, dan gate sebagai tahapan berbeda; jangan menyamakan peak Motion dengan fitur amplitude CSI. |

### **Kondisi angka model kita yang sudah tersedia**

| Model/eksperimen            | FALL windows | NON_FALL windows | Macro-F1 | FALL recall |
| --------------------------- | ------------ | ---------------- | -------- | ----------- |
| Phase-Aware event raw OOF   | 101          | 3.160            | 0,783    | 54,5%       |
| Phase-Aware event stabilized OOF | 101     | 3.160            | 0,755    | 51,5%       |
| 4–8 semua tipe              | 445          | 3.160            | 0,771    | 48,3%       |
| 4–8 tanpa keseleo           | 363          | 3.074            | 0,785    | 47,1%       |
| 4–8 tanpa lemas             | 373          | 3.085            | 0,746    | 40,8%       |
| 4–8 tanpa keseleo dan lemas | 291          | 2.999            | 0,815    | 56,7%       |
| 4–9 semua tipe              | 595          | 3.160            | 0,727    | 39,8%       |
| 4–9 tanpa keseleo           | 487          | 3.074            | 0,763    | 47,0%       |
| 4–9 tanpa lemas             | 497          | 3.085            | 0,746    | 46,1%       |
| 4–9 tanpa keseleo dan lemas | 389          | 2.999            | 0,771    | 49,4%       |

Angka ini tidak boleh dianggap sebagai perbandingan sempurna antarsemua eksperimen karena konfigurasi label dan protokolnya tidak selalu sama. Angka OOF event di atas berasal dari run tersimpan yang lebih lama (3.261 window, 189 take). Hitung ulang tanpa training pada recording snapshot saat ini, memakai policy tail aktif, menghasilkan 3.964 window berlabel dari 182 take: 925 FALL, 3.039 NON_FALL. Ini bukan evaluasi OOF baru. Perbedaan jumlah menunjukkan metrik historis tidak boleh diperlakukan sebagai evaluasi dataset snapshot sekarang.

Satu kesimpulan penting: **kualitas pembentukan training samples harus diperiksa sebelum kita menyimpulkan bahwa 16 fitur atau Linear SVM adalah penyebab rendahnya recall.**

## **10. Rekomendasi eksperimen yang paling bernilai**

Saya tidak menyarankan langsung mencoba seluruh kombinasi fitur × window × model. Itu akan menghasilkan terlalu banyak eksperimen dan sulit menentukan penyebab perubahan performa.

Urutan yang lebih kuat secara ilmiah:

| Tahap | Eksperimen                | Yang dibuat tetap                | Yang dibandingkan                                          |
| ----- | ------------------------- | -------------------------------- | ---------------------------------------------------------- |
| 1     | Dataset-to-window audit   | Dataset dan model aktif          | Recording, event, phase, window dan label                  |
| 2     | Validasi split            | Label, fitur, model              | Random window vs group-by-recording                        |
| 3     | Window/label construction | Fitur dan classifier             | Current Phase-Aware vs full action vs fall-start-to-impact |
| 4     | Feature representation    | Window, label, fold, model       | Baseline 16 fitur delta vs baseline + peak/range CSI, level relatif, atau statistik subcarrier |
| 5     | Window duration           | Label rule dan fitur             | 1, 2, 3, 4 detik                                           |
| 6     | Window stride             | Durasi dan fitur                 | 0,2–0,5 detik                                              |
| 7     | Classifier                | Semua input identik              | Linear SVM, Logistic Regression, Random Forest, RBF SVM    |
| 8     | Deployment evaluation     | Model dan preprocessing terpilih | Replay firmware dan biaya inferensi ESP32                  |

### **Prioritas representasi fitur**

Prioritas awal

1. Current 16 fitur band dari absolute first difference amplitude — baseline yang harus dipertahankan.
2. Tambahan peak, peak-to-peak, range, atau statistik distribusi CSI per band; uji ablation dengan fold dan label yang sama.
3. Amplitude relatif terhadap baseline kausal, hanya jika definisi baseline dan implementasi training/runtime identik.
4. Per-subcarrier statistic tambahan (mis. std/MAD/IQR) jika dapat dibenarkan oleh validasi grouped.
5. Full amplitude temporal matrix sebagai challenger offline berbiaya lebih tinggi.
6. Amplitude + phase hanya jika phase ESP32 terbukti repeatable; paper multi-RX bukan bukti langsung untuk WROOM-32.
7. Time-frequency representation sebagai eksperimen offline sebelum mempertimbangkan bentuk compact causal untuk MCU.
8. Raw CSI deep learning setelah jumlah event/subjek independen memadai.

Tidak perlu langsung membangun CNN atau Transformer. Jumlah subjek dan event independen saat ini belum memberikan alasan kuat untuk memprioritaskan model besar.

## **11. Daftar referensi metodologi tambahan**

Selain paper fall detection, dua penelitian berikut perlu dimasukkan ke daftar referensi tetap karena membahas masalah validitas evaluasi:

- Varga, 2024 — [Critical Analysis of Data Leakage in WiFi CSI-Based Human Action Recognition Using CNNs](https://doi.org/10.3390/s24103159?utm_source=chatgpt.com).
- Varga & Cao, 2025 — [Why Partitioning Matters: Revealing Overestimated Performance in WiFi-CSI-Based Human Action Recognition](https://doi.org/10.3390/signals6040059?utm_source=chatgpt.com).

## **Kesimpulan akhir**

Dari seluruh hasil yang tersedia, ada lima pelajaran paling penting:

1. **Recording harus mempertahankan konteks waktu.** Jangan hanya menyimpan potongan FALL dan NON_FALL tanpa hubungan ke recording aslinya.
2. **Ground truth harus mengikuti kejadian fisik.** Cue instruksi bukan timestamp gerakan sebenarnya; fall transition bukan post-fall.
3. **Windowing harus diuji secara sistematis.** Durasi 3 atau 5 detik dari paper lain tidak otomatis cocok dengan ESP32 kita.
4. **Delta amplitude sudah ada di baseline 16 fitur.** Uji fitur peak/range/level sebagai tambahan terkontrol, bukan membandingkan baseline dengan “delta” yang sama.
5. **Validasi harus mengukur kejadian nyata.** Window F1 saja tidak cukup; diperlukan event recall, false alarms/hour dan latency.

**Keputusan teknis yang saya rekomendasikan:** jangan mengganti model Phase-Aware sekarang. Selesaikan audit pembentukan training samples dan pastikan group split terlebih dahulu. Setelah itu, bandingkan current 16 features dengan amplitude+temporal-difference menggunakan window, label, dan fold yang identik.

Satu batas penting: rekomendasi classifier ini tidak menggantikan investigasi Motion decoder. Jalur Motion adalah telemetry terpisah dari amplitude CSI; nilai Motion pada saat inferensi tidak boleh disamakan dengan peak amplitude CSI per window.

## **12. Studi dan temuan yang belum tercakup di tabel utama**

Tabel utama §1–§7 sudah memuat sebagian besar studi dari riset ChatGPT, tetapi tidak seluruh studi yang muncul di riset OpenCode dan Perplexity. Baris berikut melengkapi cakupan tanpa menganggap angka dari laporan sekunder sebagai hasil yang sudah diverifikasi ulang terhadap naskah primer. `NR`/`UNKNOWN` tetap dipertahankan bila dokumen sumber tidak menetapkannya.

| Studi/kelompok yang ditambahkan | Kontribusi yang dicatat dalam riset sumber | Pelajaran yang relevan untuk proyek | Batas bukti pada matriks ini | Sumber ringkasan |
|---|---|---|---|---|
| WmFall (2018) | Pipeline dua tahap, SVM lalu DNN; membahas salah-klasifikasi fall-like seperti duduk dan perubahan NLOS. | Fall-vs-sit adalah hard negative yang perlu dilaporkan terpisah; metrik antar-tahap harus didefinisikan. | Angka presisi/FA memakai definisi paper dan tidak boleh dibandingkan langsung dengan FPR window proyek. | [OpenCode §4.5](./riset_opencode.md) |
| CSITime (preprint 2021) | Beberapa dataset publik dengan jumlah sampel hasil pemrosesan yang berbeda dari jumlah rekaman/repetisi aslinya. | Selalu laporkan `take → event → segment → window`; dataset size tanpa unit rawan disalahartikan. | Venue/DOI ditandai belum terverifikasi dalam sumber. | [OpenCode §4.8](./riset_opencode.md) |
| GMM-HMM (2021) | Contoh sampel 10 detik dengan aksi hanya pada sebagian interval di tengah. | Label seluruh sampel hanya berdasarkan kelas aksi dapat mencampur PRE, aksi, dan POST. | Klaim split dan skor di sumber sekunder perlu dicek pada paper sebelum dikutip. | [OpenCode §4.9](./riset_opencode.md) |
| HARNN (2019) | RNN dengan window beberapa detik dan dataset berulang per orang/aktivitas. | Repetisi meningkatkan volume data, bukan jumlah subjek independen. | Unit split tidak cukup jelas pada ringkasan sumber. | [OpenCode §4.10](./riset_opencode.md) |
| El-Sayed / `dlmodels2022` (2022, DOI yang sama) | Studi UT-HAR/StanWiFi; laporan OpenCode menyebut 8.959 sampel dan CNN-GRU, sedangkan sumber lain meringkas 6 partisipan dan protokol repetisi. | Sampel/window tidak identik dengan recording atau event independen; satu paper dapat diringkas dengan unit berbeda. | Angka berasal dari ringkasan sekunder dan harus direkonsiliasi ke Table 2/paper primer. | [OpenCode §4.11](./riset_opencode.md) |
| SiFall (SenSys 2022) | Sistem online dengan kamera/NTP; laporan membedakan durasi segmen deteksi dari durasi ground-truth event dan mencatat perubahan false alarm setelah adaptasi. | TPR segmen tidak otomatis berarti recall event; distribusi sinyal dapat berubah saat deployment. | Definisi protokol, event, dan FAR harus dibaca dari paper sebelum disetarakan dengan proyek. | [OpenCode §4.12](./riset_opencode.md) |
| DeFall / UMD (2020) | Template matching/DTW tanpa training classifier biasa. | Tidak semua pendekatan deteksi harus berupa supervised classifier; baseline non-neural dapat memberi pembanding. | DOI/status bibliografi belum dipastikan oleh sumber OpenCode. | [OpenCode §4.13](./riset_opencode.md) |
| ESP32 fall-detection PoC (2026) | Dua perangkat ESP32, pipeline wavelet/scattering dan classifier kecil; laporan menyebut hanya 29 instance dan satu peserta. | Kedekatan hardware membantu, tetapi tidak menggantikan validasi lintas-orang/sesi. | Satu partisipan dan split yang tidak dilaporkan tidak mendukung klaim generalisasi. | [OpenCode §4.14](./riset_opencode.md) |
| RobustTrans (preprint 2026) | Menggunakan dataset Chu; sumber membedakan random split dan leave-one-environment-out. | Selalu pisahkan hasil random dan OOD; angka yang lebih tinggi dari random split bukan bukti transfer domain. | Klaim arXiv baru dan hasil tidak diverifikasi ulang; jangan jadikan angka target proyek. | [OpenCode §4.15](./riset_opencode.md) |
| CSI-Bench (2025) | Dataset multi-pengguna, multi-lingkungan, multi-perangkat; menyediakan skenario OOD. | Contoh berguna untuk desain benchmark lintas user/environment/device, bukan untuk menyalin input atau metriknya. | Skala dan definisi “sample/event” dalam sumber harus diperiksa pada appendix primer. | [OpenCode §4.16](./riset_opencode.md) |
| TransGNN (2025) | CSI temporal dan split berdasarkan bagian durasi dalam ringkasan OpenCode. | Split temporal dari recording yang sama tidak setara dengan subject-, event-, atau session-independent holdout. | Jangan menyebutnya leakage secara definitif tanpa memeriksa pembentukan split dan sampel yang tumpang tindih. | [OpenCode §4.17](./riset_opencode.md) |
| SmartAcc (2024) | Menggabungkan CSI dengan IMU pada smartphone. | Hasil multi-modal tidak sebanding dengan sistem CSI-only; sensor dan fitur tambahan harus dinyatakan. | Metadata split dan detail perangkat pada ringkasan sumber terbatas. | [OpenCode §4.18](./riset_opencode.md) |
| WiBFall (2021) | Perbandingan SVM dan Random Forest pada konteks kamar mandi. | Menambah konteks lingkungan dan hard-negative, tetapi model tetap perlu diuji pada kondisi proyek sendiri. | Tidak cukup rincian split dan unit metrik untuk perbandingan angka. | [Perplexity](./riset_perplexity.md) |
| Adversarial augmentation CSI (2020) | Weighted moving average, tujuh fitur manual, dan SVM biner. | Fitur handcrafted dan smoothing adalah pembanding ringan; preprocessing harus sama antara train/runtime. | Angka dan unit evaluasi tidak dimasukkan karena ringkasannya belum cukup rinci. | [Perplexity](./riset_perplexity.md) |
| Self-supervised CSI HAR (2025) | Intel 5300, phase correction, dan mean pooling ke sequence panjang tetap. | Representasi sequence alternatif untuk eksperimen offline; perlu uji phase pada hardware target sebelum mengadopsinya. | HAR bukan otomatis tugas fall detection; hardware multi-antena berbeda dari WROOM-32. | [Perplexity](./riset_perplexity.md) |

**Rujukan tambahan yang belum cukup teridentifikasi:** dokumen Perplexity menyebut metode “15 subcarrier acak”, tetapi ringkasan bibliografinya tidak cukup jelas untuk menetapkannya sebagai baris paper tersendiri. Rujukan Butterworth low-pass 100 Hz/`w=20` menunjuk DOI yang sama dengan TCS-Fall pada tabel utama; diperlakukan sebagai kemungkinan duplikasi, bukan paper terpisah, dan detail `w=20` perlu dicocokkan dengan naskah primer.

### **12.1 Pelajaran lintas-riset yang sebelumnya belum cukup eksplisit**

1. **Pisahkan deteksi event dari klasifikasi window.** Continuous-stream systems harus mencari kandidat event; model yang diberi window yang sudah dipotong hanya mengklasifikasikan sampel terpilih.
2. **Simpan provenance setiap sampel turunan.** Minimal: `recording_id`, event/take group, start/end frame dan timestamp, label, sumber label, serta aturan transformasinya.
3. **Split sebelum windowing, transformasi learned, dan augmentation.** Outer split yang lebih kuat menahan subjek atau lingkungan; pemilihan model/threshold dilakukan di inner grouped validation.
4. **Paskan transformasi hanya pada training fold.** Termasuk standardization, PCA, seleksi fitur, dan threshold data-driven. Filter dua arah/zero-phase tidak dapat diasumsikan sama dengan pipeline realtime kausal.
5. **Laporkan dua tingkat evaluasi.** Window precision/recall/F1 terpisah dari event recall, missed events, latency dari timestamp fisik yang didefinisikan, dan false alarms per jam dari durasi negatif yang cukup.
6. **Hard negatives harus terlihat dalam hasil.** Duduk cepat, membungkuk, berhenti berjalan, jatuh palsu, dan gerakan normal lain jangan hanya dilebur ke satu angka NON_FALL.
7. **Klaim deployment memerlukan data deployment.** Cross-room, NLOS, perubahan hari, subjek baru, perangkat lain, dan profiling MCU adalah pertanyaan berbeda; performa satu domain tidak menjawab semuanya.

## **13. Perbandingan terverifikasi terhadap snapshot proyek**

Tabel ini menggantikan klaim codebase “TIDAK DIKETAHUI” dari [riset_perplexity.md](./riset_perplexity.md) yang dibuat tanpa akses repository. Semua fakta berikut berasal dari file yang ada sekarang; hitungan window adalah pembacaan/penghitungan offline dan bukan training baru.

| Pipeline | Keadaan proyek sekarang | Dibanding pelajaran literatur |
|---|---|---|
| Penyimpanan/provenance | `frames.csv` mempertahankan raw/valid payload, timestamps dan metadata per frame; meta menyimpan timeline, anotasi dan `motion_samples`. | Fondasi provenance cukup baik. Belum semua take punya `subject_id` atau anotasi fisik lengkap; window turunan tetap harus terhubung ke event dan timestamp. |
| Akuisisi | 183 recording complete; 55.744 frame valid; satu label aktivitas utama per take beserta timeline cue/fase. | Mengikuti protokol take dengan konteks temporal, bukan continuous mixed-activity monitoring yang panjang. |
| CSI layout | Snapshot ini konsisten pada 51 pasangan LLTF int8 (102 byte); runtime mengunci lebar 51. | Menunjukkan mengapa asumsi Intel “30 subcarrier/link” atau lebar CSI standar tidak boleh dipindah langsung. |
| Label/fase | 60 take fall; 40 memiliki event `fall_start`–`fall_impact`, semuanya dalam satu sesi; 20 tidak memiliki anotasi event lengkap. Timeline protokol tersedia, namun bukan observasi video frame-per-frame. | Lebih informatif daripada satu label take tanpa fase, tetapi belum mendukung seluruh klaim fisik/onset untuk semua take. Post-fall perlu dipisah sesuai tugas. |
| Windowing | 24 frame/stride 12; 4.379 window penuh yang tersedia. Rentang satu window bervariasi (median 0,772 s, P5–P95 0,656–0,974 s). | Window frame-based bekerja pada sampling yang tidak sepenuhnya tetap; eksperimen 1–4 s sebaiknya timestamp-based dan eksplisit tentang gap. |
| Policy label aktif | Policy file melabeli window utuh sejak detik ke-4 sampai akhir take fall sebagai FALL. Penghitungan saat ini memberi 3.964 window berlabel pada 182 take: 925 FALL, 3.039 NON_FALL; satu sesi dikecualikan. | Ini tidak sama dengan anotasi `fall_start`–`impact`; definisi tugas harus ditetapkan sebelum membandingkan skor. |
| Model firmware | `activity_model_data.h` memilih `linear-svm-phase-fall-start-to-impact-v1`, 16 fitur, 51 subcarrier, class order `fall`, `non_fall`. | Artifact runtime masih model event-interval, bukan model hasil policy tail terbaru. Summary tail tersimpan tidak menyatakan fit ulang semua data dan ekspor; jangan mengasumsikan model firmware sudah diperbarui ke label tail. |
| Fitur/model runtime | Fitur adalah 16 nilai `log1p(mean(abs(Δ amplitude)))` per band. Standardisasi dan bobot linear datang dari artifact model. | Baseline sudah termasuk temporal difference. Peak-to-peak/range/level absolut masih merupakan kandidat fitur tambahan, bukan pengganti delta yang belum pernah dicoba. |
| Split/metrik | Ada OOF historis 5-fold group-by-take. Run event lama: 3.261 window (101 FALL/3.160 NON_FALL), macro-F1 0,783 raw dan 0,755 stabilized. | Overlap windows tertahan dalam grup take, tetapi ini bukan validasi subject/environment independent. Semua angka adalah window-level dan artifact lama, bukan hasil ulang pada snapshot data sekarang. |
| Gate/runtime | Stabilizer membutuhkan 2 vote FALL dalam 3 window dan melepas FALL setelah 3 NON_FALL berurutan. Gate Motion mem-veto kelas FALL pada sampel `smooth_scaled` segar <3.850.000; >5.000.000 hanya memberi marker jika kelas setelah veto tetap FALL. | Ini state machine dan sensor bantu terpisah dari fitur CSI. Belum menggantikan event metrics atau membuktikan peak Motion/CSI sebagai threshold yang andal. |

**Jejak source utama proyek:** [train_activity_model.py](../../../../fall_detection/train_activity_model.py), [train_phase_activity_model.py](../../../../fall_detection/train_phase_activity_model.py), [phase_label_policy.json](../../../../fall_detection/phase_label_policy.json), [activity_model_data.h](../main/activity_model_data.h), [activity_model_inference.c](../main/activity_model_inference.c), [activity_classifier.c](../main/activity_classifier.c), [activity_prediction_stability.c](../main/activity_prediction_stability.c), dan [activity_motion_gate.c](../main/activity_motion_gate.c).

## **14. Kesimpulan setelah membandingkan tiga riset**

- **Yang sudah diterapkan dengan baik:** recording mentah dan metadata tetap tersedia; ada timeline dan anotasi event pada sebagian fall; input model ringkas dan cocok untuk eksperimen MCU; split OOF per take pernah dijalankan.
- **Gap terbesar saat ini:** policy label tail tidak selaras dengan model event yang ditunjuk firmware; 20 take fall tidak punya anotasi event lengkap; metadata subjek hilang pada banyak take; fall event beranotasi hanya berasal dari satu sesi; evaluasi realtime event/latency/false alarms per jam belum tersedia.
- **Perbaikan prioritas yang didukung oleh ketiga riset:** (1) tetapkan definisi target FALL versus POST_FALL; (2) lengkapi anotasi fisik dan provenance window; (3) kumpulkan lebih banyak sesi/subjek dan hard negatives; (4) lakukan perbandingan berpasangan pada fold grouped yang sama; (5) hitung event recall, latency, dan false alarms per jam; (6) baru pilih fitur/model berdasarkan hasil validasi.
- **Ablasi fitur yang lebih tepat:** jadikan 16 fitur delta saat ini sebagai baseline; bandingkan dengan baseline + fitur peak/range/peak-to-peak CSI, amplitude relatif-baseline kausal, atau statistik distribusi. Semua preprocessing yang dipelajari harus fit di training fold saja.
- **Jangan adopsi angka paper secara langsung.** Hardware, kelas, event/window unit, split, dan definisi false alarm berbeda. Laporan riset juga memiliki klaim yang belum diverifikasi atau tidak sepenuhnya konsisten; catat status itu, bukan menutupinya dengan satu angka gabungan.

## 15. Table 8 — CSI acquisition, traffic stimulus, and acquisition variables

Documentation update: 2026-11-19. This section records the acquisition comparison discussed after Tables 1–7. Source findings are carried forward from that comparison, not freshly reverified on the web for this insertion. It supplements the earlier dataset/model snapshot without replacing its counts, rerunning experiments, or asserting the identity of firmware currently flashed on the device.

**HTTP 64 KiB is the selected baseline from the user's completed acquisition experiments. It is not an acquisition method that still needs to be discovered.** The comparison below uses the repository's experiment history and implementation, ESP-IDF v5.5.3 documentation, inspected upstream Espressif examples, other projects, and accessible papers.

Completeness means identifying the acquisition mechanisms and the variables required to compare them. It does not mean inventing settings absent from available sources or claiming to have inspected every published paper. Some primary acquisition recipes could not be verified; those gaps remain explicit.

### 15.1 Evidence and rate conventions

| Marker | Meaning | Interpretation boundary |
|---|---|---|
| `C` | Configured value | A requested transmission cadence or source default is not proof of achieved reception. |
| `O` | Observed result in the referenced experiment | Retain the experiment, counter, time interval, firmware, and workload context. |
| `R` | Value reported by a paper | Achieved timing and loss are not independently verified unless the source provides that evidence. |
| `NR` | Not reported in the inspected source | This does not establish that every version, appendix, or dataset document omits it. |
| `NV` | Primary acquisition details not verified | Secondary summaries, abstracts, and search excerpts are not complete acquisition recipes. |
| `NA` | Not applicable | Do not convert this into a zero measurement. |

Keep transmission requests, successful network replies, raw CSI callbacks, target-peer callbacks, accepted frames, classifier admissions, and recorded frames separate. An application request rate, RF transmission rate, CSI callback rate, export rate, and model processing rate are different quantities.

The official API reference below is specifically **ESP-IDF v5.5.3 for classic ESP32**. Upstream example/project links refer to the source branches inspected during the preceding acquisition comparison, not pinned release builds or proof of behavior on this AP. ESPectre findings that explicitly concern v5.5.5 or another chip must not be silently applied to this project's v5.5.3 WROOM-32 firmware.

### 15.2 Our completed acquisition experiments

Source: [Experiment history, methods and measurement audit](./EXPERIMENT_HISTORY.md#L67-L225).

| Method | Traffic generator and destination | Traffic supplying CSI | Important tested settings | Result and status |
|---|---|---|---|---|
| **HTTP 64 KiB** | ESP32 downloads from Cloudflare | Associated AP → ESP32 TCP downlink | **65,536-byte body; pause 0 ms; connection reuse off** | **Selected.** HTTP campaigns reported approximately **32–36 device callbacks/s**. |
| HTTP 200,000 bytes | Same topology | Same downlink mechanism | 200,000-byte body; baseline pause 100 ms | Quiet blocks: **36.1–36.2 callbacks/s O**. |
| HTTP 65,536 bytes, quiet-block comparison | Same topology | Same downlink mechanism | 65,536 bytes; pause 0 ms | **36.0–36.5 callbacks/s O**; approximately the same plateau as the larger response. |
| HTTP keep-alive | Same topology, reused connection/client | TCP downlink while transfers succeed | Keep-alive enabled | Rejected: unstable results and a recorded **10,475 ms CSI gap**. |
| TCP gateway | ESP32 repeatedly connects/closes gateway TCP sockets | AP downlink associated with TCP exchanges | Concurrency 4; interval 10 ms; timeout 50 ms; ports 80/53 | Integrated-path results approximately **30–36 callbacks/s O**; retained, not established as better than HTTP. |
| DNS | ESP32 queries router/resolver | AP downlink carrying DNS replies | UDP; small queries; resolver-dependent response | Approximately **29 callbacks/s O**; retained as LAN-only fallback. |
| ICMP gateway ping | ESP32 sends Echo Requests | Expected AP downlink carrying Echo Replies | Runs at 10/50/100 Hz; official-parity configuration included 1-byte payload | Replies arrived, but useful target-AP CSI was absent in several runs; not selected. |
| Null-data/ACK console experiment | ESP32 sends raw Null Data to AP | Intended returning ACK path | Approximately 100 transmissions/s | **0 CSI in the recorded 60-second experiment O**; negative result for that implementation/setup. |
| Natural traffic | No deliberate stimulus | Whatever eligible frames happen to arrive | Uncontrolled cadence/content | Historically sparse input or frozen sensing windows. |
| NTP proposal | Intended UDP request/reply | Expected AP downlink | NTP response discussed as 48 bytes | **Not implemented/tested.** It must not be presented as measured zero-CSI evidence. |

These rows are not all interchangeable controlled comparisons: firmware, recording load, radio conditions, and measurement boundaries differed between campaigns. The quiet-block 64 KiB/200,000-byte results do not establish statistical equivalence or a universal throughput advantage. The history explicitly retracts an earlier claim that 64 KiB improved peer consistency; interference had been misattributed to the protocol.

The history contains stronger wording about structural small-frame rejection. That wording does not replace the layered diagnostic evidence or establish a universal root cause. See §15.8.

### 15.3 Exact HTTP baseline variables

Implementation: [HTTP stimulus source](../main/ht_stimulus.c#L33-L278). Selection and experiment context: [history §§2/4/5/7](./EXPERIMENT_HISTORY.md#L41-L225).

| Variable | Established value or limitation |
|---|---|
| Receiver | ESP32-WROOM-32, classic ESP32. |
| Toolchain in documented campaign | ESP-IDF **v5.5.3**. |
| Application protocol | **HTTP over TCP**, not HTTPS. |
| Application server | `speed.cloudflare.com`. |
| Requested URL | `http://speed.cloudflare.com/__down?bytes=65536`. |
| On-air transmitter supplying downlink CSI | **Associated AP**, not Cloudflare directly. |
| HTTP method | GET. |
| Requested body | **65,536 bytes = 64 KiB**. |
| Application read-buffer size | **4,096 bytes C**. |
| HTTP timeout setting | **15,000 ms C**. |
| Concurrent HTTP transfers | One sequential stimulus task. |
| Inter-burst pause | **0 ms C**. |
| Connection reuse | Off in the selected configuration. |
| Request frequency | **Not fixed**; depends on transfer, connection setup, errors, and scheduling. |
| Failure retry | Kconfig-controlled; do not infer it from the HTTP timeout. |
| RF configuration in documented campaign | Channel **1 / 2412 MHz**, **20 MHz**. |
| Historical RF configuration | Some earlier experiments used channel **11**; do not combine them as identical conditions. |
| Downlink MCS/GI/retries/aggregation | AP-controlled; per-frame observations are needed. |
| Typical recorded CSI layout | Raw 256 bytes; compact valid data 214 bytes in described recordings; not a universal length for every frame type. |
| Classifier input | **51 LLTF complex pairs / 102 bytes**, not every raw CSI byte. |
| CSI stream period | Selected setting **0 ms**. |
| Internet dependency | DNS resolution and connectivity to Cloudflare are required. |
| Important unknown | True RF airtime, retry-adjusted traffic cost, and exact CSI-per-PPDU relationship were not established by body size alone. |

**A 65,536-byte HTTP body is not a 65,536-byte Wi-Fi frame.** Likewise, a 4,096-byte application read does not define TCP segmentation or Wi-Fi aggregation. Generic ping-frequency metadata must not be interpreted as HTTP request cadence. Source defaults, runtime settings, historical recordings, and the installed artifact are separate provenance items.

### 15.4 Official Espressif acquisition methods

Version-matched reference: [ESP-IDF v5.5.3, classic ESP32 CSI](https://docs.espressif.com/projects/esp-idf/en/v5.5.3/esp32/api-guides/wifi.html#wi-fi-channel-state-information).

The upstream settings below describe the inspected source branches. They are not evidence that those examples achieved the configured rate on this AP.

| Method/source | Topology and generator | Frame measured | RF/settings | Payload and pacing | Constraint for our project |
|---|---|---|---|---|---|
| CSI API with existing traffic | Receiver observes eligible received packets | Packet's available LLTF/HT-LTF/STBC-HT-LTF | Depends on actual received PHY and CSI configuration | No generator or fixed rate is provided by the CSI API | Enabling CSI does not guarantee continuous input. |
| [`csi_recv_router`](https://github.com/espressif/esp-csi/blob/master/examples/get-started/csi_recv_router/main/app_main.c) | One ESP32 associated with AP; ESP32 pings gateway | AP-origin received packet | AP controls channel/downlink PHY; callback filters AP BSSID | **1-byte ping payload; 100 Hz C; 10 ms interval C** | Closest official architecture to our setup; the completed experiments demonstrate unreliability there. |
| Two associated devices, [official architecture description](https://github.com/espressif/esp-csi#how-to-get-csi) | Another ESP32 supplies traffic while devices share a router/channel | Received frames from the other device, where exposed/accepted | AP/network-dependent; source-peer selection matters | No universal payload/rate in the architectural description | Requires an additional device; physical sensing link may differ from AP→receiver. |
| [`csi_send` + `csi_recv`](https://github.com/espressif/esp-csi/tree/master/examples/get-started) | Dedicated ESP32 sender and receiver; **ESP-NOW broadcast** | Sender's vendor-specific action frames | **Channel 11; 2.4 GHz; HT40; MCS0; long GI C** | **4-byte counter; 100 sends/s C** | Sender controls more variables; default HT40 is not the classifier's current HT20 input contract. |
| [`console_test`, ping branch](https://github.com/espressif/esp-csi/blob/master/examples/esp-radar/console_test/main/app_main.c) | Associated ESP32 pings gateway through esp-radar | AP-origin frames accepted by radar filters | AP BSSID/source filter and receiver destination filter | 1-byte payload; configurable send interval | Adds component/filter behavior beyond the direct CSI API example. |
| `console_test`, Null Data branch | ESP32 sends raw Null Data to associated AP | Intended returning ACK acquisition | **Legacy OFDM 6 Mbps C**; `dump_ack_en` requested | **24-byte MAC header passed to TX API**; configurable interval | Distinguish ACK capture from receiving another device's data frame; the tested branch produced zero usable CSI. |
| [ESP-Crab](https://github.com/espressif/esp-csi/blob/master/examples/esp-crab/slave_send/main/app_main.c) | Dedicated sender with receiver nodes | ESP-NOW broadcast frames | **Channel 40; 5 GHz; HT40; MCS0; long GI C** | **4-byte counter; 40 sends/s C** | This 5 GHz configuration is **not supported by classic WROOM-32**. |

The API, an architectural example, and a complete source implementation are different evidence levels. The official README also describes dedicated broadcast-sender architectures; its general accuracy/reliability statements are not measurements for this project. Classic WROOM-32's 2.4 GHz capability must not be confused with the current classifier's narrower 20 MHz layout contract.

#### 15.4.1 Receiver configuration differences within official examples

For the classic-ESP32 branches inspected: [router receiver source](https://github.com/espressif/esp-csi/blob/master/examples/get-started/csi_recv_router/main/app_main.c) and [dedicated receiver source](https://github.com/espressif/esp-csi/blob/master/examples/get-started/csi_recv/main/app_main.c).

| Receiver variable | Router example | Dedicated ESP-NOW receiver |
|---|---|---|
| LLTF enabled | Yes | Yes |
| HT-LTF enabled | **No** | **Yes** |
| STBC HT-LTF enabled | No | Yes |
| LTF merge | Enabled | Enabled |
| Adjacent-subcarrier channel filter | Enabled | Enabled |
| Manual scaling | Enabled | Disabled |
| Scale shift | `true`, effectively 1 | 0 |
| Promiscuous enable | No explicit enable in that example's CSI initialization | Explicitly enabled |
| Source filtering | Associated AP BSSID | Fixed dedicated-sender MAC |
| Wi-Fi power save | Connection-helper configuration; not established by CSI initialization alone | Explicit `WIFI_PS_NONE` |
| Output | CSI and RX metadata printed through console | CSI, metadata, and sender counter printed through console |

**Standard Espressif acquisition is not one identical configuration.** The official v5.5.3 guide states that CSI is estimated when packets are received, available LTFs depend on the received packet, the callback runs in the Wi-Fi task, and lengthy work should be moved to a queue. `first_word_invalid` marks the first **four bytes** invalid. The guide also documents non-HT CSI, so **CSI universally requires HT data packets** is not a valid general explanation for the ping failure.

### 15.5 Acquisition in other projects

#### 15.5.1 ESPectre traffic modes

Sources: [CSI acquisition guide](https://github.com/francescopace/espectre/blob/main/docs/CSI.md) and [SDK settings](https://github.com/francescopace/espectre/blob/main/docs/SDK.md). This is a motion-sensing project, not evidence of validated fall detection on our target.

| Mode | Generator → destination | Measurement source | Payload/pacing variables | Important conditions |
|---|---|---|---|---|
| Internal `ping` | ESP32 → gateway/configured IP | Incoming Echo Reply traffic | Default target **100 pps C**; documented internal example has no extra Echo payload | Destination must answer; AP downlink PHY remains AP-controlled. |
| Internal `dns` | ESP32 → resolver, UDP port 53 | DNS response traffic | Documented root query **17 bytes**; response length variable | Resolver required; illustrative 100-byte responses in its airtime model are **not measured defaults**. |
| Internal `dns_tcp` | ESP32 → resolver over persistent TCP | DNS/TCP response traffic | Persistent connection; DNS length prefix; response and TCP ACK behavior variable | Different from our connect→close TCP stimulus. |
| Internal `wifi_raw`, AP destination | ESP32 → associated AP | **Returning ACK CSI** | Legacy OFDM **6 Mbps C**; Null Data header | Requires supported ACK capture and LLTF profile. |
| Direct `wifi_raw`, explicit peer | ESP32 A → ESP32 B | B measures incoming Null Data; A measures B's ACK | **HT20 MCS0, long GI** on 2.4 GHz; padded **26-byte TX buffer / 30 bytes including FCS** | Same channel; explicit addressing; two devices. |
| External ICMP | Host → receiver IP | Incoming Echo Requests | Host-controlled rate; receiver replies | Distinct from receiver-initiated gateway ping. |
| External UDP | Host → receiver unicast/multicast | Incoming marker packets | **4-byte marker; UDP port 5555** default | No application reply; source recommends attention to receiver uplink activity. |
| External ESP-NOW | Dedicated sender → receiver | Incoming unencrypted unicast ESP-NOW | Match sender PHY to receiver profile; HT20 MCS0 supported | Default ESP-NOW 1 Mbps is not equivalent to configured OFDM/HT operation. |

Relevant inspected ESPectre settings:

- Default `csi_target_pps`: **100 C**, configurable.
- Capture bandwidth: **20 MHz**.
- No promiscuous mode in its documented runtime.
- Classic ESP32 station TX default: **HT20 MCS0 / 6.5 Mbps**, with stated fallback conditions; this does not force the AP's downlink rate.
- Recommended TX/RX A-MPDU settings: disabled.
- Recommended FreeRTOS tick rate: **1000 Hz**, unlike the **100 Hz** documented in our acquisition campaign.
- Retransmitted frames already measured are discarded.
- ACK capture is unavailable on its documented ESP32-C6 path.

These are **upstream project settings**, not validated changes for our ESP-IDF v5.5.3 firmware. Some hardware findings explicitly concern **v5.5.5 and different chips**. The relevant version-specific examples and limitations are in its CSI guide; they do not prove a fix for the WROOM-32/AP combination.

#### 15.5.2 Other extraction toolkits

| Project | Acquisition mechanism | Controllable/recorded variables | CSI output | Applicability |
|---|---|---|---|---|
| [Intel 5300 CSI Tool](https://dhalperi.github.io/linux-80211n-csitool/faq.html) | CSI from received 802.11n traffic; supports controlled/injected transmission workflows | TX rate flags, MCS, bandwidth, antenna masks, GI; RX timestamps, Ntx/Nrx, RSSI, AGC, noise, measurement counter | **Ntx × Nrx × 30** complex values | Explains many paper setups; hardware/driver not transferable to ESP32. |
| [Atheros CSI Tool](https://wands.hk/external/wifi/AtherosCSI/index.html) | ath9k-based per-packet extraction; transmitter configuration determines traffic | Channel, bandwidth, MCS, TX power/chains; timestamps, payload, RSSI and rate | Typically **56 subcarriers at 20 MHz**, **114 at 40 MHz**, per spatial link | More controllable router/NIC testbeds; not our driver. |
| [Nexmon CSI](https://github.com/seemoo-lab/nexmon_csi) | Extracts CSI from matching OFDM frames; traffic can be injected or generated through connected devices, e.g. iperf | Channel/bandwidth, MAC-address filter, frame-control-byte filter, core/stream masks | **64/128/256 bins for 20/40/80 MHz**; export per selected core/stream | Broadcom firmware-specific; raw-bin count includes guard/null bins. |

Important Nexmon distinction: **UDP port 5500 carries exported CSI**. It does not identify the protocol that generated the on-air sensing traffic. Multiple export records can correspond to one received frame when multiple core/stream combinations are selected. Core/stream selection describes the Wi-Fi measurement, not the host CPU core used for processing.

The [ESP-IDF v5.5.3 ESP-NOW reference](https://docs.espressif.com/projects/esp-idf/en/v5.5.3/esp32/api-reference/network/esp_now.html) distinguishes default ESP-NOW behavior from explicitly configured PHY/rate operation. A paper or project name alone does not establish a shared payload, rate, or capture format.

### 15.6 Acquisition reported in papers

#### 15.6.1 Sources with usable primary acquisition details

| Paper/dataset | TX/RX and extraction | Traffic mechanism | RF configuration | Rate and CSI dimensions | Missing or non-equivalent variables |
|---|---|---|---|---|---|
| [SiFall](https://arxiv.org/html/2301.03773v2), §4.1 | Two COMPEX WPJ558/QCA9558 devices; Atheros CSI Tool | Controlled packet transmission; exact application protocol NR | **2.4 GHz; 20 MHz; fixed MCS**, index NR | **200 packets/s C**; exact selected antenna matrix NR in inspected setup passage | Packet length, channel, GI, achieved jitter/loss, duty cycle and retry settings NR. |
| [TCS-Fall](https://pmc.ncbi.nlm.nih.gov/articles/PMC11151769/) | Two Intel 5300-equipped computers; Intel CSI Tool | Exact generator/protocol NR | Channel/band/BW/MCS NR | **1000 packets/s R** in sample standardization; 3×3 links described, but **1×3×30 = 90** values retained per timestep | No complete transmission recipe or achieved-timing audit. |
| [STC-NLSTMNet—StanWiFi](https://pmc.ncbi.nlm.nih.gov/articles/PMC9823549/), §4.2 | One-antenna router TX; Intel 5300 RX with three antennas | Generator/protocol NR | RF channel/band/BW NR; **3 m LOS** placement reported | **1000 Hz R**; 90 amplitude channels | Payload, actual timing, retransmissions and sender settings NR. |
| STC-NLSTMNet—Multi-environment | Reused dataset | Acquisition recipe not established in inspected dataset subsection | NR | Do not inherit StanWiFi's rate/configuration automatically | Requires original dataset acquisition documentation. |
| [IntechOpen HAR comparison](https://www.intechopen.com/journals/1/articles/693), §§2.2/3.1 | Archer AX23 AP → Raspberry Pi 4/BCM43455C0; Nexmon | **Passive beacon capture** | **5 GHz, channel 36; configured 80 MHz** | Beacon interval **50 ms C**, approximately **20/s**; 100-frame segments; 256 raw bins | Paper acknowledges beacons occupy the primary **20 MHz**; configured 80 MHz is not 80 MHz of usable beacon information. |
| [UniFi—CommCSI-HAR](https://arxiv.org/html/2512.22143v1), §5.1.1 | ASUS AP, video-streaming phones; two Raspberry Pi 3B+ Nexmon sniffers | Existing communication traffic; data/management/control frames | **2.4 and 5 GHz**; 5 GHz monitored at 80 MHz, effective width varies **20–80 MHz** | **Irregular**, not a fixed target rate | Traffic load/content and per-frame PHY vary; not a single-receiver fall-detection benchmark. |
| UniFi—controlled reference | Dedicated Raspberry Pi injectors and sniffers | Dummy QoS data injection | Separate reference channels in 2.4/5 GHz | Approximately **150 Hz transmission R**, subsequently **downsampled to 100 Hz** | 100 Hz is processing rate, not original transmission cadence. |

Clarifications to earlier summaries:

1. TCS-Fall provides a **1000-packet/s sample convention**, although its complete acquisition configuration remains missing from the inspected source. This supplements the earlier unspecified acquisition-rate entry; it does not establish measured timing regularity.
2. The accessible IntechOpen source describes **beacon-based acquisition**, not an unspecified traffic generator. A configured 80 MHz channel and 256 output bins must not be mistaken for 80 MHz of occupied beacon bandwidth.
3. TCS-Fall's described 3×3×30 raw link structure is not its retained 90-channel input. Physical antennas, transmitted spatial streams, selected links, and model channels are different quantities.

#### 15.6.2 Remaining papers in the matrix: verification limits

The following values are carried from §1 of this document. They are **secondary summaries, not newly verified acquisition recipes**. `NV` does not mean the paper necessarily omitted the settings. The publication/source links identify the reference, not successful full-text verification during the preceding comparison.

| Study | Existing acquisition summary | What remains NV |
|---|---|---|
| [WiFall, original 2014 study](https://doi.org/10.1109/INFOCOM.2014.6847948) | Commodity 802.11n NIC | Exact chipset/version, generator, payload, band/BW/channel, rate and antenna configuration. |
| [Anti-Fall](https://arxiv.org/abs/1507.01057) | Intel 5300; approximately 100 packets/s; 5 GHz; two receive links | Full transmission recipe; accessible abstract does not establish these settings. |
| [RT-Fall](https://doi.org/10.1109/TMC.2016.2557795) | Intel 5300; approximately 100 packets/s; 5 GHz | Generator, payload, fixed PHY, achieved timing and exact receiver configuration. |
| FallDeFi—Palipana dissertation reference in §1 | Intel 5300; 5.2 GHz; processing references a 1 kHz grid | **Interpolation/processing grid must not be assumed to be verified TX cadence**. |
| [Damodaran](https://doi.org/10.1007/s42486-020-00027-1) | Two Intel 5300 laptops; 20 MHz; one TX/three RX; 90 channels | Protocol, packet size, band/channel, nominal and achieved cadence. |
| [Nakamura](https://doi.org/10.1109/JIOT.2022.3152315) | Commodity CSI across two rooms | Full acquisition settings. |
| [Surasakhon](https://doi.org/10.1504/IJSNET.2022.127111) | Acquisition detail unavailable in current summary | Full acquisition settings. |
| [El-Sayed/UT-HAR](https://doi.org/10.1007/s00521-021-06787-w) | Intel 5300; three RX antennas; approximately 1 kHz | Original dataset generator/PHY configuration and achieved timing. |
| [Mattela](https://doi.org/10.1007/s42979-022-01111-2) | Acquisition detail unavailable in current summary | Full acquisition settings. |
| [Chu](https://doi.org/10.1109/ACCESS.2023.3300726) | Intel 5300; one TX/three RX; approximately 1 kHz | Complete generation recipe and RF settings; a primary PDF was located but not successfully text-verified in the preceding comparison. |
| [DapFall](https://doi.org/10.1109/JSEN.2025.3544552) | Dynamic-amplitude representation | Device, traffic generator and RF/timing settings. |
| [AmFall](https://doi.org/10.1109/JIOT.2025.3585401) | Amplitude/selected-subcarrier processing | Device, traffic generator and RF/timing settings. |
| [Construction-worker mobile receiver](https://doi.org/10.1016/j.dibe.2025.100745) | TP-Link router; Nexus 6P/BCM4358/Nexmon; 2.4 GHz; PSPing mentioned in search excerpts | Exact PSPing mode, target/destination, frame addressing, BW/channel, packet size and actual timing. |
| [Adaptive fall detection, 2025](https://doi.org/10.1109/MeMeA65319.2025.11068083) | Acquisition detail unavailable in current summary | Full acquisition settings. |

Do not assume that every Intel 5300 paper used ping, every Nexmon study used iperf, or every 100 Hz value meant measured CSI callbacks. Dataset names or system names shared across papers are not sufficient to establish identical hardware or acquisition provenance.

### 15.7 Complete acquisition-variable checklist

This is the field set needed to make the methods genuinely comparable. Protocol plus FPS is insufficient. This checklist documents comparison requirements; it is not a claim that every field is already captured in every experiment or recording.

| Group | Variables to document |
|---|---|
| Provenance | Experiment date; paper/version; repository commit; firmware hash; SDK/driver/component versions; source configuration versus runtime readback. |
| Topology | Who generates requests; application endpoint; actual RF transmitter; receiver; AP forwarding; wired/wireless server; mesh/backhaul; number of sensing links. |
| Hardware | Board/NIC/AP model; chipset/revision; physical antennas; active RF chains; transmitted spatial streams; receiver antenna selection. |
| Placement | TX/RX distance, height and orientation; LOS/NLOS; obstacles; activity position relative to link; antenna type. |
| RF allocation | Band; primary channel; secondary channel; configured bandwidth; **actual per-packet bandwidth**; country/regulatory settings. |
| PHY | Legacy/HT/VHT/HE format; MCS/rate; GI; STBC; coding; sounding mode; TX power; automatic rate adaptation. |
| MAC addressing | Source/transmitter/BSSID/destination addresses; unicast/multicast/broadcast; ToDS/FromDS; peer filter; frame type/subtype. |
| Application traffic | HTTP/ICMP/TCP/UDP/ESP-NOW/raw frame; endpoint/port; request/response direction; payload length; requested body length. |
| Framing | TCP segment size; MAC frame length; PPDU length; A-MPDU/A-MSDU; fragmentation; FCS/header inclusion in reported sizes. |
| Pacing | Configured cycles/s; packet interval; burst length; pause; concurrency; warm-up; timeout; retry/backoff; connection reuse. |
| Receiver operation | Association state; promiscuous mode; Wi-Fi power save; scan/reconnect behavior; channel changes; live competing traffic. |
| CSI configuration | Enabled LTFs; merge; adjacent-subcarrier filter; scaling/shift; ACK capture; capture profile; error rejection. |
| CSI representation | Raw length; valid length; subcarrier order; I/Q order; integer format; missing/null/guard/pilot bins; `first_word_invalid`; spatial-link dimensions. |
| RX metadata | Device timestamp and units; RSSI; noise floor; rate/MCS; BW; GI; aggregation; STBC; antenna; receive-error flags; gain where genuinely available. |
| Execution load | CPU frequency; task priorities/core placement; tick rate; callback work; buffer/queue sizes; logging and simultaneous network services. |
| Export path | UART/network transport; baud/rate; binary/text size; batching; throttle; recording load; host parser; CSI-record multiplicity per RF frame. |
| Quality/results | Generated requests; successful replies; raw callbacks; target-peer callbacks; accepted frames; classifier admissions; recorded frames; errors/drops. |
| Timing quality | Mean/median intervals; p95/p99; maximum gap; interval CV; empty-time-bin coverage; window-duration distribution. |
| Cost/reliability | Application bytes versus RF airtime; retransmissions; channel utilization; network throughput impact; power; CPU/heap; stalls/reboots. |
| Experimental control | Same build/settings/load; matched measurement interval; activity protocol; interference observations; repeated blocks; exclusions and uncertainty. |

For classic WROOM-32, do not treat zero-valued AGC/FFT fields as measured gain merely because newer chips or another toolkit expose gain information. Application bytes cannot establish RF airtime without actual framing, PHY, retries, and channel-access information. RX sequence gaps alone cannot identify the layer that lost data.

### 15.8 What the comparison establishes about the failed standard approach

The strongest evidence remains: **ping replies can reach the network stack without producing usable target-AP CSI**.

The [AP investigation](../../../../docs/investigasi-kompatibilitas-ap-csi.md#L5-L28) distinguishes network reception, promiscuous reception, CSI callbacks, and peer acceptance. The comparisons establish different capture/filter/PHY paths, but **they do not establish one root cause**.

- Small ping payloads are **not proven universally incapable** of supplying CSI.
- Increasing configured ping rate did not solve the tested failure.
- Another project's working ping/ACK path does not prove ours should work unchanged.
- A console null-data failure does not rule out every possible ACK-capture implementation.
- HTTP success is established for the tested setup; it does not by itself prove which driver/AP behavior caused ping failure.
- Absent target-AP callbacks and rejection of unrelated peer frames are separate observations. A downstream peer filter does not independently explain why target-AP CSI callbacks were absent.
- Historical channel-one/channel-eleven results must retain date, placement, firmware, traffic, and interference differences; they are not a controlled channel-only causal comparison.

**Technical conclusion: retain HTTP `65536 / pause=0 / connection reuse off` as the experimentally informed acquisition baseline.** The useful comparison is the full acquisition contract above, not restarting the stimulus search or replacing an observed result with a documentation default.

This addition is documentation-only. No firmware/configuration changes, new acquisition experiments, model training, builds, flashing, or commits were performed to create it.