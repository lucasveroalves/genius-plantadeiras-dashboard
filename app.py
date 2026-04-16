"""
app.py — Genius Plantadeiras v13
  • Persistência completa via Supabase
  • Aba ⚙️ Admin (apenas para admins) — gerenciar usuários e senhas
  • Planilha de peças persiste entre reinicializações
"""

import streamlit as st
import pandas as pd
from datetime import date

from auth import tela_login, painel_usuario, render_painel_admin, is_admin
from data.loader import preparar_pecas, calcular_kpis_pecas, calcular_curva_abc
from components.ui import (
    render_header, render_sidebar_uploads,
    render_banner_mock_pecas, render_auto_refresh,
)
from components.estoque import render_aba_estoque
from components.producao import render_aba_pcp
from components.forms import (
    render_formulario_negociacao,
    render_formulario_orcamento_pecas,
    render_formulario_revendas,
)
from components.nf_demo import render_aba_nf_demo

# ── Configuração Base ─────────────────────────────────────────
st.set_page_config(page_title="Genius Plantadeiras", layout="wide", page_icon="🌾")

# ── 1. Autenticação ───────────────────────────────────────────
if not tela_login():
    st.stop()

# ── 2. Sidebar e Upload ───────────────────────────────────────
painel_usuario()
_peca_file = render_sidebar_uploads()

# ── 3. Carregamento de Peças ──────────────────────────────────
df_pecas, is_mock_pecas = preparar_pecas(_peca_file)

# ── 4. UI Superior ────────────────────────────────────────────
render_header()
render_auto_refresh()

# ── 5. Abas ──────────────────────────────────────────────────
_abas_base = [
    "📝 Lançar Orçamento de Peças",
    "🏬 Revendas",
    "➕ Lançar Orçamento de Máquina",
    "⚙️ PCP",
    "📦 Estoque de Máquinas",
    "📄 NF em Demonstração",
    "🔧 Peças",
]
if is_admin():
    _abas_base.append("👤 Admin")

abas = st.tabs(_abas_base)

with abas[0]:
    render_formulario_orcamento_pecas()

with abas[1]:
    render_formulario_revendas()

with abas[2]:
    render_formulario_negociacao()

with abas[3]:
    render_aba_pcp()

with abas[4]:
    render_aba_estoque()

with abas[5]:
    render_aba_nf_demo()

with abas[6]:
    if is_mock_pecas:
        render_banner_mock_pecas()
    else:
        st.header("🔧 Análise de Peças")

        col_filtro1, col_filtro2 = st.columns([4, 1])
        with col_filtro1:
            data_min = df_pecas["Data_Venda"].min().date() if not df_pecas.empty else date.today()
            data_max = df_pecas["Data_Venda"].max().date() if not df_pecas.empty else date.today()
            intervalo = st.date_input(
                "Selecione o período",
                value=(data_min, data_max),
                min_value=data_min, max_value=data_max,
                format="DD/MM/YYYY", key="peca_periodo",
            )
        with col_filtro2:
            st.write("")
            st.write("")
            if st.button("🔄 Aplicar Filtro", key="peca_btn_filtro"):
                st.rerun()

        if isinstance(intervalo, (list, tuple)) and len(intervalo) == 2:
            data_inicio, data_fim = intervalo
            df_filtrado = df_pecas[
                (df_pecas["Data_Venda"].dt.date >= data_inicio) &
                (df_pecas["Data_Venda"].dt.date <= data_fim)
            ]
        else:
            df_filtrado = df_pecas

        from data.db import ler_orcamentos
        df_orc = ler_orcamentos()
        kpis   = calcular_kpis_pecas(df_filtrado)

        pecas_em_orcamento = 0.0
        if not df_orc.empty and "Status_Orc" in df_orc.columns and "Valor_Total" in df_orc.columns:
            mask_orc = df_orc["Status_Orc"].isin(["Em Orçamento", "Aguardando"])
            pecas_em_orcamento = pd.to_numeric(
                df_orc.loc[mask_orc, "Valor_Total"], errors="coerce"
            ).fillna(0).sum()

        def _brl(v):
            try:
                v = float(v)
                inteiro  = f"{int(v):,}".replace(",", ".")
                centavos = f"{v:.2f}".split(".")[1]
                return f"R$ {inteiro},{centavos}"
            except Exception:
                return "R$ 0,00"

        def _kpi_card(label, value):
            st.markdown(
                f'<div style="background:#1F2937;border:1px solid #2D3748;'
                f'border-left:4px solid #E36C2C;border-radius:10px;'
                f'padding:14px 16px 10px;min-height:80px;">'
                f'<div style="font-size:11px;font-weight:700;color:#6A7A8A;'
                f'text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;">{label}</div>'
                f'<div style="font-size:1.45rem;font-weight:700;color:#F0F4F8;'
                f'line-height:1.2;word-break:break-word;">{value}</div></div>',
                unsafe_allow_html=True,
            )

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1: _kpi_card("💰 Peças Faturadas",      _brl(kpis["total_faturado"]))
        with col2: _kpi_card("📋 Em Orçamento",         _brl(pecas_em_orcamento))
        with col3: _kpi_card("📦 Volume de Itens",      f"{int(kpis['volume_itens']):,}".replace(",", "."))
        with col4: _kpi_card("🎟️ Ticket Médio / Venda", _brl(kpis["ticket_medio"]))
        with col5: _kpi_card("🏷️ SKUs Ativos",          f"{kpis['qtd_skus']:,}".replace(",", "."))

        st.divider()

        from charts.plots import grafico_curva_abc, grafico_ranking_revendas_pecas
        col_abc, col_rev = st.columns(2)
        with col_abc:
            st.subheader("📊 Curva ABC – Peças Mais Vendidas")
            df_abc = calcular_curva_abc(df_filtrado, top_n=12)
            if not df_abc.empty:
                st.plotly_chart(grafico_curva_abc(df_abc), use_container_width=True)
            else:
                st.info("Sem dados para exibir a Curva ABC.")
        with col_rev:
            st.subheader("🏆 Top 10 Revendas – Consumo de Peças")
            if not df_filtrado.empty:
                st.plotly_chart(grafico_ranking_revendas_pecas(df_filtrado, top_n=10),
                                use_container_width=True)
            else:
                st.info("Sem dados para o ranking de revendas.")

        st.divider()
        st.subheader("📋 Detalhamento de Vendas (Peças)")
        cols_fmt = {}
        if "Valor_Unitario" in df_filtrado.columns:
            cols_fmt["Valor_Unitario"] = "R$ {:,.2f}".format
        if "Valor_Total" in df_filtrado.columns:
            cols_fmt["Valor_Total"] = "R$ {:,.2f}".format
        st.dataframe(
            df_filtrado.style.format(cols_fmt) if cols_fmt else df_filtrado,
            use_container_width=True, height=400,
        )

# ── Aba Admin (visível apenas para admins) ────────────────────
if is_admin() and len(abas) >= 8:
    with abas[7]:
        render_painel_admin()
