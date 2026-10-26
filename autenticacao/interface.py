"""Funções de entrada e saída no terminal (leitura validada e menu)."""

from colorama import Fore


def ler_inteiro(mensagem, minimo=None, maximo=None):
    """Lê um inteiro do terminal, repetindo até que o valor seja válido."""
    while True:
        try:
            valor = int(input(mensagem).strip())
            if minimo is not None and valor < minimo:
                raise ValueError
            if maximo is not None and valor > maximo:
                raise ValueError
            return valor
        except ValueError:
            limite = ""
            if minimo is not None and maximo is not None:
                limite = f" entre {minimo} e {maximo}"
            print(Fore.RED + f"Digite um número inteiro válido{limite}.")


def ler_nota():
    """Lê uma nota (0 a 10) do terminal, aceitando vírgula ou ponto decimal."""
    while True:
        try:
            nota = float(input("Nota (0 a 10): ").strip().replace(",", "."))
            if 0 <= nota <= 10:
                return round(nota, 2)
        except ValueError:
            pass
        print(Fore.RED + "A nota deve ser um número entre 0 e 10.")


def menu(banco):
    
    from cadastros import cadastrar_aluno, cadastrar_disciplina
    from consultas import listar_alunos
    from notas import lancar_nota
    from relatorios import gerar_ranking_turmas, gerar_relatorio_aluno

    while True:
        print(Fore.CYAN + "\n=== SISTEMA DE NOTAS ===")
        print("1 - Cadastrar aluno")
        print("2 - Cadastrar disciplina")
        print("3 - Lançar ou editar nota")
        print("4 - Listar alunos")
        print("5 - Relatório de aluno")
        print("6 - Ranking de turmas")
        print("0 - Sair")
        opcao = input("Escolha uma opção: ").strip()

        if opcao == "1":
            cadastrar_aluno(banco)
        elif opcao == "2":
            cadastrar_disciplina(banco)
        elif opcao == "3":
            lancar_nota(banco)
        elif opcao == "4":
            listar_alunos(banco)
        elif opcao == "5":
            gerar_relatorio_aluno(banco)
        elif opcao == "6":
            gerar_ranking_turmas(banco)
        elif opcao == "0":
            print("Até mais!")
            break
        else:
            print(Fore.RED + "Opção inválida.")
