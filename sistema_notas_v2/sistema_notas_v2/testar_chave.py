"""Testa a chave do Gemini direto no Google, sem abrir o sistema. Execute: python testar_chave.py

A chave é pedida com a digitação oculta (ou lida de GEMINI_API_KEY) e nunca é exibida.
"""

import getpass
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from explicador import GEMINI_URL_PADRAO, modelos_gemini

BASE = os.getenv("GEMINI_BASE_URL", GEMINI_URL_PADRAO).rstrip("/")


def chamar(metodo, caminho, chave, corpo=None):
    dados = json.dumps(corpo).encode("utf-8") if corpo else None
    requisicao = urllib.request.Request(
        f"{BASE}/{caminho}", data=dados, method=metodo,
        headers={"x-goog-api-key": chave, "content-type": "application/json"})
    try:
        with urllib.request.urlopen(requisicao, timeout=60) as resposta:
            return resposta.status, json.load(resposta)
    except urllib.error.HTTPError as erro:
        try:
            detalhe = json.load(erro).get("error", {}).get("message", "")
        except ValueError:
            detalhe = ""
        return erro.code, detalhe
    except (urllib.error.URLError, OSError) as erro:
        return 0, f"falha de conexão: {erro}"


def main():
    arquivo = Path(__file__).with_name("chave_gemini.txt")
    chave = os.getenv("GEMINI_API_KEY")
    if not chave and arquivo.is_file():
        chave = arquivo.read_text(encoding="utf-8-sig")
        print("Chave lida de chave_gemini.txt.")
    chave = (chave or getpass.getpass(
        "Cole a chave do Gemini (nao aparece na tela) e aperte Enter: ")).strip().strip("\"'")
    print(f"Tamanho da chave: {len(chave)} caracteres | começa com: {chave[:3]!r}")
    if not chave:
        sys.exit("Nenhuma chave informada.")

    status, resposta = chamar("GET", "models", chave)
    if status == 200:
        print(f"[1/2] Chave ACEITA pelo Google ({len(resposta.get('models', []))} modelos listados).")
    else:
        print(f"[1/2] Chave REJEITADA (HTTP {status}): {resposta}")
        sys.exit(1)

    for modelo in modelos_gemini():
        status, resposta = chamar("POST", f"models/{modelo}:generateContent", chave, {
            "contents": [{"role": "user", "parts": [{"text": "Responda apenas: ok"}]}],
            "generationConfig": {"maxOutputTokens": 200}})
        if status == 200:
            partes = resposta["candidates"][0].get("content", {}).get("parts", [])
            texto = " ".join(p.get("text", "") for p in partes).strip()
            print(f"[2/2] Modelo {modelo} respondeu: {texto!r}")
            return
        print(f"[2/2] Modelo {modelo} falhou (HTTP {status}): {resposta}")
    print("      Todos os modelos falharam. Se for sobrecarga (503), tente de novo em alguns minutos.")
    sys.exit(1)


if __name__ == "__main__":
    main()
