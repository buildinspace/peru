@echo off
setlocal

set peru_root=%~dp0..
set PYTHONPATH=%peru_root%;%peru_root%\third-party

python "%peru_root%\bin\peru" %*
