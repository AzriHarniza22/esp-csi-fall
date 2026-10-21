# Aturan kerja untuk proyek ini

## Preflight wajib

Sebelum menyentuh perilaku runtime, baca `docs/agent-preflight.md` dan
tuliskan bukti `Dokumen: ...` + `Kutipan: ...` sebelum edit pertama. Daftar
sumber, versi terpasang, dan format trailer commit ada di sana. Commit yang
menyentuh `main/`, `tools/`, `sdkconfig*`, atau `managed_components/` tanpa
trailer `Docs:` ditolak oleh `.githooks/commit-msg`.

## Log perubahan wajib

Setiap perubahan kode **wajib** dicatat di `docs/agent-changes.md` sebelum
commit: file yang berubah, apa yang berubah, alasannya, dokumen yang dipakai,
dan verifikasinya. Ini bukan ringkasan diff. Commit yang mengubah kode tanpa
menyentuh file itu ditolak oleh `.githooks/commit-msg`. Format entri ada di
bagian atas `docs/agent-changes.md`; tambahkan entri baru di paling bawah.

## Riset dulu, baru mengubah perilaku

Sebelum mengubah apa pun yang mengubah perilaku runtime — driver Wi-Fi/BT,
konfigurasi radio, parameter keamanan, atau protokol — **buka dokumentasi
resmi atau issue tracker lebih dulu.** Bukan setelah gagal.

Alat, dari yang paling otoritatif:

1. `espressif-docs_search_espressif_sources` — dokumentasi ESP-IDF resmi
2. `context7_query-docs` dengan libraryId
   `/websites/espressif_projects_esp-idf_en_v5_5_3_esp32`
3. `gh_grep_searchGitHub` atau pencarian web — issue `espressif/esp-idf` dan
   `espressif/esp-faq`

## Perhatikan versinya

Proyek ini di-build dengan **ESP-IDF v5.5.3**, di
`/home/azri/.espressif/v5.5.3/esp-idf`.

MCP `esp-idf` yang terdaftar di `~/.config/opencode/opencode.jsonc` menunjuk ke
**v6.0**. Jangan memakainya untuk pertanyaan tentang proyek ini — hasilnya
dokumentasi versi yang salah, dan itu lebih berbahaya daripada tidak membuka
dokumentasi sama sekali. Kalau hanya v6.0 yang tersedia, sebutkan ketidakcocokan
versinya secara eksplisit sebelum menjawab.

## Cara memakainya

Dokumennya invaluable bukan untuk mengonfirmasi tebakan yang sudah saya buat,
tapi untuk **menghentikan tebakan yang akan masuk ke kode.**

Bukti dari sesi terakhir, tiga kali berbeda:

- `threshold.authmode` — tebakan saya (tambah WPA3 ke mask) terdengar masuk akal
  dan justru memperburuk masalah. Dokumentasi menyatakan itu *mode keamanan
  terlemah yang masih diterima*, bukan daftar yang dicoba. Tebakan itu kalau
  tidak dicek akan masuk ke firmware.
- `esp_wifi_connect()` — dokumentasi menyatakan fungsi itu mencoba **sekali**.
  Logika retry yang sudah ada di proyek ini mungkin terlihat wajar tapi
  tidak sesuai perilaku driver.
- Scan dan connect saling membatalkan — tidak terlihat dari kode mana pun,
  hanya dari halaman coexist.

Kalau dokumentasi dan pengamatan perangkat bertentangan, **pengamatan yang
menang**, dan tuliskan secara eksplisit bagian mana yang tidak cocok.

Kalau tidak menemukan apa-apa, katakan tidak ditemukan. Jangan diisi dengan
penalaran lalu menyebutnya fakta.

Kalau dokumentasinya ternyata keliru, catat di pesan commit. Dokumentasi yang
menyesatkan adalah bug yang perlu dilaporkan ke Espressif.

## Jangan menebak angka

Sebelum menyebut angka sebagai fakta, pastikan itu berasal dari:

- log perangkat, atau
- output pengujian, atau
- dokumen yang mengatakannya

Pernah ada angka yang disebut "terukur" padahal hanya perkiraan. Kalau belum
diukur, tulis sebagai perkiraan.

## Alat yang tersedia tapi mudah terlewat

- `playwright` MCP — untuk menguji halaman web di browser sungguhan. Sengaja
  tersedia; jangan menggantinya dengan perintah CLI manual kalau tidak perlu.
- `serial` MCP — sudah dikonfigurasi untuk `/dev/ttyUSB*`.
