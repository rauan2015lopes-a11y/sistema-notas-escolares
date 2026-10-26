"""Relatórios agregados: desempenho por aluno e ranking de turmas."""

import pandas as pd
from colorama import Fore
from tabulate import tabulate

from cadastros import selecionar_aluno
from graficos import plotar_medias_aluno


def gerar_relatorio_aluno(banco):
    """Gera o relatório de notas de um aluno, com médias e gráfico."""
    aluno = selecionar_aluno(banco)
    if not aluno:
        return

    pipeline = [
        {"$match": {"aluno_id": aluno["_id"]}},
        {
            "$lookup": {
                "from": "disciplinas",
                "localField": "disciplina_id",
                "foreignField": "_id",
                "as": "disciplina",
            }
        },
        {"$unwind": "$disciplina"},
        {"$project": {"_id": 0, "disciplina": "$disciplina.nome", "bimestre": 1, "nota": 1}},
        {"$sort": {"disciplina": 1, "bimestre": 1}},
    ]
    dados = list(banco.notas.aggregate(pipeline))
    if not dados:
        print(Fore.YELLOW + "Esse aluno ainda não possui notas.")
        return

    tabela = [[d["disciplina"], d["bimestre"], d["nota"]] for d in dados]
    print(f"\nRelatório de {aluno['nome']} - turma {aluno['turma']}")
    print(tabulate(tabela, headers=["Disciplina", "Bimestre", "Nota"], tablefmt="fancy_grid"))

    dataframe = pd.DataFrame(dados)
    medias = dataframe.groupby("disciplina", as_index=False)["nota"].mean()
    print("\nMédias por disciplina:")
    print(tabulate(medias.round(2), headers="keys", showindex=False, tablefmt="fancy_grid"))

    plotar_medias_aluno(medias, aluno["nome"])


def gerar_ranking_turmas(banco):
    """Gera o ranking de turmas pela média geral de notas."""
    pipeline = [
        {
            "$lookup": {
                "from": "alunos",
                "localField": "aluno_id",
                "foreignField": "_id",
                "as": "aluno",
            }
        },
        {"$unwind": "$aluno"},
        {"$group": {"_id": "$aluno.turma", "media": {"$avg": "$nota"}, "quantidade": {"$sum": 1}}},
        {"$sort": {"media": -1}},
    ]
    dados = list(banco.notas.aggregate(pipeline))
    if not dados:
        print(Fore.YELLOW + "Ainda não há notas para gerar o ranking.")
        return

    tabela = [[d["_id"], round(d["media"], 2), d["quantidade"]] for d in dados]
    print(tabulate(tabela, headers=["Turma", "Média geral", "Notas"], tablefmt="fancy_grid"))
