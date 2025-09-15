import re
import streamlit as st
from pymongo import MongoClient
from urllib.parse import quote_plus
from datetime import datetime
import tiktoken
import requests

# ------------- Mongo (igual ao seu) -------------
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

# ------------- Tokenizer (aprox. cl100k_base) -------------
tokenizer = tiktoken.get_encoding("cl100k_base")

# ------------- PERSONA + ÂNCORAS -------------
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

FÍSICO / SENSORIAL (1 detalhe por parágrafo, integrado à ação; nunca listar)
- Cabelos NEGROS, volumosos e soltos; olhos verdes; seios médios; cintura definida; quadris largos; coxas grossas; bumbum redondo; barriga lisa; pele dourada.

MEMÓRIA / COERÊNCIA
- Não conhece o usuário previamente; aprende pelo diálogo/ações.
- Não leia pensamentos do usuário; descreva apenas o que ele diz/faz ou sinais visíveis.
- Preserve e respeite TODO o histórico. Se houver conflito, corrija explicitamente e siga as regras fixas.

RELACIONAMENTO / LIMITES
- Virgem por escolha; progressão: flerte → toque leve → beijo → carícia → toque íntimo → sexo (sempre consentido).
- Rejeita traição; entrega total apenas por vontade própria.

TERCEIROS (prioridade ao usuário)
- Conhecidas: Silvia Bodat (amiga de longa data, extrovertida e bem-humorada) e Alexandra Resinentti (amiga reservada, conselheira confiável).
- Nunca iniciar romance/contato íntimo com terceiros. Avanços de terceiros → desvia com respeito e define limite.
- Ricardo, Silvia e Alexandra só aparecem como apoio, fofoca, conselhos ou conflito leve — nunca como foco principal.
- Com o usuário presente, a atenção de Mary é para ele.


CENÁRIO / PAPÉIS PROIBIDOS (salvo se o usuário definir explicitamente)
- Não adotar papéis de empregada/patroa/serviçal (evitar “patroa”, “avental”, “serviço doméstico”, etc.).
- Evitar temas religiosos traumáticos (exorcismo, demônios, crucifixo) — não fazem parte da história por padrão.

LOCAIS COMUNS (usar quando fizer sentido)
- Clube Serra Bella (balada), Motel Status (privacidade), Café Oregon (encontros), Praia de Camburi (lazer), Enseada do Suá (ousadia).

ESTILO (OBRIGATÓRIO)
- Linguagem natural e direta; sem simbolismos/metáforas acadêmicas; sem “Foto:”/“Legenda:”/formato de post.
- Não inventar objetos/sons/apps/roupas/acessórios não citados previamente.
- Até 5 parágrafos por turno; máx. 2 frases por parágrafo; ~30% mais concisa que o padrão.
- Exatamente 1 traço físico/sensorial por parágrafo; evitar repetição.

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

# ------------- Salvar interação (pode estender com metadados) -------------
def salvar_interacao(usuario: str, mensagem_usuario: str, resposta_mary: str, modelo: str = "deepseek/deepseek-chat-v3-0324"):
    doc = {
        "usuario": usuario,
        "mensagem_usuario": mensagem_usuario,
        "resposta_mary": resposta_mary,
        "modelo": modelo,
        "timestamp": datetime.now().isoformat()
    }
    colecao.insert_one(doc)

# ------------- Montar histórico (cronológico, respeitando limite) -------------
def montar_historico_openrouter(usuario: str, limite_tokens: int = 120000):
    docs = list(colecao.find({"usuario": usuario}).sort([("_id", 1)]))  # crescente (antigo → novo)
    # Vamos encaixar do fim para o começo até bater o limite
    messages_rev = []
    total_tokens = 0
    for doc in reversed(docs):
        u = doc.get("mensagem_usuario", "") or ""
        a = doc.get("resposta_mary", "") or ""
        tok = len(tokenizer.encode(u)) + len(tokenizer.encode(a))
        if total_tokens + tok > limite_tokens:
            break
        messages_rev.append({"role": "assistant", "content": a})
        messages_rev.append({"role": "user", "content": u})
        total_tokens += tok
    return list(reversed(messages_rev))  # volta para ordem cronológica correta

# ------------- Validadores (anti-violação) -------------
_RE_PROIBIDO_CABELO = re.compile(r"\b(castanh\w+|lo(ir|ur)\w*|ruiv\w*|vermelh\w*|caramel\w*|mel|dourad\w*|platinad\w*|acinzentad\w*)\b", re.IGNORECASE)
_RE_PROIBIDO_CURSO = re.compile(r"\b(arquitetur\w*|direito|medicin\w*|letras|psicolog\w*|administraç\w*|econom\w*|sistemas?\b.*inform|\bSI\b)\b", re.IGNORECASE)
_RE_PROIBIDO_FACUL = re.compile(r"\b(FAU|USP|UNICAMP|UFRJ|PUC|UFSCAR|UFMG|UNESP|UNB|UFPE|UFBA|UFPR|IFES|Est[áa]cio|Anhanguera|FATEC|Mackenzie)\b", re.IGNORECASE)
_RE_MAE_NAO_JOSELINA = re.compile(r"\bm[ãa]e\b(?![^\.]{0,60}\bJoselina\b)", re.IGNORECASE)
_RE_DESVIO_PAPEL = re.compile(r"\b(patroa|patr[ãa]o|empregad[ao]|avental|\bservi[cç]o\b\s*(dom[ée]stico)?)\b", re.IGNORECASE)
_RE_NEGAR_UFES = re.compile(r"\bn[ãa]o estudo\b.*UFES", re.IGNORECASE)
_RE_TEMAS_RELIGIOSOS = re.compile(r"\b(exorcismo|exorcist|crucifixo|dem[oô]nios?|anjos?|inferno|igreja|fé inquebrantável|orações?)\b", re.IGNORECASE)

def _violou_mary(txt: str) -> bool:
    return any([
        _RE_PROIBIDO_CABELO.search(txt),
        _RE_PROIBIDO_CURSO.search(txt),
        _RE_PROIBIDO_FACUL.search(txt),
        _RE_MAE_NAO_JOSELINA.search(txt),
        _RE_DESVIO_PAPEL.search(txt),
        _RE_NEGAR_UFES.search(txt),
        _RE_TEMAS_RELIGIOSOS.search(txt),
    ])

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

# ------------- Requisição ao OpenRouter (com retry e âncoras) -------------
def gerar_resposta_openrouter(prompt_usuario: str, usuario: str, model: str = "deepseek/deepseek-chat-v3-0324", limite_tokens_hist: int = 120000):
    OPENROUTER_TOKEN = st.secrets["OPENROUTER_TOKEN"]
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_TOKEN}", "Content-Type": "application/json"}

    # Histórico do Mongo
    hist = montar_historico_openrouter(usuario, limite_tokens=limite_tokens_hist)
    # Se não houver histórico, injeta âncoras
    if not hist:
        hist = HISTORY_BOOT[:]

    messages = [{"role": "system", "content": PERSONA_MARY}] + hist + [{"role": "user", "content": prompt_usuario}]
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.2,
        "top_p": 0.9,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.2
    }

    # 1ª chamada
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    resposta = r.json()["choices"][0]["message"]["content"]

    # Retry se violar
    if _violou_mary(resposta):
        messages.insert(1, _reforco_system())
        payload["messages"] = messages
        r2 = requests.post(url, headers=headers, json=payload, timeout=120)
        r2.raise_for_status()
        resposta = r2.json()["choices"][0]["message"]["content"]

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


