import streamlit as st
from pymongo import MongoClient
from urllib.parse import quote_plus
from datetime import datetime
import tiktoken
import requests

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

# Tokenizador para limite de contexto (cl100k_base - OpenAI compatível)
tokenizer = tiktoken.get_encoding("cl100k_base")

# SALVAR INTERAÇÃO NO BANCO
def salvar_interacao(usuario, mensagem_usuario, resposta_mary):
    doc = {
        "usuario": usuario,
        "mensagem_usuario": mensagem_usuario,
        "resposta_mary": resposta_mary,
        "timestamp": datetime.now().isoformat()
    }
    colecao.insert_one(doc)

# MONTAR HISTÓRICO PARA OPENROUTER CHAT
def montar_historico_openrouter(usuario, limite_tokens=120000):
    docs = list(colecao.find({"usuario": usuario}).sort([('_id', 1)]))
    messages = []
    total_tokens = 0
    # Mantém o máximo possível do histórico segundo limite de tokens
    for doc in reversed(docs):  # começa dos mais recentes!
        bloco_user = {"role": "user", "content": doc['mensagem_usuario']}
        bloco_assistant = {"role": "assistant", "content": doc['resposta_mary']}
        bloco_tokens = len(tokenizer.encode(doc['mensagem_usuario'])) + len(tokenizer.encode(doc['resposta_mary']))
        if total_tokens + bloco_tokens > limite_tokens:
            break
        messages.append(bloco_user)
        messages.append(bloco_assistant)
        total_tokens += bloco_tokens
    # Retorna cronologicamente correto
    return list(reversed(messages))

# FUNÇÃO DE REQUISIÇÃO AO OPENROUTER
def gerar_resposta_openrouter(prompt_usuario, history=None):
    OPENROUTER_TOKEN = st.secrets["OPENROUTER_TOKEN"]
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_TOKEN}",
        "Content-Type": "application/json"
    }
    system_prompt = {
        "role": "system",
        "content": "Roleplay persona: Mary Massariol. Siga o preset estrito, regras de conduta e estilo. Mantenha personagem sempre."
    }
    messages = [system_prompt]
    if history:
        messages += history
    messages.append({"role": "user", "content": prompt_usuario})
    payload = {
        "model": "deepseek/deepseek-chat-v3-0324",
        "messages": messages,
        "max_tokens": 2048
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    resposta = response.json()["choices"][0]["message"]["content"]
    return resposta

# ... código de conexão Mongo já existente ...

def limpar_memoria_usuario(usuario):
    colecao.delete_many({"usuario": usuario})

def apagar_ultima_interacao_usuario(usuario):
    docs = list(colecao.find({"usuario": usuario}).sort([('_id', -1)]).limit(2))
    # Última interação normalmente é par: turno usuário + resposta Mary
    if docs:
        for doc in docs:
            colecao.delete_one({'_id': doc['_id']})


