import re
import streamlit as st
from pymongo import MongoClient
from urllib.parse import quote_plus
from datetime import datetime
from typing import Optional, Dict, Any, List
import tiktoken
import requests
from typing import Optional, Dict, Any
from datetime import datetime

# se ainda não existir:
def set_fato(usuario: str, chave: str, valor: Any, meta: Optional[Dict] = None):
    state.update_one(
        {"usuario": usuario},
        {
            "$set": {
                f"fatos.{chave}": valor,
                f"meta.{chave}": (meta or {"fonte": "evento"}),
                "atualizado_em": datetime.utcnow(),
            }
        },
        upsert=True
    )

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
ATENÇÃO MÁXIMA — NUNCA QUEBRAR:
1) Cabelo: Meus cabelos são NEGROS, volumosos e soltos. Se perguntarem a cor, diga exatamente:
   "Meus cabelos são negros, volumosos e soltos." Nunca outra cor.
2) Curso/Faculdade: Eu estudo Engenharia Civil na UFES. Nunca diga outro curso/faculdade.
3) Mãe: O nome da minha mãe é Joselina (viva). Nunca diga outro nome nem que ela faleceu, sem evento explícito no histórico.

IDENTIDADE FIXA
- Nome: Mary Massariol, 20 anos. Estudante de Engenharia Civil (UFES).
- Mora com a mãe (Joselina), ap. 202 — Rua Beethoven, Laranjeiras. Usa moto 500cc.
- Traços: inteligente, romântica, gosta de praia e flerte; não tolera grosseria/cantada barata; quer respeito e liberdade.

FÍSICO / SENSORIAL
- Use 1 traço sensorial por parágrafo, integrado à ação.
- Traços disponíveis: cabelos NEGROS, volumosos e soltos; olhos verdes; seios médios; cintura definida; quadris largos; coxas grossas; bumbum redondo; barriga lisa; pele dourada.

RELACIONAMENTO / LIMITES
- Virgem por escolha; progressão: flerte → beijo → carícia → toque íntimo → sexo (sempre consentido).
- Rejeita traição; entrega total apenas por vontade própria.

TERCEIROS
- Silvia Bodat (extrovertida) e Alexandra Resinentti (reservada) só aparecem como apoio (fofoca, conselhos) sem tirar foco do usuário.

ESTILO
- Produza de 3 a 5 parágrafos com 2 a 3 frases cada.
- Expanda reações físicas, emoção e percepção sensorial; linguagem natural e direta.
- Marcar passagem de tempo/contexto quando necessário (“mais tarde…”, “na praia…”).
- Sem loops: efeitos e consequências persistem nas próximas interações.

REGRA DE CONSISTÊNCIA
- Cabelo: “Meus cabelos são negros, volumosos e soltos.”
- Estudo: “Eu estudo Engenharia Civil na UFES.”
- Mãe: “O nome da minha mãe é Joselina.”
- Se houver contradição, corrija explicitamente e reforce a forma correta.
""".strip()

HISTORY_BOOT = [
    {"role": "assistant", "content": "Meus cabelos são negros, volumosos e soltos."},
    {"role": "assistant", "content": "Eu estudo Engenharia Civil na UFES."},
    {"role": "assistant", "content": "Moro com minha mãe, Joselina, no ap. 202 da Rua Beethoven, em Laranjeiras."},
]

# ========== Histórico ==========
def salvar_interacao(usuario: str, mensagem_usuario: str, resposta_mary: str, modelo: str = "deepseek/deepseek-chat-v3-0324"):
    colecao.insert_one({
        "usuario": usuario,
        "mensagem_usuario": mensagem_usuario,
        "resposta_mary": resposta_mary,
        "modelo": modelo,
        "timestamp": datetime.now().isoformat()
    })

def montar_historico_openrouter(usuario: str, limite_tokens: int = 120000) -> List[Dict[str,str]]:
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

# ========== Memória canônica ==========
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

def construir_contexto_memoria(usuario: str) -> str:
    linhas: List[str] = []
    fatos = get_fatos(usuario)
    if "virgem" in fatos:
        linhas.append(f"STATUS ÍNTIMO: virgem={bool(fatos['virgem'])}")
    if "parceiro_atual" in fatos:
        linhas.append(f"RELACIONAMENTO: parceiro_atual={fatos['parceiro_atual']}")
    if "cidade_atual" in fatos:
        linhas.append(f"LOCAL: cidade_atual={fatos['cidade_atual']}")

    ev_prim = ultimo_evento(usuario, "primeira_vez")
    if ev_prim:
        dt = ev_prim["ts"].strftime("%Y-%m-%d %H:%M")
        lugar = ev_prim.get("local") or "local não especificado"
        linhas.append(f"EVENTO_CANÔNICO: primeira_vez em {dt} @ {lugar}")

    ev_ciume = ultimo_evento(usuario, "episodio_ciume_praia")
    if ev_ciume:
        dt = ev_ciume["ts"].strftime("%Y-%m-%d %H:%M")
        lugar = ev_ciume.get("local") or "Praia"
        linhas.append(f"ÚLTIMO_EVENTO_CIUME: {dt} @ {lugar} — surfista tentou flertar; Janio interveio.")

    resumo = get_resumo(usuario)
    if resumo:
        linhas.append(f"RESUMO: {resumo[:500]}")
    return "\n".join(linhas).strip()


def _aplicar_regras_evento_para_fatos(
    usuario: str,
    tipo: str,
    descricao: str,
    local: Optional[str],
    ts: datetime
):
    """
    Regras de sincronização evento -> fatos canônicos.
    Expanda livremente conforme sua história evoluir.
    """
    t = (tipo or "").strip().lower()

    if t == "primeiro_encontro":
        # Fixa o local do primeiro encontro
        if local:
            set_fato(usuario, "primeiro_encontro", local, meta={"fonte": "evento", "ts": ts})
        # Opcional: um resumo curto
        set_fato(usuario, "primeiro_encontro_resumo", descricao, meta={"fonte": "evento", "ts": ts})

    elif t == "primeira_vez":
        # Passa a não-virgem, e salva local
        set_fato(usuario, "virgem", False, meta={"fonte": "evento", "ts": ts})
        if local:
            set_fato(usuario, "primeira_vez_local", local, meta={"fonte": "evento", "ts": ts})
        set_fato(usuario, "primeira_vez_resumo", descricao, meta={"fonte": "evento", "ts": ts})

    elif t == "episodio_ciume_praia":
        # Mantém último episódio de ciúme e local
        if local:
            set_fato(usuario, "episodio_ciume_local", local, meta={"fonte": "evento", "ts": ts})
        set_fato(usuario, "episodio_ciume_resumo", descricao, meta={"fonte": "evento", "ts": ts})

    # exemplo: pedido de namoro
    elif t == "pedido_namoro":
        set_fato(usuario, "relacionamento_status", "namorando", meta={"fonte": "evento", "ts": ts})
        if local:
            set_fato(usuario, "pedido_namoro_local", local, meta={"fonte": "evento", "ts": ts})
        set_fato(usuario, "pedido_namoro_resumo", descricao, meta={"fonte": "evento", "ts": ts})


def registrar_evento_canonico(
    usuario: str,
    tipo: str,
    descricao: str,
    local: Optional[str] = None,
    data_hora: Optional[datetime] = None,
    atualizar_fatos: bool = True,
):
    """
    Wrapper: registra o evento e, opcionalmente, sincroniza fatos canônicos.
    """
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
# ========== Validadores ==========
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
        "content": "CORREÇÃO: respeite cabelo, curso, mãe, locais e eventos canônicos conforme memória salva."
    }

# ========== Geração com OpenRouter ==========
def gerar_resposta_openrouter(prompt_usuario: str, usuario: str,
                              model: str = "deepseek/deepseek-chat-v3-0324",
                              limite_tokens_hist: int = 120000) -> str:
    OPENROUTER_TOKEN = st.secrets["OPENROUTER_TOKEN"]
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_TOKEN}", "Content-Type": "application/json"}

    hist = montar_historico_openrouter(usuario, limite_tokens=limite_tokens_hist)
    if not hist:
        hist = HISTORY_BOOT[:]

    memoria_txt = construir_contexto_memoria(usuario)
    memoria_msg = [{"role": "system", "content": "MEMÓRIA CANÔNICA:\n" + memoria_txt}] if memoria_txt else []

    messages = [
        {"role": "system", "content": PERSONA_MARY},
        {"role": "system", "content": "Estilo: 3–5 parágrafos; 2–3 frases por parágrafo; 1 traço sensorial por parágrafo."},
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

    r = requests.post(url, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    resposta = r.json()["choices"][0]["message"]["content"]

    if _violou_mary(resposta, usuario):
        messages.insert(1, _reforco_system())
        payload["messages"] = messages
        r2 = requests.post(url, headers=headers, json=payload, timeout=120)
        r2.raise_for_status()
        resposta = r2.json()["choices"][0]["message"]["content"]

    return resposta

# ========== Utilidades ==========
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
