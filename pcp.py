"""
pcp.py — Genius Plantadeiras
Visão PCP (Planejamento e Controle da Produção)

Acesso público — sem login necessário.
Execute separado: streamlit run pcp.py --server.port 8502

O que o PCP VÊ:
  ✅ Equipamento, Representante, Cliente, Data, Status, Observações
  ✅ Contagens e quantidades (cards de KPI)
  ✅ Filtros por status e período

O que o PCP NÃO VÊ:
  ❌ Valor (R$) — completamente oculto
  ❌ Nenhum dado financeiro

Atualização: botão manual 🔄 + auto-refresh 30s
Compartilhe o link: http://SEU_IP:8502
"""

from pathlib import Path
import time

import pandas as pd
import streamlit as st

# ── Configuração da página ────────────────────────────────────
st.set_page_config(
    page_title="PCP — Genius Plantadeiras",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Caminhos ──────────────────────────────────────────────────
_BASE_DIR    = Path(__file__).parent
DATABASE_DIR = _BASE_DIR / "database"
ARQUIVO_CSV  = DATABASE_DIR / "pedidos_manuais.csv"

# Colunas visíveis para o PCP — Valor NUNCA é incluído
_COLUNAS_PCP = [
    "Data_Lancamento", "Equipamento", "Representante",
    "Cliente", "Data_Pedido", "Status", "Observacoes",
]
_COLUNAS_TODAS = [
    "Data_Lancamento", "Equipamento", "Representante",
    "Cliente", "Valor", "Data_Pedido", "Status", "Observacoes",
]

STATUS_OPCOES = ["Em Negociação", "Pedido Fechado", "Faturado", "Declinado"]

_STATUS_STYLE: dict = {
    "Em Negociação": {
        "bg": "rgba(232,160,32,.18)", "border": "rgba(232,160,32,.5)",
        "text": "#E8C040", "dot": "#E8A020",
    },
    "Pedido Fechado": {
        "bg": "rgba(61,153,112,.18)", "border": "rgba(61,153,112,.5)",
        "text": "#52B788", "dot": "#3D9970",
    },
    "Faturado": {
        "bg": "rgba(74,122,191,.18)", "border": "rgba(74,122,191,.5)",
        "text": "#7AAFD4", "dot": "#4A7ABF",
    },
    "Declinado": {
        "bg": "rgba(232,64,64,.18)", "border": "rgba(232,64,64,.5)",
        "text": "#E87878", "dot": "#E84040",
    },
}
_DEFAULT_STYLE = {
    "bg": "rgba(106,122,138,.15)", "border": "rgba(106,122,138,.4)",
    "text": "#A8B8CC", "dot": "#6A7A8A",
}

_STATUS_KPI_COLOR = {
    "Em Negociação": "#E8C040",
    "Pedido Fechado": "#52B788",
    "Faturado":       "#7AAFD4",
    "Declinado":      "#E87878",
}


# ── Helpers ───────────────────────────────────────────────────
def _get_style(status: str) -> dict:
    return _STATUS_STYLE.get(status, _DEFAULT_STYLE)


def _badge(status: str) -> str:
    s = _get_style(status)
    return (
        f'<span style="display:inline-flex;align-items:center;gap:6px;'
        f'background:{s["bg"]};border:1px solid {s["border"]};'
        f'color:{s["text"]};border-radius:20px;padding:3px 11px;'
        f'font-size:12px;font-weight:600;font-family:\'DM Sans\',sans-serif;">'
        f'<span style="width:7px;height:7px;border-radius:50%;'
        f'background:{s["dot"]};flex-shrink:0;"></span>'
        f'{status}</span>'
    )


def _ler_dados_pcp() -> pd.DataFrame:
    """
    Lê o CSV e retorna SOMENTE as colunas permitidas para o PCP.
    Aplica migração automática: 'Quantidade' → 'Faturado'.
    Valor financeiro é removido antes de retornar.
    """
    if not ARQUIVO_CSV.exists():
        return pd.DataFrame(columns=_COLUNAS_PCP)
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            df = pd.read_csv(ARQUIVO_CSV, encoding=enc)
            if len(df.columns) < 2:
                continue
            # Migração de status legado
            if "Status" in df.columns:
                df["Status"] = df["Status"].replace("Quantidade", "Faturado")
            # Garante que Valor NUNCA seja exposto ao PCP
            cols_visiveis = [c for c in _COLUNAS_PCP if c in df.columns]
            return df[cols_visiveis].copy()
        except Exception:
            continue
    return pd.DataFrame(columns=_COLUNAS_PCP)


def _calcular_kpis_pcp(df: pd.DataFrame) -> dict:
    """KPIs apenas de quantidade — zero dados financeiros."""
    if df.empty or "Status" not in df.columns:
        return {s: 0 for s in ["total"] + STATUS_OPCOES}
    kpis = {"total": len(df)}
    for s in STATUS_OPCOES:
        kpis[s] = int((df["Status"] == s).sum())
    return kpis


# ── CSS ───────────────────────────────────────────────────────
def _injetar_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Barlow+Condensed:wght@600;700&display=swap');

:root {
    --bg-page:  #161B22;
    --bg-card:  #1F2937;
    --bg-card2: #252E3E;
    --bdr:      #2D3748;
    --orange:   #E36C2C;
    --orange-dim: rgba(227,108,44,.14);
    --t1: #F0F4F8;
    --t2: #A8B8CC;
    --t3: #6A7A8A;
    --t4: #3A4858;
    --r:  12px;
    --rs: 8px;
}

html,body,.stApp,[class*="css"] {
    font-family:'DM Sans','Segoe UI',sans-serif !important;
    background-color:var(--bg-page) !important;
    color:var(--t1) !important;
}
.block-container {
    padding: 2rem 2rem 3rem !important;
    max-width: 100% !important;
}
header[data-testid="stHeader"] {
    background: var(--bg-page) !important;
    border-bottom: 1px solid var(--bdr) !important;
}
section[data-testid="stSidebar"] { display:none !important; }
#MainMenu, footer { display:none !important; }

/* KPI cards */
div[data-testid="metric-container"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--bdr) !important;
    border-left: 4px solid var(--orange) !important;
    border-radius: var(--r) !important;
    padding: 18px 20px 14px !important;
}
div[data-testid="metric-container"] label,
div[data-testid="metric-container"] [data-testid="stMetricLabel"] p {
    font-size:11px !important; font-weight:700 !important;
    letter-spacing:.08em !important; text-transform:uppercase !important;
    color:var(--t3) !important;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] div,
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family:'Barlow Condensed',sans-serif !important;
    font-size:2.6rem !important; font-weight:700 !important;
    color:var(--t1) !important;
}

/* Inputs */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    background: var(--bg-card) !important;
    border: 1px solid var(--bdr) !important;
    border-radius: var(--rs) !important;
    color: var(--t1) !important;
    font-size: 14px !important;
}
div[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    background: var(--orange-dim) !important;
    color: #F08040 !important; font-size:12px !important;
}

/* Buttons */
div[data-testid="stButton"] > button:not([kind="primary"]) {
    background: var(--bg-card2) !important;
    border: 1px solid var(--bdr) !important;
    border-radius: var(--rs) !important;
    color: var(--t2) !important;
    font-size:13px !important;
}
div[data-testid="stButton"] > button:not([kind="primary"]):hover {
    border-color: var(--orange) !important; color: var(--t1) !important;
}

/* Toggle */
div[data-testid="stToggle"] label { font-size:12px !important; color:var(--t3) !important; }

.genius-divider { border:none; border-top:1px solid var(--bdr); margin:20px 0; }
::-webkit-scrollbar { width:5px; height:5px; }
::-webkit-scrollbar-thumb { background:var(--bdr); border-radius:3px; }
</style>
""", unsafe_allow_html=True)


# ── Header PCP ────────────────────────────────────────────────
def _render_header():
    # Tenta carregar logo
    logo_b64 = ""
    try:
        import base64
        p = _BASE_DIR / "assets" / "genius_logo.png"
        if p.exists():
            logo_b64 = base64.b64encode(p.read_bytes()).decode()
    except Exception:
        pass

    logo_html = (
        f'<div style="background:#fff;border-radius:8px;padding:5px 12px;'
        f'display:inline-flex;align-items:center;">'
        f'<img src="data:image/png;base64,{logo_b64}" '
        f'style="height:38px;display:block;" alt="Genius"></div>'
        if logo_b64
        else '<div style="background:rgba(227,108,44,.14);border:1px solid rgba(227,108,44,.4);'
             'border-radius:8px;padding:6px 16px;font-family:\'Barlow Condensed\',sans-serif;'
             'font-size:1.4rem;font-weight:700;color:#E36C2C;letter-spacing:.1em;">GENIUS</div>'
    )

    st.markdown(f"""
<div style="display:flex;align-items:center;gap:16px;padding:10px 0 16px;
            border-bottom:1px solid #2D3748;margin-bottom:20px;">
  {logo_html}
  <div>
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:1.8rem;
                font-weight:700;color:#F0F4F8;line-height:1.1;margin:0;">
      Previsão de Vendas — PCP
    </div>
    <div style="font-size:11px;color:#6A7A8A;text-transform:uppercase;
                letter-spacing:.07em;margin-top:3px;">
      Genius Plantadeiras &nbsp;·&nbsp; Planejamento e Controle da Produção
    </div>
  </div>
  <div style="margin-left:auto;background:rgba(74,122,191,.12);
              border:1px solid rgba(74,122,191,.3);border-radius:8px;
              padding:6px 14px;font-size:11px;color:#7AAFD4;
              font-family:'DM Sans',sans-serif;font-weight:600;">
    🔓 Acesso Público — Somente Leitura
  </div>
</div>
""", unsafe_allow_html=True)


# ── Barra de refresh ──────────────────────────────────────────
def _render_refresh_bar():
    col_txt, col_auto, col_btn = st.columns([3, 2, 1], gap="small")

    with col_txt:
        ultimo = st.session_state.get("pcp_ultimo_refresh")
        if ultimo:
            delta = int(time.time() - ultimo)
            txt = (
                f"🕐 Atualizado há {delta}s"
                if delta < 60
                else f"🕐 Atualizado há {delta // 60}min"
            )
        else:
            txt = "🕐 Dados carregados agora"
        st.markdown(
            f'<div style="font-size:12px;color:#4A7ABF;padding-top:8px;">{txt}</div>',
            unsafe_allow_html=True,
        )

    with col_auto:
        auto = st.toggle(
            "Auto-refresh (30s)", key="pcp_auto_refresh", value=False,
            help="Atualiza automaticamente a cada 30 segundos",
        )

    with col_btn:
        if st.button("🔄 Atualizar", use_container_width=True, key="pcp_btn_refresh"):
            st.cache_data.clear()
            st.session_state["pcp_ultimo_refresh"] = time.time()
            st.rerun()

    if auto:
        ultimo_auto = st.session_state.get("pcp_ultimo_auto", 0)
        if time.time() - ultimo_auto >= 30:
            st.session_state["pcp_ultimo_auto"]        = time.time()
            st.session_state["pcp_ultimo_refresh"]     = time.time()
            st.cache_data.clear()
            time.sleep(0.1)
            st.rerun()

    if not st.session_state.get("pcp_ultimo_refresh"):
        st.session_state["pcp_ultimo_refresh"] = time.time()


# ── KPI Cards ────────────────────────────────────────────────
def _render_kpis(kpis: dict):
    # Linha 1: Total + Em Negociação + Pedido Fechado
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        st.metric(
            "Total de Pedidos", f"{kpis['total']}",
            delta="Todos os status",
            help="Quantidade total de pedidos lançados manualmente",
        )
    with c2:
        n = kpis.get("Em Negociação", 0)
        st.metric(
            "Em Negociação", f"{n}",
            delta="Previsão de venda",
            help="Pedidos ainda em processo de negociação — prever necessidade de estoque",
        )
    with c3:
        n = kpis.get("Pedido Fechado", 0)
        st.metric(
            "Pedido Fechado", f"{n}",
            delta="Confirmar produção",
            help="Pedidos fechados — providenciar separação e produção",
        )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # Linha 2: Faturado + Declinado
    c4, c5, _ = st.columns(3, gap="medium")
    with c4:
        n = kpis.get("Faturado", 0)
        st.metric(
            "Faturado", f"{n}",
            delta="Já entregues",
            help="Pedidos já faturados e entregues",
        )
    with c5:
        n = kpis.get("Declinado", 0)
        st.metric(
            "Declinado", f"{n}",
            delta="Cancelados",
            help="Pedidos que não foram concretizados",
        )


# ── Tabela PCP ────────────────────────────────────────────────
def _render_tabela(df: pd.DataFrame):
    if df.empty:
        st.info("Nenhum pedido lançado ainda.")
        return

    # Formata datas
    df_fmt = df.copy()
    for col_dt, fmt in [
        ("Data_Pedido",     "%d/%m/%Y"),
        ("Data_Lancamento", "%d/%m/%Y"),
    ]:
        if col_dt in df_fmt.columns:
            df_fmt[col_dt] = pd.to_datetime(
                df_fmt[col_dt], errors="coerce"
            ).dt.strftime(fmt)

    # Cabeçalho
    hdr = st.columns([1.0, 2.0, 1.2, 1.8, 1.0, 1.8, 2.0])
    for col, label in zip(hdr, [
        "Lançamento", "Equipamento", "Representante",
        "Cliente", "Data Pedido", "Status", "Observações",
    ]):
        col.markdown(
            f'<div style="font-size:10px;font-weight:700;color:#3A4858;'
            f'text-transform:uppercase;letter-spacing:.08em;padding-bottom:6px;'
            f'border-bottom:1px solid #2D3748;">{label}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    for _, row in df_fmt.iterrows():
        status = str(row.get("Status", ""))
        cols   = st.columns([1.0, 2.0, 1.2, 1.8, 1.0, 1.8, 2.0])

        cols[0].markdown(
            f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">'
            f'{row.get("Data_Lancamento","—")}</div>',
            unsafe_allow_html=True,
        )
        cols[1].markdown(
            f'<div style="font-size:13px;color:#EEF2F8;font-weight:500;'
            f'padding-top:8px;">{row.get("Equipamento","—")}</div>',
            unsafe_allow_html=True,
        )
        cols[2].markdown(
            f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">'
            f'{row.get("Representante","—")}</div>',
            unsafe_allow_html=True,
        )
        cols[3].markdown(
            f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">'
            f'{row.get("Cliente","—")}</div>',
            unsafe_allow_html=True,
        )
        cols[4].markdown(
            f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">'
            f'{row.get("Data_Pedido","—")}</div>',
            unsafe_allow_html=True,
        )
        cols[5].markdown(
            f'<div style="padding-top:4px;">{_badge(status)}</div>',
            unsafe_allow_html=True,
        )
        obs = str(row.get("Observacoes","")) if pd.notna(row.get("Observacoes","")) else "—"
        obs = obs if obs.strip() else "—"
        cols[6].markdown(
            f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;'
            f'font-style:{"italic" if obs == "—" else "normal"};">{obs}</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div style="border-bottom:1px solid rgba(45,55,72,.5);'
            'margin:3px 0;"></div>',
            unsafe_allow_html=True,
        )

    st.caption(f"Total: {len(df)} pedido(s) exibido(s).")


# ── Filtros ───────────────────────────────────────────────────
def _render_filtros(df: pd.DataFrame) -> pd.DataFrame:
    """Filtros por status, representante e busca por texto."""
    if df.empty:
        return df

    st.markdown(
        '<div style="background:#1F2937;border:1px solid #2D3748;'
        'border-left:3px solid #E36C2C;border-radius:12px;'
        'padding:14px 18px 10px;margin-bottom:18px;">'
        '<div style="font-size:11px;font-weight:700;color:#3A4858;'
        'text-transform:uppercase;letter-spacing:.1em;margin-bottom:12px;">'
        '🔍 Filtros</div></div>',
        unsafe_allow_html=True,
    )

    f1, f2, f3 = st.columns([2, 2, 2], gap="medium")

    with f1:
        status_opts = sorted(df["Status"].dropna().unique().tolist()) \
            if "Status" in df.columns else STATUS_OPCOES
        sel_status = st.multiselect(
            "Status", status_opts, default=status_opts, key="pcp_sel_status",
        )

    with f2:
        rep_opts = sorted(df["Representante"].dropna().unique().tolist()) \
            if "Representante" in df.columns else []
        sel_rep = st.multiselect(
            "Representante", rep_opts, default=rep_opts, key="pcp_sel_rep",
        )

    with f3:
        busca = st.text_input(
            "Buscar equipamento / cliente",
            placeholder="Ex: GATA 18050 ou AGROTEC",
            key="pcp_busca",
        )

    # Aplica filtros
    if sel_status and "Status" in df.columns:
        df = df[df["Status"].isin(sel_status)]

    if sel_rep and "Representante" in df.columns:
        df = df[df["Representante"].isin(sel_rep)]

    if busca.strip():
        mask = pd.Series([False] * len(df), index=df.index)
        for col in ["Equipamento", "Cliente"]:
            if col in df.columns:
                mask |= df[col].astype(str).str.lower().str.contains(
                    busca.strip().lower(), na=False
                )
        df = df[mask]

    n = len(df)
    st.markdown(
        f'<div style="font-size:13px;color:#6A7A8A;margin-bottom:8px;">'
        f'<b style="color:#A8B8CC;">{n}</b> '
        f'pedido{"s" if n != 1 else ""} após filtros.</div>',
        unsafe_allow_html=True,
    )
    return df


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════
_injetar_css()
_render_header()

# Aviso de somente leitura + sem dados financeiros
st.markdown("""
<div style="background:rgba(74,122,191,.08);border:1px solid rgba(74,122,191,.25);
            border-radius:10px;padding:10px 16px;margin-bottom:20px;
            display:flex;align-items:center;gap:10px;font-size:13px;color:#6A9FCC;">
  ℹ️ &nbsp;<span>
    Esta página é <b>somente leitura</b> e não exibe dados financeiros.
    Apenas equipamentos, representantes, clientes, datas e status são visíveis.
  </span>
</div>
""", unsafe_allow_html=True)

# Barra de refresh
_render_refresh_bar()

st.markdown('<hr class="genius-divider">', unsafe_allow_html=True)

# Carrega dados
df_pcp = _ler_dados_pcp()

if df_pcp.empty:
    st.warning(
        "Nenhum pedido encontrado. "
        "Os dados aparecem aqui conforme os vendedores lançam negociações no sistema principal."
    )
else:
    # KPIs (somente contagens)
    kpis = _calcular_kpis_pcp(df_pcp)
    _render_kpis(kpis)

    st.markdown('<hr class="genius-divider">', unsafe_allow_html=True)

    # Filtros
    df_filtrado = _render_filtros(df_pcp)

    # Tabela
    st.markdown(
        '<div style="font-size:15px;font-weight:600;color:#F0F4F8;'
        'margin-bottom:12px;">📋 Pedidos Lançados</div>',
        unsafe_allow_html=True,
    )
    _render_tabela(df_filtrado)

# Rodapé
from datetime import datetime
st.markdown(
    f'<div style="text-align:center;color:#3A4858;font-size:12px;'
    f'padding:20px 0 8px;border-top:1px solid #2D3748;margin-top:32px;">'
    f'Genius Plantadeiras — PCP · Atualizado em '
    f'{datetime.now().strftime("%d/%m/%Y às %H:%M:%S")}</div>',
    unsafe_allow_html=True,
)
