import streamlit as st
from mongo_utils import montar_memoria_dinamica, salvar_interacao
from persona import PERSONA_MARY, gerar_resposta_mary

st.set_page_config(page_title="Roleplay com Mary Massariol", layout="centered")

st.title("Roleplay | Mary Massariol")

# Identificação do usuário
usuario = st.text_input("Seu nome:", value="welnecker")

# Busca memória dinâmica logo ao abrir/atualizar
if "mary_log" not in st.session_state:
    st.session_state.mary_log = montar_memoria_dinamica(usuario)

# Mostra contexto/memória recente
st.markdown("### Histórico do roleplay:")
st.text(st.session_state.mary_log)

# Input do turno do usuário
msg_usuario = st.text_input("Envie sua mensagem para Mary:", key="mensagem_usuario")

# Dispara geração de resposta
if st.button("Enviar"):
    # Atualiza memória com máximo de tokens permitidos
    memoria = montar_memoria_dinamica(usuario)
    resposta = gerar_resposta_mary(msg_usuario, memoria)
    salvar_interacao(usuario, msg_usuario, resposta)

    # Atualiza histórico e resposta na tela
    st.session_state.mary_log = montar_memoria_dinamica(usuario)
    st.markdown("### Mary responde:")
    st.write(resposta)
    st.markdown("### Histórico atualizado:")
    st.text(st.session_state.mary_log)

