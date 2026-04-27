"""
components/tab_crm_maquinas.py — Pipeline CRM de Máquinas v2 (REDESIGN)

Adaptado ao fluxo real da Genius Implementos Agrícolas:
  - Fluxo simplificado: Em Negociação → Fechado → Declinado
  - Follow-up com alerta visual de vencimento
  - Histórico de observações com data/autor
  - Motivo do declínio obrigatório
  - Painel de follow-ups do dia na abertura
  - Métricas reais: conversão, ticket médio, motivos de perda
"""

from __future__ import annotations
from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st
from data.db import (
    ler_producao, adicionar_producao, excluir_producao,
    atualizar_producao_campo, calcular_kpis_producao,
)

# ── Status simplificados ──────────────────────────────────────
STATUS = ["Em Negociação", "Fechado", "Declinado"]

CORES = {
    "Em Negociação": ("#E8A020", "rgba(232,160,32,.12)"),
    "Fechado":       ("#3D9970", "rgba(61,153,112,.12)"),
    "Declinado":     ("#E84040", "rgba(232,64,64,.12)"),
}

_CSS = """
<style>
.crm-card {
  border-radius: 10px; padding: 14px 16px; margin-bottom: 10px;
  border: 1px solid rgba(255,255,255,.07);
}
.crm-equip { font-size: 14px; font-weight: 600; color: #EEF2F8; margin-bottom: 4px; }
.crm-cli   { font-size: 12px; color: #A8B8CC; margin-bottom: 2px; }
.crm-val   { font-size: 15px; font-weight: 700; color: #F0A84E; margin: 6px 0 4px; }
.crm-obs   { font-size: 11px; color: #6A7A8A; margin-top: 4px; line-height: 1.5; }
.crm-badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 12px; font-size: 10px; font-weight: 700;
}
.followup-hoje {
  background: rgba(232,64,64,.12); border: 1px solid rgba(232,64,64,.3);
  border-radius: 10px; padding: 12px 16px; margin-bottom: 8px;
}
.followup-prox {
  background: rgba(232,160,32,.10); border: 1px solid rgba(232,160,32,.3);
  border-radius: 10px; padding: 12px 16px; margin-bottom: 8px;
}
.hist-item {
  border-left: 2px solid #2D3748; padding: 6px 0 6px 12px; margin-bottom: 6px;
}
.hist-data  { font-size: 10px; color: #3A4858; }
.hist-texto { font-size: 12px; color: #A8B8CC; }
</style>
"""


# ══════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════

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


def _dias_followup(data_str: str) -> int | None:
    """Retorna dias até o follow-up. Negativo = atrasado."""
    try:
        d = datetime.strptime(data_str.strip(), "%d/%m/%Y").date()
        return (d - date.today()).days
    except Exception:
        return None


def _get_status(row) -> str:
    return str(row.get("Status_Producao", row.get("Status", "Em Negociação")) or "Em Negociação")


def _get_valor(row) -> float:
    try:
        return float(row.get("Valor", row.get("Valor_Total", 0)) or 0)
    except Exception:
        return 0.0


# ══════════════════════════════════════════════════════════════
# Follow-up — apenas informativo, sem alerta automático
# ══════════════════════════════════════════════════════════════

def _painel_followups(df: pd.DataFrame):
    """Sem alerta automático — ciclo sazonal, follow-up é apenas informativo."""
    pass


# ══════════════════════════════════════════════════════════════
# KPIs
# ══════════════════════════════════════════════════════════════

def _kpis(df: pd.DataFrame):
    if df is None or df.empty:
        c1,c2,c3,c4,c5 = st.columns(5)
        for c,l,v in zip([c1,c2,c3,c4,c5],
            ["📋 Total","💰 Pipeline Ativo","✅ Fechados","❌ Declinados","🎯 Conversão"],
            ["0","R$ 0,00","0","0","—"]):
            c.metric(l,v)
        return

    status_col = df.apply(_get_status, axis=1)
    valor_col  = df.apply(_get_valor, axis=1)

    n_total    = len(df)
    n_ativos   = int((status_col == "Em Negociação").sum())
    n_fechados = int((status_col == "Fechado").sum())
    n_declin   = int((status_col == "Declinado").sum())
    pipeline   = valor_col[status_col == "Em Negociação"].sum()
    n_finalizados = n_fechados + n_declin
    conversao  = f"{n_fechados/n_finalizados*100:.0f}%" if n_finalizados > 0 else "—"

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("📋 Total",          n_total)
    c2.metric("💰 Pipeline Ativo", _brl(pipeline))
    c3.metric("✅ Fechados",        n_fechados)
    c4.metric("❌ Declinados",      n_declin)
    c5.metric("🎯 Conversão",       conversao)


# ══════════════════════════════════════════════════════════════
# Formulário — Nova Oportunidade
# ══════════════════════════════════════════════════════════════

def _form_nova_oportunidade():
    with st.expander("➕ Nova Oportunidade", expanded=False):
        with st.form("form_crm_v2", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                equip     = st.text_input("Equipamento / Modelo *", placeholder="Ex: GATA 18050")
                cliente   = st.text_input("Cliente / Revenda *",    placeholder="Nome da revenda")
                rep       = st.text_input("Representante",          placeholder="Nome do vendedor")
            with c2:
                valor_txt = st.text_input("Valor Estimado (R$)",    placeholder="Ex: 250.000,00")
                dt_fu     = st.date_input("Data do Follow-up",      value=None, format="DD/MM/YYYY")
                coordenador = st.text_input("Coordenador / Contato", placeholder="Quem passou o pedido")

            obs = st.text_area("Observações / Detalhes do Pedido", height=80,
                               placeholder="Modelo, configuração, prazo solicitado...")
            salvar = st.form_submit_button("💾 Salvar Oportunidade", type="primary",
                                           use_container_width=True)
            if salvar:
                if not equip.strip():
                    st.toast("⚠️ Equipamento é obrigatório.", icon="🚫")
                elif not cliente.strip():
                    st.toast("⚠️ Cliente é obrigatório.", icon="🚫")
                else:
                    valor = _parse_brl(valor_txt)
                    # Histórico inicial
                    autor = st.session_state.get("nome_usuario", "Sistema")
                    hist  = f"[{date.today().strftime('%d/%m/%Y')} - {autor}] Oportunidade criada."
                    if obs.strip():
                        hist += f" {obs.strip()}"

                    reg = {
                        "Equipamento":           equip.strip(),
                        "Cliente":               cliente.strip(),
                        "Representante":         rep.strip(),
                        "Data_Pedido":           date.today().strftime("%d/%m/%Y"),
                        "Data_Inicio_Producao":  coordenador.strip(),
                        "Data_Entrega_Prevista": dt_fu.strftime("%d/%m/%Y") if dt_fu else "",
                        "Data_Entrega_Real":     "",
                        "Status_Producao":       "Em Negociação",
                        "Valor":                 valor,
                        "Observacoes":           hist,
                    }
                    if adicionar_producao(reg):
                        st.toast(f"✅ '{equip}' adicionado ao pipeline!", icon="✅")
                        st.rerun()


# ══════════════════════════════════════════════════════════════
# Pipeline Visual (cards por status)
# ══════════════════════════════════════════════════════════════

def _pipeline_visual(df: pd.DataFrame):
    st.markdown("### 🗂️ Pipeline de Negociações")

    status_col = df.apply(_get_status, axis=1)
    df_ativos  = df[status_col == "Em Negociação"]

    # Só exibe "Em Negociação" no kanban — fechados/declinados vão para histórico
    cor_txt, cor_bg = CORES["Em Negociação"]
    total_val = df_ativos.apply(_get_valor, axis=1).sum()

    st.markdown(
        f'<div style="background:{cor_bg};border:1px solid {cor_txt}40;'
        f'border-radius:10px;padding:10px 14px;margin-bottom:16px;">'
        f'<span style="color:{cor_txt};font-size:11px;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:.08em;">Em Negociação</span>'
        f'<span style="color:#A8B8CC;font-size:11px;margin-left:10px;">'
        f'{len(df_ativos)} oportunidade(s) · {_brl(total_val)}</span></div>',
        unsafe_allow_html=True,
    )

    if df_ativos.empty:
        st.info("Nenhuma oportunidade em negociação.")
        return

    for _, row in df_ativos.iterrows():
        row_id  = int(row.get("id", 0))
        equip   = str(row.get("Equipamento", "—"))
        cliente = str(row.get("Cliente", "—"))
        rep     = str(row.get("Representante", "—"))
        coord   = str(row.get("Data_Inicio_Producao", "") or "")
        valor   = _get_valor(row)
        fu_str  = str(row.get("Data_Entrega_Prevista", "") or "")
        obs     = str(row.get("Observacoes", "") or "")
        dias_fu = _dias_followup(fu_str) if fu_str else None

        # Data follow-up (apenas informativo)
        if dias_fu is not None:
            if dias_fu < 0:
                fu_badge = f'<span class="crm-badge" style="background:rgba(232,64,64,.15);color:#E84040;">🔴 {abs(dias_fu)}d atraso</span>'
            elif dias_fu == 0:
                fu_badge = '<span class="crm-badge" style="background:rgba(232,64,64,.15);color:#E84040;">🔴 HOJE</span>'
            elif dias_fu <= 3:
                fu_badge = f'<span class="crm-badge" style="background:rgba(232,160,32,.15);color:#E8A020;">🟡 {dias_fu}d</span>'
            else:
                fu_badge = f'<span class="crm-badge" style="background:rgba(61,153,112,.12);color:#3D9970;">✅ {dias_fu}d</span>'
        else:
            fu_badge = '<span class="crm-badge" style="background:rgba(45,55,72,.5);color:#6A7A8A;">Sem followup</span>'

        st.markdown(
            f'<div class="crm-card" style="background:{cor_bg};border-color:{cor_txt}30;">'
            f'<div class="crm-equip">{equip}</div>'
            f'<div class="crm-cli">👤 {cliente}' + (f' · 📞 {coord}' if coord else '') + '</div>'
            f'<div class="crm-cli">🤝 {rep}</div>'
            f'<div class="crm-val">{_brl(valor)}</div>'
            f'<div style="margin:6px 0;">{fu_badge}</div>'
            + (f'<div class="crm-obs">{obs.split(chr(10))[-1][:80]}</div>' if obs else '')
            + '</div>',
            unsafe_allow_html=True,
        )

        # Ações
        col_obs, col_fu, col_st, col_del = st.columns([2, 2, 2, 0.5])

        # Adicionar observação / follow-up
        nova_obs = col_obs.text_input("", placeholder="Nova observação...",
                                       key=f"obs_input_{row_id}", label_visibility="collapsed")
        nova_fu  = col_fu.date_input("", value=None, format="DD/MM/YYYY",
                                      key=f"fu_input_{row_id}", label_visibility="collapsed")

        if col_obs.button("💬 Registrar", key=f"reg_obs_{row_id}", use_container_width=True):
            if nova_obs.strip():
                autor = st.session_state.get("nome_usuario", "Sistema")
                entrada = f"\n[{date.today().strftime('%d/%m/%Y')} - {autor}] {nova_obs.strip()}"
                novo_hist = obs + entrada
                atualizar_producao_campo(row_id, "Observacoes", novo_hist)
                if nova_fu:
                    atualizar_producao_campo(row_id, "Data_Entrega_Prevista",
                                             nova_fu.strftime("%d/%m/%Y"))
                st.toast("✅ Observação registrada!", icon="✅")
                st.rerun()
            else:
                st.toast("⚠️ Digite uma observação.", icon="🚫")

        # Mudar status
        novo_st = col_st.selectbox("", STATUS, index=0,
                                    key=f"st_{row_id}", label_visibility="collapsed")
        if novo_st != "Em Negociação":
            if novo_st == "Declinado":
                st.session_state[f"_declin_{row_id}"] = True
            else:
                atualizar_producao_campo(row_id, "Status_Producao", novo_st)
                atualizar_producao_campo(row_id, "Data_Entrega_Real",
                                         date.today().strftime("%d/%m/%Y"))
                autor = st.session_state.get("nome_usuario", "Sistema")
                entrada = f"\n[{date.today().strftime('%d/%m/%Y')} - {autor}] Status alterado para {novo_st}."
                atualizar_producao_campo(row_id, "Observacoes", obs + entrada)
                st.toast(f"✅ Movido para {novo_st}!", icon="✅")
                st.rerun()

        if col_del.button("🗑", key=f"del_{row_id}"):
            if excluir_producao(row_id):
                st.toast("Removido.", icon="🗑")
                st.rerun()

        # Modal de declínio
        if st.session_state.get(f"_declin_{row_id}"):
            with st.container():
                st.markdown(f"**Motivo do declínio — {equip}:**")
                motivo = st.text_area("", placeholder="Ex: Preço acima do orçamento, concorrente X...",
                                       key=f"motivo_{row_id}", height=70, label_visibility="collapsed")
                c_ok, c_cancel = st.columns(2)
                if c_ok.button("✅ Confirmar Declínio", key=f"ok_dec_{row_id}", type="primary"):
                    if motivo.strip():
                        autor = st.session_state.get("nome_usuario", "Sistema")
                        entrada = (f"\n[{date.today().strftime('%d/%m/%Y')} - {autor}] "
                                   f"DECLINADO. Motivo: {motivo.strip()}")
                        atualizar_producao_campo(row_id, "Status_Producao", "Declinado")
                        atualizar_producao_campo(row_id, "Data_Entrega_Real",
                                                 date.today().strftime("%d/%m/%Y"))
                        atualizar_producao_campo(row_id, "Observacoes", obs + entrada)
                        st.session_state.pop(f"_declin_{row_id}", None)
                        st.toast("Negócio declinado registrado.", icon="📝")
                        st.rerun()
                    else:
                        st.warning("Informe o motivo do declínio.")
                if c_cancel.button("Cancelar", key=f"cancel_dec_{row_id}"):
                    st.session_state.pop(f"_declin_{row_id}", None)
                    st.rerun()

        st.markdown('<div style="border-bottom:1px solid rgba(45,55,72,.3);margin:6px 0 10px;"></div>',
                    unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# Lista Completa
# ══════════════════════════════════════════════════════════════

def _lista_completa(df: pd.DataFrame):
    st.markdown("### 📋 Todas as Oportunidades")

    c1, c2, c3 = st.columns(3)
    with c1:
        st_sel = st.multiselect("Status", STATUS, default=STATUS, key="crm_st_fil")
    with c2:
        busca = st.text_input("🔍 Buscar", placeholder="cliente ou equipamento", key="crm_busca")
    with c3:
        reps = ["Todos"] + sorted(df.get("Representante", pd.Series()).dropna().unique().tolist())
        rep_sel = st.selectbox("Representante", reps, key="crm_rep")

    status_col = df.apply(_get_status, axis=1)
    df_show = df[status_col.isin(st_sel)] if st_sel else df

    if busca.strip():
        mask = (
            df_show.get("Equipamento", pd.Series()).astype(str).str.contains(busca, case=False, na=False)
            | df_show.get("Cliente",    pd.Series()).astype(str).str.contains(busca, case=False, na=False)
        )
        df_show = df_show[mask]
    if rep_sel != "Todos":
        df_show = df_show[df_show.get("Representante", pd.Series()).astype(str) == rep_sel]

    if df_show.empty:
        st.info("Nenhuma oportunidade encontrada.")
        return

    cols_w = [1.6, 1.5, 1.2, 1.0, 1.1, 1.3, 2.0, 0.4]
    hdr = st.columns(cols_w)
    for c, l in zip(hdr, ["Equipamento","Cliente","Representante","Valor","Status","Follow-up","Última Observação",""]):
        c.markdown(f'<div style="font-size:10px;font-weight:700;color:#3A4858;'
                   f'text-transform:uppercase;letter-spacing:.07em;padding-bottom:6px;'
                   f'border-bottom:1px solid #2D3748;">{l}</div>', unsafe_allow_html=True)

    for _, row in df_show.iterrows():
        row_id  = int(row.get("id", 0))
        st_row  = _get_status(row)
        cor_txt, _ = CORES.get(st_row, ("#A8B8CC", ""))
        obs     = str(row.get("Observacoes", "") or "")
        ultima_obs = obs.split("\n")[-1][:60] if obs else "—"
        fu_str  = str(row.get("Data_Entrega_Prevista", "") or "")

        cols = st.columns(cols_w)
        cols[0].markdown(f'<div style="font-size:12px;color:#EEF2F8;padding-top:8px;font-weight:500;">{row.get("Equipamento","—")}</div>', unsafe_allow_html=True)
        cols[1].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Cliente","—")}</div>', unsafe_allow_html=True)
        cols[2].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Representante","—")}</div>', unsafe_allow_html=True)
        cols[3].markdown(f'<div style="font-size:12px;color:#F0A84E;padding-top:8px;font-weight:600;">{_brl(_get_valor(row))}</div>', unsafe_allow_html=True)
        cols[4].markdown(f'<div style="font-size:11px;color:{cor_txt};padding-top:8px;font-weight:600;">{st_row}</div>', unsafe_allow_html=True)
        cols[5].markdown(f'<div style="font-size:11px;color:#6A7A8A;padding-top:8px;">{fu_str or "—"}</div>', unsafe_allow_html=True)
        cols[6].markdown(f'<div style="font-size:11px;color:#A8B8CC;padding-top:8px;">{ultima_obs}</div>', unsafe_allow_html=True)
        if cols[7].button("🗑", key=f"list_del_{row_id}"):
            if excluir_producao(row_id):
                st.toast("Removido.", icon="🗑")
                st.rerun()
        st.markdown('<div style="border-bottom:1px solid rgba(45,55,72,.3);margin:2px 0;"></div>', unsafe_allow_html=True)

    csv = df_show.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button("📥 Exportar (.csv)", data=csv,
                       file_name=f"pipeline_{date.today()}.csv",
                       mime="text/csv", key="dl_crm_v2")


# ══════════════════════════════════════════════════════════════
# Histórico & Métricas
# ══════════════════════════════════════════════════════════════

def _historico_metricas(df: pd.DataFrame):
    st.markdown("### 📊 Histórico & Métricas")

    status_col = df.apply(_get_status, axis=1)
    valor_col  = df.apply(_get_valor, axis=1)

    fechados  = df[status_col == "Fechado"]
    declinados= df[status_col == "Declinado"]

    val_fechados  = valor_col[status_col == "Fechado"].sum()
    val_declinados= valor_col[status_col == "Declinado"].sum()
    ticket = float(valor_col[status_col == "Fechado"].mean()) if not fechados.empty else 0.0
    n_fin  = len(fechados) + len(declinados)
    conv   = f"{len(fechados)/n_fin*100:.0f}%" if n_fin > 0 else "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Total Fechado",   _brl(val_fechados))
    c2.metric("💸 Total Declinado", _brl(val_declinados))
    c3.metric("🎟️ Ticket Médio",    _brl(ticket))
    c4.metric("🎯 Conversão",        conv)

    # Negócios fechados
    if not fechados.empty:
        st.divider()
        st.markdown("**✅ Negócios Fechados**")
        cols_w = [2, 2, 1.5, 1.5]
        hdr = st.columns(cols_w)
        for c, l in zip(hdr, ["Equipamento","Cliente","Valor","Data Fechamento"]):
            c.markdown(f'<div style="font-size:10px;font-weight:700;color:#3A4858;">{l}</div>', unsafe_allow_html=True)
        for _, row in fechados.iterrows():
            cols = st.columns(cols_w)
            cols[0].markdown(f'<div style="font-size:12px;color:#3D9970;padding-top:6px;font-weight:500;">{row.get("Equipamento","—")}</div>', unsafe_allow_html=True)
            cols[1].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:6px;">{row.get("Cliente","—")}</div>', unsafe_allow_html=True)
            cols[2].markdown(f'<div style="font-size:12px;color:#F0A84E;padding-top:6px;font-weight:600;">{_brl(_get_valor(row))}</div>', unsafe_allow_html=True)
            cols[3].markdown(f'<div style="font-size:11px;color:#6A7A8A;padding-top:6px;">{row.get("Data_Entrega_Real","") or "—"}</div>', unsafe_allow_html=True)
            st.markdown('<div style="border-bottom:1px solid rgba(45,55,72,.3);margin:2px 0;"></div>', unsafe_allow_html=True)

    # Motivos de declínio
    if not declinados.empty:
        st.divider()
        st.markdown("**❌ Motivos de Declínio**")
        for _, row in declinados.iterrows():
            obs = str(row.get("Observacoes", "") or "")
            motivo = "Não informado"
            for linha in obs.split("\n"):
                if "DECLINADO" in linha:
                    motivo = linha.split("Motivo:")[-1].strip() if "Motivo:" in linha else linha
                    break
            st.markdown(
                f'<div style="background:rgba(232,64,64,.07);border:1px solid rgba(232,64,64,.2);'
                f'border-radius:8px;padding:10px 14px;margin-bottom:6px;">'
                f'<div style="font-size:12px;color:#EEF2F8;font-weight:500;">{row.get("Equipamento","—")} — {row.get("Cliente","—")}</div>'
                f'<div style="font-size:11px;color:#E84040;margin-top:3px;">Motivo: {motivo}</div>'
                f'<div style="font-size:10px;color:#3A4858;margin-top:2px;">{_brl(_get_valor(row))} · {row.get("Data_Entrega_Real","") or "—"}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════
# Render principal
# ══════════════════════════════════════════════════════════════

def render_aba_crm_maquinas():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown("""
<div style="display:flex;align-items:center;gap:14px;padding:10px 0 18px;
            border-bottom:1px solid #2D3748;margin-bottom:24px;">
  <div style="background:rgba(227,108,44,.14);border:1px solid rgba(227,108,44,.4);
              border-radius:10px;padding:10px 14px;font-size:22px;">🤝</div>
  <div>
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:1.9rem;
                font-weight:700;color:#F0F4F8;line-height:1.1;">Pipeline CRM — Máquinas</div>
    <div style="font-size:12px;color:#6A7A8A;text-transform:uppercase;
                letter-spacing:.07em;margin-top:4px;">
      Negociações · Follow-up · Histórico · Conversão</div>
  </div>
</div>""", unsafe_allow_html=True)

    df = ler_producao()

    # Follow-ups do dia — aparece sempre no topo
    _painel_followups(df)

    # KPIs
    _kpis(df)
    st.divider()

    # Nova oportunidade
    _form_nova_oportunidade()
    st.divider()

    # Tabs
    tab_vis, tab_lista, tab_hist = st.tabs([
        "🗂️ Pipeline Visual",
        "📋 Lista Completa",
        "📊 Histórico & Métricas",
    ])

    with tab_vis:
        _pipeline_visual(df)

    with tab_lista:
        _lista_completa(df)

    with tab_hist:
        _historico_metricas(df)
