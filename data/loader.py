"""
data/loader.py — Genius Implementos Agrícolas v17

Correções aplicadas:
  [FIX-CHAVE]   Chave única por linha: Série + Número NF + Produto + Cód.Cliente
                Permite importação diária sem duplicar registros já existentes.
  [FIX-HEADER]  Cabeçalho real na linha 4 da planilha Senior (header=4).
                Colunas: Série, Número, Emissão, Produto, Derivação,
                Cliente, Nome, Qtde.Fat., UM, Preço Un., Vlr.Liq., TnsNfv, TnsPro, Sit.
  [FIX-FAMILIA] Linhas de agrupamento por Família removidas (Série != NFE/NFS).
  [FIX-CAT]     Catálogo lido de ESTOQUES_MIN_MAX_COMPRADOS.xlsx
                (header linha 4, colunas CÓDIGO + DESCRIÇÃO — 10.727 produtos).
  [FIX-IMPORT-1] Constantes STATUS_* mantidas para calculators.py.
"""

from __future__ import annotations
import hashlib
import unicodedata
import pandas as pd
import streamlit as st


# ══════════════════════════════════════════════════════════════
# Constantes de status (importadas por calculators.py)
# ══════════════════════════════════════════════════════════════

STATUS_FATURADO_LOWER  = ["faturado", "entregue", "pedido fechado"]
STATUS_PIPELINE_LOWER  = ["em negociação", "em aberto", "crédito",
                           "pronto para faturar", "pedido fechado", "faturado"]
STATUS_ALERTA_LOWER    = ["em negociação", "em aberto"]


# ══════════════════════════════════════════════════════════════
# Utilitários
# ══════════════════════════════════════════════════════════════

def _norm_col(c: str) -> str:
    return (unicodedata.normalize("NFKD", str(c))
            .encode("ascii", "ignore").decode("ascii")
            .strip().replace(" ", "_").replace(".", "_"))


def limpar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [_norm_col(c) for c in df.columns]
    return df


def limpar_moeda_brl(serie: pd.Series) -> pd.Series:
    """Conversão vetorizada BRL → float."""
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
        "Serie", "Numero_NF", "Data_Venda", "Codigo", "Descricao_Peca",
        "Quantidade", "Valor_Unitario", "Valor_Total",
        "Cliente_Revenda", "chave_nf",
    ])


# ══════════════════════════════════════════════════════════════
# [FIX-CHAVE] Chave única por linha de venda
# ══════════════════════════════════════════════════════════════

def _gerar_chave_nf(serie: str, numero: str, produto: str, cod_cliente: str) -> str:
    """
    Chave única: Série-NúmeroNF-Produto-CódCliente
    Exemplo: NFE-17613-200000059-4321
    Garante que a mesma linha não seja inserida duas vezes,
    mesmo que a planilha seja importada múltiplas vezes.
    """
    return f"{str(serie).strip()}-{str(numero).strip()}-{str(produto).strip()}-{str(cod_cliente).strip()}"


# ══════════════════════════════════════════════════════════════
# [FIX-CAT] Leitura do catálogo ESTOQUES_MIN_MAX_COMPRADOS.xlsx
# ══════════════════════════════════════════════════════════════

def ler_catalogo_xlsx(file_bytes: bytes) -> pd.DataFrame:
    """
    Lê CÓDIGO + DESCRIÇÃO do catálogo de peças.
    Header real na linha 4 (header=4).
    Retorna DataFrame com colunas: Codigo, Descricao
    """
    import io
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), header=4, engine="openpyxl")
        cols = list(df.columns)
        col_cod  = next((c for c in cols if "CÓDIGO" in str(c).upper() or "CODIGO" in str(c).upper()), None)
        col_desc = next((c for c in cols if "DESCRI" in str(c).upper()), None)
        if not col_cod or not col_desc:
            return pd.DataFrame(columns=["Codigo", "Descricao"])
        result = df[[col_cod, col_desc]].copy()
        result.columns = ["Codigo", "Descricao"]
        result["Codigo"]    = result["Codigo"].astype(str).str.strip()
        result["Descricao"] = result["Descricao"].astype(str).str.strip()
        result = result.dropna(subset=["Codigo", "Descricao"])
        result = result[result["Codigo"].str.match(r"^\d+$", na=False)]
        result = result[result["Descricao"].str.len() > 2]
        return result.drop_duplicates("Codigo").reset_index(drop=True)
    except Exception as e:
        st.warning(f"⚠️ Erro ao ler catálogo: {e}")
        return pd.DataFrame(columns=["Codigo", "Descricao"])


# ══════════════════════════════════════════════════════════════
# [FIX-HEADER] Leitura e processamento da planilha Senior
# ══════════════════════════════════════════════════════════════

def _ler_senior_xlsx(file_bytes: bytes) -> pd.DataFrame:
    """
    Header real na linha 4 (0-indexed).
    Tenta openpyxl (.xlsx) primeiro; se falhar, tenta xlrd (.xls legado).
    Também tenta sem header fixo se o arquivo tiver estrutura diferente.
    """
    import io
    buf = io.BytesIO(file_bytes)

    # Tentativa 1: openpyxl padrão (xlsx)
    try:
        return pd.read_excel(buf, header=4, engine="openpyxl")
    except Exception:
        pass

    # Tentativa 2: xlrd (xls legado ou xlsx com problema de estrutura)
    try:
        buf.seek(0)
        return pd.read_excel(buf, header=4, engine="xlrd")
    except Exception:
        pass

    # Tentativa 3: openpyxl sem header fixo — detecta automaticamente
    try:
        buf.seek(0)
        df_raw = pd.read_excel(buf, header=None, engine="openpyxl")
        # Procura a linha que contém "Serie" ou "Série" ou "Número"
        for i, row in df_raw.iterrows():
            vals = [str(v).strip().lower() for v in row.values]
            if any(k in vals for k in ["serie", "série", "numero", "número", "emissao", "emissão"]):
                df_raw.columns = df_raw.iloc[i]
                df_raw = df_raw.iloc[i+1:].reset_index(drop=True)
                return df_raw
        # Se não achou cabeçalho, usa linha 4
        buf.seek(0)
        df_raw = pd.read_excel(buf, header=4, engine="openpyxl")
        return df_raw
    except Exception as e:
        raise ValueError(f"Não foi possível ler o arquivo. Verifique se é um Excel válido (.xlsx ou .xls). Erro: {e}")


def _processar_senior(df: pd.DataFrame, df_catalogo: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Processa planilha Senior:
    1. Remove linhas de agrupamento por Família
    2. Filtra NFs válidas (Série = NFE ou NFS)
    3. Renomeia colunas para schema interno
    4. [FIX-CHAVE] Gera chave única por linha
    5. Enriquece com descrição do catálogo
    """
    if df is None or df.empty:
        return criar_mock_pecas()

    df = limpar_colunas(df.copy())

    # [FIX-COLS] Mapeamento exato das colunas da planilha Senior
    # Coluna do nome do cliente é "Unnamed:_6" após normalização
    rename_map = {
        "Serie":      "Serie",
        "Numero":     "Numero_NF",
        "Emissao":    "Data_Venda",
        "Produto":    "Codigo",
        "Cliente":    "Cod_Cliente",
        "Unnamed:_6": "Cliente_Revenda",  # Nome do cliente — coluna sem cabeçalho no Senior
        "Qtde_Fat_":  "Quantidade",
        "Preco_Un_":  "Valor_Unitario",
        "Vlr_Liq_":   "Valor_Total",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # [FIX-FAMILIA] Filtra apenas NFE/NFS — remove linhas de família e totais
    if "Serie" not in df.columns:
        return criar_mock_pecas()
    df["Serie"] = df["Serie"].astype(str).str.strip()
    df = df[df["Serie"].isin(["NFE", "NFS"])]

    # Filtra código de produto numérico válido
    if "Codigo" not in df.columns:
        return criar_mock_pecas()
    df["Codigo"] = df["Codigo"].astype(str).str.strip()
    df = df[df["Codigo"].str.match(r"^\d+$", na=False)].dropna(subset=["Codigo"])

    if df.empty:
        return criar_mock_pecas()

    # Número da NF
    if "Numero_NF" in df.columns:
        df["Numero_NF"] = df["Numero_NF"].astype(str).str.strip()

    # Data
    if "Data_Venda" in df.columns:
        df["Data_Venda"] = pd.to_datetime(df["Data_Venda"], errors="coerce")
        if df["Data_Venda"].dt.tz is not None:
            df["Data_Venda"] = df["Data_Venda"].dt.tz_localize(None)
        df = df.dropna(subset=["Data_Venda"])

    # Valores numéricos
    for col in ["Quantidade", "Valor_Unitario", "Valor_Total"]:
        if col in df.columns:
            df[col] = limpar_moeda_brl(df[col])

    # [FIX-COLS] Cliente_Revenda já mapeado diretamente de Unnamed:_6
    # Se por algum motivo não veio, usa Cod_Cliente como fallback
    if "Cliente_Revenda" not in df.columns or df["Cliente_Revenda"].isna().all():
        if "Cod_Cliente" in df.columns:
            df["Cliente_Revenda"] = df["Cod_Cliente"].astype(str)
        else:
            df["Cliente_Revenda"] = "Não informado"

    df["Cliente_Revenda"] = (df["Cliente_Revenda"]
                              .astype(str).str.strip()
                              .replace(["nan", "", "None"], "Não informado"))

    # [FIX-CHAVE] Chave única para deduplicação na importação diária
    cod_cli = df.get("Cod_Cliente", df["Cliente_Revenda"])
    df["chave_nf"] = (
        df["Serie"].astype(str) + "-" +
        df.get("Numero_NF", pd.Series("0", index=df.index)).astype(str) + "-" +
        df["Codigo"].astype(str) + "-" +
        cod_cli.astype(str)
    )

    # Enriquece com descrição do catálogo
    df["Descricao_Peca"] = ""
    if df_catalogo is not None and not df_catalogo.empty:
        df_cat = df_catalogo.copy()
        df_cat["Codigo"] = df_cat["Codigo"].astype(str).str.strip()
        mapa = df_cat.set_index("Codigo")["Descricao"].to_dict()
        df["Descricao_Peca"] = df["Codigo"].map(mapa).fillna("")

    # [FIX-COLS] Colunas finais mapeadas exatamente para o schema do Supabase
    # Renomeia para os nomes exatos da tabela pecas_senior
    if "Numero_NF" in df.columns:
        df = df.rename(columns={"Numero_NF": "Numero"})

    # Data_Venda como string ISO para o tipo date do Supabase
    if "Data_Venda" in df.columns:
        df["Data_Venda"] = pd.to_datetime(df["Data_Venda"], errors="coerce").dt.strftime("%Y-%m-%d")

    # Valor_Total e Quantidade como float
    for col in ["Quantidade", "Valor_Unitario", "Valor_Total"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Colunas que existem no Supabase
    colunas_finais = [
        "Serie", "Numero", "Data_Venda", "Codigo", "Descricao_Peca",
        "Quantidade", "Valor_Unitario", "Valor_Total",
        "Cliente_Revenda", "chave_nf",
    ]
    for c in colunas_finais:
        if c not in df.columns:
            df[c] = "" if c not in ["Quantidade", "Valor_Unitario", "Valor_Total"] else 0.0

    return df[colunas_finais].reset_index(drop=True)


# ══════════════════════════════════════════════════════════════
# Processamento de planilha de DEVOLUÇÃO
# ══════════════════════════════════════════════════════════════

def _processar_devolucao(df: pd.DataFrame, df_catalogo=None) -> pd.DataFrame:
    """
    Processa planilha de devolução Senior.
    Mesma estrutura da planilha de venda, mas os valores são negativados
    para que Fat. Líquido = Bruto - Devolução funcione corretamente.
    """
    df_proc = _processar_senior(df, df_catalogo)
    if df_proc.empty:
        return df_proc
    # Negativar valores para representar devolução
    for col in ["Valor_Total", "Valor_Unitario", "Quantidade"]:
        if col in df_proc.columns:
            df_proc[col] = pd.to_numeric(df_proc[col], errors="coerce").fillna(0) * -1
    df_proc["Tipo"] = "Devolucao"
    return df_proc


# ══════════════════════════════════════════════════════════════
# Cache e processamento principal
# ══════════════════════════════════════════════════════════════

def _file_hash(file_bytes: bytes) -> str:
    return hashlib.md5(file_bytes).hexdigest()


@st.cache_data(show_spinner=False, ttl=300)
def _processar_bytes(file_hash: str, file_bytes: bytes, file_name: str,
                     catalogo_hash: str = "", catalogo_bytes: bytes = b"",
                     tipo: str = "venda") -> tuple[pd.DataFrame, bool]:
    """
    tipo = "venda"     → faturamento bruto (valores positivos)
    tipo = "devolucao" → devoluções (valores negativados automaticamente)
    """
    try:
        df_cat = None
        if catalogo_bytes:
            df_cat = ler_catalogo_xlsx(catalogo_bytes)
        df_raw = _ler_senior_xlsx(file_bytes)
        if tipo == "devolucao":
            df = _processar_devolucao(df_raw, df_cat)
        else:
            df = _processar_senior(df_raw, df_cat)
            df["Tipo"] = "Venda"
        if df.empty:
            st.warning(f"⚠️ Nenhum registro encontrado em '{file_name}'.")
            return criar_mock_pecas(), True
        return df, False
    except Exception as e:
        st.error(f"❌ Erro ao processar '{file_name}': {e}")
        return criar_mock_pecas(), True


@st.cache_data(ttl=3600, show_spinner=False)
def _ler_pecas_supabase() -> pd.DataFrame:
    try:
        from data.db import _sb
        client = _sb()
        todos, offset, page_size = [], 0, 1000
        while True:
            resp  = client.table("pecas_senior").select("*").range(offset, offset + page_size - 1).execute()
            batch = resp.data or []
            todos.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        if not todos:
            return pd.DataFrame()
        df = pd.DataFrame(todos)
        if "Data_Venda" in df.columns:
            df["Data_Venda"] = pd.to_datetime(df["Data_Venda"], errors="coerce")
        if "Valor_Total" in df.columns:
            df["Valor_Total"] = pd.to_numeric(df["Valor_Total"], errors="coerce").fillna(0)
        if "Quantidade" in df.columns:
            df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce").fillna(0)
        return df
    except Exception as e:
        st.warning(f"⚠️ Não foi possível ler do Supabase: {e}")
        return pd.DataFrame()


def preparar_pecas(_uploaded_file, _catalogo_file=None,
                   _devolucao_file=None) -> tuple[pd.DataFrame, bool]:
    """
    Combina planilha de venda (bruto) + planilha de devolução.
    Retorna DataFrame com coluna Tipo = Venda | Devolucao.
    Fat. Líquido = sum(Valor_Total) pois devoluções têm valores negativos.
    """
    cat_bytes, cat_hash = b"", ""
    if _catalogo_file is not None:
        _catalogo_file.seek(0)
        cat_bytes = _catalogo_file.read()
        cat_hash  = _file_hash(cat_bytes)

    df_venda    = pd.DataFrame()
    df_devolucao = pd.DataFrame()
    is_mock = True

    if _uploaded_file is not None:
        _uploaded_file.seek(0)
        file_bytes = _uploaded_file.read()
        fhash = _file_hash(file_bytes)
        df_venda, is_mock = _processar_bytes(fhash, file_bytes, _uploaded_file.name,
                                              cat_hash, cat_bytes, tipo="venda")

    if _devolucao_file is not None:
        _devolucao_file.seek(0)
        dev_bytes = _devolucao_file.read()
        dev_hash  = _file_hash(dev_bytes)
        df_devolucao, _ = _processar_bytes(dev_hash, dev_bytes, _devolucao_file.name,
                                            cat_hash, cat_bytes, tipo="devolucao")

    # Combina venda + devolução
    dfs = [df for df in [df_venda, df_devolucao] if not df.empty]
    if dfs:
        df_combined = pd.concat(dfs, ignore_index=True)
        if "Tipo" not in df_combined.columns:
            df_combined["Tipo"] = "Venda"
        if not is_mock:
            st.session_state["_pecas_df"]   = df_combined
            st.session_state["_pecas_nome"] = _uploaded_file.name if _uploaded_file else "combinado"
        return df_combined, is_mock

    # Fallback: Supabase
    df_sb = _ler_pecas_supabase()
    if not df_sb.empty:
        if "Tipo" not in df_sb.columns:
            df_sb["Tipo"] = "Venda"
        st.session_state["_pecas_df"]   = df_sb
        st.session_state["_pecas_nome"] = "Supabase"
        st.sidebar.caption(f"📂 Peças: {len(df_sb):,} registros")
        return df_sb, False

    if "_pecas_df" in st.session_state:
        st.sidebar.caption(f"📂 Peças: {st.session_state.get('_pecas_nome','cache')} (cache)")
        return st.session_state["_pecas_df"], False

    return criar_mock_pecas(), True


# ══════════════════════════════════════════════════════════════
# KPIs e análises
# ══════════════════════════════════════════════════════════════

def calcular_kpis_pecas(df: pd.DataFrame, df_orc: pd.DataFrame | None = None,
                        data_inicio=None, data_fim=None) -> dict:
    """
    Retorna KPIs separados por tipo:
    - fat_bruto:   soma das vendas (Tipo == Venda)
    - fat_dev:     soma das devoluções (valor absoluto, Tipo == Devolucao)
    - fat_liquido: bruto - devolução (= sum(Valor_Total) pois dev é negativo)
    - total_faturado: alias de fat_liquido para compatibilidade
    """
    _zero = {"total_faturado": 0, "fat_bruto": 0, "fat_devolucao": 0,
             "fat_liquido": 0, "total_pedidos": 0,
             "volume_itens": 0, "ticket_medio": 0, "qtd_skus": 0, "em_orcamento": 0}
    if df is None or df.empty:
        return _zero
    col_valor = next((c for c in ["Valor_Total", "Vlr_Liq_"] if c in df.columns), None)
    col_qtd   = next((c for c in ["Quantidade", "Qtde_Fat_"] if c in df.columns), None)
    col_cod   = next((c for c in ["Codigo", "Produto"] if c in df.columns), None)
    col_tipo  = "Tipo" if "Tipo" in df.columns else None

    df = df.copy()
    vals = pd.to_numeric(df[col_valor], errors="coerce").fillna(0) if col_valor else pd.Series([0.0]*len(df))

    if col_tipo:
        mask_venda = df[col_tipo] == "Venda"
        mask_dev   = df[col_tipo] == "Devolucao"
        fat_bruto  = float(vals[mask_venda].sum())
        fat_dev    = float(abs(vals[mask_dev].sum()))
    else:
        fat_bruto  = float(vals[vals >= 0].sum())
        fat_dev    = float(abs(vals[vals < 0].sum()))

    fat_liquido = fat_bruto - fat_dev
    vol  = pd.to_numeric(df[col_qtd], errors="coerce").fillna(0).sum() if col_qtd else 0.0
    n    = len(df[df[col_tipo] == "Venda"]) if col_tipo else len(df)
    skus = df[col_cod].nunique() if col_cod else 0

    em_orc = 0.0
    if df_orc is not None and not df_orc.empty and "Status_Orc" in df_orc.columns:
        ag = df_orc[df_orc["Status_Orc"] == "Aguardando"]
        em_orc = pd.to_numeric(ag.get("Valor_Total", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()

    return {
        "total_faturado":  fat_liquido,   # compatibilidade
        "fat_bruto":       fat_bruto,
        "fat_devolucao":   fat_dev,
        "fat_liquido":     fat_liquido,
        "total_pedidos":   int(n),
        "volume_itens":    float(vol),
        "ticket_medio":    float(fat_liquido/n) if n > 0 else 0.0,
        "qtd_skus":        int(skus),
        "em_orcamento":    float(em_orc),
    }


def calcular_curva_abc_por_codigo(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """ABC baseado no Faturamento Líquido — exclui devoluções isoladamente,
    usa Valor_Total que já é líquido quando bruto+dev são combinados."""
    _cols = ["Codigo", "Descricao_Peca", "Valor_Total", "Pct", "Pct_Acum", "Curva"]
    if df is None or df.empty:
        return pd.DataFrame(columns=_cols)
    # Filtra apenas vendas para ABC (devoluções são negativas mas já embutidas)
    if "Tipo" in df.columns:
        df = df[df["Tipo"] == "Venda"].copy()
    if df.empty:
        return pd.DataFrame(columns=_cols)
    col_cod   = next((c for c in ["Codigo", "Produto"] if c in df.columns), None)
    col_valor = next((c for c in ["Valor_Total", "Vlr_Liq_"] if c in df.columns), None)
    col_desc  = next((c for c in ["Descricao_Peca", "Descricao"] if c in df.columns), col_cod)
    if not col_cod or not col_valor:
        return pd.DataFrame(columns=_cols)
    df = df.copy()
    df["_cod"]   = df[col_cod].astype(str)
    df["_valor"] = pd.to_numeric(df[col_valor], errors="coerce").fillna(0)
    df["_desc"]  = df[col_desc].astype(str) if col_desc else df["_cod"]
    grp = df.groupby("_cod").agg(Valor_Total=("_valor","sum"), Descricao_Peca=("_desc","first")).reset_index().rename(columns={"_cod":"Codigo"})
    grp = grp[grp["Valor_Total"] > 0].sort_values("Valor_Total", ascending=False).reset_index(drop=True)
    if grp.empty:
        return pd.DataFrame(columns=_cols)
    total = grp["Valor_Total"].sum()
    grp["Pct"]      = grp["Valor_Total"] / total * 100
    grp["Pct_Acum"] = grp["Pct"].cumsum()
    grp["Curva"]    = grp["Pct_Acum"].apply(lambda x: "A" if x <= 80 else ("B" if x <= 95 else "C"))
    return grp.head(top_n).reset_index(drop=True)


def calcular_top10_revendas(df: pd.DataFrame) -> pd.DataFrame:
    """Top 10 revendas pelo Faturamento Líquido (bruto - devolução)."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["Cliente_Revenda", "Valor_Total"])
    col_cli = next((c for c in ["Cliente_Revenda", "Cliente"] if c in df.columns), None)
    col_val = next((c for c in ["Valor_Total", "Vlr_Liq_"] if c in df.columns), None)
    if not col_cli or not col_val:
        return pd.DataFrame(columns=["Cliente_Revenda", "Valor_Total"])
    df = df.copy()
    df["Cliente_Revenda"] = df[col_cli].astype(str)
    df["Valor_Total"]     = pd.to_numeric(df[col_val], errors="coerce").fillna(0)
    top = df.groupby("Cliente_Revenda")["Valor_Total"].sum().reset_index()
    top = top[~top["Cliente_Revenda"].isin(["nan","","Não informado","N/A","-"])]
    return top[top["Valor_Total"] > 0].sort_values("Valor_Total", ascending=False).head(10).reset_index(drop=True)


def calcular_abc_por_revenda(df, top_n_revendas=20, lead_time_dias=15,
                              data_ini_filtro=None, data_fim_filtro=None):
    if df is None or df.empty:
        return pd.DataFrame(), 0, "", ""
    col_cli   = next((c for c in ["Cliente_Revenda","Cliente"] if c in df.columns), None)
    col_cod   = next((c for c in ["Codigo","Produto"] if c in df.columns), None)
    col_valor = next((c for c in ["Valor_Total","Vlr_Liq_"] if c in df.columns), None)
    col_qtd   = next((c for c in ["Quantidade","Qtde_Fat_"] if c in df.columns), None)
    col_desc  = next((c for c in ["Descricao_Peca","Descricao"] if c in df.columns), col_cod)
    col_data  = next((c for c in ["Data_Venda","Emissao"] if c in df.columns), None)
    if not col_cli or not col_cod or not col_valor:
        return pd.DataFrame(), 0, "", ""
    df = df.copy()
    df["_cli"]   = df[col_cli].astype(str).str.strip()
    df["_cod"]   = df[col_cod].astype(str).str.strip()
    df["_valor"] = pd.to_numeric(df[col_valor], errors="coerce").fillna(0)
    df["_qtd"]   = pd.to_numeric(df[col_qtd],   errors="coerce").fillna(0) if col_qtd else 0
    df["_desc"]  = df[col_desc].astype(str) if col_desc else df["_cod"]
    ini_str = fim_str = "—"
    dias_periodo = 365
    if col_data:
        df["_data"] = pd.to_datetime(df[col_data], errors="coerce", dayfirst=True)
        if data_ini_filtro:
            df = df[df["_data"].dt.date >= data_ini_filtro]
        if data_fim_filtro:
            df = df[df["_data"].dt.date <= data_fim_filtro]
        if df.empty:
            return pd.DataFrame(), 0, "", ""
        d_ini = df["_data"].min()
        d_fim = df["_data"].max()
        dias_periodo = max((d_fim - d_ini).days, 1)
        ini_str = d_ini.strftime("%d/%m/%Y")
        fim_str = d_fim.strftime("%d/%m/%Y")
    top_revendas = df.groupby("_cli")["_valor"].sum().nlargest(top_n_revendas).index.tolist()
    resultados = []
    for revenda in top_revendas:
        df_rev = df[df["_cli"] == revenda].copy()
        grp = df_rev.groupby("_cod").agg(
            Descricao_Peca=("_desc","first"), Valor_Total=("_valor","sum"), Quantidade=("_qtd","sum")
        ).reset_index().rename(columns={"_cod":"Codigo"})
        if grp.empty or grp["Valor_Total"].sum() == 0:
            continue
        total_rev = grp["Valor_Total"].sum()
        grp = grp.sort_values("Valor_Total", ascending=False)
        grp["Pct"]      = grp["Valor_Total"] / total_rev * 100
        grp["Pct_Acum"] = grp["Pct"].cumsum()
        grp["Curva"]    = grp["Pct_Acum"].apply(lambda x: "A" if x <= 80 else ("B" if x <= 95 else "C"))
        grp["Media_Diaria"] = grp["Quantidade"] / dias_periodo
        grp["Estoque_Minimo_Sugerido"] = grp["Media_Diaria"].apply(
            lambda x: max(round(x * lead_time_dias, 1), 1.0) if x > 0 else 0.0
        )
        grp["Cliente_Revenda"] = revenda
        resultados.append(grp)
    if not resultados:
        return pd.DataFrame(), dias_periodo, ini_str, fim_str
    df_final = pd.concat(resultados, ignore_index=True)[[
        "Cliente_Revenda","Codigo","Descricao_Peca",
        "Valor_Total","Quantidade","Pct","Pct_Acum","Curva",
        "Media_Diaria","Estoque_Minimo_Sugerido",
    ]]
    return df_final, dias_periodo, ini_str, fim_str
