"""Lançamento e atualização de notas dos alunos."""

from datetime import datetime

from colorama import Fore

from cadastros import selecionar_aluno, selecionar_disciplina
from interface import ler_inteiro, ler_nota


def lancar_nota(banco):
    """Lança ou atualiza (upsert) a nota de um aluno em uma disciplina/bimestre."""
    aluno = selecionar_aluno(banco)
    disciplina = selecionar_disciplina(banco)
    if not aluno or not disciplina:
        return

    bimestre = ler_inteiro("Bimestre (1 a 4): ", 1, 4)
    nota = ler_nota()
    filtro = {
        "aluno_id": aluno["_id"],
        "disciplina_id": disciplina["_id"],
        "bimestre": bimestre,
    }
    documento = {**filtro, "nota": nota, "data_lancamento": datetime.now()}
    resultado = banco.notas.replace_one(filtro, documento, upsert=True)
    acao = "atualizada" if resultado.matched_count else "lançada"
    print(Fore.GREEN + f"Nota {acao} com sucesso.")
