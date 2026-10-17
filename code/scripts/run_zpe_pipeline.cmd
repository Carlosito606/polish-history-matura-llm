@echo off
set ZPE_PY=%USERPROFILE%/zpevenv/Scripts/python.exe
"C:\Program Files\Git\bin\bash.exe" -c "$HOME/wmt-matura/scripts/run_zpe_pipeline.sh > $HOME/wmt-matura/logs/zpe_fetch.log 2>&1"
