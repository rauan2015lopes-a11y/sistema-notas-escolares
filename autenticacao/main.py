from pymongo import MongoClient

# String de conexão padrão local
uri = "mongodb://localhost:27017/"

client = MongoClient(uri)

# Testa a conexão listando os bancos de dados
try:
    print("Bancos disponíveis:", client.list_database_names())
    print("Conectado com sucesso!")
except Exception as e:
    print("Erro de conexão:", e)
