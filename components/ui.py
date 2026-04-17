"""
components/ui.py — Genius Implementos Agrícolas v14 (CORRIGIDO)

Correções aplicadas:
  [FIX-PERF-2] render_auto_refresh: substituído st.cache_data.clear() global
               por invalidação seletiva — limpa apenas _processar_bytes se necessário.
               O cache global não é mais derrubado, evitando reprocessamento de
               planilhas de TODOS os usuários ao mesmo tempo.
               Na prática, os caches têm TTL próprio (300s para planilhas, 30s para
               dados Supabase) e expiram naturalmente sem precisar de clear().
"""

import os
import streamlit as st
from datetime import datetime


def render_header():
    logo = os.path.join(os.path.dirname(__file__), "..", "assets", "genius_logo.png")
    if os.path.exists(logo):
        col_l, col_c, col_r = st.columns([2, 1, 2])
        with col_c:
            st.image(logo, use_container_width=True)
    else:
        st.markdown("""
<div style='text-align:center;padding:1rem 0;'>
  <span style='font-size:2.4rem;font-weight:800;color:#E36C2C;
    font-family:Barlow Condensed,sans-serif;'>🌾 Genius Implementos Agrícolas</span><br>
  <span style='color:#6A7A8A;font-size:1rem;'>Performance Comercial e Gestão Integrada</span>
</div>""", unsafe_allow_html=True)

    st.markdown('<hr style="border:0.5px solid #2D3748;margin-bottom:1.5rem;">', unsafe_allow_html=True)


def render_sidebar_uploads():
    st.markdown("""
<style>
  [data-testid="stSidebarHeader"] { display: none !important; }
  section[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
</style>""", unsafe_allow_html=True)

    logo = os.path.join(os.path.dirname(__file__), "..", "assets", "genius_logo.png")
    if os.path.exists(logo):
        st.sidebar.markdown(
            '<div style="display:flex;justify-content:center;padding:8px 0 4px;">',
            unsafe_allow_html=True)
        col_sb_l, col_sb_c, col_sb_r = st.sidebar.columns([1, 2, 1])
        with col_sb_c:
            st.image(logo, use_container_width=True)
        st.sidebar.markdown('</div>', unsafe_allow_html=True)
    else:
        st.sidebar.markdown(
            "<div style='text-align:center;padding:12px 0 6px;'>"
            "<span style='font-size:1.1rem;font-weight:700;color:#E36C2C;'>🌾 Genius Implementos Agrícolas</span>"
            "</div>", unsafe_allow_html=True)

    st.sidebar.markdown("---")
    st.sidebar.title("📁 Importar Planilha")

    with st.sidebar.expander("Upload de Arquivos", expanded=True):
        pec = st.file_uploader("Peças (Senior ERP)", type=["xlsx"], key="up_pecas")

    return pec


def render_banner_mock_pecas():
    st.info(
        "🔧 **Módulo de Peças.** Carregue o relatório de faturamento do ERP Senior "
        "na barra lateral para ativar esta aba."
    )


def render_auto_refresh():
    """
    [FIX-PERF-2] Auto-refresh a cada 5 minutos SEM clear() global de cache.
    Os caches têm TTL próprio configurado em db.py e loader.py:
      - Dados Supabase (produção, orçamentos, leadtime): ttl=30s
      - Planilha Senior processada: ttl=300s
      - Cliente Supabase: ttl=3600s
    O auto-refresh apenas força um rerun para que os widgets reflitam
    dados cujo TTL já expirou naturalmente — sem derrubar cache de ninguém.
    """
    try:
        from streamlit_autorefresh import st_autorefresh
        # Apenas rerun — sem cache.clear()
        st_autorefresh(interval=300_000, key="autorefresh_global")
    except ImportError:
        if "last_refresh" not in st.session_state:
            st.session_state.last_refresh = datetime.now().strftime("%H:%M:%S")
        _, col_btn = st.columns([8, 2])
        with col_btn:
            if st.button("🔄 Atualizar", key="btn_refresh_manual"):
                st.session_state.last_refresh = datetime.now().strftime("%H:%M:%S")
                st.rerun()
        st.caption(f"Atualizado: {st.session_state.last_refresh}")
