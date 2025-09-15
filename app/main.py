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

usuario = st.text_input("Seu nome:", value="welnecker")

# Botão para resetar todo o histórico do usuário
if st.button("🔄 Resetar histórico"):
    limpar_memoria_usuario(usuario)
    st.session_state.mary_log = []
    st.success(f"Memória de {usuario} apagada com sucesso!")

# Botão para apagar só a última interação/resposta
if st.button("⏪ Apagar último turno"):
    apagar_ultima_interacao_usuario(usuario)
    st.session_state.mary_log = montar_historico_openrouter(usuario)
    st.info("Última interação apagada.")

# Monta e exibe histórico atualizado
if "mary_log" not in st.session_state:
    st.session_state.mary_log = montar_historico_openrouter(usuario)

st.markdown("### Histórico do roleplay:")
for msg in st.session_state.mary_log:
    if msg["role"] == "user":
        st.write(f"**Você:** {msg['content']}")
    elif msg["role"] == "assistant":
        st.write(f"**Mary:** {msg['content']}")

msg_usuario = st.text_input("Envie sua mensagem para Mary:", key="mensagem_usuario")

if st.button("Enviar"):
    historico = montar_historico_openrouter(usuario)
    resposta = gerar_resposta_openrouter(msg_usuario, history=historico)
    salvar_interacao(usuario, msg_usuario, resposta)
    st.session_state.mary_log = montar_historico_openrouter(usuario)
    st.markdown("### Mary responde:")
    st.write(resposta)
    st.markdown("### Histórico atualizado:")
    for msg in st.session_state.mary_log:
        if msg["role"] == "user":
            st.write(f"**Você:** {msg['content']}")
        elif msg["role"] == "assistant":
            st.write(f"**Mary:** {msg['content']}")

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
