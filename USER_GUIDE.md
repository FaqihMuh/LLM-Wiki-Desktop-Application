# LLM Wiki — Panduan Pengguna

Dokumen ini adalah panduan untuk **pengguna akhir** aplikasi LLM Wiki (desktop, Windows). Dokumen ini terpisah dari `docs/` (spesifikasi implementasi internal) dan `README_BUILD.md` (panduan build untuk developer) — isinya hanya menjelaskan cara memakai aplikasi yang sudah terinstal, berdasarkan struktur dan perilaku aktual aplikasi.

Untuk video dokumentasi aplikasi dapat dilihat pada laman YouTube ini: https://www.youtube.com/watch?v=RrCo1RGOuts

---

## A. Instalasi

1. Jalankan installer (`LLM_Wiki_Setup_1.0.0.exe`) dengan klik ganda.
2. Windows akan meminta izin administrator (User Account Control) — installer memerlukan ini untuk menginstal ke `Program Files`.
3. Ikuti wizard: pilih apakah ingin membuat shortcut desktop, lalu klik Install.
4. Aplikasi terinstal ke `Program Files\LLM Wiki\` (lokasi standar Windows untuk aplikasi 64-bit).

**Kebutuhan sistem:**
- Windows 64-bit.
- Hak administrator saat instalasi (bukan saat pemakaian sehari-hari).

**Dependency eksternal yang wajib ada terpisah:**
- **Claude CLI** — aplikasi ini menjalankan operasi Ingest dan Query lewat `claude` yang harus sudah terpasang dan tersedia di PATH sistem Anda. Ini **tidak** ikut terpasang oleh installer LLM Wiki. Jika belum ada, aplikasi akan mendeteksinya saat dibuka dan menampilkan link ke panduan instalasi resmi Claude CLI.

**Yang TIDAK perlu Anda instal terpisah:**
- Tesseract OCR — sudah dibundel di dalam aplikasi (lihat bagian Ingest di bawah), tidak perlu instalasi Tesseract sendiri.
- Python — aplikasi sudah dikemas sebagai executable mandiri.

Setelah instalasi selesai, wizard menawarkan untuk langsung membuka aplikasi.

---

## B. Menjalankan Aplikasi Pertama Kali

1. Buka **LLM Wiki** dari Start Menu atau shortcut desktop.
2. Aplikasi memeriksa apakah Claude CLI tersedia. Jika tidak ditemukan, muncul dialog "Claude CLI Required" — instal Claude CLI dulu, lalu buka ulang aplikasi.
3. Jika Claude CLI ditemukan dan ini pertama kali aplikasi dijalankan, muncul dialog **"Welcome to LLM Wiki"** meminta Anda memilih lokasi **workspace** — folder di komputer Anda tempat seluruh pengetahuan (Persistent Memory) akan disimpan. Lokasi default yang disarankan adalah `Documents\LLM Wiki`, tapi Anda bisa memilih folder lain lewat tombol Browse.
4. Setelah dipilih, aplikasi otomatis membuat struktur folder workspace di lokasi tersebut dan membuka jendela utama.

**Installation directory vs. Workspace — dua hal yang berbeda:**
- **Installation directory** (`Program Files\LLM Wiki\`) — berisi program aplikasi itu sendiri (exe, library, template kosong). Anda tidak perlu dan tidak sebaiknya mengubah isi folder ini.
- **Workspace** (folder pilihan Anda, mis. `Documents\LLM Wiki`) — berisi seluruh pengetahuan yang benar-benar Anda kumpulkan: dokumen sumber, ringkasan, entity, index. Ini yang bertambah seiring Anda memakai aplikasi, dan **terpisah total** dari folder instalasi.

Jika di kemudian hari Anda ingin memakai workspace yang berbeda, pilihan workspace disimpan di file config (lihat bagian Configuration).

---

## C. Struktur Workspace

Sebuah workspace LLM Wiki berisi struktur berikut:

```
workspace/
├── CLAUDE.md              (aturan operasi wiki — jangan diedit manual)
├── docs/                  (spesifikasi Ingest/Query/Maintenance yang dipakai Claude)
├── raw/                   (dokumen sumber yang sudah/akan di-ingest — PDF, PNG, JPG, JPEG)
└── wiki/                  (Persistent Memory — hasil pengetahuan)
    ├── index.md           (Source Registry + daftar semua Summary/Entity Pages)
    ├── log.md              (catatan riwayat setiap operasi Ingest, berurutan kronologis)
    ├── entities/           (satu file .md per entity/konsep pengetahuan)
    ├── summaries/          (satu file .md ringkasan per dokumen yang di-ingest)
    ├── concepts/           (dipakai oleh workflow internal)
    └── query_synthesis/    (dipakai oleh workflow internal)
```

**Penjelasan singkat tiap bagian:**
- **`raw/`** — tempat dokumen sumber (PDF/gambar) yang ingin Anda proses berada.
- **`wiki/summaries/`** — satu halaman ringkasan per dokumen yang berhasil di-ingest.
- **`wiki/entities/`** — satu halaman per konsep pengetahuan (entity) yang terakumulasi lintas dokumen — inilah "Persistent Memory" yang sebenarnya, karena satu entity bisa diperbarui berulang kali oleh dokumen-dokumen berbeda.
- **`wiki/index.md`** — daftar utama: dokumen apa saja yang sudah di-ingest, dan entity/summary apa saja yang ada.
- **`wiki/log.md`** — riwayat operasi, bertambah terus (append-only), tidak pernah ditimpa.

Jangan mengedit file di dalam `wiki/` secara manual sambil aplikasi berjalan — biarkan Ingest yang mengelolanya, agar index dan log tetap konsisten.

---

## D. Configuration

- **Lokasi:** `%LOCALAPPDATA%\LLM Wiki\config.json` (folder profil Windows Anda, bukan folder instalasi maupun workspace).
- **Fungsi:** hanya menyimpan satu hal — path folder workspace yang sedang aktif (`workspace_path`).
- **Yang boleh Anda ubah:** memilih workspace yang berbeda dilakukan lewat aplikasi sendiri (bukan dengan mengedit file ini langsung), lewat dialog pemilihan workspace.
- **Yang sebaiknya tidak diubah manual:** mengedit `config.json` secara langsung berisiko — jika isinya tidak valid, aplikasi akan menganggap belum ada workspace tersimpan dan menampilkan dialog first-launch lagi. Jika ingin pindah workspace, gunakan cara resmi lewat aplikasi.

---

## E. Ingest

**Tujuan:** mengubah satu dokumen riset (PDF atau gambar) menjadi pengetahuan permanen di Persistent Memory.

**Cara pakai (halaman Ingest):**
1. Klik **Add Documents**, pilih satu atau beberapa file PDF/PNG/JPG/JPEG.
2. Pilih model Claude yang dipakai (**Claude Sonnet**, **Claude Opus**, atau **Claude Haiku**) lewat dropdown Model.
3. Klik **Start Ingest**. Dokumen diproses satu per satu sesuai urutan antrean (Queue).

**Rekomendasi model untuk Ingest: Claude Sonnet** (pilihan default dropdown). Ingest melibatkan pemahaman dokumen, ekstraksi entity, resolusi entity, sintesis pengetahuan, dan rekonsiliasi relationship — Sonnet direkomendasikan saat kualitas dan konsistensi Persistent Memory menjadi prioritas. **Claude Haiku** tetap bisa dipakai bila kecepatan/biaya lebih diprioritaskan, tetapi pemilihan model dapat menghasilkan keputusan entity yang berbeda. Rekomendasi ini bukan jaminan — validasi Post-Ingest (lihat di bawah) tetap berjalan sebagai pemeriksa konsistensi terlepas dari model yang dipilih.

**Apa yang terjadi di balik layar:**
- **Preprocessing/OCR:** dokumen dibaca dan diubah ke teks. Jika ada halaman yang tidak punya lapisan teks (misal hasil scan), halaman itu otomatis melalui OCR — deteksi area teks, lalu pengenalan karakter memakai Tesseract OCR yang **sudah dibundel di dalam aplikasi** (tidak perlu instalasi Tesseract terpisah, dan tidak bergantung pada instalasi Tesseract eksternal jika ada).
- Setelah teks lengkap diperoleh, Claude CLI dipanggil untuk menjalankan seluruh alur Ingest: memahami dokumen, membuat ringkasan, mengekstrak calon entity, memutuskan mana yang jadi entity baru/perluasan entity lama, memperbarui `wiki/entities/`, memperbarui `wiki/index.md`, dan mencatat ke `wiki/log.md`.
- Hasilnya: satu halaman **Summary** baru, entity baru dan/atau entity lama yang diperbarui.

**Status hasil di Execution Log dan Queue:**
- **SUCCESS (Completed)** — dokumen berhasil diproses lengkap, Persistent Memory diperbarui.
- **FAILED** — proses gagal di salah satu tahap (misal dokumen tidak terbaca) sebelum sempat mengubah apa pun; wiki tidak berubah.
- **ABORTED** — Anda menekan tombol Abort di tengah proses.

**Post-Ingest Validation:** setelah dokumen berhasil (SUCCESS), aplikasi otomatis memeriksa ulang konsistensi Persistent Memory (mirip pemeriksaan yang dilakukan Maintenance). Jika ditemukan hal kecil yang tidak konsisten (misal satu link ke entity yang belum ada), ini ditampilkan sebagai **baris WARNING di Execution Log** — dokumen tetap berstatus SUCCESS karena Ingest-nya sendiri memang berhasil; warning ini murni informasi tambahan untuk Anda tinjau, bukan tanda kegagalan.

---

## F. Query

**Tujuan:** bertanya kepada Persistent Memory, bukan kepada Claude secara umum — jawaban selalu diambil dari apa yang benar-benar sudah tersimpan di `wiki/` workspace Anda (index, entity, summary), bukan dari pengetahuan umum model.

**Cara pakai (halaman Query):**
1. Ketik pertanyaan Anda di kolom teks.
2. Pilih model (Sonnet/Opus/Haiku).
3. Klik **Query**.
4. Jawaban muncul di panel **Answer**. Entity yang benar-benar berhasil dibaca Claude untuk menyusun jawaban ditampilkan di panel **Entities Used** — ini menunjukkan sumber pengetahuan di balik jawaban tersebut, bukan tebakan.

Jika Persistent Memory belum punya bukti yang cukup untuk menjawab, aplikasi akan menyatakan informasi belum tersedia, bukan mengarang jawaban.

---

## G. Maintenance

**Tujuan:** pemeriksaan kesehatan struktural Persistent Memory — bukan pemeriksaan kebenaran ilmiah isi dokumen.

Maintenance **bersifat read-only** — ia hanya membaca dan melaporkan, **tidak pernah mengubah, memperbaiki, atau menghapus** file apa pun di `wiki/`.

**Cara pakai (halaman Maintenance):**
1. Pilih **Scope**: Entire Wiki, Entity Pages, atau Summary Pages.
2. Klik **Run Maintenance**.
3. Hasil ditampilkan dalam beberapa bagian:
   - **Wiki Health** — skor kesehatan keseluruhan (HEALTHY / WARNING / CRITICAL).
   - **Validation Summary** — hasil per kategori:
     - **Structure** — apakah struktur folder/file sesuai (nama file valid, tidak ada duplikat, dsb).
     - **Metadata** — apakah setiap entity punya metadata lengkap dan valid (tipe, status, confidence, tanggal, dsb).
     - **Relationship** — apakah link antar-halaman (`[[Nama_Entity]]`) mengarah ke halaman yang benar-benar ada.
     - **Source** — apakah entity/summary merujuk ke dokumen sumber yang benar-benar ada.
   - **Detected Issues** — daftar setiap masalah yang ditemukan, dengan severity (WARNING/CRITICAL), file yang terdampak, dan deskripsi.

**Tentang warning Relationship** (contoh: `[[Nama_Entity]]` yang tidak menemukan halaman tujuannya): ini adalah laporan diagnostik yang normal terjadi sesekali — **bukan berarti Ingest yang menghasilkannya gagal** (jika Ingest sudah menyatakan SUCCESS, dokumen tersebut memang berhasil diproses). Maintenance hanya melaporkan agar Anda tahu dan bisa meninjaunya; ia **tidak pernah memperbaikinya secara otomatis**. Perbaikan (jika Anda anggap perlu) dilakukan manual — misalnya membuka file entity terkait dan menyesuaikan link-nya.

---

## H. Knowledge Explorer

Menu di sidebar kiri untuk menjelajahi Persistent Memory workspace Anda:

- **Home** — ringkasan jumlah Raw Documents, Summaries, Entity Pages, dan Indexed Sources.
- **Raw Documents** — daftar dokumen sumber (PDF) di `raw/`.
- **Summaries** — daftar dan isi halaman ringkasan per dokumen.
- **Entities** — tabel seluruh entity beserta pencarian, dan panel Entity Viewer untuk membaca isi lengkap satu entity (definisi, prinsip, relasi, dsb).
- **Index** — isi `wiki/index.md`: Source Registry dan daftar Summary/Entity Pages.
- **Operation Log** — riwayat seluruh operasi (Ingest) yang pernah dijalankan pada workspace ini.

Seluruh halaman Knowledge Explorer bersifat read-only (murni untuk melihat).

---

## I. Troubleshooting

**OCR gagal / dokumen tidak bisa diproses:**
Periksa Execution Log pada halaman Ingest — pesan error akan menyebutkan tahap yang gagal (misal preprocessing dokumen). Jika error terjadi sebelum Claude CLI dipanggil, Persistent Memory dijamin tidak berubah (tidak ada update sebagian).

**Workspace tidak ditemukan:**
Jika folder workspace yang tersimpan di config sudah dipindah/dihapus, aplikasi akan menawarkan untuk membuatnya ulang di lokasi yang sama, atau Anda bisa memilih workspace lain.

**Claude CLI tidak tersedia:**
Aplikasi menampilkan dialog "Claude CLI Required" saat startup dengan tombol untuk membuka panduan instalasi resmi. Ingest dan Query tidak bisa berjalan tanpa Claude CLI terpasang di PATH sistem.

**Maintenance menemukan WARNING (relationship tidak resolve, metadata tidak lengkap, dsb.):**
Ini adalah laporan, bukan kegagalan aplikasi. Tinjau detail di **Detected Issues**, lalu putuskan sendiri apakah perlu diperbaiki manual — Maintenance tidak akan mengubah apa pun secara otomatis.

**Aplikasi tidak dapat menemukan resource (template workspace, dsb.):**
Jarang terjadi pada instalasi normal — biasanya menandakan instalasi rusak/tidak lengkap. Coba uninstall lalu install ulang lewat installer resmi.

---

## Uninstall

Uninstall lewat **Settings → Apps** Windows (atau shortcut "Uninstall LLM Wiki" di Start Menu). Proses uninstall hanya menghapus isi folder instalasi (`Program Files\LLM Wiki\`) — **workspace Anda (folder yang berisi `wiki/`, `raw/`, dst., misalnya di `Documents\LLM Wiki` atau lokasi lain yang Anda pilih) tidak ikut terhapus**, karena workspace memang disimpan terpisah dari folder instalasi.
