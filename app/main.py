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

# Botão para resetar histórico do usuário
if st.button("🔄 Resetar histórico"):
    limpar_memoria_usuario(usuario)
    st.session_state.mary_log = []
    if "mensagem_usuario" in st.session_state:
        del st.session_state["mensagem_usuario"]
    st.success(f"Memória de {usuario} apagada com sucesso!")

# Botão para apagar só a última interação
if st.button("⏪ Apagar último turno"):
    apagar_ultima_interacao_usuario(usuario)
    st.session_state.mary_log = montar_historico_openrouter(usuario)
    st.info("Última interação apagada.")

# Monta histórico ao abrir ou após ação
if "mary_log" not in st.session_state:
    st.session_state.mary_log = montar_historico_openrouter(usuario)

st.markdown("### Histórico do roleplay:")
for msg in st.session_state.mary_log:
    if msg["role"] == "user":
        st.write(f"**Você:** {msg['content']}")
    elif msg["role"] == "assistant":
        st.write(f"**Mary:** {msg['content']}")

# Input do turno do usuário (apenas uma vez)
msg_usuario = st.text_input("Envie sua mensagem para Mary:", key="mensagem_usuario")

# Dispara geração de resposta (apenas uma vez)
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
