from datetime import datetime
"""
components/estoque.py — Genius Plantadeiras
Versão 11.0:
  • Renomeado para "Estoque de Máquinas" no header interno.
  • Conteúdo (pátio e revendas) mantido idêntico.
"""

from __future__ import annotations

import io
from datetime import date
from typing import List, Dict, Any

import pandas as pd
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────

TIPOS_MAQUINA = ["SELETA", "GSP", "GSPV", "GSPA", "GATA", "STG", "SIG", "Outro"]
CONDICOES = ["NOVA", "DEMONSTRAÇÃO", "SEMI-NOVA", "USADA/REFORMADA"]

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
# Inicialização do session_state
# ─────────────────────────────────────────────────────────────────────────────

def _init_session():
    if "estoque_patio" not in st.session_state:
        st.session_state.estoque_patio = []
    if "estoque_revendas" not in st.session_state:
        st.session_state.estoque_revendas = []

# ─────────────────────────────────────────────────────────────────────────────
# Formatação
# ─────────────────────────────────────────────────────────────────────────────

def formatar_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _badge_condicao(cond: str) -> str:
    cores = {
        "NOVA":           {"bg": "rgba(61,153,112,.18)", "border": "rgba(61,153,112,.5)", "text": "#52B788"},
        "DEMONSTRAÇÃO":   {"bg": "rgba(232,160,32,.18)", "border": "rgba(232,160,32,.5)", "text": "#E8C040"},
        "SEMI-NOVA":      {"bg": "rgba(74,122,191,.18)", "border": "rgba(74,122,191,.5)", "text": "#7AAFD4"},
        "USADA/REFORMADA":{"bg": "rgba(232,64,64,.18)",  "border": "rgba(232,64,64,.5)",  "text": "#E87878"},
    }
    c = cores.get(cond, {"bg": "rgba(106,122,138,.15)", "border": "rgba(106,122,138,.4)", "text": "#A8B8CC"})
    return f'<span style="background:{c["bg"]};border:1px solid {c["border"]};color:{c["text"]};border-radius:20px;padding:3px 10px;font-size:12px;font-weight:600;">{cond}</span>'

def _section(titulo: str):
    st.markdown(f'<div class="est-sec">{titulo}</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────────────────────────────────────

def _adicionar_patio(registro: Dict[str, Any]) -> bool:
    _init_session()
    st.session_state.estoque_patio.append(registro)
    return True

def _excluir_patio(idx: int) -> bool:
    _init_session()
    if 0 <= idx < len(st.session_state.estoque_patio):
        del st.session_state.estoque_patio[idx]
        return True
    return False

def _adicionar_revenda(registro: Dict[str, Any]) -> bool:
    _init_session()
    st.session_state.estoque_revendas.append(registro)
    return True

def _excluir_revenda(idx: int) -> bool:
    _init_session()
    if 0 <= idx < len(st.session_state.estoque_revendas):
        del st.session_state.estoque_revendas[idx]
        return True
    return False

# ─────────────────────────────────────────────────────────────────────────────
# KPIs
# ─────────────────────────────────────────────────────────────────────────────

def _kpis_estoque():
    pat = st.session_state.get("estoque_patio", [])
    rev = st.session_state.get("estoque_revendas", [])
    qtd_patio    = len(pat)
    qtd_revendas = len(rev)
    valor_total  = (
        sum(float(p.get("Preco_Lista", 0) or 0) for p in pat) +
        sum(float(r.get("Preco_Lista", 0) or 0) for r in rev)
    )
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        st.metric("🏭 Pátio", qtd_patio)
    with c2:
        st.metric("🚛 Revendas", qtd_revendas)
    with c3:
        st.metric("💰 Valor Total", formatar_brl(valor_total))

# ─────────────────────────────────────────────────────────────────────────────
# Formulário Pátio
# ─────────────────────────────────────────────────────────────────────────────

def _form_patio():
    _section("➕ Cadastrar Máquina no Pátio")
    with st.expander("Preencher formulário", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            codigo       = st.text_input("Código do Produto", key="pat_cod", placeholder="Ex: 250001020")
            tipo         = st.selectbox("Tipo", TIPOS_MAQUINA, key="pat_tipo")
            descricao    = st.text_input("Descrição", key="pat_desc", placeholder="Ex: PLANTADEIRA AMENDOIM")
        with col2:
            modelo       = st.text_input("Modelo", key="pat_mod", placeholder="Ex: 4060")
            ano          = st.number_input("Ano de Fabricação", min_value=2010, max_value=2030, value=2025, key="pat_ano")
            nome_comercial = st.text_input("Nome Comercial", key="pat_nome", placeholder="Ex: SELETA-4090-2025")
        with col3:
            gs           = st.text_input("Número GS", key="pat_gs", placeholder="Ex: GS-11688")
            condicao     = st.selectbox("Condição", CONDICOES, key="pat_cond")
            configs      = st.text_area("Configurações", key="pat_conf", height=68,
                                        placeholder="Descrição técnica completa")
        col4, col5 = st.columns(2)
        with col4:
            custo       = st.number_input("Custo de Fabricação (R$)", min_value=0.0, step=1000.0, key="pat_custo")
        with col5:
            preco_lista = st.number_input("Preço de Lista Atual (R$)", min_value=0.0, step=1000.0, key="pat_preco")
        obs = st.text_area("Observação", key="pat_obs", height=60, placeholder="Campo livre")

        if st.button("Salvar no Pátio", type="primary", use_container_width=True, key="pat_salvar"):
            if not codigo.strip():
                st.toast("⚠️ Código do Produto é obrigatório.", icon="🚫")
            elif not modelo.strip():
                st.toast("⚠️ Modelo é obrigatório.", icon="🚫")
            else:
                reg = {
                    "Codigo":        codigo.strip(),
                    "Tipo":          tipo,
                    "Descricao":     descricao.strip(),
                    "Modelo":        modelo.strip(),
                    "Ano":           int(ano),
                    "Nome":          nome_comercial.strip(),
                    "GS":            gs.strip(),
                    "Configuracoes": configs.strip(),
                    "Condicao":      condicao,
                    "Custo":         custo,
                    "Preco_Lista":   preco_lista,
                    "Observacao":    obs.strip(),
                    "Localizacao":   "PATIO",
                }
                if _adicionar_patio(reg):
                    st.toast("✅ Máquina adicionada ao pátio!", icon="✅")
                    st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# Formulário Revenda
# ─────────────────────────────────────────────────────────────────────────────

def _form_revenda():
    _section("➕ Cadastrar Máquina em Revenda")
    with st.expander("Preencher formulário", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            codigo       = st.text_input("Código do Produto", key="rev_cod",  placeholder="Ex: 250001020")
            tipo         = st.selectbox("Tipo", TIPOS_MAQUINA, key="rev_tipo")
            descricao    = st.text_input("Descrição", key="rev_desc", placeholder="Descrição do equipamento")
        with col2:
            modelo       = st.text_input("Modelo", key="rev_mod", placeholder="Ex: 4060")
            nome_rev     = st.text_input("Nome da Revenda", key="rev_nome_rev", placeholder="Ex: AgroSul")
            contato_rev  = st.text_input("Contato / Responsável", key="rev_contato", placeholder="Nome do responsável")
        with col3:
            gs           = st.text_input("Número GS", key="rev_gs", placeholder="Ex: GS-11688")
            condicao     = st.selectbox("Condição", CONDICOES, key="rev_cond")
            data_envio   = st.date_input("Data de Envio", value=date.today(), format="DD/MM/YYYY", key="rev_env")
            data_retorno = st.date_input("Previsão de Retorno", value=None, format="DD/MM/YYYY", key="rev_ret")

        col4, col5 = st.columns(2)
        with col4:
            preco_lista = st.number_input("Preço de Lista (R$)", min_value=0.0, step=1000.0, key="rev_preco")
        with col5:
            obs = st.text_area("Observação", key="rev_obs", height=60, placeholder="Campo livre")

        if st.button("Salvar em Revenda", type="primary", use_container_width=True, key="rev_salvar"):
            if not codigo.strip():
                st.toast("⚠️ Código do Produto é obrigatório.", icon="🚫")
            elif not nome_rev.strip():
                st.toast("⚠️ Nome da Revenda é obrigatório.", icon="🚫")
            else:
                reg = {
                    "Codigo":               codigo.strip(),
                    "Tipo":                 tipo,
                    "Descricao":            descricao.strip(),
                    "Modelo":               modelo.strip(),
                    "Nome_Revenda":         nome_rev.strip(),
                    "Contato":              contato_rev.strip(),
                    "GS":                   gs.strip(),
                    "Condicao":             condicao,
                    "Preco_Lista":          preco_lista,
                    "Data_Envio":           data_envio.strftime("%d/%m/%Y"),
                    "Data_Retorno_Prevista": data_retorno.strftime("%d/%m/%Y") if data_retorno else "",
                    "Observacao":           obs.strip(),
                    "Localizacao":          "REVENDA",
                }
                if _adicionar_revenda(reg):
                    st.toast("✅ Máquina cadastrada em revenda!", icon="✅")
                    st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# Tabelas
# ─────────────────────────────────────────────────────────────────────────────

def _tabela_patio():
    _init_session()
    df_pat = pd.DataFrame(st.session_state.estoque_patio)
    if df_pat.empty:
        st.info("Nenhuma máquina no pátio cadastrada.")
        return

    cols_show = ["Codigo", "Modelo", "Tipo", "Ano", "GS", "Condicao", "Preco_Lista", "Observacao"]
    for c in cols_show:
        if c not in df_pat.columns:
            df_pat[c] = "—"
    df_v = df_pat[cols_show].copy().reset_index()
    df_v.rename(columns={"index": "_idx"}, inplace=True)

    cols_w = [1.0, 1.2, 1.0, 0.7, 1.0, 1.2, 1.2, 2.0, 0.5]
    hdr = st.columns(cols_w)
    for c, lbl in zip(hdr, ["Código", "Modelo", "Tipo", "Ano", "GS", "Condição", "Preço Lista", "Observação", ""]):
        c.markdown(f'<div class="tbl-hdr">{lbl}</div>', unsafe_allow_html=True)

    for _, row in df_v.iterrows():
        idx  = int(row["_idx"])
        cols = st.columns(cols_w)
        cols[0].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{row.get("Codigo","—")}</div>', unsafe_allow_html=True)
        cols[1].markdown(f'<div style="font-size:13px;color:#EEF2F8;font-weight:500;padding-top:8px;">{row.get("Modelo","—")}</div>', unsafe_allow_html=True)
        cols[2].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Tipo","—")}</div>', unsafe_allow_html=True)
        cols[3].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Ano","—")}</div>', unsafe_allow_html=True)
        cols[4].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("GS","—")}</div>', unsafe_allow_html=True)
        cols[5].markdown(f'<div style="padding-top:4px;">{_badge_condicao(str(row.get("Condicao","—")))}</div>', unsafe_allow_html=True)
        preco = row.get("Preco_Lista", 0)
        cols[6].markdown(f'<div style="font-size:13px;color:#F0F4F8;font-weight:600;padding-top:8px;">{formatar_brl(float(preco or 0))}</div>', unsafe_allow_html=True)
        cols[7].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{str(row.get("Observacao","—")) or "—"}</div>', unsafe_allow_html=True)
        if cols[8].button("🗑", key=f"del_pat_{idx}", help="Remover"):
            if _excluir_patio(idx):
                st.toast("Máquina removida.", icon="🗑")
                st.rerun()
        st.markdown('<div class="tbl-div"></div>', unsafe_allow_html=True)
    st.caption(f"Total: {len(df_pat)} máquina(s) no pátio.")


def _tabela_revendas():
    _init_session()
    df_rev = pd.DataFrame(st.session_state.estoque_revendas)
    if df_rev.empty:
        st.info("Nenhuma máquina em revenda cadastrada.")
        return

    cols_show = ["Codigo", "Modelo", "Nome_Revenda", "Data_Envio", "Data_Retorno_Prevista",
                 "Condicao", "Preco_Lista", "Observacao"]
    for c in cols_show:
        if c not in df_rev.columns:
            df_rev[c] = "—"
    df_v = df_rev[cols_show].copy().reset_index()
    df_v.rename(columns={"index": "_idx"}, inplace=True)

    cols_w = [1.0, 1.2, 1.5, 0.9, 1.2, 1.0, 1.2, 2.0, 0.5]
    hdr = st.columns(cols_w)
    for c, lbl in zip(hdr, ["Código", "Modelo", "Revenda", "Envio", "Retorno Prev.", "Condição", "Preço Lista", "Observação", ""]):
        c.markdown(f'<div class="tbl-hdr">{lbl}</div>', unsafe_allow_html=True)

    for _, row in df_v.iterrows():
        idx  = int(row["_idx"])
        cols = st.columns(cols_w)
        cols[0].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{row.get("Codigo","—")}</div>', unsafe_allow_html=True)
        cols[1].markdown(f'<div style="font-size:13px;color:#EEF2F8;font-weight:500;padding-top:8px;">{row.get("Modelo","—")}</div>', unsafe_allow_html=True)
        cols[2].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Nome_Revenda","—")}</div>', unsafe_allow_html=True)
        cols[3].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{row.get("Data_Envio","—")}</div>', unsafe_allow_html=True)
        cols[4].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{row.get("Data_Retorno_Prevista","—")}</div>', unsafe_allow_html=True)
        cols[5].markdown(f'<div style="padding-top:4px;">{_badge_condicao(str(row.get("Condicao","—")))}</div>', unsafe_allow_html=True)
        preco = row.get("Preco_Lista", 0)
        cols[6].markdown(f'<div style="font-size:13px;color:#F0F4F8;font-weight:600;padding-top:8px;">{formatar_brl(float(preco or 0))}</div>', unsafe_allow_html=True)
        cols[7].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{str(row.get("Observacao","—")) or "—"}</div>', unsafe_allow_html=True)
        if cols[8].button("🗑", key=f"del_rev_{idx}", help="Remover"):
            if _excluir_revenda(idx):
                st.toast("Registro removido.", icon="🗑")
                st.rerun()
        st.markdown('<div class="tbl-div"></div>', unsafe_allow_html=True)
    st.caption(f"Total: {len(df_rev)} máquina(s) em revendas.")

# ─────────────────────────────────────────────────────────────────────────────
# Exportação para Excel
# ─────────────────────────────────────────────────────────────────────────────

def _exportar_excel():
    _init_session()
    pat = st.session_state.estoque_patio
    rev = st.session_state.estoque_revendas

    rows = []
    for p in pat:
        rows.append({
            "CÓD PRODUTO": p.get("Codigo"),
            "TIPO": p.get("Tipo"),
            "DESCRIÇÃO": p.get("Descricao"),
            "MODELOS": p.get("Modelo"),
            "ANO": p.get("Ano"),
            "NOME": p.get("Nome"),
            "GS": p.get("GS"),
            "CONFIGURAÇÕES": p.get("Configuracoes"),
            "CONDIÇÃO DA MÁQUINA": p.get("Condicao"),
            "Custo 120": p.get("Custo"),
            "Preço de Lista (atual)": p.get("Preco_Lista"),
            "Observação": p.get("Observacao"),
            "Localizacao": "Pátio",
        })
    for r in rev:
        rows.append({
            "CÓD PRODUTO": r.get("Codigo"),
            "TIPO": r.get("Tipo"),
            "DESCRIÇÃO": r.get("Descricao"),
            "MODELOS": r.get("Modelo"),
            "ANO": r.get("Ano"),
            "NOME": r.get("Nome"),
            "GS": r.get("GS"),
            "CONFIGURAÇÕES": r.get("Configuracoes"),
            "CONDIÇÃO DA MÁQUINA": r.get("Condicao"),
            "Custo 120": r.get("Custo"),
            "Preço de Lista (atual)": r.get("Preco_Lista"),
            "Observação": r.get("Observacao"),
            "Localizacao": r.get("Nome_Revenda"),
        })

    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="7,2%", index=False)
        pd.DataFrame().to_excel(writer, sheet_name="Base Calculo", index=False)
    return output.getvalue()

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

    _init_session()
    _kpis_estoque()
    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)

    excel_data = _exportar_excel()
    st.download_button(
        label="📥 Exportar para Excel",
        data=excel_data,
        file_name=f"estoque_genius_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="estoque_export_btn",
    )

    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)

    sub1, sub2 = st.tabs(["🏭 Pátio Próprio", "🚛 Máquinas em Revendas"])

    with sub1:
        _form_patio()
        st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)
        _section("📋 Equipamentos no Pátio")
        _tabela_patio()

    with sub2:
        _form_revenda()
        st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)
        _section("📋 Equipamentos em Revendas")
        _tabela_revendas()
