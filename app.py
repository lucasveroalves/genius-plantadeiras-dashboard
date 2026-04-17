"""
app.py — Genius Implementos Agrícolas v14 (CORRIGIDO)

Correções aplicadas:
  [FIX-SEC-6]  Guarda de sessão expirada: se abas_permitidas estiver vazio
               após login (sessão parcial), exibe aviso e força novo login.
  [FIX-BUG-4]  KPIs de peças: passa data_inicio/data_fim para calcular_kpis_pecas()
               garantindo que orçamentos sejam filtrados pelo mesmo período.
  [FIX-PERF-2] render_auto_refresh usa ttl no cache em vez de clear() global —
               alteração feita no ui.py; app.py permanece igual na chamada.
  [FIX-RBAC]   Dados financeiros filtrados por perfil ANTES de calcular KPIs:
               usuário PCP não recebe Valor_Total / Valor_Unitario.
"""

import streamlit as st
import pandas as pd
from datetime import date

from auth import tela_login, painel_usuario, render_painel_admin, is_admin, abas_permitidas
from data.loader import preparar_pecas, calcular_kpis_pecas, calcular_curva_abc, calcular_curva_abc_por_codigo, calcular_top10_revendas
from components.ui import render_header, render_sidebar_uploads, render_banner_mock_pecas, render_auto_refresh
from components.estoque   import render_aba_estoque
from components.producao  import render_aba_pcp
from components.forms     import render_formulario_negociacao, render_formulario_orcamento_pecas, render_formulario_revendas
from components.nf_demo   import render_aba_nf_demo
from data.db              import ler_orcamentos
from components.tab_leadtime import render_tab_leadtime

from charts.plots import grafico_curva_abc, grafico_ranking_revendas_pecas

# ── Configuração ──────────────────────────────────────────────
st.set_page_config(page_title="Genius Implementos Agrícolas", layout="wide", page_icon="🌾")

# ── 1. Autenticação ───────────────────────────────────────────
if not tela_login():
    st.stop()

# ── 2. Sidebar ────────────────────────────────────────────────
painel_usuario()
_peca_file = render_sidebar_uploads()

# ── 3. Dados de Peças ─────────────────────────────────────────
df_pecas, is_mock_pecas = preparar_pecas(_peca_file)

# ── 4. Header + Auto-refresh ──────────────────────────────────
render_header()
render_auto_refresh()


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def _filtrar_pecas_por_perfil(df: pd.DataFrame, perfil: str) -> pd.DataFrame:
    """
    [FIX-RBAC] Remove colunas financeiras sensíveis para usuários PCP.
    PCP só precisa de dados de volume/SKU para planejamento de estoque mínimo.
    """
    if perfil == "pcp":
        cols_remover = [c for c in ["Valor_Unitario", "Valor_Total"] if c in df.columns]
        if cols_remover:
            return df.drop(columns=cols_remover)
    return df


# ══════════════════════════════════════════════════════════════
# ABA PEÇAS
# ══════════════════════════════════════════════════════════════

def _render_aba_pecas(df_pecas_arg, is_mock_pecas_arg):
    perfil = st.session_state.get("perfil_atual", "comercial")

    if is_mock_pecas_arg:
        render_banner_mock_pecas()
        return

    st.header("🔧 Análise de Peças")

    # ── Filtro de Período ──────────────────────────────────────
    col_f1, col_f2 = st.columns([4, 1])
    with col_f1:
        data_min = df_pecas_arg["Data_Venda"].min().date() if not df_pecas_arg.empty else date.today()
        data_max = df_pecas_arg["Data_Venda"].max().date() if not df_pecas_arg.empty else date.today()
        intervalo = st.date_input(
            "Selecione o período",
            value=(data_min, data_max),
            min_value=data_min,
            max_value=data_max,
            format="DD/MM/YYYY",
            key="peca_periodo"
        )
    with col_f2:
        st.write("")
        st.write("")
        if st.button("🔄 Aplicar", key="peca_btn_filtro"):
            st.rerun()

    # Aplica filtro de período
    d0, d1 = data_min, data_max
    if isinstance(intervalo, (list, tuple)) and len(intervalo) == 2:
        d0, d1 = intervalo
        dv = df_pecas_arg["Data_Venda"]
        if hasattr(dv.dt, "tz") and dv.dt.tz is not None:
            dv = dv.dt.tz_localize(None)
        df_filtrado = df_pecas_arg[(dv.dt.date >= d0) & (dv.dt.date <= d1)]
    else:
        df_filtrado = df_pecas_arg

    # [FIX-RBAC] Filtra colunas financeiras para PCP antes de qualquer cálculo
    df_para_calculos = _filtrar_pecas_por_perfil(df_filtrado, perfil)

    # ── Orçamentos (sempre lidos frescos — cache TTL=30s no db.py) ──
    df_orc = ler_orcamentos()
    pecas_em_orc = 0.0
    if not df_orc.empty and "Status_Orc" in df_orc.columns:
        mask = df_orc["Status_Orc"].isin(["Aguardando"])
        pecas_em_orc = pd.to_numeric(df_orc.loc[mask, "Valor_Total"], errors="coerce").fillna(0).sum()

    # ── KPIs com período consistente ──────────────────────────
    # [FIX-BUG-4] Passa d0/d1 para filtrar df_orc pelo mesmo período
    if perfil == "comercial":
        kpis = calcular_kpis_pecas(df_filtrado, df_orc,
                                    data_inicio=d0, data_fim=d1)
    else:
        # PCP não recebe dados financeiros
        kpis = calcular_kpis_pecas(df_para_calculos)

    def _brl(v):
        try:
            return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "R$ 0,00"

    def _card(label, value):
        st.markdown(
            f'<div style="background:#1F2937;border:1px solid #2D3748;'
            f'border-left:4px solid #E36C2C;border-radius:10px;'
            f'padding:14px 16px 10px;min-height:80px;">'
            f'<div style="font-size:11px;font-weight:700;color:#6A7A8A;'
            f'text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;">{label}</div>'
            f'<div style="font-size:1.35rem;font-weight:700;color:#F0F4F8;'
            f'word-break:break-word;">{value}</div></div>',
            unsafe_allow_html=True
        )

    if perfil == "comercial":
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            _card("💰 Peças Faturadas", _brl(kpis["total_faturado"]))
        with c2:
            _card("📋 Em Orçamento", _brl(pecas_em_orc))
        with c3:
            _card("📦 Volume de Itens", f"{int(kpis['volume_itens']):,}".replace(",", "."))
        with c4:
            _card("🎟️ Ticket Médio", _brl(kpis["ticket_medio"]))
        with c5:
            _card("🏷️ SKUs Ativos", str(kpis["qtd_skus"]))
        st.divider()
    else:
        c1, c2 = st.columns(2)
        with c1:
            _card("📦 Volume de Itens", f"{int(kpis['volume_itens']):,}".replace(",", "."))
        with c2:
            _card("🏷️ SKUs Ativos", str(kpis["qtd_skus"]))
        st.divider()

    # ── Curva ABC — usa df_para_calculos (sem valores financeiros para PCP) ──
    df_abc = calcular_curva_abc_por_codigo(df_para_calculos, top_n=20)

    if perfil == "comercial":
        col_abc, col_rev = st.columns(2)
        with col_abc:
            st.subheader("📊 Curva ABC – Peças Mais Vendidas")
            if not df_abc.empty:
                st.plotly_chart(grafico_curva_abc(df_abc), use_container_width=True)
            else:
                st.info("Sem dados para Curva ABC.")
        with col_rev:
            st.subheader("🏆 Top 10 Revendas")
            df_top10 = calcular_top10_revendas(df_filtrado)
            if not df_top10.empty:
                st.plotly_chart(grafico_ranking_revendas_pecas(df_top10, top_n=10), use_container_width=True)
            else:
                st.info("Sem dados de revendas.")
    else:
        st.subheader("📊 Curva ABC – Previsão de Estoque Mínimo de Peças")
        if not df_abc.empty:
            st.plotly_chart(grafico_curva_abc(df_abc), use_container_width=True)
        else:
            st.info("Sem dados para Curva ABC.")

        if not df_orc.empty and "Status_Orc" in df_orc.columns:
            st.divider()
            st.subheader("📋 Orçamentos de Peças em Aberto")
            df_orc_view = df_orc[df_orc["Status_Orc"] == "Aguardando"][
                ["Nr_Pedido", "Data_Orcamento", "Cliente_Revenda", "Valor_Total", "Status_Orc"]
            ]
            st.dataframe(df_orc_view, use_container_width=True, height=300)

    if perfil == "comercial":
        st.divider()
        _tab_detalhe, _tab_lead = st.tabs(["📋 Detalhamento de Vendas", "🕐 Lead Time"])
        with _tab_detalhe:
            cols_fmt = {}
            if "Valor_Unitario" in df_filtrado.columns:
                cols_fmt["Valor_Unitario"] = "R$ {:,.2f}".format
            if "Valor_Total" in df_filtrado.columns:
                cols_fmt["Valor_Total"] = "R$ {:,.2f}".format
            st.dataframe(
                df_filtrado.style.format(cols_fmt) if cols_fmt else df_filtrado,
                use_container_width=True,
                height=400
            )
        with _tab_lead:
            render_tab_leadtime()


# ══════════════════════════════════════════════════════════════
# 5. Define abas visíveis para este usuário
# ══════════════════════════════════════════════════════════════
MAPA = {
    "📝 Orçamento de Peças":   lambda: render_formulario_orcamento_pecas(),
    "🏬 Revendas":             lambda: render_formulario_revendas(),
    "➕ Orçamento de Máquina": lambda: render_formulario_negociacao(),
    "⚙️ PCP":                  lambda: render_aba_pcp(),
    "📦 Estoque de Máquinas":  lambda: render_aba_estoque(),
    "📄 NF em Demonstração":   lambda: render_aba_nf_demo(),
    "🔧 Peças":                lambda df=df_pecas, mock=is_mock_pecas: _render_aba_pecas(df, mock),
}

permitidas = abas_permitidas()

# [FIX-SEC-6] Sessão parcial: se autenticado mas sem abas, força novo login
if not permitidas and st.session_state.get("autenticado"):
    st.warning("⚠️ Sessão expirada ou permissões não carregadas. Por favor, faça login novamente.")
    for k in ["autenticado","usuario_atual","perfil_atual","nome_usuario","is_admin","abas_permitidas"]:
        st.session_state.pop(k, None)
    st.rerun()

abas_visiveis = [a for a in MAPA if a in permitidas]

if is_admin():
    abas_visiveis.append("👤 Admin")

tabs = st.tabs(abas_visiveis)

for tab, nome in zip(tabs, abas_visiveis):
    with tab:
        if nome == "👤 Admin":
            render_painel_admin()
        else:
            MAPA[nome]()
