"""
components/producao.py — Genius Plantadeiras v15 (CORRIGIDO)

Correções aplicadas:
  [FIX-SYNTAX]  from datetime import datetime movido para ANTES do docstring
  [FIX-BUG-1]  Loop de rerun infinito eliminado: edições de data e status agora
               usam st.session_state como debounce — só salva e rerun quando o valor
               realmente mudou EM RELAÇÃO AO ESTADO ANTERIOR JÁ PERSISTIDO.
               Registros com Data_Entrega_Prevista vazia não disparam rerun.
  [FIX-PERF-4] Tabela isolada com @st.fragment (Streamlit >= 1.37) para reruns
               parciais — evita redesenho de toda a página a cada edição de célula.
               Fallback automático para versões anteriores do Streamlit.
"""

from __future__ import annotations
from datetime import date, datetime
import pandas as pd
import streamlit as st
from data.db import (
    ler_producao, adicionar_producao, excluir_producao,
    atualizar_producao_campo, importar_producao,
    exportar_producao, calcular_kpis_producao,
)
from data.loader_estoque import STATUS_PROD

ORG="#D4651E"; GRN="#3D9970"; GRN2="#52B788"; BLU2="#2A5A8A"
YEL="#E8A020"; RED="#E84040"; T1="#EEF2F8"; T2="#A8B8CC"; T3="#6A7A8A"

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


def _kpis(kpis):
    c1,c2,c3,c4,c5 = st.columns(5, gap="medium")
    c1.metric("📋 Total",       kpis["total"])
    c2.metric("🔧 Em Produção", kpis["em_producao"])
    c3.metric("✅ Prontos",      kpis["prontos"])
    c4.metric("🚚 Entregues",   kpis["entregues"])
    c5.metric("⚠️ Atrasados",   kpis["atrasados"])
    if kpis["ciclo_medio_dias"] > 0:
        st.caption(f"⏱️ Ciclo médio: **{kpis['ciclo_medio_dias']:.1f} dias**")


def _tabela_inner(df: pd.DataFrame):
    """
    Conteúdo da tabela — chamado dentro de @st.fragment quando disponível.
    [FIX-BUG-1] Debounce via session_state: compara valor novo com snapshot
    armazenado antes de salvar + rerun, impedindo loop infinito.
    """
    if df.empty:
        st.info("Nenhuma máquina em produção cadastrada.")
        return

    hoje = pd.Timestamp(date.today())

    # Snapshot dos valores atuais para comparação de debounce
    if "_prod_snapshot" not in st.session_state:
        st.session_state["_prod_snapshot"] = {}

    cols_w = [1.4, 1.4, 1.0, 0.8, 1.3, 1.3, 1.1, 1.8, 0.4]
    hdr = st.columns(cols_w)
    for c, lbl in zip(hdr, [
        "Equipamento","Cliente","Representante","Dt. Pedido",
        "Prev. Entrega ✏️","Entrega Real","Status ✏️","Observações",""
    ]):
        c.markdown(f'<div class="tbl-hdr-p">{lbl}</div>', unsafe_allow_html=True)

    for _, row in df.iterrows():
        row_id = int(row.get("id", 0))
        status = str(row.get("Status_Producao",""))
        prev   = pd.to_datetime(row.get("Data_Entrega_Prevista",""), errors="coerce", dayfirst=True)

        cols = st.columns(cols_w)
        cols[0].markdown(f'<div style="font-size:13px;color:#EEF2F8;font-weight:500;padding-top:8px;">{row.get("Equipamento","—")}</div>', unsafe_allow_html=True)
        cols[1].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Cliente","—")}</div>', unsafe_allow_html=True)
        cols[2].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Representante","—")}</div>', unsafe_allow_html=True)
        cols[3].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{row.get("Data_Pedido","—")}</div>', unsafe_allow_html=True)

        # ── Data de Entrega Prevista — editável com debounce ──
        prev_str = str(row.get("Data_Entrega_Prevista","")).strip()
        try:
            prev_val = pd.to_datetime(prev_str, dayfirst=True).date() if prev_str else date.today()
        except Exception:
            prev_val = date.today()

        nova_prev = cols[4].date_input(
            "", value=prev_val, format="DD/MM/YYYY",
            key=f"dt_prev_{row_id}", label_visibility="collapsed"
        )
        nova_prev_str = nova_prev.strftime("%d/%m/%Y")

        # [FIX-BUG-1] Só persiste se: (a) havia valor anterior E (b) mudou
        snap_key_dt = f"snap_dt_{row_id}"
        if st.session_state["_prod_snapshot"].get(snap_key_dt) != nova_prev_str:
            st.session_state["_prod_snapshot"][snap_key_dt] = nova_prev_str
            # Só salva se o campo já existia no banco (prev_str não vazio)
            if prev_str and nova_prev_str != prev_str:
                atualizar_producao_campo(row_id, "Data_Entrega_Prevista", nova_prev_str)
                st.rerun()

        cols[5].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{row.get("Data_Entrega_Real","") or "—"}</div>', unsafe_allow_html=True)

        # ── Status — editável com debounce ────────────────────
        idx_st = STATUS_PROD.index(status) if status in STATUS_PROD else 0
        novo_st = cols[6].selectbox(
            "", STATUS_PROD, index=idx_st,
            key=f"st_prod_{row_id}", label_visibility="collapsed"
        )

        snap_key_st = f"snap_st_{row_id}"
        if st.session_state["_prod_snapshot"].get(snap_key_st) != novo_st:
            st.session_state["_prod_snapshot"][snap_key_st] = novo_st
            if novo_st != status:
                atualizar_producao_campo(row_id, "Status_Producao", novo_st)
                if novo_st == "Entregue":
                    atualizar_producao_campo(row_id, "Data_Entrega_Real", date.today().strftime("%d/%m/%Y"))
                st.rerun()

        obs = str(row.get("Observacoes","")) if pd.notna(row.get("Observacoes","")) else "—"
        cols[7].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{obs}</div>', unsafe_allow_html=True)

        if cols[8].button("🗑", key=f"del_prod_{row_id}", help="Remover"):
            if excluir_producao(row_id):
                st.toast("Removido.", icon="🗑")
                st.session_state["_prod_snapshot"] = {}
                st.rerun()

        st.markdown('<div class="tbl-div-p"></div>', unsafe_allow_html=True)

    atrasados = sum(
        1 for _, r in df.iterrows()
        if pd.notna(pd.to_datetime(r.get("Data_Entrega_Prevista",""), errors="coerce", dayfirst=True))
        and pd.to_datetime(r.get("Data_Entrega_Prevista",""), errors="coerce", dayfirst=True) < hoje
        and str(r.get("Status_Producao","")) not in ("Entregue","Cancelado")
    )
    if atrasados:
        st.warning(f"⚠️ {atrasados} máquina(s) com previsão vencida.")
    st.caption(f"Total: {len(df)} registro(s).")


# [FIX-PERF-4] Tenta usar @st.fragment para reruns parciais (Streamlit >= 1.37)
try:
    @st.fragment
    def _tabela(df: pd.DataFrame):
        _tabela_inner(df)
except AttributeError:
    def _tabela(df: pd.DataFrame):
        _tabela_inner(df)


def _form():
    _sec("➕ Lançar Máquina em Produção")
    with st.expander("Preencher formulário", expanded=False):
        c1,c2,c3 = st.columns(3, gap="medium")
        with c1:
            equip = st.text_input("Equipamento", key="prod_eq", placeholder="Ex: GATA 18050")
            cli   = st.text_input("Cliente",     key="prod_cli")
        with c2:
            rep   = st.text_input("Representante", key="prod_rep")
            dt_p  = st.date_input("Data do Pedido", value=date.today(), format="DD/MM/YYYY", key="prod_dtp")
        with c3:
            dt_i  = st.date_input("Início Produção",  value=date.today(), format="DD/MM/YYYY", key="prod_dti")
            dt_pr = st.date_input("Previsão Entrega",  value=date.today(), format="DD/MM/YYYY", key="prod_dtpr")
        c4,c5 = st.columns([1,2])
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
                    st.toast("✅ Adicionado ao ciclo de produção!", icon="✅")
                    st.session_state["_prod_snapshot"] = {}
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
                font-weight:700;color:#F0F4F8;line-height:1.1;">PCP — Ciclo de Produção</div>
    <div style="font-size:12px;color:#6A7A8A;text-transform:uppercase;
                letter-spacing:.07em;margin-top:4px;">
      Controle · Lead Time · Semáforo de Prazo · Status editável na tabela</div>
  </div>
</div>""", unsafe_allow_html=True)

    df_prod = ler_producao()
    _kpis(calcular_kpis_producao(df_prod))
    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)

    col_imp, col_exp = st.columns([2,1])
    with col_imp:
        up = st.file_uploader("📥 Importar planilha (Excel/CSV)", type=["csv","xlsx"],
                               key="prod_up", label_visibility="collapsed")
        if up:
            with st.spinner("Importando..."):
                n, msg = importar_producao(up)
            if msg == "OK":
                st.toast(f"✅ {n} linha(s) importadas!", icon="✅")
                st.session_state["_prod_snapshot"] = {}
                st.rerun()
            else:
                st.error(f"❌ {msg}")
    with col_exp:
        if not df_prod.empty:
            st.download_button("📤 Exportar (.xlsx)", data=exportar_producao(),
                                file_name=f"ciclo_producao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True, key="prod_exp")

    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)
    _form()
    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)
    _sec("📋 Máquinas em Produção")
    _tabela(df_prod)
