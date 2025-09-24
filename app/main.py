# app/main.py
import re
import hashlib
import streamlit as st
from datetime import datetime

# Fuso horário (America/Sao_Paulo)
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
    TZ = ZoneInfo("America/Sao_Paulo")
except Exception:  # fallback
    TZ = None

# Import protegido do mongo_utils
try:
    import mongo_utils as mu
except Exception as e:
    mu = None
    st.error(f"Falha ao importar mongo_utils: {e}")

st.set_page_config(page_title="Roleplay | Mary Massariol", layout="centered")
st.title("Roleplay | Mary Massariol")

# --- Helpers de tempo/ids ---
def _now_iso():
    dt = datetime.now(TZ) if TZ else datetime.utcnow()
    return dt.isoformat()

def _event_id(usuario: str, tipo: str, descricao: str) -> str:
    raw = f"{usuario}|{tipo}|{descricao}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]

# --- Inferidor e normalizador de LOCAL da cena ---
_CANON_LOCAIS_UI = {
    "Praia de Camburi": "praia de camburi",
    "Academia Fisium Body": "academia fisium body",
    "Clube Náutico": "clube náutico",
    "Cafeteria Oregon": "cafeteria oregon",
    "Restaurante Partido Alto": "restaurante partido alto",
    "Enseada do Suá": "enseada do suá",
    "Motel Status": "motel status",
}

def _inferir_local_do_prompt(prompt: str) -> str | None:
    t = (prompt or "").lower()
    # praia
    if re.search(r"\b(praia|areia|onda|biqu[ií]ni|sunga|quiosque|coco|guarda-?sol|orla|mar)\b", t):
        return "praia de camburi"
    # academia
    if re.search(r"\b(academia|fisium|halter|barra|anilha|agachamento|repeti[cç][aã]o|s[eé]rie|aparelho|esteira|gl[uú]teo)\b", t):
        return "academia fisium body"
    # balada
    if re.search(r"\b(clube\s*náutico|náutico|balada|pista|dj)\b", t):
        return "clube náutico"
    # cafeteria
    if re.search(r"\b(cafeteria|café\s*oregon|oregon|capuccino)\b", t):
        return "cafeteria oregon"
    # restaurante
    if re.search(r"\b(partido\s*alto|restaurante|almo[cç]o|gar[cç]om)\b", t):
        return "restaurante partido alto"
    # enseada
    if re.search(r"\b(enseada\s*do\s*su[aá]|enseada)\b", t):
        return "enseada do suá"
    # motel
    if re.search(r"\b(motel\s*status|motel|su[ií]te|neon)\b", t):
        return "motel status"
    return None

def _fixar_local(usuario: str, local_canon: str | None):
    if mu is None or not usuario:
        return
    try:
        if local_canon:
            mu.set_fato(usuario, "local_cena_atual", local_canon, meta={"fonte": "ui/infer", "ts": _now_iso()})
        else:
            # limpar (modo auto)
            mu.set_fato(usuario, "local_cena_atual", "", meta={"fonte": "ui/infer", "ts": _now_iso(), "clear": True})
    except Exception:
        pass



def ensure_janio_context(
    usuario: str,
    registrar_primeiro_encontro: bool = True,
    registrar_primeira_vez: bool = False,
    seed_fatos: bool = True,
    overrides: dict | None = None,
):
    """
    Garante que Janio esteja no contexto canônico do 'usuario':
      - Define parceiro_atual = 'Janio'
      - (Opcional) registra 'primeiro_encontro' e/ou 'primeira_vez'
      - (Opcional) semeia fatos estáveis de Janio (trabalho, moradia, etc.)
    """
    try:
        import mongo_utils as mu  # usa o mesmo módulo já importado no app

        fatos = mu.get_fatos(usuario) or {}

        # 0) Defaults dos fatos do Janio (podem ser sobrescritos)
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
                "Cafeteria Oregon",
                "Quiosque Posto 6",
                "Clube Náutico",
                "Praia de Camburi",
            ],
            "status_relacao": fatos.get("status_relacao", "ficando"),
        }

        if overrides:
            defaults.update(overrides)

        # 1) parceiro_atual = Janio
        if fatos.get("parceiro_atual") != "Janio":
            mu.set_fato(usuario, "parceiro_atual", "Janio", meta={"fonte": "auto-init", "ts": _now_iso()})

        # 2) semear fatos do Janio
        if seed_fatos:
            for chave, valor in defaults.items():
                if fatos.get(chave) != valor:
                    mu.set_fato(usuario, chave, valor, meta={"fonte": "auto-init", "ts": _now_iso()})

        # 3) primeiro_encontro
        if registrar_primeiro_encontro:
            ev = mu.ultimo_evento(usuario, "primeiro_encontro")
            if not ev:
                mu.registrar_evento(
                    usuario=usuario,
                    tipo="primeiro_encontro",
                    descricao="Mary e Janio se conheceram oficialmente.",
                    local="praia de Camburi",
                    data_hora=datetime.now(TZ) if TZ else datetime.utcnow(),
                    tags=["primeiro_contato"],
                    meta={"origin": "auto-init"},
                )
                mu.set_fato(
                    usuario,
                    "primeiro_encontro",
                    "Janio - Praia de Camburi",
                    meta={"fonte": "auto-init", "ts": _now_iso()},
                )

        # 4) primeira_vez
        if registrar_primeira_vez:
            ev_pv = mu.ultimo_evento(usuario, "primeira_vez")
            if not ev_pv:
                mu.registrar_evento(
                    usuario=usuario,
                    tipo="primeira_vez",
                    descricao="Mary e Janio tiveram sua primeira vez.",
                    local="motel status",
                    data_hora=datetime.now(TZ) if TZ else datetime.utcnow(),
                    tags=["nsfw_liberado"],
                    meta={"origin": "auto-init"},
                )
                mu.set_fato(usuario, "virgem", False, meta={"fonte": "auto-init", "ts": _now_iso()})

    except Exception as e:
        st.warning(f"Não foi possível inicializar o contexto do Janio: {e}")


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
    # --- Inicializa Janio como parceiro canônico assim que houver usuário ativo ---
    ensure_janio_context(
        usuario_atual,
        registrar_primeiro_encontro=True,
        registrar_primeira_vez=False  # mude para True quando quiser liberar NSFW total
    )

# ===== Status íntimo / NSFW toggle =====
st.sidebar.markdown("---")
st.sidebar.subheader("🔓 Status íntimo")

# ===== Local da cena =====
st.sidebar.markdown("---")
st.sidebar.subheader("📍 Local da cena")

st.session_state.setdefault("local_auto", True)
st.session_state.setdefault("local_manual", "Praia de Camburi")

local_atual_badge = ""
if usuario_atual and mu is not None:
    try:
        local_atual_badge = mu.get_fato(usuario_atual, "local_cena_atual", "") or ""
    except Exception:
        local_atual_badge = ""

if usuario_atual:
    st.sidebar.caption(f"Atual: **{local_atual_badge or '— (auto)'}**")

st.session_state.local_auto = st.sidebar.checkbox("Inferir automaticamente pelo chat", value=st.session_state.local_auto)

st.session_state.local_manual = st.sidebar.selectbox(
    "Definir manualmente (opcional)",
    list(_CANON_LOCAIS_UI.keys()),
    index=list(_CANON_LOCAIS_UI.keys()).index(st.session_state.local_manual)
)

colL1, colL2 = st.sidebar.columns(2)
if colL1.button("📌 Fixar local", disabled=(not usuario_atual) or (mu is None)):
    _fixar_local(usuario_atual, _CANON_LOCAIS_UI[st.session_state.local_manual])
    st.sidebar.success(f"Local fixado: {_CANON_LOCAIS_UI[st.session_state.local_manual]}")
if colL2.button("🧽 Limpar local", disabled=(not usuario_atual) or (mu is None)):
    _fixar_local(usuario_atual, "")
    st.sidebar.info("Local limpo (modo auto).")


# Estado volátil para anti-rerun
st.session_state.setdefault("virgindade_estado_inicial", None)
st.session_state.setdefault("virgindade_ja_processado", False)


def registrar_primeira_vez_se_preciso(mu_mod, usuario: str):
    """Garante evento canônico 'primeira_vez' apenas uma vez."""
    descricao = "Mary e Janio tiveram sua primeira vez."
    if hasattr(mu_mod, "ultimo_evento") and not mu_mod.ultimo_evento(usuario, "primeira_vez"):
        mu_mod.registrar_evento(
            usuario=usuario,
            tipo="primeira_vez",
            descricao=descricao,
            local="motel status",
            data_hora=datetime.now(TZ) if TZ else datetime.utcnow(),
            tags=["nsfw_liberado"],
            meta={"id": _event_id(usuario, "primeira_vez", descricao), "origin": "sidebar"},
        )

if usuario_atual and mu is not None:
    try:
        virgem_atual = bool(mu.get_fato(usuario_atual, "virgem", True))
    except Exception:
        virgem_atual = True

    if st.session_state["virgindade_estado_inicial"] is None:
        st.session_state["virgindade_estado_inicial"] = virgem_atual

    marcado = st.sidebar.checkbox(
        "Mary **NÃO** é mais virgem (libera cenas NSFW)",
        value=(not virgem_atual),
        help="Se marcado, grava virgem=False e registra o evento canônico 'primeira_vez' (se ainda não existir).",
    )

    colA, colB = st.sidebar.columns(2)
    salvar = colA.button("💾 Salvar")
    desfazer = colB.button("↩️ Desfazer")

    if salvar and not st.session_state["virgindade_ja_processado"]:
        try:
            if marcado and virgem_atual:
                mu.set_fato(
                    usuario_atual,
                    "virgem",
                    False,
                    meta={"fonte": "sidebar", "ts": _now_iso()},
                )
                registrar_primeira_vez_se_preciso(mu, usuario_atual)
                st.sidebar.success("Salvo: Mary não é mais virgem. NSFW liberado.")
                st.session_state["virgindade_ja_processado"] = True

            elif not marcado and (not virgem_atual):
                mu.set_fato(
                    usuario_atual,
                    "virgem",
                    True,
                    meta={"fonte": "sidebar", "ts": _now_iso(), "manual_reset": True},
                )
                st.sidebar.info("Status redefinido para virgem=True (manual).")
                st.session_state["virgindade_ja_processado"] = True
            else:
                st.sidebar.warning("Nenhuma alteração detectada.")
        except Exception as e:
            st.sidebar.error(f"Falha ao salvar o status íntimo: {e}")

    if desfazer:
        try:
            estado_inicial = st.session_state["virgindade_estado_inicial"]
            mu.set_fato(
                usuario_atual,
                "virgem",
                bool(estado_inicial),
                meta={"fonte": "sidebar", "ts": _now_iso(), "undo": True},
            )
            st.sidebar.info("Status retornado ao estado inicial desta sessão.")
            st.session_state["virgindade_ja_processado"] = False
        except Exception as e:
            st.sidebar.error(f"Falha ao desfazer: {e}")
else:
    st.sidebar.info("Selecione um usuário para ajustar o status íntimo.")

# ===== Gate NSFW (leitura rápida + badge) =====
def nsfw_liberado(usuario: str) -> bool:
    if mu is None or not usuario:
        return False
    try:
        virgem = bool(mu.get_fato(usuario, "virgem", True))
    except Exception:
        virgem = True
    if not virgem:
        return True
    try:
        ev = mu.ultimo_evento(usuario, "primeira_vez")
        if ev:
            return True
    except Exception:
        pass
    return False

# badge de status atual
_nsfw_on = nsfw_liberado(usuario_atual)
if usuario_atual:
    st.sidebar.markdown(
        f"**NSFW:** {'✅ Liberado' if _nsfw_on else '🔒 Bloqueado'}"
    )

# ==== Memória Canônica (manual) ====
st.sidebar.markdown("---")
st.sidebar.subheader("🧠 Memória Canônica (manual)")

st.session_state.setdefault("mem_tipo", "Fato")
st.session_state.setdefault("mem_chave", "")
st.session_state.setdefault("mem_valor", "")
st.session_state.setdefault("mem_local", "")

st.session_state.mem_tipo = st.sidebar.radio("Tipo de memória", ["Fato", "Evento"], horizontal=True)

# Desabilita salvar/descartar se não tiver usuário ativo OU mu não está disponível
btn_disabled = (not bool(usuario_atual)) or (mu is None)

if st.session_state.mem_tipo == "Fato":
    st.session_state.mem_chave = st.sidebar.text_input(
        "Chave do fato (ex.: primeiro_encontro, cidade_atual)",
        value=st.session_state.mem_chave,
    )
    st.session_state.mem_valor = st.sidebar.text_area(
        "Valor do fato (ex.: Café Oregon)",
        value=st.session_state.mem_valor,
        height=80,
    )
    colf1, colf2 = st.sidebar.columns(2)
    with colf1:
        if st.button("💾 Salvar fato", disabled=btn_disabled):
            if not usuario_atual or mu is None:
                st.sidebar.warning("Escolha um usuário e verifique a conexão com o banco.")
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
                    upsert=True,
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
        value=st.session_state.mem_chave,
    )
    st.session_state.mem_valor = st.sidebar.text_area(
        "Descrição do evento (factual, curta)",
        value=st.session_state.mem_valor,
        height=80,
    )
    st.session_state.mem_local = st.sidebar.text_input(
        "Local (opcional)",
        value=st.session_state.mem_local,
        placeholder="Ex.: Café Oregon, Clube Serra Bella, Praia de Camburi",
    )
    cole1, cole2 = st.sidebar.columns(2)
    with cole1:
        if st.button("💾 Salvar evento", disabled=btn_disabled):
            if not usuario_atual or mu is None:
                st.sidebar.warning("Escolha um usuário e verifique a conexão com o banco.")
            elif st.session_state.mem_chave.strip() and st.session_state.mem_valor.strip():
                if hasattr(mu, "registrar_evento_canonico"):
                    mu.registrar_evento_canonico(
                        usuario=usuario_atual,
                        tipo=st.session_state.mem_chave.strip(),
                        descricao=st.session_state.mem_valor.strip(),
                        local=(st.session_state.mem_local.strip() or None),
                        data_hora=datetime.now(TZ) if TZ else datetime.utcnow(),
                        atualizar_fatos=True,
                    )
                else:
                    mu.registrar_evento(
                        usuario=usuario_atual,
                        tipo=st.session_state.mem_chave.strip(),
                        descricao=st.session_state.mem_valor.strip(),
                        local=(st.session_state.mem_local.strip() or None),
                        data_hora=datetime.now(TZ) if TZ else datetime.utcnow(),
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
if usuario_atual and mu is not None:
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
    if usuario_atual and mu is not None:
        try:
            for ev in list(
                mu.eventos.find({"usuario": usuario_atual}).sort([("ts", -1)]).limit(5)
            ):
                ts = ev.get("ts").strftime("%Y-%m-%d %H:%M") if ev.get("ts") else "sem data"
                st.sidebar.write(f"- **{ev.get('tipo','?')}** — {ev.get('descricao','?')} ({ev.get('local','?')}) em {ts}")
        except Exception as e:
            st.sidebar.warning(f"Não foi possível listar eventos: {e}")

# ===== Enredo inicial =====
st.session_state.enredo_inicial = st.text_area(
    "📜 Enredo inicial",
    value=st.session_state.enredo_inicial,
    placeholder="Ex.: Mary encontra o usuário depois de um dia difícil...",
    height=80,
)

# ===== Controles de memória do chat =====
cc1, cc2, cc3 = st.columns(3)
with cc1:
    if st.button("🔄 Resetar histórico (chat)", disabled=(not usuario_atual) or (mu is None)):
        if mu is not None:
            mu.limpar_memoria_usuario(usuario_atual)
        st.session_state.mary_log = []
        st.session_state.enredo_publicado = False
        st.success(f"Histórico de {usuario_atual} apagado (memórias canônicas preservadas).")

with cc2:
    if st.button("🧠 Apagar TUDO (chat + memórias)", disabled=(not usuario_atual) or (mu is None)):
        if mu is not None:
            mu.apagar_tudo_usuario(usuario_atual)
        st.session_state.mary_log = []
        st.session_state.enredo_publicado = False
        st.success(f"Chat e memórias canônicas de {usuario_atual} foram apagados.")

with cc3:
    if st.button("⏪ Apagar último turno", disabled=(not usuario_atual) or (mu is None)):
        if mu is not None:
            mu.apagar_ultima_interacao_usuario(usuario_atual)
            st.session_state.mary_log = mu.montar_historico_openrouter(usuario_atual)
        st.info("Última interação apagada.")

# ===== Publica ENREDO se necessário =====
if usuario_atual and st.session_state.enredo_inicial.strip() and not st.session_state.enredo_publicado and mu is not None:
    try:
        if mu.colecao.count_documents({
            "usuario": {"$regex": f"^{re.escape(usuario_atual)}$", "$options": "i"},
            "mensagem_usuario": "__ENREDO_INICIAL__",
        }) == 0:
            mu.salvar_interacao(usuario_atual, "__ENREDO_INICIAL__", st.session_state.enredo_inicial.strip())
            st.session_state.enredo_publicado = True
    except Exception as e:
        st.warning(f"Não foi possível publicar o enredo: {e}")

# ===== Carrega histórico =====
if usuario_atual and mu is not None:
    st.session_state.mary_log = mu.montar_historico_openrouter(usuario_atual)
else:
    st.session_state.mary_log = []

# ===== Diagnóstico (opcional) =====
with st.expander("🔍 Diagnóstico do banco"):
    try:
        if mu is None:
            raise RuntimeError("mongo_utils não disponível.")
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

# ===== Input fixo no rodapé =====

def aplicar_restricoes(prompt_usuario: str, liberar_nsfw: bool, local_atual: str = "") -> str:
    """Prefixa instruções conforme o gate NSFW e injeta o LOCAL_ATUAL."""
    if liberar_nsfw:
        prefix = (
            "[MODO_NSFW_LIBERADO]\n"
            "Tom sensual adulto quando apropriado; SEM conteúdo ilegal, menores, incesto, violência sexual ou bestialidade.\n"
            "Consentimento e bom gosto; evite gore e hiper-detalhe gráfico.\n"
        )
    else:
        prefix = (
            "[MODO_SEGURO]\n"
            "Tom romântico/afetivo leve, SEM cenas sexuais explícitas; foque em flerte, cotidiano e diálogo.\n"
        )
    if local_atual:
        prefix += f"LOCAL_ATUAL: {local_atual}\n"
        prefix += "Mantenha coerência estrita com o LOCAL_ATUAL (não misture praia com academia, etc.).\n"
    return prefix + "\n\n" + (prompt_usuario or "")


if usuario_atual:
    prompt = st.chat_input("Envie sua mensagem para Mary")
    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)
        try:
            if mu is not None:
                # 1) Auto-inferir LOCAL (se ligado)
                if st.session_state.get("local_auto", True):
                    loc_inf = _inferir_local_do_prompt(prompt)
                    if loc_inf:
                        _fixar_local(usuario_atual, loc_inf)

                # 2) Ler local atual para injetar no prompt
                try:
                    _local_now = mu.get_fato(usuario_atual, "local_cena_atual", "") or ""
                except Exception:
                    _local_now = ""

                # 3) Montar prompt final com restrições + LOCAL_ATUAL
                liberar = nsfw_liberado(usuario_atual)
                prompt_final = aplicar_restricoes(prompt, liberar, _local_now)

                # 4) Gerar resposta
                resposta = mu.gerar_resposta_openrouter(
                    prompt_final, usuario_atual, model=st.session_state.modelo_escolhido
                )
            else:
                raise RuntimeError("mongo_utils indisponível — não foi possível gerar resposta.")
        except Exception as e:
            st.error(f"Falha ao gerar resposta: {e}")
            resposta = "Desculpa, tive um problema para responder agora. Pode tentar de novo?"

        # 5) Persistir e renderizar
        try:
            if mu is not None:
                mu.salvar_interacao(usuario_atual, prompt, resposta)
        except Exception as e:
            st.warning(f"Não consegui salvar a interação: {e}")

        if mu is not None:
            st.session_state.mary_log = mu.montar_historico_openrouter(usuario_atual)

        with st.chat_message("assistant", avatar="💚"):
            st.markdown(resposta)
else:
    st.info("Selecione o usuário para liberar o chat e a memória.")
