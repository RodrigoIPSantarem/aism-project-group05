"""Abrir o Sistema Multiagente de Investimentos com duplo clique (sem terminal).

Na primeira vez: instala o que faltar (yfinance) e cria o ficheiro de configuração (.env).
O resto (modelo de linguagem, identificação para a SEC, chaves opcionais) faz-se no botão Definições da janela.
"""
import importlib.util, os, subprocess, sys, threading, traceback
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
os.chdir(RAIZ); sys.path.insert(0, str(RAIZ))
import tkinter as tk
from tkinter import messagebox

def _aviso(titulo, texto, erro=False):
    r = tk.Tk(); r.withdraw()
    (messagebox.showerror if erro else messagebox.showwarning)(titulo, texto); r.destroy()

def _em_falta():
    return [m for m in ("yfinance",) if importlib.util.find_spec(m) is None]

def _preparar(falta):
    """Instala as dependências em falta, com uma pequena janela de progresso."""
    j = tk.Tk(); j.title("Sistema Multiagente de Investimentos"); j.geometry("480x150"); j.resizable(False, False)
    tk.Label(j, text="A preparar o programa (só da primeira vez)…", font=("Segoe UI", 11, "bold")).pack(pady=(24, 6))
    tk.Label(j, text="A instalar: " + ", ".join(falta) + ". Pode demorar um minuto.", font=("Segoe UI", 9)).pack()
    res = {}
    def tarefa():
        sem_janela = 0x08000000 if sys.platform == "win32" else 0          # CREATE_NO_WINDOW
        try:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(RAIZ / "requirements.txt")],
                               capture_output=True, text=True, creationflags=sem_janela)
            res["erro"] = None if r.returncode == 0 else (r.stderr or r.stdout)[-700:]
        except Exception as e: res["erro"] = str(e)
        j.after(0, j.destroy)
    threading.Thread(target=tarefa, daemon=True).start()
    j.mainloop()
    if res.get("erro"):
        _aviso("Instalação incompleta", "Não foi possível instalar o yfinance (fonte de reserva de dados).\n"
               "O programa abre na mesma; algumas empresas terão menos dados.\n\n" + res["erro"])

if __name__ == "__main__":
    if sys.version_info < (3, 10):
        _aviso("Python antigo", "Este programa precisa do Python 3.10 ou mais recente.\nInstala-o em python.org e volta a abrir.", True)
        sys.exit(1)
    falta = _em_falta()
    if falta: _preparar(falta)
    try:
        from nucleo.configuracao import garantir_env
        from nucleo.util import _carregar_env
        garantir_env(); _carregar_env()
        from interface.app import App
        App().mainloop()
    except Exception:
        erro = traceback.format_exc()
        try:
            (RAIZ / "saidas" / "logs").mkdir(parents=True, exist_ok=True)
            (RAIZ / "saidas" / "logs" / "erro_arranque.log").write_text(erro, encoding="utf-8")
        except OSError: pass
        _aviso("Erro ao abrir", "O programa não conseguiu abrir.\nO erro ficou em saidas/logs/erro_arranque.log.\n\n" + erro[-900:], True)
