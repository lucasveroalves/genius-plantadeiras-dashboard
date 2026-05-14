"""
components/forms.py — Genius Implementos Agrícolas v17

Correções v17:
  [V17-FIX-1]  clear_on_submit=True em TODOS os formulários — campos limpam após salvar.
  [V17-FIX-2]  render_formulario_revendas(): ao cadastrar revenda, sincroniza
               automaticamente com a tabela 'territorios' — a cidade sede E todas
               as cidades em 'Regioes_Atuacao' são adicionadas ao mapa de territórios.
  [V17-FIX-3]  Export Excel adicionado na tabela de orçamentos e revendas.
"""

import streamlit as st
import pandas as pd
from datetime import date
from io import BytesIO
from data.db import (
    adicionar_producao, adicionar_orcamento, ler_orcamentos,
    atualizar_orcamento, excluir_orcamento,
    ler_revendas_cadastro, adicionar_revenda_cadastro, excluir_revenda_cadastro,
    adicionar_territorio, ler_territorios,
)


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def _brl(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except Exception:
        return "R$ 0,00"

def _parse_brl(s: str) -> float:
    try:
        s = s.strip().replace("R$","").replace(" ","")
        if "," in s:
            s = s.replace(".","").replace(",",".")
        return float(s)
    except Exception:
        return 0.0


# ══════════════════════════════════════════════════════════════
# FORMULÁRIO 1 — ORÇAMENTO DE MÁQUINA
# ══════════════════════════════════════════════════════════════

def render_formulario_negociacao():
    st.markdown("## ✏️ Lançar Orçamento de Máquina")

    uid = "maq"

    with st.form(key=f"form_neg_{uid}", clear_on_submit=True):  # [V17-FIX-1]
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

            # [V18-FIX] Valor embutido nas Observacoes — coluna Valor nao existe no schema
            valor_str = f"[VALOR:{valor:.2f}]" if valor > 0 else ""
            obs_final = (valor_str + " " + observacoes.strip()).strip()

            reg = {
                "Equipamento":           equipamento.strip(),
                "Cliente":               cliente.strip(),
                "Representante":         representante.strip(),
                "Data_Pedido":           data_pedido.strftime("%d/%m/%Y"),
                "Status":                status_inicial,
                "Status_Producao":       status_inicial,
                "Data_Inicio_Producao":  data_inicio.strftime("%d/%m/%Y")  if data_inicio  else "",
                "Data_Entrega_Prevista": data_entrega.strftime("%d/%m/%Y") if data_entrega else "",
                "Data_Entrega_Real":     "",
                "Observacoes":           obs_final,
            }
            if adicionar_producao(reg):
                st.toast("✅ Orçamento de máquina salvo!", icon="✅")
                st.rerun()
            else:
                st.toast("❌ Erro ao salvar. Tente novamente.", icon="❌")


# ══════════════════════════════════════════════════════════════
# FORMULÁRIO 2 — ORÇAMENTO DE PEÇAS
# ══════════════════════════════════════════════════════════════

def render_formulario_orcamento_pecas():
    st.markdown("## 📝 Lançar Orçamento de Peças")

    with st.form(key="form_orc_pecas", clear_on_submit=True):  # [V17-FIX-1]
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

        obs_orc = st.text_area("Observações", placeholder="", height=70)
        submitted = st.form_submit_button("💾 Salvar Orçamento de Peças", type="primary")

        if submitted:
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

    # ── Tabela de orçamentos ───────────────────────────────────
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

    # [V17-FIX-3] Export Excel
    buf = BytesIO()
    df_orc.drop(columns=["id"], errors="ignore").to_excel(buf, index=False)
    kc4.download_button("📥 Exportar Excel", data=buf.getvalue(),
                         file_name="orcamentos_pecas.xlsx",
                         mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         key="dl_orc_excel")

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

        st.markdown('<div style="border-bottom:1px solid rgba(45,55,72,.5);margin:3px 0;"></div>',
                    unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# FORMULÁRIO 3 — CADASTRO DE REVENDAS
# [V17-FIX-2] Sincronização automática com territórios
# ══════════════════════════════════════════════════════════════

# Banco de coordenadas para sincronização automática
_COORDS_REVENDA: dict[str, tuple[float, float]] = {
    "Florianópolis": (-27.5954, -48.5480), "Joinville": (-26.3044, -48.8487),
    "Blumenau": (-26.9194, -49.0661), "Chapecó": (-27.1005, -52.6156),
    "Lages": (-27.8153, -50.3253), "Criciúma": (-28.6773, -49.3700),
    "Campos Novos": (-27.4017, -51.2244), "Xanxerê": (-26.8753, -52.4033),
    "Concórdia": (-27.2344, -52.0278), "Caçador": (-26.7753, -51.0136),
    "São Miguel do Oeste": (-26.7278, -53.5150), "Joaçaba": (-27.1722, -51.5044),
    "Videira": (-27.0072, -51.1558), "Porto Alegre": (-30.0346, -51.2177),
    "Passo Fundo": (-28.2576, -52.4090), "Santa Maria": (-29.6842, -53.8069),
    "Curitiba": (-25.4284, -49.2733), "Londrina": (-23.3045, -51.1696),
    "Maringá": (-23.4205, -51.9333), "Cascavel": (-24.9578, -53.4595),
    "Pato Branco": (-26.2295, -52.6705), "Francisco Beltrão": (-26.0813, -53.0557),
    "Água Doce": (-26.7244, -51.5531), "Catanduvas": (-26.9058, -51.6464),
    "Vargem Bonita": (-26.9789, -51.5300), "Irani": (-27.0217, -51.9014),
    "Presidente Castello Branco": (-27.1542, -51.7297),
    "Jabor": (-27.1, -51.9), "Tangará": (-27.1253, -51.2544),
    "Fraiburgo": (-27.0244, -50.9194), "Curitibanos": (-27.2794, -50.5822),
    "Lebon Régis": (-26.9294, -50.6911), "Monte Carlo": (-27.2161, -50.9736),
    "Brunópolis": (-27.1058, -51.0275), "Anita Garibaldi": (-27.6944, -51.1322),
    "Zortéa": (-27.4833, -51.5594), "Ibiam": (-27.2319, -51.4694),
    "São Lourenço do Oeste": (-26.3589, -52.8519),
    "Palmitos": (-27.0750, -53.1597), "Maravilha": (-26.7647, -53.1892),
    "Pinhalzinho": (-26.8497, -52.9906), "Itapiranga": (-27.1675, -53.7128),
    "Erechim": (-27.6339, -52.2739), "Frederico Westphalen": (-27.3594, -53.3953),
    "Santo Ângelo": (-28.2994, -54.2642), "Ijuí": (-28.3878, -53.9148),
    "Cruz Alta": (-28.6378, -53.6058), "Vacaria": (-28.5122, -50.9336),
    "Guarapuava": (-25.3908, -51.4628), "União da Vitória": (-26.2278, -51.0875),
}


def _sincronizar_revenda_com_territorios(nome_rev: str, cidade_sede: str, estado: str,
                                          responsavel: str, regioes_txt: str):
    """
    [V17-FIX-2] Ao cadastrar uma revenda, adiciona automaticamente ao mapa
    de territórios: (1) a cidade sede e (2) todas as cidades em Regioes_Atuacao.
    Evita duplicatas verificando se já existe o par revenda+cidade.
    """
    try:
        df_terr = ler_territorios()
        ja_existem = set()
        if not df_terr.empty and "Revenda" in df_terr.columns and "Cidade" in df_terr.columns:
            for _, r in df_terr.iterrows():
                if str(r.get("Revenda","")).strip() == nome_rev:
                    ja_existem.add(str(r.get("Cidade","")).strip())

        cidades = []
        # Cidade sede
        if cidade_sede.strip():
            cidades.append(cidade_sede.strip())
        # Cidades de atuação
        if regioes_txt.strip():
            for c in regioes_txt.split(","):
                c = c.strip()
                if c and c not in cidades:
                    cidades.append(c)

        adicionadas = 0
        for cidade in cidades:
            if cidade in ja_existem:
                continue
            reg = {
                "Revenda":       nome_rev,
                "Representante": responsavel,
                "Cidade":        cidade,
                "Estado":        estado.upper(),
                "Observacoes":   f"Importado do cadastro de revendas",
            }
            if adicionar_territorio(reg):
                adicionadas += 1

        return adicionadas
    except Exception as e:
        st.warning(f"⚠️ Erro ao sincronizar territórios: {e}")
        return 0


def render_formulario_revendas():
    st.markdown("## 🏬 Cadastro de Revendas")

    with st.form(key="form_revenda_cadastro", clear_on_submit=True):  # [V17-FIX-1]
        col1, col2 = st.columns(2)
        with col1:
            nome_rev    = st.text_input("Nome da Revenda",  placeholder="Ex: Agro Sul Implementos")
            cnpj        = st.text_input("CNPJ",              placeholder="00.000.000/0001-00")
        with col2:
            cidade      = st.text_input("Cidade Sede",       placeholder="Ex: Chapecó")
            estado      = st.text_input("Estado (UF)",       placeholder="Ex: SC", max_chars=2)
            responsavel = st.text_input("Responsável",       placeholder="Nome do contato principal")
        regioes = st.text_area("Cidades de Atuação (separe por vírgula)",
                               placeholder="Ex: Chapecó, Xanxerê, Concórdia, Água Doce...", height=80)
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
                # [V17-FIX-2] Sincroniza automaticamente com territórios
                n_terr = _sincronizar_revenda_com_territorios(
                    nome_rev.strip(), cidade.strip(), estado.strip(),
                    responsavel.strip(), regioes.strip()
                )
                msg = f"✅ Revenda cadastrada!"
                if n_terr > 0:
                    msg += f" {n_terr} cidade(s) adicionada(s) ao mapa de territórios."
                st.toast(msg, icon="✅")
                st.rerun()

    _df_rev = ler_revendas_cadastro()
    lista = _df_rev.to_dict('records') if not _df_rev.empty else []
    if lista:
        st.divider()

        # [V17-FIX-3] Export Excel
        col_tit, col_exp = st.columns([3, 1])
        col_tit.subheader(f"📋 Revendas Cadastradas ({len(lista)})")
        buf = BytesIO()
        _df_rev.drop(columns=["id"], errors="ignore").to_excel(buf, index=False)
        col_exp.download_button("📥 Exportar Excel", data=buf.getvalue(),
                                 file_name="revendas.xlsx",
                                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 key="dl_rev_excel")

        for rev in lista:
            row_id = rev.get("id")
            cols = st.columns([3, 2, 2, 2, 2, 1])
            cols[0].write(f"**{rev.get('Nome_Revenda','—')}**")
            cols[1].write(f"{rev.get('Cidade','—')} / {rev.get('Estado','—')}")
            cols[2].write(rev.get("CNPJ","—"))
            cols[3].write(rev.get("Responsavel","—"))
            reg_txt = rev.get("Regioes_Atuacao","—")
            cols[4].write(reg_txt[:40] + "..." if len(str(reg_txt)) > 40 else reg_txt)
            if cols[5].button("🗑", key=f"del_rev_{row_id}"):
                if excluir_revenda_cadastro(row_id):
                    st.toast("Revenda removida.", icon="🗑")
                    st.rerun()
    else:
        st.info("Nenhuma revenda cadastrada ainda.")
