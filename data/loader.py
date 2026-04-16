"""
data/loader.py — Genius Plantadeiras v13
Planilha Senior de peças agora persiste via Supabase (genius_pecas_cache).
"""

from __future__ import annotations

import io
import unicodedata

import pandas as pd
import streamlit as st

from data.db import salvar_cache_pecas, ler_cache_pecas


# ── Utilitários ───────────────────────────────────────────────

def limpar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [
        unicodedata.normalize("NFKD", str(c)).encode("ascii", "ignore").decode("ascii")
        .strip().replace(" ", "_")
        for c in df.columns
    ]
    return df


def limpar_moeda_brl(serie: pd.Series) -> pd.Series:
    def _parse(v):
        if pd.isna(v):
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".").strip()
        try:
            return float(s)
        except Exception:
            return 0.0
    return serie.apply(_parse)


def criar_mock_data() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "Status", "Revenda", "Valor", "Data_Pedido", "Observacao",
        "Equipamento", "Representante", "Cliente",
    ])


def criar_mock_pecas() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "Codigo", "Descricao_Peca", "Quantidade", "Valor_Unitario",
        "Valor_Total", "Cliente_Revenda", "Data_Venda", "Status_Peca",
    ])


# ── Processamento de Máquinas ─────────────────────────────────

@st.cache_data
def _preparar_dados_bytes(file_bytes: bytes, file_name: str):
    try:
        if file_name.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8", sep=None, engine="python")
        else:
            df = pd.read_excel(io.BytesIO(file_bytes))
        df = limpar_colunas(df)
        if "Valor" in df.columns:
            df["Valor"] = limpar_moeda_brl(df["Valor"])
        if "Data_Pedido" in df.columns:
            df["Data_Pedido"] = pd.to_datetime(df["Data_Pedido"], dayfirst=True, errors="coerce")
        return df, False
    except Exception:
        return criar_mock_data(), True


def preparar_dados(_uploaded_file) -> tuple[pd.DataFrame, bool]:
    if _uploaded_file is None:
        return criar_mock_data(), True
    _uploaded_file.seek(0)
    return _preparar_dados_bytes(_uploaded_file.read(), _uploaded_file.name)


# ── Processamento de Peças — com cache no Supabase ────────────

@st.cache_data(show_spinner=False)
def _processar_pecas_bytes(file_bytes: bytes, file_name: str) -> tuple[pd.DataFrame, bool]:
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), header=4)

        mapeamento = {
            "Emissão":         "Data_Venda",
            "Produto":         "Codigo",
            "Unnamed: 6":      "Descricao_Peca",
            "Qtde.Fat.":       "Quantidade",
            "Preço Un.":       "Valor_Unitario",
            "Vlr.Liq.":        "Valor_Total",
            "Cliente/Revenda": "Cliente_Revenda",
        }
        if "Unnamed: 6" in df.columns and "Descricao_Peca" not in df.columns:
            df = df.rename(columns={"Unnamed: 6": "Descricao_Peca"})
        df = df.rename(columns=mapeamento)

        if "Codigo" in df.columns:
            df = df[~df["Codigo"].astype(str).str.contains("Família:", na=False)]
        df = df.dropna(subset=["Codigo"])

        if "Quantidade" in df.columns:
            df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce").fillna(0)
        for col in ["Valor_Unitario", "Valor_Total"]:
            if col in df.columns:
                df[col] = limpar_moeda_brl(df[col])

        if "Data_Venda" in df.columns:
            df["Data_Venda"] = pd.to_datetime(df["Data_Venda"], errors="coerce")
            df = df[df["Data_Venda"] >= "2024-01-01"]

        df["Status_Peca"] = "Faturado"

        if "Cliente_Revenda" not in df.columns:
            if "Unnamed: 5" in df.columns:
                df["Cliente_Revenda"] = df["Unnamed: 5"].astype(str)
            else:
                df["Cliente_Revenda"] = "Cliente não informado"

        return df, False
    except Exception as e:
        st.error(f"Erro na planilha de peças: {e}")
        return criar_mock_pecas(), True


def preparar_pecas(_uploaded_file) -> tuple[pd.DataFrame, bool]:
    """
    Ordem de prioridade:
      1. Novo upload agora         → processa, salva no Supabase e no session_state
      2. session_state (mesmo run) → usa sem re-processar
      3. Cache no Supabase         → carrega na primeira vez após reinicialização
      4. Sem dados                 → retorna mock vazio
    """
    if _uploaded_file is not None:
        _uploaded_file.seek(0)
        file_bytes = _uploaded_file.read()
        df, is_mock = _processar_pecas_bytes(file_bytes, _uploaded_file.name)
        if not is_mock:
            # Salva tanto localmente na sessão quanto no Supabase
            st.session_state["_pecas_df_cache"]    = df
            st.session_state["_pecas_nome_arquivo"] = _uploaded_file.name
            salvar_cache_pecas(df, _uploaded_file.name)
        return df, is_mock

    # 2. Memória da sessão (rápido)
    if "_pecas_df_cache" in st.session_state:
        nome = st.session_state.get("_pecas_nome_arquivo", "planilha carregada")
        st.sidebar.caption(f"📂 Peças: {nome}")
        return st.session_state["_pecas_df_cache"], False

    # 3. Supabase (persiste entre reinicializações)
    df_sb, nome_sb = ler_cache_pecas()
    if df_sb is not None:
        st.session_state["_pecas_df_cache"]    = df_sb
        st.session_state["_pecas_nome_arquivo"] = nome_sb
        st.sidebar.caption(f"📂 Peças: {nome_sb}")
        return df_sb, False

    return criar_mock_pecas(), True


# ── KPIs e Análises ───────────────────────────────────────────

def calcular_kpis_pecas(df: pd.DataFrame) -> dict:
    if df.empty:
        return {k: 0 for k in ["total_faturado", "total_pedidos", "volume_itens",
                                "ticket_medio", "qtd_skus"]}
    faturamento = pd.to_numeric(df["Valor_Total"], errors="coerce").sum()
    volume      = pd.to_numeric(df["Quantidade"],  errors="coerce").sum()
    return {
        "total_faturado": faturamento,
        "total_pedidos":  len(df),
        "volume_itens":   volume,
        "ticket_medio":   faturamento / len(df) if len(df) > 0 else 0,
        "qtd_skus":       df["Codigo"].nunique(),
    }


def calcular_curva_abc(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    if df.empty or "Descricao_Peca" not in df.columns:
        return pd.DataFrame(columns=["Descricao_Peca", "Valor_Total", "Pct", "Curva"])
    abc = (df.groupby("Descricao_Peca")["Valor_Total"]
             .sum().sort_values(ascending=False).reset_index())
    total = abc["Valor_Total"].sum()
    abc["Pct"]      = (abc["Valor_Total"] / total) * 100
    abc["Pct_Acum"] = abc["Pct"].cumsum()
    abc["Curva"]    = abc["Pct_Acum"].apply(
        lambda x: "A" if x <= 80 else ("B" if x <= 95 else "C"))
    return abc.head(top_n)
