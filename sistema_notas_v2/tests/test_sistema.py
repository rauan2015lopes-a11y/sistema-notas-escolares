"""Testes das regras de cálculo e da autenticação (usa mongomock, sem Atlas)."""

import json
import os
import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, HTTPServer
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import mongomock  # noqa: E402
from pymongo.errors import DuplicateKeyError  # noqa: E402

import autenticacao  # noqa: E402
import calculos  # noqa: E402
import docencia  # noqa: E402
import explicador  # noqa: E402
import risco  # noqa: E402


class TestCalculos(unittest.TestCase):
    def test_ler_nota(self):
        self.assertIsNone(calculos.ler_nota_opcional("  "))
        self.assertEqual(calculos.ler_nota_opcional("7,456"), 7.46)
        for ruim in ("11", "-1", "abc", "nan", "inf"):
            with self.assertRaises(ValueError):
                calculos.ler_nota_opcional(ruim)

    def test_media_duas_maiores(self):
        self.assertEqual(calculos.calcular_media([4, 8, 10]), 9.0)
        self.assertEqual(calculos.calcular_media([None, 6, 8]), 7.0)
        self.assertIsNone(calculos.calcular_media([None, 6, None]))

    def test_boletim_e_medias(self):
        dados = [
            {"disciplina": "Mat", "semestre": 1, "avg": 8, "avi": 10, "avc": None},  # 9
            {"disciplina": "Port", "semestre": 1, "avg": 6, "avi": 6, "avc": None},  # 6
            {"disciplina": "Mat", "semestre": 2, "avg": 7, "avi": 7, "avc": 3},      # 7
            {"disciplina": "Hist", "semestre": 2, "avg": 5, "avi": None, "avc": None},  # sem média
        ]
        semestres, geral, qtd = calculos.montar_boletim(dados)
        self.assertEqual([m for _, _, m in semestres], [7.5, 7.0, None, None])
        self.assertEqual((geral, qtd), (7.25, 2))
        self.assertEqual(calculos.medias_por_disciplina(dados), {"Mat": 8.0, "Port": 6.0})


class TestBanco(unittest.TestCase):
    def setUp(self):
        self.banco = mongomock.MongoClient()["teste"]

    def test_senha(self):
        self.assertIsNotNone(autenticacao.validar_senha("curta1"))
        self.assertIsNotNone(autenticacao.validar_senha("somenteletras"))
        self.assertIsNone(autenticacao.validar_senha("senha1234"))

    def test_primeiro_admin_so_uma_vez(self):
        autenticacao.criar_primeiro_admin(self.banco, "Admin", "senha1234")
        with self.assertRaises(PermissionError):
            autenticacao.criar_primeiro_admin(self.banco, "outro", "senha1234")
        with self.assertRaises(ValueError):
            autenticacao.criar_admin(self.banco, "x", "fraca")

    def test_login_e_bloqueio(self):
        autenticacao.criar_admin(self.banco, "admin", "senha1234")
        self.assertIsNotNone(autenticacao.autenticar(self.banco, " ADMIN ", "senha1234"))
        for _ in range(autenticacao.MAX_FALHAS):
            self.assertIsNone(autenticacao.autenticar(self.banco, "admin", "errada123"))
        with self.assertRaises(autenticacao.BloqueadoError) as ctx:
            autenticacao.autenticar(self.banco, "admin", "senha1234")  # nem a certa entra
        self.assertGreater(ctx.exception.segundos, 0)

        # passado o prazo, volta a funcionar e zera o registro
        self.banco.tentativas_login.update_one(
            {"_id": "admin"},
            {"$set": {"bloqueado_ate": datetime.now(timezone.utc) - timedelta(seconds=1)}})
        self.assertIsNotNone(autenticacao.autenticar(self.banco, "admin", "senha1234"))
        self.assertIsNone(self.banco.tentativas_login.find_one({"_id": "admin"}))

    def test_usuario_inexistente_tambem_conta_falha(self):
        for _ in range(autenticacao.MAX_FALHAS):
            self.assertIsNone(autenticacao.autenticar(self.banco, "fantasma", "qualquer1"))
        with self.assertRaises(autenticacao.BloqueadoError):
            autenticacao.autenticar(self.banco, "fantasma", "qualquer1")

    def test_consulta_de_notas(self):
        a1 = self.banco.alunos.insert_one({"nome": "Ana", "turma": "A"}).inserted_id
        a2 = self.banco.alunos.insert_one({"nome": "Beto", "turma": "B"}).inserted_id
        mat = self.banco.disciplinas.insert_one({"nome": "Mat"}).inserted_id
        self.banco.notas.insert_many([
            {"aluno_id": a1, "disciplina_id": mat, "semestre": 1, "avg": 8, "avi": 10, "avc": None},
            {"aluno_id": a2, "disciplina_id": mat, "semestre": 1, "avg": 5, "avi": 7, "avc": None},
            {"aluno_id": a2, "disciplina_id": mat, "semestre": 2, "avg": 4, "avi": None, "avc": None},
            {"aluno_id": a1, "disciplina_id": mat, "bimestre": 1, "nota": 3},  # legado: ignorado
        ])
        dados = calculos.notas_do_aluno(self.banco, a1)
        self.assertEqual(len(dados), 1)
        self.assertEqual(dados[0]["disciplina"], "Mat")


class TestUsuarios(unittest.TestCase):
    SENHA = "Senha1234"

    def setUp(self):
        import banco as modulo_banco
        self.banco = mongomock.MongoClient()["usuarios"]
        modulo_banco.criar_indices(self.banco)  # como o sistema faz ao conectar (índice único de usuário)
        autenticacao.criar_primeiro_admin(self.banco, "chefe", self.SENHA)

    def test_admin_tem_perfil_e_contas_antigas_sao_admin(self):
        admin = autenticacao.autenticar(self.banco, "chefe", self.SENHA)
        self.assertEqual(autenticacao.perfil_do(admin), autenticacao.PERFIL_ADMIN)
        self.assertEqual(autenticacao.perfil_do({"usuario": "antigo"}), autenticacao.PERFIL_ADMIN)

    def test_limite_de_tres_usuarios_alem_do_admin(self):
        for i, perfil in enumerate(("professor", "consulta", "professor"), start=1):
            autenticacao.criar_usuario(self.banco, f"user{i}", self.SENHA, perfil)
        self.assertEqual(autenticacao.contar_extras(self.banco), 3)
        with self.assertRaises(autenticacao.LimiteUsuariosError):
            autenticacao.criar_usuario(self.banco, "user4", self.SENHA, "consulta")
        self.assertEqual(self.banco.usuarios.count_documents({}), 4)  # 1 admin + 3
        # excluir um libera uma vaga
        self.assertTrue(autenticacao.excluir_usuario(self.banco, "user2"))
        autenticacao.criar_usuario(self.banco, "user4", self.SENHA, "consulta")

    def test_nao_cria_segundo_admin_nem_perfil_invalido(self):
        for perfil in ("administrador", "chefe", ""):
            with self.assertRaises(ValueError):
                autenticacao.criar_usuario(self.banco, "novo", self.SENHA, perfil)
        self.assertEqual(autenticacao.contar_extras(self.banco), 0)

    def test_validacoes_de_nome_senha_e_duplicado(self):
        with self.assertRaises(ValueError):
            autenticacao.criar_usuario(self.banco, "  ", self.SENHA, "professor")
        with self.assertRaises(ValueError):
            autenticacao.criar_usuario(self.banco, "fraco", "curta", "professor")
        autenticacao.criar_usuario(self.banco, "Maria", self.SENHA, "professor")
        with self.assertRaises(DuplicateKeyError):
            autenticacao.criar_usuario(self.banco, "maria", self.SENHA, "consulta")

    def test_login_devolve_o_perfil(self):
        autenticacao.criar_usuario(self.banco, "prof", self.SENHA, "professor")
        doc = autenticacao.autenticar(self.banco, "prof", self.SENHA)
        self.assertEqual(autenticacao.perfil_do(doc), "professor")

    def test_trocar_senha_e_excluir(self):
        autenticacao.criar_usuario(self.banco, "prof", self.SENHA, "professor")
        self.assertTrue(autenticacao.trocar_senha(self.banco, "prof", "Nova12345"))
        self.assertIsNone(autenticacao.autenticar(self.banco, "prof", self.SENHA))
        self.assertIsNotNone(autenticacao.autenticar(self.banco, "prof", "Nova12345"))
        with self.assertRaises(ValueError):
            autenticacao.trocar_senha(self.banco, "prof", "fraca")
        self.assertFalse(autenticacao.trocar_senha(self.banco, "fantasma", "Nova12345"))
        self.assertTrue(autenticacao.excluir_usuario(self.banco, "prof"))
        self.assertFalse(autenticacao.excluir_usuario(self.banco, "prof"))

    def test_administrador_nao_pode_ser_excluido(self):
        with self.assertRaises(PermissionError):
            autenticacao.excluir_usuario(self.banco, "chefe")
        self.assertIsNotNone(autenticacao.autenticar(self.banco, "chefe", self.SENHA))

    def test_listar_usuarios_sem_segredos_e_admin_primeiro(self):
        autenticacao.criar_usuario(self.banco, "ana", self.SENHA, "consulta")
        lista = autenticacao.listar_usuarios(self.banco)
        self.assertEqual([u["usuario"] for u in lista], ["chefe", "ana"])
        self.assertTrue(all("hash" not in u and "salt" not in u for u in lista))

    def test_permissoes_do_menu_do_terminal(self):
        import interface
        admin, prof, cons = "administrador", "professor", "consulta"
        for opcao in "1234567":
            self.assertTrue(interface.opcao_permitida(opcao, admin))
        for opcao in "123":  # só a secretaria edita
            self.assertFalse(interface.opcao_permitida(opcao, prof))
            self.assertFalse(interface.opcao_permitida(opcao, cons))
        for opcao in "4567":
            self.assertTrue(interface.opcao_permitida(opcao, prof))
            self.assertTrue(interface.opcao_permitida(opcao, cons))

    def test_rotulo_do_perfil(self):
        self.assertEqual(autenticacao.rotulo_perfil("administrador"), "Secretaria")
        self.assertEqual(autenticacao.rotulo_perfil("professor"), "Professor")


class TestDocencia(unittest.TestCase):
    """Cada disciplina tem no máximo um professor e cada professor, no máximo uma disciplina."""
    SENHA = "Senha1234"

    def setUp(self):
        import banco as modulo_banco
        self.banco = mongomock.MongoClient()["docencia"]
        modulo_banco.criar_indices(self.banco)
        autenticacao.criar_primeiro_admin(self.banco, "chefe", self.SENHA)
        autenticacao.criar_usuario(self.banco, "rafael", self.SENHA, "professor")
        autenticacao.criar_usuario(self.banco, "ana", self.SENHA, "professor")
        autenticacao.criar_usuario(self.banco, "leitor", self.SENHA, "consulta")
        self.edf = self.banco.disciplinas.insert_one(
            {"nome": "Educação Física", "codigo": "EDF", "carga_horaria": 40,
             "professor": "rafael"}).inserted_id
        self.mat = self.banco.disciplinas.insert_one(
            {"nome": "Matemática", "codigo": "MAT", "carga_horaria": 80}).inserted_id

    def test_rotulos(self):
        d = self.banco.disciplinas.find_one({"_id": self.edf})
        self.assertEqual(docencia.rotulo_disciplina(d), "EDF - Educação Física (Prof. Rafael)")
        self.assertEqual(docencia.texto_professor(d), "Prof. Rafael")
        sem = self.banco.disciplinas.find_one({"_id": self.mat})
        self.assertEqual(docencia.texto_professor(sem), "-")
        self.assertEqual(docencia.rotulo_disciplina(sem), "MAT - Matemática")

    def test_professor_ocupado_e_recusado(self):
        with self.assertRaises(docencia.ProfessorOcupadoError):
            docencia.validar_professor(self.banco, "rafael", self.mat)

    def test_mesma_disciplina_pode_manter_o_professor(self):
        docencia.validar_professor(self.banco, "rafael", self.edf)

    def test_professor_livre_e_vazio_sao_aceitos(self):
        docencia.validar_professor(self.banco, "ana", self.mat)
        docencia.validar_professor(self.banco, "", self.mat)

    def test_so_usuario_com_perfil_professor(self):
        for nome in ("leitor", "chefe", "naoexiste"):
            with self.assertRaises(ValueError):
                docencia.validar_professor(self.banco, nome, self.mat)

    def test_professores_livres(self):
        self.assertEqual(docencia.professores_livres(self.banco), ["ana"])
        self.assertEqual(sorted(docencia.professores_livres(self.banco, self.edf)),
                         ["ana", "rafael"])

    def test_indice_do_banco_barra_professor_repetido(self):
        with self.assertRaises(DuplicateKeyError):
            self.banco.disciplinas.insert_one(
                {"nome": "Artes", "codigo": "ART", "carga_horaria": 30, "professor": "rafael"})

    def test_varias_disciplinas_sem_professor(self):
        self.banco.disciplinas.insert_one({"nome": "Artes", "codigo": "ART", "carga_horaria": 30})
        self.banco.disciplinas.insert_one({"nome": "Inglês", "codigo": "ING", "carga_horaria": 30})

    def test_operacao_de_atualizacao(self):
        self.assertEqual(docencia.operacao_de_atualizacao({"nome": "X"}, "ana"),
                         {"$set": {"nome": "X", "professor": "ana"}})
        self.assertEqual(docencia.operacao_de_atualizacao({"nome": "X"}, ""),
                         {"$set": {"nome": "X"}, "$unset": {"professor": ""}})

    def test_excluir_usuario_libera_a_disciplina(self):
        autenticacao.excluir_usuario(self.banco, "rafael")
        d = self.banco.disciplinas.find_one({"_id": self.edf})
        self.assertNotIn("professor", d)

    def test_notas_do_aluno_traz_o_professor(self):
        aluno = self.banco.alunos.insert_one({"nome": "Ana", "matricula": "1"}).inserted_id
        self.banco.notas.insert_one({"aluno_id": aluno, "disciplina_id": self.edf,
                                     "semestre": 1, "avg": 8.0, "avi": None, "avc": 9.0})
        notas = calculos.notas_do_aluno(self.banco, aluno)
        self.assertEqual(notas[0]["professor"], "rafael")


class TestRisco(unittest.TestCase):
    @staticmethod
    def nota(disc, sem, avg, avi, avc=None):
        return {"disciplina": disc, "semestre": sem, "avg": avg, "avi": avi, "avc": avc}

    def test_sem_dados(self):
        self.assertEqual(risco.avaliar_aluno([])["nivel"], "sem dados")
        self.assertEqual(risco.avaliar_aluno([self.nota("Mat", 1, 5, None)])["nivel"], "sem dados")

    def test_aluno_estavel_tem_risco_baixo(self):
        r = risco.avaliar_aluno([self.nota("Mat", 1, 8, 9), self.nota("Mat", 2, 8, 8)])
        self.assertEqual((r["nivel"], r["pontos"]), ("baixo", 0))
        self.assertEqual(r["motivos"], ["Sem sinais de risco."])

    def test_aluno_em_queda_tem_risco_alto(self):
        dados = [self.nota("Mat", 1, 9, 9), self.nota("Port", 1, 9, 9),
                 self.nota("Mat", 2, 4, 4), self.nota("Port", 2, 4, 5)]
        r = risco.avaliar_aluno(dados)  # média geral 6.6; fracas: 2; queda 4.5
        self.assertEqual(r["nivel"], "alto")
        self.assertEqual(r["pontos"], 12 + 20 + 25)
        self.assertEqual(len(r["motivos"]), 3)

    def test_pontuacao_limitada_a_100_e_ordem(self):
        banco = mongomock.MongoClient()["risco"]
        bom = banco.alunos.insert_one({"nome": "Bom", "matricula": "1", "turma": "A"}).inserted_id
        mau = banco.alunos.insert_one({"nome": "Mau", "matricula": "2", "turma": "A"}).inserted_id
        banco.alunos.insert_one({"nome": "Novo", "matricula": "3", "turma": "A"})
        mat = banco.disciplinas.insert_one({"nome": "Mat"}).inserted_id
        banco.notas.insert_many([
            {"aluno_id": bom, "disciplina_id": mat, "semestre": 1, "avg": 9, "avi": 9},
            {"aluno_id": mau, "disciplina_id": mat, "semestre": 1, "avg": 3, "avi": 2},
        ])
        resultado = risco.avaliar_todos(banco)
        self.assertEqual([r["nome"] for r in resultado], ["Mau", "Bom", "Novo"])
        self.assertEqual(resultado[0]["nivel"], "alto")
        self.assertEqual(resultado[2]["nivel"], "sem dados")
        self.assertLessEqual(resultado[0]["pontos"], 100)


class FakeCliente:
    """Imita anthropic.Anthropic().messages.create sem chamar a API."""

    def __init__(self, resposta=None, erro=None):
        self.chamadas = []
        self.resposta, self.erro = resposta, erro
        self.messages = self

    def create(self, **kwargs):
        self.chamadas.append(kwargs)
        if self.erro:
            raise self.erro
        return self.resposta


class Resp:
    def __init__(self, texto="Resumo.", stop="end_turn"):
        self.stop_reason = stop
        self.content = [types.SimpleNamespace(type="thinking", thinking=""),
                        types.SimpleNamespace(type="text", text=texto)] if texto else []


class TestExplicador(unittest.TestCase):
    DADOS = [{"disciplina": "Mat", "semestre": 1, "avg": 9, "avi": 9, "avc": None},
             {"disciplina": "Mat", "semestre": 2, "avg": 4, "avi": 4, "avc": None}]

    def test_envia_so_dados_anonimos_e_devolve_texto(self):
        # como na tela: o dicionário completo do aluno, com dados que NÃO podem sair
        avaliacao = {**risco.avaliar_aluno(self.DADOS), "nome": "Fulano da Silva",
                     "matricula": "98765", "turma": "Turma Secreta", "aluno_id": "abc123"}
        fake = FakeCliente(Resp("Texto da IA."))
        self.assertEqual(explicador.explicar(avaliacao, self.DADOS, cliente=fake), "Texto da IA.")
        chamada = fake.chamadas[0]
        self.assertEqual(chamada["model"], "claude-opus-5-5")
        enviado = repr(chamada)
        for segredo in ("Fulano", "98765", "Turma Secreta", "abc123"):
            self.assertNotIn(segredo, enviado)
        self.assertIn("motivos_do_alerta", enviado)

    def test_erros_viram_explicador_erro(self):
        avaliacao = risco.avaliar_aluno(self.DADOS)
        with self.assertRaises(explicador.ExplicadorErro):
            explicador.explicar(avaliacao, self.DADOS, cliente=FakeCliente(Resp(stop="refusal")))
        with self.assertRaises(explicador.ExplicadorErro):
            explicador.explicar(avaliacao, self.DADOS, cliente=FakeCliente(Resp(texto="")))
        with self.assertRaises(explicador.ExplicadorErro):
            explicador.explicar(avaliacao, self.DADOS, cliente=FakeCliente(erro=TimeoutError("lento")))
        with self.assertRaises(explicador.ExplicadorErro):
            explicador.explicar(risco.avaliar_aluno([]), [], cliente=FakeCliente(Resp()))

    VARIAVEIS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "EXPLICADOR_PROVEDOR",
                 "GEMINI_BASE_URL", "GEMINI_MODELO")

    def setUp(self):
        self.guardadas = {v: os.environ.pop(v, None) for v in self.VARIAVEIS}

    def tearDown(self):
        for v in self.VARIAVEIS:
            os.environ.pop(v, None)
            if self.guardadas[v] is not None:
                os.environ[v] = self.guardadas[v]

    def test_sem_chave_pede_configuracao(self):
        self.assertFalse(explicador.disponivel())
        with self.assertRaises(explicador.ExplicadorErro):
            explicador.explicar(risco.avaliar_aluno(self.DADOS), self.DADOS)

    def test_chave_salva_em_arquivo(self):
        import tempfile
        from pathlib import Path
        from unittest import mock as _mock
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "chave_gemini.txt"
            with _mock.patch.object(explicador, "ARQUIVO_CHAVE", arquivo):
                self.assertFalse(explicador.carregar_chave_salva())        # sem arquivo: nada
                explicador.salvar_chave('  "chave-de-teste"  ')
                self.assertEqual(arquivo.read_text(encoding="utf-8"), "chave-de-teste")
                self.assertTrue(explicador.carregar_chave_salva())         # carrega para o ambiente
                self.assertEqual(os.environ["GEMINI_API_KEY"], "chave-de-teste")
                os.environ["GEMINI_API_KEY"] = "outra-do-ambiente"
                self.assertFalse(explicador.carregar_chave_salva())        # a do ambiente tem prioridade
                self.assertEqual(os.environ["GEMINI_API_KEY"], "outra-do-ambiente")
                self.assertTrue(explicador.esquecer_chave_salva())
                self.assertFalse(arquivo.exists())
                self.assertFalse(explicador.esquecer_chave_salva())

    def test_escolha_do_provedor(self):
        os.environ["ANTHROPIC_API_KEY"] = "a"
        self.assertEqual(explicador.provedor_ativo(), "claude")
        os.environ["GEMINI_API_KEY"] = "g"
        self.assertEqual(explicador.provedor_ativo(), "gemini")  # Gemini tem preferência
        os.environ["EXPLICADOR_PROVEDOR"] = "claude"
        self.assertEqual(explicador.provedor_ativo(), "claude")
        del os.environ["ANTHROPIC_API_KEY"]
        self.assertIsNone(explicador.provedor_ativo())  # forçou claude, mas sem chave

    def servidor_gemini(self, status=200, resposta=None):
        """Sobe um servidor HTTP local que imita o generateContent e guarda o que recebeu."""
        recebido = {}

        class Manipulador(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                recebido["caminho"] = self.path
                recebido["chave"] = self.headers.get("x-goog-api-key")
                recebido["corpo"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(resposta).encode())

        servidor = HTTPServer(("127.0.0.1", 0), Manipulador)
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        self.addCleanup(servidor.shutdown)
        os.environ["GEMINI_API_KEY"] = "chave-de-teste"
        os.environ["GEMINI_BASE_URL"] = f"http://127.0.0.1:{servidor.server_port}/v1beta"
        return recebido

    def test_gemini_envia_so_dados_anonimos_e_le_a_resposta(self):
        recebido = self.servidor_gemini(resposta={"candidates": [{"content": {"parts": [
            {"text": "pensando...", "thought": True}, {"text": "Texto do Gemini."}]},
            "finishReason": "STOP"}]})
        avaliacao = {**risco.avaliar_aluno(self.DADOS), "nome": "Fulano da Silva",
                     "matricula": "98765", "turma": "Turma Secreta", "aluno_id": "abc123"}
        self.assertEqual(explicador.explicar(avaliacao, self.DADOS), "Texto do Gemini.")
        self.assertEqual(recebido["caminho"], "/v1beta/models/gemini-3.8-flash:generateContent")
        self.assertEqual(recebido["chave"], "chave-de-teste")  # chave no cabeçalho, não na URL
        enviado = json.dumps(recebido["corpo"], ensure_ascii=False)
        for segredo in ("Fulano", "98765", "Turma Secreta", "abc123"):
            self.assertNotIn(segredo, enviado)
        self.assertIn("motivos_do_alerta", enviado)
        self.assertIn("systemInstruction", recebido["corpo"])

    def test_gemini_troca_de_modelo_quando_sobrecarregado(self):
        modelos_usados = []

        class Manipulador(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                modelos_usados.append(self.path.split("/models/")[1].split(":")[0])
                if len(modelos_usados) == 1:  # o modelo padrão está sobrecarregado
                    status, corpo = 503, {"error": {"message": "high demand"}}
                else:
                    status, corpo = 200, {"candidates": [{"content": {"parts": [{"text": "Veio do reserva."}]}}]}
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(corpo).encode())

        servidor = HTTPServer(("127.0.0.1", 0), Manipulador)
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        self.addCleanup(servidor.shutdown)
        os.environ["GEMINI_API_KEY"] = "k"
        os.environ["GEMINI_BASE_URL"] = f"http://127.0.0.1:{servidor.server_port}/v1beta"
        avaliacao = risco.avaliar_aluno(self.DADOS)
        self.assertEqual(explicador.explicar(avaliacao, self.DADOS), "Veio do reserva.")
        self.assertEqual(modelos_usados, ["gemini-3.8-flash", "gemini-3.5-flash-lite"])

        # com GEMINI_MODELO definido, não há reserva: o erro aparece
        modelos_usados.clear()
        os.environ["GEMINI_MODELO"] = "meu-modelo"
        with self.assertRaisesRegex(explicador.ExplicadorErro, "503"):
            explicador.explicar(avaliacao, self.DADOS)
        self.assertEqual(modelos_usados, ["meu-modelo"])

    def test_gemini_erros_viram_explicador_erro(self):
        avaliacao = risco.avaliar_aluno(self.DADOS)
        self.servidor_gemini(status=400, resposta={"error": {"message": "API key not valid."}})
        with self.assertRaisesRegex(explicador.ExplicadorErro, "400.*API key not valid"):
            explicador.explicar(avaliacao, self.DADOS)
        self.servidor_gemini(resposta={"promptFeedback": {"blockReason": "SAFETY"}})
        with self.assertRaisesRegex(explicador.ExplicadorErro, "bloqueou"):
            explicador.explicar(avaliacao, self.DADOS)
        self.servidor_gemini(resposta={"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": []}}]})
        with self.assertRaisesRegex(explicador.ExplicadorErro, "MAX_TOKENS"):
            explicador.explicar(avaliacao, self.DADOS)
        os.environ["GEMINI_BASE_URL"] = "http://127.0.0.1:1/v1beta"  # porta fechada
        with self.assertRaisesRegex(explicador.ExplicadorErro, "conexão"):
            explicador.explicar(avaliacao, self.DADOS)


if __name__ == "__main__":
    unittest.main()
