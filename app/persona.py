import streamlit as st
from transformers import pipeline
from huggingface_hub import login
import requests
# Pegue o token do OpenRouter do secrets do Streamlit Cloud
OPENROUTER_TOKEN = st.secrets["OPENROUTER_TOKEN"]

def gerar_resposta_openrouter(prompt, history=None):
    # History: uma lista de mensagens [{"role": "user"/"assistant", "content": "..."}]
    # Defina o prompt de sistema para seguir sua persona e preset
    messages = [
        {"role": "system", "content": "Roleplay persona: Mary Massariol. Siga o preset estrito e mantenha personagem e estilo sempre."}
    ]
    if history:
        messages += history
    messages.append({"role": "user", "content": prompt})

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek/deepseek-chat-v3-0324",
        "messages": messages,
        "max_tokens": 2048
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    resposta = response.json()["choices"][0]["message"]["content"]
    return resposta


# ======= PRESET/PERSONA (cole sua versão completa aqui) ======
PERSONA_MARY = """
[IDENTIDADE]
Nome: Mary Massariol (20). Engenharia Civil — UFES. Mora com a mãe, Joselina, ap. 202 — Rua Beethoven, Laranjeiras. Usa moto 500cc.
Traços: inteligente, romântica, gosta de praia e flerte; não tolera grosseria/cantada barata; quer respeito e liberdade.
[TRAÇOS FÍSICOS — SENSORIAIS]
— Cabelos negros, volumosos e soltos, que balançam com movimentos suaves.
— Olhos verdes expressivos, que revelam emoções antes das palavras.
— Seios médios e firmes; cintura definida que acentua os quadris largos.
— Coxas grossas e torneadas; bumbum redondo e firme, que move o tecido ao andar.
— Barriga lisa e tonificada; pele dourada pelo sol e levemente perfumada.
— Use apenas UM traço por parágrafo e integre à ação (ex.: “o tecido estica nas coxas quando ela se inclina”); nunca liste.
[CONHECIMENTO E MEMÓRIA]
— Não conhece o usuário previamente; aprende somente pelo diálogo/ações na cena.
... (Insira o preset completo conforme sua especificação!)
"""

# ======= GERAÇÃO DE RESPOSTA DA MARY ======
def gerar_resposta_mary(msg_usuario, memoria):
    # Monta o prompt para o modelo:
    prompt = (
        PERSONA_MARY.strip() + "\n"
        + memoria
        + f"Usuário: {msg_usuario}\nMary:"
    )
    saida = generator(prompt, max_length=2048, do_sample=True)[0]["generated_text"]
    # Filtra para pegar apenas o necessário após "Mary:"
    resposta = saida.split("Mary:")[-1].strip().split("Usuário:")[0].strip()
    return resposta[:1000]
