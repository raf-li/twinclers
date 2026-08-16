@echo off
REM Nuitka build script for Twinclers Guard (CI/CD Friendly)
cd %~dp0\..

python -m nuitka --standalone --windows-disable-console --enable-plugin=wx --enable-plugin=anti-bloat --noinclude-module=tkinter --noinclude-module=unittest --noinclude-module=pydoc --include-data-dir=locales=locales --include-data-dir=libs=libs --windows-icon-from-ico=app.ico --output-dir=dist --output-filename=TwinclersGuard.exe --product-name="Twinclers Guard" --product-version=1.0 main.py
