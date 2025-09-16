# app/main.py
import streamlit as st
from mongo_utils import (
    montar_historico_openrouter,
    salvar_interacao,
    gerar_resposta_openrouter,
    limpar_memoria_usuario,       # só chat
    limpar_memoria_canonica,      # só memórias canônicas
    apagar_tudo_usuario,          # chat + memórias
    registrar_evento, set_fato, ultimo_evento  # (se usar botões de memória canônica)
)

st.set_page_config(page_title="Roleplay | Mary Massariol", layout="centered")
st.title("Roleplay | Mary Massariol")

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
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("🔄 Resetar histórico (chat)"):
        limpar_memoria_usuario(USUARIO)
        st.session_state.mary_log = []
        st.session_state.enredo_publicado = False
        st.session_state.elenco_publicado = False
        st.success(f"Histórico de {USUARIO} apagado (memórias canônicas preservadas).")

with c2:
    if st.button("🧠 Apagar TUDO (chat + memórias)"):
        apagar_tudo_usuario(USUARIO)
        st.session_state.mary_log = []
        st.session_state.enredo_publicado = False
        st.session_state.elenco_publicado = False
        st.success(f"Chat e memórias canônicas de {USUARIO} foram apagados.")

with c3:
    if st.button("⏪ Apagar último turno"):
        from mongo_utils import apagar_ultima_interacao_usuario
        apagar_ultima_interacao_usuario(USUARIO)
        st.session_state.mary_log = montar_historico_openrouter(USUARIO)
        st.info("Última interação apagada.")

# ===== Carrega histórico =====
st.session_state.mary_log = montar_historico_openrouter(USUARIO)

# ===== Publicação inicial (Enredo + Elenco em um passo) =====
if not st.session_state.mary_log:
    inseriu_algo = False
    if st.session_state.enredo_inicial.strip() and not st.session_state.enredo_publicado:
        salvar_interacao(USUARIO, "__ENREDO_INICIAL__", st.session_state.enredo_inicial.strip())
        st.session_state.enredo_publicado = True
        inseriu_algo = True
    if not st.session_state.elenco_publicado:
        elenco_txt = (
            "**Elenco de apoio**\n\n"
            "- **Silvia Bodat** — extrovertida, bem-humorada; puxa conversa e descontrai.\n"
            "- **Alexandra Resinentti** — reservada, conselheira; fala pouco e vai direto ao ponto.\n\n"
            "_Aparecem como apoio (fofocas, conselhos, contexto), sem tirar o foco do usuário._"
        )
        salvar_interacao(USUARIO, "__ELENCO__", elenco_txt)
        st.session_state.elenco_publicado = True
        inseriu_algo = True
    if inseriu_algo:
        st.session_state.mary_log = montar_historico_openrouter(USUARIO)

# ===== Diagnóstico (opcional, útil) =====
with st.expander("🔍 Diagnóstico do banco"):
    try:
        from pymongo import DESCENDING
        from mongo_utils import db, colecao, state, eventos, perfil
        st.write(f"**DB**: `{db.name}`")
        st.write(f"**Coleções**: {[c for c in db.list_collection_names()]}")
        total_hist = colecao.count_documents({"usuario": USUARIO})
        total_state = state.count_documents({"usuario": USUARIO})
        total_eventos = eventos.count_documents({"usuario": USUARIO})
        total_perfil = perfil.count_documents({"usuario": USUARIO})
        st.write(f"Histórico (`mary_historia`): **{total_hist}**")
        st.write(f"Memória canônica — state: **{total_state}**, eventos: **{total_eventos}**, perfil: **{total_perfil}**")
        if total_hist:
            ult = list(colecao.find({"usuario": USUARIO}).sort([("_id", DESCENDING)]).limit(5))
            st.write("Últimos 5 (histórico):")
            for d in ult:
                st.code({
                    "ts": d.get("timestamp"),
                    "user": (d.get("mensagem_usuario") or "")[:120],
                    "mary": (d.get("resposta_mary") or "")[:120],
                })
        else:
            st.info("Nenhuma interação no histórico para este usuário.")
    except Exception as e:
        st.error(f"Falha no diagnóstico: {e}")

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
