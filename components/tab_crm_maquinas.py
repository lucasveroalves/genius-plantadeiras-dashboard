"""
components/tab_crm_maquinas.py — Genius Implementos Agrícolas v17

Melhorias v17:
  [V17-CRM-1]  Formulário com clear_on_submit=True — campos limpam após salvar.
  [V17-CRM-2]  Pipeline Visual redesenhado: cards expansíveis com histórico completo
               de observações, inline sem scroll externo.
  [V17-CRM-3]  Follow-up inteligente: alertas visuais no topo do pipeline.
  [V17-CRM-4]  Export Excel em todas as sub-abas (Pipeline Visual, Lista, Histórico).
  [V17-CRM-5]  Filtros avançados: por representante, status, período, valor mínimo.
  [V17-CRM-6]  Ticket médio e funil de conversão em Histórico & Métricas.
  [V17-CRM-7]  "Reabrir" oportunidade declinada/fechada adicionado.
"""

from __future__ import annotations
from datetime import date, datetime, timedelta, timezone


def _hoje_brt() -> str:
    """Retorna data atual no fuso Brasil (UTC-3) formato DD/MM/YYYY."""
    return datetime.now(timezone(timedelta(hours=-3))).strftime('%d/%m/%Y')

from io import BytesIO
import pandas as pd
import streamlit as st
from data.db import (
    ler_producao, adicionar_producao, excluir_producao,
    atualizar_producao_campo,
)

STATUS = ["Em Negociação", "Fechado", "Declinado"]

CORES = {
    "Em Negociação": ("#E8A020", "rgba(232,160,32,.12)"),
    "Fechado":       ("#3D9970", "rgba(61,153,112,.12)"),
    "Declinado":     ("#E84040", "rgba(232,64,64,.12)"),
}

_CSS = """
<style>
.crm-card {
  border-radius:10px;padding:14px 16px;margin-bottom:10px;
  border:1px solid rgba(255,255,255,.07);
}
.crm-equip{font-size:14px;font-weight:600;color:#EEF2F8;margin-bottom:4px;}
.crm-cli{font-size:12px;color:#A8B8CC;margin-bottom:2px;}
.crm-val{font-size:15px;font-weight:700;color:#F0A84E;margin:6px 0 4px;}
.crm-obs{font-size:11px;color:#6A7A8A;margin-top:4px;line-height:1.5;}
.crm-badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:12px;font-size:10px;font-weight:700;}
.hist-item{border-left:2px solid #2D3748;padding:6px 0 6px 12px;margin-bottom:6px;}
.hist-data{font-size:10px;color:#3A4858;}
.hist-texto{font-size:12px;color:#A8B8CC;}
.fu-banner{border-radius:10px;padding:12px 16px;margin-bottom:12px;
  background:rgba(232,64,64,.10);border:1px solid rgba(232,64,64,.3);}
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
    try:
        d = datetime.strptime(data_str.strip(), "%d/%m/%Y").date()
        return (d - date.today()).days
    except Exception:
        return None

def _get_status(row) -> str:
    return str(row.get("Status_Producao", row.get("Status", "Em Negociação")) or "Em Negociação")

def _get_valor(row) -> float:
    """Lê valor da coluna Valor (se existir) ou extrai [VALOR:xxx] das Observacoes."""
    import re as _re
    try:
        v = row.get("Valor", None)
        if v is not None and str(v).strip() not in ("", "None", "0", "nan"):
            return float(v)
    except Exception:
        pass
    try:
        obs = str(row.get("Observacoes", "") or "")
        m = _re.search(r"\[VALOR:([\d.]+)\]", obs)
        if m:
            return float(m.group(1))
    except Exception:
        pass
    return 0.0


# ══════════════════════════════════════════════════════════════
# Painel de follow-ups urgentes [V17-CRM-3]
# ══════════════════════════════════════════════════════════════

def _painel_followups(df: pd.DataFrame):
    if df is None or df.empty:
        return

    status_col = df.apply(_get_status, axis=1)
    df_ativos = df[status_col == "Em Negociação"]

    urgentes = []
    for _, row in df_ativos.iterrows():
        fu_str = str(row.get("Data_Entrega_Prevista", "") or "")
        if not fu_str:
            continue
        dias = _dias_followup(fu_str)
        if dias is not None and dias <= 3:
            urgentes.append((row, dias))

    if not urgentes:
        return

    st.markdown(f"""
<div class="fu-banner">
  <strong style="color:#E87878;">🔔 {len(urgentes)} follow-up(s) urgente(s) hoje ou nos próximos 3 dias!</strong>
</div>""", unsafe_allow_html=True)

    for row, dias in sorted(urgentes, key=lambda x: x[1]):
        msg = "HOJE" if dias == 0 else (f"{abs(dias)}d atrás" if dias < 0 else f"em {dias}d")
        cor = "#E87878" if dias <= 0 else "#E8A020"
        st.markdown(
            f'<div style="font-size:12px;color:{cor};padding:2px 0;">'
            f'📞 <strong>{row.get("Equipamento","—")}</strong> — {row.get("Cliente","—")} '
            f'· Follow-up: <strong>{msg}</strong></div>',
            unsafe_allow_html=True,
        )
    st.markdown("---")


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
    c1.metric("📋 Total",      n_total)
    # [V18-FIX] Pipeline Ativo usa markdown para não truncar valor longo
    c2.markdown(
        f'<div style="padding:4px 0;">'
        f'<div style="font-size:11px;color:#6A7A8A;font-weight:600;">💰 PIPELINE ATIVO</div>'
        f'<div style="font-size:1.4rem;font-weight:700;color:#F0F4F8;margin-top:4px;word-break:break-word;">{_brl(pipeline)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    c3.metric("✅ Fechados",   n_fechados)
    c4.metric("❌ Declinados", n_declin)
    c5.metric("🎯 Conversão",  conversao)


# ══════════════════════════════════════════════════════════════
# Formulário — Nova Oportunidade [V17-CRM-1]
# ══════════════════════════════════════════════════════════════

def _form_nova_oportunidade():
    with st.expander("➕ Nova Oportunidade", expanded=False):
        with st.form("form_crm_v17", clear_on_submit=True):  # [V17-CRM-1]
            c1, c2 = st.columns(2)
            with c1:
                equip       = st.text_input("Equipamento / Modelo *", placeholder="Ex: GATA 18050")
                cliente     = st.text_input("Cliente / Revenda *",    placeholder="Nome da revenda")
                rep         = st.text_input("Representante",          placeholder="Nome do vendedor")
            with c2:
                valor_txt   = st.text_input("Valor Estimado (R$)",    placeholder="Ex: 250.000,00")
                dt_fu       = st.date_input("Data do Follow-up",      value=None, format="DD/MM/YYYY")
                coordenador = st.text_input("Coordenador / Contato",  placeholder="Quem passou o pedido")

            obs = st.text_area("Observações / Detalhes do Pedido", height=80,
                               placeholder="Modelo, configuração, prazo solicitado...")
            salvar = st.form_submit_button("💾 Salvar Oportunidade", type="primary", use_container_width=True)

            if salvar:
                if not equip.strip():
                    st.toast("⚠️ Equipamento é obrigatório.", icon="🚫")
                elif not cliente.strip():
                    st.toast("⚠️ Cliente é obrigatório.", icon="🚫")
                else:
                    valor = _parse_brl(valor_txt)
                    from datetime import timezone, timedelta as _td
                    _brt  = datetime.now(timezone(timedelta(hours=-3)))
                    autor = st.session_state.get("nome_usuario", "Sistema")
                    hist  = f"[{_brt.strftime('%d/%m/%Y')} - {autor}] Oportunidade criada."
                    if obs.strip():
                        hist += f" {obs.strip()}"

                    # [V18-FIX] Valor embutido em Observacoes — coluna Valor nao existe no schema
                    valor_str = f"[VALOR:{valor:.2f}]" if valor > 0 else ""
                    hist_com_valor = (valor_str + " " + hist).strip()

                    reg = {
                        "Equipamento":           equip.strip(),
                        "Cliente":               cliente.strip(),
                        "Representante":         rep.strip(),
                        "Data_Pedido":           date.today().strftime("%d/%m/%Y"),
                        "Data_Inicio_Producao":  coordenador.strip(),
                        "Data_Entrega_Prevista": dt_fu.strftime("%d/%m/%Y") if dt_fu else "",
                        "Data_Entrega_Real":     "",
                        "Status_Producao":       "Em Negociação",
                        "Observacoes":           hist_com_valor,
                    }
                    if adicionar_producao(reg):
                        st.toast(f"✅ '{equip}' adicionado ao pipeline!", icon="✅")
                        st.rerun()


# ══════════════════════════════════════════════════════════════
# Pipeline Visual [V17-CRM-2]
# ══════════════════════════════════════════════════════════════

def _pipeline_visual(df: pd.DataFrame):
    if df is None or df.empty:
        st.info("Nenhuma oportunidade no pipeline.")
        return

    status_col = df.apply(_get_status, axis=1)
    df_ativos  = df[status_col == "Em Negociação"]

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
        st.info("Nenhuma oportunidade em negociação. Use **➕ Nova Oportunidade** acima.")
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

        # Badge de follow-up — apenas mostra a data, sem alerta de atraso
        if fu_str:
            fu_badge = f'<span class="crm-badge" style="background:rgba(45,55,72,.5);color:#A8B8CC;">📅 Follow-up: {fu_str}</span>'
        else:
            fu_badge = '<span class="crm-badge" style="background:rgba(45,55,72,.5);color:#6A7A8A;">Sem follow-up definido</span>'

        # Última linha do histórico
        ultima_obs = obs.strip().split("\n")[-1][:100] if obs.strip() else ""

        st.markdown(
            f'<div class="crm-card" style="background:{cor_bg};border-color:{cor_txt}30;">'
            f'<div class="crm-equip">{equip}</div>'
            f'<div class="crm-cli">👤 {cliente}' + (f' · 📞 {coord}' if coord else '') + '</div>'
            f'<div class="crm-cli">🤝 {rep}</div>'
            f'<div class="crm-val">{_brl(valor)}</div>'
            f'<div style="margin:6px 0;">{fu_badge}</div>'
            + (f'<div class="crm-obs">{ultima_obs}</div>' if ultima_obs else '')
            + '</div>',
            unsafe_allow_html=True,
        )

        # Ações — obs usa st.form com clear_on_submit para limpar após registrar
        col_fu2, col_st, col_del = st.columns([2, 2, 0.5])

        with st.form(key=f"form_obs_{row_id}", clear_on_submit=True):
            fc1, fc2 = st.columns([3, 1])
            nova_obs = fc1.text_input("", placeholder="Nova observação...",
                                      label_visibility="collapsed")
            nova_fu  = fc2.date_input("", value=None, format="DD/MM/YYYY",
                                      label_visibility="collapsed")
            if st.form_submit_button("💬 Registrar obs.", use_container_width=True, type="primary"):
                if nova_obs.strip():
                    autor = st.session_state.get("nome_usuario", "Sistema")
                    entrada = f"\n[{_hoje_brt()} - {autor}] {nova_obs.strip()}"
                    novo_hist = obs + entrada
                    atualizar_producao_campo(row_id, "Observacoes", novo_hist)
                    if nova_fu:
                        atualizar_producao_campo(row_id, "Data_Entrega_Prevista", nova_fu.strftime("%d/%m/%Y"))
                    st.toast("✅ Observação registrada!", icon="✅")
                    st.rerun()
                else:
                    st.toast("⚠️ Digite uma observação.", icon="🚫")

        novo_st = col_st.selectbox("", STATUS, index=0,
                                    key=f"st_{row_id}", label_visibility="collapsed")
        if novo_st != "Em Negociação":
            if novo_st == "Declinado":
                st.session_state[f"_declin_{row_id}"] = True
            else:
                atualizar_producao_campo(row_id, "Status_Producao", novo_st)
                atualizar_producao_campo(row_id, "Data_Entrega_Real", date.today().strftime("%d/%m/%Y"))
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
                        atualizar_producao_campo(row_id, "Data_Entrega_Real", date.today().strftime("%d/%m/%Y"))
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
# Lista Completa [V17-CRM-4] + [V17-CRM-5]
# ══════════════════════════════════════════════════════════════

def _lista_completa(df: pd.DataFrame):
    if df is None or df.empty:
        st.info("Nenhuma oportunidade cadastrada.")
        return

    # Filtros avançados [V17-CRM-5]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st_sel = st.multiselect("Status", STATUS, default=STATUS, key="crm_st_fil")
    with c2:
        busca = st.text_input("🔍 Buscar", placeholder="cliente ou equipamento", key="crm_busca")
    with c3:
        reps = ["Todos"] + sorted(df.get("Representante", pd.Series()).dropna().unique().tolist())
        rep_sel = st.selectbox("Representante", reps, key="crm_rep")
    with c4:
        val_min = st.number_input("Valor mínimo (R$)", min_value=0.0, value=0.0, step=10000.0, key="crm_val_min")

    status_col = df.apply(_get_status, axis=1)
    df_show = df[status_col.isin(st_sel)] if st_sel else df.copy()

    if busca.strip():
        mask = (
            df_show.get("Equipamento", pd.Series()).astype(str).str.contains(busca, case=False, na=False)
            | df_show.get("Cliente",    pd.Series()).astype(str).str.contains(busca, case=False, na=False)
        )
        df_show = df_show[mask]
    if rep_sel != "Todos":
        df_show = df_show[df_show.get("Representante", pd.Series()).astype(str) == rep_sel]
    if val_min > 0:
        df_show = df_show[df_show.apply(_get_valor, axis=1) >= val_min]

    if df_show.empty:
        st.info("Nenhuma oportunidade encontrada com os filtros aplicados.")
        return

    # Export [V18-FIX] Excel limpo — colunas traduzidas, Observacoes sem prefixo VALOR
    import re as _re
    df_exp = df_show.copy()
    df_exp["_Status"] = df_exp.apply(_get_status, axis=1)
    df_exp["_Valor"]  = df_exp.apply(_get_valor, axis=1)
    # Limpar Observacoes — remover prefixo [VALOR:xxx]
    if "Observacoes" in df_exp.columns:
        df_exp["_Obs"] = df_exp["Observacoes"].astype(str).apply(
            lambda x: _re.sub(r"\[VALOR:[\d.]+\]\s*", "", x).strip()
        )
    else:
        df_exp["_Obs"] = ""

    df_export = pd.DataFrame({
        "Equipamento / Modelo": df_exp.get("Equipamento", ""),
        "Cliente / Revenda":    df_exp.get("Cliente", ""),
        "Representante":        df_exp.get("Representante", ""),
        "Valor Estimado (R$)":  df_exp["_Valor"],
        "Status":               df_exp["_Status"],
        "Data do Pedido":       df_exp.get("Data_Pedido", ""),
        "Data Follow-up":       df_exp.get("Data_Entrega_Prevista", ""),
        "Observações":          df_exp["_Obs"],
    })
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name="Pipeline")
        ws = writer.sheets["Pipeline"]
        for col in ws.columns:
            max_len = max(len(str(col[0].value or "")), max((len(str(cell.value or "")) for cell in col[1:]), default=0))
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)
    col_exp, col_count = st.columns([1, 3])
    col_exp.download_button("📥 Exportar Excel", data=buf.getvalue(),
                             file_name=f"pipeline_{date.today()}.xlsx",
                             mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             key="dl_crm_excel")
    col_count.caption(f"{len(df_show)} oportunidade(s) · Valor total em negociação: {_brl(df_show[df_show.apply(_get_status, axis=1)=='Em Negociação'].apply(_get_valor, axis=1).sum())}")

    cols_w = [1.6, 1.5, 1.2, 1.0, 1.1, 1.3, 2.0, 0.7]
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
        ultima_obs = obs.strip().split("\n")[-1][:60] if obs.strip() else "—"
        fu_str  = str(row.get("Data_Entrega_Prevista", "") or "")

        cols = st.columns(cols_w)
        cols[0].markdown(f'<div style="font-size:12px;color:#EEF2F8;padding-top:8px;font-weight:500;">{row.get("Equipamento","—")}</div>', unsafe_allow_html=True)
        cols[1].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Cliente","—")}</div>', unsafe_allow_html=True)
        cols[2].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Representante","—")}</div>', unsafe_allow_html=True)
        cols[3].markdown(f'<div style="font-size:12px;color:#F0A84E;padding-top:8px;font-weight:600;">{_brl(_get_valor(row))}</div>', unsafe_allow_html=True)
        cols[4].markdown(f'<div style="font-size:11px;color:{cor_txt};padding-top:8px;font-weight:600;">{st_row}</div>', unsafe_allow_html=True)
        cols[5].markdown(f'<div style="font-size:11px;color:#6A7A8A;padding-top:8px;">{fu_str or "—"}</div>', unsafe_allow_html=True)
        cols[6].markdown(f'<div style="font-size:11px;color:#A8B8CC;padding-top:8px;">{ultima_obs}</div>', unsafe_allow_html=True)

        # Ações: reabrir ou excluir [V17-CRM-7]
        btn_col1, btn_col2 = cols[7].columns(2)
        if st_row in ("Fechado", "Declinado"):
            if btn_col1.button("↩", key=f"reabrir_{row_id}", help="Reabrir oportunidade"):
                autor = st.session_state.get("nome_usuario", "Sistema")
                entrada = f"\n[{date.today().strftime('%d/%m/%Y')} - {autor}] Oportunidade reaberta."
                atualizar_producao_campo(row_id, "Status_Producao", "Em Negociação")
                atualizar_producao_campo(row_id, "Observacoes", obs + entrada)
                st.toast("↩ Oportunidade reaberta!", icon="✅")
                st.rerun()
        if btn_col2.button("🗑", key=f"list_del_{row_id}"):
            if excluir_producao(row_id):
                st.toast("Removido.", icon="🗑")
                st.rerun()

        st.markdown('<div style="border-bottom:1px solid rgba(45,55,72,.3);margin:2px 0;"></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# Histórico & Métricas [V17-CRM-6]
# ══════════════════════════════════════════════════════════════

def _historico_metricas(df: pd.DataFrame):
    if df is None or df.empty:
        st.info("Sem dados de histórico.")
        return

    status_col = df.apply(_get_status, axis=1)
    valor_col  = df.apply(_get_valor, axis=1)

    fechados   = df[status_col == "Fechado"]
    declinados = df[status_col == "Declinado"]
    ativos     = df[status_col == "Em Negociação"]

    val_fechados   = valor_col[status_col == "Fechado"].sum()
    val_declinados = valor_col[status_col == "Declinado"].sum()
    val_ativos     = valor_col[status_col == "Em Negociação"].sum()
    ticket = float(valor_col[status_col == "Fechado"].mean()) if not fechados.empty else 0.0
    n_fin  = len(fechados) + len(declinados)
    conv   = f"{len(fechados)/n_fin*100:.0f}%" if n_fin > 0 else "—"

    c1, c2, c3, c4, c5 = st.columns(5)
    def _kpi_card(col, label, valor_str):
        col.markdown(
            f'<div style="padding:4px 0;">'            f'<div style="font-size:11px;color:#6A7A8A;font-weight:600;">{label}</div>'            f'<div style="font-size:1.25rem;font-weight:700;color:#F0F4F8;margin-top:4px;word-break:break-word;">{valor_str}</div>'            f'</div>',
            unsafe_allow_html=True,
        )
    _kpi_card(c1, "💰 TOTAL FECHADO",   _brl(val_fechados))
    _kpi_card(c2, "🔄 EM NEGOCIAÇÃO",   _brl(val_ativos))
    _kpi_card(c3, "💸 TOTAL DECLINADO", _brl(val_declinados))
    _kpi_card(c4, "🎟️ TICKET MÉDIO",    _brl(ticket))
    _kpi_card(c5, "🎯 CONVERSÃO",        conv)

    # Export [V18-FIX] histórico limpo
    import re as _re
    df_exp_h = df.copy()
    df_exp_h["_Status"] = df_exp_h.apply(_get_status, axis=1)
    df_exp_h["_Valor"]  = df_exp_h.apply(_get_valor, axis=1)
    df_exp_h["_Obs"] = df_exp_h.get("Observacoes", pd.Series(dtype=str)).astype(str).apply(
        lambda x: _re.sub(r"\[VALOR:[\d.]+\]\s*", "", x).strip()
    )
    df_hist_export = pd.DataFrame({
        "Equipamento / Modelo": df_exp_h.get("Equipamento", ""),
        "Cliente / Revenda":    df_exp_h.get("Cliente", ""),
        "Representante":        df_exp_h.get("Representante", ""),
        "Valor Estimado (R$)":  df_exp_h["_Valor"],
        "Status":               df_exp_h["_Status"],
        "Data do Pedido":       df_exp_h.get("Data_Pedido", ""),
        "Data Follow-up":       df_exp_h.get("Data_Entrega_Prevista", ""),
        "Data Fechamento":      df_exp_h.get("Data_Entrega_Real", ""),
        "Observações":          df_exp_h["_Obs"],
    })
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_hist_export.to_excel(writer, index=False, sheet_name="Histórico Pipeline")
        ws = writer.sheets["Histórico Pipeline"]
        for col in ws.columns:
            max_len = max(len(str(col[0].value or "")), max((len(str(cell.value or "")) for cell in col[1:]), default=0))
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)
    st.download_button("📥 Exportar Histórico Completo (.xlsx)", data=buf.getvalue(),
                        file_name=f"historico_pipeline_{date.today()}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_hist_excel")

    # Negócios fechados
    if not fechados.empty:
        st.divider()
        st.markdown("**✅ Negócios Fechados**")
        cols_w = [2, 2, 1.5, 1.5, 0.7]
        hdr = st.columns(cols_w)
        for c, l in zip(hdr, ["Equipamento","Cliente","Valor","Data Fechamento","Ação"]):
            c.markdown(f'<div style="font-size:10px;font-weight:700;color:#3A4858;">{l}</div>', unsafe_allow_html=True)
        for _, row in fechados.iterrows():
            row_id = int(row.get("id", 0))
            cols = st.columns(cols_w)
            cols[0].markdown(f'<div style="font-size:12px;color:#3D9970;padding-top:6px;font-weight:500;">{row.get("Equipamento","—")}</div>', unsafe_allow_html=True)
            cols[1].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:6px;">{row.get("Cliente","—")}</div>', unsafe_allow_html=True)
            cols[2].markdown(f'<div style="font-size:12px;color:#F0A84E;padding-top:6px;font-weight:600;">{_brl(_get_valor(row))}</div>', unsafe_allow_html=True)
            cols[3].markdown(f'<div style="font-size:11px;color:#6A7A8A;padding-top:6px;">{row.get("Data_Entrega_Real","") or "—"}</div>', unsafe_allow_html=True)
            if cols[4].button("↩", key=f"reabrir_h_{row_id}", help="Reabrir"):
                obs = str(row.get("Observacoes","") or "")
                autor = st.session_state.get("nome_usuario", "Sistema")
                entrada = f"\n[{date.today().strftime('%d/%m/%Y')} - {autor}] Oportunidade reaberta."
                atualizar_producao_campo(row_id, "Status_Producao", "Em Negociação")
                atualizar_producao_campo(row_id, "Observacoes", obs + entrada)
                st.rerun()
            st.markdown('<div style="border-bottom:1px solid rgba(45,55,72,.3);margin:2px 0;"></div>', unsafe_allow_html=True)

    # Motivos de declínio
    if not declinados.empty:
        st.divider()
        st.markdown("**❌ Motivos de Declínio**")
        for _, row in declinados.iterrows():
            row_id = int(row.get("id", 0))
            obs = str(row.get("Observacoes", "") or "")
            motivo = "Não informado"
            for linha in obs.split("\n"):
                if "DECLINADO" in linha:
                    motivo = linha.split("Motivo:")[-1].strip() if "Motivo:" in linha else linha
                    break
            c_txt, c_btn = st.columns([5, 1])
            c_txt.markdown(
                f'<div style="background:rgba(232,64,64,.07);border:1px solid rgba(232,64,64,.2);'
                f'border-radius:8px;padding:10px 14px;margin-bottom:6px;">'
                f'<div style="font-size:12px;color:#EEF2F8;font-weight:500;">{row.get("Equipamento","—")} — {row.get("Cliente","—")}</div>'
                f'<div style="font-size:11px;color:#E84040;margin-top:3px;">Motivo: {motivo}</div>'
                f'<div style="font-size:10px;color:#3A4858;margin-top:2px;">{_brl(_get_valor(row))} · {row.get("Data_Entrega_Real","") or "—"}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if c_btn.button("↩", key=f"reabrir_d_{row_id}", help="Reabrir"):
                autor = st.session_state.get("nome_usuario", "Sistema")
                entrada = f"\n[{date.today().strftime('%d/%m/%Y')} - {autor}] Oportunidade reaberta."
                atualizar_producao_campo(row_id, "Status_Producao", "Em Negociação")
                atualizar_producao_campo(row_id, "Observacoes", obs + entrada)
                st.rerun()


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
      Negociações · Follow-up · Histórico · Conversão · Reabrir</div>
  </div>
</div>""", unsafe_allow_html=True)

    df = ler_producao()

    # KPIs
    _kpis(df)
    st.divider()

    # Nova oportunidade [V17-CRM-1]
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
