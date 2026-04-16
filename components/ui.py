"""
components/ui.py — Genius Plantadeiras
Versão 11.0:
  • Sidebar: removido upload de Máquinas, mantido apenas Peças Senior.
  • Logo Genius adicionada na sidebar (assets/genius_logo.png).
  • Auto-refresh real a cada 30 segundos via st_autorefresh (ou fallback manual).
"""

import streamlit as st
from datetime import datetime
import os

def render_header():
    st.markdown("""
        <div style='text-align: center; padding: 1rem 0;'>
            <h1 style='color: #EEF2F8; margin-bottom: 0;'>Genius Plantadeiras</h1>
            <p style='color: #6A7A8A; font-size: 1.1rem;'>Performance Comercial e Gestão Integrada</p>
        </div>
        <hr style='border: 0.5px solid #2D3748; margin-bottom: 2rem;'>
    """, unsafe_allow_html=True)


def render_sidebar_uploads():
    """
    Renderiza a sidebar com:
      - Logo Genius (assets/genius_logo.png)
      - Upload de Peças (Senior) apenas
    Retorna: arquivo de peças (ou None)
    """
    # ── Logo ──────────────────────────────────────────────────
    logo_path = os.path.join(os.path.dirname(__file__), "..", "assets", "genius_logo.png")
    if os.path.exists(logo_path):
        st.sidebar.image(logo_path, use_container_width=True)
    else:
        st.sidebar.markdown(
            "<div style='text-align:center;padding:10px 0 6px;'>"
            "<span style='font-size:1.3rem;font-weight:700;color:#E36C2C;'>🌾 Genius Plantadeiras</span>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.sidebar.markdown("---")
    st.sidebar.title("📁 Importar Planilha")

    with st.sidebar.expander("Upload de Arquivos", expanded=True):
        pec = st.file_uploader("Peças (Senior ERP)", type=["xlsx"], key="up_pecas")

    return pec


def render_banner_mock():
    st.info("💡 **Aguardando dados.** O dashboard está em modo de espera.")


def render_banner_mock_pecas():
    st.info(
        "🔧 **Módulo de Peças.** Por favor, carregue o relatório de faturamento "
        "do ERP Senior para ativar esta aba."
    )


def render_auto_refresh():
    """
    Auto-refresh a cada 30 segundos.
    Usa streamlit-autorefresh se disponível; caso contrário exibe botão manual.
    """
    # Tenta usar streamlit-autorefresh (pip install streamlit-autorefresh)
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=30_000, key="autorefresh_global")
    except ImportError:
        # Fallback: botão manual de atualização
        if "last_refresh" not in st.session_state:
            st.session_state.last_refresh = datetime.now().strftime("%H:%M:%S")

        col1, col2 = st.columns([8, 2])
        with col2:
            if st.button("🔄 Atualizar Dados", key="btn_refresh_manual"):
                st.session_state.last_refresh = datetime.now().strftime("%H:%M:%S")
                st.rerun()
        st.caption(f"Dados atualizados em: {st.session_state.last_refresh}")
