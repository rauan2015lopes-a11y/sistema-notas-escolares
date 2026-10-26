"""Relatórios: desempenho por aluno (boletim e gráfico), alerta de risco e resumo por IA."""

from colorama import Fore
from tabulate import tabulate

from cadastros import selecionar_aluno
from calculos import (SEMESTRES, fmt, media_da_nota, medias_por_disciplina,
                      montar_boletim, notas_do_aluno)
from graficos import mostrar_medias_aluno
import docencia
import explicador
from risco import avaliar_aluno, avaliar_todos


def gerar_relatorio_aluno(banco):
    """Gera o boletim de um aluno, com médias por semestre e gráfico."""
    aluno = selecionar_aluno(banco)
    if not aluno:
        return

    dados = notas_do_aluno(banco, aluno["_id"])
    if not dados:
        print(Fore.YELLOW + "Esse aluno ainda não possui notas.")
        return

    print(f"\nRelatório de {aluno['nome']} - matrícula {aluno['matricula']} - turma {aluno['turma']}")
    semestres, geral, qtd = montar_boletim(dados)
    for numero, disciplinas, media in semestres:
        print(f"\n{numero}º semestre - média: {fmt(media)}")
        if not disciplinas:
            print("  (sem notas lançadas)")
            continue
        linhas = [[d["disciplina"], docencia.texto_professor(d), fmt(d.get("avg")), fmt(d.get("avi")),
                   fmt(d.get("avc")), fmt(media_da_nota(d))] for d in disciplinas]
        print(tabulate(linhas, headers=["Disciplina", "Professor", "AVG", "AVI", "AVC", "Média"],
                       tablefmt="fancy_grid", disable_numparse=True))
    print(f"\nMédia geral ({qtd} de {SEMESTRES} semestres com média): {fmt(geral)}")

    medias = medias_por_disciplina(dados)
    if medias:
        print("\nMédias por disciplina:")
        print(tabulate(list(medias.items()), headers=["Disciplina", "Média"],
                       floatfmt=".2f", tablefmt="fancy_grid"))
        mostrar_medias_aluno(medias, aluno["nome"])


def gerar_alerta_risco(banco):
    """Lista os alunos por nível de risco acadêmico, com os motivos."""
    resultado = avaliar_todos(banco)
    if not resultado:
        print(Fore.YELLOW + "Nenhum aluno cadastrado.")
        return
    cores = {"alto": Fore.RED, "médio": Fore.YELLOW, "baixo": Fore.GREEN}
    for r in resultado:
        cor = cores.get(r["nivel"], "")
        print(cor + f"[{r['nivel'].upper()} - {r['pontos']} pts] "
              f"{r['nome']} ({r['turma']}) - média {fmt(r['media'])}")
        for motivo in r["motivos"]:
            print(f"    - {motivo}")


def explicar_aluno_com_ia(banco):
    """Resumo em linguagem natural (IA) do risco de um aluno. Envia só dados anônimos."""
    if not explicador.disponivel():
        print(Fore.YELLOW + explicador.ORIENTACAO)
        return
    aluno = selecionar_aluno(banco)
    if not aluno:
        return
    dados = notas_do_aluno(banco, aluno["_id"])
    avaliacao = avaliar_aluno(dados)
    print(f"\n{aluno['nome']} - risco {avaliacao['nivel']} ({avaliacao['pontos']} pts)")
    print(f"Gerando resumo com {explicador.nome_provedor()} "
          "(apenas médias e motivos são enviados, sem o nome do aluno)...")
    try:
        print("\n" + explicador.explicar(avaliacao, dados))
    except explicador.ExplicadorErro as erro:
        print(Fore.RED + str(erro))
        return
    print(Fore.YELLOW + "\n(Texto gerado por IA; confira antes de usar.)")
