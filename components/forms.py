"""
components/forms.py — Genius Plantadeiras v13
Persistência de orçamentos e revendas via Supabase.
"""

import streamlit as st
import pandas as pd
from datetime import date
from data.db import (
    adicionar_producao, adicionar_orcamento, ler_orcamentos,
    ler_revendas_cadastro, adicionar_revenda_cadastro, excluir_revenda_cadastro,
)


# ══════════════════════════════════════════════════════════════
# FORMULÁRIO 1 — LANÇAR ORÇAMENTO DE MÁQUINA
# ══════════════════════════════════════════════════════════════

def render_formulario_negociacao():
    st.markdown("## ✏️ Lançar Orçamento de Máquina")

    if "global_form_counter" not in st.session_state:
        st.session_state.global_form_counter = 0
    st.session_state.global_form_counter += 1
    uid = st.session_state.global_form_counter

    with st.form(key=f"form_neg_{uid}", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            equipamento   = st.text_input("Equipamento / Modelo", placeholder="Ex: GATA 18050", key=f"eq_{uid}")
            cliente        = st.text_input("Cliente / Revenda", placeholder="Nome da revenda ou cliente final", key=f"cli_{uid}")
            representante  = st.text_input("Representante", placeholder="Nome do vendedor", key=f"rep_{uid}")
        with col2:
            data_pedido    = st.date_input("Data do Pedido", value=date.today(), format="DD/MM/YYYY", key=f"dt_ped_{uid}")
            valor          = st.number_input("Valor do Pedido (R$)", min_value=0.0, step=1000.0, format="%.2f", key=f"val_{uid}")
            status_inicial = st.selectbox("Status Inicial",
                                          ["Em Negociação", "Em Aberto", "Crédito", "Pronto para Faturar"],
                                          key=f"st_{uid}")
        st.markdown("---")
        st.markdown("#### Datas de Produção (opcional)")
        col3, col4 = st.columns(2)
        with col3:
            data_inicio  = st.date_input("Início da Produção",  value=None, format="DD/MM/YYYY", key=f"dt_ini_{uid}")
        with col4:
            data_entrega = st.date_input("Previsão de Entrega", value=None, format="DD/MM/YYYY", key=f"dt_ent_{uid}")
        observacoes = st.text_area("Observações", placeholder="Detalhes adicionais...", key=f"obs_{uid}")
        submitted = st.form_submit_button("💾 Salvar Orçamento de Máquina", type="primary")

        if submitted:
            if not equipamento.strip():
                st.toast("⚠️ O campo 'Equipamento' é obrigatório.", icon="🚫")
            elif not cliente.strip():
                st.toast("⚠️ O campo 'Cliente' é obrigatório.", icon="🚫")
            elif valor <= 0:
                st.toast("⚠️ O valor do pedido deve ser maior que zero.", icon="🚫")
            else:
                reg = {
                    "Equipamento":           equipamento.strip(),
                    "Cliente":               cliente.strip(),
                    "Representante":         representante.strip(),
                    "Data_Pedido":           data_pedido.strftime("%d/%m/%Y"),
                    "Valor":                 valor,
                    "Status":                status_inicial,
                    "Data_Inicio_Producao":  data_inicio.strftime("%d/%m/%Y")  if data_inicio  else "",
                    "Data_Entrega_Prevista": data_entrega.strftime("%d/%m/%Y") if data_entrega else "",
                    "Data_Entrega_Real":     "",
                    "Observacoes":           observacoes.strip(),
                    "Status_Producao":       status_inicial,
                }
                if adicionar_producao(reg):
                    st.toast("✅ Orçamento de máquina salvo com sucesso!", icon="✅")
                    st.rerun()
                else:
                    st.toast("❌ Erro ao salvar. Tente novamente.", icon="❌")


# ══════════════════════════════════════════════════════════════
# FORMULÁRIO 2 — LANÇAR ORÇAMENTO DE PEÇAS
# ══════════════════════════════════════════════════════════════

def render_formulario_orcamento_pecas():
    st.markdown("## 📝 Lançar Orçamento de Peças")

    with st.form(key="form_orc_pecas", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            data_orc     = st.date_input("Data", value=date.today(), format="DD/MM/YYYY", key="orc_data")
            nr_orcamento = st.text_input("Número do Orçamento", placeholder="Ex: ORC-2025-001", key="orc_nr")
        with col2:
            cliente_rev = st.text_input("Cliente / Revenda", placeholder="Nome do cliente ou revenda", key="orc_cliente")
            valor_orc   = st.number_input("Valor (R$)", min_value=0.0, step=100.0, format="%.2f", key="orc_valor")
        status_orc = st.selectbox("Status", ["Aguardando", "Declinado", "Fechado"], key="orc_status")
        submitted  = st.form_submit_button("💾 Salvar Orçamento de Peças", type="primary")

        if submitted:
            if not nr_orcamento.strip():
                st.toast("⚠️ Número do Orçamento é obrigatório.", icon="🚫")
            elif not cliente_rev.strip():
                st.toast("⚠️ Cliente / Revenda é obrigatório.", icon="🚫")
            elif valor_orc <= 0:
                st.toast("⚠️ O valor deve ser maior que zero.", icon="🚫")
            else:
                reg = {
                    "Nr_Pedido":       nr_orcamento.strip(),
                    "Data_Orcamento":  data_orc.strftime("%d/%m/%Y"),
                    "Cliente_Revenda": cliente_rev.strip(),
                    "Descricao_Peca":  "",
                    "Quantidade":      0,
                    "Valor_Unit":      0.0,
                    "Valor_Total":     valor_orc,
                    "Status_Orc":      status_orc,
                    "Observacoes":     "",
                }
                if adicionar_orcamento(reg):
                    st.toast("✅ Orçamento de peças salvo!", icon="✅")
                    st.rerun()
                else:
                    st.toast("❌ Erro ao salvar. Tente novamente.", icon="❌")

    # ── Tabela de orçamentos ──────────────────────────────────
    df_orc = ler_orcamentos()
    if not df_orc.empty:
        st.divider()
        st.subheader("📋 Orçamentos Lançados")

        def _brl(v):
            return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        kc1, kc2, kc3 = st.columns(3)
        total_orc  = pd.to_numeric(df_orc["Valor_Total"], errors="coerce").fillna(0).sum()
        aguardando = int((df_orc["Status_Orc"] == "Aguardando").sum()) if "Status_Orc" in df_orc.columns else 0
        fechado    = int((df_orc["Status_Orc"] == "Fechado").sum())    if "Status_Orc" in df_orc.columns else 0

        kc1.metric("💰 Total em Orçamentos", _brl(total_orc))
        kc2.metric("⏳ Aguardando", aguardando)
        kc3.metric("✅ Fechados",   fechado)
        st.dataframe(df_orc, use_container_width=True, height=300)
    else:
        st.info("Nenhum orçamento lançado ainda.")


# ══════════════════════════════════════════════════════════════
# FORMULÁRIO 3 — CADASTRO DE REVENDAS
# ══════════════════════════════════════════════════════════════

def render_formulario_revendas():
    st.markdown("## 🏬 Cadastro de Revendas")

    with st.form(key="form_revenda_cadastro", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nome_rev    = st.text_input("Nome da Revenda",  placeholder="Ex: Agro Sul Implementos", key="rev_nome")
            cnpj        = st.text_input("CNPJ",              placeholder="00.000.000/0001-00",       key="rev_cnpj")
            endereco    = st.text_input("Endereço",          placeholder="Rua, número, bairro",      key="rev_end")
        with col2:
            cidade      = st.text_input("Cidade",            placeholder="Ex: Chapecó",              key="rev_cidade")
            estado      = st.text_input("Estado (UF)",       placeholder="Ex: SC", max_chars=2,      key="rev_uf")
            responsavel = st.text_input("Responsável",       placeholder="Nome do contato principal",key="rev_resp")
        regioes = st.text_area("Região / Cidades de Atuação",
                               placeholder="Ex: Chapecó, Xanxerê, Concórdia, Joaçaba...",
                               height=80, key="rev_regioes")
        submitted = st.form_submit_button("💾 Salvar Revenda", type="primary")

        if submitted:
            if not nome_rev.strip():
                st.toast("⚠️ Nome da Revenda é obrigatório.", icon="🚫")
            elif not cidade.strip():
                st.toast("⚠️ Cidade é obrigatória.", icon="🚫")
            else:
                reg = {
                    "Nome_Revenda":    nome_rev.strip(),
                    "CNPJ":            cnpj.strip(),
                    "Endereco":        endereco.strip(),
                    "Cidade":          cidade.strip(),
                    "Estado":          estado.strip().upper(),
                    "Responsavel":     responsavel.strip(),
                    "Regioes_Atuacao": regioes.strip(),
                }
                if adicionar_revenda_cadastro(reg):
                    st.toast("✅ Revenda cadastrada com sucesso!", icon="✅")
                    st.rerun()

    # ── Tabela de revendas ────────────────────────────────────
    lista = ler_revendas_cadastro()
    if lista:
        st.divider()
        st.subheader(f"📋 Revendas Cadastradas ({len(lista)})")
        for rev in lista:
            row_id = rev.get("id")
            cols = st.columns([3, 2, 2, 2, 2, 1])
            cols[0].write(f"**{rev.get('Nome_Revenda','—')}**")
            cols[1].write(f"{rev.get('Cidade','—')} / {rev.get('Estado','—')}")
            cols[2].write(rev.get("CNPJ", "—"))
            cols[3].write(rev.get("Responsavel", "—"))
            reg_txt = rev.get("Regioes_Atuacao", "—")
            cols[4].write(reg_txt[:40] + "..." if len(reg_txt) > 40 else reg_txt)
            if cols[5].button("🗑", key=f"del_rev_{row_id}", help="Remover"):
                if excluir_revenda_cadastro(row_id):
                    st.toast("Revenda removida.", icon="🗑")
                    st.rerun()
    else:
        st.info("Nenhuma revenda cadastrada ainda.")
