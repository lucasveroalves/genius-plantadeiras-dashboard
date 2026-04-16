"""
components/ui.py — Genius Plantadeiras v14
• Logo Genius na sidebar (substitui logo Streamlit)
• Auto-refresh a cada 30 segundos via streamlit-autorefresh
• Sidebar sem upload de Máquinas
"""

import os
import streamlit as st
from datetime import datetime


def render_header():
    # Logo / título centralizado
    logo = os.path.join(os.path.dirname(__file__), "..", "assets", "genius_logo.png")
    if os.path.exists(logo):
        col_l, col_c, col_r = st.columns([2, 1, 2])
        with col_c:
            st.image(logo, use_container_width=True)
    else:
        st.markdown("""
<div style='text-align:center;padding:1rem 0;'>
  <span style='font-size:2.4rem;font-weight:800;color:#E36C2C;
    font-family:Barlow Condensed,sans-serif;'>🌾 Genius Plantadeiras</span><br>
  <span style='color:#6A7A8A;font-size:1rem;'>Performance Comercial e Gestão Integrada</span>
</div>""", unsafe_allow_html=True)

    st.markdown('<hr style="border:0.5px solid #2D3748;margin-bottom:1.5rem;">', unsafe_allow_html=True)


def render_sidebar_uploads():
    """
    Sidebar com logo Genius no topo (em vez do logo do Streamlit).
    Retorna: arquivo de peças ou None.
    """
    # Esconde o branding padrão do Streamlit
    st.markdown("""
<style>
  [data-testid="stSidebarHeader"] { display: none !important; }
  section[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
</style>""", unsafe_allow_html=True)

    logo = os.path.join(os.path.dirname(__file__), "..", "assets", "genius_logo.png")
    if os.path.exists(logo):
        st.sidebar.image(logo, use_container_width=True)
    else:
        st.sidebar.markdown(
            "<div style='text-align:center;padding:12px 0 6px;'>"
            "<span style='font-size:1.2rem;font-weight:700;color:#E36C2C;'>🌾 Genius Plantadeiras</span>"
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
    Auto-refresh real a cada 30 s (atualiza dados do Supabase para todos os usuários).
    """
    try:
        from streamlit_autorefresh import st_autorefresh
        count = st_autorefresh(interval=30_000, key="autorefresh_global")
        if count and count > 0:
            # Limpa cache do Supabase para forçar releitura
            st.cache_resource.clear()
    except ImportError:
        if "last_refresh" not in st.session_state:
            st.session_state.last_refresh = datetime.now().strftime("%H:%M:%S")
        _, col_btn = st.columns([8, 2])
        with col_btn:
            if st.button("🔄 Atualizar", key="btn_refresh_manual"):
                st.session_state.last_refresh = datetime.now().strftime("%H:%M:%S")
                st.cache_resource.clear()
                st.rerun()
        st.caption(f"Atualizado: {st.session_state.last_refresh}")
