# app/main.py
import re
import streamlit as st
from datetime import datetime

# Importa o módulo inteiro para permitir fallback caso algumas funções não existam
import mongo_utils as mu

st.set_page_config(page_title="Roleplay | Mary Massariol", layout="centered")
st.title("Roleplay | Mary Massariol")

# ==== Seletor de modelo (OpenRouter) ====
st.session_state.setdefault("modelo_escolhido", "deepseek/deepseek-chat-v3-0324")
MODELOS_OPENROUTER = [
    "deepseek/deepseek-chat-v3-0324",
    "anthropic/claude-3.5-haiku",
    "thedrummer/anubis-70b-v1.1",
    "qwen/qwen3-max",
    "nousresearch/hermes-3-llama-3.1-405b",
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

# ===== Campos fixos do topo =====
st.session_state.setdefault("usuario_input", "welnecker")
st.session_state.setdefault("usuario_fixado", None)
st.session_state.setdefault("enredo_inicial", "")
st.session_state.setdefault("enredo_publicado", False)

c1, c2 = st.columns([3, 1])
with c1:
    st.session_state.usuario_input = st.text_input(
        "👤 Usuário",
        value=st.session_state.usuario_input,
        placeholder="Seu nome"
    )
with c2:
    if st.button("✅ Usar este usuário"):
        st.session_state.usuario_fixado = st.session_state.usuario_input.strip()

usuario_atual = st.session_state.get("usuario_fixado")

if not usuario_atual:
    st.info("Defina o usuário e clique em **Usar este usuário**.")
else:
    st.success(f"Usuário ativo: **{usuario_atual}**")

# ==== Memória Canônica (manual) ====
st.sidebar.markdown("---")
st.sidebar.subheader("🧠 Memória Canônica (manual)")

st.session_state.setdefault("mem_tipo", "Fato")
st.session_state.setdefault("mem_chave", "")
st.session_state.setdefault("mem_valor", "")
st.session_state.setdefault("mem_local", "")

st.session_state.mem_tipo = st.sidebar.radio("Tipo de memória", ["Fato", "Evento"], horizontal=True)

# Desabilita salvar/descartar se não tiver usuário ativo
btn_disabled = not bool(usuario_atual)

if st.session_state.mem_tipo == "Fato":
    st.session_state.mem_chave = st.sidebar.text_input(
        "Chave do fato (ex.: primeiro_encontro, cidade_atual)",
        value=st.session_state.mem_chave
    )
    st.session_state.mem_valor = st.sidebar.text_area(
        "Valor do fato (ex.: Café Oregon)",
        value=st.session_state.mem_valor,
        height=80
    )
    colf1, colf2 = st.sidebar.columns(2)
    with colf1:
        if st.button("💾 Salvar fato", disabled=btn_disabled):
            if not usuario_atual:
                st.sidebar.warning("Escolha um usuário antes de salvar.")
            elif st.session_state.mem_chave.strip() and st.session_state.mem_valor.strip():
                mu.state.update_one(
                    {"usuario": usuario_atual},
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
        if st.button("🗑️ Descartar fato", disabled=btn_disabled):
            st.session_state.mem_chave = ""
            st.session_state.mem_valor = ""
            st.sidebar.info("Edição descartada.")
else:
    st.session_state.mem_chave = st.sidebar.text_input(
        "Tipo do evento (ex.: primeiro_encontro, primeira_vez, episodio_ciume_praia)",
        value=st.session_state.mem_chave
    )
    st.session_state.mem_valor = st.sidebar.text_area(
        "Descrição do evento (factual, curta)",
        value=st.session_state.mem_valor,
        height=80
    )
    st.session_state.mem_local = st.sidebar.text_input(
        "Local (opcional)",
        value=st.session_state.mem_local,
        placeholder="Ex.: Café Oregon, Clube Serra Bella, Praia de Camburi"
    )
    cole1, cole2 = st.sidebar.columns(2)
    with cole1:
        if st.button("💾 Salvar evento", disabled=btn_disabled):
            if not usuario_atual:
                st.sidebar.warning("Escolha um usuário antes de salvar.")
            elif st.session_state.mem_chave.strip() and st.session_state.mem_valor.strip():
                # Usa wrapper se existir; caso contrário, cai no registrar_evento simples
                if hasattr(mu, "registrar_evento_canonico"):
                    mu.registrar_evento_canonico(
                        usuario=usuario_atual,
                        tipo=st.session_state.mem_chave.strip(),
                        descricao=st.session_state.mem_valor.strip(),
                        local=(st.session_state.mem_local.strip() or None),
                        data_hora=datetime.utcnow(),
                        atualizar_fatos=True,
                    )
                else:
                    mu.registrar_evento(
                        usuario=usuario_atual,
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
        if st.sidebar.button("🗑️ Descartar evento", disabled=btn_disabled):
            st.session_state.mem_chave = ""
            st.session_state.mem_valor = ""
            st.session_state.mem_local = ""
            st.sidebar.info("Edição descartada.")

# Listagem rápida das memórias já salvas
st.sidebar.markdown("---")
st.sidebar.caption("Memórias salvas")
if usuario_atual:
    try:
        fatos_exist = mu.get_fatos(usuario_atual)
    except Exception:
        fatos_exist = {}
else:
    fatos_exist = {}

if not usuario_atual:
    st.sidebar.info("Escolha um usuário para visualizar memórias.")
else:
    if fatos_exist:
        st.sidebar.markdown("**Fatos**")
        for k, v in fatos_exist.items():
            st.sidebar.write(f"- `{k}` → {v}")
    else:
        st.sidebar.write("_Nenhum fato salvo._")

    st.sidebar.markdown("**Eventos (últimos 5)**")
    for ev in list(
        mu.eventos.find({"usuario": usuario_atual}).sort([("ts", -1)]).limit(5)
    ):
        ts = ev.get("ts").strftime("%Y-%m-%d %H:%M") if ev.get("ts") else "sem data"
        st.sidebar.write(f"- **{ev.get('tipo','?')}** — {ev.get('descricao','?')} ({ev.get('local','?')}) em {ts}")

# ===== Enredo inicial =====
st.session_state.enredo_inicial = st.text_area(
    "📜 Enredo inicial",
    value=st.session_state.enredo_inicial,
    placeholder="Ex.: Mary encontra o usuário depois de um dia difícil...",
    height=80
)

# ===== Controles de memória do chat =====
cc1, cc2, cc3 = st.columns(3)
with cc1:
    if st.button("🔄 Resetar histórico (chat)", disabled=not usuario_atual):
        mu.limpar_memoria_usuario(usuario_atual)
        st.session_state.mary_log = []
        st.session_state.enredo_publicado = False
        st.success(f"Histórico de {usuario_atual} apagado (memórias canônicas preservadas).")

with cc2:
    if st.button("🧠 Apagar TUDO (chat + memórias)", disabled=not usuario_atual):
        mu.apagar_tudo_usuario(usuario_atual)
        st.session_state.mary_log = []
        st.session_state.enredo_publicado = False
        st.success(f"Chat e memórias canônicas de {usuario_atual} foram apagados.")

with cc3:
    if st.button("⏪ Apagar último turno", disabled=not usuario_atual):
        mu.apagar_ultima_interacao_usuario(usuario_atual)
        st.session_state.mary_log = mu.montar_historico_openrouter(usuario_atual)
        st.info("Última interação apagada.")

# ===== Publica ENREDO se necessário =====
if usuario_atual and st.session_state.enredo_inicial.strip() and not st.session_state.enredo_publicado:
    if mu.colecao.count_documents({
        "usuario": {"$regex": f"^{re.escape(usuario_atual)}$", "$options": "i"},
        "mensagem_usuario": "__ENREDO_INICIAL__"
    }) == 0:
        mu.salvar_interacao(usuario_atual, "__ENREDO_INICIAL__", st.session_state.enredo_inicial.strip())
        st.session_state.enredo_publicado = True

# ===== Carrega histórico =====
if usuario_atual:
    st.session_state.mary_log = mu.montar_historico_openrouter(usuario_atual)
else:
    st.session_state.mary_log = []

# ===== Diagnóstico (opcional) =====
with st.expander("🔍 Diagnóstico do banco"):
    try:
        from pymongo import DESCENDING
        st.write(f"**DB**: `{mu.db.name}`")
        st.write(f"**Coleções**: {[c for c in mu.db.list_collection_names()]}")
        if usuario_atual:
            total_hist = mu.colecao.count_documents({"usuario": {"$regex": f"^{re.escape(usuario_atual)}$", "$options": "i"}})
            total_state = mu.state.count_documents({"usuario": usuario_atual})
            total_eventos = mu.eventos.count_documents({"usuario": usuario_atual})
            total_perfil = mu.perfil.count_documents({"usuario": usuario_atual})
            st.write(f"Histórico (`mary_historia`): **{total_hist}**")
            st.write(f"Memória canônica — state: **{total_state}**, eventos: **{total_eventos}**, perfil: **{total_perfil}**")
            if total_hist:
                ult = list(mu.colecao.find({"usuario": {"$regex": f"^{re.escape(usuario_atual)}$", "$options": "i"}}).sort([("_id", DESCENDING)]).limit(5))
                st.write("Últimos 5 (histórico):")
                for d in ult:
                    st.code({
                        "ts": d.get("timestamp"),
                        "user": (d.get("mensagem_usuario") or "")[:120],
                        "mary": (d.get("resposta_mary") or "")[:120],
                    })
            else:
                st.info("Nenhuma interação no histórico para este usuário.")
        else:
            st.info("Escolha um usuário para ver o diagnóstico.")
    except Exception as e:
        st.error(f"Falha no diagnóstico: {e}")

# ===== Chat (render) =====
chat = st.container()
with chat:
    msgs = st.session_state.mary_log
    i = 0
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
if usuario_atual:
    if prompt := st.chat_input("Envie sua mensagem para Mary"):
        with st.chat_message("user"):
            st.markdown(prompt)
        try:
            resposta = mu.gerar_resposta_openrouter(
                prompt, usuario_atual, model=st.session_state.modelo_escolhido
            )
        except Exception as e:
            st.error(f"Falha ao gerar resposta: {e}")
            resposta = "Desculpa, tive um problema para responder agora. Pode tentar de novo?"
        try:
            mu.salvar_interacao(usuario_atual, prompt, resposta)
        except Exception as e:
            st.warning(f"Não consegui salvar a interação: {e}")
        st.session_state.mary_log = mu.montar_historico_openrouter(usuario_atual)
        with st.chat_message("assistant", avatar="💚"):
            st.markdown(resposta)
else:
    st.info("Selecione o usuário para liberar o chat e a memória.")
