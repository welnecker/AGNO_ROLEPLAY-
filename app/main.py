# app/main.py
import re
import streamlit as st
from datetime import datetime
import mongo_utils


# ==== Importação eficiente e diagnóstico de mongo_utils ====
try:
    import mongo_utils as mu
except Exception as e:
    mu = None
    st.error(f"Falha ao importar mongo_utils: {e}")

# ==== Configuração da página ====
st.set_page_config(page_title="Roleplay | Mary Massariol", layout="centered")
st.title("Roleplay | Mary Massariol")

# ==== Helpers: State Defaults ====
def default_state(key, val):
    if key not in st.session_state:
        st.session_state[key] = val

# ==== Inicialização canônica Janio ====
def ensure_janio_context(usuario: str,
    registrar_primeiro_encontro=True, registrar_primeira_vez=False, seed_fatos=True, overrides=None):
    """Garante contexto canônico do parceiro Janio imediatamente com mínimo side-effect em rede."""
    if not mu:
        return
    try:
        fatos = mu.get_fatos(usuario) or {}
        defaults = {
            "parceiro_atual": "Janio",
            "janio_nome": "Janio Donisete",
            "janio_profissao": "Personal trainer",
            "janio_local_trabalho": "Academia Fisium Body",
            "janio_moradia": "Apartamento em Camburi (próximo à orla)",
            "janio_cidade": "Vitória/ES",
            "janio_estilo": "calmo, protetor, competitivo no treino; carinhoso no afeto",
            "janio_limites": "respeita consentimento; não tolera traição",
            "janio_locais_publicos": [
                "Cafeteria Oregon", "Quiosque Posto 6", "Clube Náutico", "Praia de Camburi"
            ],
            "status_relacao": fatos.get("status_relacao", "ficando"),
        }
        if overrides:
            defaults.update(overrides)
        if fatos.get("parceiro_atual") != "Janio":
            mu.set_fato(usuario, "parceiro_atual", "Janio", meta={"fonte": "auto-init"})
        if seed_fatos:
            for chave, valor in defaults.items():
                if fatos.get(chave) != valor:
                    mu.set_fato(usuario, chave, valor, meta={"fonte": "auto-init"})
        if registrar_primeiro_encontro and not mu.ultimo_evento(usuario, "primeiro_encontro"):
            mu.registrar_evento(usuario=usuario, tipo="primeiro_encontro",
                descricao="Mary e Janio se conheceram oficialmente.",
                local="praia de Camburi", data_hora=datetime.utcnow(), tags=["primeiro_contato"])
            mu.set_fato(usuario, "primeiro_encontro", "Janio - Praia de Camburi", meta={"fonte": "auto-init"})
        if registrar_primeira_vez and not mu.ultimo_evento(usuario, "primeira_vez"):
            mu.registrar_evento(usuario=usuario, tipo="primeira_vez",
                descricao="Mary e Janio tiveram sua primeira vez.",
                local="motel status", data_hora=datetime.utcnow(), tags=["nsfw_liberado"])
            mu.set_fato(usuario, "virgem", False, meta={"fonte": "auto-init"})
    except Exception as e:
        st.warning(f"Não foi possível inicializar o contexto do Janio: {e}")

# ==== Selectbox modelo e layout ====
MODELOS_OPENROUTER = [
    "deepseek/deepseek-chat-v3-0324",
    "anthropic/claude-3.5-haiku",
    "thedrummer/anubis-70b-v1.1",
    "qwen/qwen3-max",
    "nousresearch/hermes-3-llama-3.1-405b",
]
default_state("modelo_escolhido", MODELOS_OPENROUTER[0])
colm1, colm2 = st.columns([4, 1])
with colm1:
    st.session_state.modelo_escolhido = st.selectbox(
        "🧠 Modelo OpenRouter", MODELOS_OPENROUTER,
        index=MODELOS_OPENROUTER.index(st.session_state.modelo_escolhido)
    )
with colm2:
    st.markdown(
        f"""
        <div style="background-color:#222;color:#eee;padding:6px 10px;border-radius:8px;font-size:12px;text-align:center;margin-top:24px;opacity:.8">
            <b>{st.session_state.modelo_escolhido}</b>
        </div>
        """, unsafe_allow_html=True
    )

# ==== Sidebar: imagem/avatar e créditos ====
st.sidebar.title("Mary Massariol")
st.sidebar.caption("Roleplay imersivo")
default_state("sidebar_img_url", "")
default_state("sidebar_credito", "")
st.sidebar.subheader("Imagem (URL)")
st.session_state.sidebar_img_url = st.sidebar.text_input("Cole uma URL de imagem", value=st.session_state.sidebar_img_url)
st.sidebar.subheader("Ou envie um arquivo")
upload_file = st.sidebar.file_uploader("PNG/JPG", type=["png", "jpg", "jpeg"])
img_shown = False
if upload_file:
    st.sidebar.image(upload_file, use_container_width=True)
    img_shown = True
elif st.session_state.sidebar_img_url.strip():
    try:
        st.sidebar.image(st.session_state.sidebar_img_url.strip(), use_container_width=True)
        img_shown = True
    except Exception:
        st.sidebar.warning("Não foi possível carregar a imagem da URL.")
st.session_state.sidebar_credito = st.sidebar.text_input("Crédito/legenda (opcional)", value=st.session_state.sidebar_credito)
if img_shown and st.session_state.sidebar_credito.strip():
    st.sidebar.caption(st.session_state.sidebar_credito.strip())

# ==== Usuário: bind fixo/simplificado ====
default_state("usuario_input", "welnecker")
default_state("usuario_fixado", None)
default_state("enredo_inicial", "")
default_state("enredo_publicado", False)
c1, c2 = st.columns([3, 1])
with c1:
    st.session_state.usuario_input = st.text_input("👤 Usuário", value=st.session_state.usuario_input)
with c2:
    if st.button("✅ Usar este usuário"):
        st.session_state.usuario_fixado = st.session_state.usuario_input.strip()
usuario_atual = st.session_state.get("usuario_fixado")
if not usuario_atual:
    st.info("Defina o usuário e clique em **Usar este usuário**.")
else:
    st.success(f"Usuário ativo: **{usuario_atual}**")
    ensure_janio_context(usuario_atual, registrar_primeiro_encontro=True, registrar_primeira_vez=False)

# ==== Sidebar: memória canônica, modularizada ====
st.sidebar.markdown("---")
st.sidebar.subheader("🧠 Memória Canônica (manual)")
default_state("mem_tipo", "Fato")
default_state("mem_chave", "")
default_state("mem_valor", "")
default_state("mem_local", "")
st.session_state.mem_tipo = st.sidebar.radio("Tipo de memória", ["Fato", "Evento"], horizontal=True)
btn_disabled = not usuario_atual or mu is None
def limpar_mem_fields():
    st.session_state.mem_chave = ""
    st.session_state.mem_valor = ""
    st.session_state.mem_local = ""
def salvar_fato():
    if not (usuario_atual and mu):
        st.sidebar.warning("Escolha um usuário e verifique a conexão com o banco.")
        return
    if st.session_state.mem_chave.strip() and st.session_state.mem_valor.strip():
        mu.set_fato(
            usuario_atual,
            st.session_state.mem_chave.strip(),
            st.session_state.mem_valor.strip(),
            meta={"fonte": "manual", "ts": datetime.utcnow()}
        )
        st.sidebar.success("Fato salvo!")
        limpar_mem_fields()
    else:
        st.sidebar.warning("Preencha a chave e o valor do fato.")
def salvar_evento():
    if not (usuario_atual and mu):
        st.sidebar.warning("Escolha um usuário e verifique a conexão com o banco.")
        return
    if st.session_state.mem_chave.strip() and st.session_state.mem_valor.strip():
        mu.registrar_evento(
            usuario=usuario_atual,
            tipo=st.session_state.mem_chave.strip(),
            descricao=st.session_state.mem_valor.strip(),
            local=(st.session_state.mem_local.strip() or None),
            data_hora=datetime.utcnow()
        )
        st.sidebar.success("Evento salvo!")
        limpar_mem_fields()
    else:
        st.sidebar.warning("Preencha tipo e descrição do evento.")
# Inputs memória
if st.session_state.mem_tipo == "Fato":
    st.session_state.mem_chave = st.sidebar.text_input("Chave do fato", value=st.session_state.mem_chave)
    st.session_state.mem_valor = st.sidebar.text_area("Valor do fato", value=st.session_state.mem_valor, height=80)
    colf1, colf2 = st.sidebar.columns(2)
    with colf1: st.button("💾 Salvar fato", disabled=btn_disabled, on_click=salvar_fato)
    with colf2: st.button("🗑️ Descartar fato", disabled=btn_disabled, on_click=limpar_mem_fields)
else:
    st.session_state.mem_chave = st.sidebar.text_input("Tipo do evento", value=st.session_state.mem_chave)
    st.session_state.mem_valor = st.sidebar.text_area("Descrição do evento", value=st.session_state.mem_valor, height=80)
    st.session_state.mem_local = st.sidebar.text_input("Local (opcional)", value=st.session_state.mem_local)
    cole1, cole2 = st.sidebar.columns(2)
    with cole1: st.button("💾 Salvar evento", disabled=btn_disabled, on_click=salvar_evento)
    with cole2: st.button("🗑️ Descartar evento", disabled=btn_disabled, on_click=limpar_mem_fields)

# ==== Sidebar: listagem rápida das memórias ====
st.sidebar.markdown("---")
st.sidebar.caption("Memórias salvas")
def listar_fatos():
    try:
        if usuario_atual and mu:
            fatos_exist = mu.get_fatos(usuario_atual)
            if fatos_exist:
                st.sidebar.markdown("**Fatos**")
                for k, v in fatos_exist.items():
                    st.sidebar.write(f"- `{k}` → {v}")
            else:
                st.sidebar.write("_Nenhum fato salvo._")
    except Exception:
        st.sidebar.warning("Falha ao recuperar fatos.")
def listar_eventos():
    try:
        if usuario_atual and mu:
            eventos = mu.eventos.find({"usuario": usuario_atual}).sort([("ts", -1)]).limit(5)
            st.sidebar.markdown("**Eventos (últimos 5)**")
            for ev in eventos:
                ts = ev.get("ts").strftime("%Y-%m-%d %H:%M") if ev.get("ts") else "sem data"
                st.sidebar.write(f"- **{ev.get('tipo','?')}** — {ev.get('descricao','?')} ({ev.get('local','?')}) em {ts}")
    except Exception:
        st.sidebar.warning("Falha ao recuperar eventos.")
if usuario_atual: listar_fatos(); listar_eventos()
else: st.sidebar.info("Escolha um usuário para visualizar memórias.")

# ==== Enredo inicial, reset, apagar memória: DRY ====
default_state("mary_log", [])
reset_buttons = {
    "🔄 Resetar histórico (chat)": ("limpar_memoria_usuario", True),
    "🧠 Apagar TUDO (chat + memórias)": ("apagar_tudo_usuario", False),
    "⏪ Apagar último turno": ("apagar_ultima_interacao_usuario", False)
}
cc1, cc2, cc3 = st.columns(3)
for i, (txt, (fn, clear_only_chat)) in enumerate(list(reset_buttons.items())):
    def fn_closure(fn=fn, only_chat=clear_only_chat):
        if usuario_atual and mu:
            getattr(mu, fn)(usuario_atual)
            st.session_state.mary_log = mu.montar_historico_openrouter(usuario_atual) if only_chat or fn == "apagar_ultima_interacao_usuario" else []
            st.success(f"Ação concluída para {usuario_atual}.")
    if i == 0: cc = cc1
    elif i == 1: cc = cc2
    else: cc = cc3
    cc.button(txt, disabled=btn_disabled, on_click=fn_closure)

# ==== Publicação do Enredo inicial (proteção contra duplicidade e erro) ====
if usuario_atual and st.session_state.enredo_inicial.strip() and not st.session_state.enredo_publicado and mu:
    try:
        if mu.colecao.count_documents({
            "usuario": {"$regex": f"^{re.escape(usuario_atual)}$", "$options": "i"},
            "mensagem_usuario": "__ENREDO_INICIAL__"
        }) == 0:
            mu.salvar_interacao(usuario_atual, "__ENREDO_INICIAL__", st.session_state.enredo_inicial.strip())
            st.session_state.enredo_publicado = True
    except Exception as e:
        st.warning(f"Não foi possível publicar o enredo: {e}")

# ==== Carrega histórico ====
if usuario_atual and mu:
    st.session_state.mary_log = mu.montar_historico_openrouter(usuario_atual)
else:
    st.session_state.mary_log = []

# ==== Diagnóstico (opcional) DRY ====
with st.expander("🔍 Diagnóstico do banco"):
    try:
        if not mu:
            raise RuntimeError("mongo_utils não disponível.")
        from pymongo import DESCENDING
        db = mu.db
        st.write(f"**DB**: `{db.name}`")
        st.write(f"**Coleções**: {[c for c in db.list_collection_names()]}")
        if usuario_atual:
            valores = [
                ("Histórico", mu.colecao, {"usuario": {"$regex": f"^{re.escape(usuario_atual)}$", "$options": "i"}}, 'mary_historia'),
                ("Memória", mu.state, {"usuario": usuario_atual}, 'state'),
                ("Eventos", mu.eventos, {"usuario": usuario_atual}, 'eventos'),
                ("Perfil", mu.perfil, {"usuario": usuario_atual}, 'perfil'),
            ]
            for nome, col, filt, tag in valores:
                cnt = col.count_documents(filt)
                st.write(f"{nome} ({tag}): **{cnt}**")
            ult = list(mu.colecao.find({"usuario": {"$regex": f"^{re.escape(usuario_atual)}$", "$options": "i"}})
                       .sort([("_id", DESCENDING)]).limit(5))
            if ult:
                st.write("Últimos 5 (histórico):")
                for d in ult:
                    st.code({
                        "ts": d.get("timestamp"),
                        "user": (d.get("mensagem_usuario") or "")[:120],
                        "mary": (d.get("resposta_mary") or "")[:120]})
            else:
                st.info("Nenhuma interação no histórico para este usuário.")
        else:
            st.info("Escolha um usuário para ver o diagnóstico.")
    except Exception as e:
        st.error(f"Falha no diagnóstico: {e}")

# ==== Render do chat ====
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
    if msg["role"] == "user":
        with st.chat_message("user"):
            if msg["content"].strip() != "__ENREDO_INICIAL__":
                st.markdown(msg["content"])
    else:
        with st.chat_message("assistant", avatar="💚"):
            st.markdown(msg["content"])
    i += 1

# ==== Input fixo no rodapé ====
if usuario_atual:
    if prompt := st.chat_input("Envie sua mensagem para Mary"):
        with st.chat_message("user"):
            st.markdown(prompt)
        resposta = ""
        try:
            if mu:
                resposta = mu.gerar_resposta_openrouter(
                    prompt, usuario_atual, model=st.session_state.modelo_escolhido
                )
            else:
                raise RuntimeError("mongo_utils indisponível — não foi possível gerar resposta.")
        except Exception as e:
            st.error(f"Falha ao gerar resposta: {e}")
            resposta = "Desculpa, tive um problema para responder agora. Pode tentar de novo?"
        try:
            if mu:
                mu.salvar_interacao(usuario_atual, prompt, resposta)
        except Exception as e:
            st.warning(f"Não consegui salvar a interação: {e}")
        if mu:
            st.session_state.mary_log = mu.montar_historico_openrouter(usuario_atual)
        with st.chat_message("assistant", avatar="💚"):
            st.markdown(resposta)
else:
    st.info("Selecione o usuário para liberar o chat e a memória.")
