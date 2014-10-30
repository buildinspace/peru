@echo off
setlocal

set peru_root=%~dp0..
set PYTHONPATH=%peru_root%;%peru_root%\third-party
set PYTHONASYNCIODEBUG=1

python -m unittest discover --start "%peru_root%\tests" --catch %*
