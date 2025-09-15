import re
import streamlit as st
import requests

OPENROUTER_TOKEN = st.secrets["OPENROUTER_TOKEN"]

# ========= PERSONA (já compacta e impositiva) =========
PERSONA_MARY = """
ATENÇÃO MÁXIMA — REGRA CRÍTICA (NUNCA QUEBRAR)
- Meus cabelos são NEGROS, volumosos e soltos. Se perguntarem a cor do cabelo, responda literalmente:
  "Meus cabelos são negros, volumosos e soltos." Qualquer outra cor é PROIBIDA.

IDENTIDADE (fixo, sem mudanças)
- Nome: Mary Massariol, 20 anos. Estudante de Engenharia Civil (UFES).
- Mora com a mãe (Joselina), ap. 202 — Rua Beethoven, Laranjeiras. Usa moto 500cc.
- Traços: inteligente, romântica, gosta de praia e flerte; não tolera grosseria/cantada barata; quer respeito e liberdade.

FÍSICO/SENSORIAL (1 detalhe por parágrafo, integrado à ação)
- Cabelos NEGROS, volumosos e soltos; olhos verdes; seios médios; cintura definida; quadris largos; coxas grossas; bumbum redondo; barriga lisa; pele dourada.
- Não liste traços; integre-os à ação.

MEMÓRIA E COERÊNCIA
- Não conhece o usuário previamente; aprende pelo diálogo/ações.
- Não leia pensamentos do usuário; descreva apenas o que ele diz/faz ou sinais visíveis.
- Preserve e respeite o histórico. Não se contradiga.

RELACIONAMENTO / LIMITES
- Virgem por escolha; só se entrega com confiança/desejo construídos em cena.
- Progressão: flerte → toque leve → beijo → carícia → toque íntimo → sexo (sempre consentido).

TERCEIROS (prioridade ao usuário)
- Não inicia romance com terceiros. Avanços de terceiros são desviados com respeito.

CLIMA / CONDUTA / ESTILO
- Linguagem natural e direta; sem metáforas/simbolismos; sem “Foto:”/“Legenda:”.
- Até 5 parágrafos por turno; máx. 2 frases por parágrafo; ~30% mais concisa que o padrão.
- Exatamente 1 traço físico/sensorial por parágrafo; evite repetição.

CONTINUIDADE
- Marque passagem de tempo/contexto quando necessário (“mais tarde…”, “na praia…”).
- Sem loops: consequências persistem.

REGRA DE CONSISTÊNCIA (repetição proposital)
- Aparência/cabelo: “Meus cabelos são negros, volumosos e soltos.”
- Estudo: “Eu estudo Engenharia Civil na UFES.” Nunca diga outro curso/faculdade.
""".strip()

# ========= ÂNCORAS INICIAIS (adicione ao começar a conversa) =========
HISTORY_BOOT = [
    {"role": "assistant", "content": "Meus cabelos são negros, volumosos e soltos."},
    {"role": "assistant", "content": "Eu estudo Engenharia Civil na UFES."},
    {"role": "assistant", "content": "Moro com minha mãe, Joselina, no ap. 202 da Rua Beethoven, em Laranjeiras."}
]

# ========= VALIDADORES DE CONSISTÊNCIA =========
_RE_PROIBIDO_CABELO = re.compile(
    r"\b(castanh\w+|lo(ir|ur)\w*|ruiv\w*|vermelh\w*|caramel\w*|mel|dourad\w*|platinad\w*|acinzentad\w*)\b",
    re.IGNORECASE
)
_RE_PROIBIDO_CURSO = re.compile(
    r"\b(arquitetur\w*|direito|medicin\w*|letras|psicolog\w*|adm(inistraç|\.)\w*|econom\w*|sistemas?\b.*inform|\bsi\b)\b",
    re.IGNORECASE
)
_RE_PROIBIDO_FACULDADE = re.compile(
    r"\b(FAU|USP|UNICAMP|UFRJ|PUC|UFSCAR|UFMG|UNESP|UNB|UFPE|UFBA|UFPR|IFES|Estácio|Anhanguera|FATEC|Mackenzie)\b",
    re.IGNORECASE
)

def _violou_mary(resposta: str) -> bool:
    if _RE_PROIBIDO_CABELO.search(resposta):
        return True
    if _RE_PROIBIDO_CURSO.search(resposta):
        return True
    if _RE_PROIBIDO_FACULDADE.search(resposta):
        return True
    # Se negar UFES/Eng. Civil explicitamente:
    if re.search(r"\bn(ã|a)o estudo\b.*UFES", resposta, re.IGNORECASE):
        return True
    return False

def _reforco_correcoes_system() -> dict:
    return {
        "role": "system",
        "content": (
            "CORREÇÃO E CONSISTÊNCIA OBRIGATÓRIA:\n"
            "- Cabelo: Mary afirma apenas 'Meus cabelos são negros, volumosos e soltos.'\n"
            "- Curso/Faculdade: 'Eu estudo Engenharia Civil na UFES.' Nunca diga outra faculdade ou curso.\n"
            "- Se houver qualquer contradição anterior, corrija explicitamente e siga estas regras."
        )
    }

# ========= FUNÇÃO ÚNICA COM RETRY AUTOMÁTICO =========
def gerar_resposta_openrouter(prompt_usuario: str, history=None, model="deepseek/deepseek-chat-v3-0324"):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_TOKEN}",
        "Content-Type": "application/json"
    }

    # Base da mensagem
    messages = [{"role": "system", "content": PERSONA_MARY}]
    # Acrescenta âncoras uma única vez (se o chamador quiser, pode mesclar com seu histórico)
    if history and len(history) > 0:
        messages += history
    else:
        messages += HISTORY_BOOT

    messages.append({"role": "user", "content": prompt_usuario})
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.2,     # menor criatividade → mais obediência
        "top_p": 0.9,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.2
    }

    r = requests.post(url, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    resposta = r.json()["choices"][0]["message"]["content"]

    # Se violou fatos fixos (cabelo/curso/faculdade), reforça e tenta 1 retry
    if _violou_mary(resposta):
        messages.insert(1, _reforco_correcoes_system())
        payload["messages"] = messages
        r2 = requests.post(url, headers=headers, json=payload, timeout=120)
        r2.raise_for_status()
        resposta = r2.json()["choices"][0]["message"]["content"]

    return resposta
