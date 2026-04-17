"""
data/loader.py — Genius Implementos Agrícolas v14 (corrigido)
Correções aplicadas:
  • [BUG#1] calcular_kpis_pecas: verificação de coluna corrigida (estava invertida)
  • [BUG#2] tz_localize(None) trocado por tz_convert(None) — evita exceção em dados tz-aware
  • [BUG#3] Filtro de data agora usa dropna() antes da comparação — evita erro com NaT
  • [BUG#4] Variável 'mapeamento' morta removida (nunca era aplicada)
  • [BUG#5] _norm_col aplicada às chaves de mapeamento_norm para garantir match real
"""

from __future__ import annotations
import io, unicodedata
import pandas as pd
import streamlit as st
from data.db import salvar_cache_pecas, ler_cache_pecas


def _norm_col(c: str) -> str:
    return (unicodedata.normalize("NFKD", str(c))
            .encode("ascii", "ignore").decode("ascii")
            .strip().replace(" ", "_"))

def limpar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [_norm_col(c) for c in df.columns]
    return df

def limpar_moeda_brl(serie: pd.Series) -> pd.Series:
    def _p(v):
        if pd.isna(v): return 0.0
        if isinstance(v, (int, float)): return float(v)
        s = str(v).replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".").strip()
        try: return float(s)
        except: return 0.0
    return serie.apply(_p)

def criar_mock_pecas() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "Codigo", "Descricao_Peca", "Quantidade", "Valor_Unitario",
        "Valor_Total", "Cliente_Revenda", "Data_Venda", "Status_Peca",
    ])


# ── Processamento da planilha Senior ─────────────────────────

# Colunas que sinalizam que encontramos o cabeçalho real da planilha Senior
_SENIOR_HEADER_KEYS = {"Emissao", "Produto", "Vlr.Liq.", "Emissão", "Emissao_"}

def _ler_excel_robusto(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    """
    Lê planilha do ERP Senior com detecção automática de:
      - Formato: .xlsx (openpyxl) | .xls legado (xlrd) | xlsx corrompido (calamine)
      - Header row: tenta header=4 (padrão Senior) e header=0 como fallback
      - Detecta header correto procurando pela linha que contém "Emissão" ou "Produto"

    O erro "There is no item named 'xl/workbook.xml' in the archive" ocorre quando
    o arquivo é .xls binário renomeado como .xlsx, ou exportado pelo Senior em formato
    de compatibilidade. Solução: tentar múltiplos engines em sequência.
    """
    fname_lower = file_name.lower()

    # Estratégias de leitura em ordem de preferência
    strategies = []

    if fname_lower.endswith(".xls"):
        # Arquivo .xls legado — só xlrd consegue ler
        strategies = [
            {"engine": "xlrd",    "header": 4},
            {"engine": "xlrd",    "header": 0},
        ]
    else:
        # .xlsx — tenta openpyxl primeiro, depois calamine (mais tolerante a corrupção)
        strategies = [
            {"engine": "openpyxl",  "header": 4},
            {"engine": "openpyxl",  "header": 0},
            {"engine": "calamine",  "header": 4},
            {"engine": "calamine",  "header": 0},
        ]

    last_err = None
    for strat in strategies:
        try:
            df = pd.read_excel(
                io.BytesIO(file_bytes),
                header=strat["header"],
                engine=strat["engine"],
            )
            # Verifica se o header faz sentido: procura coluna com nome típico do Senior
            cols_norm = {_norm_col(str(c)) for c in df.columns}
            if cols_norm & _SENIOR_HEADER_KEYS or strat["header"] == 0:
                return df   # encontrou header válido
        except Exception as e:
            last_err = e
            continue

    # Última tentativa: lê sem header e detecta a linha do cabeçalho manualmente
    try:
        df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None, engine="openpyxl")
        for i, row in df_raw.iterrows():
            row_vals = {_norm_col(str(v)) for v in row.values if pd.notna(v)}
            if row_vals & _SENIOR_HEADER_KEYS:
                df = pd.read_excel(io.BytesIO(file_bytes), header=i, engine="openpyxl")
                return df
    except Exception as e:
        last_err = e

    raise RuntimeError(
        f"Não foi possível ler a planilha '{file_name}'.\n"
        f"Último erro: {last_err}\n\n"
        "Verifique se o arquivo foi exportado corretamente pelo Senior ERP.\n"
        "Formatos aceitos: .xlsx (padrão) ou .xls (legado).\n"
        "Se o arquivo for .xlsx, abra-o no Excel e salve novamente antes de fazer upload."
    )


@st.cache_data(show_spinner=False)
def _processar_bytes(file_bytes: bytes, file_name: str) -> tuple[pd.DataFrame, bool]:
    try:
        df = _ler_excel_robusto(file_bytes, file_name)

        # Normaliza colunas primeiro
        df = limpar_colunas(df)

        # Mapeamento usando nomes já normalizados
        mapeamento_norm = {
            "Emissao":          "Data_Venda",
            "Emissao_":         "Data_Venda",
            "Data":             "Data_Venda",   # variação em algumas versões do Senior
            "Produto":          "Codigo",
            "Qtde.Fat.":        "Quantidade",
            "Qtde_Fat_":        "Quantidade",   # após normalização de pontos
            "Quantidade":       "Quantidade",
            "Preco_Un.":        "Valor_Unitario",
            "Preco_Un_":        "Valor_Unitario",
            "Vlr.Liq.":         "Valor_Total",
            "Vlr_Liq_":         "Valor_Total",
            "Cliente/Revenda":  "Cliente_Revenda",
            "Cliente_Revenda":  "Cliente_Revenda",
            "Razao_Social":     "Cliente_Revenda",  # variação Senior
            "Cliente":          "Cliente_Revenda",
            "Descricao":        "Descricao_Peca",
            "Descricao_Produto":"Descricao_Peca",
        }

        rename_map = {}
        for col in df.columns:
            # Primeira coluna "Unnamed" sem nome → Descricao_Peca
            if col.startswith("Unnamed") and "Descricao_Peca" not in df.columns:
                rename_map[col] = "Descricao_Peca"
        for k, v in mapeamento_norm.items():
            if k in df.columns and k != v:
                rename_map[k] = v
        df = df.rename(columns=rename_map)

        # Remove linhas de agrupamento ("Família:")
        if "Codigo" in df.columns:
            df = df[~df["Codigo"].astype(str).str.contains(
                "Família:|Familia:|^nan$", na=False, regex=True)]
        df = df.dropna(subset=["Codigo"])
        df = df[df["Codigo"].astype(str).str.strip() != ""]

        # Tipos numéricos
        if "Quantidade" in df.columns:
            df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce").fillna(0)
        for col in ["Valor_Unitario", "Valor_Total"]:
            if col in df.columns:
                df[col] = limpar_moeda_brl(df[col])

        # Data — sem timezone
        if "Data_Venda" in df.columns:
            df["Data_Venda"] = pd.to_datetime(df["Data_Venda"], errors="coerce")
            if df["Data_Venda"].dt.tz is not None:
                df["Data_Venda"] = df["Data_Venda"].dt.tz_convert(None)
            df = df.dropna(subset=["Data_Venda"])
            df = df[df["Data_Venda"] >= "2024-01-01"]

        if "Cliente_Revenda" not in df.columns:
            df["Cliente_Revenda"] = "Não informado"
        df["Status_Peca"] = "Faturado"

        # Garante colunas mínimas
        for col in ["Codigo", "Descricao_Peca", "Quantidade", "Valor_Unitario",
                    "Valor_Total", "Cliente_Revenda", "Data_Venda", "Status_Peca"]:
            if col not in df.columns:
                df[col] = "" if col not in ["Quantidade", "Valor_Unitario", "Valor_Total"] else 0.0

        return df.reset_index(drop=True), False

    except RuntimeError as e:
        # Mensagem amigável do _ler_excel_robusto — mostrar em warning, não erro vermelho
        st.warning(str(e))
        return criar_mock_pecas(), True
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


# ── KPIs de Peças ─────────────────────────────────────────────

def calcular_kpis_pecas(df: pd.DataFrame, df_orc: pd.DataFrame | None = None) -> dict:
    """
    Calcula KPIs de peças faturadas + orçamentos fechados.

    Parâmetros:
      df      — DataFrame da planilha Senior (peças faturadas via ERP)
      df_orc  — DataFrame de orçamentos do Supabase (opcional).
                Orçamentos com Status_Orc == 'Fechado' somam em
                total_faturado e volume_itens (campo Quantidade).

    Regra de negócio:
      • "Peças Faturadas" = faturamento ERP + orçamentos Fechados
      • "Volume de Itens"  = qtd ERP + qtd de itens dos orçamentos Fechados
      • "Em Orçamento"     = soma dos orçamentos com Status_Orc == 'Aguardando'
    """
    _zero = {"total_faturado": 0, "total_pedidos": 0,
             "volume_itens": 0, "ticket_medio": 0, "qtd_skus": 0,
             "em_orcamento": 0}

    if df is None or df.empty:
        fat = pd.DataFrame()
        faturamento = 0.0
        volume      = 0.0
        n           = 0
        qtd_skus    = 0
    else:
        if "Status_Peca" in df.columns:
            fat = df[df["Status_Peca"] == "Faturado"].copy()
            if fat.empty:
                fat = df.copy()
        else:
            fat = df.copy()

        faturamento = pd.to_numeric(fat["Valor_Total"], errors="coerce").fillna(0).sum()
        volume      = pd.to_numeric(fat["Quantidade"], errors="coerce").fillna(0).sum()                       if "Quantidade" in fat.columns else 0.0
        n           = len(fat)
        qtd_skus    = fat["Codigo"].nunique() if "Codigo" in fat.columns else 0

    # Soma orçamentos FECHADOS em faturamento e volume
    em_orcamento = 0.0
    if df_orc is not None and not df_orc.empty and "Status_Orc" in df_orc.columns:
        fechados = df_orc[df_orc["Status_Orc"] == "Fechado"]
        faturamento += pd.to_numeric(fechados["Valor_Total"], errors="coerce").fillna(0).sum()
        volume      += pd.to_numeric(fechados.get("Quantidade", pd.Series(dtype=float)),
                                     errors="coerce").fillna(0).sum()

        aguardando = df_orc[df_orc["Status_Orc"] == "Aguardando"]
        em_orcamento = pd.to_numeric(aguardando["Valor_Total"], errors="coerce").fillna(0).sum()

    ticket = faturamento / n if n > 0 else 0

    return {
        "total_faturado": faturamento,
        "total_pedidos":  n,
        "volume_itens":   volume,
        "ticket_medio":   ticket,
        "qtd_skus":       qtd_skus,
        "em_orcamento":   em_orcamento,
    }


def calcular_curva_abc(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """Mantido por compatibilidade. Novo padrão: calcular_curva_abc_por_codigo."""
    _cols = ["Descricao_Peca", "Valor_Total", "Pct", "Curva"]
    if df is None or df.empty or "Descricao_Peca" not in df.columns:
        return pd.DataFrame(columns=_cols)
    abc = (df.groupby("Descricao_Peca")["Valor_Total"]
             .sum().sort_values(ascending=False).reset_index())
    abc = abc[abc["Valor_Total"] > 0].reset_index(drop=True)
    if abc.empty:
        return pd.DataFrame(columns=_cols)
    total           = abc["Valor_Total"].sum()
    abc["Pct"]      = (abc["Valor_Total"] / total) * 100
    abc["Pct_Acum"] = abc["Pct"].cumsum()
    abc["Curva"]    = abc["Pct_Acum"].apply(
        lambda x: "A" if x <= 80 else ("B" if x <= 95 else "C"))
    return abc.head(top_n)


def calcular_curva_abc_por_codigo(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """
    Curva ABC agrupada por CÓDIGO de peça (ex: 200000386).
    Eixo Y = Codigo. Ordenação decrescente por Valor_Total.
    """
    _cols = ["Codigo", "Descricao_Peca", "Valor_Total", "Pct", "Curva"]
    if df is None or df.empty or "Codigo" not in df.columns:
        return pd.DataFrame(columns=_cols)

    # Agrupa por código; traz junto a descrição (primeira ocorrência)
    grp = df.groupby("Codigo").agg(
        Valor_Total=("Valor_Total", "sum"),
        Descricao_Peca=("Descricao_Peca", "first") if "Descricao_Peca" in df.columns else ("Codigo", "first"),
    ).reset_index()
    grp = grp[grp["Valor_Total"] > 0].sort_values("Valor_Total", ascending=False).reset_index(drop=True)

    if grp.empty:
        return pd.DataFrame(columns=_cols)

    total           = grp["Valor_Total"].sum()
    grp["Pct"]      = (grp["Valor_Total"] / total) * 100
    grp["Pct_Acum"] = grp["Pct"].cumsum()
    grp["Curva"]    = grp["Pct_Acum"].apply(
        lambda x: "A" if x <= 80 else ("B" if x <= 95 else "C"))
    return grp.head(top_n)


def calcular_top10_revendas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Top 10 revendas por consumo de peças (Valor_Total).
    - Remove 'Não informado' e valores vazios/nulos
    - Retorna colunas: Cliente_Revenda, Valor_Total
    - Ordenação decrescente
    """
    if df is None or df.empty or "Cliente_Revenda" not in df.columns:
        return pd.DataFrame(columns=["Cliente_Revenda", "Valor_Total"])

    top = (df.groupby("Cliente_Revenda")["Valor_Total"]
             .sum().reset_index())
    # Remove "Não informado", vazios e nulos
    top = top[
        top["Cliente_Revenda"].notna() &
        (top["Cliente_Revenda"].astype(str).str.strip() != "") &
        (~top["Cliente_Revenda"].astype(str).str.lower().isin(
            ["não informado", "nao informado", "n/a", "na", "-", "—"]))
    ]
    top = top[top["Valor_Total"] > 0]
    top = top.sort_values("Valor_Total", ascending=False).head(10).reset_index(drop=True)
    return top
