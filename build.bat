@echo off
REM Build firewall-tnc.exe pakai PyInstaller
REM Output: Dist\firewall-tnc.exe (build artifact)
REM Auto-copy: firewall-tnc.exe di project root (siap dijalankan, sebelah source_excel\ dan result\)
REM Cara pakai: double-click file ini, atau jalankan dari cmd

echo === Installing dependencies ===
python -m pip install --upgrade pip
python -m pip install pyinstaller pandas openpyxl tabulate

echo.
echo === Building firewall-tnc.exe (output ke folder Dist\) ===
REM Pakai "python -m PyInstaller" (bukan "pyinstaller") supaya works
REM di Python Microsoft Store yang gak nambahin Scripts ke PATH.
python -m PyInstaller --noconfirm --clean --distpath Dist main.spec

echo.
echo === Copy exe ke project root (sebelah source_excel dan result) ===
if exist "Dist\firewall-tnc.exe" (
    copy /Y "Dist\firewall-tnc.exe" "firewall-tnc.exe" >nul
    echo [OK] Exe siap dijalankan:  firewall-tnc.exe
    echo [OK] Build artifact tetap di:  Dist\firewall-tnc.exe
) else (
    echo [WARN] Dist\firewall-tnc.exe gak ketemu, build mungkin gagal
)

echo.
echo === Done ===
echo.
echo Cara jalanin:
echo     cd D:\Automation_Script\Firewall\New-Firewall
echo     firewall-tnc.exe
echo.
pause
