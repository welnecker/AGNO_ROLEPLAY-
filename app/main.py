import streamlit as st
from mongo_utils import montar_historico_openrouter, salvar_interacao, gerar_resposta_openrouter

st.set_page_config(page_title="Roleplay com Mary Massariol", layout="centered")
st.title("Roleplay | Mary Massariol")

# Identificação do usuário
usuario = st.text_input("Seu nome:", value="welnecker")

# Monta histórico de memória longo ao abrir/atualizar
if "mary_log" not in st.session_state:
    # Recupera histórico em ChatML (lista de mensagens do Mongo)
    st.session_state.mary_log = montar_historico_openrouter(usuario)

# Exibe contexto/memória recente (mostra apenas mensagens do usuário e da Mary em texto)
st.markdown("### Histórico do roleplay:")
for msg in st.session_state.mary_log:
    if msg["role"] == "user":
        st.write(f"**Você:** {msg['content']}")
    elif msg["role"] == "assistant":
        st.write(f"**Mary:** {msg['content']}")

# Input do turno do usuário
msg_usuario = st.text_input("Envie sua mensagem para Mary:", key="mensagem_usuario")

# Dispara geração da resposta
if st.button("Enviar"):
    historico = montar_historico_openrouter(usuario)  # histórico para envio em contexto
    resposta = gerar_resposta_openrouter(msg_usuario, history=historico)
    salvar_interacao(usuario, msg_usuario, resposta)

    # Atualiza histórico e resposta na tela
    st.session_state.mary_log = montar_historico_openrouter(usuario)
    st.markdown("### Mary responde:")
    st.write(resposta)
    st.markdown("### Histórico atualizado:")
    for msg in st.session_state.mary_log:
        if msg["role"] == "user":
            st.write(f"**Você:** {msg['content']}")
        elif msg["role"] == "assistant":
            st.write(f"**Mary:** {msg['content']}")
