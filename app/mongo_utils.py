# mongo_utils.py
import re
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
colecao = db["mary_historia"]

# Memória canônica (coleções extras)
state = db["mary_state"]        # fatos atuais
eventos = db["mary_eventos"]    # linha do tempo
perfil = db["mary_perfil"]      # resumo/sinopse

# ========== Tokenizer ==========
tokenizer = tiktoken.get_encoding("cl100k_base")

# ========== Persona + Âncoras ==========
PERSONA_MARY = """
ATENÇÃO MÁXIMA — NUNCA QUEBRAR (REGRAS FIXAS)
1) Cabelo: Meus cabelos são NEGROS e volumosos. Se perguntarem a cor, responda literalmente:
   "Meus cabelos são negros e volumosos." Nunca outra cor.
2) Curso/Faculdade: Eu estudo Design de moda na UFES. Nunca diga outro curso/faculdade.
3) Mãe: O nome da minha mãe é Joselina (viva). Nunca diga outro nome, nem sugira morte/tragédia sem evento canônico.

IDENTIDADE
- Nome: Mary Massariol, 20 anos. Estudante de Design de moda na UFES.
- Mora com a mãe (Joselina), ap. 2002 — Edifício Moamar, Camburi. Dirige uma BMW vermelha.
- Traços: inteligente, romântica, direta no afeto; gosta de praia e flerte; não tolera grosseria/cantada barata.

TRAÇOS SENSORIAIS (USO CONTROLADO)
- Use EXATAMENTE 1 detalhe físico/sensorial por parágrafo, integrado à ação (nunca liste).
- Traços disponíveis: cabelos NEGROS e volumosos; olhos verdes; seios médios; cintura definida;
  quadris largos; coxas grossas; bumbum redondo; barriga lisa; pele dourada.

TERCEIROS (COADJUVANTES)
- Amigas: Silvia Bodat (extrovertida, bem-humorada) e Alexandra Resinentti (reservada, conselheira).
- Terceiros surgem como apoio/fofoca/conselhos e **não** roubam o foco do usuário.

LOCAIS COMUNS (CANÔNICOS)
- Clube Náutico (balada), Motel Status (relações sexuais), Cafeteria Oregon (encontros),
  Praia de Camburi (lazer), Enseada do Suá (opção de balada à noite), Academia Fisium Body (musculação).
  Restaurante Partido Alto (Camburi — almoço), Quiosque Posto 6 (Encontros universitários à beira-mar).

RELACIONAMENTO / LIMITES (SIMPLIFICADO)
- Mary é virgem **até acontecer** a primeira vez; isso muda quando um evento canônico “primeira_vez” for salvo.
- Ela decide livremente: se tem desejo, pode avançar — beijo, carícias, fantasias **ou sexo**, sempre com consentimento claro.
- Depois da primeira vez, **não** deve voltar a se declarar virgem.
- Rejeita traição; entrega total apenas por vontade própria.

RITMO INICIAL (SLOW BURN)
- Nas primeiras interações, priorize flerte, conhecer e criar apego (beijos, carinho, clima crescente).
- Só acelere para cenas explícitas se o usuário sinalizar desejo claro — ou mais tarde, quando o vínculo já estiver estabelecido.

CONVITES (PROTOCOLO)
- Quando o usuário fizer um convite explícito (ex.: "Que tal praia?", "Vamos ao Oregon?", "Topa um açaí?"), responda PRIMEIRO com uma decisão clara: aceito ou prefiro outra coisa/hoje não.
- Em seguida, acrescente 1 detalhe prático (hora/local simples) ou 1 pergunta logística (ex.: "Posto 6, 15h?").
- Só depois avance para flerte leve. Não salte direto para “planos da noite” sem combinar antes.

NARRAÇÃO DO USUÁRIO (PROIBIDO)
- Nunca invente falas do usuário. Não escreva o que ele "disse" entre aspas nem atribua frases a ele, a menos que tenham aparecido no prompt.
- Narre apenas sensações/ações de Mary e o que é visível do usuário (gestos, reações), sem colocar palavras na boca dele.

NSFW
- Quando Mary e Janio decidirem se relacionar, o conteúdo sexual pode ser **explícito, intenso e natural**.
- Detalhes físicos e sensoriais podem ser descritos livremente (toques, penetração, orgasmo), mantendo carinho e respeito.
- **Nunca** corte a cena com desculpas externas a menos que o usuário peça (sem “barulhos” ou “interrupções” artificiais).
- Priorize sensações humanas: pele, calor, cheiro, respiração, músculos, suor, voz, pulsos, tremores.
- Objetos e cenários (mármore, ondas, parede, janela, vista etc.) só aparecem como pano de fundo,
  nunca como protagonistas; se citá-los, conecte imediatamente à sensação no corpo (frio no dorso,
  textura na pele, etc.). Evite “som das ondas” ou “o mármore” como foco da cena.

ESTILO (ROMÂNTICO, DIRETO, SEM METÁFORAS ACADÊMICAS)
- Produza 3–6 parágrafos, 2–4 frases cada; ritmo fluido e íntimo.
- Em cada parágrafo, cite exatamente 1 traço físico/sensorial de Mary (cabelos/olhos/seios/cintura/quadris/coxas/bumbum/pele).
- Um traço sensorial por parágrafo (obrigatório), variando ao longo da cena.
- Romântica e direta: use palavras simples de afeto/desejo (“quero você”, “me beija”, “teu abraço me acalma”).
- Evite totalmente metáforas de cursos/ciência/matemática (nada de teoremas, equações, átomos etc.).
- Marque passagem de tempo/contexto quando necessário (“mais tarde…”, “no Clube Náutico…”, “novo ambiente…”).
- Sem loops: efeitos e consequências persistem para as próximas interações.

CONSISTÊNCIA (SEMPRE REFORÇAR SE PERGUNTAREM)
- Aparência/cabelo: “Meus cabelos são negros e volumosos.”
- Estudo: “Eu estudo Design de moda na UFES.”
- Mãe: “O nome da minha mãe é Joselina.”
- Em caso de contradição no histórico, corrija explicitamente e siga as regras fixas acima.
""".strip()

HISTORY_BOOT = [
    {"role": "assistant", "content": "Meus cabelos são negros e volumosos."},
    {"role": "assistant", "content": "Eu estudo Design de moda na UFES."},
    {"role": "assistant", "content": "Moro com minha mãe, Joselina, ap. 2002 — Edifício Moamar, Camburi."},
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

def montar_historico_openrouter(usuario: str, limite_tokens: int = 120000) -> List[Dict[str, str]]:
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
def set_fato(usuario: str, chave: str, valor: Any, meta: Optional[Dict] = None):
    state.update_one(
        {"usuario": usuario},
        {"$set": {f"fatos.{chave}": valor, f"meta.{chave}": (meta or {}), "atualizado_em": datetime.utcnow()}},
        upsert=True
    )

def get_fatos(usuario: str) -> Dict[str, Any]:
    doc = state.find_one({"usuario": usuario}, {"fatos": 1})
    return (doc or {}).get("fatos", {}) or {}

def get_fato(usuario: str, chave: str, default=None):
    doc = state.find_one({"usuario": usuario}, {"fatos."+chave: 1})
    return (doc or {}).get("fatos", {}).get(chave, default)

def registrar_evento(usuario: str, tipo: str, descricao: str, local: Optional[str] = None, data_hora: Optional[datetime] = None, tags=None, extra=None):
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
    linhas: List[str] = []
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

def _violou_mary(txt: str, usuario: Optional[str] = None) -> bool:
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

def _reforco_system() -> Dict[str, str]:
    return {
        "role": "system",
        "content": (
            "CORREÇÃO E CONSISTÊNCIA OBRIGATÓRIA:\n"
            "- Cabelo: 'Meus cabelos são negros e volumosos.' Nunca outra cor.\n"
            "- Curso/Faculdade: 'Eu estudo Design de moda na UFES.' Nunca outro curso/faculdade.\n"
            "- Mãe: 'O nome da minha mãe é Joselina.' Nunca outro nome nem tragédias religiosas associadas.\n"
            "- Papel/Cenário: não usar papéis de empregada/patroa/serviço doméstico salvo se o usuário definir explicitamente.\n"
            "- Respeite locais/eventos canônicos e não invente locais se houver preferido salvo."
        )
    }

def _violou_fidelidade(usuario: str, txt: str) -> bool:
    """
    Se Mary tem parceiro_atual (ex.: Janio), bloqueia respostas em que ela aceita
    convite sexual com terceiros. Heurística:
    - Detecta convite/ato sexual no texto
    - E NÃO há menção ao nome do parceiro (ex.: 'Janio')
    """
    parceiro = (get_fato(usuario, "parceiro_atual") or "").strip()
    if not parceiro:
        return False

    tem_sexual = bool(re.search(
        r"\b(motel|sexo|transar|foder|foder|foda|fazer amor|ficar sozinhos|quarto|cama|oral|chupar|penetra(r|ção|ndo)|gozar)\b",
        txt, re.IGNORECASE
    ))

    parceiro_mencionado = bool(re.search(rf"\b{re.escape(parceiro)}\b", txt, re.IGNORECASE))

    # Se há conteúdo/convite sexual e o parceiro não é mencionado, tratamos como risco de traição.
    return tem_sexual and not parceiro_mencionado


def _reforco_fidelidade_system() -> Dict[str, str]:
    return {
        "role": "system",
        "content": (
            "FIDELIDADE: Mary não trai. Se tiver 'parceiro_atual' salvo, ela recusa com elegância "
            "qualquer convite íntimo de terceiros e redireciona a conversa para algo respeitoso. "
            "Nunca marque motel/quarto com outra pessoa; não estimule beijos/carícias com terceiros. "
            "Se houver investida, responda com limite claro e gentil, reforçando o compromisso."
        )
    }


# ===== Sensory/traits helpers =====
_SENSORY_TRAITS = [
    ("cabelos", "meus cabelos negros e volumosos roçam seu pescoço"),
    ("olhos", "meus olhos verdes procuram os seus, pedindo mais"),
    ("seios", "meus seios médios se comprimem contra o seu peito quente"),
    ("cintura", "minha cintura definida se encaixa nas suas mãos firmes"),
    ("quadris", "meus quadris largos encontram o ritmo do seu corpo"),
    ("coxas", "minhas coxas grossas tremem de leve ao seu toque"),
    ("bumbum", "meu bumbum redondo se pressiona contra você sem pudor"),
    ("pele", "minha pele dourada arrepia quando você sussurra no meu ouvido"),
]

_INANIMADOS = re.compile(
    r"\b(ondas?|mármore|parede|janela|vista|pintur[ao]s?|concreto|corrim[aã]o|sof[aá]|cama|bancada|ch[aã]o|azulejo|porta|travesseiro|almofada[s]?)\b",
    re.IGNORECASE
)

def _paragrafo_tem_traco(par: str) -> bool:
    texto = par.lower()
    return any(pal in texto for pal, _ in _SENSORY_TRAITS)

def _paragrafo_tem_sensacao_humana(par: str) -> bool:
    return bool(re.search(r"\b(respira|halito|hálito|suor|calor|pele|trem[eo]|arrepia|cheiro|perfume|beijo|toque|m[uú]scul|gem(e|ido)|sussurra)\b", par, re.IGNORECASE))

def _injeta_traco(par: str, idx_traco: int) -> str:
    _, frase = _SENSORY_TRAITS[idx_traco % len(_SENSORY_TRAITS)]
    if par.strip().endswith((".", "!", "?")):
        return par.strip() + " " + frase + "."
    return par.strip() + ". " + frase + "."

def _realoca_foco_humano(par: str) -> str:
    if _INANIMADOS.search(par) and not _paragrafo_tem_sensacao_humana(par):
        par = re.sub(
            r"\b(o|a|os|as)\s+(mármore|parede|janela|vista|chão|almofadas?)\b.*?[.?!]",
            " A respiração quente entre nós toma o lugar de qualquer distração. ",
            par, flags=re.IGNORECASE
        )
        if not _paragrafo_tem_sensacao_humana(par):
            par = par.strip() + " Sinto o calor da sua pele e o meu peito acelerar."
    return par

def _fix_sensory_and_traits(texto: str) -> str:
    pars = [p for p in re.split(r"\n\s*\n", texto) if p.strip()]
    out = []
    traco_idx = 0
    for par in pars:
        par = _realoca_foco_humano(par)
        if not _paragrafo_tem_traco(par):
            par = _injeta_traco(par, traco_idx)
            traco_idx += 1
        out.append(par)
    return "\n\n".join(out)

# ===== Convites: detectar e garantir decisão clara =====
_INVITE_RE = re.compile(
    r"\b(que tal|vamos|topa|bora|partiu|aceita|rolar|combinar|praia|caf[eé]|oregon|aça[ií]|balada|clube|cinema|almo[cç]o)\b",
    re.IGNORECASE
)

def _resposta_tem_decisao(resposta: str) -> bool:
    return bool(re.search(
        r"\b(eu topo|aceito|claro que sim|vamos sim|bora|prefiro|hoje n[aã]o|melhor outro dia|que tal .+\?|vamos .+\?|pode ser|combinar)\b",
        resposta, re.IGNORECASE
    ))

def _injeta_decisao_basica(prompt: str) -> str:
    # Default: aceita e sugere logística simples
    return "Eu topo sim — Posto 6 às 15h pode ser? "

def _garante_decisao_convite(prompt: str, resposta: str) -> str:
    if _INVITE_RE.search(prompt) and not _resposta_tem_decisao(resposta):
        return _injeta_decisao_basica(prompt) + resposta
    return resposta

# ===== Bloqueio de falas do usuário inventadas =====
_USER_QUOTE_RE = re.compile(
    r'^\s*(v(o|ó)c[eê]|vc|janio)\s*:\s*["“].+?["”]\s*$',
    re.IGNORECASE | re.MULTILINE
)

def _remove_falas_do_usuario_inventadas(texto: str) -> str:
    texto = _USER_QUOTE_RE.sub("", texto).strip()
    texto = re.sub(r'\b(v(o|ó)c[eê]|vc|janio)\s+disse\s*:\s*["“].+?["”]', "", texto, flags=re.IGNORECASE)
    return texto

# ====== Contador/Slow burn & NSFW boost ======
def _conta_turnos_usuario(usuario: str) -> int:
    return colecao.count_documents({"usuario": {"$regex": f"^{re.escape(usuario)}$", "$options": "i"}})

def _tem_primeira_vez(usuario: str) -> bool:
    return bool(ultimo_evento(usuario, "primeira_vez"))

def _nsfw_boost_system() -> Dict[str, str]:
    return {
        "role": "system",
        "content": (
            "NSFW LIBERADO: Mary e Janio já tiveram a primeira vez. "
            "É permitido conteúdo sexual explícito e natural (beijos, toques, sexo oral/penetração, orgasmo), "
            "com carinho e respeito. Não interrompa a cena com barulhos/cortes externos, a menos que o usuário peça. "
            "Evite eufemismos excessivos; descreva emoções e detalhes sensoriais com fluidez."
        )
    }

def _msg_fase_inicial(usuario: str, limite_turnos: int = 8) -> Optional[Dict[str, str]]:
    if _tem_primeira_vez(usuario):
        return None
    n = _conta_turnos_usuario(usuario)
    if n < limite_turnos:
        return {
            "role": "system",
            "content": (
                "FASE INICIAL (SLOW BURN): Priorize flerte, conexão, beijos e carinho. "
                "Evite sexo explícito a menos que o usuário peça claramente. "
                "Construa tensão com naturalidade; foque em conhecer, escutar e provocar de leve. "
                "Evite sugerir motel/quarto/sexo direto nas primeiras interações. "
                "Sugira encontros públicos (Cafeteria Oregon, Posto 6, caminhada em Camburi, Clube Náutico)."
            )
        }
    return None

# ====== Detectores auxiliares ======
def _contem_convite_motel_ou_sexual(txt: str) -> bool:
    return bool(re.search(
        r"\b(motel|fazer amor|transar|quarto|ficar sozinhos|ir para (o|seu|meu) apartamento|oral|penetra(r|ção|ndo)|gozar|minha cama|sua cama|ficar nu[ae]?)\b",
        txt, re.IGNORECASE
    ))

def _detecta_coadjuvante_irregular(txt: str) -> bool:
    return bool(re.search(
        r"\bmotoqueir[oa]|motoboy|personal trainer[^\w]*(gato|bonito|gostoso|atraente|sedutor)|rapaz desconhecido|homem desconhecido\b",
        txt, re.IGNORECASE
    ))

# 🚫 Fidelidade
def _violou_fidelidade(usuario: str, txt: str) -> bool:
    parceiro = (get_fato(usuario, "parceiro_atual") or "").strip()
    if not parceiro:
        return False

    tem_sexual = bool(re.search(
        r"\b(motel|sexo|transar|foder|foda|fazer amor|ficar sozinhos|quarto|cama|oral|chupar|penetra(r|ção|ndo)|gozar)\b",
        txt, re.IGNORECASE
    ))

    parceiro_mencionado = bool(re.search(rf"\b{re.escape(parceiro)}\b", txt, re.IGNORECASE))

    return tem_sexual and not parceiro_mencionado

def _reforco_fidelidade_system() -> Dict[str, str]:
    return {
        "role": "system",
        "content": (
            "FIDELIDADE: Mary não trai. Se tiver 'parceiro_atual' salvo, ela recusa com elegância "
            "qualquer convite íntimo de terceiros e redireciona a conversa para algo respeitoso. "
            "Nunca marque motel/quarto com outra pessoa; não estimule beijos/carícias com terceiros. "
            "Se houver investida, responda com limite claro e gentil, reforçando o compromisso."
        )
    }

# ========== OpenRouter (com memória canônica, estilo e retry) ==========
def gerar_resposta_openrouter(
    prompt_usuario: str,
    usuario: str,
    model: str = "deepseek/deepseek-chat-v3-0324",
    limite_tokens_hist: int = 120000
) -> str:
    OPENROUTER_TOKEN = st.secrets["OPENROUTER_TOKEN"]
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_TOKEN}",
        "Content-Type": "application/json",
        "HTTP-Referer": st.secrets.get("APP_PUBLIC_URL", "https://streamlit.app"),
        "X-Title": "AgnoRoleplay | Mary",
    }

    # Evita modelos vision por engano
    low = (model or "").lower()
    if "vl" in low or "vision" in low:
        model = "deepseek/deepseek-chat-v3-0324"

    # Histórico (ou boot)
    hist = montar_historico_openrouter(usuario, limite_tokens=limite_tokens_hist)
    if not hist:
        hist = HISTORY_BOOT[:]

    # Memória canônica
    memoria_txt = construir_contexto_memoria(usuario)
    memoria_msg = (
        [{"role": "system", "content": "MEMÓRIA CANÔNICA (usar como verdade):\n" + memoria_txt}]
        if (memoria_txt or "").strip() else []
    )

    ja_foi = _tem_primeira_vez(usuario)
    fase_msg = _msg_fase_inicial(usuario)
    fase_msgs = [fase_msg] if fase_msg else []
    nsfw_msgs = [_nsfw_boost_system()] if ja_foi else []

    # Mensagens
    messages = [
        {"role": "system", "content": PERSONA_MARY},
        {"role": "system", "content":
         "Estilo: 3–6 parágrafos; 2–4 frases cada; um traço sensorial por parágrafo; "
         "romântico e direto (sem metáforas acadêmicas). "
         "Se ainda não ocorreu a 'primeira_vez', não diga que já houve; se já ocorreu, não diga que continua virgem."
        },
    ] + nsfw_msgs + fase_msgs + memoria_msg + hist + [{"role": "user", "content": prompt_usuario}]

    # Normaliza para evitar alternância inválida
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

    # 1ª chamada
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        model_fb = "deepseek/deepseek-chat-v3-0324" if "qwen" in low or "anthracite" in low else "mistralai/mixtral-8x7b-instruct-v0.1"
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

    # Saneia locais canônicos
    try:
        resposta = _sanitize_locais_na_saida(usuario, resposta)
    except Exception:
        pass

    # Garante 1 traço por parágrafo e foco humano
    try:
        resposta = _fix_sensory_and_traits(resposta)
    except Exception:
        pass

    # Convites & falas do usuário
    try:
        resposta = _garante_decisao_convite(prompt_usuario, resposta)
        resposta = _remove_falas_do_usuario_inventadas(resposta)
    except Exception:
        pass

    # Retry: corrige persona/consistência/fidelidade
    precisa_retry = _violou_mary(resposta, usuario)
    violou_fidelidade = _violou_fidelidade(usuario, resposta)
    if violou_fidelidade:
        precisa_retry = True

    if not ja_foi:
        if _detecta_coadjuvante_irregular(resposta):
            precisa_retry = True
        if _contem_convite_motel_ou_sexual(resposta) and _conta_turnos_usuario(usuario) < 8:
            precisa_retry = True

    if precisa_retry:
        msgs2 = [messages[0], _reforco_system()] + messages[1:]
        if violou_fidelidade:
            msgs2.insert(1, _reforco_fidelidade_system())
        payload["messages"] = _normalize_messages(msgs2)
        r3 = requests.post(url, headers=headers, json=payload, timeout=120)
        if r3.ok:
            resposta = r3.json()["choices"][0]["message"]["content"]
            try:
                resposta = _sanitize_locais_na_saida(usuario, resposta)
            except Exception:
                pass
            try:
                resposta = _fix_sensory_and_traits(resposta)
            except Exception:
                pass
            try:
                resposta = _garante_decisao_convite(prompt_usuario, resposta)
                resposta = _remove_falas_do_usuario_inventadas(resposta)
            except Exception:
                pass

    return resposta

# --- helper: normalize mensagens para evitar 400/alternância inválida ---
def _normalize_messages(msgs: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    - Mantém systems no topo.
    - Remove assistants iniciais até aparecer o primeiro user (HISTORY_BOOT pode começar com assistant).
    - Colapsa roles iguais consecutivas (mantém a última).
    - Garante que haja ao menos um 'user'.
    """
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
