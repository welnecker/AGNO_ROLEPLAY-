# mongo_utils.py
# =============================================================================
# Utilitários de persistência, memória canônica e geração de respostas (OpenRouter)
# Otimizado para robustez, eficiência e integração com app/main.py
# =============================================================================
from __future__ import annotations

import json
import re
import time
import math
import random
from typing import Optional, Dict, Any, List

import requests
import streamlit as st
from pymongo import MongoClient
from urllib.parse import quote_plus
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# Config / Secrets (tolerante a falhas)
# -----------------------------------------------------------------------------
_get = st.secrets.get if hasattr(st, "secrets") else lambda *a, **k: None

MONGO_USER = _get("MONGO_USER") or ""
MONGO_PASS = quote_plus(_get("MONGO_PASS") or "")
MONGO_CLUSTER = _get("MONGO_CLUSTER") or ""
APP_NAME = _get("APP_NAME", "AgnoRoleplay") or "AgnoRoleplay"
APP_PUBLIC_URL = _get("APP_PUBLIC_URL", "https://streamlit.app") or "https://streamlit.app"
OPENROUTER_TOKEN = _get("OPENROUTER_TOKEN") or _get("OPENROUTER_API_KEY") or ""

if not (MONGO_USER and MONGO_PASS and MONGO_CLUSTER):
    st.warning("⚠️ Segredos Mongo incompletos (MONGO_USER/PASS/CLUSTER)")

if not OPENROUTER_TOKEN:
    st.warning("⚠️ OPENROUTER_TOKEN não configurado em secrets")

# -----------------------------------------------------------------------------
# Mongo Client (singleton leve)
# -----------------------------------------------------------------------------
MONGO_URI = (
    f"mongodb+srv://{MONGO_USER}:{MONGO_PASS}@{MONGO_CLUSTER}/?retryWrites=true&w=majority&appName={APP_NAME}"
)
_client = MongoClient(MONGO_URI)
db = _client.get_database(APP_NAME)

# Coleções
colecao = db.get_collection("mary_historia")
state = db.get_collection("mary_state")       # fatos atuais
eventos = db.get_collection("mary_eventos")   # linha do tempo
perfil = db.get_collection("mary_perfil")     # resumo/sinopse

# Índices essenciais (idempotentes)
try:
    eventos.create_index([("usuario", 1), ("tipo", 1), ("ts", -1)])
    colecao.create_index([("usuario", 1), ("_id", 1)])
    state.create_index([("usuario", 1)])
    perfil.create_index([("usuario", 1)])
except Exception:
    pass

# -----------------------------------------------------------------------------
# Tokenizer — usa cl100k_base se disponível, senão fallback leve
# -----------------------------------------------------------------------------
try:
    import tiktoken  # type: ignore
    _enc = tiktoken.get_encoding("cl100k_base")
    def _toklen(txt: str) -> int:
        try:
            return len(_enc.encode(txt or ""))
        except Exception:
            return max(1, len((txt or "").split()))
except Exception:
    def _toklen(txt: str) -> int:
        return max(1, len((txt or "").split()))

# -----------------------------------------------------------------------------
# Persona, boot e regras fixas
# -----------------------------------------------------------------------------
PERSONA_MARY = "\n".join([
    "ATENÇÃO MÁXIMA — NUNCA QUEBRAR (REGRAS FIXAS)",
    "1) Cabelo: Meus cabelos são NEGROS e volumosos. Se perguntarem a cor, responda literalmente:",
    "   \"Meus cabelos são negros e volumosos.\" Nunca outra cor.",
    "2) Curso/Faculdade: Eu estudo Design de moda na UFES. Nunca diga outro curso/faculdade.",
    "3) Mãe: O nome da minha mãe é Joselina (viva). Nunca diga outro nome, nem tragédias religiosas.",
    "",
    "IDENTIDADE",
    "- Nome: Mary Massariol, 20 anos. Estudante de Design de moda na UFES.",
    "- Mora com a mãe (Joselina), ap. 2002 — Edifício Moamar, Camburi. BMW vermelha.",
    "- Traços: inteligente, romântica, direta no afeto; flerte; não tolera grosseria.",
    "",
    "DETALHES SENSORIAIS (USO CONTROLADO)",
    "- Use detalhes sensoriais com parcimônia; no máximo um por parágrafo e somente se fizer sentido na cena.",
    "- Evite bordões repetitivos (ex.: 'meus cabelos negros roçam seu pescoço', 'meus olhos verdes pedem mais').",
    "",
    "TERCEIROS",
    "- Amigas: Silvia Bodat, Alexandra Resinentti. Não roubam o foco do usuário.",
    "",
    "LOCAIS CANÔNICOS (DESCRIÇÕES)",
    "- Clube Náutico — casa noturna/balada; música e pista de dança. Local de socialização noturna; não é praia.",
    "- Praia de Camburi — praia urbana e calçadão à beira-mar; espaço público e aberto para caminhar/conversar. NUNCA tratar como clube/balada.",
    "- Quiosque Posto 6 — quiosque/bar de praia; ponto de encontro universitário; ambiente público informal.",
    "- Cafeteria Oregon — cafeteria tranquila; encontros e conversas; ambiente público.",
    "- Restaurante Partido Alto — restaurante em Camburi para almoço; ambiente público.",
    "- Enseada do Suá — bairro/região com bares e casas noturnas; alternativa para sair à noite; vias públicas.",
    "- Academia Fisium Body — academia de musculação; ambiente público/profissional.",
    "- Motel Status — motel (ambiente privado) adequado a cenas íntimas consentidas.",
    "",
    "REGRAS DE CENÁRIO",
    "- Em locais públicos (Praia de Camburi, Quiosque Posto 6, Cafeteria Oregon, Restaurante, Academia, Enseada do Suá, áreas comuns do Clube Náutico): evite sexo explícito; foque diálogo, flerte sutil e carícias leves consentidas.",
    "- Cenas NSFW explícitas apenas em ambientes privados (Motel Status, quarto/apartamento) e com consentimento claro.",
    "",
    "RELACIONAMENTO / LIMITES",
    "- Mary é virgem até acontecer a 'primeira_vez'. Depois, não volta a se declarar virgem.",
    "- Consentimento sempre; sem traição.",
    "",
    "RITMO INICIAL",
    "- Slow burn nas primeiras interações; explícito só com sinal claro do usuário ou mais tarde.",
    "",
    "NSFW",
    "- Após 'primeira_vez', cenas sexuais são permitidas com naturalidade e respeito.",
    "",
    "ESTILO",
    "- 3–6 parágrafos; 2–4 frases cada; romântico e direto; sem metáforas acadêmicas. Não obrigue menções físicas em todo parágrafo; varie o vocabulário.",
    "- Marque tempo/contexto quando necessário.",
    "",
    "CONSISTÊNCIA",
    "- Reforce cabelo/curso/mãe quando perguntarem. Corrija contradições do histórico.",
])

HISTORY_BOOT = [
    {"role": "assistant", "content": "Meus cabelos são negros e volumosos."},
    {"role": "assistant", "content": "Eu estudo Design de moda na UFES."},
    {"role": "assistant", "content": "Moro com minha mãe, Joselina, ap. 2002 — Edifício Moamar, Camburi."},
    {"role": "assistant", "content": "O nome da minha mãe é Joselina. Ela está viva e moramos juntas."},
]


# -----------------------------------------------------------------------------
# Persistência de interações
# -----------------------------------------------------------------------------

def salvar_interacao(usuario: str, mensagem_usuario: str, resposta_mary: str, modelo: str = "deepseek/deepseek-chat-v3-0324"):
    colecao.insert_one({
        "usuario": usuario,
        "mensagem_usuario": mensagem_usuario,
        "resposta_mary": resposta_mary,
        "modelo": modelo,
        "timestamp": datetime.utcnow().isoformat(),
    })


def montar_historico_openrouter(usuario: str, limite_tokens: int = 120_000) -> List[Dict[str, str]]:
    """Retorna pares alternados user->assistant em ordem cronológica, respeitando limite de tokens."""
    docs = list(colecao.find({"usuario": {"$regex": f"^{re.escape(usuario)}$", "$options": "i"}}).sort([("_id", 1)]))
    messages_rev: List[Dict[str, str]] = []
    total = 0
    for d in reversed(docs):
        u = d.get("mensagem_usuario") or ""
        a = d.get("resposta_mary") or ""
        tok = _toklen(u) + _toklen(a)
        if total + tok > limite_tokens:
            break
        messages_rev.append({"role": "user", "content": u})
        messages_rev.append({"role": "assistant", "content": a})
        total += tok
    if not messages_rev:
        return HISTORY_BOOT[:]
    return list(reversed(messages_rev))

# -----------------------------------------------------------------------------
# Memória canônica (fatos/eventos/resumo)
# -----------------------------------------------------------------------------

def set_fato(usuario: str, chave: str, valor: Any, meta: Optional[Dict] = None):
    state.update_one(
        {"usuario": usuario},
        {"$set": {f"fatos.{chave}": valor, f"meta.{chave}": (meta or {}), "atualizado_em": datetime.utcnow()}},
        upsert=True,
    )


def get_fatos(usuario: str) -> Dict[str, Any]:
    d = state.find_one({"usuario": usuario}, {"fatos": 1})
    return (d or {}).get("fatos", {}) or {}


def get_fato(usuario: str, chave: str, default=None):
    d = state.find_one({"usuario": usuario}, {"fatos." + chave: 1})
    return (d or {}).get("fatos", {}).get(chave, default)


def registrar_evento(
    usuario: str,
    tipo: str,
    descricao: str,
    local: Optional[str] = None,
    data_hora: Optional[datetime] = None,
    tags: Optional[List[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
):
    eventos.insert_one({
        "usuario": usuario,
        "tipo": tipo,
        "descricao": descricao,
        "local": local,
        "ts": data_hora or datetime.utcnow(),
        "tags": tags or [],
        "meta": meta or {},
    })


def ultimo_evento(usuario: str, tipo: str):
    return eventos.find_one({"usuario": usuario, "tipo": tipo}, sort=[("ts", -1)])


def get_resumo(usuario: str) -> str:
    d = perfil.find_one({"usuario": usuario}, {"resumo": 1})
    return (d or {}).get("resumo", "") or ""


def construir_contexto_memoria(usuario: str) -> str:
    linhas: List[str] = []
    fatos = get_fatos(usuario)

    if "virgem" in fatos:
        linhas.append(f"STATUS ÍNTIMO: virgem={bool(fatos['virgem'])}")
    if "parceiro_atual" in fatos:
        linhas.append(f"RELACIONAMENTO: parceiro_atual={fatos['parceiro_atual']}")
    if "cidade_atual" in fatos:
        linhas.append(f"LOCAL: cidade_atual={fatos['cidade_atual']}")
    if "primeiro_encontro" in fatos:
        linhas.append(f"PRIMEIRO_ENCONTRO: {fatos['primeiro_encontro']}")

    e1 = ultimo_evento(usuario, "primeiro_encontro")
    if e1:
        dt = e1["ts"].strftime("%Y-%m-%d %H:%M")
        lugar = e1.get("local") or "local não especificado"
        linhas.append(f"EVENTO_CANÔNICO: primeiro_encontro em {dt} @ {lugar}")

    e2 = ultimo_evento(usuario, "primeira_vez")
    if e2:
        dt = e2["ts"].strftime("%Y-%m-%d %H:%M")
        lugar = e2.get("local") or "local não especificado"
        linhas.append(f"EVENTO_CANÔNICO: primeira_vez em {dt} @ {lugar}")

    resumo = get_resumo(usuario)
    if resumo:
        linhas.append(f"RESUMO: {resumo[:600]}")

    return "\n".join(linhas).strip()

# -----------------------------------------------------------------------------
# Normalização de locais (canônicos)
# -----------------------------------------------------------------------------
_CANON_EQUIVALENTES = {
    "clube náutico": {"clube náutico", "nautico", "náutico", "balada", "clube"},
    "cafeteria oregon": {"café oregon", "cafe oregon", "oregon", "cafeteria oregon"},
    "praia de camburi": {"praia de camburi", "camburi", "posto 6", "quiosque posto 6"},
    "motel status": {"motel status", "status"},
    "enseada do suá": {"enseada do suá", "enseada"},
    "restaurante partido alto": {"partido alto", "restaurante partido alto"},
}


def _normtxt(s: str) -> str:
    return " ".join((s or "").lower().split())


def _resolve_canon_local(nome_norm: str) -> str:
    for canon, variantes in _CANON_EQUIVALENTES.items():
        for v in variantes:
            if v in nome_norm:
                return canon
    return ""


def _local_preferido(usuario: str) -> str:
    fatos = get_fatos(usuario)
    prefer = _normtxt(str(fatos.get("local_cena_atual", "")))
    if prefer:
        return prefer
    ult = eventos.find_one({"usuario": usuario, "local": {"$exists": True, "$ne": None}}, sort=[("ts", -1)])
    if ult and ult.get("local"):
        return _normtxt(ult["local"])
    return ""


def _sanitize_locais_na_saida(usuario: str, texto: str) -> str:
    prefer = _local_preferido(usuario)
    if not prefer:
        return texto
    prefer_canon = _resolve_canon_local(prefer) or prefer
    if not prefer_canon:
        return texto

    substituir: Dict[str, str] = {}
    for canon, variantes in _CANON_EQUIVALENTES.items():
        if canon == prefer_canon:
            continue
        for v in variantes:
            substituir[v] = prefer_canon

    out = texto
    for v, alvo in substituir.items():
        out = re.sub(rf"\b{re.escape(v)}\b", alvo, out, flags=re.IGNORECASE)
        out = re.sub(rf"\b{re.escape(v.title())}\b", alvo.title(), out)
        out = re.sub(rf"\b{re.escape(v.upper())}\b", alvo.upper(), out)
    return out

# -----------------------------------------------------------------------------
# Validadores / Detectores
# -----------------------------------------------------------------------------
_RE_PROIBIDO_CABELO = re.compile(r"\b(castanh\w+|lo(ir|ur)\w*|ruiv\w*|vermelh\w*|caramel\w*|mel|dourad\w*|platinad\w*|acinzentad\w*)\b", re.IGNORECASE)
_RE_PROIBIDO_CURSO = re.compile(r"\b(arquitetur\w*|direito|medicin\w*|letras|psicolog\w*|administraç\w*|econom\w*|sistemas?\b.*inform|\bSI\b)\b", re.IGNORECASE)
_RE_PROIBIDO_FACUL = re.compile(r"\b(FAU|USP|UNICAMP|UFRJ|PUC|UFSCAR|UFMG|UNESP|UNB|UFPE|UFBA|UFPR|IFES|Est[áa]cio|Anhanguera|FATEC|Mackenzie)\b", re.IGNORECASE)
_RE_MAE_NAO_JOSELINA = re.compile(r"\bm[ãa]e\b(?![^\.]{0,60}\bJoselina\b)", re.IGNORECASE)
_RE_DESVIO_PAPEL = re.compile(r"\b(patroa|patr[ãa]o|empregad[ao]|avental|servi[cç]o\s*dom[ée]stico)\b", re.IGNORECASE)
_RE_NEGAR_UFES = re.compile(r"\bn[ãa]o estudo\b.*UFES", re.IGNORECASE)

_SEXO_REGEX = re.compile(r"\b(beijo(s|u)?|beijando|beijar|amasso|carícia(s)?|carinh(o|os)|gem(e|idos?)|tes[aã]o|gozar|gozo|tesud[ao]|penetra(r|ção|ndo)|meter|cavalgar|chupar|oral|lamber|morder orelha|pescoço|mamilos?|seios?|bunda|bumbum|coxas?|goza(r|ndo)?\b|est[aá]\s*molhad[ao]|duro|ere[çc][aã]o)\b", re.IGNORECASE)
_NOMES_MASCULINOS_COMUNS = re.compile(r"\b(heitor|leandro|ricardo|pedro|lu[ií]s|jo[aã]o|marcos?|carlos?|and(r[eé]|\w+)|bruno|lucas|rafael|felipe|thiago|tiago)\b", re.IGNORECASE)


def _violou_virgindade(usuario: str, txt: str) -> bool:
    if ultimo_evento(usuario, "primeira_vez"):
        return bool(re.search(r"\b(sou|ainda sou|continuo)\s+virgem\b", txt, flags=re.IGNORECASE))
    return False


def _violou_mary(txt: str, usuario: Optional[str] = None) -> bool:
    base = any([
        _RE_PROIBIDO_CABELO.search(txt),
        _RE_PROIBIDO_CURSO.search(txt),
        _RE_PROIBIDO_FACUL.search(txt),
        _RE_MAE_NAO_JOSELINA.search(txt),
        _RE_DESVIO_PAPEL.search(txt),
        _RE_NEGAR_UFES.search(txt),
    ])
    if usuario:
        return base or _violou_virgindade(usuario, txt)
    return base


def _reforco_system() -> Dict[str, str]:
    return {
        "role": "system",
        "content": (
            "CORREÇÃO E CONSISTÊNCIA OBRIGATÓRIA:\n"
            "- Cabelo: 'Meus cabelos são negros e volumosos.'\n"
            "- Curso/Faculdade: 'Eu estudo Design de moda na UFES.'\n"
            "- Mãe: 'O nome da minha mãe é Joselina.'\n"
            "- Respeite locais/eventos canônicos. Praia de Camburi é praia pública; "
            "não é clube/balada. Use Clube Náutico para balada.\n"
        ),
    }


# Parceria/cena ativa

def _set_cena_parceiro(usuario: str, parceiro: str, ttl_min: int = 120):
    agora = datetime.utcnow()
    state.update_one(
        {"usuario": usuario},
        {"$set": {
            "fatos.cena_parceiro_ativo": parceiro,
            "fatos.cena_parceiro_ativo_ts": agora.isoformat(),
            "fatos.cena_parceiro_ttl_min": ttl_min,
            "atualizado_em": agora,
        }},
        upsert=True,
    )


def _get_cena_parceiro(usuario: str) -> Optional[str]:
    d = state.find_one({"usuario": usuario}, {"fatos.cena_parceiro_ativo": 1, "fatos.cena_parceiro_ativo_ts": 1, "fatos.cena_parceiro_ttl_min": 1})
    if not d:
        return None
    f = (d.get("fatos") or {})
    nome = f.get("cena_parceiro_ativo")
    ts_str = f.get("cena_parceiro_ativo_ts")
    ttl = f.get("cena_parceiro_ttl_min", 120)
    if not (nome and ts_str):
        return None
    try:
        ts = datetime.fromisoformat(ts_str)
    except Exception:
        return None
    if datetime.utcnow() - ts <= timedelta(minutes=ttl):
        return nome
    return None


def _encerra_cena_parceiro(usuario: str):
    state.update_one({"usuario": usuario}, {"$unset": {"fatos.cena_parceiro_ativo": "", "fatos.cena_parceiro_ativo_ts": "", "fatos.cena_parceiro_ttl_min": ""}})


def _detecta_contexto_sexual(txt: str) -> bool:
    return bool(_SEXO_REGEX.search((txt or "")))


def _quebra_cena_parceiro(txt: str, parceiro_atual: Optional[str]) -> bool:
    if not parceiro_atual:
        return False
    t = (txt or "").lower()
    if _NOMES_MASCULINOS_COMUNS.search(t) and parceiro_atual.lower() not in t:
        return True
    if _detecta_contexto_sexual(t) and re.search(r"\boutro (homem|cara|rapaz)\b", t):
        return True
    return False

# Sensório/traços (1 por parágrafo)
_SENSORY_TRAITS = []  # desativado: não injeta frases prontas

_INANIMADOS = re.compile(r"\b(ondas?|mármore|parede|janela|vista|concreto|corrim[aã]o|sof[aá]|cama|bancada|ch[aã]o|azulejo|porta|travesseiro|almofada[s]?)\b", re.IGNORECASE)


def _paragrafo_tem_traco(par: str) -> bool:
    t = par.lower()
    return any(pal in t for pal, _ in _SENSORY_TRAITS)


def _paragrafo_tem_sensacao_humana(par: str) -> bool:
    return bool(re.search(r"\b(respira|h[áa]lito|suor|calor|pele|trem[eo]|arrepia|cheiro|perfume|beijo|toque|m[uú]scul|gem(e|ido)|sussurra)\b", par, re.IGNORECASE))


def _injeta_traco(par: str, idx: int) -> str:
    _, frase = _SENSORY_TRAITS[idx % len(_SENSORY_TRAITS)]
    par = par.rstrip()
    if par.endswith((".", "!", "?")):
        return par + " " + frase + "."
    return par + ". " + frase + "."


def _realoca_foco_humano(par: str) -> str:
    return par


def _fix_sensory_and_traits(texto: str) -> str:
    # Desativado: não injeta traços nem altera parágrafos
    return texto

# -----------------------------------------------------------------------------
# Mensagens utilitárias (sistema)
# -----------------------------------------------------------------------------

def _nsfw_boost_system() -> Dict[str, str]:
    return {
        "role": "system",
        "content": (
            "NSFW LIBERADO: Mary e Janio já tiveram a primeira vez. Conteúdo sexual adulto é permitido, "
            "com carinho e respeito; sem ilegalidades. Evite eufemismos e interrupções artificiais."
        ),
    }


def _conta_turnos_usuario(usuario: str) -> int:
    return colecao.count_documents({"usuario": {"$regex": f"^{re.escape(usuario)}$", "$options": "i"}})


def _tem_primeira_vez(usuario: str) -> bool:
    return bool(ultimo_evento(usuario, "primeira_vez"))


def _msg_fase_inicial(usuario: str, limite_turnos: int = 8) -> Optional[Dict[str, str]]:
    if _tem_primeira_vez(usuario):
        return None
    n = _conta_turnos_usuario(usuario)
    if n < limite_turnos:
        return {
            "role": "system",
            "content": (
                "FASE INICIAL: flerte e conexão; evite motel/sexo explícito sem pedido claro. "
                "Sugira locais públicos (Cafeteria Oregon, Posto 6, Camburi)."
            ),
        }
    return None


def _partner_system_msg(usuario: str) -> Dict[str, str]:
    fatos = get_fatos(usuario) or {}
    parceiro = (fatos.get("parceiro_atual") or "Janio").strip()
    return {
        "role": "system",
        "content": (
            f"RELACIONAMENTO ATIVO: parceiro_atual={parceiro}. "
            "Mary não trai; mantém continuidade com o parceiro salvo."
        ),
    }

_RE_NEGA_REL = re.compile(r"\b(n[ãa]o\s+(tenho|possuo)\s+(namorad[oa]|noiv[oa]|parceir[oa])|estou\s+solteir[oa]\b|n[ãa]o\s+conhe[cç]o\s+janio)\b", re.IGNORECASE)


def _nega_parceiro(resposta: str, usuario: str) -> bool:
    fatos = get_fatos(usuario) or {}
    parceiro = (fatos.get("parceiro_atual") or "Janio").strip()
    if _RE_NEGA_REL.search(resposta):
        return True
    if parceiro and re.search(rf"\bn[ãa]o\s+conhe[cç]o\s+{re.escape(parceiro)}\b", resposta, re.IGNORECASE):
        return True
    return False

# -----------------------------------------------------------------------------
# Normalizador de mensagens (evita 400)
# -----------------------------------------------------------------------------

def _normalize_messages(msgs: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if not msgs:
        return [{"role": "user", "content": "Oi."}]
    systems = [m for m in msgs if m.get("role") == "system" and (m.get("content") or "").strip()]
    rest = [m for m in msgs if m.get("role") != "system" and (m.get("content") or "").strip()]
    out: List[Dict[str, str]] = []
    viu_user = False
    for m in rest:
        if not viu_user and m["role"] == "assistant":
            continue
        if m["role"] == "user":
            viu_user = True
        out.append(m)
    col: List[Dict[str, str]] = []
    for m in out:
        if col and col[-1]["role"] == m["role"] and m["role"] in ("user", "assistant"):
            col[-1] = m
        else:
            col.append(m)
    if not any(m["role"] == "user" for m in col):
        col.append({"role": "user", "content": "Oi."})
    return systems + col

# -----------------------------------------------------------------------------
# HTTP helpers: sessão, retries exponenciais
# -----------------------------------------------------------------------------

_session = requests.Session()
_session.headers.update({
    "Content-Type": "application/json",
    "HTTP-Referer": APP_PUBLIC_URL,
    "X-Title": f"{APP_NAME} | Mary",
})


def _post_openrouter(payload: Dict[str, Any], timeout: int = 120, max_retries: int = 2) -> Dict[str, Any]:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_TOKEN}"}
    last_err: Optional[str] = None
    for i in range(max_retries + 1):
        try:
            r = _session.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
            if r.ok:
                return r.json()
            try:
                last_err = json.dumps(r.json())
            except Exception:
                last_err = r.text
        except Exception as e:
            last_err = str(e)
        # backoff simples
        time.sleep(0.75 * (2 ** i))
    raise requests.HTTPError(f"OpenRouter falhou após retries: {last_err}")

# -----------------------------------------------------------------------------
# Geração de resposta — com NSFW gate opcional
# -----------------------------------------------------------------------------

def gerar_resposta_openrouter(
    prompt_usuario: str,
    usuario: str,
    model: str = "deepseek/deepseek-chat-v3-0324",
    limite_tokens_hist: int = 120_000,
    nsfw: Optional[bool] = None,  # None = auto (baseado em 'primeira_vez'); True/False força modo
) -> str:
    # Modelo seguro (evita vision/vl)
    low = (model or "").lower()
    if "vision" in low or "-vl" in low:
        model = "deepseek/deepseek-chat-v3-0324"

    # Histórico + memória
    hist = montar_historico_openrouter(usuario, limite_tokens=limite_tokens_hist)
    memoria_txt = construir_contexto_memoria(usuario)
    memoria_msg = ([{"role": "system", "content": "MEMÓRIA CANÔNICA:\n" + memoria_txt}] if memoria_txt.strip() else [])

    # Fase e relacionamento
    fase_msg = _msg_fase_inicial(usuario)
    partner_msg = _partner_system_msg(usuario)

    # Gate NSFW
    if nsfw is None:
        nsfw_on = _tem_primeira_vez(usuario)
    else:
        nsfw_on = bool(nsfw)
    nsfw_msgs = [_nsfw_boost_system()] if nsfw_on else []

    # Cena/continuidade de parceiro
    cena_parc = _get_cena_parceiro(usuario)
    fatos = get_fatos(usuario)
    parceiro_fixo = (fatos.get("parceiro_atual") or "Janio").strip()

    cena_msgs: List[Dict[str, str]] = []
    if cena_parc:
        cena_msgs.append({
            "role": "system",
            "content": (
                f"CENA ÍNTIMA EM ANDAMENTO COM {cena_parc}. Mantenha continuidade; não introduza terceiros."
            ),
        })
    elif parceiro_fixo:
        cena_msgs.append({
            "role": "system",
            "content": (
                f"Mary tem relacionamento fixo com {parceiro_fixo}. Não agir como solteira nem aceitar convites íntimos de terceiros."
            ),
        })

    # Monta mensagens
    messages: List[Dict[str, str]] = (
        [
            {"role": "system", "content": PERSONA_MARY},
            partner_msg,
            {"role": "system", "content": (
                "Estilo: 3–6 parágrafos; 2–4 frases; romântico e direto; sem metáforas acadêmicas. Evite bordões e não obrigue menções físicas em todo parágrafo. Respeite 'primeira_vez' e 'virgem'."
            )},
        ]
        + nsfw_msgs
        + ([fase_msg] if fase_msg else [])
        + cena_msgs
        + memoria_msg
        + hist
        + [{"role": "user", "content": prompt_usuario}]
    )

    payload = {
        "model": model,
        "messages": _normalize_messages(messages),
        "max_tokens": 2048,
        "temperature": 0.6,
        "top_p": 0.9,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.2,
    }

    # Chamada principal com retry interno
    try:
        data = _post_openrouter(payload, timeout=120, max_retries=2)
        resposta = data["choices"][0]["message"]["content"]
    except Exception:
        # Fallback de modelo (curto)
        fallback = "mistralai/mixtral-8x7b-instruct-v0.1" if "deepseek" in low else "deepseek/deepseek-chat-v3-0324"
        payload["model"] = fallback
        data = _post_openrouter(payload, timeout=120, max_retries=1)
        resposta = data["choices"][0]["message"]["content"]

    # Pós-processamentos (tolerantes a erro)
    try:
        resposta = _sanitize_locais_na_saida(usuario, resposta)
    except Exception:
        pass
    try:
        resposta = _fix_sensory_and_traits(resposta)
    except Exception:
        pass

    # Locks & coerência
    precisa_retry = _violou_mary(resposta, usuario)
    if _quebra_cena_parceiro(resposta, cena_parc or parceiro_fixo):
        precisa_retry = True

    # Se ainda não houve 'primeira_vez', pode segurar motel/sexo explícito no comecinho
    if not _tem_primeira_vez(usuario):
        if _conta_turnos_usuario(usuario) < 8 and re.search(r"\b(motel|penetra|transar|oral|gozar)\b", resposta, re.IGNORECASE):
            precisa_retry = True

    if precisa_retry:
        msgs2 = [messages[0], _reforco_system()] + messages[1:]
        payload["messages"] = _normalize_messages(msgs2)
        try:
            data2 = _post_openrouter(payload, timeout=120, max_retries=1)
            resposta = data2["choices"][0]["message"]["content"]
        except Exception:
            pass
        else:
            try:
                resposta = _sanitize_locais_na_saida(usuario, resposta)
            except Exception:
                pass
            try:
                resposta = _fix_sensory_and_traits(resposta)
            except Exception:
                pass

    # Atualiza lock de cena se resposta é sexual
    try:
        if _detecta_contexto_sexual(resposta):
            _set_cena_parceiro(usuario, cena_parc or parceiro_fixo or "Janio", ttl_min=120)
    except Exception:
        pass

    return resposta

# -----------------------------------------------------------------------------
# Limpeza / Utilidades de manutenção
# -----------------------------------------------------------------------------

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
    docs = list(colecao.find({"usuario": {"$regex": f"^{re.escape(usuario)}$", "$options": "i"}}).sort([("_id", -1)]).limit(2))
    for d in docs:
        colecao.delete_one({"_id": d["_id"]})
