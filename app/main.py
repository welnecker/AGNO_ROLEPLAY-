# app/main.py
import streamlit as st
from datetime import datetime
from typing import Optional, List, Tuple

from mongo_utils import (
    montar_historico_openrouter,
    salvar_interacao,
    gerar_resposta_openrouter,
    limpar_memoria_usuario,       # só chat
    limpar_memoria_canonica,      # só memórias canônicas
    apagar_tudo_usuario,          # chat + memórias
)

# ---- imports opcionais (podem não existir ainda no seu mongo_utils) ----
HAS_CANON = True
try:
    from mongo_utils import registrar_evento, set_fato, ultimo_evento, get_fatos
except Exception:
    HAS_CANON = False

# ================== Setup ==================
st.set_page_config(page_title="Roleplay | Mary Massariol", layout="centered")
st.title("Roleplay | Mary Massariol")

def canon(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()

# ================== Sidebar: identidade visual ==================
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

# ================== Campos fixos (usuário/enredo) ==================
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
        st.session_state.usuario_fixado = canon(st.session_state.usuario_input)

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

# ================== Controles de memória/chat ==================
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

# ================== Carrega histórico ==================
st.session_state.mary_log = montar_historico_openrouter(USUARIO)

# ================== Publicação inicial (Enredo + Elenco) ==================
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

# ================== Sidebar: Memória Canônica (assistida) ==================
st.sidebar.markdown("---")
st.sidebar.subheader("🧠 Memória Canônica (assistida)")

if not HAS_CANON:
    st.sidebar.info(
        "Painel desativado: exponha no `mongo_utils.py` as funções "
        "`set_fato`, `registrar_evento`, `get_fatos` e `ultimo_evento` "
        "ou use a versão com coleção única `memorias`."
    )
else:
    # Vocabulário simples de locais (catálogo mínimo)
    KNOWN_LOCATIONS = {
        "academia": {"academia", "gym", "musculação", "box"},
        "biblioteca": {"biblioteca", "biblio"},
        "serra bella": {"serra bella", "serra bela", "clube serra bella"},
        "ufes": {"ufes", "universidade federal do espírito santo"},
        "estacionamento": {"estacionamento", "vaga", "pátio"},
        "praia": {"praia", "areia", "beira-mar"},
        "motel status": {"motel status", "status"},
        "café oregon": {"café oregon", "cafe oregon", "oregon"},
        "enseada do suá": {"enseada do suá", "enseada"},
    }
    LOCAL_KEYS = [
        "primeiro_encontro",
        "primeira_vez_local",
        "pedido_namoro_local",
        "episodio_ciume_local",
    ]

    def _norm(s: Optional[str]) -> str:
        return " ".join((s or "").strip().lower().split())

    def _detect_location(text: str) -> Optional[str]:
        t = _norm(text)
        for label, variants in KNOWN_LOCATIONS.items():
            for v in variants:
                if v in t:
                    return label
        return None

    def _sugerir_fatos(mensagens: List[dict]) -> List[Tuple[str, str, str]]:
        """Retorna sugestões (key, value, justificativa) com base nas últimas 6 mensagens."""
        sugestoes: List[Tuple[str, str, str]] = []
        janela = mensagens[-6:] if len(mensagens) > 6 else mensagens
        gatilhos_primeiro_encontro = {"primeiro encontro", "primeira vez que nos vimos", "nos vimos pela primeira vez"}
        gatilhos_primeira_vez = {"primeira vez", "deixou de ser virgem"}
        gatilhos_pedido = {"pedido de namoro", "oficializamos", "ficamos oficiais"}
        gatilhos_ciume = {"ciúme", "ciume", "protetor", "afugentou", "afastou", "flertar com você na praia"}

        for msg in janela:
            txt = msg.get("content", "")
            loc = _detect_location(txt)  # pode ser None
            t = _norm(txt)

            if loc and any(g in t for g in gatilhos_primeiro_encontro):
                sugestoes.append(("primeiro_encontro", loc, "Detectado 'primeiro encontro' + local"))
            if loc and any(g in t for g in gatilhos_primeira_vez):
                sugestoes.append(("primeira_vez_local", loc, "Detectado 'primeira vez' + local"))
            if loc and any(g in t for g in gatilhos_pedido):
                sugestoes.append(("pedido_namoro_local", loc, "Detectado 'pedido de namoro' + local"))
            if any(g in t for g in gatilhos_ciume) and loc:
                sugestoes.append(("episodio_ciume_local", loc, "Detectado episódio de ciúme + local"))

        # dedup mantendo ordem
        seen, uniq = set(), []
        for k, v, j in sugestoes:
            sig = (k, v)
            if sig not in seen:
                uniq.append((k, v, j))
                seen.add(sig)
        return uniq

    msgs_atual = st.session_state.get("mary_log", [])
    sugs = _sugerir_fatos(msgs_atual)

    with st.sidebar.expander("Sugestões a partir do diálogo", expanded=bool(sugs)):
        if not sugs:
            st.caption("Sem sugestões automáticas no momento.")
        else:
            idx = st.selectbox(
                "Escolha uma sugestão",
                options=list(range(len(sugs))),
                format_func=lambda i: f"{sugs[i][0]} = {sugs[i][1]}  ·  {sugs[i][2]}",
            )
            key_sug, val_sug, _ = sugs[idx]
            key_edit = st.text_input("Chave (fato canônico)", value=key_sug, key="fact_key_edit")
            val_edit = st.text_input("Valor (ex.: academia, praia...)", value=val_sug, key="fact_val_edit")
            salvar_como_evento = st.checkbox("Também registrar como evento datado", value=False, key="fact_as_event")
            if salvar_como_evento:
                evento_tipo = st.text_input("Tipo do evento", value=key_edit.replace("_local", "").replace("_", " "), key="fact_event_type")
                evento_local = st.text_input("Local do evento", value=val_edit, key="fact_event_local")
            if st.button("💾 Salvar fato canônico"):
                set_fato(USUARIO, key_edit.strip(), val_edit.strip())
                if salvar_como_evento:
                    registrar_evento(
                        USUARIO,
                        tipo=_norm(evento_tipo or key_edit),
                        descricao=f"{key_edit} = {val_edit}",
                        local=(evento_local or val_edit),
                        data_hora=datetime.utcnow(),
                        tags=[key_edit],
                    )
                st.success(f"Salvo: {key_edit} = {val_edit}")

    with st.sidebar.expander("Fatos canônicos salvos"):
        try:
            fatos = get_fatos(USUARIO)
        except Exception as e:
            fatos = {}
        if not fatos:
            st.caption("Nenhum fato salvo ainda.")
        else:
            for k, v in fatos.items():
                st.write(f"• **{k}** = {v}")
            k_edit2 = st.selectbox("Editar chave", ["(selecionar)"] + list(fatos.keys()), key="fact_edit_select")
            if k_edit2 != "(selecionar)":
                v_edit2 = st.text_input("Novo valor", value=str(fatos[k_edit2]), key="fact_edit_value")
                if st.button("✏️ Atualizar fato"):
                    set_fato(USUARIO, k_edit2, v_edit2)
                    st.success(f"Atualizado: {k_edit2} = {v_edit2}")

# ================== Diagnóstico ==================
with st.expander("🔍 Diagnóstico do banco"):
    try:
        from pymongo import DESCENDING
        # primeiro tenta coleção unificada 'memorias'
        try:
            from mongo_utils import db, colecao, memorias
            tem_memorias = True
        except Exception:
            from mongo_utils import db, colecao, state, eventos, perfil
            tem_memorias = False

        st.write(f"**DB**: `{db.name}`")
        st.write(f"**Coleções**: {[c for c in db.list_collection_names()]}")

        total_hist = colecao.count_documents({"usuario": USUARIO})
        if tem_memorias:
            total_state  = memorias.count_documents({"usuario": USUARIO, "kind": "state"})
            total_eventos= memorias.count_documents({"usuario": USUARIO, "kind": "evento"})
            total_perfil = memorias.count_documents({"usuario": USUARIO, "kind": "perfil"})
        else:
            total_state  = state.count_documents({"usuario": USUARIO}) if 'state' in dir() else 0
            total_eventos= eventos.count_documents({"usuario": USUARIO}) if 'eventos' in dir() else 0
            total_perfil = perfil.count_documents({"usuario": USUARIO}) if 'perfil' in dir() else 0

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

# ================== Chat ==================
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

        # ⚠️ REMOVIDO: bloco especial de elenco (__ELENCO__)

        # Mensagens normais
        if msg["role"] == "user":
            with st.chat_message("user"):
                if msg["content"].strip() not in {"__ENREDO_INICIAL__", "__ELENCO__"}:
                    st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar="💚"):
                st.markdown(msg["content"])
        i += 1


# ================== Input fixo no rodapé ==================
if prompt := st.chat_input("Envie sua mensagem para Mary"):
    with st.chat_message("user"):
        st.markdown(prompt)
    resposta = gerar_resposta_openrouter(prompt, USUARIO)
    salvar_interacao(USUARIO, prompt, resposta)
    st.session_state.mary_log = montar_historico_openrouter(USUARIO)
    with st.chat_message("assistant", avatar="💚"):
        st.markdown(resposta)
