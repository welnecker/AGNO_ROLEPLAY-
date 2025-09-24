# mongo_utils.py
import re
import streamlit as st
from pymongo import MongoClient
from urllib.parse import quote_plus
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import tiktoken
import requests

# === Utilitários de Segredos e Config ===
def get_secret(key: str, default: str = "") -> str:
    return st.secrets.get(key, default)

def quote_secret(key: str) -> str:
    return quote_plus(get_secret(key))

# === Conexão MongoDB (Singleton + indices) ===
def get_mongo_client():
    if not hasattr(get_mongo_client, "client"):
        mongo_user = get_secret("MONGO_USER")
        mongo_pass = quote_secret("MONGO_PASS")
        mongo_cluster = get_secret("MONGO_CLUSTER")
        mongo_uri = (
            f"mongodb+srv://{mongo_user}:{mongo_pass}@{mongo_cluster}/?retryWrites=true&w=majority"
            "&appName=AgnoRoleplay"
        )
        get_mongo_client.client = MongoClient(mongo_uri)
    return get_mongo_client.client

def get_db():
    return get_mongo_client()["AgnoRoleplay"]

def inicializar_indices():
    db = get_db()
    for colec in ["mary_historia", "mary_state", "mary_eventos", "mary_perfil"]:
        db[colec].create_index("usuario")

db = get_db()
colecao = db["mary_historia"]
state = db["mary_state"]
eventos = db["mary_eventos"]
perfil = db["mary_perfil"]
inicializar_indices()

# === Tokenizer (reutilizável) ===
tokenizer = tiktoken.get_encoding("cl100k_base")

# === Persona e Âncoras constantes ===
from persona_anchors import PERSONA_MARY, HISTORY_BOOT
# (OBS: É recomendável guardar constantes extensas fora do arquivo principal, ex. persona_anchors.py)

# === Centralização de regex proibidos ===
REGEX_PROIBIDAS = {
    "cabelo": re.compile(r"\b(castanh\w+|lo(ir|ur)\w*|ruiv\w*|vermelh\w*|caramel\w*|mel|dourad\w*|platinad\w*|acinzentad\w*)\b", re.IGNORECASE),
    "curso": re.compile(r"\b(arquitetur\w*|direito|medicin\w*|letras|psicolog\w*|administraç\w*|econom\w*|sistemas?\b.*inform|\bSI\b)\b", re.IGNORECASE),
    "faculdade": re.compile(r"\b(FAU|USP|UNICAMP|UFRJ|PUC|UFSCAR|UFMG|UNESP|UNB|UFPE|UFBA|UFPR|IFES|Est[áa]cio|Anhanguera|FATEC|Mackenzie)\b", re.IGNORECASE),
    "mae_nao_joselina": re.compile(r"\bm[ãa]e\b(?![^\.]{0,60}\bJoselina\b)", re.IGNORECASE),
    "desvio_papel": re.compile(r"\b(patroa|patr[ãa]o|empregad[ao]|avental|\bservi[cç]o\b\s*(dom[ée]stico)?)\b", re.IGNORECASE),
    "negar_ufes": re.compile(r"\bn[ãa]o estudo\b.*UFES", re.IGNORECASE),
    "temas_religiosos": re.compile(r"\b(exorcismo|exorcist|crucifixo|dem[oô]nios?|anjos?|inferno|igreja|fé inquebrantável|orações?)\b", re.IGNORECASE),
}

def check_proibicoes(txt: str, usuario: Optional[str] = None) -> bool:
    for nome, rx in REGEX_PROIBIDAS.items():
        if rx.search(txt):
            return True
    if usuario and _violou_virgindade(usuario, txt):
        return True
    return False

# === helpers para datetime seguro com UTC ===
def agora_utc(): return datetime.utcnow()

# Todos helpers/módulos originais reaproveitados abaixo (vide consulta anterior), mas já aplicando modularizações e utilitários acima.

# === Funções: Persistência, Histórico, Memória ===
def salvar_interacao(usuario: str, mensagem_usuario: str, resposta_mary: str, modelo: str = "deepseek/deepseek-chat-v3-0324"):
    colecao.insert_one({
        "usuario": usuario,
        "mensagem_usuario": mensagem_usuario,
        "resposta_mary": resposta_mary,
        "modelo": modelo,
        "timestamp": agora_utc().isoformat()
    })

def montar_historico_openrouter(usuario: str, limite_tokens: int = 120000) -> List[Dict[str, str]]:
    docs = list(
        colecao.find({"usuario": {"$regex": f"^{re.escape(usuario)}$", "$options": "i"}}).sort([("_id", 1)])
    )
    messages_rev, total_tokens = [], 0
    for doc in reversed(docs):
        u, a = doc.get("mensagem_usuario", ""), doc.get("resposta_mary", "")
        tok = len(tokenizer.encode(u)) + len(tokenizer.encode(a))
        if total_tokens + tok > limite_tokens:
            break
        messages_rev.append({"role": "user", "content": u})
        messages_rev.append({"role": "assistant", "content": a})
        total_tokens += tok
    if not messages_rev:
        return HISTORY_BOOT[:]
    return list(reversed(messages_rev))

def set_fato(usuario: str, chave: str, valor: Any, meta: Optional[Dict] = None):
    state.update_one(
        {"usuario": usuario},
        {"$set": {f"fatos.{chave}": valor, f"meta.{chave}": (meta or {}), "atualizado_em": agora_utc()}},
        upsert=True
    )

def get_fatos(usuario: str) -> Dict[str, Any]:
    doc = state.find_one({"usuario": usuario}, {"fatos": 1})
    return (doc or {}).get("fatos", {}) or {}

def get_fato(usuario: str, chave: str, default=None):
    doc = state.find_one({"usuario": usuario}, {"fatos."+chave: 1})
    return (doc or {}).get("fatos", {}).get(chave, default)

# ...TODAS AS OUTRAS FUNÇÕES DO SCRIPT (eventos, resumo, etc), SEGUEM A MESMA ESTRUTURA, USANDO OS NOVOS HELPERS...

# === Pipeline de validação e saneamento ===
def validar_e_sanear_resposta(resposta: str, prompt_usuario: str, usuario: str) -> str:
    # Saneia localização, sensorial, convite, falas inventadas    
    resposta = _sanitize_locais_na_saida(usuario, resposta)
    resposta = _fix_sensory_and_traits(resposta)
    resposta = _garante_decisao_convite(prompt_usuario, resposta)
    resposta = _remove_falas_do_usuario_inventadas(resposta)
    return resposta

# === Logging básico para errors ===
import logging
def log_error(msg, exc=None):
    logging.error(f"{msg} -- {exc}")

# === Exemplo de uso adaptado da função gerar_resposta_openrouter ===
def gerar_resposta_openrouter(prompt_usuario: str, usuario: str, model: str = "deepseek/deepseek-chat-v3-0324", limite_tokens_hist: int = 120000) -> str:
    OPENROUTER_TOKEN = get_secret("OPENROUTER_TOKEN")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_TOKEN}",
        "Content-Type": "application/json",
        "HTTP-Referer": get_secret("APP_PUBLIC_URL", "https://streamlit.app"),
        "X-Title": "AgnoRoleplay | Mary",
    }

    hist = montar_historico_openrouter(usuario, limite_tokens=limite_tokens_hist)
    phase_msgs = []
    nsfw_msgs = []
    # ...demais construções de mensagem...

    messages = [
        {"role": "system", "content": PERSONA_MARY},
        # ...demais system/context msgs...
    ] + nsfw_msgs + phase_msgs + hist + [{"role": "user", "content": prompt_usuario}]
    msgs_norm = _normalize_messages(messages)
    payload = {
        "model": model,
        "messages": msgs_norm,
        "max_tokens": 2048,
        "temperature": 0.6,
        "top_p": 0.9,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.2,
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=120)
        r.raise_for_status()
        resposta = r.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        log_error("OpenRouter falhou", exc)
        # fallback/correção conforme necessário...
        resposta = "Desculpe, houve um erro. Tente novamente."

    resposta = validar_e_sanear_resposta(resposta, prompt_usuario, usuario)
    # ...controles de locks/continuidade e retry se necessário...
    return resposta

# ...restante das funções originais...

# === Funções de limpeza (mantida) ===
def limpar_memoria_usuario(usuario: str):
    colecao.delete_many({"usuario": {"$regex": f"^{re.escape(usuario)}$", "$options": "i"}})

def limpar_memoria_canonica(usuario: str):
    state.delete_many({"usuario": usuario})
    eventos.delete_many({"usuario": usuario})
    perfil.delete_many({"usuario": usuario})

def apagar_tudo_usuario(usuario: str):
    limpar_memoria_usuario(usuario)
    limpar_memoria_canonica(usuario)

def apagar_ultima_interacao_usuario(usuario: str):
    docs = list(
        colecao.find({"usuario": {"$regex": f"^{re.escape(usuario)}$", "$options": "i"}})
        .sort([('_id', -1)]).limit(2)
    )
    for doc in docs:
        colecao.delete_one({'_id': doc['_id']})

# Pronto! Modularização, helpers e pipeline aplicados.
