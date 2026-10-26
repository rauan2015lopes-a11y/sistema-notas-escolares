"""Configurações e constantes do sistema de notas escolares.

Defina a variável de ambiente MONGODB_URI com a string de conexão do
MongoDB Atlas antes de executar o sistema.
"""

import os

from colorama import init

init(autoreset=True)

NOME_BANCO = "escola_bigdata"


def obter_uri_mongodb():
    """Lê a URI de conexão do MongoDB a partir da variável de ambiente."""
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise RuntimeError(
            "Defina a variável de ambiente MONGODB_URI com a conexão do MongoDB Atlas."
        )
    return uri
