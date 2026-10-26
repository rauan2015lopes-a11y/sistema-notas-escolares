# Sistema de Notas Escolares

Python + MongoDB Atlas (banco `escola_bigdata`). Duas interfaces sobre os mesmos dados.

## Como executar

```
pip install -r requirements.txt
set MONGODB_URI=mongodb+srv://...      # PowerShell: $env:MONGODB_URI="..."
python tela.py      # interface gráfica
python main.py      # terminal
```

Opcional: defina `ADMIN_SETUP_CODE` antes do primeiro acesso para exigir um código
na criação da conta da secretaria.

## Regras
- Nota por aluno + disciplina + semestre (1 a 4), com provas AVG, AVI e AVC (0 a 10).
- Média da disciplina = soma das duas maiores notas ÷ 2 (precisa de 2 notas).
- Média do semestre = média das disciplinas; média geral = média dos semestres.
- Alerta precoce de risco (`risco.py`): modelo explicável que soma pontos por média geral baixa
  (<7, <6, <5), disciplinas com média <6, queda ≥1 ponto entre os dois últimos semestres e dados
  incompletos. Baixo <25, médio 25-49, alto ≥50. Não é aprendizado de máquina treinado (o banco
  não guarda aprovação/reprovação); com esse histórico, o modelo pode ser substituído por um treinado.
- Resumo por IA (`explicador.py`, opcional): botão "Explicar com IA" na aba Alerta de risco
  (opção 7 no terminal). A IA escreve um resumo em português e sugestões de acompanhamento
  a partir das médias e dos motivos do alerta. **Nome e matrícula do aluno não são enviados.**
  - **Gemini (Google), recomendado para testar:** defina `GEMINI_API_KEY` (chave gratuita em
    aistudio.google.com/apikey). Não precisa instalar nada. Modelo padrão `gemini-3.8-flash`
    (`GEMINI_MODELO` troca). **No plano gratuito o Google pode usar o conteúdo enviado para
    melhorar os produtos dele: use só com dados fictícios/de demonstração.**
  - **Claude (Anthropic), pago:** `pip install anthropic` e `ANTHROPIC_API_KEY`.
  - Com as duas chaves, vale o Gemini; `EXPLICADOR_PROVEDOR=claude` força o Claude.
- Senha da secretaria: mínimo 8 caracteres, com letras e números.
- 5 tentativas inválidas bloqueiam o usuário por 5 minutos (registrado no banco).
- Excluir aluno ou disciplina (só na tela) apaga também as notas ligadas a ele.

## Arquivos
- `docencia.py` – vínculo professor↔disciplina (um professor por matéria)
- `calculos.py` – regras de média e boletim (usado pelas duas interfaces)
- `autenticacao.py`, `banco.py`, `config.py` – login, conexão e índices
- `tela.py` – interface gráfica
- `main.py`, `interface.py`, `cadastros.py`, `notas.py`, `consultas.py`, `relatorios.py`, `entrada.py` – terminal
- `graficos.py` – gráfico de médias
- `tests/` – testes (`python -m unittest discover tests`)

Notas antigas por bimestre (campo `nota`) não são mais lidas pelo sistema.

## Perfis
- **Secretaria**: único perfil que edita (alunos, disciplinas, professor da disciplina, notas, usuários).
- **Professor** e **Consulta**: somente visualização. Cada professor leciona no máximo uma disciplina.
