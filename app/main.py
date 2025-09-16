# app/main.py
import re
import streamlit as st
from datetime import datetime

from mongo_utils import (
    montar_historico_openrouter,
    salvar_interacao,
    gerar_resposta_openrouter,
    limpar_memoria_usuario,
    limpar_memoria_canonica,
    apagar_tudo_usuario,
    registrar_evento, set_fato, ultimo_evento,
    colecao, db, state, eventos, perfil
)

st.set_page_config(page_title="Roleplay | Mary Massariol", layout="centered")
st.title("Roleplay | Mary Massariol")

# ==== Seletor de modelo ====
st.session_state.setdefault("modelo_escolhido", "deepseek/deepseek-chat-v3-0324")
MODELOS_OPENROUTER = [
    "deepseek/deepseek-chat-v3-0324",
    "openai/gpt-4o-search-preview",
    "qwen/qwen-2-72b-instruct",
    "mistralai/mixtral-8x7b-instruct-v0.1",
    "nousresearch/nous-hermes-2-mistral-7b-dpo",
]

c1, c2 = st.columns([4, 1])
with c1:
    st.session_state.modelo_escolhido = st.selectbox(
        "🧠 Modelo OpenRouter",
        MODELOS_OPENROUTER,
        index=MODELOS_OPENROUTER.index(st.session_state.modelo_escolhido)
        if st.session_state.modelo_escolhido in MODELOS_OPENROUTER else 0
    )
with c2:
    etiqueta_modelo = st.empty()
    etiqueta_modelo.markdown(
        f"""
        <div style="background-color: #222; color: #eee; padding: 6px 10px;
                    border-radius: 8px; font-size: 12px; text-align: center;
                    font-family: sans-serif; margin-top: 24px; opacity: 0.75;">
            <b>{st.session_state.modelo_escolhido}</b>
        </div>
        """,
        unsafe_allow_html=True
    )

# Atualiza etiqueta sempre que trocar modelo
if st.session_state.get("_last_model") != st.session_state.modelo_escolhido:
    st.session_state["_last_model"] = st.session_state.modelo_escolhido
    etiqueta_modelo.markdown(
        f"""
        <div style="background-color: #222; color: #eee; padding: 6px 10px;
                    border-radius: 8px; font-size: 12px; text-align: center;
                    font-family: sans-serif; margin-top: 24px; opacity: 0.75;">
            <b>{st.session_state.modelo_escolhido}</b>
        </div>
        """,
        unsafe_allow_html=True
    )

# ==== Sidebar (logo/ilustração) ====
st.sidebar.title("Mary Massariol")
st.sidebar.caption("Roleplay imersivo")

st.session_state.setdefault("sidebar_img_url", "")
st.session_state.setdefault("sidebar_credito", "")

st.sidebar.subheader("Imagem (URL)")
st.session_state.sidebar_img_url = st.sidebar.text_input(
    "Cole uma URL de imagem",
    value=st.session_state.sidebar_img_url,
    placeholder="https://exemplo.com/mary.png"
)

st.sidebar.subheader("Ou envie um arquivo")
upload_file = st.sidebar.file_uploader("PNG/JPG", type=["png", "jpg", "jpeg"])

img_shown = False
if upload_file is not None:
    st.sidebar.image(upload_file, use_container_width=True)
    img_shown = True
elif st.session_state.sidebar_img_url.strip():
    try:
        st.sidebar.image(st.session_state.sidebar_img_url.strip(), use_container_width=True)
        img_shown = True
    except Exception:
        st.sidebar.warning("Não foi possível carregar a imagem da URL.")

st.session_state.sidebar_credito = st.sidebar.text_input(
    "Crédito/legenda (opcional)",
    value=st.session_state.sidebar_credito,
    placeholder="Ilustração: @artista"
)
if img_shown and st.session_state.sidebar_credito.strip():
    st.sidebar.caption(st.session_state.sidebar_credito.strip())

# ===== Campos fixos =====
st.session_state.setdefault("usuario_input", "welnecker")
st.session_state.setdefault("usuario_fixado", None)
st.session_state.setdefault("enredo_inicial", "")
st.session_state.setdefault("enredo_publicado", False)

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
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("🔄 Resetar histórico (chat)"):
        limpar_memoria_usuario(USUARIO)
        st.session_state.mary_log = []
        st.session_state.enredo_publicado = False
        st.success(f"Histórico de {USUARIO} apagado (memórias canônicas preservadas).")

with c2:
    if st.button("🧠 Apagar TUDO (chat + memórias)"):
        apagar_tudo_usuario(USUARIO)
        st.session_state.mary_log = []
        st.session_state.enredo_publicado = False
        st.success(f"Chat e memórias canônicas de {USUARIO} foram apagados.")

with c3:
    if st.button("⏪ Apagar último turno"):
        from mongo_utils import apagar_ultima_interacao_usuario
        apagar_ultima_interacao_usuario(USUARIO)
        st.session_state.mary_log = montar_historico_openrouter(USUARIO)
        st.info("Última interação apagada.")

# ===== Publica ENREDO se necessário =====
if st.session_state.enredo_inicial.strip() and not st.session_state.enredo_publicado:
    if colecao.count_documents({"usuario": {"$regex": f"^{re.escape(USUARIO)}$", "$options": "i"},
                                "mensagem_usuario": "__ENREDO_INICIAL__"}) == 0:
        salvar_interacao(USUARIO, "__ENREDO_INICIAL__", st.session_state.enredo_inicial.strip())
        st.session_state.enredo_publicado = True

# ===== Carrega histórico =====
st.session_state.mary_log = montar_historico_openrouter(USUARIO)

# ===== Chat =====
chat = st.container()
with chat:
    i = 0
    msgs = st.session_state.mary_log
    while i < len(msgs):
        msg = msgs[i]
        if msg["role"] == "user" and msg["content"].strip() == "__ENREDO_INICIAL__":
            if i + 1 < len(msgs) and msgs[i+1]["role"] == "assistant":
                with st.chat_message("assistant", avatar="📝"):
                    st.markdown(f"**Cenário inicial**\n\n{msgs[i+1]['content']}")
                i += 2
                continue
        if msg["role"] == "user":
            with st.chat_message("user"):
                if msg["content"].strip() != "__ENREDO_INICIAL__":
                    st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar="💚"):
                st.markdown(msg["content"])
        i += 1

# ===== Input fixo no rodapé =====
if prompt := st.chat_input("Envie sua mensagem para Mary"):
    with st.chat_message("user"):
        st.markdown(prompt)
    resposta = gerar_resposta_openrouter(prompt, USUARIO, model=st.session_state.modelo_escolhido)
    salvar_interacao(USUARIO, prompt, resposta)
    st.session_state.mary_log = montar_historico_openrouter(USUARIO)
    with st.chat_message("assistant", avatar="💚"):
        st.markdown(resposta)
