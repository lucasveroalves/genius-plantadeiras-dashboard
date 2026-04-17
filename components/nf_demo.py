"""
components/nf_demo.py — Genius Plantadeiras v14
• Persistência via Supabase
• Controle de NFs em demonstração com validade de 60 dias e alertas visuais.
"""

from __future__ import annotations
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from data.db import ler_nfs, adicionar_nf, excluir_nf

VALIDADE_DIAS = 60
ALERTA_DIAS   = 15   # avisa com 15 e 10 dias

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


def _dias(data_str: str) -> int:
    try:
        emissao = pd.to_datetime(data_str, dayfirst=True).date()
        return (emissao + timedelta(days=VALIDADE_DIAS) - date.today()).days
    except Exception:
        return 9999

def _venc_str(data_str: str) -> str:
    try:
        return (pd.to_datetime(data_str, dayfirst=True).date() + timedelta(days=VALIDADE_DIAS)).strftime("%d/%m/%Y")
    except Exception:
        return "—"

def _badge(dias: int) -> str:
    if dias < 0:
        return ('<span style="background:rgba(232,64,64,.10);border:1px solid rgba(232,64,64,.4);'
                'color:#E87878;border-radius:20px;padding:3px 10px;font-size:12px;font-weight:700;">'
                '🔴 VENCIDA</span>')
    if dias <= 10:
        return ('<span style="background:rgba(232,64,64,.10);border:1px solid rgba(232,64,64,.4);'
                'color:#E87878;border-radius:20px;padding:3px 10px;font-size:12px;font-weight:700;">'
                f'🟠 {dias}d CRÍTICO</span>')
    if dias <= ALERTA_DIAS:
        return ('<span style="background:rgba(232,160,32,.10);border:1px solid rgba(232,160,32,.4);'
                'color:#E8C040;border-radius:20px;padding:3px 10px;font-size:12px;font-weight:700;">'
                f'⚠️ {dias}d</span>')
    return ('<span style="background:rgba(61,153,112,.10);border:1px solid rgba(61,153,112,.4);'
            'color:#52B788;border-radius:20px;padding:3px 10px;font-size:12px;font-weight:700;">'
            f'✅ {dias}d</span>')


def _painel_alertas(lista: list):
    proximas = [nf for nf in lista if _dias(nf.get("Data_Emissao","")) <= ALERTA_DIAS]
    if not proximas:
        return
    st.markdown("### ⚠️ Alertas de Vencimento")
    for nf in proximas:
        dias = _dias(nf.get("Data_Emissao",""))
        css  = "alerta-vencida" if dias < 0 else "alerta-vence"
        ico  = "🔴" if dias < 0 else ("🟠" if dias <= 10 else "🟡")
        msg  = f"{abs(dias)} dia(s) em atraso" if dias < 0 else f"{dias} dia(s) restante(s)"
        cor  = "#E87878" if dias < 0 else "#E8C040"
        st.markdown(
            f'<div class="alerta-card {css}"><span style="font-size:22px;">{ico}</span><div>'
            f'<div style="font-weight:700;color:{cor};font-size:14px;">'
            f'NF {nf.get("Nr_NF","—")} — {nf.get("Cliente","—")} — {nf.get("Maquina","—")}</div>'
            f'<div style="color:#A8B8CC;font-size:12px;margin-top:3px;">'
            f'Emitida {nf.get("Data_Emissao","—")} · Vence {_venc_str(nf.get("Data_Emissao",""))} '
            f'<strong style="color:{cor};">({msg})</strong></div></div></div>',
            unsafe_allow_html=True)
    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)


def _kpis(lista: list):
    total   = len(lista)
    ok      = sum(1 for nf in lista if _dias(nf.get("Data_Emissao","")) > ALERTA_DIAS)
    aten    = sum(1 for nf in lista if 0 <= _dias(nf.get("Data_Emissao","")) <= ALERTA_DIAS)
    venc    = sum(1 for nf in lista if _dias(nf.get("Data_Emissao","")) < 0)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("📄 Total NFs",    total)
    c2.metric("✅ Em dia",        ok)
    c3.metric("⚠️ Vencem breve", aten)
    c4.metric("🔴 Vencidas",     venc)


def _formulario():
    st.markdown('<div class="nf-sec">➕ Lançar Nova NF em Demonstração</div>', unsafe_allow_html=True)
    with st.form("form_nf_demo", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            data_emissao = st.date_input("Data de Emissão", value=date.today(), format="DD/MM/YYYY")
            nr_nf        = st.text_input("Número da NF", placeholder="Ex: 001234")
        with col2:
            cliente  = st.text_input("Cliente / Revenda", placeholder="Nome do cliente")
            maquina  = st.text_input("Máquina / Equipamento", placeholder="Ex: GATA 18050 — GS-11688")
        obs = st.text_area("Observações (opcional)", height=70)
        sub = st.form_submit_button("💾 Salvar NF em Demonstração", type="primary")
        if sub:
            if not nr_nf.strip(): st.toast("⚠️ Número da NF obrigatório.", icon="🚫")
            elif not cliente.strip(): st.toast("⚠️ Cliente obrigatório.", icon="🚫")
            elif not maquina.strip(): st.toast("⚠️ Máquina obrigatória.", icon="🚫")
            else:
                reg = {"Data_Emissao": data_emissao.strftime("%d/%m/%Y"),
                       "Nr_NF": nr_nf.strip(), "Cliente": cliente.strip(),
                       "Maquina": maquina.strip(), "Observacoes": obs.strip()}
                if adicionar_nf(reg):
                    vence = (data_emissao + timedelta(days=VALIDADE_DIAS)).strftime("%d/%m/%Y")
                    st.toast(f"✅ NF {nr_nf.strip()} salva! Vence {vence}.", icon="✅")
                    st.rerun()


def _tabela(lista: list):
    if not lista:
        st.info("Nenhuma NF cadastrada.")
        return
    st.markdown('<div class="nf-sec">📋 NFs em Demonstração</div>', unsafe_allow_html=True)

    cols_w = [0.9, 1.0, 2.0, 2.5, 1.0, 1.2, 0.5]
    hdr = st.columns(cols_w)
    for c, lbl in zip(hdr, ["Nº NF","Emissão","Cliente","Máquina","Vencimento","Status",""]):
        c.markdown(f'<div class="nf-tbl-hdr">{lbl}</div>', unsafe_allow_html=True)

    for nf in lista:
        dias   = _dias(nf.get("Data_Emissao",""))
        row_id = nf.get("id")
        cols   = st.columns(cols_w)
        cols[0].markdown(f'<div style="font-size:13px;color:#EEF2F8;font-weight:600;padding-top:8px;">{nf.get("Nr_NF","—")}</div>', unsafe_allow_html=True)
        cols[1].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{nf.get("Data_Emissao","—")}</div>', unsafe_allow_html=True)
        cols[2].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{nf.get("Cliente","—")}</div>', unsafe_allow_html=True)
        cols[3].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{nf.get("Maquina","—")}</div>', unsafe_allow_html=True)
        cols[4].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{_venc_str(nf.get("Data_Emissao",""))}</div>', unsafe_allow_html=True)
        cols[5].markdown(f'<div style="padding-top:4px;">{_badge(dias)}</div>', unsafe_allow_html=True)
        if cols[6].button("🗑", key=f"del_nf_{row_id}"):
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
      Controle · Validade 60 dias · Alertas 15 e 10 dias antes</div>
  </div>
</div>""", unsafe_allow_html=True)

    lista = ler_nfs()
    _painel_alertas(lista)
    _kpis(lista)

    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)
    _formulario()
    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)
    _tabela(lista)
