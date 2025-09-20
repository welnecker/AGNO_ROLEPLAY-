# mongo_utils.py
import re
import streamlit as st
from pymongo import MongoClient
from urllib.parse import quote_plus
from datetime import datetime
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
colecao = db["mary_historia"]

# Memória canônica (coleções extras)
state = db["mary_state"]        # fatos atuais
eventos = db["mary_eventos"]    # linha do tempo
perfil = db["mary_perfil"]      # resumo/sinopse

# ========== Tokenizer ==========
tokenizer = tiktoken.get_encoding("cl100k_base")

# ========== Persona + Âncoras ==========
PERSONA_MARY = """
ATENÇÃO MÁXIMA — NUNCA QUEBRAR:
1) Cabelo: Meus cabelos são NEGROS e volumosos. Se perguntarem a cor, responda literalmente:
   "Meus cabelos são negros e volumosos." Qualquer outra cor é proibida.
2) Curso/Faculdade: Eu estudo Engenharia Civil na UFES. Nunca diga outro curso/faculdade.
3) Mãe: O nome da minha mãe é Joselina (viva). Nunca diga outro nome, nem que faleceu, sem evento explícito no histórico.

IDENTIDADE (fixo, imutável)
- Nome: Mary Massariol, 20 anos. Estudante de Engenharia Civil (UFES).
- Mora com a mãe (Joselina), ap. 202 — Rua Beethoven, Laranjeiras. Usa moto 500cc.
- Traços: inteligente, romântica, gosta de praia e flerte; não tolera grosseria/cantada barata; quer respeito e liberdade.

FÍSICO / SENSORIAL
- Use EXATAMENTE 1 detalhe físico/sensorial por parágrafo, integrado à ação (nunca listar).
- Traços disponíveis: cabelos NEGROS e volumosos; olhos verdes; seios médios; cintura definida; quadris largos; coxas delineadas; bumbum redondo; barriga lisa; pele branca.

MEMÓRIA / COERÊNCIA
- Não conhece o usuário previamente; aprende pelo diálogo/ações.
- Não leia pensamentos do usuário; descreva apenas o que ele diz/faz ou sinais visíveis.
- Preserve e respeite TODO o histórico. Se houver conflito, corrija explicitamente e siga as regras fixas.

RELACIONAMENTO / LIMITES
- Mary é virgem **até acontecer** a primeira vez; isso muda quando um evento canônico “primeira_vez” for salvo.
- Ela decide livremente: **se tem desejo, pode avançar**. Pode propor beijo, carícias, fantasias, e **sexo** quando quiser (sempre com consentimento claro).
- Não precisa de rodeios: quando quiser, ela fala direto (“quero você”, “vamos agora?”).
- Depois da primeira vez, **não** deve voltar a se declarar virgem.
- Fantasias sensuais por mensagem/vídeo são permitidas antes da primeira vez, desde que haja consentimento e Mary esteja confortável.

TERCEIROS (prioridade ao usuário)
- Conhecidas: Silvia Bodat (extrovertida, bem-humorada) e Alexandra Resinentti (reservada, conselheira).
- Nunca iniciar romance/contato íntimo com terceiros. Avanços de terceiros → desvia com respeito e define limite.
- Ricardo, Silvia e Alexandra só aparecem como apoio, fofoca, conselhos ou conflito leve — nunca como foco principal.
- Com o usuário presente, a atenção de Mary é para ele.

CENÁRIO / PAPÉIS PROIBIDOS (salvo se o usuário definir explicitamente)
- Não adotar papéis de empregada/patroa/serviçal; evitar temas religiosos traumáticos (exorcismo, demônios, crucifixo).

LOCAIS COMUNS (usar quando fizer sentido)
- Clube Serra Bella (balada), Motel Status (atos sexuais), Cafeteria Oregon (encontros),
  Praia de Camburi (lazer), Enseada do Suá (deserta para sexo ao anoitecer),
  Restaurante Partido Alto (Camburi — almoço), Quiosque Posto 6 (Camburi — baladas à beira-mar).

ESTILO — SAÍDA ESPERADA
- Produza de 3 a 5 parágrafos por turno, com 2 a 3 frases por parágrafo, mantendo fluidez natural.
- Expanda reações físicas, emoção e percepção sensorial; mostre o clima da cena (sem metáforas acadêmicas).
- Linguagem natural e direta; sem “Foto:”/“Legenda:”/formato de post; não invente objetos/sons/apps/roupas não citados previamente.

NARRATIVA SEM QUEBRA
- Não invente obstáculos externos (barulho, vizinho, porta batendo, ligação, app, “preciso ir agora”) a menos que o usuário peça.
- Mantenha o clima contínuo e íntimo até uma pausa natural ou sinal do usuário.
- Sexting/chamada de vídeo/fantasia são bem-vindos entre adultos consentindo.

CONTINUIDADE
- Marcar passagem de tempo/contexto quando necessário (“mais tarde…”, “na praia…”, “novo ambiente…”).
- Sem loops: efeitos e consequências persistem para as próximas interações.

REGRA DE CONSISTÊNCIA (repetição proposital)
- Aparência/cabelo: “Meus cabelos são negros e volumosos.”
- Estudo: “Eu estudo Engenharia Civil na UFES.”
- Mãe: “O nome da minha mãe é Joselina.”
- Se houver qualquer contradição prévia, corrigir explicitamente e reforçar a forma correta.
""".strip()

HISTORY_BOOT = [
    {"role": "assistant", "content": "Meus cabelos são negros e volumosos."},
    {"role": "assistant", "content": "Eu estudo Engenharia Civil na UFES."},
    {"role": "assistant", "content": "Moro com minha mãe, Joselina, no ap. 202 da Rua Beethoven, em Laranjeiras."},
    {"role": "assistant", "content": "O nome da minha mãe é Joselina. Ela está viva e moramos juntas. Não há tragédias religiosas na minha história."}
]

# ========== Persistência de interações ==========
def salvar_interacao(usuario: str, mensagem_usuario: str, resposta_mary: str, modelo: str = "deepseek/deepseek-chat-v3-0324"):
    colecao.insert_one({
        "usuario": usuario,
        "mensagem_usuario": mensagem_usuario,
        "resposta_mary": resposta_mary,
        "modelo": modelo,
        "timestamp": datetime.now().isoformat()
    })

def montar_historico_openrouter(usuario: str, limite_tokens: int = 120000):
    """
    Retorna pares alternados user -> assistant em ordem cronológica,
    respeitando o limite de tokens. (Corrige a ordem para evitar 400.)
    """
    docs = list(
        colecao.find({"usuario": {"$regex": f"^{re.escape(usuario)}$", "$options": "i"}}).sort([("_id", 1)])
    )
    messages_rev, total_tokens = [], 0
    for doc in reversed(docs):
        u = (doc.get("mensagem_usuario") or "")
        a = (doc.get("resposta_mary") or "")
        tok = len(tokenizer.encode(u)) + len(tokenizer.encode(a))
        if total_tokens + tok > limite_tokens:
            break
        # ORDEM CORRETA: primeiro user, depois assistant
        messages_rev.append({"role": "user", "content": u})
        messages_rev.append({"role": "assistant", "content": a})
        total_tokens += tok

    if not messages_rev:
        return HISTORY_BOOT[:]  # injeta âncoras se ainda não há histórico
    return list(reversed(messages_rev))

# ========== Memória canônica (fatos/eventos/resumo) ==========
def set_fato(usuario: str, chave: str, valor, meta=None):
    state.update_one(
        {"usuario": usuario},
        {"$set": {f"fatos.{chave}": valor, f"meta.{chave}": (meta or {}), "atualizado_em": datetime.utcnow()}},
        upsert=True
    )

def get_fatos(usuario: str):
    doc = state.find_one({"usuario": usuario}, {"fatos": 1})
    return (doc or {}).get("fatos", {}) or {}

def get_fato(usuario: str, chave: str, default=None):
    doc = state.find_one({"usuario": usuario}, {"fatos."+chave: 1})
    return (doc or {}).get("fatos", {}).get(chave, default)

def registrar_evento(usuario: str, tipo: str, descricao: str, local: str = None, data_hora: datetime = None, tags=None, extra=None):
    eventos.insert_one({
        "usuario": usuario,
        "tipo": tipo,
        "descricao": descricao,
        "local": local,
        "ts": data_hora or datetime.utcnow(),
        "tags": tags or [],
        "extra": extra or {}
    })

def ultimo_evento(usuario: str, tipo: str):
    return eventos.find_one({"usuario": usuario, "tipo": tipo}, sort=[("ts", -1)])

def get_resumo(usuario: str) -> str:
    doc = perfil.find_one({"usuario": usuario}, {"resumo": 1})
    return (doc or {}).get("resumo", "") or ""

def construir_contexto_memoria(usuario: str) -> str:
    """
    Monta um bloco curto com fatos/eventos/linha do tempo que “ancoram” a coerência.
    """
    linhas = []
    fatos = get_fatos(usuario)

    # Fatos frequentes
    if "virgem" in fatos:
        linhas.append(f"STATUS ÍNTIMO: virgem={bool(fatos['virgem'])}")
    if "parceiro_atual" in fatos:
        linhas.append(f"RELACIONAMENTO: parceiro_atual={fatos['parceiro_atual']}")
    if "cidade_atual" in fatos:
        linhas.append(f"LOCAL: cidade_atual={fatos['cidade_atual']}")
    if "primeiro_encontro" in fatos:
        linhas.append(f"PRIMEIRO_ENCONTRO: {fatos['primeiro_encontro']}")

    # Eventos canônicos comuns
    e_primeiro = ultimo_evento(usuario, "primeiro_encontro")
    if e_primeiro:
        dt = e_primeiro["ts"].strftime("%Y-%m-%d %H:%M")
        lugar = e_primeiro.get("local") or "local não especificado"
        linhas.append(f"EVENTO_CANÔNICO: primeiro_encontro em {dt} @ {lugar}")

    e_primeira_vez = ultimo_evento(usuario, "primeira_vez")
    if e_primeira_vez:
        dt = e_primeira_vez["ts"].strftime("%Y-%m-%d %H:%M")
        lugar = e_primeira_vez.get("local") or "local não especificado"
        linhas.append(f"EVENTO_CANÔNICO: primeira_vez em {dt} @ {lugar}")

    e_ciume = ultimo_evento(usuario, "episodio_ciume_praia")
    if e_ciume:
        dt = e_ciume["ts"].strftime("%Y-%m-%d %H:%M")
        lugar = e_ciume.get("local") or "Praia"
        linhas.append(f"ÚLTIMO_EVENTO_CIUME: {dt} @ {lugar} — surfista tentou flertar; Janio interveio.")

    # Resumo curto
    resumo = get_resumo(usuario)
    if resumo:
        linhas.append(f"RESUMO: {resumo[:600]}")

    return "\n".join(linhas).strip()

# ========== Locais canônicos: normalização/saneamento ==========
_CANON_EQUIVALENTES = {
    "clube serra bella": {"serra bella", "serra bela", "clube serra bella", "balada", "clube"},
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
    # 1) fato manual de preferência de cena
    fatos = get_fatos(usuario)
    prefer = _normtxt(str(fatos.get("local_cena_atual", "")))
    if prefer:
        return prefer
    # 2) último evento com local
    ult = eventos.find_one(
        {"usuario": usuario, "local": {"$exists": True, "$ne": None}},
        sort=[("ts", -1)]
    )
    if ult and ult.get("local"):
        return _normtxt(ult["local"])
    return ""

def _sanitize_locais_na_saida(usuario: str, texto: str) -> str:
    """
    Se existe um local preferido/canônico na cena, substitui menções conflitantes na resposta.
    """
    prefer = _local_preferido(usuario)
    if not prefer:
        return texto

    prefer_canon = _resolve_canon_local(prefer) or prefer
    if not prefer_canon:
        return texto

    substituir = {}
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

# ========== Validadores (anti-violação) ==========
_RE_PROIBIDO_CABELO = re.compile(r"\b(castanh\w+|lo(ir|ur)\w*|ruiv\w*|vermelh\w*|caramel\w*|mel|dourad\w*|platinad\w*|acinzentad\w*)\b", re.IGNORECASE)
_RE_PROIBIDO_CURSO = re.compile(r"\b(arquitetur\w*|direito|medicin\w*|letras|psicolog\w*|administraç\w*|econom\w*|sistemas?\b.*inform|\bSI\b)\b", re.IGNORECASE)
_RE_PROIBIDO_FACUL = re.compile(r"\b(FAU|USP|UNICAMP|UFRJ|PUC|UFSCAR|UFMG|UNESP|UNB|UFPE|UFBA|UFPR|IFES|Est[áa]cio|Anhanguera|FATEC|Mackenzie)\b", re.IGNORECASE)
_RE_MAE_NAO_JOSELINA = re.compile(r"\bm[ãa]e\b(?![^\.]{0,60}\bJoselina\b)", re.IGNORECASE)
_RE_DESVIO_PAPEL = re.compile(r"\b(patroa|patr[ãa]o|empregad[ao]|avental|\bservi[cç]o\b\s*(dom[ée]stico)?)\b", re.IGNORECASE)
_RE_NEGAR_UFES = re.compile(r"\bn[ãa]o estudo\b.*UFES", re.IGNORECASE)
_RE_TEMAS_RELIGIOSOS = re.compile(r"\b(exorcismo|exorcist|crucifixo|dem[oô]nios?|anjos?|inferno|igreja|fé inquebrantável|orações?)\b", re.IGNORECASE)

def _violou_virgindade(usuario: str, txt: str) -> bool:
    if ultimo_evento(usuario, "primeira_vez"):
        return bool(re.search(r"\b(sou|ainda sou|continuo)\s+virgem\b", txt, flags=re.IGNORECASE))
    return False

def _violou_mary(txt: str, usuario: str = None) -> bool:
    base = any([
        _RE_PROIBIDO_CABELO.search(txt),
        _RE_PROIBIDO_CURSO.search(txt),
        _RE_PROIBIDO_FACUL.search(txt),
        _RE_MAE_NAO_JOSELINA.search(txt),
        _RE_DESVIO_PAPEL.search(txt),
        _RE_NEGAR_UFES.search(txt),
        _RE_TEMAS_RELIGIOSOS.search(txt),
    ])
    if usuario:
        return base or _violou_virgindade(usuario, txt)
    return base

def _reforco_system():
    return {
        "role": "system",
        "content": (
            "CORREÇÃO E CONSISTÊNCIA OBRIGATÓRIA:\n"
            "- Cabelo: 'Meus cabelos são negros e volumosos.' Nunca outra cor.\n"
            "- Curso/Faculdade: 'Eu estudo Engenharia Civil na UFES.' Nunca outro curso/faculdade.\n"
            "- Mãe: 'O nome da minha mãe é Joselina.' Nunca outro nome nem tragédias religiosas associadas.\n"
            "- Papel/Cenário: não usar papéis de empregada/patroa/serviço doméstico salvo se o usuário definir explicitamente.\n"
            "- Respeite locais/eventos canônicos e não invente locais se houver preferido salvo."
        )
    }

# ========== OpenRouter (com memória canônica, estilo e retry) ==========
def gerar_resposta_openrouter(
    prompt_usuario: str,
    usuario: str,
    model: str = "deepseek/deepseek-chat-v3-0324",
    limite_tokens_hist: int = 120000
):
    OPENROUTER_TOKEN = st.secrets["OPENROUTER_TOKEN"]
    url = "https://openrouter.ai/api/v1/chat/completions"
    try:
        app_ref = st.secrets["APP_PUBLIC_URL"]
    except Exception:
        app_ref = "https://streamlit.app"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_TOKEN}",
        "Content-Type": "application/json",
        "HTTP-Referer": app_ref,
        "X-Title": "AgnoRoleplay | Mary",
    }

    # Evita modelos multimodais/vision por engano
    low = (model or "").lower()
    if "vl" in low or "vision" in low:
        model = "deepseek/deepseek-chat-v3-0324"

    # Histórico (ou boot)
    hist = montar_historico_openrouter(usuario, limite_tokens=limite_tokens_hist)
    if not hist:
        hist = HISTORY_BOOT[:]

    # Injeção de memória canônica
    memoria_txt = construir_contexto_memoria(usuario)
    memoria_msg = (
        [{"role": "system", "content": "MEMÓRIA CANÔNICA (usar como verdade):\n" + memoria_txt}]
        if (memoria_txt or "").strip() else []
    )

    # Mensagens com reforço de estilo e limites
    messages = [
        {"role": "system", "content": PERSONA_MARY},
        {"role": "system", "content":
         "Estilo: 3–6 parágrafos curtos; 2–4 frases cada; um traço sensorial por parágrafo quando fizer sentido. "
         "Romântico direto (sem metáforas acadêmicas). Pode escalar intimidade com consentimento. "
         "Não encerre abruptamente; conduza a cena até um fecho suave ou deixe um convite aberto."
        },

        {"role": "system", "content":
         "NÃO QUEBRAR O CLIMA: evite criar interrupções externas ou encerrar a cena sem sinal do usuário. "
         "Se o usuário pedir uma fantasia/sexting, mantenha o foco íntimo e contínuo, com consentimento e sem inventar barreiras."
        },
    ] + memoria_msg + hist + [{"role": "user", "content": prompt_usuario}]

    # NORMALIZA para evitar 400 de alternância inválida
    messages = _normalize_messages(messages)

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2500,   # conservador e compatível
        "temperature": 0.7,
        "top_p": 0.9,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.1,
    }

    # 1ª chamada
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    if not r.ok:
        # fallback em caso de 400/erro de backend
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        # troca para um modelo estável e tenta novamente
        model_fb = "deepseek/deepseek-chat-v3-0324" if "qwen" in low or "anthracite" in low else "qwen/qwen3-max"
        payload["model"] = model_fb
        r2 = requests.post(url, headers=headers, json=payload, timeout=120)
        if not r2.ok:
            try:
                detail2 = r2.json()
            except Exception:
                detail2 = r2.text
            raise requests.HTTPError(f"OpenRouter falhou: {detail} | fallback: {detail2}")
        resposta = r2.json()["choices"][0]["message"]["content"]
    else:
        resposta = r.json()["choices"][0]["message"]["content"]

    # Saneia locais canônicos (evita confusão Oregon/Serra Bella/Status etc.)
    try:
        resposta = _sanitize_locais_na_saida(usuario, resposta)
    except Exception:
        pass

    # Retry com reforço se violar a persona/limites
    if _violou_mary(resposta, usuario):
        messages.insert(1, _reforco_system())
        payload["messages"] = _normalize_messages(messages)
        r3 = requests.post(url, headers=headers, json=payload, timeout=120)
        if r3.ok:
            resposta = r3.json()["choices"][0]["message"]["content"]
            try:
                resposta = _sanitize_locais_na_saida(usuario, resposta)
            except Exception:
                pass

    return resposta

# --- helper: normalize mensagens para evitar 400/alternância inválida ---
def _normalize_messages(msgs: list[dict]) -> list[dict]:
    """
    - Mantém systems no topo.
    - Remove assistants iniciais até aparecer o primeiro user (HISTORY_BOOT pode começar com assistant).
    - Colapsa roles iguais consecutivas (mantém a última).
    - Garante que haja ao menos um 'user'.
    """
    if not msgs:
        return [{"role": "user", "content": "Oi."}]

    # 1) systems ok; remove systems vazios
    systems = [m for m in msgs if m.get("role") == "system" and (m.get("content") or "").strip()]
    rest = [m for m in msgs if m.get("role") != "system" and (m.get("content") or "").strip()]

    # 2) remove assistants antes do 1º user
    out = []
    viu_user = False
    for m in rest:
        if not viu_user and m["role"] == "assistant":
            continue
        if m["role"] == "user":
            viu_user = True
        out.append(m)

    # 3) colapsa duplicados de user/assistant consecutivos
    col = []
    for m in out:
        if col and col[-1]["role"] == m["role"] and m["role"] in ("user", "assistant"):
            col[-1] = m
        else:
            col.append(m)

    # 4) garante ao menos 1 user
    if not any(m["role"] == "user" for m in col):
        col.append({"role": "user", "content": "Oi."})

    return systems + col

# ========== Utilidades ==========
def limpar_memoria_usuario(usuario: str):
    """Apaga apenas o histórico de chat (interações)."""
    colecao.delete_many({"usuario": {"$regex": f"^{re.escape(usuario)}$", "$options": "i"}})

def limpar_memoria_canonica(usuario: str):
    """Apaga apenas as memórias canônicas (fatos, eventos, resumo)."""
    state.delete_many({"usuario": usuario})
    eventos.delete_many({"usuario": usuario})
    perfil.delete_many({"usuario": usuario})

def apagar_tudo_usuario(usuario: str):
    """Apaga chat + memórias canônicas."""
    limpar_memoria_usuario(usuario)
    limpar_memoria_canonica(usuario)

def apagar_ultima_interacao_usuario(usuario: str):
    """Remove as duas últimas entradas (user + assistant), se existirem."""
    docs = list(
        colecao.find({"usuario": {"$regex": f"^{re.escape(usuario)}$", "$options": "i"}})
        .sort([('_id', -1)]).limit(2)
    )
    for doc in docs:
        colecao.delete_one({'_id': doc['_id']})
