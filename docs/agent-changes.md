# Log perubahan oleh AI agent

File ini **wajib** diperbarui setiap kali agent mengubah kode. Satu entri per
perubahan logis, ditulis sebelum commit. Tujuannya agar alasan keputusan tidak
hilang di riwayat chat dan bisa ditinjau tanpa membedah diff.

## Aturan

- Tambahkan entri baru di **paling bawah**, jangan menimpa entri lama.
- Satu entri boleh mencakup beberapa file bila perubahannya satu tujuan.
- Tulis alasan yang bisa diperiksa, bukan "memperbaiki bug". Sebutkan gejala,
  penyebab, dan bukti (log, angka pengukuran, dokumen).
- Cantumkan sumber dokumentasi. Bila tidak ada, tulis eksplisit
  `tidak ditemukan` beserta alasannya.
- Jangan menyalin seluruh diff. Ringkas keputusan dan konsekuensinya.
- Bila perubahan dibatalkan kemudian, tambahkan entri baru yang menyebut
  pembatalannya; jangan menghapus entri lama.

## Format entri

```markdown
## YYYY-MM-DD — <judul singkat>

- Agent/tool: <nama agent atau model>
- Branch/commit: <branch> / <hash atau "belum di-commit">
- File: <daftar file yang berubah>
- Perubahan: <apa yang berubah, secara perilaku>
- Alasan: <gejala/penyebab/bukti yang mendorong perubahan>
- Dokumen: <komponen> <versi> <path/URL> — "<kutipan singkat>"
- Verifikasi: <build/flash/log/uji yang benar-benar dijalankan>
```

## Entri

## 2026-10-20 — Gate dokumentasi dan log perubahan wajib

- Agent/tool: opencode (deepseek-v4.1-flash-free)
- Branch/commit: default / belum di-commit
- File: `AGENTS.md`, `docs/agent-preflight.md`, `docs/agent-changes.md`,
  `.githooks/commit-msg`, `.cursor/rules/espressif-docs.mdc`,
  `.github/copilot-instructions.md`, `CLAUDE.md`
- Perubahan: menambahkan preflight dokumentasi wajib dan log perubahan wajib.
  Hook `commit-msg` sekarang menolak commit yang mengubah kode tanpa entri di
  file ini, dan tetap menolak commit yang menyentuh perilaku runtime tanpa
  trailer `Docs:`.
- Alasan: instruksi di `AGENTS.md` saja tidak menjamin dokumen dibaca atau
  alasan perubahan tercatat. Gate yang bisa diperiksa membuat keduanya dapat
  diaudit dan berlaku untuk semua agent yang memakai hook repo ini.
- Dokumen: tidak berlaku (perubahan tooling repo, bukan perilaku runtime).
- Verifikasi: hook diuji dengan file sementara di `main/` — tanpa entri
  changelog `rc=1`, dengan entri `rc=0`, tanpa trailer `Docs:` `rc=1`.
