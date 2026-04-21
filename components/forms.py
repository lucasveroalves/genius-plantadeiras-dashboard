"""
components/forms.py — Genius Implementos Agrícolas v14 (CORRIGIDO)

Correções aplicadas:
  [FIX-BUG-3]  Validação do formulário de orçamento de peças reestruturada:
               bloco único com return antecipado — elimina toasts duplos/conflitantes
               quando múltiplos campos estão inválidos simultaneamente.
  [FIX-PERF-2] ler_orcamentos() com cache TTL=30s no db.py — forms.py não precisa
               de mudança mas se beneficia automaticamente do cache.
               Após mutações (adicionar/atualizar/excluir), cache é invalidado via
               .clear() nas funções de db.py.
"""

import streamlit as st
import pandas as pd
from datetime import date
from data.db import (
    adicionar_producao, adicionar_orcamento, ler_orcamentos,
    atualizar_orcamento, excluir_orcamento,
    ler_revendas_cadastro, adicionar_revenda_cadastro, excluir_revenda_cadastro,
)


# ══════════════════════════════════════════════════════════════
# FORMULÁRIO 1 — ORÇAMENTO DE MÁQUINA
# ══════════════════════════════════════════════════════════════

def render_formulario_negociacao():
    st.markdown("## ✏️ Lançar Orçamento de Máquina")

    uid = "maq"

    with st.form(key=f"form_neg_{uid}", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            equipamento   = st.text_input("Equipamento / Modelo", placeholder="Ex: GATA 18050",  key=f"eq_{uid}")
            cliente        = st.text_input("Cliente / Revenda",    placeholder="Nome da revenda", key=f"cli_{uid}")
            representante  = st.text_input("Representante",         placeholder="Nome do vendedor",key=f"rep_{uid}")
        with col2:
            data_pedido    = st.date_input("Data do Pedido", value=date.today(), format="DD/MM/YYYY", key=f"dt_ped_{uid}")
            valor_txt      = st.text_input("Valor (R$)", placeholder="Ex: 250.000,00", key=f"val_{uid}")
            status_inicial = st.selectbox("Status Inicial",
                ["Em Negociação","Em Aberto","Crédito","Pronto para Faturar"], key=f"st_{uid}")
        st.markdown("---")
        st.markdown("#### Datas de Produção (opcional)")
        col3, col4 = st.columns(2)
        with col3:
            data_inicio  = st.date_input("Início da Produção",  value=None, format="DD/MM/YYYY", key=f"dt_ini_{uid}")
        with col4:
            data_entrega = st.date_input("Previsão de Entrega", value=None, format="DD/MM/YYYY", key=f"dt_ent_{uid}")
        observacoes = st.text_area("Observações", key=f"obs_{uid}")
        submitted   = st.form_submit_button("💾 Salvar Orçamento de Máquina", type="primary")

        if submitted:
            # Validação centralizada com retorno antecipado
            if not equipamento.strip():
                st.toast("⚠️ 'Equipamento' é obrigatório.", icon="🚫")
                st.stop()
            if not cliente.strip():
                st.toast("⚠️ 'Cliente' é obrigatório.", icon="🚫")
                st.stop()
            valor = _parse_brl(valor_txt)
            if valor <= 0 and valor_txt.strip():
                st.toast("⚠️ Valor inválido. Use o formato: 250.000,00", icon="🚫")
                st.stop()
            if valor <= 0:
                st.toast("⚠️ Valor deve ser maior que zero.", icon="🚫")
                st.stop()

            reg = {
                "Equipamento":           equipamento.strip(),
                "Cliente":               cliente.strip(),
                "Representante":         representante.strip(),
                "Data_Pedido":           data_pedido.strftime("%d/%m/%Y"),
                "Valor":                 valor,
                "Status":                status_inicial,
                "Status_Producao":       status_inicial,
                "Data_Inicio_Producao":  data_inicio.strftime("%d/%m/%Y")  if data_inicio  else "",
                "Data_Entrega_Prevista": data_entrega.strftime("%d/%m/%Y") if data_entrega else "",
                "Data_Entrega_Real":     "",
                "Observacoes":           observacoes.strip(),
            }
            if adicionar_producao(reg):
                st.toast("✅ Orçamento de máquina salvo!", icon="✅")
                st.rerun()
            else:
                st.toast("❌ Erro ao salvar. Tente novamente.", icon="❌")


# ══════════════════════════════════════════════════════════════
# FORMULÁRIO 2 — ORÇAMENTO DE PEÇAS
# ══════════════════════════════════════════════════════════════

def _brl(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except Exception:
        return "R$ 0,00"

def _parse_brl(s: str) -> float:
    """Converte string BRL para float. Aceita: 250.000,00 | 250000.00 | 250000"""
    try:
        s = s.strip().replace("R$","").replace(" ","")
        if "," in s:
            s = s.replace(".","").replace(",",".")
        return float(s)
    except Exception:
        return 0.0


def render_formulario_orcamento_pecas():
    st.markdown("## 📝 Lançar Orçamento de Peças")

    with st.form(key="form_orc_pecas", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            data_orc     = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
            nr_orcamento = st.text_input("Número do Orçamento", placeholder="Ex: ORC-2025-001")
        with col2:
            cliente_rev   = st.text_input("Cliente / Revenda", placeholder="Nome do cliente")
            valor_orc_txt = st.text_input("Valor Total (R$)", placeholder="Ex: 15.000,00")
        col3, col4 = st.columns(2)
        with col3:
            qtd_itens = st.number_input("Volume de Itens (qtd peças)", min_value=0, step=1, value=0)
        with col4:
            status_orc = st.selectbox("Status", ["Aguardando","Faturado"])

        obs_orc = st.text_area("Observações",
                               placeholder="",
                               height=70)

        submitted = st.form_submit_button("💾 Salvar Orçamento de Peças", type="primary")

        if submitted:
            # [FIX-BUG-3] Validação unificada com retorno antecipado — sem toasts duplos
            erro = None
            if not nr_orcamento.strip():
                erro = "⚠️ Número do Orçamento é obrigatório."
            elif not cliente_rev.strip():
                erro = "⚠️ Cliente é obrigatório."
            else:
                valor_orc = _parse_brl(valor_orc_txt)
                if valor_orc <= 0 and valor_orc_txt.strip():
                    erro = "⚠️ Valor inválido. Use o formato: 15.000,00"
                elif valor_orc <= 0:
                    erro = "⚠️ Valor deve ser maior que zero."
    
            if erro:
                st.toast(erro, icon="🚫")
                st.stop()

            reg = {
                "Nr_Pedido":       nr_orcamento.strip(),
                "Data_Orcamento":  data_orc.strftime("%d/%m/%Y"),
                "Cliente_Revenda": cliente_rev.strip(),
                "Descricao_Peca":  "",
                "Quantidade":      int(qtd_itens),
                "Valor_Unit":      0.0,
                "Valor_Total":     valor_orc,
                "Status_Orc":      status_orc,
                "Observacoes":     obs_orc.strip(),
            }
            if adicionar_orcamento(reg):
                st.toast("✅ Orçamento salvo!", icon="✅")
                st.rerun()
            else:
                st.toast("❌ Erro ao salvar.", icon="❌")

    # ── Tabela de orçamentos com edição de status ─────────────
    df_orc = ler_orcamentos()

    if df_orc.empty:
        st.info("Nenhum orçamento lançado ainda.")
        return

    st.divider()
    st.subheader("📋 Orçamentos Lançados")

    kc1, kc2, kc3, kc4 = st.columns(4)
    total_val  = pd.to_numeric(df_orc["Valor_Total"], errors="coerce").fillna(0).sum()
    aguardando = int((df_orc["Status_Orc"] == "Aguardando").sum())
    fechado    = int((df_orc["Status_Orc"] == "Faturado").sum())
    
    kc1.metric("💰 Total em Orçamentos", _brl(total_val))
    kc2.metric("⏳ Aguardando",  aguardando)
    kc3.metric("✅ Faturados",   fechado)
    

    st.markdown("---")

    cols_w = [0.8, 1.1, 1.7, 0.9, 1.2, 1.4, 1.4, 0.5]
    hdr = st.columns(cols_w)
    for c, lbl in zip(hdr, ["Nº Orc.","Data","Cliente","Valor","Qtd","Status","Observação",""]):
        c.markdown(f'<div style="font-size:10px;font-weight:700;color:#3A4858;text-transform:uppercase;'
                   f'letter-spacing:.08em;padding-bottom:6px;border-bottom:1px solid #2D3748;">{lbl}</div>',
                   unsafe_allow_html=True)

    for _, row in df_orc.iterrows():
        row_id = int(row.get("id", 0))
        cols   = st.columns(cols_w)
        cols[0].markdown(f'<div style="font-size:12px;color:#EEF2F8;padding-top:8px;">{row.get("Nr_Pedido","—")}</div>', unsafe_allow_html=True)
        cols[1].markdown(f'<div style="font-size:11px;color:#6A7A8A;padding-top:8px;">{row.get("Data_Orcamento","—")}</div>', unsafe_allow_html=True)
        cols[2].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Cliente_Revenda","—")}</div>', unsafe_allow_html=True)
        cols[3].markdown(f'<div style="font-size:13px;color:#F0F4F8;font-weight:600;padding-top:8px;">{_brl(row.get("Valor_Total",0))}</div>', unsafe_allow_html=True)

        _qtd_val = row.get("Quantidade", 0)
        try: _qtd_val = int(float(_qtd_val))
        except: _qtd_val = 0
        cols[4].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{_qtd_val:,}</div>', unsafe_allow_html=True)

        status_atual = str(row.get("Status_Orc","Aguardando"))
        opcoes = ["Aguardando","Faturado"]
        idx_atual = opcoes.index(status_atual) if status_atual in opcoes else 0
        novo_status = cols[5].selectbox("", opcoes, index=idx_atual,
                                         key=f"st_orc_{row_id}", label_visibility="collapsed")
        if novo_status != status_atual:
            atualizar_orcamento(row_id, {"Status_Orc": novo_status})
            st.rerun()

        cols[6].markdown(f'<div style="font-size:11px;color:#A8B8CC;padding-top:8px;">{row.get("Observacoes","") or "—"}</div>', unsafe_allow_html=True)

        if cols[7].button("🗑", key=f"del_orc_{row_id}"):
            excluir_orcamento(row_id)
            st.rerun()

        if st.session_state.get(f"_declinar_{row_id}"):
            with st.container():
                motivo = st.text_area(f"Motivo do declínio — {row.get('Nr_Pedido','')}",
                                       key=f"motivo_{row_id}", height=70)
                c_ok, c_cancel = st.columns(2)
                if c_ok.button("✅ Confirmar", key=f"ok_dec_{row_id}", type="primary"):
                    if motivo.strip():
                        atualizar_orcamento(row_id, {"Status_Orc": "Declinado", "Observacoes": motivo.strip()})
                        st.session_state.pop(f"_declinar_{row_id}", None)
                        st.rerun()
                    else:
                        st.warning("Informe o motivo.")
                if c_cancel.button("Cancelar", key=f"cancel_dec_{row_id}"):
                    st.session_state.pop(f"_declinar_{row_id}", None)
                    st.rerun()

        st.markdown('<div style="border-bottom:1px solid rgba(45,55,72,.5);margin:3px 0;"></div>',
                    unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# FORMULÁRIO 3 — CADASTRO DE REVENDAS
# ══════════════════════════════════════════════════════════════

def render_formulario_revendas():
    st.markdown("## 🏬 Cadastro de Revendas")

    with st.form(key="form_revenda_cadastro", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nome_rev    = st.text_input("Nome da Revenda",  placeholder="Ex: Agro Sul Implementos")
            cnpj        = st.text_input("CNPJ",              placeholder="00.000.000/0001-00")
        with col2:
            cidade      = st.text_input("Cidade",            placeholder="Ex: Chapecó")
            estado      = st.text_input("Estado (UF)",       placeholder="Ex: SC", max_chars=2)
            responsavel = st.text_input("Responsável",       placeholder="Nome do contato principal")
        regioes = st.text_area("Região / Cidades de Atuação",
                               placeholder="Ex: Chapecó, Xanxerê, Concórdia...", height=80)
        submitted = st.form_submit_button("💾 Salvar Revenda", type="primary")

        if submitted:
            if not nome_rev.strip():
                st.toast("⚠️ Nome da Revenda é obrigatório.", icon="🚫")
                st.stop()
            if not cidade.strip():
                st.toast("⚠️ Cidade é obrigatória.", icon="🚫")
                st.stop()

            reg = {
                "Nome_Revenda":    nome_rev.strip(),
                "CNPJ":            cnpj.strip(),
                "Cidade":          cidade.strip(),
                "Estado":          estado.strip().upper(),
                "Responsavel":     responsavel.strip(),
                "Regioes_Atuacao": regioes.strip(),
            }
            if adicionar_revenda_cadastro(reg):
                st.toast("✅ Revenda cadastrada!", icon="✅")
                st.rerun()

    lista = ler_revendas_cadastro()
    if lista:
        st.divider()
        st.subheader(f"📋 Revendas Cadastradas ({len(lista)})")
        for rev in lista:
            row_id = rev.get("id")
            cols = st.columns([3, 2, 2, 2, 2, 1])
            cols[0].write(f"**{rev.get('Nome_Revenda','—')}**")
            cols[1].write(f"{rev.get('Cidade','—')} / {rev.get('Estado','—')}")
            cols[2].write(rev.get("CNPJ","—"))
            cols[3].write(rev.get("Responsavel","—"))
            reg_txt = rev.get("Regioes_Atuacao","—")
            cols[4].write(reg_txt[:40] + "..." if len(reg_txt) > 40 else reg_txt)
            if cols[5].button("🗑", key=f"del_rev_{row_id}"):
                if excluir_revenda_cadastro(row_id):
                    st.toast("Revenda removida.", icon="🗑")
                    st.rerun()
    else:
        st.info("Nenhuma revenda cadastrada ainda.")
