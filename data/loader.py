"""
data/loader.py — Genius Implementos Agrícolas v16

Correções aplicadas:
  [FIX-BUG-4]  calcular_kpis_pecas: df_orc filtrado pelo mesmo período das peças
  [FIX-PERF-5] limpar_moeda_brl: pipeline vetorizado (10-50x mais rápido)
  [FIX-PERF-6] @st.cache_data com ttl=300 por entrada
  [FIX-BUG-2]  tz_convert(None) para dados tz-aware
  [FIX-BUG-3]  dropna() antes de comparação de datas
  [FIX-SENIOR] Reescrita completa baseada na estrutura real do Senior ERP:
               - Cabeçalho detectado automaticamente por varredura (geralmente linha 4)
               - Coluna "Produto"       → Codigo da peça (ex: 200001114)
               - Coluna "Cliente"       → código numérico (ignorado)
               - Coluna unnamed após "Cliente" → Nome do cliente → Cliente_Revenda
               - Coluna "Emissão"       → Data_Venda
               - Linhas "Família:" removidas automaticamente
               - Dados da planilha ACUMULAM com lançamentos manuais (nunca sobrescrevem)
"""

from __future__ import annotations
import io, unicodedata, hashlib
import pandas as pd
import streamlit as st
from data.db import salvar_cache_pecas, ler_cache_pecas


# ── Utilitários ───────────────────────────────────────────────

def _norm_col(c: str) -> str:
    return (unicodedata.normalize("NFKD", str(c))
            .encode("ascii", "ignore").decode("ascii")
            .strip().replace(" ", "_").replace(".", "_"))

def limpar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [_norm_col(c) for c in df.columns]
    return df

def limpar_moeda_brl(serie: pd.Series) -> pd.Series:
    """[FIX-PERF-5] Conversão vetorizada."""
    if pd.api.types.is_numeric_dtype(serie):
        return serie.fillna(0.0).astype(float)
    s = (serie.astype(str)
         .str.replace(r"R\$", "", regex=True)
         .str.replace(r"\s+", "", regex=True))
    mask_br = s.str.contains(",", na=False) & ~s.str.match(r"^\d+\.\d{1,2}$", na=False)
    s_br = s[mask_br].str.replace(r"\.", "", regex=True).str.replace(",", ".", regex=False)
    s_en = s[~mask_br]
    result = pd.Series(index=serie.index, dtype=float)
    result[mask_br] = pd.to_numeric(s_br, errors="coerce")
    result[~mask_br] = pd.to_numeric(s_en, errors="coerce")
    return result.fillna(0.0)

def criar_mock_pecas() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "Codigo", "Descricao_Peca", "Quantidade", "Valor_Unitario",
        "Valor_Total", "Cliente_Revenda", "Data_Venda", "Status_Peca",
    ])


# ── Leitura do arquivo Senior ERP ────────────────────────────

def _encontrar_linha_cabecalho(df_raw: pd.DataFrame) -> int:
    """
    Varre o DataFrame (lido sem header) procurando a linha que contém
    ao menos 2 das palavras-chave do relatório Senior.
    Retorna o índice da linha ou 4 como fallback.
    """
    keywords = {"emissao", "emissao_", "produto", "vlr", "cliente",
                "qtde", "preco", "serie", "numero"}
    for i in range(min(20, len(df_raw))):
        row_vals = set()
        for v in df_raw.iloc[i].values:
            if pd.notna(v):
                norm = (unicodedata.normalize("NFKD", str(v))
                        .encode("ascii", "ignore").decode("ascii")
                        .strip().lower().replace(".", "_").replace(" ", "_"))
                row_vals.add(norm)
        if len(row_vals & keywords) >= 2:
            return i
    return 4


def _ler_senior_xlsx(file_bytes: bytes) -> pd.DataFrame:
    """
    Lê o xlsx do Senior em duas passagens:
    1. Sem header para detectar a linha do cabeçalho
    2. Com header na linha detectada
    """
    df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None, engine="openpyxl")
    header_row = _encontrar_linha_cabecalho(df_raw)
    df = pd.read_excel(io.BytesIO(file_bytes), header=header_row, engine="openpyxl")
    return df


def _processar_senior(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza o DataFrame bruto do Senior para o schema interno.

    Regra especial para Cliente_Revenda:
      Senior exporta CÓDIGO em "Cliente" e NOME na coluna unnamed seguinte.
      Precisamos do NOME para o Top 10 Revendas.
    """
    # ── Passo 1: capturar coluna de nome do cliente ANTES de normalizar ──
    cols_orig = list(df.columns)
    nome_cliente_col_orig = None
    for i, col in enumerate(cols_orig):
        if str(col).strip().lower() == "cliente":
            if i + 1 < len(cols_orig):
                prox = str(cols_orig[i + 1]).strip()
                # Coluna unnamed ou vazia após "Cliente" = nome do cliente
                if prox.startswith("Unnamed") or prox == "" or prox.lower() == "nan":
                    nome_cliente_col_orig = cols_orig[i + 1]
            break

    # ── Passo 2: normalizar nomes de colunas ─────────────────────────
    df = limpar_colunas(df)

    # Nome normalizado da coluna do cliente (para usar no rename_map)
    nome_cliente_col_norm = (_norm_col(str(nome_cliente_col_orig))
                             if nome_cliente_col_orig is not None else None)

    # ── Passo 3: renomear para schema interno ────────────────────────
    mapeamento = {
        "Emissao":           "Data_Venda",
        "Emissao_":          "Data_Venda",   # "Emissão" → após _norm_col
        "Data":              "Data_Venda",
        "Produto":           "Codigo",
        "Qtde_Fat_":         "Quantidade",
        "Quantidade":        "Quantidade",
        "Preco_Un_":         "Valor_Unitario",
        "Vlr_Liq_":          "Valor_Total",
        "Descricao":         "Descricao_Peca",
        "Descricao_Produto": "Descricao_Peca",
    }

    # Mapeia a coluna de nome do cliente identificada acima
    if nome_cliente_col_norm and nome_cliente_col_norm in df.columns:
        mapeamento[nome_cliente_col_norm] = "Cliente_Revenda"
    elif "Cliente" in df.columns:
        # Fallback: usa o campo "Cliente" (código numérico) se não achou o nome
        mapeamento["Cliente"] = "Cliente_Revenda"

    rename_map = {k: v for k, v in mapeamento.items()
                  if k in df.columns and k != v}
    df = df.rename(columns=rename_map)

    # ── Passo 4: remover linhas de agrupamento por Família ───────────
    if "Serie" in df.columns:
        df = df[~df["Serie"].astype(str).str.strip().str.lower().isin(
            ["família:", "familia:", "familia", "família", "famlia:"]
        )]
    if "Codigo" in df.columns:
        df = df[~df["Codigo"].astype(str).str.contains(
            r"Família|Familia|^nan$", na=False, regex=True
        )]

    # ── Passo 5: filtrar apenas linhas com código de peça válido ─────
    if "Codigo" in df.columns:
        df = df.dropna(subset=["Codigo"])
        # Produto vem como float (200001114.0) do Excel — converter para int string
        def _norm_codigo(v):
            try:
                return str(int(float(str(v).strip())))
            except Exception:
                return str(v).strip()
        df["Codigo"] = df["Codigo"].apply(_norm_codigo)
        df = df[df["Codigo"] != ""]
        df = df[df["Codigo"].str.lower() != "nan"]
        # Códigos Senior são numéricos (ex: 200001114)
        df = df[df["Codigo"].str.match(r"^\d+$", na=False)]

    if df.empty:
        return df

    # ── Passo 6: converter tipos ──────────────────────────────────────
    if "Quantidade" in df.columns:
        df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce").fillna(0)

    for col in ["Valor_Unitario", "Valor_Total"]:
        if col in df.columns:
            df[col] = limpar_moeda_brl(df[col])

    if "Data_Venda" in df.columns:
        df["Data_Venda"] = pd.to_datetime(df["Data_Venda"], errors="coerce")
        if df["Data_Venda"].dt.tz is not None:
            df["Data_Venda"] = df["Data_Venda"].dt.tz_convert(None)
        df = df.dropna(subset=["Data_Venda"])

    # ── Passo 7: limpar Cliente_Revenda ──────────────────────────────
    if "Cliente_Revenda" not in df.columns:
        df["Cliente_Revenda"] = "Não informado"
    else:
        df["Cliente_Revenda"] = (df["Cliente_Revenda"]
                                 .fillna("Não informado")
                                 .astype(str).str.strip())
        df.loc[df["Cliente_Revenda"].isin(["", "nan"]), "Cliente_Revenda"] = "Não informado"

    # ── Passo 8: colunas obrigatórias ─────────────────────────────────
    df["Status_Peca"] = "Faturado"
    for col in ["Codigo", "Descricao_Peca", "Quantidade", "Valor_Unitario",
                "Valor_Total", "Cliente_Revenda", "Data_Venda", "Status_Peca"]:
        if col not in df.columns:
            df[col] = "" if col not in ["Quantidade", "Valor_Unitario", "Valor_Total"] else 0.0

    return df.reset_index(drop=True)


# ── Cache e processamento ─────────────────────────────────────

def _file_hash(file_bytes: bytes) -> str:
    return hashlib.md5(file_bytes).hexdigest()


@st.cache_data(show_spinner=False, ttl=300)
def _processar_bytes(file_hash: str, file_bytes: bytes, file_name: str) -> tuple[pd.DataFrame, bool]:
    """[FIX-PERF-6] TTL=300s por entrada. file_hash = chave de cache."""
    try:
        df_raw = _ler_senior_xlsx(file_bytes)
        df     = _processar_senior(df_raw)

        if df.empty:
            st.warning(
                f"⚠️ A planilha '{file_name}' foi lida mas nenhum registro de peça foi encontrado.\n"
                "Verifique se há linhas com código de produto numérico (ex: 200001114)."
            )
            return criar_mock_pecas(), True

        return df, False

    except Exception as e:
        st.error(
            f"❌ Erro ao processar '{file_name}': {e}\n\n"
            "Tente abrir o arquivo no Excel, salvar novamente como .xlsx e fazer upload."
        )
        return criar_mock_pecas(), True


def preparar_pecas(_uploaded_file) -> tuple[pd.DataFrame, bool]:
    """
    [FIX-ACUMULO] Dados da planilha são base histórica.
    Lançamentos manuais futuros SOMAM por cima — nunca sobrescrevem.
    """
    if _uploaded_file is not None:
        _uploaded_file.seek(0)
        file_bytes = _uploaded_file.read()
        fhash = _file_hash(file_bytes)
        df, is_mock = _processar_bytes(fhash, file_bytes, _uploaded_file.name)
        if not is_mock:
            st.session_state["_pecas_df"]   = df
            st.session_state["_pecas_nome"] = _uploaded_file.name
            salvar_cache_pecas(df, _uploaded_file.name)
        return df, is_mock

    if "_pecas_df" in st.session_state:
        nome = st.session_state.get("_pecas_nome", "planilha carregada")
        st.sidebar.caption(f"📂 Peças: {nome}")
        return st.session_state["_pecas_df"], False

    df_sb, nome_sb = ler_cache_pecas()
    if df_sb is not None and not df_sb.empty:
        st.session_state["_pecas_df"]   = df_sb
        st.session_state["_pecas_nome"] = nome_sb
        st.sidebar.caption(f"📂 Peças: {nome_sb} (cache)")
        return df_sb, False

    return criar_mock_pecas(), True


# ── KPIs ──────────────────────────────────────────────────────

def calcular_kpis_pecas(df: pd.DataFrame, df_orc: pd.DataFrame | None = None,
                        data_inicio=None, data_fim=None) -> dict:
    """[FIX-BUG-4] df_orc filtrado pelo mesmo período de datas que df."""
    _zero = {"total_faturado": 0, "total_pedidos": 0,
             "volume_itens": 0, "ticket_medio": 0, "qtd_skus": 0,
             "em_orcamento": 0}

    if df is None or df.empty:
        fat = pd.DataFrame()
        faturamento = volume = 0.0
        n = qtd_skus = 0
    else:
        fat = df[df["Status_Peca"] == "Faturado"].copy() if "Status_Peca" in df.columns else df.copy()
        if fat.empty:
            fat = df.copy()
        faturamento = pd.to_numeric(fat.get("Valor_Total", pd.Series(dtype=float)),
                                    errors="coerce").fillna(0).sum()
        volume      = pd.to_numeric(fat.get("Quantidade", pd.Series(dtype=float)),
                                    errors="coerce").fillna(0).sum()
        n           = len(fat)
        qtd_skus    = fat["Codigo"].nunique() if "Codigo" in fat.columns else 0

        if data_inicio is None and not fat.empty and "Data_Venda" in fat.columns:
            try:
                data_inicio = fat["Data_Venda"].min().date()
                data_fim    = fat["Data_Venda"].max().date()
            except Exception:
                pass

    em_orcamento = 0.0
    if df_orc is not None and not df_orc.empty and "Status_Orc" in df_orc.columns:
        df_orc_f = df_orc.copy()
        if data_inicio is not None and "Data_Orcamento" in df_orc.columns:
            try:
                d = pd.to_datetime(df_orc_f["Data_Orcamento"], errors="coerce", dayfirst=True)
                df_orc_f = df_orc_f[(d.dt.date >= data_inicio) & (d.dt.date <= data_fim)]
            except Exception:
                pass
        fechados = df_orc_f[df_orc_f["Status_Orc"] == "Fechado"]
        faturamento += pd.to_numeric(fechados.get("Valor_Total", pd.Series(dtype=float)),
                                     errors="coerce").fillna(0).sum()
        aguardando   = df_orc_f[df_orc_f["Status_Orc"] == "Aguardando"]
        em_orcamento = pd.to_numeric(aguardando.get("Valor_Total", pd.Series(dtype=float)),
                                     errors="coerce").fillna(0).sum()

    return {
        "total_faturado": float(faturamento),
        "total_pedidos":  int(n),
        "volume_itens":   float(volume),
        "ticket_medio":   float(faturamento / n) if n > 0 else 0.0,
        "qtd_skus":       int(qtd_skus),
        "em_orcamento":   float(em_orcamento),
    }


def calcular_curva_abc(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    _cols = ["Descricao_Peca", "Valor_Total", "Pct", "Curva"]
    if df is None or df.empty or "Descricao_Peca" not in df.columns:
        return pd.DataFrame(columns=_cols)
    abc = df.groupby("Descricao_Peca")["Valor_Total"].sum().sort_values(ascending=False).reset_index()
    abc = abc[abc["Valor_Total"] > 0].reset_index(drop=True)
    if abc.empty:
        return pd.DataFrame(columns=_cols)
    total        = abc["Valor_Total"].sum()
    abc["Pct"]   = abc["Valor_Total"] / total * 100
    abc["Pct_Acum"] = abc["Pct"].cumsum()
    abc["Curva"] = abc["Pct_Acum"].apply(lambda x: "A" if x <= 80 else ("B" if x <= 95 else "C"))
    return abc.head(top_n)


def calcular_curva_abc_por_codigo(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """
    Curva ABC por código de peça (coluna Produto do Senior).

    CORRECAO: A classificacao A/B/C é calculada sobre o UNIVERSO COMPLETO
    de pecas (Pct_Acum em relacao ao total geral). So depois os top_n sao
    retornados para exibicao. Assim a curva reflete a real concentracao de
    faturamento — nao apenas o recorte exibido.
    """
    _cols = ["Codigo", "Descricao_Peca", "Valor_Total", "Pct", "Pct_Acum", "Curva"]
    if df is None or df.empty or "Codigo" not in df.columns:
        return pd.DataFrame(columns=_cols)

    agg = {"Valor_Total": ("Valor_Total", "sum")}
    agg["Descricao_Peca"] = ("Descricao_Peca", "first") if "Descricao_Peca" in df.columns \
                             else ("Codigo", "first")

    grp = df.groupby("Codigo").agg(**agg).reset_index()
    grp = grp[grp["Valor_Total"] > 0].sort_values("Valor_Total", ascending=False).reset_index(drop=True)
    if grp.empty:
        return pd.DataFrame(columns=_cols)

    # Classificacao sobre universo COMPLETO
    total           = grp["Valor_Total"].sum()
    grp["Pct"]      = grp["Valor_Total"] / total * 100
    grp["Pct_Acum"] = grp["Pct"].cumsum()
    grp["Curva"]    = grp["Pct_Acum"].apply(
        lambda x: "A" if x <= 80 else ("B" if x <= 95 else "C")
    )

    # Retorna apenas os top_n para exibicao (curva ja correta)
    return grp.head(top_n).reset_index(drop=True)


def calcular_top10_revendas(df: pd.DataFrame) -> pd.DataFrame:
    """Top 10 revendas por faturamento — usa o NOME do cliente (col após 'Cliente' no Senior)."""
    if df is None or df.empty or "Cliente_Revenda" not in df.columns:
        return pd.DataFrame(columns=["Cliente_Revenda", "Valor_Total"])

    top = df.groupby("Cliente_Revenda")["Valor_Total"].sum().reset_index()
    top = top[
        top["Cliente_Revenda"].notna() &
        (~top["Cliente_Revenda"].astype(str).str.strip().isin(
            ["", "nan", "Não informado", "Nao informado", "N/A", "NA", "-", "—"]
        ))
    ]
    top = top[top["Valor_Total"] > 0]
    return top.sort_values("Valor_Total", ascending=False).head(10).reset_index(drop=True)
