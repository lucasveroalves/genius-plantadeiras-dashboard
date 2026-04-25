"""
app.py — Genius Implementos Agrícolas v15

Alterações aplicadas:
  [WHITE-1]  CSS whitelabel injeta no boot: oculta MainMenu, footer, header,
             DeployButton e stToolbar.
  [FIX-DATE] Filtro de data agora é totalmente livre — sem travar nas datas
             mínima/máxima do DataFrame. Usa today() como default do range
             superior quando df estiver vazio.
  [DB-MIGR]  Após upload da planilha Senior, dispara
             importar_pecas_senior_para_supabase(df) antes de exibir dados.
  [EST-MIN]  Nova sub-aba "📐 Estoque Mínimo por Revenda" baseada em
             Pandas puro — sem IA, matemática determinística.
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta

from auth import tela_login, painel_usuario, render_painel_admin, is_admin, abas_permitidas
from data.loader import (
    preparar_pecas, calcular_kpis_pecas,
    calcular_curva_abc_por_codigo, calcular_top10_revendas,
)
from components.ui import (
    render_header, render_sidebar_uploads,
    render_banner_mock_pecas, render_auto_refresh,
)
from components.estoque      import render_aba_estoque
from components.producao     import render_aba_pcp
from components.forms        import (
    render_formulario_negociacao,
    render_formulario_orcamento_pecas,
    render_formulario_revendas,
)
try:
    from components.tab_crm_maquinas import render_aba_crm_maquinas
except ImportError:
    def render_aba_crm_maquinas():
        st.error("Módulo CRM não encontrado. Verifique components/tab_crm_maquinas.py")
from components.nf_demo      import render_aba_nf_demo
from data.db                 import ler_orcamentos, importar_pecas_senior_para_supabase, importar_catalogo_pecas, ler_catalogo_pecas, ler_lancamentos_pecas
try:
    from components.tab_territorios import render_aba_territorios
except ImportError:
    def render_aba_territorios():
        st.error("Módulo Territórios não encontrado.")
from charts.plots            import grafico_curva_abc, grafico_ranking_revendas_pecas, grafico_top_produtos

# ══════════════════════════════════════════════════════════════
# PAGE CONFIG  (deve ser a PRIMEIRA chamada Streamlit)
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Genius Implementos Agrícolas",
    layout="wide",
    page_icon="🌾",
)

# ══════════════════════════════════════════════════════════════
# [WHITE-1]  CSS WHITELABEL — oculta todos os elementos nativos
# ══════════════════════════════════════════════════════════════
_WHITELABEL_CSS = """
<style>
  /* Menu hambúrguer */
  #MainMenu { visibility: hidden !important; display: none !important; }

  /* Footer "Made with Streamlit" */
  footer { visibility: hidden !important; display: none !important; }

  /* Header topo (manage app, star, share) */
  header[data-testid="stHeader"] { display: none !important; }

  /* Botão Deploy (nuvem) */
  .stDeployButton { display: none !important; }

  /* Toolbar de ferramentas (Rerun, Settings…) */
  [data-testid="stToolbar"] { display: none !important; }

  /* Padding extra que o header removia */
  .block-container { padding-top: 1.5rem !important; }
</style>
"""
st.markdown(_WHITELABEL_CSS, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# 1. Autenticação
# ══════════════════════════════════════════════════════════════
if not tela_login():
    st.stop()

# ══════════════════════════════════════════════════════════════
# 2. Sidebar
# ══════════════════════════════════════════════════════════════
painel_usuario()
_peca_file, _catalogo_file = render_sidebar_uploads()

# ══════════════════════════════════════════════════════════════
# 3. Dados de Peças
#    [DB-MIGR] Se o usuário fez upload, importa para o Supabase
#              antes de preparar o df em memória.
# ══════════════════════════════════════════════════════════════
# ── Importa catálogo de descrições ───────────────────────────
if _catalogo_file is not None and not st.session_state.get("_catalogo_importado"):
    with st.spinner("📚 Importando catálogo de peças..."):
        try:
            import pandas as _pd_cat
            df_cat = _pd_cat.read_excel(_catalogo_file, header=4)
            df_cat = df_cat[["CÓDIGO","DESCRIÇÃO"]].dropna(subset=["CÓDIGO","DESCRIÇÃO"])
            df_cat.columns = ["Codigo","Descricao"]
            df_cat["Codigo"] = df_cat["Codigo"].astype(str).str.strip()
            df_cat = df_cat[df_cat["Codigo"].str.match(r"^\d+$")]
            n_cat, msg_cat = importar_catalogo_pecas(df_cat)
            if msg_cat == "OK":
                st.sidebar.success(f"✅ {n_cat} descrições importadas!")
                st.session_state["_catalogo_importado"] = True
            else:
                st.sidebar.error(f"❌ Catálogo: {msg_cat}")
        except Exception as e:
            st.sidebar.error(f"❌ Erro ao ler catálogo: {e}")

if _peca_file is not None and not st.session_state.get("_pecas_importadas"):
    with st.spinner("⬆️ Carregando planilha e importando para o banco..."):
        # preparar_pecas já faz o parse; pegamos o df bruto para upsert
        df_raw, _ = preparar_pecas(_peca_file)
        if not df_raw.empty:
            n_ok, msg_imp = importar_pecas_senior_para_supabase(df_raw)
            if msg_imp == "OK":
                st.sidebar.success(f"✅ {n_ok} linha(s) importadas para o Supabase!")
                st.session_state["_pecas_importadas"] = True
            else:
                st.sidebar.error(f"❌ Importação: {msg_imp}")

df_pecas, is_mock_pecas = preparar_pecas(_peca_file)

# ── Enriquece df_pecas com descrições do catálogo ─────────────
if not df_pecas.empty and not is_mock_pecas:
    df_cat_desc = ler_catalogo_pecas()
    if not df_cat_desc.empty:
        col_cod = next((c for c in ["Codigo","Produto","produto"] if c in df_pecas.columns), None)
        if col_cod:
            df_pecas = df_pecas.copy()
            df_pecas["_cod_str"] = df_pecas[col_cod].astype(str).str.strip()
            df_cat_desc["Codigo"] = df_cat_desc["Codigo"].astype(str).str.strip()
            mapa = df_cat_desc.set_index("Codigo")["Descricao"].to_dict()
            df_pecas["Descricao_Peca"] = df_pecas["_cod_str"].map(mapa)
            df_pecas = df_pecas.drop(columns=["_cod_str"])

# ══════════════════════════════════════════════════════════════
# 4. Header + Auto-refresh
# ══════════════════════════════════════════════════════════════
render_header()
render_auto_refresh()


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def _filtrar_pecas_por_perfil(df: pd.DataFrame, perfil: str) -> pd.DataFrame:
    """Remove colunas financeiras para perfil PCP."""
    if perfil == "pcp":
        cols_remover = [c for c in ["Valor_Unitario", "Valor_Total"] if c in df.columns]
        if cols_remover:
            return df.drop(columns=cols_remover)
    return df


def _calcular_estoque_minimo(df: pd.DataFrame, lead_time_dias: int = 15) -> pd.DataFrame:
    """
    [EST-MIN] Calcula estoque mínimo por (Peça × Revenda) usando Pandas puro.

    Fórmula:
        estoque_minimo = media_vendas_diarias × lead_time_dias

    Onde:
        media_vendas_diarias = total_qty_no_periodo / dias_no_periodo

    Colunas esperadas no df:
        Data_Venda  (datetime), Codigo_Peca (str), Descricao (str),
        Revenda (str), Quantidade (numeric), Estoque_Atual (numeric, opcional)

    Retorna DataFrame com colunas:
        Codigo_Peca, Descricao, Revenda,
        Total_Vendido, Media_Diaria, Estoque_Minimo_Sugerido,
        Estoque_Atual, Abaixo_Minimo (bool)
    """
    if df is None or df.empty:
        return pd.DataFrame()

    colunas_necessarias = {"Data_Venda", "Codigo_Peca", "Quantidade", "Revenda"}
    if not colunas_necessarias.issubset(df.columns):
        return pd.DataFrame()

    df = df.copy()
    df["Data_Venda"] = pd.to_datetime(df["Data_Venda"], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["Data_Venda", "Codigo_Peca", "Quantidade"])
    df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce").fillna(0)

    if df.empty:
        return pd.DataFrame()

    # Período do histórico disponível
    data_ini = df["Data_Venda"].min()
    data_fim = df["Data_Venda"].max()
    dias_periodo = max((data_fim - data_ini).days, 1)

    # Agrupamento por Peça + Revenda
    grp = (
        df.groupby(["Codigo_Peca", "Revenda"], as_index=False)
        .agg(
            Descricao=("Descricao", "first") if "Descricao" in df.columns else ("Codigo_Peca", "first"),
            Total_Vendido=("Quantidade", "sum"),
        )
    )

    grp["Media_Diaria"]           = grp["Total_Vendido"] / dias_periodo
    grp["Estoque_Minimo_Sugerido"] = (grp["Media_Diaria"] * lead_time_dias).round(1)

    # Estoque atual — coluna opcional; se não existir, assume 0
    if "Estoque_Atual" in df.columns:
        est_atual = (
            df.groupby(["Codigo_Peca", "Revenda"])["Estoque_Atual"]
            .last()
            .reset_index()
        )
        grp = grp.merge(est_atual, on=["Codigo_Peca", "Revenda"], how="left")
        grp["Estoque_Atual"] = pd.to_numeric(grp["Estoque_Atual"], errors="coerce").fillna(0)
    else:
        grp["Estoque_Atual"] = 0.0

    grp["Abaixo_Minimo"] = grp["Estoque_Atual"] < grp["Estoque_Minimo_Sugerido"]

    # Ordena: abaixo do mínimo primeiro, depois maior venda
    grp = grp.sort_values(
        ["Abaixo_Minimo", "Total_Vendido"],
        ascending=[False, False],
    ).reset_index(drop=True)

    return grp


# ══════════════════════════════════════════════════════════════
# ABA PEÇAS
# ══════════════════════════════════════════════════════════════

def _render_aba_pecas(df_pecas_arg, is_mock_pecas_arg):
    perfil = st.session_state.get("perfil_atual", "comercial")

    if is_mock_pecas_arg:
        render_banner_mock_pecas()
        return

    st.header("🔧 Análise de Peças")

    # ── [FIX-DATE] Filtro de Período Dinâmico ─────────────────
    # Não trava nas datas do df: usuário pode escolher livremente.
    hoje = date.today()
    col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
    default_ini = date(2020, 1, 1)
    default_fim = hoje
    with col_f1:
        d0 = st.date_input("De", value=default_ini, format="DD/MM/YYYY", key="peca_d0")
    with col_f2:
        d1 = st.date_input("Até", value=default_fim, format="DD/MM/YYYY", key="peca_d1")
    with col_f3:
        st.write("")
        st.write("")
        if st.button("🔄 Aplicar", key="peca_btn_filtro"):
            st.rerun()

    if not df_pecas_arg.empty and "Data_Venda" in df_pecas_arg.columns:
        dv = df_pecas_arg["Data_Venda"]
        if hasattr(dv.dt, "tz") and dv.dt.tz is not None:
            dv = dv.dt.tz_localize(None)
        df_filtrado = df_pecas_arg[(dv.dt.date >= d0) & (dv.dt.date <= d1)]
    else:
        df_filtrado = df_pecas_arg

    df_para_calculos = _filtrar_pecas_por_perfil(df_filtrado, perfil)

    # ── Orçamentos ─────────────────────────────────────────────
    df_orc = ler_orcamentos()
    orc_faturados = 0.0
    orc_aguardando = 0.0
    if not df_orc.empty and "Status_Orc" in df_orc.columns:
        orc_faturados  = pd.to_numeric(df_orc.loc[df_orc["Status_Orc"]=="Faturado",  "Valor_Total"], errors="coerce").fillna(0).sum()
        orc_aguardando = pd.to_numeric(df_orc.loc[df_orc["Status_Orc"]=="Aguardando","Valor_Total"], errors="coerce").fillna(0).sum()
    pecas_em_orc = 0.0
    if not df_orc.empty and "Status_Orc" in df_orc.columns:
        mask = df_orc["Status_Orc"].isin(["Aguardando"])
        pecas_em_orc = pd.to_numeric(
            df_orc.loc[mask, "Valor_Total"], errors="coerce"
        ).fillna(0).sum()

    # ── KPIs ───────────────────────────────────────────────────
    if perfil == "comercial":
        # df_orc sem filtro de período — orçamentos lançados hoje sempre somam
        kpis = calcular_kpis_pecas(df_filtrado, df_orc)
    else:
        kpis = calcular_kpis_pecas(df_para_calculos)

    def _brl(v):
        try:
            return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "R$ 0,00"

    def _card(label, value):
        st.markdown(
            f'<div style="background:#1F2937;border:1px solid #2D3748;'
            f'border-left:4px solid #E36C2C;border-radius:10px;'
            f'padding:14px 16px 10px;min-height:80px;">'
            f'<div style="font-size:11px;font-weight:700;color:#6A7A8A;'
            f'text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;">{label}</div>'
            f'<div style="font-size:1.35rem;font-weight:700;color:#F0F4F8;'
            f'word-break:break-word;">{value}</div></div>',
            unsafe_allow_html=True,
        )

    if perfil == "comercial":
        c1, c2, c3, c4, c5 = st.columns(5)
        total_com_orc = kpis["total_faturado"] + orc_faturados
        with c1: _card("💰 Total Faturado",  _brl(total_com_orc))
        with c2: _card("⏳ Orc. Aguardando", _brl(orc_aguardando))
        with c3: _card("📦 Volume de Itens",  f"{int(kpis['volume_itens']):,}".replace(",", "."))
        with c4: _card("🎟️ Ticket Médio",     _brl(kpis["ticket_medio"]))
        with c5: _card("🏷️ SKUs Ativos",      str(kpis["qtd_skus"]))
        st.divider()
    else:
        c1, c2 = st.columns(2)
        with c1: _card("📦 Volume de Itens", f"{int(kpis['volume_itens']):,}".replace(",", "."))
        with c2: _card("🏷️ SKUs Ativos",     str(kpis["qtd_skus"]))
        st.divider()

    # ── Curva ABC — inclui orçamentos manuais Faturados ──────
    # Monta df extra dos orçamentos para enriquecer a curva e o top10
    # Orçamentos faturados para ABC
    df_orc_para_abc = pd.DataFrame()
    if not df_orc.empty and "Status_Orc" in df_orc.columns:
        df_fat_orc = df_orc[df_orc["Status_Orc"] == "Faturado"].copy()
        if not df_fat_orc.empty:
            df_orc_para_abc = pd.DataFrame({
                "Codigo":          df_fat_orc.get("Nr_Pedido", pd.Series(dtype=str)),
                "Descricao_Peca":  df_fat_orc.get("Cliente_Revenda", pd.Series(dtype=str)),
                "Valor_Total":     pd.to_numeric(df_fat_orc.get("Valor_Total", pd.Series(dtype=float)), errors="coerce").fillna(0),
                "Cliente_Revenda": df_fat_orc.get("Cliente_Revenda", pd.Series(dtype=str)),
            })

    # Lançamentos manuais de peças (itens individuais com código)
    df_lanc = ler_lancamentos_pecas()
    df_lanc_para_abc = pd.DataFrame()
    if not df_lanc.empty:
        df_lanc_fat = df_lanc[df_lanc.get("Status_Lanc", pd.Series(dtype=str)) == "Faturado"] if "Status_Lanc" in df_lanc.columns else df_lanc
        if not df_lanc_fat.empty:
            df_lanc_para_abc = pd.DataFrame({
                "Codigo":          df_lanc_fat.get("Codigo", pd.Series(dtype=str)).astype(str),
                "Descricao_Peca":  df_lanc_fat.get("Descricao", pd.Series(dtype=str)),
                "Valor_Total":     pd.to_numeric(df_lanc_fat.get("Valor_Total", pd.Series(dtype=float)), errors="coerce").fillna(0),
                "Cliente_Revenda": df_lanc_fat.get("Cliente_Revenda", pd.Series(dtype=str)),
                "Quantidade":      pd.to_numeric(df_lanc_fat.get("Quantidade", pd.Series(dtype=float)), errors="coerce").fillna(0),
            })

    df_para_calculos_enriquecido = pd.concat(
        [df_para_calculos, df_orc_para_abc, df_lanc_para_abc],
        ignore_index=True
    )
    df_abc = calcular_curva_abc_por_codigo(df_para_calculos_enriquecido, top_n=20)
    # df_completo para pie chart calcular distribuição A/B/C real
    df_abc_completo = calcular_curva_abc_por_codigo(df_para_calculos_enriquecido, top_n=99999)

    if perfil == "comercial":
        col_abc, col_rev = st.columns(2)
        with col_abc:
            st.subheader("📊 Curva ABC – Peças Mais Vendidas")
            if not df_abc_completo.empty:
                st.plotly_chart(grafico_curva_abc(df_abc_completo), use_container_width=True)
                # Top 15 por cada classe A, B, C
                for _classe, _emoji, _cor in [("A","🟠","#E67E22"),("B","🟢","#3D9970"),("C","🔵","#2A5A8A")]:
                    _df_classe = df_abc_completo[df_abc_completo["Curva"] == _classe] if "Curva" in df_abc_completo.columns else pd.DataFrame()
                    if not _df_classe.empty:
                        st.markdown(f"##### {_emoji} Top 15 Produtos — Classe {_classe}")
                        st.plotly_chart(grafico_top_produtos(_df_classe, top_n=15), use_container_width=True)
            else:
                st.info("Sem dados para Curva ABC.")
        with col_rev:
            st.subheader("🏆 Top 10 Revendas")
            # Combina planilha Senior + orçamentos manuais Faturados
            df_orc_fat = pd.DataFrame()
            if not df_orc.empty and "Status_Orc" in df_orc.columns:
                df_orc_fat = df_orc[df_orc["Status_Orc"] == "Faturado"][["Cliente_Revenda","Valor_Total"]].copy()
                df_orc_fat["Valor_Total"] = pd.to_numeric(df_orc_fat["Valor_Total"], errors="coerce").fillna(0)
            df_para_top10 = pd.concat([
                df_filtrado[["Cliente_Revenda","Valor_Total"]] if not df_filtrado.empty else pd.DataFrame(),
                df_orc_fat,
            ], ignore_index=True) if not df_orc_fat.empty else df_filtrado
            df_top10 = calcular_top10_revendas(df_para_top10)
            if not df_top10.empty:
                st.plotly_chart(
                    grafico_ranking_revendas_pecas(df_top10, top_n=10),
                    use_container_width=True,
                )
            else:
                st.info("Sem dados de revendas.")
    else:
        st.subheader("📊 Curva ABC – Previsão de Estoque Mínimo de Peças")
        if not df_abc.empty:
            st.plotly_chart(grafico_curva_abc(df_abc_completo), use_container_width=True)
        else:
            st.info("Sem dados para Curva ABC.")

        if not df_orc.empty and "Status_Orc" in df_orc.columns:
            st.divider()
            st.subheader("📋 Orçamentos de Peças em Aberto")
            df_orc_view = df_orc[df_orc["Status_Orc"] == "Aguardando"][
                ["Nr_Pedido", "Data_Orcamento", "Cliente_Revenda", "Valor_Total", "Status_Orc"]
            ]
            st.dataframe(df_orc_view, use_container_width=True, height=300)

    if perfil == "comercial":
        st.divider()

        _render_abc_por_revenda(df_filtrado)


# ══════════════════════════════════════════════════════════════
# [EST-MIN]  Sub-aba: Estoque Mínimo por Revenda
# ══════════════════════════════════════════════════════════════

def _render_estoque_minimo(df: pd.DataFrame):
    st.markdown("""
<div style="display:flex;align-items:center;gap:14px;padding:10px 0 18px;
            border-bottom:1px solid #2D3748;margin-bottom:20px;">
  <div style="background:rgba(52,183,120,.13);border:1px solid rgba(52,183,120,.4);
              border-radius:10px;padding:10px 14px;font-size:22px;">📐</div>
  <div>
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:1.7rem;
                font-weight:700;color:#F0F4F8;line-height:1.1;">
      Estoque Mínimo por Revenda</div>
    <div style="font-size:12px;color:#6A7A8A;text-transform:uppercase;
                letter-spacing:.07em;margin-top:4px;">
      Fórmula: Média de Vendas Diárias × Lead Time (dias) · Sem IA · Pandas puro</div>
  </div>
</div>""", unsafe_allow_html=True)

    col_lt, col_btn = st.columns([2, 1])
    with col_lt:
        lead_time = st.number_input(
            "Lead Time (dias)", min_value=1, max_value=90,
            value=15, step=1, key="est_min_lead",
            help="Quantidade de dias que leva para reabastecer o estoque.",
        )
    with col_btn:
        st.write("")
        calcular = st.button("⚙️ Calcular", key="btn_calcular_estmin", type="primary")

    if not calcular and "df_estmin_cache" not in st.session_state:
        st.info("Clique em **Calcular** para gerar a análise de estoque mínimo.")
        return

    with st.spinner("Calculando estoque mínimo..."):
        df_estmin = _calcular_estoque_minimo(df, lead_time_dias=int(lead_time))
        st.session_state["df_estmin_cache"] = df_estmin
    
    df_estmin = st.session_state.get("df_estmin_cache", pd.DataFrame())

    if df_estmin.empty:
        st.warning("⚠️ Não foi possível calcular. Verifique se o DataFrame contém as colunas: "
                   "`Data_Venda`, `Codigo_Peca`, `Quantidade`, `Revenda`.")
        return

    # ── KPIs rápidos ───────────────────────────────────────────
    total_itens   = len(df_estmin)
    abaixo_count  = int(df_estmin["Abaixo_Minimo"].sum())
    pct_critico   = (abaixo_count / total_itens * 100) if total_itens else 0

    k1, k2, k3 = st.columns(3)
    k1.metric("📦 Combinações Peça × Revenda", f"{total_itens:,}".replace(",", "."))
    k2.metric("🔴 Abaixo do Mínimo",           f"{abaixo_count:,}".replace(",", "."))
    k3.metric("⚠️ % Crítico",                  f"{pct_critico:.1f}%")

    st.divider()

    # ── Filtros de exibição ────────────────────────────────────
    col_f1, col_f2 = st.columns([3, 1])
    with col_f1:
        busca = st.text_input("🔍 Filtrar por peça ou revenda", key="est_min_busca",
                               placeholder="Ex: 123456 ou Revenda João")
    with col_f2:
        apenas_criticos = st.checkbox("Mostrar só críticos 🔴", key="est_min_criticos")

    df_show = df_estmin.copy()
    if apenas_criticos:
        df_show = df_show[df_show["Abaixo_Minimo"]]
    if busca.strip():
        mask = (
            df_show["Codigo_Peca"].astype(str).str.contains(busca, case=False, na=False)
            | df_show["Revenda"].astype(str).str.contains(busca, case=False, na=False)
        )
        df_show = df_show[mask]

    # ── Tabela estilizada ──────────────────────────────────────
    # Highlight vermelho em linhas abaixo do mínimo
    def _highlight_critico(row):
        cor = "background-color: rgba(232,64,64,.18); color: #E87878;" if row["Abaixo_Minimo"] else ""
        return [cor] * len(row)

    cols_exibir = [c for c in [
        "Codigo_Peca", "Descricao", "Revenda",
        "Total_Vendido", "Media_Diaria",
        "Estoque_Minimo_Sugerido", "Estoque_Atual", "Abaixo_Minimo",
    ] if c in df_show.columns]

    styled = (
        df_show[cols_exibir]
        .style
        .apply(_highlight_critico, axis=1)
        .format({
            "Total_Vendido":           "{:.0f}",
            "Media_Diaria":            "{:.2f}",
            "Estoque_Minimo_Sugerido": "{:.1f}",
            "Estoque_Atual":           "{:.1f}",
        })
    )

    st.dataframe(styled, use_container_width=True, height=500)
    st.caption(
        f"🔢 {len(df_show):,} linha(s) exibida(s) · "
        f"Lead time: {int(lead_time)} dias · "
        f"Fórmula: Estoque Mín. = Média Diária × {int(lead_time)}"
    )

    # ── Download CSV ───────────────────────────────────────────
    csv_bytes = df_show[cols_exibir].to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button(
        "📥 Exportar tabela (.csv)",
        data=csv_bytes,
        file_name=f"estoque_minimo_lead{int(lead_time)}d.csv",
        mime="text/csv",
        key="dl_estmin",
    )


# ══════════════════════════════════════════════════════════════
# 5. Define abas visíveis para este usuário
# ══════════════════════════════════════════════════════════════
MAPA = {
    "📝 Orçamento de Peças":   lambda: render_formulario_orcamento_pecas(),
    "🏬 Revendas":             lambda: render_formulario_revendas(),
    "🤝 Pipeline Máquinas":    lambda: render_aba_crm_maquinas(),
    "⚙️ PCP":                  lambda: render_aba_pcp(),
    "📦 Estoque de Máquinas":  lambda: render_aba_estoque(),
    "📄 NF em Demonstração":   lambda: render_aba_nf_demo(),
    "🔧 Peças":                lambda df=df_pecas, mock=is_mock_pecas: _render_aba_pecas(df, mock),
    "🗺️ Territórios":          lambda: render_aba_territorios(),
}

permitidas = abas_permitidas()

# Sessão parcial: se autenticado mas sem abas, força novo login
if not permitidas and st.session_state.get("autenticado"):
    st.warning(
        "⚠️ Sessão expirada ou permissões não carregadas. "
        "Por favor, faça login novamente."
    )
    for k in ["autenticado", "usuario_atual", "perfil_atual",
              "nome_usuario", "is_admin", "abas_permitidas"]:
        st.session_state.pop(k, None)
    st.rerun()

abas_visiveis = [a for a in MAPA if a in permitidas]

if is_admin():
    abas_visiveis.append("👤 Admin")

tabs = st.tabs(abas_visiveis)

for tab, nome in zip(tabs, abas_visiveis):
    with tab:
        if nome == "👤 Admin":
            render_painel_admin()
        else:
            MAPA[nome]()
