@echo off
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw -3 "Abrir.pyw" & exit /b 0)
where pythonw >nul 2>nul && (start "" pythonw "Abrir.pyw" & exit /b 0)
echo Nao encontrei o Python neste computador.
echo Instala o Python 3.11 ou mais recente em https://www.python.org
echo (no instalador, marca a opcao "Add python.exe to PATH") e volta a fazer duplo clique neste ficheiro.
pause
