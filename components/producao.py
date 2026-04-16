"""
components/producao.py — Genius Plantadeiras v13
Persistência via Supabase (genius_producao).
A tabela retorna 'id' em cada linha; usamos esse id para excluir corretamente.
"""

from __future__ import annotations
from datetime import date

import pandas as pd
import streamlit as st

from data.db import (
    ler_producao, adicionar_producao, excluir_producao,
    importar_producao, exportar_producao, calcular_kpis_producao,
)
from data.loader_estoque import STATUS_PROD

# ── Paleta ────────────────────────────────────────────────────
ORG  = "#D4651E"; GRN  = "#3D9970"; GRN2 = "#52B788"
BLU2 = "#2A5A8A"; YEL  = "#E8A020"; RED  = "#E84040"
T1   = "#EEF2F8"; T2   = "#A8B8CC"; T3   = "#6A7A8A"

_STATUS_PROD_CORES = {
    "Aguardando":  {"dot": YEL,  "text": "#E8C040"},
    "Em Produção": {"dot": ORG,  "text": "#F08040"},
    "Pronto":      {"dot": GRN,  "text": GRN2},
    "Entregue":    {"dot": BLU2, "text": "#7AAFD4"},
    "Cancelado":   {"dot": RED,  "text": "#E87878"},
}
_DEF_PROD = {"dot": T3, "text": T2}

_CSS = """
<style>
.pcp-sec{font-size:11px;font-weight:700;color:#3A4858;text-transform:uppercase;
  letter-spacing:.1em;border-bottom:1px solid #30394A;padding-bottom:6px;margin-bottom:14px;}
.tbl-hdr-p{font-size:10px;font-weight:700;color:#3A4858;text-transform:uppercase;
  letter-spacing:.08em;padding-bottom:6px;border-bottom:1px solid #2D3748;}
.tbl-div-p{border-bottom:1px solid rgba(45,55,72,.5);margin:3px 0;}
</style>
"""


def _sec(t):
    st.markdown(f'<div class="pcp-sec">{t}</div>', unsafe_allow_html=True)


def _badge_prod(status: str) -> str:
    c = _STATUS_PROD_CORES.get(status, _DEF_PROD)
    return (f'<span style="display:inline-flex;align-items:center;gap:5px;'
            f'color:{c["text"]};font-size:12px;font-weight:600;">'
            f'<span style="width:8px;height:8px;border-radius:50%;'
            f'background:{c["dot"]};"></span>{status}</span>')


def _kpis_producao(kpis: dict):
    c1, c2, c3, c4, c5 = st.columns(5, gap="medium")
    c1.metric("📋 Total",        kpis["total"])
    c2.metric("🔧 Em Produção",  kpis["em_producao"])
    c3.metric("✅ Prontos",       kpis["prontos"])
    c4.metric("🚚 Entregues",    kpis["entregues"])
    c5.metric("⚠️ Atrasados",    kpis["atrasados"])
    if kpis["ciclo_medio_dias"] > 0:
        st.caption(f"⏱️ Ciclo médio de produção: **{kpis['ciclo_medio_dias']:.1f} dias**")


def _tabela_producao(df: pd.DataFrame):
    if df.empty:
        st.info("Nenhuma máquina em produção cadastrada.")
        return

    hoje = pd.Timestamp(date.today())

    # O Supabase devolve 'id' em cada linha — preservamos para deleção
    df_v = df.copy()
    if "id" not in df_v.columns:
        df_v["id"] = range(len(df_v))   # fallback caso não haja id

    cols_w = [1.5, 1.5, 1.2, 0.9, 0.9, 1.0, 0.9, 1.1, 2.0, 0.4]
    hdr = st.columns(cols_w)
    for c, lbl in zip(hdr, [
        "Equipamento", "Cliente", "Representante", "Dt. Pedido",
        "Ini. Produção", "Prev. Entrega", "Entrega Real",
        "Status", "Observações", "",
    ]):
        c.markdown(f'<div class="tbl-hdr-p">{lbl}</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    for _, row in df_v.iterrows():
        row_id = row.get("id")
        status = str(row.get("Status_Producao", ""))

        prev = pd.to_datetime(row.get("Data_Entrega_Prevista", ""), errors="coerce", dayfirst=True)
        atrasado = (pd.notna(prev) and prev < hoje and
                    status not in ("Entregue", "Cancelado"))

        cols = st.columns(cols_w)
        cols[0].markdown(f'<div style="font-size:13px;color:#EEF2F8;font-weight:500;padding-top:8px;">{row.get("Equipamento","—")}</div>', unsafe_allow_html=True)
        cols[1].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Cliente","—")}</div>', unsafe_allow_html=True)
        cols[2].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Representante","—")}</div>', unsafe_allow_html=True)
        cols[3].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{row.get("Data_Pedido","—")}</div>', unsafe_allow_html=True)
        cols[4].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{row.get("Data_Inicio_Producao","—")}</div>', unsafe_allow_html=True)

        prev_txt = row.get("Data_Entrega_Prevista", "—")
        cor_prev = "#E84040" if atrasado else "#6A7A8A"
        cols[5].markdown(f'<div style="font-size:12px;color:{cor_prev};padding-top:8px;font-weight:{"700" if atrasado else "400"}">{"⚠️ " if atrasado else ""}{prev_txt}</div>', unsafe_allow_html=True)
        cols[6].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{row.get("Data_Entrega_Real","—")}</div>', unsafe_allow_html=True)
        cols[7].markdown(f'<div style="padding-top:4px;">{_badge_prod(status)}</div>', unsafe_allow_html=True)

        obs = str(row.get("Observacoes", "")) if pd.notna(row.get("Observacoes", "")) else "—"
        cols[8].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{obs}</div>', unsafe_allow_html=True)

        if cols[9].button("🗑", key=f"del_prod_{row_id}", help="Remover"):
            if excluir_producao(row_id):
                st.toast("Registro removido.", icon="🗑")
                st.rerun()

        st.markdown('<div class="tbl-div-p"></div>', unsafe_allow_html=True)

    atrasado_count = sum(
        1 for _, r in df_v.iterrows()
        if pd.notna(pd.to_datetime(r.get("Data_Entrega_Prevista", ""), errors="coerce", dayfirst=True))
        and pd.to_datetime(r.get("Data_Entrega_Prevista", ""), errors="coerce", dayfirst=True) < hoje
        and str(r.get("Status_Producao", "")) not in ("Entregue", "Cancelado")
    )
    if atrasado_count:
        st.warning(f"⚠️ {atrasado_count} máquina(s) com previsão de entrega vencida.")
    st.caption(f"Total: {len(df)} registro(s).")


def _form_producao():
    _sec("➕ Lançar Máquina em Produção")
    with st.expander("Preencher formulário", expanded=False):
        c1, c2, c3 = st.columns(3, gap="medium")
        with c1:
            equip = st.text_input("Equipamento", key="prod_eq", placeholder="Ex: GATA 18050")
            cli   = st.text_input("Cliente",     key="prod_cli", placeholder="Nome do cliente")
        with c2:
            rep   = st.text_input("Representante", key="prod_rep", placeholder="Nome do vendedor")
            dt_p  = st.date_input("Data do Pedido", value=date.today(), format="DD/MM/YYYY", key="prod_dtp")
        with c3:
            dt_i  = st.date_input("Início Produção", value=date.today(), format="DD/MM/YYYY", key="prod_dti")
            dt_pr = st.date_input("Previsão Entrega", value=date.today(), format="DD/MM/YYYY", key="prod_dtpr")

        c4, c5 = st.columns([1, 2])
        with c4:
            st_p = st.selectbox("Status", STATUS_PROD, key="prod_st")
        with c5:
            obs  = st.text_area("Observações", key="prod_obs", height=70)

        if st.button("Salvar em Produção", type="primary", use_container_width=True, key="prod_salvar"):
            if not equip.strip():
                st.toast("⚠️ Equipamento é obrigatório.", icon="🚫")
            else:
                reg = {
                    "Equipamento":           equip.strip(),
                    "Cliente":               cli.strip(),
                    "Representante":         rep.strip(),
                    "Data_Pedido":           dt_p.strftime("%d/%m/%Y"),
                    "Data_Inicio_Producao":  dt_i.strftime("%d/%m/%Y"),
                    "Data_Entrega_Prevista": dt_pr.strftime("%d/%m/%Y"),
                    "Data_Entrega_Real":     "",
                    "Status_Producao":       st_p,
                    "Observacoes":           obs.strip(),
                }
                if adicionar_producao(reg):
                    st.toast("✅ Máquina adicionada ao ciclo de produção!", icon="✅")
                    st.rerun()


def render_aba_pcp(df_maq=None):
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown("""
<div style="display:flex;align-items:center;gap:14px;padding:10px 0 18px;
            border-bottom:1px solid #2D3748;margin-bottom:24px;">
  <div style="background:rgba(227,108,44,.14);border:1px solid rgba(227,108,44,.4);
              border-radius:10px;padding:10px 14px;font-size:22px;">🏭</div>
  <div>
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:1.9rem;
                font-weight:700;color:#F0F4F8;line-height:1.1;">
      PCP — Ciclo de Produção</div>
    <div style="font-size:12px;color:#6A7A8A;text-transform:uppercase;
                letter-spacing:.07em;margin-top:4px;">
      Controle de Máquinas em Produção · Lead Time · Semáforo de Prazo</div>
  </div>
</div>
""", unsafe_allow_html=True)

    df_prod = ler_producao()
    kpis_p  = calcular_kpis_producao(df_prod)

    _kpis_producao(kpis_p)
    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)

    col_imp, col_exp = st.columns([2, 1], gap="medium")
    with col_imp:
        up = st.file_uploader("📥 Importar planilha de produção (Excel/CSV)",
                              type=["csv", "xlsx"], key="prod_up",
                              label_visibility="collapsed")
        if up:
            with st.spinner("Importando..."):
                n, msg = importar_producao(up)
            if msg == "OK":
                st.toast(f"✅ {n} linha(s) importadas!", icon="✅")
                st.rerun()

    with col_exp:
        if not df_prod.empty:
            st.download_button(
                "📤 Exportar Produção (.xlsx)",
                data=exportar_producao(),
                file_name="ciclo_producao.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="prod_exp",
            )

    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)
    _form_producao()
    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)
    _sec("📋 Máquinas em Produção")
    _tabela_producao(df_prod)
