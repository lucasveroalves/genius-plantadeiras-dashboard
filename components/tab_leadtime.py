from datetime import datetime
"""
components/tab_leadtime.py — Genius Implementos Agrícolas v14
Sub-aba: Controle de Lead Time — Orçamento → Requisição → NF

Fluxo:
  1. Orçamento fechado (vem de genius_orcamentos com Status_Orc = 'Fechado')
     → comercial lança aqui com Nr_Requisicao e Data_Requisicao
  2. Logística confirma separação → status evolui para 'Req. Enviada'
  3. Comercial emite NF → preenche Nr_NF e Data_NF → status 'NF Emitida'
  4. Dashboard calcula lead time médio em dias para cada etapa.

Tabela Supabase necessária:
  CREATE TABLE genius_leadtime_pecas (
    id                      BIGSERIAL PRIMARY KEY,
    Nr_Orcamento            TEXT,
    Cliente_Revenda         TEXT,
    Valor_Total             TEXT,
    Data_Orcamento_Fechado  TEXT,
    Nr_Requisicao           TEXT,
    Data_Requisicao         TEXT,
    Nr_NF                   TEXT,
    Data_NF                 TEXT,
    Status_Lead             TEXT DEFAULT 'Orçamento Fechado',
    Observacoes             TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW()
  );
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
from data.db import (
    ler_leadtime, adicionar_leadtime, atualizar_leadtime,
    excluir_leadtime, calcular_kpis_leadtime,
)


# ── Helpers de formatação ──────────────────────────────────────

def _brl(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def _parse_brl(s: str) -> float:
    try:
        s = str(s).strip().replace("R$", "").replace(" ", "")
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        return float(s)
    except Exception:
        return 0.0

def _dias_cor(dias: int) -> str:
    """Cor semáforo por lead time em dias."""
    if dias is None: return "#6A7A8A"
    if dias <= 3:    return "#27AE60"   # verde — rápido
    if dias <= 7:    return "#F39C12"   # amarelo — atenção
    return "#E74C3C"                    # vermelho — atrasado

def _fmt_data(s: str) -> str:
    """Garante formato DD/MM/YYYY ou retorna '—'."""
    if not s or str(s).strip() in ("", "nan", "None"):
        return "—"
    return str(s).strip()

STATUS_LEAD = ["Orçamento Fechado", "Req. Enviada", "NF Emitida"]

BADGE = {
    "Orçamento Fechado": ("🟡", "#F39C12"),
    "Req. Enviada":       ("🔵", "#3498DB"),
    "NF Emitida":         ("🟢", "#27AE60"),
}


# ══════════════════════════════════════════════════════════════
# RENDER PRINCIPAL
# ══════════════════════════════════════════════════════════════

def render_tab_leadtime():
    st.markdown("## 🕐 Lead Time — Orçamento → Requisição → NF")
    st.caption(
        "Registre aqui cada orçamento fechado. Acompanhe o tempo até a emissão da NF "
        "e identifique gargalos no processo logístico."
    )

    df = ler_leadtime()
    kpis = calcular_kpis_leadtime(df)

    # ── KPIs ─────────────────────────────────────────────────
    _render_kpis(kpis)

    st.markdown("---")

    # ── Sub-abas ─────────────────────────────────────────────
    tab_novo, tab_pipeline, tab_historico = st.tabs([
        "➕ Lançar Novo",
        "🔄 Pipeline",
        "📊 Histórico & Métricas",
    ])

    with tab_novo:
        _render_form_novo()

    with tab_pipeline:
        _render_pipeline(df)

    with tab_historico:
        _render_historico(df, kpis)


# ── KPIs ──────────────────────────────────────────────────────

def _render_kpis(kpis: dict):
    c1, c2, c3, c4, c5, c6 = st.columns(6)

    c1.metric("📋 Total Registros",   kpis["total_registros"])
    c2.metric("🟡 Ag. Requisição",    kpis["aguardando_req"])
    c3.metric("🔵 Req. Enviada",       kpis["req_enviada"])
    c4.metric("🟢 NF Emitida",         kpis["nf_emitida"])

    lead_med = kpis.get("lead_medio_dias")
    lead_max = kpis.get("lead_max_dias")
    c5.metric(
        "⏱ Lead Médio (dias)",
        f"{lead_med} d" if lead_med is not None else "—",
        help="Média de dias entre orçamento fechado e emissão da NF"
    )
    c6.metric(
        "⚠️ Lead Máx (dias)",
        f"{lead_max} d" if lead_max is not None else "—",
        help="Caso mais demorado registrado"
    )


# ── Formulário de lançamento ──────────────────────────────────

def _render_form_novo():
    st.markdown("### ➕ Lançar Orçamento Fechado")

    with st.form(key="form_leadtime_novo", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            nr_orc      = st.text_input("Nº do Orçamento *",    placeholder="Ex: ORC-2026-042")
            cliente     = st.text_input("Cliente / Revenda *",   placeholder="Nome da revenda")
        with col2:
            valor_txt   = st.text_input("Valor do Orçamento (R$)", placeholder="Ex: 12.500,00")
            dt_fechado  = st.date_input("Data do Fechamento *",  value=date.today(), format="DD/MM/YYYY")
        with col3:
            nr_req      = st.text_input("Nº da Requisição",      placeholder="Ex: REQ-00123  (opcional)")
            dt_req      = st.date_input("Data da Requisição",    value=None, format="DD/MM/YYYY")

        obs = st.text_area("Observações", height=60)

        # Status inicial depende se req já foi informada
        submitted = st.form_submit_button("💾 Salvar", type="primary")

        if submitted:
            erros = []
            if not nr_orc.strip():   erros.append("Nº do Orçamento é obrigatório.")
            if not cliente.strip():  erros.append("Cliente é obrigatório.")
            if erros:
                for e in erros:
                    st.toast(f"⚠️ {e}", icon="🚫")
            else:
                status = "Req. Enviada" if nr_req.strip() else "Orçamento Fechado"
                reg = {
                    "Nr_Orcamento":            nr_orc.strip(),
                    "Cliente_Revenda":          cliente.strip(),
                    "Valor_Total":              str(_parse_brl(valor_txt)),
                    "Data_Orcamento_Fechado":   dt_fechado.strftime("%d/%m/%Y"),
                    "Nr_Requisicao":            nr_req.strip(),
                    "Data_Requisicao":          dt_req.strftime("%d/%m/%Y") if dt_req else "",
                    "Nr_NF":                    "",
                    "Data_NF":                  "",
                    "Status_Lead":              status,
                    "Observacoes":              obs.strip(),
                }
                if adicionar_leadtime(reg):
                    st.toast("✅ Registro salvo!", icon="✅")
                    st.rerun()
                else:
                    st.toast("❌ Erro ao salvar.", icon="❌")

    st.info(
        "💡 **Fluxo:** Lance o orçamento fechado → informe o Nº da Requisição "
        "enviada à logística → quando a NF for emitida, atualize no Pipeline.",
        icon="ℹ️"
    )


# ── Pipeline (kanban visual em tabela editável) ───────────────

def _render_pipeline(df: pd.DataFrame):
    st.markdown("### 🔄 Pipeline de Pedidos em Andamento")

    if df.empty:
        st.info("Nenhum registro lançado ainda. Use a aba '➕ Lançar Novo'.")
        return

    # Filtra apenas não concluídos
    em_aberto = df[df["Status_Lead"] != "NF Emitida"].copy()
    if em_aberto.empty:
        st.success("✅ Todos os pedidos já tiveram NF emitida!")
        return

    # Cabeçalho
    cols_w = [1.0, 1.6, 1.4, 1.1, 1.3, 1.3, 1.4, 1.0, 0.5]
    hdr = st.columns(cols_w)
    labels = ["Nº Orc.", "Cliente", "Valor", "Dt. Fechto.", "Nº Req.", "Dt. Req.", "Status", "Ação", ""]
    for col, lbl in zip(hdr, labels):
        col.markdown(
            f'<div style="font-size:10px;font-weight:700;color:#6A7A8A;'
            f'text-transform:uppercase;letter-spacing:.07em;padding-bottom:4px;'
            f'border-bottom:1px solid #2D3748;">{lbl}</div>',
            unsafe_allow_html=True
        )

    for _, row in em_aberto.iterrows():
        row_id  = int(row.get("id", 0))
        status  = str(row.get("Status_Lead", "Orçamento Fechado"))
        badge_icon, badge_color = BADGE.get(status, ("⚪", "#6A7A8A"))
        cols    = st.columns(cols_w)

        cols[0].markdown(f'<div style="font-size:11px;color:#EEF2F8;padding-top:6px;">{row.get("Nr_Orcamento","—")}</div>', unsafe_allow_html=True)
        cols[1].markdown(f'<div style="font-size:11px;color:#A8B8CC;padding-top:6px;">{row.get("Cliente_Revenda","—")}</div>', unsafe_allow_html=True)
        cols[2].markdown(f'<div style="font-size:12px;color:#F0F4F8;font-weight:600;padding-top:6px;">{_brl(row.get("Valor_Total",0))}</div>', unsafe_allow_html=True)
        cols[3].markdown(f'<div style="font-size:11px;color:#6A7A8A;padding-top:6px;">{_fmt_data(row.get("Data_Orcamento_Fechado",""))}</div>', unsafe_allow_html=True)
        cols[4].markdown(f'<div style="font-size:11px;color:#A8B8CC;padding-top:6px;">{row.get("Nr_Requisicao","—") or "—"}</div>', unsafe_allow_html=True)
        cols[5].markdown(f'<div style="font-size:11px;color:#6A7A8A;padding-top:6px;">{_fmt_data(row.get("Data_Requisicao",""))}</div>', unsafe_allow_html=True)
        cols[6].markdown(
            f'<div style="font-size:11px;font-weight:600;color:{badge_color};padding-top:6px;">'
            f'{badge_icon} {status}</div>',
            unsafe_allow_html=True
        )

        # Botão de ação contextual
        if status == "Orçamento Fechado":
            if cols[7].button("📤 Req.", key=f"btn_req_{row_id}", help="Informar requisição enviada"):
                st.session_state[f"_modal_req_{row_id}"] = True
        elif status == "Req. Enviada":
            if cols[7].button("🧾 NF", key=f"btn_nf_{row_id}", help="Informar emissão da NF"):
                st.session_state[f"_modal_nf_{row_id}"] = True

        if cols[8].button("🗑", key=f"del_lead_{row_id}"):
            excluir_leadtime(row_id)
            st.rerun()

        # Modal: informar requisição
        if st.session_state.get(f"_modal_req_{row_id}"):
            with st.container():
                st.markdown(f"**📤 Informar Requisição — {row.get('Nr_Orcamento','')}**")
                mc1, mc2 = st.columns(2)
                nr_req_input = mc1.text_input("Nº da Requisição *", key=f"req_nr_{row_id}",
                                               placeholder="Ex: REQ-00123")
                dt_req_input = mc2.date_input("Data da Requisição *", value=date.today(),
                                               format="DD/MM/YYYY", key=f"req_dt_{row_id}")
                bc1, bc2 = st.columns(2)
                if bc1.button("✅ Confirmar", key=f"ok_req_{row_id}", type="primary"):
                    if nr_req_input.strip():
                        atualizar_leadtime(row_id, {
                            "Nr_Requisicao":   nr_req_input.strip(),
                            "Data_Requisicao": dt_req_input.strftime("%d/%m/%Y"),
                            "Status_Lead":     "Req. Enviada",
                        })
                        st.session_state.pop(f"_modal_req_{row_id}", None)
                        st.rerun()
                    else:
                        st.warning("Informe o número da requisição.")
                if bc2.button("Cancelar", key=f"cancel_req_{row_id}"):
                    st.session_state.pop(f"_modal_req_{row_id}", None)
                    st.rerun()

        # Modal: informar NF
        if st.session_state.get(f"_modal_nf_{row_id}"):
            with st.container():
                st.markdown(f"**🧾 Emissão de NF — {row.get('Nr_Orcamento','')}**")
                mc1, mc2 = st.columns(2)
                nr_nf_input  = mc1.text_input("Nº da NF *", key=f"nf_nr_{row_id}",
                                               placeholder="Ex: 001234")
                dt_nf_input  = mc2.date_input("Data de Emissão da NF *", value=date.today(),
                                               format="DD/MM/YYYY", key=f"nf_dt_{row_id}")
                bc1, bc2 = st.columns(2)
                if bc1.button("✅ Confirmar NF", key=f"ok_nf_{row_id}", type="primary"):
                    if nr_nf_input.strip():
                        atualizar_leadtime(row_id, {
                            "Nr_NF":       nr_nf_input.strip(),
                            "Data_NF":     dt_nf_input.strftime("%d/%m/%Y"),
                            "Status_Lead": "NF Emitida",
                        })
                        st.session_state.pop(f"_modal_nf_{row_id}", None)
                        st.rerun()
                    else:
                        st.warning("Informe o número da NF.")
                if bc2.button("Cancelar", key=f"cancel_nf_{row_id}"):
                    st.session_state.pop(f"_modal_nf_{row_id}", None)
                    st.rerun()

        st.markdown(
            '<div style="border-bottom:1px solid rgba(45,55,72,.4);margin:2px 0;"></div>',
            unsafe_allow_html=True
        )


# ── Histórico & Métricas ──────────────────────────────────────

def _render_historico(df: pd.DataFrame, kpis: dict):
    st.markdown("### 📊 Histórico de Lead Times")

    if df.empty:
        st.info("Nenhum dado disponível.")
        return

    concluidos = df[df["Status_Lead"] == "NF Emitida"].copy()

    if concluidos.empty:
        st.info("Nenhuma NF emitida ainda. Os lead times aparecerão aqui quando o ciclo for concluído.")
        return

    # Calcula lead time por linha
    def _calc_lead(row):
        try:
            d1 = datetime.strptime(str(row["Data_Orcamento_Fechado"]).strip(), "%d/%m/%Y")
            d2 = datetime.strptime(str(row["Data_NF"]).strip(), "%d/%m/%Y")
            return (d2 - d1).days
        except Exception:
            return None

    concluidos["Lead_Dias"] = concluidos.apply(_calc_lead, axis=1)
    concluidos_validos = concluidos.dropna(subset=["Lead_Dias"])

    if not concluidos_validos.empty:
        # Gráfico de barras por orçamento
        try:
            import altair as alt

            chart_df = concluidos_validos[["Nr_Orcamento", "Cliente_Revenda", "Lead_Dias"]].copy()
            chart_df["Lead_Dias"] = chart_df["Lead_Dias"].astype(int)
            chart_df["Cor"] = chart_df["Lead_Dias"].apply(
                lambda d: "Rápido (≤3d)" if d <= 3 else ("Normal (≤7d)" if d <= 7 else "Atrasado (>7d)")
            )

            cores = {
                "Rápido (≤3d)":    "#27AE60",
                "Normal (≤7d)":    "#F39C12",
                "Atrasado (>7d)":  "#E74C3C",
            }

            bar = alt.Chart(chart_df).mark_bar().encode(
                x=alt.X("Lead_Dias:Q", title="Dias"),
                y=alt.Y("Nr_Orcamento:N", sort="-x", title="Nº Orçamento"),
                color=alt.Color("Cor:N",
                    scale=alt.Scale(domain=list(cores.keys()), range=list(cores.values())),
                    legend=alt.Legend(title="Lead Time")),
                tooltip=["Nr_Orcamento", "Cliente_Revenda", "Lead_Dias",
                         "Data_Orcamento_Fechado", "Data_NF"]
            ).properties(
                title="Lead Time por Orçamento (dias)",
                height=max(200, len(chart_df) * 28)
            )
            st.altair_chart(bar, use_container_width=True)

        except ImportError:
            # Fallback sem altair
            st.dataframe(
                concluidos_validos[["Nr_Orcamento","Cliente_Revenda",
                                    "Data_Orcamento_Fechado","Data_NF","Lead_Dias"]]
                .rename(columns={"Lead_Dias":"Dias"}),
                use_container_width=True
            )

    # Tabela completa com todos os registros
    st.markdown("#### 📋 Registros Completos")
    display_cols = ["Nr_Orcamento","Cliente_Revenda","Valor_Total",
                    "Data_Orcamento_Fechado","Nr_Requisicao","Data_Requisicao",
                    "Nr_NF","Data_NF","Status_Lead"]
    df_show = df[[c for c in display_cols if c in df.columns]].copy()
    if "Valor_Total" in df_show.columns:
        df_show["Valor_Total"] = df_show["Valor_Total"].apply(_brl)

    st.dataframe(df_show, use_container_width=True, hide_index=True)

    # Botão de export
    try:
        import io
        buf = io.BytesIO()
        df_show.to_excel(buf, index=False, engine="openpyxl")
        st.download_button(
            "⬇️ Exportar Excel",
            data=buf.getvalue(),
            file_name=f"leadtime_pecas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception:
        pass
