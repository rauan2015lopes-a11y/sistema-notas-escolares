"""Interface gráfica (Tkinter) do sistema de notas escolares.

Reaproveita banco.py e config.py. Execute com: python tela.py
(a variável de ambiente MONGODB_URI precisa estar definida).
"""

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from pymongo.errors import DuplicateKeyError, PyMongoError

import autenticacao
from banco import conectar_banco
from config import NOME_BANCO


SEMESTRES = 4  # curso de 2 anos = 4 semestres
PROVAS = ("AVG", "AVI", "AVC")
COLUNAS_NOTAS = ("Disciplina", "Semestre", "AVG", "AVI", "AVC", "Média")
LARGURAS_NOTAS = (320, 90, 90, 90, 90, 100)


def ler_nota_opcional(texto):
    """Converte o texto de um campo em nota (0 a 10). Vazio vira None; inválido gera ValueError."""
    texto = texto.strip().replace(",", ".")
    if not texto:
        return None
    valor = float(texto)
    if not 0 <= valor <= 10:
        raise ValueError
    return round(valor, 2)


def calcular_media(valores):
    """Média do aluno: soma das duas maiores notas dividida por dois.

    Precisa de pelo menos duas notas lançadas; senão devolve None.
    """
    validos = sorted((v for v in valores if v is not None), reverse=True)
    if len(validos) < 2:
        return None
    return round((validos[0] + validos[1]) / 2, 2)


def media_da_nota(documento):
    return calcular_media([documento.get(p.lower()) for p in PROVAS])


def fmt(valor):
    return "-" if valor is None else f"{valor:.2f}"


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


def preencher(tabela, linhas):
    tabela.delete(*tabela.get_children())
    for linha in linhas:
        tabela.insert("", "end", values=linha)


class Login(tk.Tk):
    """Tela inicial: só deixa entrar no sistema quem for administrador."""

    MAX_TENTATIVAS = 5

    def __init__(self, banco):
        super().__init__()
        self.banco = banco
        self.usuario = None
        self.tentativas = 0
        self.primeiro_acesso = not autenticacao.existe_admin(banco)

        self.title("Sistema de Notas Escolares - Login")
        self.geometry("380x" + ("420" if self.primeiro_acesso else "340"))
        self.resizable(False, False)
        ttk.Style(self).theme_use("clam")

        quadro = ttk.Frame(self, padding=28)
        quadro.pack(fill="both", expand=True)
        ttk.Label(quadro, text="Sistema de Notas Escolares",
                  font=("Segoe UI", 14, "bold")).pack(pady=(0, 4))
        subtitulo = ("Primeiro acesso: crie o administrador"
                     if self.primeiro_acesso else "Acesso restrito aos administradores")
        ttk.Label(quadro, text=subtitulo).pack(pady=(0, 16))

        ttk.Label(quadro, text="Usuário:").pack(anchor="w")
        self.e_usuario = ttk.Entry(quadro, width=34)
        self.e_usuario.pack(pady=(0, 8))
        ttk.Label(quadro, text="Senha:").pack(anchor="w")
        self.e_senha = ttk.Entry(quadro, width=34, show="*")
        self.e_senha.pack(pady=(0, 8))

        self.e_confirma = None
        if self.primeiro_acesso:
            ttk.Label(quadro, text="Confirmar senha (mínimo 6 caracteres):").pack(anchor="w")
            self.e_confirma = ttk.Entry(quadro, width=34, show="*")
            self.e_confirma.pack(pady=(0, 8))

        texto = "Criar administrador" if self.primeiro_acesso else "Entrar"
        self.botao = ttk.Button(quadro, text=texto, command=self.confirmar)
        self.botao.pack(pady=10, fill="x")
        self.lbl_erro = ttk.Label(quadro, text="", foreground="#c0392b")
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
        except DuplicateKeyError:
            return self.erro("Esse usuário já existe.")
        except PyMongoError as erro:
            return messagebox.showerror("Erro no banco de dados", str(erro))

        if documento:
            self.usuario = documento["usuario"]
            self.destroy()
            return
        self.tentativas += 1
        restantes = self.MAX_TENTATIVAS - self.tentativas
        if restantes <= 0:
            messagebox.showerror("Acesso bloqueado", "Muitas tentativas inválidas. O programa será fechado.")
            self.destroy()
            return
        self.e_senha.delete(0, "end")
        self.erro(f"Usuário ou senha incorretos. Tentativas restantes: {restantes}")

    def criar_primeiro_admin(self, usuario, senha):
        if len(senha) < 6:
            return self.erro("A senha deve ter pelo menos 6 caracteres.")
        if senha != self.e_confirma.get():
            return self.erro("As senhas não conferem.")
        autenticacao.criar_admin(self.banco, usuario, senha)
        self.usuario = usuario.lower()
        messagebox.showinfo("Sucesso", "Administrador criado. Você já está logado.")
        self.destroy()


class App(tk.Tk):
    def __init__(self, banco, usuario):
        super().__init__()
        self.banco = banco
        self.usuario = usuario
        self.sair_para_login = False
        self.mapa_alunos = {}
        self.mapa_disciplinas = {}
        self.combos_alunos = []
        self.combos_disciplinas = []

        self.title("Sistema de Notas Escolares")
        self.geometry("1000x720")
        ttk.Style(self).theme_use("clam")

        barra = ttk.Frame(self, padding=(10, 6))
        barra.pack(fill="x")
        ttk.Label(barra, text=f"Administrador: {usuario}").pack(side="left")
        ttk.Button(barra, text="Sair", command=self.sair).pack(side="right")

        self.abas = ttk.Notebook(self)
        self.abas.pack(fill="both", expand=True, padx=8, pady=8)
        self.montar_aba_alunos()
        self.montar_aba_disciplinas()
        self.montar_aba_notas()
        self.montar_aba_relatorio()
        self.montar_aba_boletim()
        self.abas.bind("<<NotebookTabChanged>>", lambda e: self.carregar_dados())
        self.carregar_dados()

    def sair(self):
        """Encerra a sessão: volta para a tela de login."""
        self.sair_para_login = True
        self.destroy()

    # ---------- utilidades ----------
    def aba(self, titulo):
        quadro = ttk.Frame(self.abas, padding=12)
        self.abas.add(quadro, text=titulo)
        return quadro

    def campo(self, pai, rotulo, linha, largura=30):
        ttk.Label(pai, text=rotulo).grid(row=linha, column=0, sticky="w", pady=3)
        entrada = ttk.Entry(pai, width=largura)
        entrada.grid(row=linha, column=1, sticky="w", padx=8, pady=3)
        return entrada

    def combo(self, pai, rotulo, linha, lista):
        ttk.Label(pai, text=rotulo).grid(row=linha, column=0, sticky="w", pady=3)
        cb = ttk.Combobox(pai, state="readonly", width=40)
        cb.grid(row=linha, column=1, sticky="w", padx=8, pady=3)
        lista.append(cb)
        return cb

    def erro_banco(self, erro):
        messagebox.showerror("Erro no banco de dados", str(erro))

    def dados_aluno(self, aluno_id):
        """Notas do aluno com o nome da disciplina (mesma agregação do relatório)."""
        pipeline = [
            {"$match": {"aluno_id": aluno_id, "semestre": {"$exists": True}}},
            {"$lookup": {"from": "disciplinas", "localField": "disciplina_id",
                         "foreignField": "_id", "as": "disciplina"}},
            {"$unwind": "$disciplina"},
            {"$project": {"_id": 0, "disciplina": "$disciplina.nome", "semestre": 1,
                          "avg": 1, "avi": 1, "avc": 1}},
            {"$sort": {"disciplina": 1, "semestre": 1}},
        ]
        return list(self.banco.notas.aggregate(pipeline))

    def carregar_dados(self):
        """Recarrega alunos/disciplinas nas tabelas e nas caixas de seleção."""
        try:
            alunos = list(self.banco.alunos.find().sort("nome", 1))
            disciplinas = list(self.banco.disciplinas.find().sort("nome", 1))
        except PyMongoError as erro:
            return self.erro_banco(erro)
        self.mapa_alunos = {f"{a['matricula']} - {a['nome']}": a for a in alunos}
        self.mapa_disciplinas = {f"{d['codigo']} - {d['nome']}": d for d in disciplinas}
        for cb in self.combos_alunos:
            cb["values"] = list(self.mapa_alunos)
        for cb in self.combos_disciplinas:
            cb["values"] = list(self.mapa_disciplinas)
        preencher(self.tab_alunos, [(a["nome"], a["matricula"], a["turma"]) for a in alunos])
        preencher(self.tab_disc, [(d["nome"], d["codigo"], d["carga_horaria"]) for d in disciplinas])

    # ---------- abas ----------
    def montar_aba_alunos(self):
        f = self.aba("Alunos")
        form = ttk.Frame(f)
        form.pack(fill="x")
        self.e_nome = self.campo(form, "Nome completo:", 0)
        self.e_matricula = self.campo(form, "Matrícula:", 1)
        self.e_turma = self.campo(form, "Turma:", 2)
        ttk.Button(form, text="Cadastrar aluno", command=self.cadastrar_aluno).grid(
            row=3, column=1, sticky="w", padx=8, pady=8)
        self.tab_alunos = criar_tabela(f, ("Nome", "Matrícula", "Turma"), (400, 150, 150))

    def cadastrar_aluno(self):
        nome, mat, turma = (e.get().strip() for e in (self.e_nome, self.e_matricula, self.e_turma))
        if not nome or not mat or not turma:
            return messagebox.showwarning("Atenção", "Todos os campos são obrigatórios.")
        try:
            self.banco.alunos.insert_one({"nome": nome, "matricula": mat, "turma": turma,
                                          "data_cadastro": datetime.now()})
        except DuplicateKeyError:
            return messagebox.showerror("Erro", "Essa matrícula já está cadastrada.")
        except PyMongoError as erro:
            return self.erro_banco(erro)
        for e in (self.e_nome, self.e_matricula, self.e_turma):
            e.delete(0, "end")
        self.carregar_dados()
        messagebox.showinfo("Sucesso", "Aluno cadastrado com sucesso.")

    def montar_aba_disciplinas(self):
        f = self.aba("Disciplinas")
        form = ttk.Frame(f)
        form.pack(fill="x")
        self.e_dnome = self.campo(form, "Nome da disciplina:", 0)
        self.e_codigo = self.campo(form, "Código:", 1)
        self.e_carga = self.campo(form, "Carga horária (h):", 2, 10)
        ttk.Button(form, text="Cadastrar disciplina", command=self.cadastrar_disciplina).grid(
            row=3, column=1, sticky="w", padx=8, pady=8)
        self.tab_disc = criar_tabela(f, ("Nome", "Código", "Carga horária"), (400, 150, 150))

    def cadastrar_disciplina(self):
        nome, codigo = self.e_dnome.get().strip(), self.e_codigo.get().strip()
        try:
            carga = int(self.e_carga.get().strip())
            if carga < 1:
                raise ValueError
        except ValueError:
            return messagebox.showwarning("Atenção", "A carga horária deve ser um inteiro positivo.")
        if not nome or not codigo:
            return messagebox.showwarning("Atenção", "Nome e código são obrigatórios.")
        try:
            self.banco.disciplinas.insert_one(
                {"nome": nome, "codigo": codigo, "carga_horaria": carga})
        except DuplicateKeyError:
            return messagebox.showerror("Erro", "Esse código já está cadastrado.")
        except PyMongoError as erro:
            return self.erro_banco(erro)
        for e in (self.e_dnome, self.e_codigo, self.e_carga):
            e.delete(0, "end")
        self.carregar_dados()
        messagebox.showinfo("Sucesso", "Disciplina cadastrada com sucesso.")

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
            return
        try:
            dados = self.dados_aluno(aluno["_id"])
        except PyMongoError as erro:
            return self.erro_banco(erro)
        preencher(self.tab_notas, [linha_nota(d) for d in dados])

    def lancar_nota(self):
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
        documento = {**filtro, **notas, "data_lancamento": datetime.now()}
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

    # ---------- relatório do aluno ----------
    def montar_aba_relatorio(self):
        f = self.aba("Relatório do aluno")
        topo = ttk.Frame(f)
        topo.pack(fill="x")
        self.cb_rel_aluno = self.combo(topo, "Aluno:", 0, self.combos_alunos)
        ttk.Button(topo, text="Gerar relatório", command=self.gerar_relatorio).grid(
            row=0, column=2, padx=8)
        self.lbl_rel = self.quadro_dados_aluno(f)
        self.lbl_rel_aviso = ttk.Label(f, text="Selecione um aluno para ver as notas.", foreground="#555555")
        self.lbl_rel_aviso.pack(anchor="w")
        self.tab_rel = criar_tabela(f, COLUNAS_NOTAS, LARGURAS_NOTAS)
        self.cb_rel_aluno.bind("<<ComboboxSelected>>", lambda e: self.gerar_relatorio())
        ttk.Label(f, text="Média = soma das duas maiores notas (AVG, AVI, AVC) dividida por 2.",
                  foreground="#555555").pack(anchor="w")

    def gerar_relatorio(self):
        aluno = self.mapa_alunos.get(self.cb_rel_aluno.get())
        if not aluno:
            return messagebox.showwarning("Atenção", "Selecione um aluno.")
        try:
            dados = self.dados_aluno(aluno["_id"])
        except PyMongoError as erro:
            return self.erro_banco(erro)
        self.mostrar_dados_aluno(self.lbl_rel, aluno)
        preencher(self.tab_rel, [linha_nota(d) for d in dados])
        self.lbl_rel_aviso.config(text="" if dados else "Esse aluno ainda não possui notas.")

    # ---------- boletim ----------
    def montar_aba_boletim(self):
        f = self.aba("Boletim")
        topo = ttk.Frame(f)
        topo.pack(fill="x")
        self.cb_bol_aluno = self.combo(topo, "Aluno:", 0, self.combos_alunos)
        ttk.Button(topo, text="Ver boletim", command=self.gerar_boletim).grid(
            row=0, column=2, padx=8)
        self.lbl_bol = self.quadro_dados_aluno(f)
        self.lbl_bol_aviso = ttk.Label(f, text="Selecione um aluno para ver o boletim.", foreground="#555555")
        self.lbl_bol_aviso.pack(anchor="w")

        # rodapé empacotado antes da tabela para nunca ficar cortado
        ttk.Label(f, text=("Média da disciplina = soma das duas maiores notas ÷ 2. "
                           "Média do semestre = média das disciplinas. "
                           "Média geral = média dos semestres."),
                  foreground="#555555").pack(side="bottom", anchor="w")
        self.lbl_media_geral = ttk.Label(f, text="Média geral: -", font=("Segoe UI", 11, "bold"))
        self.lbl_media_geral.pack(side="bottom", anchor="e", pady=(4, 2))

        quadro = ttk.Frame(f)
        quadro.pack(fill="both", expand=True, pady=6)
        self.arvore = ttk.Treeview(quadro, columns=("avg", "avi", "avc", "media"),
                                   show="tree headings", height=14)
        self.arvore.heading("#0", text="Semestre / Disciplina", anchor="w")
        self.arvore.column("#0", width=340, anchor="w")
        for coluna, titulo in (("avg", "AVG"), ("avi", "AVI"), ("avc", "AVC"), ("media", "Média")):
            self.arvore.heading(coluna, text=titulo, anchor="center")
            self.arvore.column(coluna, width=100, anchor="center")
        self.arvore.tag_configure("semestre", background="#e3eaf7", font=("Segoe UI", 9, "bold"))
        barra = ttk.Scrollbar(quadro, orient="vertical", command=self.arvore.yview)
        self.arvore.configure(yscrollcommand=barra.set)
        self.arvore.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.cb_bol_aluno.bind("<<ComboboxSelected>>", lambda e: self.gerar_boletim())

    def gerar_boletim(self):
        aluno = self.mapa_alunos.get(self.cb_bol_aluno.get())
        if not aluno:
            return messagebox.showwarning("Atenção", "Selecione um aluno.")
        try:
            dados = self.dados_aluno(aluno["_id"])
        except PyMongoError as erro:
            return self.erro_banco(erro)
        self.mostrar_dados_aluno(self.lbl_bol, aluno)

        por_semestre = {}
        for d in dados:
            por_semestre.setdefault(d["semestre"], []).append(d)

        self.arvore.delete(*self.arvore.get_children())
        medias_semestres = []
        for semestre in range(1, SEMESTRES + 1):
            disciplinas = sorted(por_semestre.get(semestre, []), key=lambda d: d["disciplina"])
            medias = [m for m in (media_da_nota(d) for d in disciplinas) if m is not None]
            media_semestre = round(sum(medias) / len(medias), 2) if medias else None
            if media_semestre is not None:
                medias_semestres.append(media_semestre)
            pai = self.arvore.insert("", "end", text=f"{semestre}º Semestre", open=True,
                                     values=("", "", "", fmt(media_semestre)), tags=("semestre",))
            if not disciplinas:
                self.arvore.insert(pai, "end", text="(sem notas lançadas)")
            for d in disciplinas:
                self.arvore.insert(pai, "end", text=d["disciplina"], values=(
                    fmt(d.get("avg")), fmt(d.get("avi")), fmt(d.get("avc")), fmt(media_da_nota(d))))

        geral = round(sum(medias_semestres) / len(medias_semestres), 2) if medias_semestres else None
        self.lbl_media_geral.config(
            text=f"Média geral ({len(medias_semestres)} de {SEMESTRES} semestres com média): {fmt(geral)}")
        self.lbl_bol_aviso.config(text="" if dados else "Esse aluno ainda não possui notas lançadas.")

def main():
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
                break  # fechou a janela ou excedeu as tentativas
            app = App(banco, login.usuario)
            app.mainloop()
            if not app.sair_para_login:
                break  # fechou a janela principal
    finally:
        cliente.close()


if __name__ == "__main__":
    main()
