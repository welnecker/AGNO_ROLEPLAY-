import streamlit as st
from mongo_utils import (
    montar_historico_openrouter,
    salvar_interacao,
    gerar_resposta_openrouter,
    limpar_memoria_usuario,
    apagar_ultima_interacao_usuario
)

st.set_page_config(page_title="Roleplay com Mary Massariol", layout="centered")
st.title("Roleplay | Mary Massariol")

# ===========================
# CAMPOS FIXOS NO TOPO
# ===========================
st.session_state.setdefault("usuario", "welnecker")
st.session_state.setdefault("enredo_inicial", "")
st.session_state.setdefault("enredo_publicado", False)

col1, col2 = st.columns([1, 2])
with col1:
    st.session_state.usuario = st.text_input("👤 Usuário", value=st.session_state.usuario, placeholder="Seu nome")
with col2:
    st.session_state.enredo_inicial = st.text_area(
        "📜 Enredo inicial",
        value=st.session_state.enredo_inicial,
        placeholder="Ex.: Mary encontra o usuário depois de um dia difícil...",
        height=80
    )

# ===========================
# CONTROLES DE MEMÓRIA
# ===========================
colr1, colr2 = st.columns(2)
with colr1:
    if st.button("🔄 Resetar histórico"):
        limpar_memoria_usuario(st.session_state.usuario)
        st.session_state.mary_log = []
        st.session_state.pop("mensagem_usuario", None)
        st.session_state.enredo_publicado = False
        st.success(f"Memória de {st.session_state.usuario} apagada com sucesso!")
with colr2:
    if st.button("⏪ Apagar último turno"):
        apagar_ultima_interacao_usuario(st.session_state.usuario)
        st.session_state.mary_log = montar_historico_openrouter(st.session_state.usuario)
        st.info("Última interação apagada.")

# ===========================
# HISTÓRICO + PUBLICAÇÃO DO ENREDO
# ===========================
if "mary_log" not in st.session_state:
    st.session_state.mary_log = montar_historico_openrouter(st.session_state.usuario)

# Publica o enredo inicial UMA ÚNICA VEZ (salva no Mongo com marcador especial)
if (
    st.session_state.enredo_inicial.strip()
    and not st.session_state.enredo_publicado
    and not st.session_state.mary_log  # só no começo da conversa
):
    salvar_interacao(
        st.session_state.usuario,
        "__ENREDO_INICIAL__",                     # marcador interno (user)
        st.session_state.enredo_inicial.strip()  # conteúdo do cenário (assistant)
    )
    st.session_state.mary_log = montar_historico_openrouter(st.session_state.usuario)
    st.session_state.enredo_publicado = True

# ===========================
# RENDER DO CHAT (com “Cenário inicial” especial)
# ===========================
chat_container = st.container()
with chat_container:
    i = 0
    msgs = st.session_state.mary_log
    while i < len(msgs):
        msg = msgs[i]
        # Se acharmos o marcador do enredo, renderizamos como um bloco especial e pulamos o par (user+assistant)
        if msg["role"] == "user" and msg["content"].strip() == "__ENREDO_INICIAL__":
            # o conteúdo do enredo está no próximo item (assistant)
            if i + 1 < len(msgs) and msgs[i + 1]["role"] == "assistant":
                enredo_txt = msgs[i + 1]["content"]
                with st.chat_message("assistant", avatar="📝"):
                    st.markdown(f"**Cenário inicial**\n\n{enredo_txt}")
                i += 2
                continue
        # Mensagens normais
        if msg["role"] == "user":
            with st.chat_message("user"):
                if msg["content"].strip() != "__ENREDO_INICIAL__":  # nunca exiba o marcador cru
                    st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar="💚"):
                st.markdown(msg["content"])
        i += 1

# ===========================
# INPUT FIXO NO RODAPÉ
# ===========================
if prompt := st.chat_input("Envie sua mensagem para Mary"):
    # balão do usuário imediato
    with st.chat_message("user"):
        st.markdown(prompt)

    # gera resposta e salva
    resposta = gerar_resposta_openrouter(prompt, st.session_state.usuario)
    salvar_interacao(st.session_state.usuario, prompt, resposta)

    # atualiza histórico e exibe a resposta
    st.session_state.mary_log = montar_historico_openrouter(st.session_state.usuario)
    with st.chat_message("assistant", avatar="💚"):
        st.markdown(resposta)
