"""Vínculo entre professores e disciplinas.

Regra: cada disciplina tem no máximo UM professor e cada professor leciona no máximo UMA
disciplina (quem dá Educação Física não dá outra matéria).

O professor é um usuário com perfil "professor" (criado na aba Usuários). O vínculo fica no
campo `professor` (o nome de usuário) do documento da disciplina. Disciplina sem professor
simplesmente não tem o campo: nunca guardamos null. O banco reforça a regra com um índice
único parcial (ver banco.criar_indices); as funções daqui dão mensagens claras antes disso.
"""

import autenticacao


class ProfessorOcupadoError(Exception):
    """O professor escolhido já leciona outra disciplina."""


def nome_exibicao(usuario):
    """'rafael' -> 'Rafael'; 'ana.souza' -> 'Ana Souza'."""
    return usuario.replace(".", " ").replace("_", " ").title()


def rotulo_professor(usuario):
    """'rafael' -> 'Prof. Rafael'."""
    return f"Prof. {nome_exibicao(usuario)}"


def rotulo_disciplina(disciplina):
    """'EDF - Educação Física (Prof. Rafael)': mostra a disciplina junto do professor."""
    texto = f"{disciplina['codigo']} - {disciplina['nome']}"
    if disciplina.get("professor"):
        texto += f" ({rotulo_professor(disciplina['professor'])})"
    return texto


def texto_professor(disciplina):
    """Professor da disciplina para tabelas ('-' se não houver)."""
    return rotulo_professor(disciplina["professor"]) if disciplina.get("professor") else "-"


def disciplina_do_professor(banco, usuario):
    """Disciplina que o professor leciona (ou None)."""
    return banco.disciplinas.find_one({"professor": usuario})


def professores_livres(banco, disciplina_id=None):
    """Usuários professores que ainda não lecionam nada, mais o da própria `disciplina_id`."""
    ocupados = {d["professor"] for d in banco.disciplinas.find({"professor": {"$exists": True}})
                if d["_id"] != disciplina_id}
    return [u["usuario"] for u in autenticacao.listar_usuarios(banco)
            if autenticacao.perfil_do(u) == autenticacao.PERFIL_PROFESSOR
            and u["usuario"] not in ocupados]


def validar_professor(banco, professor, disciplina_id=None):
    """Confere se `professor` pode assumir a disciplina. Vazio/None = sem professor (sempre ok).

    Lança ValueError se o usuário não existe ou não tem perfil professor, e
    ProfessorOcupadoError se ele já leciona outra disciplina (diferente de `disciplina_id`)."""
    if not professor:
        return
    usuario = banco.usuarios.find_one({"usuario": professor})
    if not usuario or autenticacao.perfil_do(usuario) != autenticacao.PERFIL_PROFESSOR:
        raise ValueError("Escolha um usuário com perfil professor.")
    filtro = {"professor": professor}
    if disciplina_id is not None:
        filtro["_id"] = {"$ne": disciplina_id}
    outra = banco.disciplinas.find_one(filtro)
    if outra:
        raise ProfessorOcupadoError(
            f"{rotulo_professor(professor)} já leciona {outra['nome']}. "
            "Cada professor pode ter somente uma disciplina.")


def operacao_de_atualizacao(campos, professor):
    """Operação do update_one que grava `campos` e define ou remove o professor."""
    if professor:
        return {"$set": {**campos, "professor": professor}}
    return {"$set": dict(campos), "$unset": {"professor": ""}}


def duplicata_de_professor(erro):
    """True se um DuplicateKeyError veio do índice do professor (e não do código da disciplina)."""
    return "professor_1" in str(erro)
