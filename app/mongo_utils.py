# mongo_utils.py
import re
import json
import streamlit as st
from pymongo import MongoClient
from urllib.parse import quote_plus
from datetime import datetime
from typing import Optional, Dict, Any, List
import tiktoken
import requests

# ========== Mongo ==========
mongo_user = st.secrets["MONGO_USER"]
mongo_pass = quote_plus(st.secrets["MONGO_PASS"])
mongo_cluster = st.secrets["MONGO_CLUSTER"]
MONGO_URI = (
    f"mongodb+srv://{mongo_user}:{mongo_pass}@{mongo_cluster}/?retryWrites=true&w=majority"
    "&appName=AgnoRoleplay"
)
client = MongoClient(MONGO_URI)
db = client["AgnoRoleplay"]

colecao = db["mary_historia"]       # histórico de chat
state = db["mary_state"]            # fatos atuais
eventos = db["mary_eventos"]        # linha do tempo
perfil = db["mary_perfil"]          # resumo/sinopse

# ========== Tokenizer ==========
tokenizer = tiktoken.get_encoding("cl100k_base")

# ========== Persona base ==========
PERSONA_MARY = """
ATENÇÃO MÁXIMA — NUNCA QUEBRAR (REGRAS CRÍTICAS)
1) Cabelo: Meus cabelos são NEGROS e volumosos. Se perguntarem a cor, responda exatamente:
   "Meus cabelos são negros e volumosos." Nunca outra cor.
2) Curso/Faculdade: Eu estudo Engenharia Civil na UFES. Nunca diga outro curso/faculdade.
3) Mãe: O nome da minha mãe é Joselina (viva). Nunca diga outro nome nem sugira morte/tragédia sem evento explícito no histórico.

IDENTIDADE FIXA
- Nome: Mary Massariol, 20 anos. Estudante de Engenharia Civil (UFES).
- Mora com a mãe (Joselina), ap. 202 — Rua Beethoven, Laranjeiras. Usa moto 500cc.
- Traços de personalidade: inteligente, romântica, direta no afeto; gosta de praia e flerte; não tolera grosseria/cantada barata; busca respeito e liberdade.

TRAÇOS SENSORIAIS (USO CONTROLADO)
- Em cada parágrafo use EXATAMENTE 1 traço físico/sensorial, integrado à ação (nunca liste).
- Traços disponíveis: cabelos NEGROS e volumosos; olhos verdes; seios médios e empinados; cintura definida; quadris largos; coxas grossas; bumbum redondo e firme; barriga lisa; pele branca.

PERSONALIDADE & INICIATIVA (ATIVA)
- Mary toma iniciativa: pode sugerir encontros, ligar, mandar mensagem, marcar lugares inusitados (dentro do bom senso e do consentimento).
- Pode propor: “Vamos fugir pra praia?”, “Te busco de moto?”, “Topo um drink no Serra Bella?”, “Que tal um banho de madrugada na Enseada?”.
- Mantém respeito e leitura do clima: se sentir desconforto do usuário, recua com elegância.

RELACIONAMENTO & LIMITES
- Virgem por escolha até evento canônico contrário; progressão: flerte → toque leve → beijo → carícia → toque íntimo → sexo (sempre consentido).
- Rejeita traição; entrega total apenas por vontade própria.
- Depois de cenas intensas, alterna com cuidado/colo/humor para equilíbrio do tom.

TERCEIROS (COADJUVANTES)
- Amigas: Silvia Bodat (extrovertida, bem-humorada) e Alexandra Resinentti (reservada, conselheira).
- Terceiros surgem como apoio (fofoca, contexto, conselhos) sem roubar o foco do usuário.

CENÁRIOS FREQUENTES
- Clube Serra Bella (balada), Motel Status (atos sexuais), Cafeteria Oregon (encontros),
  Praia de Camburi (lazer), Enseada do Suá (namoro à noite), Restaurante Partido Alto (Camburi — almoço),
  Quiosque Posto 6 (Camburi — drinks à beira-mar), UFES (rotina acadêmica).

ESTILO (ROMÂNTICO DIRETO — SEM METÁFORAS ACADÊMICAS)
- Produza 3 a 5 parágrafos, com 2 a 3 frases cada; ritmo fluido e natural.
- Um traço sensorial por parágrafo (obrigatório) e sem repetição excessiva.
- Romântica e direta: use palavras simples de afeto/desejo (“quero você”, “me faz bem”, “teu abraço é meu abrigo”).
- Evite totalmente metáforas técnicas/estudantis (nada de teoremas, equações, átomos, “físico nuclear” etc.).
- Marque passagem de tempo/contexto quando necessário (“mais tarde…”, “na praia…”, “novo ambiente…”).
- Sem loops: efeitos e consequências persistem nas próximas interações.

CONSISTÊNCIA (SEMPRE REFORÇAR SE PERGUNTAREM)
- Aparência/cabelo: “Meus cabelos são negros e volumosos.”
- Estudo: “Eu estudo Engenharia Civil na UFES.”
- Mãe: “O nome da minha mãe é Joselina.”
- Se houver contradição no histórico, corrija explicitamente e siga as regras fixas acima.
""".strip()

HISTORY_BOOT = [
    {"role": "assistant", "content": "Meus cabelos são negros e volumosos."},
    {"role": "assistant", "content": "Eu estudo Engenharia Civil na UFES."},
    {"role": "assistant", "content": "Moro com minha mãe, Joselina, no ap. 202 da Rua Beethoven, em Laranjeiras."},
]

# ============================
# Histórico (persistência)
# ============================
def salvar_interacao(usuario: str, mensagem_usuario: str, resposta_mary: str, modelo: str = "deepseek/deepseek-chat-v3-0324"):
    colecao.insert_one({
        "usuario": usuario,
        "mensagem_usuario": mensagem_usuario,
        "resposta_mary": resposta_mary,
        "modelo": modelo,
        "timestamp": datetime.now().isoformat()
    })

def montar_historico_openrouter(usuario: str, limite_tokens: int = 120000) -> List[Dict[str, str]]:
    docs = list(
        colecao.find({"usuario": {"$regex": f"^{re.escape(usuario)}$", "$options": "i"}}).sort([("_id", 1)])
    )
    messages_rev, total_tokens = [], 0
    for doc in reversed(docs):
        u = doc.get("mensagem_usuario") or ""
        a = doc.get("resposta_mary") or ""
        tok = len(tokenizer.encode(u)) + len(tokenizer.encode(a))
        if total_tokens + tok > limite_tokens:
            break
        messages_rev.append({"role": "assistant", "content": a})
        messages_rev.append({"role": "user", "content": u})
        total_tokens += tok
    if not messages_rev:
        return HISTORY_BOOT[:]
    return list(reversed(messages_rev))

# ============================
# Memória canônica (CRUD)
# ============================
def set_fato(usuario: str, chave: str, valor: Any, meta: Optional[Dict] = None):
    state.update_one(
        {"usuario": usuario},
        {
            "$set": {
                f"fatos.{chave}": valor,
                f"meta.{chave}": (meta or {"fonte": "manual"}),
                "atualizado_em": datetime.utcnow(),
            }
        },
        upsert=True
    )

def get_fatos(usuario: str) -> Dict[str, Any]:
    doc = state.find_one({"usuario": usuario}, {"fatos": 1})
    return (doc or {}).get("fatos", {}) or {}

def get_resumo(usuario: str) -> str:
    doc = perfil.find_one({"usuario": usuario}, {"resumo": 1})
    return (doc or {}).get("resumo", "") or ""

def ultimo_evento(usuario: str, tipo: str):
    return eventos.find_one({"usuario": usuario, "tipo": tipo}, sort=[("ts", -1)])

def registrar_evento(usuario: str, tipo: str, descricao: str,
                     local: Optional[str] = None, data_hora: Optional[datetime] = None):
    eventos.insert_one({
        "usuario": usuario,
        "tipo": tipo,
        "descricao": descricao,
        "local": local,
        "ts": data_hora or datetime.utcnow()
    })

# ---------- Regras evento -> fatos (ATUALIZADA) ----------
def _aplicar_regras_evento_para_fatos(
    usuario: str,
    tipo: str,
    descricao: str,
    local: Optional[str],
    ts: datetime
):
    """
    Regras de sincronização evento -> fatos canônicos.
    Detecta:
    - 'primeiro_encontro' ou texto contendo 'se conheceram' => primeiro_encontro = local do evento
    - 'forró'/'forro'/'posto 6' na descrição => forro_local = 'Quiosque Posto 6'
    - demais (primeira_vez, episodio_ciume_praia, pedido_namoro)
    """
    t = (tipo or "").strip().lower()
    desc_norm = (descricao or "").lower()

    # 1) Primeiro encontro
    if t == "primeiro_encontro" or ("se conheceram" in desc_norm):
        if local:
            set_fato(usuario, "primeiro_encontro", local, meta={"fonte": "evento", "ts": ts})
        set_fato(usuario, "primeiro_encontro_resumo", descricao, meta={"fonte": "evento", "ts": ts})

    # 2) Primeira vez (sexual)
    if t == "primeira_vez":
        set_fato(usuario, "virgem", False, meta={"fonte": "evento", "ts": ts})
        if local:
            set_fato(usuario, "primeira_vez_local", local, meta={"fonte": "evento", "ts": ts})
        set_fato(usuario, "primeira_vez_resumo", descricao, meta={"fonte": "evento", "ts": ts})

    # 3) Episódio de ciúme na praia
    if t == "episodio_ciume_praia":
        if local:
            set_fato(usuario, "episodio_ciume_local", local, meta={"fonte": "evento", "ts": ts})
        set_fato(usuario, "episodio_ciume_resumo", descricao, meta={"fonte": "evento", "ts": ts})

    # 4) Pedido de namoro
    if t == "pedido_namoro":
        set_fato(usuario, "relacionamento_status", "namorando", meta={"fonte": "evento", "ts": ts})
        if local:
            set_fato(usuario, "pedido_namoro_local", local, meta={"fonte": "evento", "ts": ts})
        set_fato(usuario, "pedido_namoro_resumo", descricao, meta={"fonte": "evento", "ts": ts})

    # 5) Heurística: forró + Posto 6
    if ("forró" in desc_norm) or ("forro" in desc_norm) or ("posto 6" in desc_norm):
        set_fato(usuario, "forro_local", "Quiosque Posto 6", meta={"fonte": "evento", "ts": ts})
        set_fato(usuario, "forro_resumo", descricao, meta={"fonte": "evento", "ts": ts})

def registrar_evento_canonico(
    usuario: str,
    tipo: str,
    descricao: str,
    local: Optional[str] = None,
    data_hora: Optional[datetime] = None,
    atualizar_fatos: bool = True,
):
    """Wrapper: registra o evento e, opcionalmente, sincroniza fatos canônicos."""
    ts = data_hora or datetime.utcnow()
    eventos.insert_one({
        "usuario": usuario,
        "tipo": tipo,
        "descricao": descricao,
        "local": local,
        "ts": ts
    })
    if atualizar_fatos:
        _aplicar_regras_evento_para_fatos(usuario, tipo, descricao, local, ts)

# ---------- Bloco de memória injetado ----------
def construir_contexto_memoria(usuario: str) -> str:
    linhas: List[str] = []
    fatos = get_fatos(usuario)

    if "virgem" in fatos:
        linhas.append(f"STATUS ÍNTIMO: virgem={bool(fatos['virgem'])}")
    if "parceiro_atual" in fatos:
        linhas.append(f"RELACIONAMENTO: parceiro_atual={fatos['parceiro_atual']}")
    if "relacionamento_status" in fatos:
        linhas.append(f"RELACIONAMENTO_STATUS: {fatos['relacionamento_status']}")
    if "cidade_atual" in fatos:
        linhas.append(f"LOCAL: cidade_atual={fatos['cidade_atual']}")

    # >>> Locais canônicos distintos
    if "primeiro_encontro" in fatos:
        linhas.append(f"PRIMEIRO_ENCONTRO: {fatos['primeiro_encontro']}")
    if "forro_local" in fatos:
        linhas.append(f"FORRÓ: local={fatos['forro_local']}")

    # Eventos úteis
    e_primeira = ultimo_evento(usuario, "primeira_vez")
    if e_primeira:
        dt = e_primeira["ts"].strftime("%Y-%m-%d %H:%M")
        lugar = e_primeira.get("local") or "local não especificado"
        linhas.append(f"EVENTO_CANÔNICO: primeira_vez em {dt} @ {lugar}")

    resumo = get_resumo(usuario)
    if resumo:
        linhas.append(f"RESUMO: {resumo[:600]}")

    return "\n".join(linhas).strip()

# ============================
# Sanitização de locais (ATUALIZADA)
# ============================
_CANON_SETS = {
    "clube serra bella": {"serra bella", "serra bela", "clube serra bella"},
    "café oregon": {"café oregon", "cafe oregon", "oregon"},
    "praia de camburi": {"praia de camburi", "camburi", "quiosque posto 6", "posto 6"},
    "motel status": {"motel status", "status"},
    "ufes": {"ufes", "universidade federal do espírito santo"},
}

_GENERIC_TO_CANON = {
    r"\bbalada\b": "clube serra bella",
    r"\bbarzinho\b": "café oregon",
    r"\bbar\b": "café oregon",
    r"\bquiosque\b": "praia de camburi",
}

def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())

def _is_known_canon(token: str) -> Optional[str]:
    t = _norm(token)
    for canon, variants in _CANON_SETS.items():
        if t == canon or any(t == _norm(v) for v in variants):
            return canon
    return None

def _sanitize_locais_na_saida(usuario: str, texto: str) -> str:
    """
    Corrige apenas termos genéricos/inventados.
    NÃO substitui locais canônicos distintos (ex.: 'Café Oregon' e 'Posto 6' podem coexistir).
    """
    out = texto

    # 1) Genéricos -> canônicos
    for pat, canon in _GENERIC_TO_CANON.items():
        out = re.sub(pat, canon, out, flags=re.IGNORECASE)

    # 2) Inventados comuns (barX, pubY, loungeZ) – sem tocar canônicos já corretos
    out = re.sub(
        r"\bbar\w+\b",
        lambda m: "café oregon" if not _is_known_canon(m.group(0)) else m.group(0),
        out,
        flags=re.IGNORECASE
    )
    out = re.sub(
        r"\bpub\w+\b",
        lambda m: "clube serra bella" if not _is_known_canon(m.group(0)) else m.group(0),
        out,
        flags=re.IGNORECASE
    )
    out = re.sub(
        r"\blounge\w*\b",
        lambda m: "clube serra bella" if not _is_known_canon(m.group(0)) else m.group(0),
        out,
        flags=re.IGNORECASE
    )

    return out

# ============================
# Validadores mínimos
# ============================
_RE_PROIBIDO_CABELO = re.compile(r"\b(castanh\w+|lo(ir|ur)\w*|ruiv\w*|vermelh\w*|caramel\w*|mel|dourad\w*|platinad\w*|acinzentad\w*)\b", re.IGNORECASE)
_RE_PROIBIDO_CURSO = re.compile(r"\b(arquitetur\w*|direito|medicin\w*|letras|psicolog\w*|administraç\w*|econom\w*|sistemas?\b.*inform)\b", re.IGNORECASE)
_RE_MAE_NAO_JOSELINA = re.compile(r"\bm[ãa]e\b(?![^\.]{0,60}\bJoselina\b)", re.IGNORECASE)

def _violou_mary(txt: str, usuario: Optional[str] = None) -> bool:
    base = any([
        _RE_PROIBIDO_CABELO.search(txt),
        _RE_PROIBIDO_CURSO.search(txt),
        _RE_MAE_NAO_JOSELINA.search(txt),
    ])
    return base

def _reforco_system() -> Dict[str, str]:
    return {
        "role": "system",
        "content": "CORREÇÃO: respeite cabelo, curso, mãe, e locais/eventos canônicos conforme memória salva. Evite metáforas acadêmicas."
    }

# ============================
# Geração com OpenRouter (usa saneador)
# ============================
def gerar_resposta_openrouter(prompt_usuario: str, usuario: str,
                              model: str = "deepseek/deepseek-chat-v3-0324",
                              limite_tokens_hist: int = 120000) -> str:
    OPENROUTER_TOKEN = st.secrets["OPENROUTER_TOKEN"]
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_TOKEN}", "Content-Type": "application/json"}

    # Histórico recente (ou âncoras se vazio)
    hist = montar_historico_openrouter(usuario, limite_tokens=limite_tokens_hist)
    if not hist:
        hist = HISTORY_BOOT[:]

    # Memória canônica → system message
    memoria_txt = construir_contexto_memoria(usuario)
    memoria_msg = [{"role": "system", "content": "MEMÓRIA CANÔNICA:\n" + memoria_txt}] if memoria_txt else []

    # Mensagens (com orientação de estilo e iniciativa)
    messages = [
        {"role": "system", "content": PERSONA_MARY},
        {"role": "system", "content": (
            "Estilo narrativo obrigatório:\n"
            "- 3 a 5 parágrafos, 2–3 frases cada; um traço sensorial por parágrafo.\n"
            "- Mary é ativa: pode propor próximos passos (consentidos) e convites claros quando couber.\n"
            "- Romântica e direta; não use metáforas de cursos/ciência/matemática."
        )},
    ] + memoria_msg + hist + [{"role": "user", "content": prompt_usuario}]

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 3000,
        "temperature": 0.6,
        "top_p": 0.9,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.2
    }

    # 1ª chamada
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    resposta = r.json()["choices"][0]["message"]["content"]

    # Saneia locais genéricos/inventados sem unificar canônicos distintos
    try:
        resposta = _sanitize_locais_na_saida(usuario, resposta)
    except Exception:
        pass

    # Retry com reforço se violar coerência/persona
    if _violou_mary(resposta, usuario):
        messages.insert(1, _reforco_system())
        payload["messages"] = messages
        r2 = requests.post(url, headers=headers, json=payload, timeout=120)
        r2.raise_for_status()
        resposta = r2.json()["choices"][0]["message"]["content"]
        try:
            resposta = _sanitize_locais_na_saida(usuario, resposta)
        except Exception:
            pass

    return resposta

# ============================
# Utilidades (limpeza)
# ============================
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
    docs = list(colecao.find({"usuario": {"$regex": f"^{re.escape(usuario)}$", "$options": "i"}}).sort([('_id', -1)]).limit(2))
    for d in docs:
        colecao.delete_one({'_id': d['_id']})
