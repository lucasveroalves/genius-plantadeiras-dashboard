"""
components/nf_demo.py — Genius Plantadeiras v13
Persistência via Supabase (genius_nf_demo).
"""

from __future__ import annotations
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from data.db import ler_nfs, adicionar_nf, excluir_nf

VALIDADE_DIAS = 60
ALERTA_DIAS   = 10

_CSS = """
<style>
.nf-sec{font-size:11px;font-weight:700;color:#3A4858;text-transform:uppercase;
  letter-spacing:.1em;border-bottom:1px solid #30394A;padding-bottom:6px;margin-bottom:14px;}
.nf-tbl-hdr{font-size:10px;font-weight:700;color:#3A4858;text-transform:uppercase;
  letter-spacing:.08em;padding-bottom:6px;border-bottom:1px solid #2D3748;}
.nf-tbl-div{border-bottom:1px solid rgba(45,55,72,.5);margin:3px 0;}
.alerta-card{border-radius:10px;padding:14px 18px;margin-bottom:10px;
  display:flex;align-items:flex-start;gap:14px;}
.alerta-vence{background:rgba(232,160,32,.13);border:1px solid rgba(232,160,32,.45);}
.alerta-vencida{background:rgba(232,64,64,.13);border:1px solid rgba(232,64,64,.45);}
</style>
"""


def _dias_restantes(data_emissao_str: str) -> int:
    try:
        emissao    = pd.to_datetime(data_emissao_str, dayfirst=True).date()
        vencimento = emissao + timedelta(days=VALIDADE_DIAS)
        return (vencimento - date.today()).days
    except Exception:
        return 9999


def _status_nf(dias: int) -> dict:
    if dias < 0:
        return {"label": "VENCIDA", "dot": "#E84040", "text": "#E87878",
                "bg": "rgba(232,64,64,.10)", "border": "rgba(232,64,64,.4)"}
    if dias <= ALERTA_DIAS:
        return {"label": "ATENÇÃO", "dot": "#E8A020", "text": "#E8C040",
                "bg": "rgba(232,160,32,.10)", "border": "rgba(232,160,32,.4)"}
    return     {"label": "OK",      "dot": "#3D9970", "text": "#52B788",
                "bg": "rgba(61,153,112,.10)", "border": "rgba(61,153,112,.4)"}


def _badge(dias: int) -> str:
    s = _status_nf(dias)
    return (f'<span style="background:{s["bg"]};border:1px solid {s["border"]};'
            f'color:{s["text"]};border-radius:20px;padding:3px 10px;'
            f'font-size:12px;font-weight:700;">'
            f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
            f'background:{s["dot"]};margin-right:5px;vertical-align:middle;"></span>'
            f'{s["label"]}</span>')


def _vencimento_str(data_emissao_str: str) -> str:
    try:
        emissao = pd.to_datetime(data_emissao_str, dayfirst=True).date()
        return (emissao + timedelta(days=VALIDADE_DIAS)).strftime("%d/%m/%Y")
    except Exception:
        return "—"


def _painel_alertas(lista: list):
    proximas = [nf for nf in lista
                if _dias_restantes(nf.get("Data_Emissao", "")) <= ALERTA_DIAS]
    vencidas  = [nf for nf in proximas if _dias_restantes(nf.get("Data_Emissao", "")) < 0]
    a_vencer  = [nf for nf in proximas if _dias_restantes(nf.get("Data_Emissao", "")) >= 0]
    if not proximas:
        return
    st.markdown("### ⚠️ Alertas de Vencimento")
    for nf in vencidas:
        dias = _dias_restantes(nf.get("Data_Emissao", ""))
        st.markdown(
            f'<div class="alerta-card alerta-vencida">'
            f'<span style="font-size:22px;">🔴</span><div>'
            f'<div style="font-weight:700;color:#E87878;font-size:14px;">'
            f'NF {nf.get("Nr_NF","—")} — {nf.get("Cliente","—")} — {nf.get("Maquina","—")}</div>'
            f'<div style="color:#A8B8CC;font-size:12px;margin-top:3px;">'
            f'Emitida em {nf.get("Data_Emissao","—")} · Venceu em {_vencimento_str(nf.get("Data_Emissao",""))} '
            f'<strong style="color:#E84040;">({abs(dias)} dia(s) em atraso)</strong>'
            f'</div></div></div>', unsafe_allow_html=True)
    for nf in a_vencer:
        dias = _dias_restantes(nf.get("Data_Emissao", ""))
        st.markdown(
            f'<div class="alerta-card alerta-vence">'
            f'<span style="font-size:22px;">🟡</span><div>'
            f'<div style="font-weight:700;color:#E8C040;font-size:14px;">'
            f'NF {nf.get("Nr_NF","—")} — {nf.get("Cliente","—")} — {nf.get("Maquina","—")}</div>'
            f'<div style="color:#A8B8CC;font-size:12px;margin-top:3px;">'
            f'Emitida em {nf.get("Data_Emissao","—")} · Vence em {_vencimento_str(nf.get("Data_Emissao",""))} '
            f'<strong style="color:#E8A020;">({dias} dia(s) restante(s))</strong>'
            f'</div></div></div>', unsafe_allow_html=True)
    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">',
                unsafe_allow_html=True)


def _kpis(lista: list):
    total    = len(lista)
    ok       = sum(1 for nf in lista if _dias_restantes(nf.get("Data_Emissao","")) > ALERTA_DIAS)
    atencao  = sum(1 for nf in lista if 0 <= _dias_restantes(nf.get("Data_Emissao","")) <= ALERTA_DIAS)
    vencidas = sum(1 for nf in lista if _dias_restantes(nf.get("Data_Emissao","")) < 0)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📄 Total de NFs",    total)
    c2.metric("✅ Em dia",           ok)
    c3.metric("⚠️ Vencem em breve", atencao)
    c4.metric("🔴 Vencidas",        vencidas)


def _formulario():
    st.markdown('<div class="nf-sec">➕ Lançar Nova NF em Demonstração</div>',
                unsafe_allow_html=True)
    with st.form(key="form_nf_demo", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            data_emissao = st.date_input("Data de Emissão da NF", value=date.today(),
                                         format="DD/MM/YYYY", key="nf_emissao")
            nr_nf = st.text_input("Número da NF", placeholder="Ex: 001234", key="nf_nr")
        with col2:
            cliente = st.text_input("Cliente / Revenda",
                                    placeholder="Nome do cliente ou revenda", key="nf_cliente")
            maquina = st.text_input("Máquina / Equipamento",
                                    placeholder="Ex: GATA 18050 — GS-11688", key="nf_maquina")
        obs = st.text_area("Observações (opcional)", placeholder="Informações adicionais...",
                           height=70, key="nf_obs")
        submitted = st.form_submit_button("💾 Salvar NF em Demonstração", type="primary")

        if submitted:
            if not nr_nf.strip():
                st.toast("⚠️ Número da NF é obrigatório.", icon="🚫")
            elif not cliente.strip():
                st.toast("⚠️ Cliente é obrigatório.", icon="🚫")
            elif not maquina.strip():
                st.toast("⚠️ Máquina é obrigatória.", icon="🚫")
            else:
                reg = {
                    "Data_Emissao": data_emissao.strftime("%d/%m/%Y"),
                    "Nr_NF":        nr_nf.strip(),
                    "Cliente":      cliente.strip(),
                    "Maquina":      maquina.strip(),
                    "Observacoes":  obs.strip(),
                }
                if adicionar_nf(reg):
                    vence = (data_emissao + timedelta(days=VALIDADE_DIAS)).strftime("%d/%m/%Y")
                    st.toast(f"✅ NF {nr_nf.strip()} salva! Vence em {vence}.", icon="✅")
                    st.rerun()


def _tabela(lista: list):
    if not lista:
        st.info("Nenhuma NF em demonstração cadastrada.")
        return
    st.markdown('<div class="nf-sec">📋 NFs em Demonstração</div>', unsafe_allow_html=True)

    cols_w = [0.9, 1.0, 2.0, 2.5, 1.0, 1.0, 1.2, 0.5]
    hdr = st.columns(cols_w)
    for col, lbl in zip(hdr, ["Nº NF","Emissão","Cliente","Máquina","Vencimento","Restam","Status",""]):
        col.markdown(f'<div class="nf-tbl-hdr">{lbl}</div>', unsafe_allow_html=True)

    for nf in lista:
        dias     = _dias_restantes(nf.get("Data_Emissao", ""))
        venc_str = _vencimento_str(nf.get("Data_Emissao", ""))
        row_id   = nf.get("id")
        cols     = st.columns(cols_w)

        cols[0].markdown(f'<div style="font-size:13px;color:#EEF2F8;font-weight:600;padding-top:8px;">{nf.get("Nr_NF","—")}</div>', unsafe_allow_html=True)
        cols[1].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{nf.get("Data_Emissao","—")}</div>', unsafe_allow_html=True)
        cols[2].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{nf.get("Cliente","—")}</div>', unsafe_allow_html=True)
        cols[3].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{nf.get("Maquina","—")}</div>', unsafe_allow_html=True)
        cols[4].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{venc_str}</div>', unsafe_allow_html=True)

        if dias < 0:
            dias_txt = f'<span style="color:#E84040;font-weight:700;">{abs(dias)}d atraso</span>'
        elif dias <= ALERTA_DIAS:
            dias_txt = f'<span style="color:#E8A020;font-weight:700;">{dias}d</span>'
        else:
            dias_txt = f'<span style="color:#52B788;">{dias}d</span>'
        cols[5].markdown(f'<div style="padding-top:8px;">{dias_txt}</div>', unsafe_allow_html=True)
        cols[6].markdown(f'<div style="padding-top:4px;">{_badge(dias)}</div>', unsafe_allow_html=True)

        if cols[7].button("🗑", key=f"del_nf_{row_id}", help="Remover NF"):
            if excluir_nf(row_id):
                st.toast("NF removida.", icon="🗑")
                st.rerun()

        st.markdown('<div class="nf-tbl-div"></div>', unsafe_allow_html=True)

    st.caption(f"Total: {len(lista)} NF(s) · Validade: {VALIDADE_DIAS} dias · Alerta: {ALERTA_DIAS} dias antes.")


def render_aba_nf_demo():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown("""
<div style="display:flex;align-items:center;gap:14px;padding:10px 0 18px;
            border-bottom:1px solid #2D3748;margin-bottom:24px;">
  <div style="background:rgba(227,108,44,.14);border:1px solid rgba(227,108,44,.4);
              border-radius:10px;padding:10px 14px;font-size:22px;">📄</div>
  <div>
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:1.9rem;
                font-weight:700;color:#F0F4F8;line-height:1.1;">NF em Demonstração</div>
    <div style="font-size:12px;color:#6A7A8A;text-transform:uppercase;
                letter-spacing:.07em;margin-top:4px;">
      Controle de Notas Fiscais · Validade 60 dias · Alerta 10 dias antes</div>
  </div>
</div>
""", unsafe_allow_html=True)

    lista = ler_nfs()   # ← Supabase, persiste sempre

    _painel_alertas(lista)
    _kpis(lista)
    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">',
                unsafe_allow_html=True)
    _formulario()
    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">',
                unsafe_allow_html=True)
    _tabela(lista)
