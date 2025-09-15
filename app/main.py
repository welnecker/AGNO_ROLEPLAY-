# app/main.py
import streamlit as st
from mongo_utils import (
    montar_historico_openrouter,
    salvar_interacao,
    gerar_resposta_openrouter,
    limpar_memoria_usuario,
    apagar_ultima_interacao_usuario
)

st.set_page_config(page_title="Roleplay | Mary Massariol", layout="centered")
st.title("Roleplay | Mary Massariol")

# ===== Campos fixos =====
st.session_state.setdefault("usuario_input", "welnecker")
st.session_state.setdefault("usuario_fixado", None)
st.session_state.setdefault("enredo_inicial", "")
st.session_state.setdefault("enredo_publicado", False)
st.session_state.setdefault("elenco_publicado", False)

c1, c2 = st.columns([3, 1])
with c1:
    st.session_state.usuario_input = st.text_input("👤 Usuário", value=st.session_state.usuario_input, placeholder="Seu nome")
with c2:
    if st.button("✅ Usar este usuário"):
        st.session_state.usuario_fixado = st.session_state.usuario_input.strip()

if not st.session_state.usuario_fixado:
    st.info("Defina o usuário e clique em **Usar este usuário**.")
    st.stop()

USUARIO = st.session_state.usuario_fixado

st.session_state.enredo_inicial = st.text_area(
    "📜 Enredo inicial",
    value=st.session_state.enredo_inicial,
    placeholder="Ex.: Mary encontra o usuário depois de um dia difícil...",
    height=80
)

# ===== Controles de memória =====
b1, b2 = st.columns(2)
with b1:
    if st.button("🔄 Resetar histórico"):
        limpar_memoria_usuario(USUARIO)
        st.session_state.mary_log = []
        st.session_state.enredo_publicado = False
        st.session_state.elenco_publicado = False
        st.success(f"Memória de {USUARIO} apagada.")
with b2:
    if st.button("⏪ Apagar último turno"):
        apagar_ultima_interacao_usuario(USUARIO)
        st.session_state.mary_log = montar_historico_openrouter(USUARIO)
        st.info("Última interação apagada.")

# ===== Carrega histórico =====
st.session_state.mary_log = montar_historico_openrouter(USUARIO)

# Publica enredo inicial uma única vez no começo
if st.session_state.enredo_inicial.strip() and not st.session_state.enredo_publicado and not st.session_state.mary_log:
    salvar_interacao(USUARIO, "__ENREDO_INICIAL__", st.session_state.enredo_inicial.strip())
    st.session_state.mary_log = montar_historico_openrouter(USUARIO)
    st.session_state.enredo_publicado = True

# Publica “Elenco” uma única vez no começo (Silvia/Alexandra)
if not st.session_state.elenco_publicado and not st.session_state.mary_log:
    elenco_txt = (
        "**Elenco de apoio**\n\n"
        "- **Silvia Bodat** — extrovertida, bem-humorada; puxa conversa e descontrai.\n"
        "- **Alexandra Resinentti** — reservada, conselheira; fala pouco e vai direto ao ponto.\n\n"
        "_Aparecem como apoio (fofocas, conselhos, contexto), sem tirar o foco do usuário._"
    )
    salvar_interacao(USUARIO, "__ELENCO__", elenco_txt)
    st.session_state.mary_log = montar_historico_openrouter(USUARIO)
    st.session_state.elenco_publicado = True

# ===== Chat =====
chat = st.container()
with chat:
    i = 0
    msgs = st.session_state.mary_log
    while i < len(msgs):
        msg = msgs[i]
        # Bloco especial: Enredo inicial
        if msg["role"] == "user" and msg["content"].strip() == "__ENREDO_INICIAL__":
            if i + 1 < len(msgs) and msgs[i + 1]["role"] == "assistant":
                with st.chat_message("assistant", avatar="📝"):
                    st.markdown(f"**Cenário inicial**\n\n{msgs[i+1]['content']}")
                i += 2
                continue
        # Bloco especial: Elenco
        if msg["role"] == "user" and msg["content"].strip() == "__ELENCO__":
            if i + 1 < len(msgs) and msgs[i + 1]["role"] == "assistant":
                with st.chat_message("assistant", avatar="🎭"):
                    st.markdown(msgs[i+1]["content"])
                i += 2
                continue
        # Mensagens normais
        if msg["role"] == "user":
            with st.chat_message("user"):
                if msg["content"].strip() not in {"__ENREDO_INICIAL__", "__ELENCO__"}:
                    st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar="💚"):
                st.markdown(msg["content"])
        i += 1

# ===== Input fixo no rodapé =====
if prompt := st.chat_input("Envie sua mensagem para Mary"):
    with st.chat_message("user"):
        st.markdown(prompt)
    resposta = gerar_resposta_openrouter(prompt, USUARIO)
    salvar_interacao(USUARIO, prompt, resposta)
    st.session_state.mary_log = montar_historico_openrouter(USUARIO)
    with st.chat_message("assistant", avatar="💚"):
        st.markdown(resposta)
