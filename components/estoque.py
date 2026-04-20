"""
components/estoque.py — Genius Implementos Agrícolas v15 (CORRIGIDO)

Correções aplicadas:
  [FIX-SYNTAX]  from datetime import datetime movido para ANTES do docstring
  [FIX-BUG-DATA] Substituído session_state por Supabase (db.py) para pátio e revendas
                 — dados agora são compartilhados entre TODOS os usuários em tempo real
  [FIX-SCHEMA]  Colunas alinhadas com db.py (_COLS_PATIO / _COLS_EST_REV):
                Pátio:   Codigo, Modelo, Tipo, Ano, Cor, Numero_Serie,
                         Data_Entrada, Status_Patio, Observacoes
                Revendas: Codigo, Modelo, Revenda, Contato, Cidade, Estado,
                          Data_Envio, Data_Retorno_Prevista, Status_Revenda, Observacoes
"""

from __future__ import annotations
from datetime import date, datetime

import io
import pandas as pd
import streamlit as st

from data.db import (
    ler_patio,          adicionar_patio,    excluir_patio,    exportar_patio,
    ler_revendas_estoque, adicionar_revenda_estoque, excluir_revenda_estoque, exportar_revendas_estoque,
)
from data.loader_estoque import STATUS_PATIO, STATUS_REV, TIPOS_PATIO

# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────

TIPOS_MAQUINA = ["SELETA", "GSP", "GSPV", "GSPA", "GATA", "STG", "SIG", "Outro"]
CONDICOES     = ["NOVA", "DEMONSTRAÇÃO", "SEMI-NOVA", "USADA/REFORMADA"]

_CSS = """
<style>
.est-sec{font-size:11px;font-weight:700;color:#3A4858;text-transform:uppercase;
  letter-spacing:.1em;border-bottom:1px solid #30394A;padding-bottom:6px;margin-bottom:14px;}
.est-kpi-label{font-size:11px;font-weight:700;color:#6A7A8A;text-transform:uppercase;
  letter-spacing:.08em;}
.est-kpi-val{font-family:'Barlow Condensed',sans-serif;font-size:2.2rem;font-weight:700;
  color:#F0F4F8;line-height:1.1;}
.est-kpi-card{background:#1F2937;border:1px solid #2D3748;border-left:4px solid #E36C2C;
  border-radius:12px;padding:16px 20px 12px;}
.tbl-hdr{font-size:10px;font-weight:700;color:#3A4858;text-transform:uppercase;
  letter-spacing:.08em;padding-bottom:6px;border-bottom:1px solid #2D3748;}
.tbl-div{border-bottom:1px solid rgba(45,55,72,.5);margin:3px 0;}
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# Formatação
# ─────────────────────────────────────────────────────────────────────────────

def formatar_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _badge_status_patio(status: str) -> str:
    cores = {
        "Disponível":      {"bg": "rgba(61,153,112,.18)",  "border": "rgba(61,153,112,.5)",  "text": "#52B788"},
        "Reservada":       {"bg": "rgba(232,160,32,.18)",  "border": "rgba(232,160,32,.5)",  "text": "#E8C040"},
        "Vendida":         {"bg": "rgba(74,122,191,.18)",  "border": "rgba(74,122,191,.5)",  "text": "#7AAFD4"},
        "Em Manutenção":   {"bg": "rgba(232,64,64,.18)",   "border": "rgba(232,64,64,.5)",   "text": "#E87878"},
    }
    c = cores.get(status, {"bg": "rgba(106,122,138,.15)", "border": "rgba(106,122,138,.4)", "text": "#A8B8CC"})
    return (f'<span style="background:{c["bg"]};border:1px solid {c["border"]};color:{c["text"]};'
            f'border-radius:20px;padding:3px 10px;font-size:12px;font-weight:600;">{status}</span>')

def _badge_status_rev(status: str) -> str:
    cores = {
        "Na Revenda": {"bg": "rgba(232,160,32,.18)", "border": "rgba(232,160,32,.5)", "text": "#E8C040"},
        "Retornou":   {"bg": "rgba(61,153,112,.18)", "border": "rgba(61,153,112,.5)", "text": "#52B788"},
        "Vendida":    {"bg": "rgba(74,122,191,.18)", "border": "rgba(74,122,191,.5)", "text": "#7AAFD4"},
    }
    c = cores.get(status, {"bg": "rgba(106,122,138,.15)", "border": "rgba(106,122,138,.4)", "text": "#A8B8CC"})
    return (f'<span style="background:{c["bg"]};border:1px solid {c["border"]};color:{c["text"]};'
            f'border-radius:20px;padding:3px 10px;font-size:12px;font-weight:600;">{status}</span>')

def _section(titulo: str):
    st.markdown(f'<div class="est-sec">{titulo}</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# KPIs
# ─────────────────────────────────────────────────────────────────────────────

def _kpis_estoque(df_pat: pd.DataFrame, df_rev: pd.DataFrame):
    qtd_patio    = len(df_pat)
    qtd_revendas = len(df_rev)
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.metric("🏭 Máquinas no Pátio", qtd_patio)
    with c2:
        st.metric("🚛 Máquinas em Revendas", qtd_revendas)

# ─────────────────────────────────────────────────────────────────────────────
# Formulário Pátio
# ─────────────────────────────────────────────────────────────────────────────

def _form_patio():
    _section("➕ Cadastrar Máquina no Pátio")
    with st.expander("Preencher formulário", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            codigo      = st.text_input("Código do Produto", key="pat_cod",   placeholder="Ex: 250001020")
            modelo      = st.text_input("Modelo",            key="pat_mod",   placeholder="Ex: GATA 18050")
            tipo        = st.selectbox("Tipo",   TIPOS_MAQUINA, key="pat_tipo")
        with col2:
            ano         = st.number_input("Ano de Fabricação", min_value=2010, max_value=2030, value=2025, key="pat_ano")
            cor         = st.text_input("Cor",                key="pat_cor",  placeholder="Ex: Laranja")
            numero_serie = st.text_input("Número de Série",   key="pat_ns",   placeholder="Ex: GS-11688")
        with col3:
            data_entrada = st.date_input("Data de Entrada", value=date.today(), format="DD/MM/YYYY", key="pat_dt_ent")
            status_patio = st.selectbox("Status", STATUS_PATIO, key="pat_status")
            obs          = st.text_area("Observações", key="pat_obs", height=68, placeholder="Campo livre")

        if st.button("Salvar no Pátio", type="primary", use_container_width=True, key="pat_salvar"):
            if not codigo.strip():
                st.toast("⚠️ Código do Produto é obrigatório.", icon="🚫")
            elif not modelo.strip():
                st.toast("⚠️ Modelo é obrigatório.", icon="🚫")
            else:
                reg = {
                    "Codigo":       codigo.strip(),
                    "Modelo":       modelo.strip(),
                    "Tipo":         tipo,
                    "Ano":          str(int(ano)),
                    "Cor":          cor.strip(),
                    "Numero_Serie": numero_serie.strip(),
                    "Data_Entrada": data_entrada.strftime("%d/%m/%Y"),
                    "Status_Patio": status_patio,
                    "Observacoes":  obs.strip(),
                }
                if adicionar_patio(reg):
                    st.toast("✅ Máquina adicionada ao pátio!", icon="✅")
                    st.rerun()
                else:
                    st.error("❌ Falha ao salvar. Verifique a conexão com o banco de dados.")

# ─────────────────────────────────────────────────────────────────────────────
# Formulário Revenda
# ─────────────────────────────────────────────────────────────────────────────

def _form_revenda():
    _section("➕ Cadastrar Máquina em Revenda")
    with st.expander("Preencher formulário", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            codigo      = st.text_input("Código do Produto", key="rev_cod",      placeholder="Ex: 250001020")
            modelo      = st.text_input("Modelo",            key="rev_mod",      placeholder="Ex: GATA 18050")
            revenda     = st.text_input("Nome da Revenda",   key="rev_nome_rev", placeholder="Ex: AgroSul")
        with col2:
            contato     = st.text_input("Contato / Responsável", key="rev_contato", placeholder="Nome do responsável")
            cidade      = st.text_input("Cidade",                key="rev_cidade",  placeholder="Ex: Chapecó")
            estado      = st.text_input("Estado (UF)",           key="rev_estado",  placeholder="Ex: SC", max_chars=2)
        with col3:
            data_envio  = st.date_input("Data de Envio",         value=date.today(), format="DD/MM/YYYY", key="rev_env")
            data_ret    = st.date_input("Previsão de Retorno",   value=None,         format="DD/MM/YYYY", key="rev_ret")
            status_rev  = st.selectbox("Status", STATUS_REV, key="rev_status")
        obs = st.text_area("Observações", key="rev_obs", height=60, placeholder="Campo livre")

        if st.button("Salvar em Revenda", type="primary", use_container_width=True, key="rev_salvar"):
            if not codigo.strip():
                st.toast("⚠️ Código do Produto é obrigatório.", icon="🚫")
            elif not revenda.strip():
                st.toast("⚠️ Nome da Revenda é obrigatório.", icon="🚫")
            else:
                reg = {
                    "Codigo":               codigo.strip(),
                    "Modelo":               modelo.strip(),
                    "Revenda":              revenda.strip(),
                    "Contato":              contato.strip(),
                    "Cidade":               cidade.strip(),
                    "Estado":               estado.strip().upper(),
                    "Data_Envio":           data_envio.strftime("%d/%m/%Y"),
                    "Data_Retorno_Prevista": data_ret.strftime("%d/%m/%Y") if data_ret else "",
                    "Status_Revenda":       status_rev,
                    "Observacoes":          obs.strip(),
                }
                if adicionar_revenda_estoque(reg):
                    st.toast("✅ Máquina cadastrada em revenda!", icon="✅")
                    st.rerun()
                else:
                    st.error("❌ Falha ao salvar. Verifique a conexão com o banco de dados.")

# ─────────────────────────────────────────────────────────────────────────────
# Tabelas
# ─────────────────────────────────────────────────────────────────────────────

def _tabela_patio(df_pat: pd.DataFrame):
    if df_pat.empty:
        st.info("Nenhuma máquina no pátio cadastrada.")
        return

    # Garante colunas necessárias
    for c in ["Codigo", "Modelo", "Tipo", "Ano", "Numero_Serie", "Status_Patio", "Observacoes"]:
        if c not in df_pat.columns:
            df_pat[c] = "—"

    cols_w = [1.0, 1.2, 1.0, 0.7, 1.0, 1.2, 2.0, 0.5]
    hdr    = st.columns(cols_w)
    for col, lbl in zip(hdr, ["Código", "Modelo", "Tipo", "Ano", "Nº Série", "Status", "Observações", ""]):
        col.markdown(f'<div class="tbl-hdr">{lbl}</div>', unsafe_allow_html=True)

    for _, row in df_pat.iterrows():
        row_id = row.get("id")
        cols   = st.columns(cols_w)
        cols[0].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{row.get("Codigo","—")}</div>', unsafe_allow_html=True)
        cols[1].markdown(f'<div style="font-size:13px;color:#EEF2F8;font-weight:500;padding-top:8px;">{row.get("Modelo","—")}</div>', unsafe_allow_html=True)
        cols[2].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Tipo","—")}</div>', unsafe_allow_html=True)
        cols[3].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Ano","—")}</div>', unsafe_allow_html=True)
        cols[4].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Numero_Serie","—")}</div>', unsafe_allow_html=True)
        cols[5].markdown(f'<div style="padding-top:4px;">{_badge_status_patio(str(row.get("Status_Patio","—")))}</div>', unsafe_allow_html=True)
        cols[6].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Observacoes","—") or "—"}</div>', unsafe_allow_html=True)
        if cols[7].button("🗑", key=f"del_pat_{row_id}", help="Remover"):
            if excluir_patio(int(row_id)):
                st.toast("Máquina removida.", icon="🗑")
                st.rerun()
        st.markdown('<div class="tbl-div"></div>', unsafe_allow_html=True)

    st.caption(f"Total: {len(df_pat)} máquina(s) no pátio.")


def _tabela_revendas(df_rev: pd.DataFrame):
    if df_rev.empty:
        st.info("Nenhuma máquina em revenda cadastrada.")
        return

    for c in ["Codigo", "Modelo", "Revenda", "Cidade", "Estado", "Data_Envio", "Data_Retorno_Prevista", "Status_Revenda", "Observacoes"]:
        if c not in df_rev.columns:
            df_rev[c] = "—"

    cols_w = [1.0, 1.2, 1.5, 1.0, 0.6, 0.9, 1.1, 1.1, 2.0, 0.5]
    hdr    = st.columns(cols_w)
    for col, lbl in zip(hdr, ["Código", "Modelo", "Revenda", "Contato", "UF", "Envio", "Retorno Prev.", "Status", "Observações", ""]):
        col.markdown(f'<div class="tbl-hdr">{lbl}</div>', unsafe_allow_html=True)

    for _, row in df_rev.iterrows():
        row_id = row.get("id")
        cols   = st.columns(cols_w)
        cols[0].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{row.get("Codigo","—")}</div>', unsafe_allow_html=True)
        cols[1].markdown(f'<div style="font-size:13px;color:#EEF2F8;font-weight:500;padding-top:8px;">{row.get("Modelo","—")}</div>', unsafe_allow_html=True)
        cols[2].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Revenda","—")}</div>', unsafe_allow_html=True)
        cols[3].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Contato","—")}</div>', unsafe_allow_html=True)
        cols[4].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Estado","—")}</div>', unsafe_allow_html=True)
        cols[5].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{row.get("Data_Envio","—")}</div>', unsafe_allow_html=True)
        cols[6].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{row.get("Data_Retorno_Prevista","—") or "—"}</div>', unsafe_allow_html=True)
        cols[7].markdown(f'<div style="padding-top:4px;">{_badge_status_rev(str(row.get("Status_Revenda","—")))}</div>', unsafe_allow_html=True)
        cols[8].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Observacoes","—") or "—"}</div>', unsafe_allow_html=True)
        if cols[9].button("🗑", key=f"del_rev_{row_id}", help="Remover"):
            if excluir_revenda_estoque(int(row_id)):
                st.toast("Registro removido.", icon="🗑")
                st.rerun()
        st.markdown('<div class="tbl-div"></div>', unsafe_allow_html=True)

    st.caption(f"Total: {len(df_rev)} máquina(s) em revendas.")

# ─────────────────────────────────────────────────────────────────────────────
# Render principal
# ─────────────────────────────────────────────────────────────────────────────

def render_aba_estoque():
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown("""
<div style="display:flex;align-items:center;gap:14px;padding:10px 0 18px;
            border-bottom:1px solid #2D3748;margin-bottom:24px;">
  <div style="background:rgba(227,108,44,.14);border:1px solid rgba(227,108,44,.4);
              border-radius:10px;padding:10px 14px;font-size:22px;">🏪</div>
  <div>
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:1.9rem;
                font-weight:700;color:#F0F4F8;line-height:1.1;">Estoque de Máquinas</div>
    <div style="font-size:12px;color:#6A7A8A;text-transform:uppercase;
                letter-spacing:.07em;margin-top:4px;">
      Pátio Próprio &nbsp;·&nbsp; Máquinas em Revendas</div>
  </div>
</div>
""", unsafe_allow_html=True)

    # Carrega dados do Supabase (compartilhado entre todos usuários)
    df_pat = ler_patio()
    df_rev = ler_revendas_estoque()

    _kpis_estoque(df_pat, df_rev)
    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)

    # Botões de exportação
    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        st.download_button(
            label="📥 Exportar Pátio (.xlsx)",
            data=exportar_patio(),
            file_name=f"estoque_patio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="estoque_export_patio_btn",
        )
    with col_exp2:
        st.download_button(
            label="📥 Exportar Revendas (.xlsx)",
            data=exportar_revendas_estoque(),
            file_name=f"estoque_revendas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="estoque_export_rev_btn",
        )

    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)

    sub1, sub2 = st.tabs(["🏭 Pátio Próprio", "🚛 Máquinas em Revendas"])

    with sub1:
        _form_patio()
        st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)
        _section("📋 Equipamentos no Pátio")
        _tabela_patio(df_pat)

    with sub2:
        _form_revenda()
        st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)
        _section("📋 Equipamentos em Revendas")
        _tabela_revendas(df_rev)
