"""Geração de gráficos com Matplotlib/Seaborn."""

import matplotlib.pyplot as plt
import seaborn as sns


def plotar_medias_aluno(medias, nome_aluno):
    """Plota um gráfico de barras com a média do aluno por disciplina."""
    sns.set_theme(style="whitegrid")
    eixo = sns.barplot(data=medias, x="disciplina", y="nota", hue="disciplina", legend=False)
    eixo.set(title=f"Média de {nome_aluno}", xlabel="Disciplina", ylabel="Média")
    eixo.set_ylim(0, 10)
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.show()
