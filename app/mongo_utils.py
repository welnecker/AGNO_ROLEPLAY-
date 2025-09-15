import streamlit as st
from pymongo import MongoClient
from urllib.parse import quote_plus
from datetime import datetime
import tiktoken

mongo_user = st.secrets["MONGO_USER"]
mongo_pass = quote_plus(st.secrets["MONGO_PASS"])
mongo_cluster = st.secrets["MONGO_CLUSTER"]
MONGO_URI = (
    f"mongodb+srv://{mongo_user}:{mongo_pass}@{mongo_cluster}/?retryWrites=true&w=majority"
    "&appName=AgnoRoleplay"
)
client = MongoClient(MONGO_URI)
db = client["AgnoRoleplay"]
colecao = db["mary_historia"]

# ======= TOKENIZAÇÃO PARA LIMITE DE MEMÓRIA ======
# Utilize o tokenizer compatível com seu modelo LLM.
tokenizer = tiktoken.get_encoding("cl100k_base")  # Funciona com contexto estilo OpenAI/DeepSeek (~cl100k_base)

# ======= FUNÇÃO: SALVAR INTERAÇÃO NO BANCO ======
def salvar_interacao(usuario, mensagem_usuario, resposta_mary):
    doc = {
        "usuario": usuario,
        "mensagem_usuario": mensagem_usuario,
        "resposta_mary": resposta_mary,
        "timestamp": datetime.now().isoformat()
    }
    colecao.insert_one(doc)

# ======= FUNÇÃO: MONTAR HISTÓRICO DENTRO DO LIMITE DE TOKENS ======
def montar_memoria_dinamica(usuario, limite_tokens=120000, persona_preset=""):
    docs = list(colecao.find({"usuario": usuario}).sort([('_id', 1)]))  # ordem mais antiga -> mais recente
    historia = ""
    total_tokens = len(tokenizer.encode(persona_preset)) if persona_preset else 0
    blocos = []

    # Empilha o máximo possível de histórico (do mais antigo ao mais recente)
    for doc in reversed(docs):  # começa dos mais recentes!
        bloco = f"Usuário: {doc['mensagem_usuario']}\nMary: {doc['resposta_mary']}\n"
        bloco_tokens = len(tokenizer.encode(bloco))
        if total_tokens + bloco_tokens > limite_tokens:
            break
        blocos.append(bloco)
        total_tokens += bloco_tokens

    historia = "".join(reversed(blocos))  # retorna do mais antigo ao mais recente
    return historia

