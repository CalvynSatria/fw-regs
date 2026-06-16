Firewall TNC Tester — Build & Run Guide
======================================

STRUKTUR FOLDER
---------------
D:\Automation_Script\Firewall\New-Firewall\
├── firewall-tnc.py            <-- script utama
├── main.spec                  <-- konfigurasi PyInstaller
├── build.bat                  <-- double-click untuk build
├── source_excel\
│   └── test-fw-1.xlsx         <-- taruh file input di sini
├── result\                    <-- output otomatis masuk sini
└── dist\
    └── firewall-tnc.exe       <-- hasil build (ini yang dijalankan)


CARA BUILD (.exe)
-----------------
1. Buka Command Prompt di folder New-Firewall
2. Jalankan:     build.bat
3. Tunggu sampai selesai (1-3 menit pertama kali)
4. Ambil exe di: dist\firewall-tnc.exe


CARA JALANKAN EXE
-----------------
1. Taruh file Excel input di folder source_excel\ (sejajar dengan folder dist\)
2. Double-click dist\firewall-tnc.exe
   ATAU dari cmd:   cd D:\...\New-Firewall\dist && firewall-tnc.exe
3. Output xlsx otomatis tersimpan di folder result\ (sejajar New-Firewall)

Script otomatis cari folder 'source_excel' dengan urutan:
  1. dist\source_excel\        (kalau data di-copy ke dalam dist)
  2. New-Firewall\source_excel\ (parent dari dist)
  3. Naik max 3 level ke atas

Jadi exe di dist/ bisa baca data dari project root tanpa perlu dipindah.


CATATAN PENTING
---------------
- Hanya jalan di Windows (karena pakai Test-NetConnection / tnc)
- File .exe dan folder source_excel\ harus dalam satu project tree
  (max 3 level ke atas dari exe)
- Ukuran exe sekitar 50-80 MB (pandas + openpyxl di-bundle)
- Antivirus kadang false-positive — whitelist aja kalau perlu
- Pakai Python Microsoft Store? build.bat udah handle,
  tetep pakai "python -m PyInstaller" bukan "pyinstaller"
