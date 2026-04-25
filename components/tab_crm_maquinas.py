"""
components/tab_crm_maquinas.py — Pipeline CRM de Máquinas v1

Pipeline visual com estágios de negociação:
  Em Negociação → Proposta Enviada → Em Aprovação → Ganho → Perdido

Funcionalidades:
  - Kanban/Pipeline por estágio
  - Cadastro de oportunidades com valor, cliente, representante
  - Followup com data e observações
  - Histórico de movimentações
  - KPIs: total pipeline, taxa de conversão, ticket médio
"""

from __future__ import annotations
from datetime import date, datetime
import pandas as pd
import streamlit as st
from data.db import (
    ler_producao, adicionar_producao, excluir_producao,
    atualizar_producao_campo, calcular_kpis_producao,
)

# Estágios do pipeline
ESTAGIOS = [
    "Em Negociação",
    "Proposta Enviada",
    "Em Aprovação",
    "Ganho",
    "Perdido",
]

CORES_ESTAGIO = {
    "Em Negociação":  ("#E8A020", "rgba(232,160,32,.15)"),
    "Proposta Enviada": ("#2A5A8A", "rgba(42,90,138,.15)"),
    "Em Aprovação":   ("#9B59B6", "rgba(155,89,182,.15)"),
    "Ganho":          ("#3D9970", "rgba(61,153,112,.15)"),
    "Perdido":        ("#E84040", "rgba(232,64,64,.15)"),
}

_CSS = """
<style>
.crm-card{border-radius:10px;padding:12px 14px;margin-bottom:8px;
  border:1px solid rgba(255,255,255,.08);cursor:default;}
.crm-label{font-size:10px;font-weight:700;text-transform:uppercase;
  letter-spacing:.08em;margin-bottom:8px;}
.crm-equip{font-size:13px;font-weight:600;color:#EEF2F8;margin-bottom:3px;}
.crm-cli{font-size:11px;color:#A8B8CC;margin-bottom:3px;}
.crm-val{font-size:14px;font-weight:700;color:#F0A84E;}
.crm-data{font-size:10px;color:#6A7A8A;margin-top:4px;}
</style>
"""


def _brl(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def _parse_brl(s: str) -> float:
    try:
        s = s.strip().replace("R$", "").replace(" ", "")
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        return float(s)
    except Exception:
        return 0.0


def _kpis_pipeline(df: pd.DataFrame):
    """KPIs do pipeline."""
    if df is None or df.empty:
        c1,c2,c3,c4,c5 = st.columns(5)
        for c,l,v in zip([c1,c2,c3,c4,c5],
            ["📋 Total","💰 Pipeline Ativo","✅ Ganhos","❌ Perdidos","🎯 Conversão"],
            ["0","R$ 0,00","0","0","0%"]):
            c.metric(l, v)
        return

    status = df.get("Status", df.get("Status_Producao", pd.Series(dtype=str))).astype(str)
    valor  = pd.to_numeric(df.get("Valor", df.get("Valor_Total", pd.Series(dtype=float))),
                           errors="coerce").fillna(0)

    ativos  = status.isin(["Em Negociação","Proposta Enviada","Em Aprovação"])
    ganhos  = (status == "Ganho")
    perdidos= (status == "Perdido")
    total   = len(df)

    pipeline_val = valor[ativos].sum()
    n_ganhos     = int(ganhos.sum())
    n_perdidos   = int(perdidos.sum())
    n_fechados   = n_ganhos + n_perdidos
    taxa         = f"{n_ganhos/n_fechados*100:.0f}%" if n_fechados > 0 else "—"

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("📋 Total Oportunidades", total)
    c2.metric("💰 Pipeline Ativo",      _brl(pipeline_val))
    c3.metric("✅ Ganhos",              n_ganhos)
    c4.metric("❌ Perdidos",            n_perdidos)
    c5.metric("🎯 Taxa de Conversão",   taxa)


def _form_nova_oportunidade():
    """Formulário para cadastrar nova oportunidade."""
    with st.expander("➕ Nova Oportunidade", expanded=False):
        with st.form("form_crm_maq", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                equip = st.text_input("Equipamento / Modelo *", placeholder="Ex: GATA 18050")
                cli   = st.text_input("Cliente / Revenda *",    placeholder="Nome da revenda")
            with c2:
                rep   = st.text_input("Representante",          placeholder="Nome do vendedor")
                valor_txt = st.text_input("Valor Estimado (R$)", placeholder="Ex: 250.000,00")
            with c3:
                estagio = st.selectbox("Estágio", ESTAGIOS[:3])  # Só estágios ativos no cadastro
                dt_followup = st.date_input("Data de Followup", value=None,
                                            format="DD/MM/YYYY")
            obs = st.text_area("Observações / Próximo Passo", height=70)
            salvar = st.form_submit_button("💾 Salvar Oportunidade", type="primary",
                                           use_container_width=True)

            if salvar:
                if not equip.strip():
                    st.toast("⚠️ Equipamento é obrigatório.", icon="🚫")
                elif not cli.strip():
                    st.toast("⚠️ Cliente é obrigatório.", icon="🚫")
                else:
                    valor = _parse_brl(valor_txt)
                    reg = {
                        "Equipamento":           equip.strip(),
                        "Cliente":               cli.strip(),
                        "Representante":         rep.strip(),
                        "Data_Pedido":           date.today().strftime("%d/%m/%Y"),
                        "Data_Inicio_Producao":  "",
                        "Data_Entrega_Prevista": dt_followup.strftime("%d/%m/%Y") if dt_followup else "",
                        "Data_Entrega_Real":     "",
                        "Status_Producao":       estagio,
                        "Valor":                 valor,
                        "Observacoes":           obs.strip(),
                    }
                    if adicionar_producao(reg):
                        st.toast(f"✅ Oportunidade '{equip}' criada!", icon="✅")
                        st.rerun()


def _pipeline_kanban(df: pd.DataFrame):
    """Visão Kanban do pipeline."""
    st.markdown("### 🗂️ Pipeline de Negociações")

    # Filtra só estágios ativos (não Ganho/Perdido)
    estagios_ativos = ["Em Negociação", "Proposta Enviada", "Em Aprovação"]
    cols = st.columns(3)

    status_col = df.get("Status_Producao", df.get("Status", pd.Series(dtype=str))).astype(str)

    for col, estagio in zip(cols, estagios_ativos):
        cor_txt, cor_bg = CORES_ESTAGIO[estagio]
        df_est = df[status_col == estagio]
        total_val = pd.to_numeric(
            df_est.get("Valor", df_est.get("Valor_Total", pd.Series())), errors="coerce"
        ).fillna(0).sum()

        with col:
            st.markdown(
                f'<div style="background:{cor_bg};border:1px solid {cor_txt}40;'
                f'border-radius:10px;padding:10px 12px;margin-bottom:12px;">'
                f'<div class="crm-label" style="color:{cor_txt};">{estagio}</div>'
                f'<div style="font-size:11px;color:#A8B8CC;">'
                f'{len(df_est)} oportunidade(s) · {_brl(total_val)}</div></div>',
                unsafe_allow_html=True
            )

            if df_est.empty:
                st.caption("Nenhuma oportunidade neste estágio.")
            else:
                for _, row in df_est.iterrows():
                    row_id   = int(row.get("id", 0))
                    equip    = str(row.get("Equipamento", "—"))
                    cli      = str(row.get("Cliente", "—"))
                    rep      = str(row.get("Representante", "—"))
                    valor    = float(row.get("Valor", row.get("Valor_Total", 0)) or 0)
                    followup = str(row.get("Data_Entrega_Prevista", "") or "")
                    obs      = str(row.get("Observacoes", "") or "")

                    with st.container():
                        st.markdown(
                            f'<div class="crm-card" style="background:{cor_bg};'
                            f'border-color:{cor_txt}30;">'
                            f'<div class="crm-equip">{equip}</div>'
                            f'<div class="crm-cli">👤 {cli}</div>'
                            f'<div class="crm-cli">🤝 {rep}</div>'
                            f'<div class="crm-val">{_brl(valor)}</div>'
                            + (f'<div class="crm-data">📅 Followup: {followup}</div>' if followup else '')
                            + (f'<div class="crm-data">📝 {obs[:60]}{"..." if len(obs)>60 else ""}</div>' if obs else '')
                            + '</div>',
                            unsafe_allow_html=True
                        )

                        # Ações inline
                        col_st, col_del = st.columns([3, 1])
                        novo_st = col_st.selectbox(
                            "", ESTAGIOS, index=ESTAGIOS.index(estagio),
                            key=f"crm_st_{row_id}", label_visibility="collapsed"
                        )
                        if novo_st != estagio:
                            atualizar_producao_campo(row_id, "Status_Producao", novo_st)
                            if novo_st == "Ganho":
                                atualizar_producao_campo(
                                    row_id, "Data_Entrega_Real",
                                    date.today().strftime("%d/%m/%Y")
                                )
                            st.rerun()

                        if col_del.button("🗑", key=f"crm_del_{row_id}"):
                            if excluir_producao(row_id):
                                st.toast("Removido.", icon="🗑")
                                st.rerun()

                        st.markdown("---")


def _pipeline_lista(df: pd.DataFrame):
    """Visão lista completa do pipeline."""
    st.markdown("### 📋 Todas as Oportunidades")

    # Filtros
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        est_sel = st.multiselect("Estágio", ESTAGIOS, default=ESTAGIOS[:3], key="crm_est_fil")
    with c2:
        busca = st.text_input("🔍 Buscar", placeholder="cliente ou equipamento", key="crm_busca")
    with c3:
        rep_opts = ["Todos"] + sorted(df.get("Representante", pd.Series()).dropna().unique().tolist())
        rep_sel = st.selectbox("Representante", rep_opts, key="crm_rep_fil")

    status_col = df.get("Status_Producao", df.get("Status", pd.Series(dtype=str))).astype(str)
    df_show = df[status_col.isin(est_sel)] if est_sel else df

    if busca.strip():
        mask = (
            df_show.get("Equipamento", pd.Series()).astype(str).str.contains(busca, case=False, na=False)
            | df_show.get("Cliente", pd.Series()).astype(str).str.contains(busca, case=False, na=False)
        )
        df_show = df_show[mask]

    if rep_sel != "Todos":
        df_show = df_show[df_show.get("Representante", pd.Series()).astype(str) == rep_sel]

    if df_show.empty:
        st.info("Nenhuma oportunidade encontrada.")
        return

    cols_w = [1.5, 1.5, 1.2, 1.0, 1.2, 1.5, 1.5, 0.4]
    hdr = st.columns(cols_w)
    for c, l in zip(hdr, ["Equipamento","Cliente","Representante","Valor","Estágio","Followup","Observações",""]):
        c.markdown(f'<div style="font-size:10px;font-weight:700;color:#3A4858;'
                   f'text-transform:uppercase;">{l}</div>', unsafe_allow_html=True)

    for _, row in df_show.iterrows():
        row_id = int(row.get("id", 0))
        estagio_atual = str(row.get("Status_Producao", row.get("Status", "Em Negociação")))
        cor_txt, _ = CORES_ESTAGIO.get(estagio_atual, ("#A8B8CC","rgba(0,0,0,0)"))
        cols = st.columns(cols_w)
        cols[0].markdown(f'<div style="font-size:12px;color:#EEF2F8;padding-top:8px;">{row.get("Equipamento","—")}</div>', unsafe_allow_html=True)
        cols[1].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Cliente","—")}</div>', unsafe_allow_html=True)
        cols[2].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Representante","—")}</div>', unsafe_allow_html=True)
        cols[3].markdown(f'<div style="font-size:12px;color:#F0A84E;padding-top:8px;font-weight:600;">{_brl(row.get("Valor",0))}</div>', unsafe_allow_html=True)
        cols[4].markdown(f'<div style="font-size:11px;color:{cor_txt};padding-top:8px;font-weight:600;">{estagio_atual}</div>', unsafe_allow_html=True)
        cols[5].markdown(f'<div style="font-size:11px;color:#6A7A8A;padding-top:8px;">{row.get("Data_Entrega_Prevista","") or "—"}</div>', unsafe_allow_html=True)
        obs = str(row.get("Observacoes","") or "")
        cols[6].markdown(f'<div style="font-size:11px;color:#A8B8CC;padding-top:8px;">{obs[:40]}{"..." if len(obs)>40 else ""}</div>', unsafe_allow_html=True)
        if cols[7].button("🗑", key=f"crm_list_del_{row_id}"):
            if excluir_producao(row_id):
                st.toast("Removido.", icon="🗑")
                st.rerun()
        st.markdown('<div style="border-bottom:1px solid rgba(45,55,72,.4);margin:2px 0;"></div>', unsafe_allow_html=True)

    # Export
    csv = df_show.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button("📥 Exportar (.csv)", data=csv,
                       file_name=f"pipeline_maquinas_{date.today()}.csv",
                       mime="text/csv", key="dl_crm")


def _metricas_historico(df: pd.DataFrame):
    """Métricas e histórico de fechamentos."""
    st.markdown("### 📊 Histórico & Métricas")

    status_col = df.get("Status_Producao", df.get("Status", pd.Series(dtype=str))).astype(str)
    valor_col  = pd.to_numeric(
        df.get("Valor", df.get("Valor_Total", pd.Series())), errors="coerce"
    ).fillna(0)

    ganhos  = df[status_col == "Ganho"]
    perdidos= df[status_col == "Perdido"]

    c1, c2, c3 = st.columns(3)
    val_ganhos = valor_col[status_col == "Ganho"].sum()
    val_perdidos = valor_col[status_col == "Perdido"].sum()
    ticket = float(valor_col[status_col == "Ganho"].mean()) if not ganhos.empty else 0

    c1.metric("💰 Total Ganho",     _brl(val_ganhos))
    c2.metric("💸 Total Perdido",   _brl(val_perdidos))
    c3.metric("🎟️ Ticket Médio",    _brl(ticket))

    if not ganhos.empty:
        st.markdown("**✅ Negócios Ganhos**")
        cols_w = [2, 2, 1.5, 1.5]
        hdr = st.columns(cols_w)
        for c, l in zip(hdr, ["Equipamento","Cliente","Valor","Data Fechamento"]):
            c.markdown(f'<div style="font-size:10px;font-weight:700;color:#3A4858;">{l}</div>', unsafe_allow_html=True)
        for _, row in ganhos.iterrows():
            cols = st.columns(cols_w)
            cols[0].markdown(f'<div style="font-size:12px;color:#3D9970;padding-top:6px;">{row.get("Equipamento","—")}</div>', unsafe_allow_html=True)
            cols[1].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:6px;">{row.get("Cliente","—")}</div>', unsafe_allow_html=True)
            cols[2].markdown(f'<div style="font-size:12px;color:#F0A84E;padding-top:6px;font-weight:600;">{_brl(row.get("Valor",0))}</div>', unsafe_allow_html=True)
            cols[3].markdown(f'<div style="font-size:11px;color:#6A7A8A;padding-top:6px;">{row.get("Data_Entrega_Real","") or "—"}</div>', unsafe_allow_html=True)
            st.markdown('<div style="border-bottom:1px solid rgba(45,55,72,.3);margin:2px 0;"></div>', unsafe_allow_html=True)


def render_aba_crm_maquinas():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown("""
<div style="display:flex;align-items:center;gap:14px;padding:10px 0 18px;
            border-bottom:1px solid #2D3748;margin-bottom:24px;">
  <div style="background:rgba(227,108,44,.14);border:1px solid rgba(227,108,44,.4);
              border-radius:10px;padding:10px 14px;font-size:22px;">🤝</div>
  <div>
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:1.9rem;
                font-weight:700;color:#F0F4F8;line-height:1.1;">
      Pipeline CRM — Máquinas</div>
    <div style="font-size:12px;color:#6A7A8A;text-transform:uppercase;
                letter-spacing:.07em;margin-top:4px;">
      Negociações · Followup · Conversão · Histórico</div>
  </div>
</div>""", unsafe_allow_html=True)

    df = ler_producao()

    # KPIs
    _kpis_pipeline(df)
    st.divider()

    # Nova oportunidade
    _form_nova_oportunidade()
    st.divider()

    # Tabs: Kanban | Lista | Histórico
    tab_kanban, tab_lista, tab_hist = st.tabs([
        "🗂️ Pipeline Visual",
        "📋 Lista Completa",
        "📊 Histórico & Métricas",
    ])

    with tab_kanban:
        _pipeline_kanban(df)

    with tab_lista:
        _pipeline_lista(df)

    with tab_hist:
        _metricas_historico(df)
