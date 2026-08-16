@echo off
REM Nuitka build script for Twinclers Guard (CI/CD Friendly)
cd %~dp0\..

python -m nuitka --assume-yes-for-downloads --standalone --windows-disable-console --noinclude-unittest-mode=nofollow --noinclude-pydoc-mode=nofollow --noinclude-default-mode=nofollow --include-data-dir=locales=locales --include-data-dir=libs=libs --windows-icon-from-ico=app.ico --output-dir=dist --output-filename=TwinclersGuard.exe --product-name="Twinclers Guard" --product-version=1.0 main.py
