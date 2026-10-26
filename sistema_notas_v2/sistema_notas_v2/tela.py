"""Interface gráfica (Tkinter) do sistema de notas escolares.

Execute com: python tela.py
(a variável de ambiente MONGODB_URI precisa estar definida).
"""

import os
import threading
import time
import tkinter as tk
from datetime import datetime, timezone
from tkinter import messagebox, ttk

from pymongo.errors import DuplicateKeyError, PyMongoError

import autenticacao
import docencia
import explicador
from banco import conectar_banco
from calculos import (PROVAS, SEMESTRES, calcular_media, fmt, ler_nota_opcional,
                      media_da_nota, medias_por_disciplina, montar_boletim,
                      notas_do_aluno)
from config import NOME_BANCO
from risco import avaliar_aluno, avaliar_todos

TODAS_TURMAS = "Todas as turmas"
SEM_PROFESSOR = "(sem professor)"
COLUNAS_NOTAS = ("Disciplina", "Semestre", "AVG", "AVI", "AVC", "Média")
LARGURAS_NOTAS = (320, 90, 90, 90, 90, 100)


def linha_nota(d):
    return (d["disciplina"], f"{d['semestre']}º", fmt(d.get("avg")), fmt(d.get("avi")),
            fmt(d.get("avc")), fmt(media_da_nota(d)))


def criar_tabela(pai, colunas, larguras=None):
    """Cria um Treeview com barra de rolagem e devolve o Treeview."""
    quadro = ttk.Frame(pai)
    quadro.pack(fill="both", expand=True, pady=6)
    tabela = ttk.Treeview(quadro, columns=colunas, show="headings", height=8)
    for i, col in enumerate(colunas):
        alinhamento = "w" if i == 0 else "center"
        tabela.heading(col, text=col, anchor=alinhamento)
        tabela.column(col, width=(larguras[i] if larguras else 120), anchor=alinhamento)
    barra = ttk.Scrollbar(quadro, orient="vertical", command=tabela.yview)
    tabela.configure(yscrollcommand=barra.set)
    tabela.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y")
    return tabela


def preencher(tabela, linhas, iids=None):
    """Troca o conteúdo da tabela. `iids` (opcional) dá um identificador a cada linha."""
    tabela.delete(*tabela.get_children())
    for i, linha in enumerate(linhas):
        tabela.insert("", "end", iid=iids[i] if iids else None, values=linha)


def limpar_campos(*entradas):
    for entrada in entradas:
        entrada.delete(0, "end")


class Login(tk.Tk):
    """Tela inicial: só deixa entrar no sistema quem tem usuário e senha cadastrados."""

    def __init__(self, banco):
        super().__init__()
        self.banco = banco
        self.usuario = None
        self.perfil = None
        self.primeiro_acesso = not autenticacao.existe_admin(banco)

        self.title("Sistema de Notas Escolares - Login")
        self.minsize(380, 0)
        self.resizable(False, False)
        ttk.Style(self).theme_use("clam")

        quadro = ttk.Frame(self, padding=28)
        quadro.pack(fill="both", expand=True)
        ttk.Label(quadro, text="Sistema de Notas Escolares",
                  font=("Segoe UI", 14, "bold")).pack(pady=(0, 4))
        subtitulo = ("Primeiro acesso: crie a conta da secretaria"
                     if self.primeiro_acesso else "Acesso restrito a usuários cadastrados")
        ttk.Label(quadro, text=subtitulo).pack(pady=(0, 16))

        ttk.Label(quadro, text="Usuário:").pack(anchor="w")
        self.e_usuario = ttk.Entry(quadro, width=34)
        self.e_usuario.pack(pady=(0, 8))
        ttk.Label(quadro, text="Senha:").pack(anchor="w")
        self.e_senha = ttk.Entry(quadro, width=34, show="*")
        self.e_senha.pack(pady=(0, 8))

        self.e_confirma = None
        self.e_codigo = None
        if self.primeiro_acesso:
            ttk.Label(quadro, text=f"Confirmar senha (mín. {autenticacao.SENHA_MINIMA}, letras e números):"
                      ).pack(anchor="w")
            self.e_confirma = ttk.Entry(quadro, width=34, show="*")
            self.e_confirma.pack(pady=(0, 8))
            if autenticacao.codigo_configuracao_exigido():
                ttk.Label(quadro, text="Código de configuração:").pack(anchor="w")
                self.e_codigo = ttk.Entry(quadro, width=34, show="*")
                self.e_codigo.pack(pady=(0, 8))

        texto = "Criar conta da secretaria" if self.primeiro_acesso else "Entrar"
        self.botao = ttk.Button(quadro, text=texto, command=self.confirmar)
        self.botao.pack(pady=10, fill="x")
        self.lbl_erro = ttk.Label(quadro, text="", foreground="#c0392b", wraplength=320)
        self.lbl_erro.pack()

        self.bind("<Return>", lambda e: self.confirmar())
        self.e_usuario.focus()

    def erro(self, texto):
        self.lbl_erro.config(text=texto)

    def confirmar(self):
        usuario = self.e_usuario.get().strip()
        senha = self.e_senha.get()
        if not usuario or not senha:
            return self.erro("Informe usuário e senha.")
        try:
            if self.primeiro_acesso:
                return self.criar_primeiro_admin(usuario, senha)
            documento = autenticacao.autenticar(self.banco, usuario, senha)
        except autenticacao.BloqueadoError as erro:
            minutos = -(-erro.segundos // 60)
            self.e_senha.delete(0, "end")
            return self.erro(f"Muitas tentativas inválidas. Tente de novo em {minutos} min.")
        except DuplicateKeyError:
            return self.erro("Esse usuário já existe.")
        except PyMongoError as erro:
            return messagebox.showerror("Erro no banco de dados", str(erro))

        if documento:
            self.usuario = documento["usuario"]
            self.perfil = autenticacao.perfil_do(documento)
            self.destroy()
            return
        self.e_senha.delete(0, "end")
        self.erro("Usuário ou senha incorretos.")

    def criar_primeiro_admin(self, usuario, senha):
        problema = autenticacao.validar_senha(senha)
        if problema:
            return self.erro(problema)
        if senha != self.e_confirma.get():
            return self.erro("As senhas não conferem.")
        if self.e_codigo and not autenticacao.codigo_configuracao_confere(self.e_codigo.get()):
            return self.erro("Código de configuração incorreto.")
        try:
            autenticacao.criar_primeiro_admin(self.banco, usuario, senha)
        except PermissionError as erro:
            return self.erro(str(erro))
        self.usuario = usuario.lower()
        self.perfil = autenticacao.PERFIL_ADMIN
        messagebox.showinfo("Sucesso", "Conta da secretaria criada. Você já está logado.")
        self.destroy()


class App(tk.Tk):
    def __init__(self, banco, usuario, perfil=autenticacao.PERFIL_ADMIN):
        super().__init__()
        self.banco = banco
        self.usuario = usuario
        self.perfil = perfil
        # Secretaria (administrador): único perfil que edita. Professor e consulta só visualizam.
        self.eh_admin = perfil == autenticacao.PERFIL_ADMIN
        self.pode_lancar = self.eh_admin
        self.frames_abas = {}
        self.quadros_edicao = []  # formulários e botões de edição: só a secretaria os vê
        self.professores_por_rotulo = {}
        self.sair_para_login = False
        self.mapa_alunos = {}
        self.mapa_disciplinas = {}
        self.alunos_por_iid = {}
        self.disciplinas_por_iid = {}
        self.combos_alunos = []
        self.combos_disciplinas = []

        self.title("Sistema de Notas Escolares")
        self.geometry("1020x780")
        ttk.Style(self).theme_use("clam")

        barra = ttk.Frame(self, padding=(10, 6))
        barra.pack(fill="x")
        self.lbl_cabecalho = ttk.Label(barra, text=self.texto_cabecalho())
        self.lbl_cabecalho.pack(side="left")
        ttk.Button(barra, text="Sair", command=self.sair).pack(side="right")

        self.abas = ttk.Notebook(self)
        self.abas.pack(fill="both", expand=True, padx=8, pady=8)
        self.montar_aba_alunos()
        self.montar_aba_disciplinas()
        self.montar_aba_notas()
        self.montar_aba_relatorio()
        self.montar_aba_risco()
        if self.eh_admin:
            self.montar_aba_usuarios()
        else:  # professor e consulta: nenhum formulário nem botão de edição aparece
            for quadro in self.quadros_edicao:
                quadro.pack_forget()
        if not self.pode_lancar:
            self.abas.hide(self.frames_abas["Lançar notas"])
        self.abas.bind("<<NotebookTabChanged>>", self.ao_trocar_aba)
        self.carregar_dados()
        if self.eh_admin:
            self.carregar_usuarios()

    def sair(self):
        """Encerra a sessão: volta para a tela de login."""
        self.sair_para_login = True
        self.destroy()

    def texto_cabecalho(self):
        """Ex.: 'Secretaria: ana' ou 'Professor: rafael | Disciplina: Educação Física | Somente visualização'."""
        texto = f"{autenticacao.rotulo_perfil(self.perfil)}: {self.usuario}"
        if self.perfil == autenticacao.PERFIL_PROFESSOR:
            try:
                disciplina = docencia.disciplina_do_professor(self.banco, self.usuario)
            except PyMongoError:
                disciplina = None
            texto += (f"  |  Disciplina: {disciplina['nome']}" if disciplina
                      else "  |  Sem disciplina vinculada")
        if not self.eh_admin:
            texto += "  |  Somente visualização"
        return texto

    def atualizar_cabecalho(self):
        self.lbl_cabecalho.config(text=self.texto_cabecalho())

    # ---------- utilidades ----------
    def aba(self, titulo):
        quadro = ttk.Frame(self.abas, padding=12)
        self.abas.add(quadro, text=titulo)
        self.frames_abas[titulo] = quadro
        return quadro

    def exigir(self, permitido, acao):
        """Barra a ação (com aviso) se o perfil não tem permissão. Vale mesmo que o botão seja contornado."""
        if not permitido:
            messagebox.showwarning("Sem permissão", f"O perfil {self.perfil} não pode {acao}.")
        return permitido

    def campo(self, pai, rotulo, linha, largura=30):
        ttk.Label(pai, text=rotulo).grid(row=linha, column=0, sticky="w", pady=3)
        entrada = ttk.Entry(pai, width=largura)
        entrada.grid(row=linha, column=1, sticky="w", padx=8, pady=3)
        return entrada

    def combo(self, pai, rotulo, linha, lista):
        ttk.Label(pai, text=rotulo).grid(row=linha, column=0, sticky="w", pady=3)
        cb = ttk.Combobox(pai, state="readonly", width=52)
        cb.grid(row=linha, column=1, sticky="w", padx=8, pady=3)
        lista.append(cb)
        return cb

    def botoes_crud(self, pai, linha, rotulo_cadastrar, cadastrar, salvar, excluir, limpar):
        quadro = ttk.Frame(pai)
        quadro.grid(row=linha, column=1, sticky="w", padx=8, pady=8)
        b_cadastrar = ttk.Button(quadro, text=rotulo_cadastrar, command=cadastrar)
        b_salvar = ttk.Button(quadro, text="Salvar alterações", command=salvar)
        b_excluir = ttk.Button(quadro, text="Excluir", command=excluir)
        b_cadastrar.pack(side="left")
        b_salvar.pack(side="left", padx=6)
        b_excluir.pack(side="left")
        ttk.Button(quadro, text="Limpar", command=limpar).pack(side="left", padx=6)

    def erro_banco(self, erro):
        messagebox.showerror("Erro no banco de dados", str(erro))

    def carregar_dados(self):
        """Recarrega alunos/disciplinas nas tabelas e nas caixas de seleção."""
        try:
            alunos = list(self.banco.alunos.find().sort("nome", 1))
            disciplinas = list(self.banco.disciplinas.find().sort("nome", 1))
        except PyMongoError as erro:
            return self.erro_banco(erro)
        self.mapa_alunos = {f"{a['matricula']} - {a['nome']}": a for a in alunos}
        self.mapa_disciplinas = {docencia.rotulo_disciplina(d): d for d in disciplinas}
        self.alunos_por_iid = {str(a["_id"]): a for a in alunos}
        self.disciplinas_por_iid = {str(d["_id"]): d for d in disciplinas}
        for combos, mapa in ((self.combos_alunos, self.mapa_alunos),
                             (self.combos_disciplinas, self.mapa_disciplinas)):
            for cb in combos:
                cb["values"] = list(mapa)
                if cb.get() not in mapa:  # item renomeado ou excluído
                    cb.set("")
        self.lista_alunos = alunos
        self.atualizar_filtros_turma()
        self.atualizar_tabela_alunos()
        preencher(self.tab_disc, [(d["nome"], d["codigo"], d["carga_horaria"], docencia.texto_professor(d))
                                  for d in disciplinas],
                  [str(d["_id"]) for d in disciplinas])
        if self.eh_admin:
            self.atualizar_combo_professor()

    def ao_trocar_aba(self, _evento=None):
        aba = self.abas.tab(self.abas.select(), "text")
        self.atualizar_cabecalho()
        if aba == "Alerta de risco":
            self.gerar_risco()
        elif aba == "Relatório do aluno" and self.cb_rel_aluno.get():
            self.gerar_relatorio(avisar=False)  # traz notas lançadas depois da última consulta
        elif aba == "Disciplinas" and self.eh_admin:
            self.atualizar_combo_professor()  # professores criados na aba Usuários

    @staticmethod
    def selecionado(tabela, por_iid):
        """Registro da linha selecionada na tabela (ou None)."""
        escolha = tabela.selection()
        return por_iid.get(escolha[0]) if escolha else None

    # ---------- alunos ----------
    def montar_aba_alunos(self):
        f = self.aba("Alunos")
        form = ttk.Frame(f)
        form.pack(fill="x")
        self.quadros_edicao.append(form)
        self.e_nome = self.campo(form, "Nome completo:", 0)
        self.e_matricula = self.campo(form, "Matrícula:", 1)
        self.e_turma = self.campo(form, "Turma:", 2)
        self.botoes_crud(form, 3, "Cadastrar aluno", self.cadastrar_aluno,
                         self.salvar_aluno, self.excluir_aluno, self.limpar_aluno)
        self.lista_alunos = []

        filtro = ttk.Frame(f)
        filtro.pack(fill="x", pady=(8, 0))
        ttk.Label(filtro, text="Turma:").pack(side="left")
        self.cb_filtro_turma = ttk.Combobox(filtro, state="readonly", width=22, values=[TODAS_TURMAS])
        self.cb_filtro_turma.set(TODAS_TURMAS)
        self.cb_filtro_turma.pack(side="left", padx=(4, 14))
        self.cb_filtro_turma.bind("<<ComboboxSelected>>", lambda e: self.atualizar_tabela_alunos())
        ttk.Label(filtro, text="Buscar (nome ou matrícula):").pack(side="left")
        self.e_busca_aluno = ttk.Entry(filtro, width=26)
        self.e_busca_aluno.pack(side="left", padx=(4, 8))
        self.e_busca_aluno.bind("<KeyRelease>", lambda e: self.atualizar_tabela_alunos())
        ttk.Button(filtro, text="Limpar filtros", command=self.limpar_filtros_alunos).pack(side="left")
        self.lbl_contagem_alunos = ttk.Label(filtro, text="", foreground="#555555")
        self.lbl_contagem_alunos.pack(side="right")

        dica = ("Alunos agrupados por turma. Selecione um aluno para editar ou excluir."
                if self.eh_admin else "Alunos agrupados por turma. Somente visualização.")
        ttk.Label(f, text=dica, foreground="#555555").pack(anchor="w", pady=(4, 0))
        quadro = ttk.Frame(f)
        quadro.pack(fill="both", expand=True, pady=6)
        self.tab_alunos = ttk.Treeview(quadro, columns=("matricula", "turma"), show="tree headings", height=8)
        self.tab_alunos.heading("#0", text="Turma / Aluno", anchor="w")
        self.tab_alunos.column("#0", width=380, anchor="w")
        for coluna, titulo in (("matricula", "Matrícula"), ("turma", "Turma")):
            self.tab_alunos.heading(coluna, text=titulo, anchor="center")
            self.tab_alunos.column(coluna, width=150, anchor="center")
        self.tab_alunos.tag_configure("turma", background="#e3eaf7", font=("Segoe UI", 9, "bold"))
        barra = ttk.Scrollbar(quadro, orient="vertical", command=self.tab_alunos.yview)
        self.tab_alunos.configure(yscrollcommand=barra.set)
        self.tab_alunos.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.tab_alunos.bind("<<TreeviewSelect>>", self.ao_selecionar_aluno)

    def atualizar_filtros_turma(self):
        """Atualiza a lista de turmas dos filtros (Alunos e Alerta de risco), mantendo a escolha."""
        turmas = sorted({a["turma"] for a in self.lista_alunos}, key=str.casefold)
        valores = [TODAS_TURMAS, *turmas]
        for cb in (self.cb_filtro_turma, self.cb_risco_turma):
            cb["values"] = valores
            if cb.get() not in valores:  # a turma escolhida deixou de existir
                cb.set(TODAS_TURMAS)

    def atualizar_tabela_alunos(self):
        """Mostra os alunos agrupados por turma, respeitando o filtro de turma e a busca."""
        turma = self.cb_filtro_turma.get()
        busca = self.e_busca_aluno.get().strip().casefold()
        grupos = {}
        for a in self.lista_alunos:
            if turma != TODAS_TURMAS and a["turma"] != turma:
                continue
            if busca and busca not in a["nome"].casefold() and busca not in a["matricula"].casefold():
                continue
            grupos.setdefault(a["turma"], []).append(a)

        self.tab_alunos.delete(*self.tab_alunos.get_children())
        total = 0
        for nome_turma in sorted(grupos, key=str.casefold):
            alunos = sorted(grupos[nome_turma], key=lambda a: a["nome"].casefold())
            plural = "aluno" if len(alunos) == 1 else "alunos"
            pai = self.tab_alunos.insert("", "end", iid=f"turma:{nome_turma}", open=True, tags=("turma",),
                                         text=f"{nome_turma}  ({len(alunos)} {plural})", values=("", ""))
            for a in alunos:
                self.tab_alunos.insert(pai, "end", iid=str(a["_id"]), text=a["nome"],
                                       values=(a["matricula"], a["turma"]))
            total += len(alunos)
        self.lbl_contagem_alunos.config(text=f"{total} de {len(self.lista_alunos)} aluno(s)")

    def limpar_filtros_alunos(self):
        self.cb_filtro_turma.set(TODAS_TURMAS)
        self.e_busca_aluno.delete(0, "end")
        self.atualizar_tabela_alunos()

    def campos_aluno(self):
        valores = tuple(e.get().strip() for e in (self.e_nome, self.e_matricula, self.e_turma))
        if not all(valores):
            messagebox.showwarning("Atenção", "Todos os campos são obrigatórios.")
            return None
        return valores

    def ao_selecionar_aluno(self, _evento=None):
        aluno = self.selecionado(self.tab_alunos, self.alunos_por_iid)
        if aluno:
            limpar_campos(self.e_nome, self.e_matricula, self.e_turma)
            self.e_nome.insert(0, aluno["nome"])
            self.e_matricula.insert(0, aluno["matricula"])
            self.e_turma.insert(0, aluno["turma"])

    def limpar_aluno(self):
        limpar_campos(self.e_nome, self.e_matricula, self.e_turma)
        self.tab_alunos.selection_set(())

    def cadastrar_aluno(self):
        if not self.exigir(self.eh_admin, "cadastrar alunos"):
            return
        valores = self.campos_aluno()
        if not valores:
            return
        nome, mat, turma = valores
        try:
            self.banco.alunos.insert_one({"nome": nome, "matricula": mat, "turma": turma,
                                          "data_cadastro": datetime.now(timezone.utc)})
        except DuplicateKeyError:
            return messagebox.showerror("Erro", "Essa matrícula já está cadastrada.")
        except PyMongoError as erro:
            return self.erro_banco(erro)
        self.limpar_aluno()
        self.carregar_dados()
        messagebox.showinfo("Sucesso", "Aluno cadastrado com sucesso.")

    def salvar_aluno(self):
        if not self.exigir(self.eh_admin, "alterar alunos"):
            return
        aluno = self.selecionado(self.tab_alunos, self.alunos_por_iid)
        if not aluno:
            return messagebox.showwarning("Atenção", "Selecione um aluno na tabela.")
        valores = self.campos_aluno()
        if not valores:
            return
        nome, mat, turma = valores
        try:
            self.banco.alunos.update_one(
                {"_id": aluno["_id"]}, {"$set": {"nome": nome, "matricula": mat, "turma": turma}})
        except DuplicateKeyError:
            return messagebox.showerror("Erro", "Essa matrícula já está cadastrada.")
        except PyMongoError as erro:
            return self.erro_banco(erro)
        self.limpar_aluno()
        self.carregar_dados()
        messagebox.showinfo("Sucesso", "Aluno atualizado.")

    def excluir_aluno(self):
        if not self.exigir(self.eh_admin, "excluir alunos"):
            return
        aluno = self.selecionado(self.tab_alunos, self.alunos_por_iid)
        if not aluno:
            return messagebox.showwarning("Atenção", "Selecione um aluno na tabela.")
        try:
            qtd = self.banco.notas.count_documents({"aluno_id": aluno["_id"]})
            if not messagebox.askyesno(
                    "Confirmar exclusão",
                    f"Excluir {aluno['nome']} e as {qtd} nota(s) dele? Isso não pode ser desfeito."):
                return
            self.banco.notas.delete_many({"aluno_id": aluno["_id"]})
            self.banco.alunos.delete_one({"_id": aluno["_id"]})
        except PyMongoError as erro:
            return self.erro_banco(erro)
        self.limpar_aluno()
        self.carregar_dados()

    # ---------- disciplinas ----------
    def montar_aba_disciplinas(self):
        f = self.aba("Disciplinas")
        form = ttk.Frame(f)
        form.pack(fill="x")
        self.quadros_edicao.append(form)
        self.e_dnome = self.campo(form, "Nome da disciplina:", 0)
        self.e_codigo = self.campo(form, "Código:", 1)
        self.e_carga = self.campo(form, "Carga horária (h):", 2, 10)
        ttk.Label(form, text="Professor:").grid(row=3, column=0, sticky="w", pady=3)
        self.cb_professor = ttk.Combobox(form, state="readonly", width=27, values=[SEM_PROFESSOR])
        self.cb_professor.set(SEM_PROFESSOR)
        self.cb_professor.grid(row=3, column=1, sticky="w", padx=8, pady=3)
        ttk.Label(form, text="Cada professor só pode lecionar uma disciplina.",
                  foreground="#555555").grid(row=3, column=2, sticky="w")
        self.botoes_crud(form, 4, "Cadastrar disciplina", self.cadastrar_disciplina,
                         self.salvar_disciplina, self.excluir_disciplina, self.limpar_disciplina)
        dica = ("Selecione uma linha para editar ou excluir."
                if self.eh_admin else "Disciplinas e seus professores. Somente visualização.")
        ttk.Label(f, text=dica, foreground="#555555").pack(anchor="w")
        self.tab_disc = criar_tabela(f, ("Nome", "Código", "Carga horária", "Professor"),
                                     (300, 120, 120, 230))
        self.tab_disc.bind("<<TreeviewSelect>>", self.ao_selecionar_disciplina)

    def campos_disciplina(self):
        nome, codigo = self.e_dnome.get().strip(), self.e_codigo.get().strip()
        try:
            carga = int(self.e_carga.get().strip())
            if carga < 1:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Atenção", "A carga horária deve ser um inteiro positivo.")
            return None
        if not nome or not codigo:
            messagebox.showwarning("Atenção", "Nome e código são obrigatórios.")
            return None
        return nome, codigo, carga

    def atualizar_combo_professor(self, disciplina_id=None):
        """Lista os professores que ainda não lecionam (e o da disciplina em edição, se houver)."""
        try:
            livres = docencia.professores_livres(self.banco, disciplina_id)
        except PyMongoError as erro:
            return self.erro_banco(erro)
        self.professores_por_rotulo = {docencia.rotulo_professor(u): u for u in livres}
        valores = [SEM_PROFESSOR, *self.professores_por_rotulo]
        self.cb_professor["values"] = valores
        if self.cb_professor.get() not in valores:
            self.cb_professor.set(SEM_PROFESSOR)

    def professor_escolhido(self):
        """Usuário do professor escolhido no formulário (None = sem professor)."""
        return self.professores_por_rotulo.get(self.cb_professor.get())

    def ao_selecionar_disciplina(self, _evento=None):
        disciplina = self.selecionado(self.tab_disc, self.disciplinas_por_iid)
        if disciplina:
            limpar_campos(self.e_dnome, self.e_codigo, self.e_carga)
            self.e_dnome.insert(0, disciplina["nome"])
            self.e_codigo.insert(0, disciplina["codigo"])
            self.e_carga.insert(0, str(disciplina["carga_horaria"]))
            if self.eh_admin:
                self.atualizar_combo_professor(disciplina["_id"])
                professor = disciplina.get("professor")
                self.cb_professor.set(docencia.rotulo_professor(professor) if professor else SEM_PROFESSOR)

    def limpar_disciplina(self):
        limpar_campos(self.e_dnome, self.e_codigo, self.e_carga)
        self.tab_disc.selection_set(())
        if self.eh_admin:
            self.atualizar_combo_professor()
            self.cb_professor.set(SEM_PROFESSOR)

    def erro_duplicata_disciplina(self, erro):
        if docencia.duplicata_de_professor(erro):
            return messagebox.showwarning(
                "Professor já tem disciplina",
                "Esse professor já leciona outra disciplina. Cada professor pode ter somente uma.")
        return messagebox.showerror("Erro", "Esse código já está cadastrado.")

    def cadastrar_disciplina(self):
        if not self.exigir(self.eh_admin, "cadastrar disciplinas"):
            return
        valores = self.campos_disciplina()
        if not valores:
            return
        nome, codigo, carga = valores
        professor = self.professor_escolhido()
        documento = {"nome": nome, "codigo": codigo, "carga_horaria": carga}
        try:
            docencia.validar_professor(self.banco, professor)
            if professor:
                documento["professor"] = professor
            self.banco.disciplinas.insert_one(documento)
        except docencia.ProfessorOcupadoError as erro:
            return messagebox.showwarning("Professor já tem disciplina", str(erro))
        except ValueError as erro:
            return messagebox.showwarning("Atenção", str(erro))
        except DuplicateKeyError as erro:
            return self.erro_duplicata_disciplina(erro)
        except PyMongoError as erro:
            return self.erro_banco(erro)
        self.limpar_disciplina()
        self.carregar_dados()
        messagebox.showinfo("Sucesso", "Disciplina cadastrada com sucesso.")

    def salvar_disciplina(self):
        if not self.exigir(self.eh_admin, "alterar disciplinas"):
            return
        disciplina = self.selecionado(self.tab_disc, self.disciplinas_por_iid)
        if not disciplina:
            return messagebox.showwarning("Atenção", "Selecione uma disciplina na tabela.")
        valores = self.campos_disciplina()
        if not valores:
            return
        nome, codigo, carga = valores
        professor = self.professor_escolhido()
        try:
            docencia.validar_professor(self.banco, professor, disciplina["_id"])
            self.banco.disciplinas.update_one(
                {"_id": disciplina["_id"]},
                docencia.operacao_de_atualizacao(
                    {"nome": nome, "codigo": codigo, "carga_horaria": carga}, professor))
        except docencia.ProfessorOcupadoError as erro:
            return messagebox.showwarning("Professor já tem disciplina", str(erro))
        except ValueError as erro:
            return messagebox.showwarning("Atenção", str(erro))
        except DuplicateKeyError as erro:
            return self.erro_duplicata_disciplina(erro)
        except PyMongoError as erro:
            return self.erro_banco(erro)
        self.limpar_disciplina()
        self.carregar_dados()
        messagebox.showinfo("Sucesso", "Disciplina atualizada.")

    def excluir_disciplina(self):
        if not self.exigir(self.eh_admin, "excluir disciplinas"):
            return
        disciplina = self.selecionado(self.tab_disc, self.disciplinas_por_iid)
        if not disciplina:
            return messagebox.showwarning("Atenção", "Selecione uma disciplina na tabela.")
        try:
            qtd = self.banco.notas.count_documents({"disciplina_id": disciplina["_id"]})
            if not messagebox.askyesno(
                    "Confirmar exclusão",
                    f"Excluir {disciplina['nome']} e as {qtd} nota(s) lançadas nela? "
                    "Isso não pode ser desfeito."):
                return
            self.banco.notas.delete_many({"disciplina_id": disciplina["_id"]})
            self.banco.disciplinas.delete_one({"_id": disciplina["_id"]})
        except PyMongoError as erro:
            return self.erro_banco(erro)
        self.limpar_disciplina()
        self.carregar_dados()

    # ---------- lançar notas (AVG, AVI e AVC por disciplina e semestre) ----------
    def montar_aba_notas(self):
        f = self.aba("Lançar notas")
        form = ttk.Frame(f)
        form.pack(fill="x")
        self.cb_nota_aluno = self.combo(form, "Aluno:", 0, self.combos_alunos)
        self.cb_nota_disc = self.combo(form, "Disciplina:", 1, self.combos_disciplinas)
        ttk.Label(form, text="Semestre:").grid(row=2, column=0, sticky="w", pady=3)
        self.sp_semestre = ttk.Spinbox(form, from_=1, to=SEMESTRES, width=5, state="readonly",
                                       command=self.preencher_form_notas)
        self.sp_semestre.set(1)
        self.sp_semestre.grid(row=2, column=1, sticky="w", padx=8, pady=3)

        provas = ttk.LabelFrame(form, text="Notas das provas (0 a 10)", padding=10)
        provas.grid(row=3, column=0, columnspan=2, sticky="w", pady=8)
        self.e_provas = {}
        for i, nome in enumerate(PROVAS):
            ttk.Label(provas, text=f"{nome}:").grid(row=0, column=2 * i, padx=(0 if i == 0 else 16, 4))
            entrada = ttk.Entry(provas, width=8, justify="center")
            entrada.grid(row=0, column=2 * i + 1)
            entrada.bind("<KeyRelease>", lambda e: self.atualizar_media_previa())
            self.e_provas[nome] = entrada
        self.lbl_media_previa = ttk.Label(form, text="Média: -", font=("Segoe UI", 10, "bold"))
        self.lbl_media_previa.grid(row=4, column=1, sticky="w", padx=8)
        ttk.Button(form, text="Lançar / atualizar notas", command=self.lancar_nota).grid(
            row=5, column=1, sticky="w", padx=8, pady=8)

        ttk.Label(f, text="Notas do aluno selecionado:").pack(anchor="w")
        self.tab_notas = criar_tabela(f, COLUNAS_NOTAS, LARGURAS_NOTAS)
        self.cb_nota_aluno.bind("<<ComboboxSelected>>", lambda e: self.ao_mudar_selecao())
        self.cb_nota_disc.bind("<<ComboboxSelected>>", lambda e: self.ao_mudar_selecao())

    def ao_mudar_selecao(self):
        self.preencher_form_notas()
        self.atualizar_notas_aluno()

    def atualizar_media_previa(self):
        valores = []
        for entrada in self.e_provas.values():
            try:
                valores.append(ler_nota_opcional(entrada.get()))
            except ValueError:
                valores.append(None)
        self.lbl_media_previa.config(text=f"Média: {fmt(calcular_media(valores))}")

    def preencher_form_notas(self):
        """Se já existem notas para aluno + disciplina + semestre, mostra nos campos para edição."""
        for entrada in self.e_provas.values():
            entrada.delete(0, "end")
        aluno = self.mapa_alunos.get(self.cb_nota_aluno.get())
        disciplina = self.mapa_disciplinas.get(self.cb_nota_disc.get())
        if aluno and disciplina:
            try:
                existente = self.banco.notas.find_one({
                    "aluno_id": aluno["_id"], "disciplina_id": disciplina["_id"],
                    "semestre": int(self.sp_semestre.get())})
            except PyMongoError as erro:
                return self.erro_banco(erro)
            if existente:
                for nome, entrada in self.e_provas.items():
                    valor = existente.get(nome.lower())
                    if valor is not None:
                        entrada.insert(0, f"{valor:g}")
        self.atualizar_media_previa()

    def atualizar_notas_aluno(self):
        aluno = self.mapa_alunos.get(self.cb_nota_aluno.get())
        if not aluno:
            return preencher(self.tab_notas, [])
        try:
            dados = notas_do_aluno(self.banco, aluno["_id"])
        except PyMongoError as erro:
            return self.erro_banco(erro)
        preencher(self.tab_notas, [linha_nota(d) for d in dados])

    def lancar_nota(self):
        if not self.exigir(self.pode_lancar, "lançar notas"):
            return
        aluno = self.mapa_alunos.get(self.cb_nota_aluno.get())
        disciplina = self.mapa_disciplinas.get(self.cb_nota_disc.get())
        if not aluno or not disciplina:
            return messagebox.showwarning("Atenção", "Selecione o aluno e a disciplina.")
        try:
            notas = {nome.lower(): ler_nota_opcional(e.get()) for nome, e in self.e_provas.items()}
        except ValueError:
            return messagebox.showwarning(
                "Atenção", "As notas devem ser números entre 0 e 10 (ou ficar em branco).")
        if all(v is None for v in notas.values()):
            return messagebox.showwarning("Atenção", "Informe pelo menos uma nota.")
        filtro = {"aluno_id": aluno["_id"], "disciplina_id": disciplina["_id"],
                  "semestre": int(self.sp_semestre.get())}
        documento = {**filtro, **notas, "data_lancamento": datetime.now(timezone.utc)}
        try:
            r = self.banco.notas.replace_one(filtro, documento, upsert=True)
        except PyMongoError as erro:
            return self.erro_banco(erro)
        self.atualizar_notas_aluno()
        acao = "atualizadas" if r.matched_count else "lançadas"
        media = calcular_media(notas.values())
        extra = f" Média: {fmt(media)}." if media is not None else " A média aparece com 2 ou mais notas."
        messagebox.showinfo("Sucesso", f"Notas {acao} com sucesso.{extra}")

    # ---------- componentes compartilhados ----------
    def quadro_dados_aluno(self, pai):
        """Quadro com nome, matrícula e turma do aluno. Devolve os rótulos para preencher depois."""
        quadro = ttk.LabelFrame(pai, text="Dados do aluno", padding=10)
        quadro.pack(fill="x", pady=10)
        rotulos = {}
        for i, (chave, titulo) in enumerate((("nome", "Nome"), ("matricula", "Matrícula"), ("turma", "Turma"))):
            ttk.Label(quadro, text=f"{titulo}:", font=("Segoe UI", 9, "bold")).grid(
                row=0, column=2 * i, sticky="w", padx=(0 if i == 0 else 28, 4))
            rotulo = ttk.Label(quadro, text="-")
            rotulo.grid(row=0, column=2 * i + 1, sticky="w")
            rotulos[chave] = rotulo
        return rotulos

    @staticmethod
    def mostrar_dados_aluno(rotulos, aluno):
        for chave, rotulo in rotulos.items():
            rotulo.config(text=aluno[chave] if aluno else "-")

    # ---------- relatório do aluno (boletim + resumo por IA, numa aba só) ----------
    def montar_aba_relatorio(self):
        f = self.aba("Relatório do aluno")
        topo = ttk.Frame(f)
        topo.pack(fill="x")
        self.cb_rel_aluno = self.combo(topo, "Aluno:", 0, self.combos_alunos)
        ttk.Button(topo, text="Atualizar", command=self.gerar_relatorio).grid(row=0, column=2, padx=8)
        ttk.Button(topo, text="Ver gráfico", command=self.abrir_grafico).grid(row=0, column=3)
        self.bt_rel_ia = ttk.Button(topo, text="Resumo por IA", command=self.resumo_ia_relatorio)
        self.bt_rel_ia.grid(row=0, column=4, padx=8)
        ttk.Button(topo, text="Chave de IA...", command=self.configurar_chave_ia).grid(row=0, column=5)
        self.lbl_rel = self.quadro_dados_aluno(f)
        self.lbl_rel_aviso = ttk.Label(f, text="Selecione um aluno para ver o boletim.", foreground="#555555")
        self.lbl_rel_aviso.pack(anchor="w")

        # rodapé, resumo por IA e média geral são empacotados antes da tabela para nunca ficarem cortados
        ttk.Label(f, text=("Média da disciplina = soma das duas maiores notas (AVG, AVI, AVC) ÷ 2. "
                           "Média do semestre = média das disciplinas. Média geral = média dos semestres."),
                  foreground="#555555", wraplength=940, justify="left").pack(side="bottom", anchor="w")
        self.txt_rel_ia = tk.Text(f, height=7, wrap="word", state="disabled", relief="solid",
                                  borderwidth=1, font=("Segoe UI", 10))
        self.txt_rel_ia.pack(side="bottom", fill="x", pady=(0, 6))
        self.escrever_caixa(self.txt_rel_ia, "Escolha um aluno e clique em \"Resumo por IA\" "
                            "para ler um resumo do desempenho em linguagem natural.")
        self.faixa_rel_ia = self.criar_faixa_ia(f, "bottom")
        self.lbl_media_geral = ttk.Label(f, text="Média geral: -", font=("Segoe UI", 11, "bold"))
        self.lbl_media_geral.pack(side="bottom", anchor="e", pady=(4, 2))

        quadro = ttk.Frame(f)
        quadro.pack(fill="both", expand=True, pady=6)
        self.arvore = ttk.Treeview(quadro, columns=("professor", "avg", "avi", "avc", "media"),
                                   show="tree headings", height=10)
        self.arvore.heading("#0", text="Semestre / Disciplina", anchor="w")
        self.arvore.column("#0", width=300, anchor="w")
        self.arvore.heading("professor", text="Professor", anchor="w")
        self.arvore.column("professor", width=180, anchor="w")
        for coluna, titulo in (("avg", "AVG"), ("avi", "AVI"), ("avc", "AVC"), ("media", "Média")):
            self.arvore.heading(coluna, text=titulo, anchor="center")
            self.arvore.column(coluna, width=85, anchor="center")
        self.arvore.tag_configure("semestre", background="#e3eaf7", font=("Segoe UI", 9, "bold"))
        barra = ttk.Scrollbar(quadro, orient="vertical", command=self.arvore.yview)
        self.arvore.configure(yscrollcommand=barra.set)
        self.arvore.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.cb_rel_aluno.bind("<<ComboboxSelected>>", lambda e: self.gerar_relatorio())

    def gerar_relatorio(self, avisar=True):
        aluno = self.mapa_alunos.get(self.cb_rel_aluno.get())
        if not aluno:
            if avisar:
                messagebox.showwarning("Atenção", "Selecione um aluno.")
            return
        try:
            dados = notas_do_aluno(self.banco, aluno["_id"])
        except PyMongoError as erro:
            return self.erro_banco(erro)
        self.mostrar_dados_aluno(self.lbl_rel, aluno)

        semestres, geral, qtd = montar_boletim(dados)
        self.arvore.delete(*self.arvore.get_children())
        for numero, disciplinas, media in semestres:
            pai = self.arvore.insert("", "end", text=f"{numero}º Semestre", open=True,
                                     values=("", "", "", "", fmt(media)), tags=("semestre",))
            if not disciplinas:
                self.arvore.insert(pai, "end", text="(sem notas lançadas)")
            for d in disciplinas:
                self.arvore.insert(pai, "end", text=d["disciplina"], values=(
                    docencia.texto_professor(d), fmt(d.get("avg")), fmt(d.get("avi")),
                    fmt(d.get("avc")), fmt(media_da_nota(d))))

        self.lbl_media_geral.config(
            text=f"Média geral ({qtd} de {SEMESTRES} semestres com média): {fmt(geral)}")
        self.lbl_rel_aviso.config(text="" if dados else "Esse aluno ainda não possui notas lançadas.")
        self.escrever_caixa(self.txt_rel_ia, "Clique em \"Resumo por IA\" para ler um resumo "
                            f"do desempenho de {aluno['nome']}.")

    def abrir_grafico(self):
        """Abre uma janela com o gráfico de médias por disciplina do aluno selecionado."""
        aluno = self.mapa_alunos.get(self.cb_rel_aluno.get())
        if not aluno:
            return messagebox.showwarning("Atenção", "Selecione um aluno.")
        try:
            medias = medias_por_disciplina(notas_do_aluno(self.banco, aluno["_id"]))
        except PyMongoError as erro:
            return self.erro_banco(erro)
        if not medias:
            return messagebox.showinfo("Gráfico", "Esse aluno ainda não possui médias para exibir.")
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
        except ImportError:
            return messagebox.showerror(
                "Gráfico", "Instale o matplotlib (pip install matplotlib) para ver o gráfico.")
        from graficos import desenhar_medias

        janela = tk.Toplevel(self)
        janela.title(f"Médias de {aluno['nome']}")
        figura = Figure(figsize=(8, 4.5), dpi=100)
        desenhar_medias(figura, medias, aluno["nome"])
        canvas = FigureCanvasTkAgg(figura, master=janela)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # ---------- alerta precoce de risco ----------
    def montar_aba_risco(self):
        f = self.aba("Alerta de risco")
        topo = ttk.Frame(f)
        topo.pack(fill="x")
        ttk.Button(topo, text="Atualizar análise", command=self.gerar_risco).pack(side="left")
        self.bt_ia = ttk.Button(topo, text="Explicar com IA", command=self.explicar_com_ia)
        self.bt_ia.pack(side="left", padx=6)
        ttk.Button(topo, text="Chave de IA...", command=self.configurar_chave_ia).pack(side="left")
        ttk.Label(topo, text="Turma:").pack(side="left", padx=(14, 4))
        self.cb_risco_turma = ttk.Combobox(topo, state="readonly", width=20, values=[TODAS_TURMAS])
        self.cb_risco_turma.set(TODAS_TURMAS)
        self.cb_risco_turma.pack(side="left")
        self.cb_risco_turma.bind("<<ComboboxSelected>>", lambda e: self.mostrar_risco())
        self.lbl_risco_resumo = ttk.Label(topo, text="", font=("Segoe UI", 10, "bold"))
        self.lbl_risco_resumo.pack(side="left", padx=14)
        self.risco_por_iid = {}
        self.risco_lista = []
        self.tab_risco = criar_tabela(
            f, ("Aluno", "Turma", "Média", "Risco", "Pontos", "Motivos"),
            (190, 90, 70, 80, 60, 520))
        self.faixa_ia = self.criar_faixa_ia(f)
        self.txt_ia = tk.Text(f, height=9, wrap="word", state="disabled", relief="solid",
                              borderwidth=1, font=("Segoe UI", 10))
        self.txt_ia.pack(fill="x", pady=(0, 6))
        self.mostrar_texto_ia("Selecione um aluno na tabela e clique em \"Explicar com IA\" "
                              "para gerar um resumo em linguagem natural.")
        self.tab_risco.column("Motivos", anchor="w")
        for nivel, cor in (("alto", "#f8d7da"), ("médio", "#fff3cd"), ("baixo", "#d9f0de")):
            self.tab_risco.tag_configure(nivel, background=cor)
        ttk.Label(f, text=("Modelo explicável: soma pontos por média baixa, disciplinas abaixo de 6, "
                           "queda entre semestres e dados incompletos. Baixo < 25, médio 25-49, alto ≥ 50. "
                           "É um alerta para apoiar a decisão, não um veredito."),
                  foreground="#555555", wraplength=940, justify="left").pack(anchor="w")

    def gerar_risco(self):
        try:
            resultado = avaliar_todos(self.banco)
        except PyMongoError as erro:
            return self.erro_banco(erro)
        self.risco_lista = resultado
        self.risco_por_iid = {str(r["aluno_id"]): r for r in resultado}
        self.mostrar_risco()

    def mostrar_risco(self):
        """Preenche a tabela de risco, filtrando pela turma escolhida (a lista completa fica guardada)."""
        turma = self.cb_risco_turma.get()
        visiveis = [r for r in self.risco_lista if turma in (TODAS_TURMAS, r["turma"])]
        self.tab_risco.delete(*self.tab_risco.get_children())
        for r in visiveis:
            self.tab_risco.insert("", "end", iid=str(r["aluno_id"]), tags=(r["nivel"],), values=(
                r["nome"], r["turma"], fmt(r["media"]), r["nivel"].capitalize(),
                r["pontos"], " ".join(r["motivos"])))
        altos = sum(r["nivel"] == "alto" for r in visiveis)
        medios = sum(r["nivel"] == "médio" for r in visiveis)
        escopo = "" if turma == TODAS_TURMAS else f" ({turma})"
        self.lbl_risco_resumo.config(
            text=f"{altos} em risco alto, {medios} em risco médio, de {len(visiveis)} aluno(s){escopo}")


    # ---------- usuários (só o administrador) ----------
    def montar_aba_usuarios(self):
        f = self.aba("Usuários")
        form = ttk.Frame(f)
        form.pack(fill="x")
        self.e_usuario_novo = self.campo(form, "Usuário:", 0)
        ttk.Label(form, text="Senha:").grid(row=1, column=0, sticky="w", pady=3)
        self.e_senha_nova = ttk.Entry(form, width=30, show="*")
        self.e_senha_nova.grid(row=1, column=1, sticky="w", padx=8, pady=3)
        ttk.Label(form, text="Perfil:").grid(row=2, column=0, sticky="w", pady=3)
        self.cb_perfil_novo = ttk.Combobox(form, state="readonly", width=27, values=autenticacao.PERFIS_EXTRAS)
        self.cb_perfil_novo.set(autenticacao.PERFIL_PROFESSOR)
        self.cb_perfil_novo.grid(row=2, column=1, sticky="w", padx=8, pady=3)

        botoes = ttk.Frame(form)
        botoes.grid(row=3, column=1, sticky="w", padx=8, pady=8)
        self.bt_criar_usuario = ttk.Button(botoes, text="Criar usuário", command=self.criar_usuario)
        self.bt_criar_usuario.pack(side="left")
        ttk.Button(botoes, text="Trocar senha do selecionado",
                   command=self.trocar_senha_usuario).pack(side="left", padx=6)
        ttk.Button(botoes, text="Excluir selecionado", command=self.excluir_usuario).pack(side="left")
        self.lbl_limite_usuarios = ttk.Label(f, text="", font=("Segoe UI", 10, "bold"))
        self.lbl_limite_usuarios.pack(anchor="w", pady=(4, 0))
        self.tab_usuarios = criar_tabela(f, ("Usuário", "Perfil", "Disciplina", "Criado em"),
                                         (220, 130, 260, 170))
        ttk.Label(f, text=("Secretaria: único perfil que edita (alunos, disciplinas, notas e usuários). Só existe "
                           "uma conta, e ela não pode ser excluída.\nProfessor: apenas visualiza e leciona no "
                           "máximo uma disciplina; o vínculo é feito na aba Disciplinas.\nConsulta: apenas "
                           "visualiza. Para trocar a senha, escolha o usuário na tabela e digite a nova senha "
                           "no campo Senha."),
                  foreground="#555555", justify="left").pack(anchor="w")

    def carregar_usuarios(self):
        try:
            usuarios = autenticacao.listar_usuarios(self.banco)
            disciplina_de = {d["professor"]: d["nome"]
                             for d in self.banco.disciplinas.find({"professor": {"$exists": True}})}
        except PyMongoError as erro:
            return self.erro_banco(erro)
        linhas = []
        for u in usuarios:
            criado = u.get("data_cadastro")
            linhas.append((u["usuario"], autenticacao.rotulo_perfil(autenticacao.perfil_do(u)),
                           disciplina_de.get(u["usuario"], "-"),
                           criado.strftime("%d/%m/%Y %H:%M") if criado else "-"))
        preencher(self.tab_usuarios, linhas, [u["usuario"] for u in usuarios])
        extras = sum(autenticacao.perfil_do(u) in autenticacao.PERFIS_EXTRAS for u in usuarios)
        maximo = autenticacao.MAX_USUARIOS_EXTRAS
        self.lbl_limite_usuarios.config(text=f"Usuários além da secretaria: {extras} de {maximo}")
        self.bt_criar_usuario.config(state="disabled" if extras >= maximo else "normal")

    def criar_usuario(self):
        if not self.exigir(self.eh_admin, "criar usuários"):
            return
        try:
            autenticacao.criar_usuario(self.banco, self.e_usuario_novo.get(), self.e_senha_nova.get(),
                                       self.cb_perfil_novo.get())
        except autenticacao.LimiteUsuariosError as erro:
            self.carregar_usuarios()
            return messagebox.showwarning("Limite de usuários", str(erro))
        except ValueError as erro:
            return messagebox.showwarning("Atenção", str(erro))
        except DuplicateKeyError:
            return messagebox.showerror("Erro", "Esse usuário já existe.")
        except PyMongoError as erro:
            return self.erro_banco(erro)
        limpar_campos(self.e_usuario_novo, self.e_senha_nova)
        self.carregar_usuarios()
        messagebox.showinfo("Sucesso", "Usuário criado.")

    def usuario_selecionado(self):
        escolha = self.tab_usuarios.selection()
        if not escolha:
            messagebox.showwarning("Atenção", "Selecione um usuário na tabela.")
            return None
        return escolha[0]

    def trocar_senha_usuario(self):
        if not self.exigir(self.eh_admin, "trocar senhas"):
            return
        nome = self.usuario_selecionado()
        if not nome:
            return
        try:
            autenticacao.trocar_senha(self.banco, nome, self.e_senha_nova.get())
        except ValueError as erro:
            return messagebox.showwarning("Atenção", str(erro))
        except PyMongoError as erro:
            return self.erro_banco(erro)
        limpar_campos(self.e_senha_nova)
        messagebox.showinfo("Sucesso", f"Senha de {nome} alterada.")

    def excluir_usuario(self):
        if not self.exigir(self.eh_admin, "excluir usuários"):
            return
        nome = self.usuario_selecionado()
        if not nome:
            return
        if not messagebox.askyesno("Confirmar exclusão", f"Excluir o usuário {nome}?"):
            return
        try:
            autenticacao.excluir_usuario(self.banco, nome)
        except PermissionError as erro:
            return messagebox.showwarning("Não permitido", str(erro))
        except PyMongoError as erro:
            return self.erro_banco(erro)
        self.carregar_usuarios()
        self.carregar_dados()  # a disciplina que ele lecionava fica sem professor

    # ---------- chave de IA (informada na própria janela) ----------
    @staticmethod
    def aplicar_chave_ia(chave, lembrar=False):
        """Usa a chave do Gemini. Por padrão só na memória; com lembrar=True também grava chave_gemini.txt."""
        chave = chave.strip().strip("\"'")
        if not chave:
            return False
        os.environ["GEMINI_API_KEY"] = chave
        os.environ.pop("GOOGLE_API_KEY", None)
        if lembrar:
            explicador.salvar_chave(chave)
        return True

    @staticmethod
    def descricao_chave_ia():
        """Descreve a chave em uso sem expô-la: só provedor, tamanho e as 3 primeiras letras."""
        if not explicador.disponivel():
            return "Nenhuma chave de IA configurada."
        chave = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                 or os.getenv("ANTHROPIC_API_KEY") or "")
        return f"Em uso: {explicador.nome_provedor()}, {len(chave)} caracteres, começa com {chave[:3]!r}."

    def configurar_chave_ia(self):
        """Janela para colar a chave do Gemini (Ctrl+V funciona normalmente)."""
        janela = tk.Toplevel(self)
        janela.title("Chave de IA (Gemini)")
        janela.resizable(False, False)
        janela.transient(self)
        quadro = ttk.Frame(janela, padding=16)
        quadro.pack()
        ttk.Label(quadro, text="Cole aqui a chave do Gemini (aistudio.google.com/apikey):").pack(anchor="w")
        entrada = ttk.Entry(quadro, width=58, show="*")
        entrada.pack(pady=(6, 2))
        mostrar = tk.BooleanVar(value=False)
        ttk.Checkbutton(quadro, text="Mostrar a chave", variable=mostrar,
                        command=lambda: entrada.config(show="" if mostrar.get() else "*")).pack(anchor="w")
        lembrar = tk.BooleanVar(value=False)
        ttk.Checkbutton(quadro, variable=lembrar, text=(
            "Lembrar nesta máquina (grava a chave em chave_gemini.txt, texto simples)")).pack(anchor="w", pady=(6, 0))
        status = ttk.Label(quadro, text=self.descricao_chave_ia(), foreground="#555555", wraplength=420)
        status.pack(anchor="w", pady=(8, 2))
        ttk.Label(quadro, text=("Sem marcar \"Lembrar\", a chave fica só na memória e some ao fechar o programa.\n"
                                "Apenas médias e motivos do alerta são enviados, sem nome do aluno."),
                  foreground="#555555", justify="left").pack(anchor="w")

        def usar():
            if not self.aplicar_chave_ia(entrada.get(), lembrar.get()):
                return status.config(text="Cole a chave no campo acima.", foreground="#c0392b")
            entrada.delete(0, "end")
            status.config(text=self.descricao_chave_ia(), foreground="#1e7e34")
            extra = " Ela foi salva em chave_gemini.txt." if lembrar.get() else ""
            messagebox.showinfo("Chave de IA", "Chave aplicada. Já pode usar o resumo por IA." + extra,
                                parent=janela)
            janela.destroy()

        def esquecer():
            apagou = explicador.esquecer_chave_salva()
            os.environ.pop("GEMINI_API_KEY", None)
            os.environ.pop("GOOGLE_API_KEY", None)
            status.config(text=("Chave removida da memória e do arquivo." if apagou
                                else "Chave removida da memória."), foreground="#555555")

        botoes = ttk.Frame(quadro)
        botoes.pack(anchor="e", pady=(10, 0))
        ttk.Button(botoes, text="Usar esta chave", command=usar).pack(side="left")
        ttk.Button(botoes, text="Esquecer chave", command=esquecer).pack(side="left", padx=6)
        ttk.Button(botoes, text="Cancelar", command=janela.destroy).pack(side="left", padx=6)
        entrada.focus()
        janela.bind("<Return>", lambda e: usar())
        janela.grab_set()

    @staticmethod
    def escrever_caixa(caixa, texto):
        caixa.config(state="normal")
        caixa.delete("1.0", "end")
        caixa.insert("1.0", texto)
        caixa.config(state="disabled")

    def mostrar_texto_ia(self, texto):
        self.escrever_caixa(self.txt_ia, texto)

    def criar_faixa_ia(self, pai, lado="top"):
        """Faixa de status do resumo por IA: texto e barra animada, visíveis só enquanto carrega.

        Devolve (quadro, rótulo, barra). O espaço da faixa fica reservado, então a tela não "pula"."""
        quadro = ttk.Frame(pai)
        quadro.pack(side=lado, fill="x", pady=(2, 4))
        rotulo = ttk.Label(quadro, text="", width=46, foreground="#1f4e9c", font=("Segoe UI", 9, "bold"))
        rotulo.grid(row=0, column=0, sticky="w")
        barra = ttk.Progressbar(quadro, mode="indeterminate", length=200)
        barra.grid(row=0, column=1, padx=10)
        barra.grid_remove()
        return quadro, rotulo, barra

    def gerar_resumo_ia(self, nome, avaliacao, dados, botao, caixa, faixa):
        """Pede o resumo à IA em segundo plano e o mostra na caixa de texto (sem travar a janela).

        Enquanto espera, a `faixa` mostra uma barra animada e o tempo decorrido, para a pessoa saber
        que o sistema está trabalhando. A IA só redige o texto: o nível, os pontos e os motivos
        vêm das regras de risco.py."""
        _, rotulo, barra = faixa
        if avaliacao["nivel"] == "sem dados":
            return self.escrever_caixa(
                caixa, f"{nome} ainda não tem médias calculáveis (são necessárias pelo menos "
                "2 provas lançadas em uma disciplina).\nLance as notas na aba \"Lançar notas\"; "
                "nenhuma chamada à IA foi feita.")
        if not explicador.disponivel():
            if messagebox.askyesno("Resumo por IA",
                                   explicador.ORIENTACAO + "\n\nQuer informar a chave agora?"):
                self.configurar_chave_ia()
            return

        provedor = explicador.nome_provedor()
        botao.config(state="disabled")
        self.escrever_caixa(caixa, f"Gerando resumo com {provedor}...\n"
                            "Isso pode levar alguns segundos. A tela não está travada: "
                            "o sistema está buscando a resposta.")
        barra.grid()
        barra.start(12)
        inicio = time.monotonic()
        resultado = {}

        def trabalho():
            try:
                resultado["texto"] = explicador.explicar(avaliacao, dados)
            except explicador.ExplicadorErro as erro:
                resultado["erro"] = str(erro)
            except Exception as erro:  # qualquer outra falha também precisa encerrar a animação
                resultado["erro"] = f"Erro inesperado: {erro}"

        def verificar():
            if not resultado:
                decorrido = time.monotonic() - inicio
                pontos = "." * (int(decorrido * 3) % 4)
                rotulo.config(text=f"Gerando resumo com {provedor}{pontos}   ({int(decorrido)} s)")
                return self.after(150, verificar)
            barra.stop()
            barra.grid_remove()
            rotulo.config(text="")
            botao.config(state="normal")
            if "erro" in resultado:
                self.escrever_caixa(caixa, f"Não foi possível gerar o resumo.\n{resultado['erro']}")
            else:
                self.escrever_caixa(
                    caixa, f"{nome} - risco {avaliacao['nivel']} ({avaliacao['pontos']} pts)\n\n"
                    f"{resultado['texto']}\n\n(Texto gerado por {provedor} a partir de dados sem "
                    "identificação; confira antes de usar.)")

        threading.Thread(target=trabalho, daemon=True).start()
        self.after(150, verificar)

    def explicar_com_ia(self):
        """Resumo por IA do aluno selecionado na tabela de risco."""
        escolha = self.tab_risco.selection()
        risco = self.risco_por_iid.get(escolha[0]) if escolha else None
        if not risco:
            return messagebox.showwarning("Atenção", "Selecione um aluno na tabela.")
        try:
            dados = notas_do_aluno(self.banco, risco["aluno_id"])
        except PyMongoError as erro:
            return self.erro_banco(erro)
        self.gerar_resumo_ia(risco["nome"], risco, dados, self.bt_ia, self.txt_ia, self.faixa_ia)

    def resumo_ia_relatorio(self):
        """Resumo por IA do aluno escolhido na aba Relatório do aluno."""
        aluno = self.mapa_alunos.get(self.cb_rel_aluno.get())
        if not aluno:
            return messagebox.showwarning("Atenção", "Selecione um aluno.")
        try:
            dados = notas_do_aluno(self.banco, aluno["_id"])
        except PyMongoError as erro:
            return self.erro_banco(erro)
        self.gerar_resumo_ia(aluno["nome"], avaliar_aluno(dados), dados,
                             self.bt_rel_ia, self.txt_rel_ia, self.faixa_rel_ia)


def main():
    explicador.carregar_chave_salva()  # usa a chave guardada em chave_gemini.txt, se você pediu para lembrar
    try:
        cliente, banco = conectar_banco()
    except (RuntimeError, PyMongoError) as erro:
        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror("Erro de conexão", f"Não foi possível conectar ao banco '{NOME_BANCO}':\n{erro}")
        return
    try:
        while True:
            login = Login(banco)
            login.mainloop()
            if not login.usuario:
                break  # fechou a janela de login
            app = App(banco, login.usuario, login.perfil)
            app.mainloop()
            if not app.sair_para_login:
                break  # fechou a janela principal
    finally:
        cliente.close()


if __name__ == "__main__":
    main()
