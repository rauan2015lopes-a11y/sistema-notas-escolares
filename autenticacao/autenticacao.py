"""Autenticação de administradores (senha com hash PBKDF2 + salt).

As senhas nunca são guardadas em texto puro: o banco (coleção `usuarios`)
guarda apenas o salt e o hash gerado com PBKDF2-HMAC-SHA256.
"""

import hashlib
import hmac
import os
from datetime import datetime

ITERACOES = 200_000


def gerar_hash(senha, salt=None):
    """Devolve (salt_hex, hash_hex) da senha. Gera um salt novo se não for informado."""
    salt = salt or os.urandom(16)
    resultado = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, ITERACOES)
    return salt.hex(), resultado.hex()


def verificar_senha(senha, salt_hex, hash_hex):
    """Confere a senha digitada contra o hash guardado (comparação em tempo constante)."""
    _, calculado = gerar_hash(senha, bytes.fromhex(salt_hex))
    return hmac.compare_digest(calculado, hash_hex)


def existe_admin(banco):
    """Indica se já existe algum administrador cadastrado."""
    return banco.usuarios.count_documents({}, limit=1) > 0


def criar_admin(banco, usuario, senha):
    """Cadastra um administrador. Lança DuplicateKeyError se o usuário já existir."""
    salt, hash_senha = gerar_hash(senha)
    documento = {
        "usuario": usuario.strip().lower(),
        "salt": salt,
        "hash": hash_senha,
        "data_cadastro": datetime.now(),
    }
    banco.usuarios.insert_one(documento)
    return documento


def autenticar(banco, usuario, senha):
    """Devolve o documento do usuário se as credenciais estiverem corretas, senão None."""
    documento = banco.usuarios.find_one({"usuario": usuario.strip().lower()})
    if not documento:
        gerar_hash(senha)  # gasta o mesmo tempo, para não revelar se o usuário existe
        return None
    if verificar_senha(senha, documento["salt"], documento["hash"]):
        return documento
    return None
