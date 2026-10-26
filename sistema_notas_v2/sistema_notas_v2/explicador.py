"""Resumo em linguagem natural do alerta de risco, escrito por IA generativa.

Provedores suportados (escolhidos pelas variáveis de ambiente):
  - Google Gemini: GEMINI_API_KEY (ou GOOGLE_API_KEY). Tem plano gratuito, mas no plano
    gratuito o Google pode usar o conteúdo enviado para melhorar os produtos dele.
  - Anthropic Claude: ANTHROPIC_API_KEY (pago) e `pip install anthropic`.
Se as duas chaves existirem, vale o Gemini; EXPLICADOR_PROVEDOR=claude|gemini força um.

O modelo recebe só dados SEM identificação (médias, disciplinas e os motivos do alerta
calculados por risco.py). Nome e matrícula do aluno nunca são enviados.

Opcionais: GEMINI_MODELO (padrão gemini-3.8-flash), CLAUDE_MODELO (padrão claude-opus-5-5).
"""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from calculos import media_da_nota, montar_boletim

GEMINI_MODELO_PADRAO = "gemini-3.8-flash"
# Se o modelo padrão estiver sobrecarregado (503) ou indisponível, tenta estes, na ordem.
GEMINI_MODELOS_RESERVA = ("gemini-3.5-flash-lite", "gemini-flash-latest")
CODIGOS_DE_TROCA = (404, 429, 500, 502, 503, 504)
GEMINI_URL_PADRAO = "https://generativelanguage.googleapis.com/v1beta"
CLAUDE_MODELO_PADRAO = "claude-opus-5-5"
TEMPO_LIMITE = 90  # segundos

ORIENTACAO = (
    "Para usar o resumo por IA, defina a variável de ambiente GEMINI_API_KEY "
    "(chave gratuita em aistudio.google.com/apikey) ou ANTHROPIC_API_KEY (pago, e "
    "'pip install anthropic').\n\nApenas médias e motivos do alerta são enviados; "
    "o nome do aluno não sai do seu computador.")

INSTRUCOES = """Você é um assistente pedagógico que ajuda coordenadores e professores de um curso \
de 2 anos (4 semestres) a interpretar um alerta precoce de risco acadêmico.

Você receberá um JSON anônimo com as médias de um aluno e os motivos do alerta, calculados por \
regras fixas do sistema (notas de 0 a 10; a média de cada disciplina é a soma das duas maiores \
provas dividida por 2; abaixo de 6 é considerado fraco).

Escreva em português do Brasil, em um parágrafo de 3 a 5 frases e, depois, 2 ou 3 sugestões \
práticas e curtas de acompanhamento em lista. Regras:
- Use apenas os números do JSON; não invente notas, faltas ou fatos sobre o aluno.
- Não faça diagnóstico psicológico nem atribua causas pessoais; fale só do desempenho nas notas.
- Deixe claro, em uma frase, que o alerta é um apoio à decisão e não um veredito.
- Tom respeitoso e construtivo; se o risco for baixo, destaque o que está indo bem.
- Não use o nome do aluno (não foi informado); refira-se a "o aluno" ou "a turma"."""


class ExplicadorErro(Exception):
    """Falha ao gerar o resumo (sem chave, erro da API, bloqueio, resposta vazia).

    `codigo` guarda o status HTTP quando a falha veio da API (senão, None)."""

    codigo = None


ARQUIVO_CHAVE = Path(__file__).with_name("chave_gemini.txt")  # opcional; fica fora do zip distribuído


def _chave_gemini():
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def carregar_chave_salva():
    """Se não há chave no ambiente, lê a salva em chave_gemini.txt. Devolve True se carregou."""
    if provedor_ativo() or not ARQUIVO_CHAVE.is_file():
        return False
    chave = ARQUIVO_CHAVE.read_text(encoding="utf-8-sig").strip().strip("\"'")
    if chave:
        os.environ["GEMINI_API_KEY"] = chave
    return bool(chave)


def salvar_chave(chave):
    """Guarda a chave em chave_gemini.txt (texto simples, só neste computador)."""
    ARQUIVO_CHAVE.write_text(chave.strip().strip("\"'"), encoding="utf-8")


def esquecer_chave_salva():
    """Apaga o chave_gemini.txt, se existir. Devolve True se havia arquivo."""
    if ARQUIVO_CHAVE.is_file():
        ARQUIVO_CHAVE.unlink()
        return True
    return False


def provedor_ativo():
    """'gemini', 'claude' ou None, conforme as variáveis de ambiente."""
    escolhido = os.getenv("EXPLICADOR_PROVEDOR", "").strip().lower()
    if escolhido == "claude":
        return "claude" if os.getenv("ANTHROPIC_API_KEY") else None
    if escolhido == "gemini":
        return "gemini" if _chave_gemini() else None
    if _chave_gemini():
        return "gemini"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "claude"
    return None


def disponivel():
    """True se há alguma chave configurada."""
    return provedor_ativo() is not None


def nome_provedor():
    return {"gemini": "Gemini (Google)", "claude": "Claude (Anthropic)"}.get(provedor_ativo(), "IA")


def montar_dados(avaliacao, dados):
    """Monta o JSON anônimo enviado à IA a partir da avaliação e das notas do aluno."""
    semestres, geral, _ = montar_boletim(dados)
    return {
        "media_geral": geral,
        "nivel_de_risco": avaliacao["nivel"],
        "pontuacao_de_risco_0_a_100": avaliacao["pontos"],
        "motivos_do_alerta": avaliacao["motivos"],
        "semestres": [
            {"semestre": numero, "media": media,
             "disciplinas": [{"disciplina": d["disciplina"], "media": media_da_nota(d)}
                             for d in disciplinas]}
            for numero, disciplinas, media in semestres if disciplinas
        ],
    }


# ---------- Gemini (HTTP direto, sem dependência extra) ----------
def modelos_gemini():
    """Modelos a tentar, em ordem. Com GEMINI_MODELO definido, só ele (sem reserva)."""
    escolhido = os.getenv("GEMINI_MODELO")
    return (escolhido,) if escolhido else (GEMINI_MODELO_PADRAO, *GEMINI_MODELOS_RESERVA)


def _chamar_gemini(conteudo):
    """Tenta cada modelo da lista; passa ao próximo se o atual estiver sobrecarregado/indisponível."""
    ultimo_erro = None
    for modelo in modelos_gemini():
        try:
            return _chamar_gemini_modelo(modelo, conteudo)
        except ExplicadorErro as erro:
            if erro.codigo not in CODIGOS_DE_TROCA:
                raise
            ultimo_erro = erro
    raise ultimo_erro


def _chamar_gemini_modelo(modelo, conteudo):
    base = os.getenv("GEMINI_BASE_URL", GEMINI_URL_PADRAO).rstrip("/")
    corpo = {
        "systemInstruction": {"parts": [{"text": INSTRUCOES}]},
        "contents": [{"role": "user", "parts": [{"text": conteudo}]}],
        # o limite inclui os tokens de "raciocínio" dos modelos 3.x, por isso é folgado
        "generationConfig": {"maxOutputTokens": 4000},
    }
    requisicao = urllib.request.Request(
        f"{base}/models/{modelo}:generateContent",
        data=json.dumps(corpo).encode("utf-8"),
        headers={"content-type": "application/json", "x-goog-api-key": _chave_gemini()},
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=TEMPO_LIMITE) as resposta:
            retorno = json.load(resposta)
    except urllib.error.HTTPError as erro:
        try:
            detalhe = json.load(erro).get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            detalhe = ""
        finally:
            erro.close()
        mensagem = f"Falha ao consultar o Gemini ({modelo}, HTTP {erro.code}): {detalhe}".strip()
        if erro.code in (400, 401, 403) and "key" in detalhe.lower():
            chave = _chave_gemini() or ""  # só o tamanho e o início, nunca a chave inteira
            mensagem += (f"\nChave em uso: {len(chave)} caracteres, começa com {chave[:3]!r}. "
                         "Se não for a sua chave, feche o programa, limpe a variável "
                         "(Remove-Item Env:GEMINI_API_KEY) e abra de novo colando a chave certa.")
        falha = ExplicadorErro(mensagem)
        falha.codigo = erro.code
        raise falha from erro
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        raise ExplicadorErro(f"Falha de conexão com o Gemini: {erro}") from erro
    except ValueError as erro:
        raise ExplicadorErro("Resposta inválida do Gemini.") from erro

    bloqueio = (retorno.get("promptFeedback") or {}).get("blockReason")
    if bloqueio:
        raise ExplicadorErro(f"O Gemini bloqueou o pedido ({bloqueio}).")
    candidatos = retorno.get("candidates") or []
    partes = ((candidatos[0].get("content") or {}).get("parts") or []) if candidatos else []
    texto = "\n".join(p["text"] for p in partes if p.get("text") and not p.get("thought")).strip()
    if not texto:
        motivo = candidatos[0].get("finishReason", "desconhecido") if candidatos else "sem resposta"
        raise ExplicadorErro(f"O Gemini não devolveu texto (motivo: {motivo}).")
    return texto


# ---------- Claude ----------
def _chamar_claude(conteudo, cliente=None):
    if cliente is None:
        try:
            import anthropic
        except ImportError as erro:
            raise ExplicadorErro("Instale o pacote: pip install anthropic") from erro
        cliente = anthropic.Anthropic(timeout=float(TEMPO_LIMITE))
    try:
        resposta = cliente.messages.create(
            model=os.getenv("CLAUDE_MODELO", CLAUDE_MODELO_PADRAO),
            max_tokens=4000,
            system=INSTRUCOES,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": conteudo}],
        )
    except Exception as erro:  # erros tipados do SDK: auth, limite, rede, 5xx...
        raise ExplicadorErro(f"Falha ao consultar o Claude ({type(erro).__name__}): {erro}") from erro
    if resposta.stop_reason == "refusal":
        raise ExplicadorErro("O Claude recusou gerar este resumo.")
    texto = "\n".join(b.text for b in resposta.content if b.type == "text").strip()
    if not texto:
        raise ExplicadorErro("O Claude não devolveu texto (resposta cortada ou vazia).")
    return texto


def explicar(avaliacao, dados, cliente=None):
    """Devolve o resumo em texto. `cliente` (testes) injeta um cliente do Claude."""
    if avaliacao["nivel"] == "sem dados":
        raise ExplicadorErro("Esse aluno ainda não tem médias para o resumo.")
    conteudo = json.dumps(montar_dados(avaliacao, dados), ensure_ascii=False, indent=2)
    if cliente is not None:
        return _chamar_claude(conteudo, cliente)
    provedor = provedor_ativo()
    if provedor == "gemini":
        return _chamar_gemini(conteudo)
    if provedor == "claude":
        return _chamar_claude(conteudo)
    raise ExplicadorErro(ORIENTACAO.split("\n\n")[0])
