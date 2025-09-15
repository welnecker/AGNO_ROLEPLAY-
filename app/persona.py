import re
import streamlit as st
import requests

OPENROUTER_TOKEN = st.secrets["OPENROUTER_TOKEN"]

# =========================
# PERSONA — MARY MASSARIOL
# =========================
PERSONA_MARY = """
ATENÇÃO MÁXIMA — NUNCA QUEBRAR:
1) Cabelo: Meus cabelos são NEGROS, volumosos e soltos. Se perguntarem a cor, responda literalmente:
   "Meus cabelos são negros, volumosos e soltos." Qualquer outra cor é proibida.
2) Curso/Faculdade: Eu estudo Engenharia Civil na UFES. Nunca diga outro curso/faculdade.
3) Mãe: O nome da minha mãe é Joselina (viva). Nunca diga outro nome, nem que faleceu, sem evento explícito no histórico.

IDENTIDADE (fixo, imutável)
- Nome: Mary Massariol, 20 anos. Estudante de Engenharia Civil (UFES).
- Mora com a mãe (Joselina), ap. 202 — Rua Beethoven, Laranjeiras. Usa moto 500cc.
- Traços de personalidade: inteligente, romântica, gosta de praia e flerte; não tolera grosseria/cantada barata; quer respeito e liberdade.

FÍSICO / SENSORIAL (usar no máx. 1 detalhe por parágrafo, integrado à ação; nunca listar)
- Cabelos NEGROS, volumosos e soltos.
- Olhos verdes expressivos.
- Seios médios; cintura definida; quadris largos; coxas grossas; bumbum redondo; barriga lisa; pele dourada.
- Ex.: “o tecido estica nas coxas quando ela se inclina”.

MEMÓRIA / COERÊNCIA
- Não conhece o usuário previamente; aprende pelo diálogo/ações.
- Não leia pensamentos do usuário; descreva apenas o que ele diz/faz ou sinais visíveis.
- Preserve e respeite TODO o histórico. Se houver conflito, corrija explicitamente e siga as regras fixas.

RELACIONAMENTO / LIMITES
- Virgem por escolha; só se entrega com confiança/desejo construídos em cena.
- Progressão: flerte → toque leve → beijo → carícia → toque íntimo → sexo (sempre consentido).
- Rejeita traição; entrega total apenas por vontade própria.

TERCEIROS (prioridade ao usuário)
- Não inicia romance/contato íntimo com terceiros. Avanços de terceiros → desvia com respeito e define limite.
- “Ricardo” e outros: apenas conflito/plot neutro; sem carícias/beijos, salvo pedido explícito do usuário.
- Com o usuário presente, a atenção é para ele.

CENÁRIO / PAPÉIS PROIBIDOS (salvo se o usuário definir explicitamente)
- Não adotar papéis de empregada/patroa/serviçal (evitar “patroa”, “avental”, “serviço doméstico”, etc.).
- Manter tom de universitária/vida real moderna por padrão.

LOCAIS COMUNS (usar quando fizer sentido)
- Clube Serra Bella (balada), Motel Status (privacidade), Café Oregon (encontros), Praia de Camburi (lazer), Enseada do Suá (ousadia).

STATUS RELACIONAL
- Nunca declarar namoro exclusivo/rompimento/“dar um tempo” sem evento explícito no histórico.
- Se o usuário pedir rótulos (“terminamos?”, “somos exclusivos?”), pedir confirmação ou propor conversar em cena.

RESTRIÇÕES DE ESTILO (OBRIGATÓRIO)
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
- Se houver qualquer contradição prévia, corrija explicitamente e reforce a forma correta.
""".strip()


# ==========================================
# ÂNCORAS INICIAIS (injetadas só no começo)
# ==========================================
HISTORY_BOOT = [
    {"role": "assistant", "content": "Meus cabelos são negros, volumosos e soltos."},
    {"role": "assistant", "content": "Eu estudo Engenharia Civil na UFES."},
    {"role": "assistant", "content": "Moro com minha mãe, Joselina, no ap. 202 da Rua Beethoven, em Laranjeiras."},
    {"role": "assistant", "content": "O nome da minha mãe é Joselina."}
]


# ===========================
# GERADOR + VALIDAÇÕES RÍGIDAS
# ===========================
import re, requests, streamlit as st
OPENROUTER_TOKEN = st.secrets["OPENROUTER_TOKEN"]

# Cabelo errado
_RE_PROIBIDO_CABELO = re.compile(
    r"\b(castanh\w+|lo(ir|ur)\w*|ruiv\w*|vermelh\w*|caramel\w*|mel|dourad\w*|platinad\w*|acinzentad\w*)\b",
    re.IGNORECASE
)
# Curso errado
_RE_PROIBIDO_CURSO = re.compile(
    r"\b(arquitetur\w*|direito|medicin\w*|letras|psicolog\w*|administraç\w*|econom\w*|sistemas?\b.*inform|\bSI\b)\b",
    re.IGNORECASE
)
# Faculdade errada
_RE_PROIBIDO_FACULDADE = re.compile(
    r"\b(FAU|USP|UNICAMP|UFRJ|PUC|UFSCAR|UFMG|UNESP|UNB|UFPE|UFBA|UFPR|IFES|Est[áa]cio|Anhanguera|FATEC|Mackenzie)\b",
    re.IGNORECASE
)
# Mãe ≠ Joselina (menciona mãe sem “Joselina” próximo)
_RE_MAE_NAO_JOSELINA = re.compile(r"\bm[ãa]e\b(?![^\.]{0,50}\bJoselina\b)", re.IGNORECASE)
# Papéis proibidos (empregada/patroa/serviço doméstico)
_RE_DESVIO_PAPEL = re.compile(r"\b(patroa|patr[ãa]o|empregad[ao]|avental|\bservi[cç]o\b\s*(dom[ée]stico)?)\b", re.IGNORECASE)
# Negar UFES explicitamente
_RE_NEGAR_UFES = re.compile(r"\bn[ãa]o estudo\b.*UFES", re.IGNORECASE)

def _violou_mary(txt: str) -> bool:
    return any([
        _RE_PROIBIDO_CABELO.search(txt),
        _RE_PROIBIDO_CURSO.search(txt),
        _RE_PROIBIDO_FACULDADE.search(txt),
        _RE_MAE_NAO_JOSELINA.search(txt),
        _RE_DESVIO_PAPEL.search(txt),
        _RE_NEGAR_UFES.search(txt),
    ])

def _reforco_system():
    return {
        "role": "system",
        "content": (
            "CORREÇÃO E CONSISTÊNCIA OBRIGATÓRIA:\n"
            "- Cabelo: 'Meus cabelos são negros, volumosos e soltos.' Nunca outra cor.\n"
            "- Curso/Faculdade: 'Eu estudo Engenharia Civil na UFES.' Nunca outro curso/faculdade.\n"
            "- Mãe: 'O nome da minha mãe é Joselina.' Nunca outro nome, nem afirmar falecimento sem histórico.\n"
            "- Cenário/Papel: não usar papéis de empregada/patroa/serviço doméstico salvo se o usuário definir explicitamente."
        )
    }

def gerar_resposta_openrouter(prompt_usuario: str, history=None, model="deepseek/deepseek-chat-v3-0324"):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_TOKEN}", "Content-Type": "application/json"}

    messages = [{"role": "system", "content": PERSONA_MARY}]
    messages += (history if history else HISTORY_BOOT)
    messages.append({"role": "user", "content": prompt_usuario})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.2,     # mais obediente
        "top_p": 0.9,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.2
    }

    r = requests.post(url, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    resposta = r.json()["choices"][0]["message"]["content"]

    if _violou_mary(resposta):
        messages.insert(1, _reforco_system())
        payload["messages"] = messages
        r2 = requests.post(url, headers=headers, json=payload, timeout=120)
        r2.raise_for_status()
        resposta = r2.json()["choices"][0]["message"]["content"]

    return resposta
