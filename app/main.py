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
    registrar_evento,         # já usado para eventos
    get_fatos, get_resumo,    # para listar no sidebar
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
colm1, colm2 = st.columns([4, 1])
with colm1:
    st.session_state.modelo_escolhido = st.selectbox(
        "🧠 Modelo OpenRouter",
        MODELOS_OPENROUTER,
        index=MODELOS_OPENROUTER.index(st.session_state.modelo_escolhido)
        if st.session_state.modelo_escolhido in MODELOS_OPENROUTER else 0
    )
with colm2:
    st.markdown(
        f"""
        <div style="background-color:#222;color:#eee;padding:6px 10px;border-radius:8px;
                    font-size:12px;text-align:center;margin-top:24px;opacity:.8">
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

# ==== Memória Canônica (manual) ====
st.sidebar.markdown("---")
st.sidebar.subheader("🧠 Memória Canônica (manual)")

st.session_state.setdefault("mem_tipo", "Fato")
st.session_state.setdefault("mem_chave", "")
st.session_state.setdefault("mem_valor", "")
st.session_state.setdefault("mem_local", "")

st.session_state.mem_tipo = st.sidebar.radio("Tipo de memória", ["Fato", "Evento"], horizontal=True)

if st.session_state.mem_tipo == "Fato":
    st.session_state.mem_chave = st.sidebar.text_input("Chave do fato (ex.: primeiro_encontro, cidade_atual)", value=st.session_state.mem_chave)
    st.session_state.mem_valor = st.sidebar.text_area("Valor do fato (ex.: Academia)", value=st.session_state.mem_valor, height=80)
    colf1, colf2 = st.sidebar.columns(2)
    with colf1:
        if st.button("💾 Salvar fato"):
            if st.session_state.mem_chave.strip() and st.session_state.mem_valor.strip():
                state.update_one(
                    {"usuario": st.session_state.get("usuario_fixado", "desconhecido")},
                    {
                        "$set": {
                            f"fatos.{st.session_state.mem_chave.strip()}": st.session_state.mem_valor.strip(),
                            f"meta.{st.session_state.mem_chave.strip()}": {"fonte": "manual", "ts": datetime.utcnow()},
                            "atualizado_em": datetime.utcnow(),
                        }
                    },
                    upsert=True
                )
                st.sidebar.success("Fato salvo!")
                st.session_state.mem_chave = ""
                st.session_state.mem_valor = ""
            else:
                st.sidebar.warning("Preencha a chave e o valor do fato.")
    with colf2:
        if st.button("🗑️ Descartar fato"):
            st.session_state.mem_chave = ""
            st.session_state.mem_valor = ""
            st.sidebar.info("Edição descartada.")
else:
    st.session_state.mem_chave = st.sidebar.text_input("Tipo do evento (ex.: primeira_vez, encontro, briga)", value=st.session_state.mem_chave)
    st.session_state.mem_valor = st.sidebar.text_area("Descrição do evento (factual, curta)", value=st.session_state.mem_valor, height=80)
    st.session_state.mem_local = st.sidebar.text_input("Local (opcional)", value=st.session_state.mem_local, placeholder="Ex.: Academia, Praia de Camburi")
    cole1, cole2 = st.sidebar.columns(2)
    with cole1:
        if st.button("💾 Salvar evento"):
            if st.session_state.mem_chave.strip() and st.session_state.mem_valor.strip():
                registrar_evento(
                    usuario=st.session_state.get("usuario_fixado", "desconhecido"),
                    tipo=st.session_state.mem_chave.strip(),
                    descricao=st.session_state.mem_valor.strip(),
                    local=(st.session_state.mem_local.strip() or None),
                    data_hora=datetime.utcnow()
                )
                st.sidebar.success("Evento salvo!")
                st.session_state.mem_chave = ""
                st.session_state.mem_valor = ""
                st.session_state.mem_local = ""
            else:
                st.sidebar.warning("Preencha tipo e descrição do evento.")
    with cole2:
        if st.button("🗑️ Descartar evento"):
            st.session_state.mem_chave = ""
            st.session_state.mem_valor = ""
            st.session_state.mem_local = ""
            st.sidebar.info("Edição descartada.")

# Listagem rápida das memórias já salvas
st.sidebar.markdown("—")
st.sidebar.caption("Memórias salvas")
fatos_exist = get_fatos(st.session_state.get("usuario_fixado", "desconhecido"))
if fatos_exist:
    st.sidebar.markdown("**Fatos**")
    for k, v in fatos_exist.items():
        st.sidebar.write(f"- `{k}` → {v}")
else:
    st.sidebar.write("_Nenhum fato salvo._")
st.sidebar.markdown("**Eventos (últimos 5)**")
for ev in list(eventos.find({"usuario": st.session_state.get("usuario_fixado", "desconhecido")}).sort([("ts", -1)]).limit(5)):
    ts = ev.get("ts").strftime("%Y-%m-%d %H:%M") if ev.get("ts") else "sem data"
    st.sidebar.write(f"- **{ev.get('tipo','?')}** — {ev.get('descricao','?')} ({ev.get('local','?')}) em {ts}")

# ===== Campos fixos do topo =====
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

# ===== Controles de memória do chat =====
cc1, cc2, cc3 = st.columns(3)
with cc1:
    if st.button("🔄 Resetar histórico (chat)"):
        limpar_memoria_usuario(USUARIO)
        st.session_state.mary_log = []
        st.session_state.enredo_publicado = False
        st.success(f"Histórico de {USUARIO} apagado (memórias canônicas preservadas).")

with cc2:
    if st.button("🧠 Apagar TUDO (chat + memórias)"):
        apagar_tudo_usuario(USUARIO)
        st.session_state.mary_log = []
        st.session_state.enredo_publicado = False
        st.success(f"Chat e memórias canônicas de {USUARIO} foram apagados.")

with cc3:
    if st.button("⏪ Apagar último turno"):
        from mongo_utils import apagar_ultima_interacao_usuario
        apagar_ultima_interacao_usuario(USUARIO)
        st.session_state.mary_log = montar_historico_openrouter(USUARIO)
        st.info("Última interação apagada.")

# ===== Publica ENREDO se necessário =====
if st.session_state.enredo_inicial.strip() and not st.session_state.enredo_publicado:
    if colecao.count_documents({
        "usuario": {"$regex": f"^{re.escape(USUARIO)}$", "$options": "i"},
        "mensagem_usuario": "__ENREDO_INICIAL__"
    }) == 0:
        salvar_interacao(USUARIO, "__ENREDO_INICIAL__", st.session_state.enredo_inicial.strip())
        st.session_state.enredo_publicado = True

# ===== Carrega histórico =====
st.session_state.mary_log = montar_historico_openrouter(USUARIO)

# ===== Diagnóstico (opcional) =====
with st.expander("🔍 Diagnóstico do banco"):
    try:
        from pymongo import DESCENDING
        st.write(f"**DB**: `{db.name}`")
        st.write(f"**Coleções**: {[c for c in db.list_collection_names()]}")
        total_hist = colecao.count_documents({"usuario": {"$regex": f"^{re.escape(USUARIO)}$", "$options": "i"}})
        total_state = state.count_documents({"usuario": USUARIO})
        total_eventos = eventos.count_documents({"usuario": USUARIO})
        total_perfil = perfil.count_documents({"usuario": USUARIO})
        st.write(f"Histórico (`mary_historia`): **{total_hist}**")
        st.write(f"Memória canônica — state: **{total_state}**, eventos: **{total_eventos}**, perfil: **{total_perfil}**")
        if total_hist:
            ult = list(colecao.find({"usuario": {"$regex": f"^{re.escape(USUARIO)}$", "$options": "i"}}).sort([("_id", DESCENDING)]).limit(5))
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

# ===== Chat (render) =====
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
        # Mensagens normais
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
