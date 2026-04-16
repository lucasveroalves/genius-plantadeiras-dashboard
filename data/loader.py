"""
data/loader.py — Genius Plantadeiras v14
Correções:
  • Colunas normalizadas antes de qualquer operação
  • Data_Venda convertida corretamente (timezone safe)
  • Filtro de data robusto (sem tz mismatch)
  • Cache Supabase sem erros de serialização
"""

from __future__ import annotations
import io, unicodedata
import pandas as pd
import streamlit as st
from data.db import salvar_cache_pecas, ler_cache_pecas


def _norm_col(c: str) -> str:
    return (unicodedata.normalize("NFKD", str(c))
            .encode("ascii","ignore").decode("ascii")
            .strip().replace(" ","_"))

def limpar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [_norm_col(c) for c in df.columns]
    return df

def limpar_moeda_brl(serie: pd.Series) -> pd.Series:
    def _p(v):
        if pd.isna(v): return 0.0
        if isinstance(v, (int, float)): return float(v)
        s = str(v).replace("R$","").replace(" ","").replace(".","").replace(",",".").strip()
        try: return float(s)
        except: return 0.0
    return serie.apply(_p)

def criar_mock_pecas() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "Codigo","Descricao_Peca","Quantidade","Valor_Unitario",
        "Valor_Total","Cliente_Revenda","Data_Venda","Status_Peca",
    ])


# ── Processamento da planilha Senior ─────────────────────────

@st.cache_data(show_spinner=False)
def _processar_bytes(file_bytes: bytes, file_name: str) -> tuple[pd.DataFrame, bool]:
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), header=4, engine="openpyxl")

        # Renomeia colunas pelo nome original (antes da normalização)
        mapeamento = {
            "Emissão":         "Data_Venda",
            "Emissao":         "Data_Venda",
            "Produto":         "Codigo",
            "Qtde.Fat.":       "Quantidade",
            "Preco_Un.":       "Valor_Unitario",
            "Vlr.Liq.":        "Valor_Total",
            "Cliente/Revenda": "Cliente_Revenda",
        }
        df = limpar_colunas(df)

        # Mapeia nomes normalizados
        mapeamento_norm = {
            "Emissao":          "Data_Venda",
            "Produto":          "Codigo",
            "Qtde.Fat.":        "Quantidade",
            "Preco_Un.":        "Valor_Unitario",
            "Vlr.Liq.":         "Valor_Total",
            "Cliente/Revenda":  "Cliente_Revenda",
        }
        # Aplica renomeação dinâmica
        rename_map = {}
        for col in df.columns:
            # coluna de descrição: Unnamed: 6 após normalização vira Unnamed:_6
            if col.startswith("Unnamed") and "Descricao_Peca" not in df.columns:
                rename_map[col] = "Descricao_Peca"
        for k, v in mapeamento_norm.items():
            if k in df.columns:
                rename_map[k] = v
        df = df.rename(columns=rename_map)

        # Remove linhas de agrupamento ("Família:")
        if "Codigo" in df.columns:
            df = df[~df["Codigo"].astype(str).str.contains("Família:|Familia:", na=False, regex=True)]
        df = df.dropna(subset=["Codigo"])

        # Tipos numéricos
        for col in ["Quantidade"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        for col in ["Valor_Unitario","Valor_Total"]:
            if col in df.columns:
                df[col] = limpar_moeda_brl(df[col])

        # Data — sem timezone
        if "Data_Venda" in df.columns:
            df["Data_Venda"] = pd.to_datetime(df["Data_Venda"], errors="coerce")
            if df["Data_Venda"].dt.tz is not None:
                df["Data_Venda"] = df["Data_Venda"].dt.tz_localize(None)
            df = df[df["Data_Venda"] >= "2024-01-01"]

        if "Cliente_Revenda" not in df.columns:
            df["Cliente_Revenda"] = "Não informado"
        df["Status_Peca"] = "Faturado"

        # Garante colunas mínimas
        for col in ["Codigo","Descricao_Peca","Quantidade","Valor_Unitario",
                    "Valor_Total","Cliente_Revenda","Data_Venda","Status_Peca"]:
            if col not in df.columns:
                df[col] = "" if col not in ["Quantidade","Valor_Unitario","Valor_Total"] else 0.0

        return df.reset_index(drop=True), False
    except Exception as e:
        st.error(f"Erro ao processar planilha de peças: {e}")
        return criar_mock_pecas(), True


def preparar_pecas(_uploaded_file) -> tuple[pd.DataFrame, bool]:
    """
    Prioridade:
      1. Novo upload → processa, salva session + Supabase
      2. session_state → uso rápido entre reruns
      3. Supabase (cache persistente)
      4. Mock vazio
    """
    if _uploaded_file is not None:
        _uploaded_file.seek(0)
        file_bytes = _uploaded_file.read()
        df, is_mock = _processar_bytes(file_bytes, _uploaded_file.name)
        if not is_mock:
            st.session_state["_pecas_df"]   = df
            st.session_state["_pecas_nome"] = _uploaded_file.name
            salvar_cache_pecas(df, _uploaded_file.name)
        return df, is_mock

    if "_pecas_df" in st.session_state:
        nome = st.session_state.get("_pecas_nome","planilha carregada")
        st.sidebar.caption(f"📂 Peças: {nome}")
        return st.session_state["_pecas_df"], False

    df_sb, nome_sb = ler_cache_pecas()
    if df_sb is not None and not df_sb.empty:
        st.session_state["_pecas_df"]   = df_sb
        st.session_state["_pecas_nome"] = nome_sb
        st.sidebar.caption(f"📂 Peças: {nome_sb} (cache)")
        return df_sb, False

    return criar_mock_pecas(), True


# ── KPIs de Peças ─────────────────────────────────────────────

def calcular_kpis_pecas(df: pd.DataFrame) -> dict:
    """
    Calcula KPIs apenas das peças com Status_Peca == 'Faturado'.
    Orçamentos em aberto são somados separadamente na aba.
    """
    if df is None or df.empty:
        return {"total_faturado":0,"total_pedidos":0,"volume_itens":0,"ticket_medio":0,"qtd_skus":0}
    fat = df[df.get("Status_Peca","Faturado") == "Faturado"] if "Status_Peca" in df.columns else df
    if fat.empty:
        fat = df
    faturamento = pd.to_numeric(fat["Valor_Total"], errors="coerce").sum()
    volume      = pd.to_numeric(fat["Quantidade"],  errors="coerce").sum()
    return {
        "total_faturado": faturamento,
        "total_pedidos":  len(fat),
        "volume_itens":   volume,
        "ticket_medio":   faturamento / len(fat) if len(fat) > 0 else 0,
        "qtd_skus":       fat["Codigo"].nunique() if "Codigo" in fat.columns else 0,
    }


def calcular_curva_abc(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    if df is None or df.empty or "Descricao_Peca" not in df.columns:
        return pd.DataFrame(columns=["Descricao_Peca","Valor_Total","Pct","Curva"])
    abc = (df.groupby("Descricao_Peca")["Valor_Total"]
             .sum().sort_values(ascending=False).reset_index())
    # Remove zeros
    abc = abc[abc["Valor_Total"] > 0].reset_index(drop=True)
    if abc.empty:
        return pd.DataFrame(columns=["Descricao_Peca","Valor_Total","Pct","Curva"])
    total       = abc["Valor_Total"].sum()
    abc["Pct"]      = (abc["Valor_Total"] / total) * 100
    abc["Pct_Acum"] = abc["Pct"].cumsum()
    abc["Curva"]    = abc["Pct_Acum"].apply(lambda x: "A" if x<=80 else ("B" if x<=95 else "C"))
    return abc.head(top_n)
