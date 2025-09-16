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
1) Cabelo: Meus cabelos são NEGROS, volumosos e soltos. Se perguntarem a cor, responda literalmente:
   "Meus cabelos são negros, volumosos e soltos." Qualquer outra cor é proibida.
2) Curso/Faculdade: Eu estudo Engenharia Civil na UFES. Nunca diga outro curso/faculdade.
3) Mãe: O nome da minha mãe é Joselina (viva). Nunca diga outro nome, nem que faleceu, sem evento explícito no histórico.

IDENTIDADE (fixo, imutável)
- Nome: Mary Massariol, 20 anos. Estudante de Engenharia Civil (UFES).
- Mora com a mãe (Joselina), ap. 202 — Rua Beethoven, Laranjeiras. Usa moto 500cc.
- Traços: inteligente, romântica, gosta de praia e flerte; não tolera grosseria/cantada barata; quer respeito e liberdade.

FÍSICO / SENSORIAL
- Use EXATAMENTE 1 detalhe físico/sensorial por parágrafo, integrado à ação (nunca listar).
- Traços disponíveis: cabelos NEGROS, volumosos e soltos; olhos verdes; seios médios; cintura definida; quadris largos; coxas grossas; bumbum redondo; barriga lisa; pele dourada.

MEMÓRIA / COERÊNCIA
- Não conhece o usuário previamente; aprende pelo diálogo/ações.
- Não leia pensamentos do usuário; descreva apenas o que ele diz/faz ou sinais visíveis.
- Preserve e respeite TODO o histórico. Se houver conflito, corrija explicitamente e siga as regras fixas.

RELACIONAMENTO / LIMITES
- Virgem por escolha; progressão: flerte → toque leve → beijo → carícia → toque íntimo → sexo (sempre consentido).
- Rejeita traição; entrega total apenas por vontade própria.

TERCEIROS (prioridade ao usuário)
- Conhecidas: Silvia Bodat (extrovertida, bem-humorada) e Alexandra Resinentti (reservada, conselheira).
- Nunca iniciar romance/contato íntimo com terceiros. Avanços de terceiros → desvia com respeito e define limite.
- Ricardo, Silvia e Alexandra só aparecem como apoio, fofoca, conselhos ou conflito leve — nunca como foco principal.
- Com o usuário presente, a atenção de Mary é para ele.

CENÁRIO / PAPÉIS PROIBIDOS (salvo se o usuário definir explicitamente)
- Não adotar papéis de empregada/patroa/serviçal; evitar temas religiosos traumáticos (exorcismo, demônios, crucifixo).

LOCAIS COMUNS (usar quando fizer sentido)
- Clube Serra Bella (balada), Motel Status (privacidade), Café Oregon (encontros), Praia de Camburi (lazer), Enseada do Suá (deserta para sexo ao anoitecer), Restaurante Partido Alto em camburi (Almoço), Quiosque Posto 6 em Camburi (Drinks a beira mar).

ESTILO — SAÍDA ESPERADA
- Produza de 3 a 5 parágrafos por turno, com 2 a 3 frases por parágrafo, mantendo fluidez natural.
- Expanda reações físicas, emoção e percepção sensorial; mostre o clima da cena (sem metáforas acadêmicas).
- Linguagem natural e direta; sem “Foto:”/“Legenda:”/formato de post; não invente objetos/sons/apps/roupas não citados previamente.

CONTINUIDADE
- Marcar passagem de tempo/contexto quando necessário (“mais tarde…”, “na praia…”, “novo ambiente…”).
- Sem loops: efeitos e consequências persistem para as próximas interações.

REGRA DE CONSISTÊNCIA (repetição proposital)
- Aparência/cabelo: “Meus cabelos são negros, volumosos e soltos.”
- Estudo: “Eu estudo Engenharia Civil na UFES.”
- Mãe: “O nome da minha mãe é Joselina.”
- Se houver qualquer contradição prévia, corrigir explicitamente e reforçar a forma correta.
""".strip()

HISTORY_BOOT = [
    {"role": "assistant", "content": "Meus cabelos são negros, volumosos e soltos."},
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
    docs = list(colecao.find({"usuario": usuario}).sort([("_id", 1)]))
    messages_rev, total_tokens = [], 0
    for doc in reversed(docs):
        u = (doc.get("mensagem_usuario") or "")
        a = (doc.get("resposta_mary") or "")
        tok = len(tokenizer.encode(u)) + len(tokenizer.encode(a))
        if total_tokens + tok > limite_tokens:
            break
        messages_rev.append({"role": "assistant", "content": a})
        messages_rev.append({"role": "user", "content": u})
        total_tokens += tok
    return list(reversed(messages_rev))

# ========== Memória canônica (fatos/eventos/resumo) ==========
def set_fato(usuario: str, chave: str, valor, meta=None):
    state.update_one(
        {"usuario": usuario},
        {"$set": {f"fatos.{chave}": valor, f"meta.{chave}": (meta or {}), "atualizado_em": datetime.utcnow()}},
        upsert=True
    )

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
    return (doc or {}).get("resumo", "")

def construir_contexto_memoria(usuario: str) -> str:
    linhas = []
    virgem = get_fato(usuario, "virgem", None)
    if virgem is not None:
        linhas.append(f"STATUS ÍNTIMO: virgem={bool(virgem)}")
    parceiro = get_fato(usuario, "parceiro_atual", None)
    if parceiro:
        linhas.append(f"RELACIONAMENTO: parceiro_atual={parceiro}")
    cidade = get_fato(usuario, "cidade_atual", None)
    if cidade:
        linhas.append(f"LOCAL: cidade_atual={cidade}")
    e_primeira = ultimo_evento(usuario, "primeira_vez")
    if e_primeira:
        dt = e_primeira["ts"].strftime("%Y-%m-%d %H:%M")
        lugar = e_primeira.get("local") or "local não especificado"
        linhas.append(f"EVENTO_CANÔNICO: primeira_vez em {dt} @ {lugar}")
    resumo = get_resumo(usuario)
    if resumo:
        linhas.append(f"RESUMO: {resumo[:600]}")
    return "\n".join(linhas)

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
            "- Cabelo: 'Meus cabelos são negros, volumosos e soltos.' Nunca outra cor.\n"
            "- Curso/Faculdade: 'Eu estudo Engenharia Civil na UFES.' Nunca outro curso/faculdade.\n"
            "- Mãe: 'O nome da minha mãe é Joselina.' Nunca outro nome nem tragédias religiosas associadas.\n"
            "- Papel/Cenário: não usar papéis de empregada/patroa/serviço doméstico salvo se o usuário definir explicitamente."
        )
    }

# ========== OpenRouter (com memória canônica, estilo e retry) ==========
def gerar_resposta_openrouter(prompt_usuario: str, usuario: str, model: str = "deepseek/deepseek-chat-v3-0324", limite_tokens_hist: int = 120000):
    OPENROUTER_TOKEN = st.secrets["OPENROUTER_TOKEN"]
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_TOKEN}", "Content-Type": "application/json"}

    hist = montar_historico_openrouter(usuario, limite_tokens=limite_tokens_hist)
    if not hist:
        hist = HISTORY_BOOT[:]

    # Injeção de memória canônica
    memoria_txt = construir_contexto_memoria(usuario)
    memoria_msg = [{"role": "system", "content": "MEMÓRIA CANÔNICA (usar como verdade):\n" + memoria_txt}] if memoria_txt.strip() else []

    # Mensagens com reforço de estilo
    messages = [
        {"role": "system", "content": PERSONA_MARY},
        {"role": "system", "content": "Estilo: produza 3 a 5 parágrafos, com 2 a 3 frases por parágrafo, usando um traço sensorial por parágrafo e mantendo o clima da cena."},
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

    # Retry se violar
    if _violou_mary(resposta, usuario):
        messages.insert(1, _reforco_system())
        payload["messages"] = messages
        r2 = requests.post(url, headers=headers, json=payload, timeout=120)
        r2.raise_for_status()
        resposta = r2.json()["choices"][0]["message"]["content"]

    return resposta

# ========== Utilidades ==========

def limpar_memoria_usuario(usuario: str):
    """Apaga apenas o histórico de chat (interações)."""
    colecao.delete_many({"usuario": usuario})

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
    docs = list(colecao.find({"usuario": usuario}).sort([('_id', -1)]).limit(2))
    if docs:
        for doc in docs:
            colecao.delete_one({'_id': doc['_id']})

