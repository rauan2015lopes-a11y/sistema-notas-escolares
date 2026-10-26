# Sistema de Notas Escolares — Documentação

> Versão da documentação: reflete o código com **alerta de risco** e **resumo por IA** incluídos.
> Seção 12 informa o que foi e o que **não** foi verificado.

## Sumário
1. [Visão geral](#1-visão-geral)
2. [Arquitetura](#2-arquitetura)
3. [Estrutura de arquivos](#3-estrutura-de-arquivos)
4. [Modelo de dados](#4-modelo-de-dados-mongodb)
5. [Regras de negócio](#5-regras-de-negócio)
6. [Autenticação e segurança](#6-autenticação-e-segurança)
7. [Interface gráfica](#7-interface-gráfica-telapy)
8. [Interface de terminal](#8-interface-de-terminal)
9. [Instalação e execução](#9-instalação-e-execução)
10. [Configuração (variáveis de ambiente)](#10-configuração-variáveis-de-ambiente)
11. [Testes](#11-testes)
12. [Estado da verificação](#12-estado-da-verificação)
13. [Limitações conhecidas](#13-limitações-conhecidas)
14. [Ideias de evolução](#14-ideias-de-evolução)
15. [Solução de problemas](#15-solução-de-problemas)
16. [Glossário](#16-glossário)

---

## 1. Visão geral

Sistema para uma escola/curso de **2 anos (4 semestres)** em que a **secretaria** (acesso total) edita os dados e professores e consulta apenas visualizam:

- cadastrar, editar e excluir **alunos** e **disciplinas**;
- lançar **notas por aluno + disciplina + semestre**, em três provas (AVG, AVI e AVC);
- consultar o **relatório do aluno** (notas, boletim por semestre, média geral e **gráfico de médias** numa só aba);
- vincular cada **disciplina a um professor** (um professor leciona no máximo uma disciplina);
- ver um **alerta precoce de risco acadêmico**, com os motivos explicados;
- (opcional) pedir a uma **IA generativa (Gemini ou Claude)** um resumo em linguagem natural desse alerta.

Tecnologias: **Python 3.10+**, **MongoDB Atlas** (`pymongo`), **Tkinter** (janelas), **Matplotlib**
(gráficos), **colorama** e **tabulate** (terminal) e, opcionalmente, a API do **Gemini** (sem pacote extra) ou o SDK **`anthropic`** (Claude).

Há **duas interfaces sobre o mesmo banco e as mesmas regras**:

| Interface | Como abrir | Para quem |
|---|---|---|
| Gráfica (janelas) | `python tela.py` | Uso do dia a dia |
| Terminal (menu de texto) | `python main.py` | Uso rápido, servidores, scripts |

---

## 2. Arquitetura

```
              ┌──────────────┐          ┌──────────────┐
              │   tela.py    │          │   main.py    │
              │ (Tkinter GUI)│          │  (terminal)  │
              └──────┬───────┘          └──────┬───────┘
                     │                         │ interface.py, cadastros.py, notas.py,
                     │                         │ consultas.py, relatorios.py, entrada.py
                     ▼                         ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ Regras compartilhadas (sem interface)                       │
   │  calculos.py     médias e boletim                            │
   │  risco.py        alerta de risco (determinístico)           │
   │  explicador.py   resumo por IA (opcional, dados anônimos) ──┼──► Gemini ou Claude
   │  autenticacao.py login, senha, bloqueio                     │
   │  graficos.py     gráfico de médias                          │
   └───────────────────────────────┬─────────────────────────────┘
                                   ▼
                        banco.py + config.py
                                   ▼
                       MongoDB Atlas (escola_bigdata)
```

Princípio: **as regras ficam fora das interfaces**. Tela e terminal só leem dados e exibem
resultados; qualquer cálculo vive em `calculos.py`/`risco.py`. Assim as duas interfaces nunca
divergem e as regras são testáveis sem abrir janela nem conectar a um banco real.

A IA **não** participa dos cálculos: ela só redige texto a partir de um resultado que
`risco.py` já calculou.

---

## 3. Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `config.py` | Nome do banco (`escola_bigdata`) e leitura de `MONGODB_URI` |
| `banco.py` | Conexão com o Atlas (com `ping`) e criação dos índices |
| `docencia.py` | Vínculo professor↔disciplina: rótulos ("Prof. Rafael") e regra de um professor por disciplina |
| `calculos.py` | `SEMESTRES`, `PROVAS`, média, boletim, médias por disciplina, consulta das notas do aluno |
| `risco.py` | Alerta precoce de risco acadêmico |
| `explicador.py` | Resumo do alerta em linguagem natural via Gemini ou Claude (opcional, dados anônimos) |
| `autenticacao.py` | Hash e política de senha, login, bloqueio por tentativas, 1º administrador |
| `graficos.py` | Gráfico de barras das médias por disciplina |
| `tela.py` | Interface gráfica (login + 8 abas) |
| `main.py` | Ponto de entrada do terminal |
| `interface.py` | Login e menu do terminal |
| `cadastros.py` | Cadastro e busca de alunos/disciplinas (terminal) |
| `notas.py` | Lançamento/edição de notas (terminal) |
| `consultas.py` | Listagem de alunos (terminal) |
| `relatorios.py` | Relatório do aluno, alerta de risco e resumo por IA (terminal) |
| `entrada.py` | Leitura validada de inteiros (terminal) |
| `demo.py` | Abre a tela com um banco de demonstração em memória (precisa de `mongomock`) |
| `testar_chave.py` | Testa a chave do Gemini direto no Google (sem abrir o sistema) |
| `rodar_demo.ps1` | Atalho que abre `demo.py` |
| `tests/test_sistema.py` | 41 testes automáticos |
| `requirements.txt` | Dependências |
| `README.md` | Guia rápido |
| `DOCUMENTACAO.md` | Este documento |

---

## 4. Modelo de dados (MongoDB)

Banco **`escola_bigdata`**, cinco coleções.

### `alunos`
```json
{ "_id": ObjectId, "nome": "Ana Souza", "matricula": "1001", "turma": "Turma A", "data_cadastro": ISODate }
```
Índice **único** em `matricula`.

### `disciplinas`
```json
{ "_id": ObjectId, "nome": "Educação Física", "codigo": "EDF", "carga_horaria": 40, "professor": "rafael" }
```
Índice **único** em `codigo`. `professor` é o nome de usuário (perfil professor); o campo **não existe** quando
não há professor. Índice **único parcial** em `professor`: o banco recusa o mesmo professor em duas disciplinas.

### `notas`
Um documento por **aluno + disciplina + semestre**:
```json
{ "_id": ObjectId, "aluno_id": ObjectId, "disciplina_id": ObjectId, "semestre": 2,
  "avg": 8.0, "avi": null, "avc": 9.0, "data_lancamento": ISODate }
```
- `avg`, `avi`, `avc` são as provas (0 a 10); `null` = não lançada.
- Índice **único parcial** em `(aluno_id, disciplina_id, semestre)`, válido quando `semestre`
  existe: impede duas linhas para o mesmo aluno/disciplina/semestre.
- Índices simples em `aluno_id` e `disciplina_id`.
- Documentos antigos do modelo por bimestre (campo `nota`, sem `semestre`) **são ignorados**
  por todas as consultas. O índice antigo `aluno_id_1_disciplina_id_1_bimestre_1` é removido
  automaticamente ao conectar.

### `usuarios`
```json
{ "_id": ObjectId, "usuario": "admin", "perfil": "administrador", "salt": "<hex>", "hash": "<hex>", "data_cadastro": ISODate }
```
Índice **único** em `usuario`. A senha **nunca** é guardada, só `salt` e `hash`. O campo `perfil` vale
`administrador`, `professor` ou `consulta`; contas antigas, sem o campo, são tratadas como administrador.

### `tentativas_login`
```json
{ "_id": "admin", "falhas": 3, "bloqueado_ate": ISODate, "atualizado_em": ISODate }
```
O `_id` é o nome de usuário. Índice **TTL** em `atualizado_em` (expira em 1 dia).

Datas são gravadas em **UTC**.

---

## 5. Regras de negócio

### 5.1 Notas
- Cada prova vale de 0 a 10; a vírgula é aceita como decimal; o valor é arredondado para 2
  casas. Texto vazio = prova não lançada. `NaN`, `inf` e valores fora da faixa são rejeitados.
- Para lançar é preciso informar **pelo menos uma** prova.
- Lançar de novo para o mesmo aluno/disciplina/semestre **atualiza** o registro (*upsert*).

### 5.2 Médias
| Média | Fórmula |
|---|---|
| **Disciplina** (em um semestre) | soma das **duas maiores** notas entre AVG, AVI e AVC, dividida por 2. Exige ao menos 2 notas; senão é "sem média" (`-`) |
| **Semestre** | média simples das médias das disciplinas que têm média |
| **Geral** | média simples das médias dos semestres que têm média |
| **Disciplina no gráfico** | média das médias da disciplina ao longo dos semestres |

Exemplos: AVG 8, AVI 10, AVC vazia → (10 + 8) / 2 = **9,00**.
AVG 4, AVI 8, AVC 10 → (10 + 8) / 2 = **9,00** (a menor é descartada).

### 5.3 Alerta de risco acadêmico (`risco.py`)
Modelo **estatístico explicável**: cada sinal soma pontos e gera uma frase de motivo; a
pontuação (limitada a 100) define o nível.

| Sinal | Pontos |
|---|---|
| Média geral < 5 | +45 |
| Média geral < 6 | +30 |
| Média geral < 7 | +12 |
| Disciplinas com média < 6 na última avaliação | +10 por disciplina (máx. 30) |
| Queda ≥ 1 ponto entre os dois últimos semestres com média | +15 |
| Queda ≥ 2 pontos entre os dois últimos semestres com média | +25 |
| Disciplinas com menos de 2 provas (sem média) | +5 por disciplina (máx. 10) |

Níveis: **baixo** (< 25), **médio** (25 a 49), **alto** (≥ 50). Aluno sem nenhuma média
calculável aparece como **sem dados**. A lista sai ordenada do maior para o menor risco.

> **Limite importante:** isso **não é aprendizado de máquina treinado**. O banco não guarda
> aprovação/reprovação, então não há como treinar um modelo. Os pesos são julgamento definido
> no projeto, não resultado estatístico. É apoio à decisão, não veredito. Com histórico de
> desfechos, as regras podem ser trocadas por um modelo treinado mantendo a mesma saída
> (`nivel`, `pontos`, `media`, `motivos`).

### 5.4 Resumo por IA generativa (`explicador.py`) — opcional

Transforma o resultado do alerta em texto: um parágrafo em português (3 a 5 frases) e 2 ou 3
sugestões práticas de acompanhamento, escritos por uma IA generativa. Há dois provedores:

| | **Gemini (Google)** | **Claude (Anthropic)** |
|---|---|---|
| Chave | `GEMINI_API_KEY` (ou `GOOGLE_API_KEY`), **gratuita** em aistudio.google.com/apikey | `ANTHROPIC_API_KEY`, **paga** (créditos no Console) |
| Instalação | nada extra (HTTP direto, biblioteca padrão do Python) | `pip install anthropic` |
| Modelo padrão | `gemini-3.8-flash` (`GEMINI_MODELO`) | `claude-opus-5-5` (`CLAUDE_MODELO`) |
| Chamada | `POST .../v1beta/models/<modelo>:generateContent`, chave no cabeçalho `x-goog-api-key` | SDK oficial, `output_config.effort="low"` |
| Limite de saída | `maxOutputTokens=4000` (inclui o "raciocínio" do modelo) | `max_tokens=4000` |

**Modelo reserva (Gemini):** se o modelo padrão responder 503 (sobrecarga), 429 (limite), 404
ou 5xx, o sistema tenta automaticamente `gemini-3.5-flash-lite` e depois `gemini-flash-latest`.
Com `GEMINI_MODELO` definido, usa só esse modelo, sem reserva. Erros de chave (400/401/403)
não trocam de modelo, porque o problema não é o modelo.

Chaves do Gemini podem começar com `AIza` ou `AQ.`; ambas funcionam (verificado com uma chave
`AQ.` de 53 caracteres, aceita pelo Google na listagem de modelos).

Escolha automática: com `GEMINI_API_KEY` usa o Gemini; senão, com `ANTHROPIC_API_KEY`, usa o
Claude. `EXPLICADOR_PROVEDOR=claude` ou `gemini` força um (e fica indisponível se faltar a
chave dele). Nos dois, o prompt de sistema é o mesmo e o tempo limite é de 90 s.

**Onde usar:** aba **Relatório do aluno** (botão *Resumo por IA*, para o aluno escolhido) ou aba
**Alerta de risco** (botão *Explicar com IA*). Nas duas, a IA só **redige** o texto: nível,
pontos e motivos vêm sempre das regras de `risco.py`, então a IA não decide o risco nem faz
contas. Aluno sem médias não aciona a IA. A chamada roda em segundo plano, sem travar a janela.

> **Atenção (Gemini gratuito):** segundo a página de preços do Google, no plano gratuito o
> conteúdo enviado **pode ser usado para melhorar os produtos do Google**; no plano pago, não.
> Mesmo anonimizado, **use o plano gratuito só com dados fictícios ou de demonstração**. Para
> dados reais de alunos, use um plano pago (Gemini ou Claude) ou não ative a IA.

| Item | Detalhe |
|---|---|
| O que é enviado | JSON **anônimo**: média geral, nível e pontuação de risco, motivos do alerta, médias por semestre e disciplina |
| O que **não** é enviado | nome, matrícula, turma e identificadores do aluno |
| Regras no prompt | usar só os números recebidos; não inventar fatos; não diagnosticar causas pessoais; não citar nomes; lembrar que o alerta é apoio à decisão |
| Saída | texto + aviso "gerado por IA, confira antes de usar" |
| Falhas | sem chave, pacote ausente, erro de rede/autenticação/limite, recusa do modelo ou resposta vazia viram uma mensagem (`ExplicadorErro`); o programa não cai |
| Custo | Gemini: gratuito dentro dos limites do plano (com a ressalva de privacidade acima). Claude: cada resumo é uma chamada paga (estimativa não medida: ~US$ 0,02 a 0,04) |

O nome do aluno aparece no texto exibido apenas porque a **própria tela** o escreve
localmente, depois de receber a resposta.

> **Privacidade:** mesmo anonimizados, os dados saem da máquina para um serviço externo.
> Confira a política da escola e a LGPD (alunos podem ser menores) antes de usar com dados
> reais. Sem nenhuma chave configurada, nada é enviado.

---

## 6. Autenticação e segurança

- **Senhas:** PBKDF2-HMAC-SHA256, 200.000 iterações, salt aleatório de 16 bytes, comparação em
  tempo constante (`hmac.compare_digest`).
- **Política:** mínimo 8 caracteres, com letras **e** números.
- **Usuário inexistente:** gasta o mesmo tempo de um hash, para não revelar quais usuários existem.
- **Bloqueio por tentativas:** 5 falhas seguidas bloqueiam o usuário por **5 minutos**. O
  contador fica no banco, então reabrir o programa **não** zera a contagem. Usuários
  inexistentes também são contados. Um login correto apaga o registro.
  Efeito colateral aceito: alguém pode travar o admin por 5 minutos errando de propósito.
- **Primeiro acesso:** enquanto não há administrador, a tela pede para criar um. Depois que
  existe, `criar_primeiro_admin` recusa (`PermissionError`). Se `ADMIN_SETUP_CODE` estiver
  definida, esse código é exigido nessa criação, impedindo que outra pessoa crie o admin
  antes de você.
- **Segredos:** `MONGODB_URI`, `GEMINI_API_KEY` e `ANTHROPIC_API_KEY` vêm só de variáveis de ambiente; nada é
  gravado no código.
- **Perfis e limite de usuários:** há **um único administrador** (criado no primeiro acesso, não pode
  ser excluído) e **no máximo 3 outros usuários**, criados só por ele na aba *Usuários*. O limite é
  garantido no código (`autenticacao.criar_usuario` lança `LimiteUsuariosError` no 4º), e não só
  escondido na tela. Excluir um usuário libera uma vaga.

  | Perfil | Pode | Não pode |
  |---|---|---|
  | **Secretaria** (`administrador`) | **Único perfil que edita**: alunos, disciplinas (com professor), notas e usuários | Ser excluída |
  | **Professor** | **Somente visualizar** (alunos, disciplinas com professor, relatório do aluno, risco, resumo por IA) | Qualquer alteração: cadastros, notas, usuários (botões de edição nem aparecem) |
  | **Consulta** | Apenas **visualizar** (mesmas telas do professor) | Qualquer alteração |

  As permissões valem na **tela** (abas escondidas e botões desativados, com trava também dentro de
  cada ação) e no **terminal** (o menu só mostra as opções do perfil). O cabeçalho mostra o perfil
  (ex.: "Professor: rafael | Disciplina: Educação Física | Somente visualização").

---

## 7. Interface gráfica (`tela.py`)

Ao abrir: **Login** (ou criação da conta da secretaria). Depois, a janela principal, com o
botão **Sair** (volta ao login) e as abas:

| Aba | O que faz |
|---|---|
| **Alunos** | Formulário (nome, matrícula, turma) e tabela **agrupada por turma** (cada turma é um grupo que abre e fecha, com a contagem de alunos). **Filtro por turma** e **busca por nome ou matrícula** (sem diferenciar maiúsculas); *Limpar filtros* volta ao normal. Clicar num aluno preenche o formulário. Botões: Cadastrar, Salvar alterações, Excluir, Limpar |
| **Disciplinas** | Nome, código, carga horária e **Professor** (lista só com professores livres); a tabela mostra o professor de cada disciplina. Escolher um professor que já leciona outra matéria é recusado. Para professor/consulta, só a tabela aparece |
| **Lançar notas** (só secretaria) | Escolhe aluno, disciplina e semestre; digita AVG/AVI/AVC; mostra a **média prévia** enquanto digita e carrega notas já existentes para edição; tabela com as notas do aluno |
| **Relatório do aluno** | Aba única (antigos *Relatório* + *Boletim*): árvore por semestre (1º ao 4º) com disciplina, professor, AVG/AVI/AVC e média, média de cada semestre e **média geral**; **Ver gráfico** abre as médias por disciplina; **Resumo por IA** escreve um resumo do aluno e, enquanto a IA responde, mostra uma **barra de carregamento** com os segundos decorridos (a tela não parece travada) |
| **Usuários** (só secretaria) | Tabela de usuários (usuário, perfil, disciplina, criado em) e contador "Usuários além da secretaria: N de 3". Formulário para **criar** (usuário, senha, perfil professor ou consulta), **trocar a senha** do selecionado e **excluir** o selecionado. O botão de criar se desativa ao chegar a 3; o administrador não pode ser excluído |
| **Alerta de risco** | Filtro por **turma** (o resumo do topo conta só a turma escolhida). Todos os alunos por nível (vermelho/amarelo/verde), com média, pontos e motivos; resumo no topo; botão **Explicar com IA** e caixa de texto com o resumo do aluno selecionado |

Comportamentos que valem saber:
- **Excluir aluno ou disciplina apaga também as notas ligadas a ele**, após confirmação que
  informa quantas notas serão removidas. Não há desfazer.
- Matrícula ou código repetidos são recusados (índice único).
- Erros de banco aparecem em caixa de diálogo, sem fechar o programa.
- Alunos e disciplinas são recarregados após cada alteração, não a cada troca de aba; só
  o Alerta de risco atualiza ao abrir a aba.
- **Explicar com IA** roda em segundo plano (a janela não trava), desativa o botão durante a
  chamada e mostra o erro na própria caixa de texto se algo falhar. Sem nenhuma chave de IA,
  mostra uma orientação de configuração.

---

## 8. Interface de terminal

`python main.py` → login com senha oculta (`getpass`; 3 tentativas por execução, além do
bloqueio persistente) → menu:

```
1 - Cadastrar aluno                  5 - Relatório de aluno
2 - Cadastrar disciplina             6 - Alerta de risco acadêmico
3 - Lançar ou editar notas           7 - Explicar risco de um aluno com IA
4 - Listar alunos
0 - Sair
```

- Alunos e disciplinas são localizados por **matrícula** e **código**.
- Ao relançar notas, **Enter mantém** o valor atual da prova e **`-` apaga** a nota.
- O relatório do aluno imprime o boletim por semestre, a média geral e as médias por
  disciplina, e abre o gráfico em uma janela do Matplotlib.
- O terminal **não** edita nem exclui alunos/disciplinas (só a tela faz isso).

---

## 9. Instalação e execução

Requisitos: Python 3.10+ e um cluster MongoDB Atlas (ou MongoDB compatível).

```bash
pip install -r requirements.txt
```

Defina a conexão (PowerShell):

```bash
$env:MONGODB_URI = "mongodb+srv://USUARIO:SENHA@SEU-CLUSTER.mongodb.net/"
```

Para guardar de forma permanente: `setx MONGODB_URI "..."` (vale para novos terminais).
Caracteres especiais na senha precisam ser codificados na URI (`@` vira `%40`). No Atlas,
libere o seu IP em **Network Access**.

Executar:

```bash
python tela.py      # interface gráfica
python main.py      # terminal
```

**Resumo por IA (opcional):**

Opção gratuita (Gemini, sem instalar nada): crie uma chave em aistudio.google.com/apikey (veja
o aviso de privacidade na seção 5.4). Há duas formas de informá-la:

- **Pelo botão "Chave de IA..." (recomendado):** nas abas *Relatório do aluno* e *Alerta de
  risco*. Abre uma janela onde a chave é colada com Ctrl+V (campo mascarado, com opção de
  mostrar). Por padrão a chave fica **só na memória** e some ao fechar o programa. Marcando
  **"Lembrar nesta máquina"**, ela é gravada em `chave_gemini.txt` (texto simples, só neste
  computador, fora do zip distribuído) e carregada sozinha nas próximas vezes; o botão
  **"Esquecer chave"** apaga o arquivo. A janela mostra só provedor, tamanho e as 3 primeiras
  letras da chave em uso. Se você clicar em *Resumo por IA* sem chave, o sistema oferece abrir
  essa janela.
- **Por variável de ambiente**, no mesmo terminal em que vai rodar o sistema:

```bash
$env:GEMINI_API_KEY = "sua-chave-do-gemini"
```

Para **testar a chave** sem abrir o sistema: `python testar_chave.py` (pede a chave oculta;
mostra só o tamanho e as 3 primeiras letras; confere se o Google aceita a chave e se o modelo
responde).

> Evite ler a chave com `SecureString`/`PtrToStringBSTR` no PowerShell: antivírus podem
> bloquear esse padrão como "conteúdo mal-intencionado" (aconteceu na máquina do autor).

Opção paga (Claude):

```bash
pip install anthropic
$env:ANTHROPIC_API_KEY = "sua-chave"
```

**Demonstração sem banco real:** `pip install mongomock` e `python demo.py` abre o sistema com 6
alunos (um sem notas), 3 disciplinas e notas de exemplo (inclui uma aluna em queda para o
alerta). Passa pela **tela de login**: como o banco da demo começa sem usuários, no primeiro
acesso você mesmo cria o administrador (usuário e senha de sua escolha, mínimo 8 caracteres
com letras e números); o botão *Sair* volta ao login. Os dados e o usuário somem ao fechar.

---

## 10. Configuração (variáveis de ambiente)

| Variável | Obrigatória | Função |
|---|---|---|
| `MONGODB_URI` | Sim | String de conexão do MongoDB |
| `ADMIN_SETUP_CODE` | Não | Código exigido para criar o primeiro administrador |
| `GEMINI_API_KEY` (ou `GOOGLE_API_KEY`) | Não | Chave do Gemini para o resumo por IA (gratuita; seção 5.4) |
| `ANTHROPIC_API_KEY` | Não | Chave do Claude para o resumo por IA (paga; seção 5.4) |
| `EXPLICADOR_PROVEDOR` | Não | `gemini` ou `claude`, para forçar um provedor |
| `GEMINI_MODELO` | Não | Modelo do Gemini (padrão `gemini-3.8-flash`) |
| `GEMINI_BASE_URL` | Não | URL base da API do Gemini (uso em testes) |
| `CLAUDE_MODELO` | Não | Modelo do resumo por IA (padrão `claude-opus-5-5`) |

---

## 11. Testes

```bash
pip install mongomock
python -m unittest discover tests -v
```

41 testes, usando `mongomock` (sem tocar no Atlas), um cliente do Claude falso e um servidor HTTP
local que imita o Gemini (sem chamar nenhuma API real):

- **Cálculos:** leitura de notas (vírgula, limites, NaN/inf), média das duas maiores, boletim,
  médias por disciplina.
- **Banco:** consulta de notas (ignorando documentos legados).
- **Autenticação:** política de senha, primeiro admin só uma vez, login, bloqueio e liberação
  após o prazo, bloqueio de usuário inexistente.
- **Risco:** sem dados, aluno estável, aluno em queda, ordenação e limite de 100 pontos.
- **Resumo por IA:** o conteúdo enviado (Claude e Gemini) não contém nome, matrícula, turma nem
  id do aluno; escolha do provedor por variáveis de ambiente; no Gemini, caminho, cabeçalho de
  chave, partes de "raciocínio" ignoradas; recusa, bloqueio, resposta vazia, erro HTTP, falha
  de conexão, aluno sem dados e falta de chave viram `ExplicadorErro`.

---

## 12. Estado da verificação

| Item | Situação |
|---|---|
| Testes automáticos (41) | Escritos; rodar `python -m unittest discover tests` |
| Chave do Gemini real (`AQ.`, 53 caracteres) na máquina do autor | **Aceita** pelo Google. O modelo padrão respondeu 503 (sobrecarga) e o reserva `gemini-3.5-flash-lite` respondeu. O **resumo por IA de ponta a ponta funcionou** na tela (resumo em português com média, notas por disciplina, risco e sugestões, confirmado em captura de tela do autor) |
| Interface gráfica (cadastro, edição, exclusão, notas, relatório, boletim, gráfico, alerta de risco, botão de IA) | Exercitada contra um banco **simulado** (`mongomock`) |
| Terminal (cadastro, notas com edição, relatório, login e primeiro acesso) | Exercitado com entradas simuladas |
| Resumo por IA com o **SDK `anthropic` real** (v1.13) apontado para um servidor HTTP **local** que imita a API | **Verificado**: a requisição vai a `/v1/messages` com o modelo, `effort: low` e prompt de sistema corretos, sem dados do aluno; a resposta é lida; um erro 401 vira mensagem amigável |
| Resumo por IA via **Gemini**, contra um servidor HTTP **local** que imita o `generateContent` | **Verificado** nos testes: caminho e cabeçalho `x-goog-api-key` corretos, nenhum dado do aluno no corpo, partes de "raciocínio" ignoradas, erro HTTP, bloqueio, resposta vazia e falha de conexão viram mensagem |
| Conexão com o **MongoDB Atlas real** | **Não testada** (sem credenciais neste ambiente) |
| Chamada à **API real do Gemini ou da Anthropic** (qualidade do texto, limites, nome exato do modelo na sua conta) | **Não testada** (sem chave neste ambiente). O formato do Gemini foi conferido na documentação oficial do Google, mas nunca executado contra o serviço real |

---

## 13. Limitações conhecidas

- Atlas real, Gemini real e Claude real nunca foram exercitados (seção 12).
- No plano gratuito do Gemini, o conteúdo enviado pode ser usado pelo Google; sem plano pago,
  a IA só deve ser usada com dados fictícios.
- Um único administrador (sem recuperação de senha se ele a esquecer, a não ser mexendo direto no
  banco) e no máximo 3 outros usuários; o professor lança notas de qualquer turma; o gerenciamento de
  usuários só existe na tela, não no terminal.
- Sem edição/exclusão de alunos e disciplinas no terminal.
- Sem exportação (PDF/Excel) de boletins.
- Sem registro de aprovação/reprovação, o que impede treinar um modelo de risco real.
- Os pesos do alerta de risco são julgamento do projeto, não calibrados com dados.
- O resumo por IA não tem fallback automático para outro modelo; se o modelo recusar, a tela
  informa a recusa.
- Notas do antigo modelo por bimestre continuam no banco, mas o sistema não as lê.
- O bloqueio é por usuário: terceiros podem travar o admin por 5 minutos.
- O índice único de notas é parcial; documentos sem `semestre` escapam da proteção contra
  duplicatas (por isso ficam ignorados).

---

## 14. Ideias de evolução

- Modelo de risco **treinado** (regressão logística ou árvore) quando houver histórico de
  desfechos, mantendo a explicação por motivos e o resumo por IA.
- Versão web (FastAPI + front-end) para acesso por qualquer dispositivo.
- Troca do PBKDF2 por **Argon2**, ou login com passkeys (WebAuthn).
- Exportação de boletim em PDF e planilha.
- Perfis de usuário (secretaria, professor, coordenação) e tela de gestão de usuários.
- Frequência/faltas como novo sinal de risco.
- Script de migração das notas por bimestre para semestre, se houver dados reais antigos.

---

## 15. Solução de problemas

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| "Defina a variável de ambiente MONGODB_URI" | Variável não definida na janela atual | Defina com `$env:MONGODB_URI=...` e rode de novo |
| Erro de conexão / timeout ao abrir | IP não liberado no Atlas, ou senha com caracteres especiais sem codificar | Libere o IP em Network Access; codifique `@`, `:`, `/` na senha |
| "Muitas tentativas inválidas" | 5 senhas erradas seguidas | Aguarde 5 minutos |
| Botão "Explicar com IA" só mostra orientação | Nenhuma chave de IA definida **neste terminal** | Defina `GEMINI_API_KEY` (ou `ANTHROPIC_API_KEY`) no mesmo terminal e **reabra** o programa |
| "Falha ao consultar o Gemini (HTTP 400/403)" | Chave inválida, ou sem permissão | Gere outra em aistudio.google.com/apikey e confira se não é o texto de exemplo |
| "Falha ao consultar o Gemini (HTTP 404)" | Nome do modelo não existe na sua conta | Defina `GEMINI_MODELO` com um modelo da lista em ai.google.dev/gemini-api/docs/models |
| "Falha ao consultar o Gemini (… HTTP 503)" | Modelo sobrecarregado no Google (temporário) | O sistema já tenta os modelos reserva; se todos falharem, tente de novo em alguns minutos |
| "Falha ao consultar o Gemini (… HTTP 429)" | Limite do plano gratuito atingido | Espere alguns minutos |
| "Este script contém conteúdo mal-intencionado" ao ler a chave no PowerShell | O antivírus bloqueia o truque de `SecureString` | Use `python testar_chave.py` ou `python demo.py`, que leem a chave com `getpass` |
| "O Gemini não devolveu texto (motivo: MAX_TOKENS)" | Resposta cortada | Tente de novo; se repetir, troque `GEMINI_MODELO` |
| "Falha ao consultar a IA (AuthenticationError)" | Chave inválida | Confira a chave |
| "Falha ao consultar a IA (RateLimitError)" | Limite de uso atingido | Tente de novo mais tarde |
| "Instale o matplotlib" ao ver o gráfico | Pacote ausente | `pip install matplotlib` |
| Aluno aparece como "sem dados" | Menos de 2 provas lançadas em todas as disciplinas | Lance ao menos 2 provas por disciplina |
| Notas antigas não aparecem | Estão no modelo por bimestre | Relance por semestre (ou peça um script de migração) |

---

## 16. Glossário

| Termo | Significado |
|---|---|
| **AVG / AVI / AVC** | As três provas lançadas por disciplina em cada semestre |
| **Média da disciplina** | Média das duas maiores notas entre as provas |
| **Atlas** | Serviço de MongoDB na nuvem |
| **Índice único / parcial** | Regra do banco que impede duplicatas (parcial = só vale para documentos que têm o campo) |
| **TTL** | Índice que apaga documentos automaticamente após um tempo |
| **PBKDF2** | Algoritmo que transforma a senha em hash resistente a força bruta |
| **Upsert** | Atualiza o registro se existir, senão cria |
| **Gemini / Claude** | Modelos de IA (Google / Anthropic) usados só para redigir o resumo do alerta |
| **Sistema especialista / regras** | Decisão por regras explícitas e pesos fixos, ao contrário de um modelo treinado |
| **LGPD** | Lei Geral de Proteção de Dados (Brasil) |


