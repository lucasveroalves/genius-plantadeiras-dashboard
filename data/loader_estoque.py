"""
data/loader_estoque.py v4 — Genius Plantadeiras

Novidades v4:
  • Removida toda lógica de importação de planilhas XLSX/CSV para estoque.
  • Persistência de estoque (pátio e revendas) agora exclusivamente via st.session_state.
  • Funções CRUD mantidas com mesmas assinaturas, mas operando sobre listas em sessão.
  • Demais módulos (forecast, produção, orçamentos) permanecem inalterados.
"""

from __future__ import annotations

import io
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st

# ── Diretório base ────────────────────────────────────────────
DATABASE_DIR = Path(__file__).parent.parent / "database"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)

# ── Arquivos (apenas para forecast, produção e orçamentos) ───
CSV_FORECAST    = DATABASE_DIR / "forecast.csv"
CSV_PRODUCAO    = DATABASE_DIR / "producao.csv"
CSV_ORCAMENTOS  = DATABASE_DIR / "orcamentos_pecas.csv"

# ── Schemas ───────────────────────────────────────────────────
COLS_PATIO = [
    "Codigo", "Modelo", "Tipo", "Ano", "Cor",
    "Numero_Serie", "Data_Entrada", "Status_Patio", "Observacoes",
]
COLS_REVENDAS = [
    "Codigo", "Modelo", "Revenda", "Contato", "Cidade", "Estado",
    "Data_Envio", "Data_Retorno_Prevista", "Status_Revenda", "Observacoes",
]
COLS_FORECAST = ["Ano", "Mes", "Meta_Valor"]
COLS_PRODUCAO = [
    "Equipamento", "Cliente", "Representante", "Data_Pedido",
    "Data_Inicio_Producao", "Data_Entrega_Prevista", "Data_Entrega_Real",
    "Status_Producao", "Observacoes",
]
COLS_ORCAMENTOS = [
    "Nr_Pedido", "Data_Orcamento", "Cliente_Revenda",
    "Descricao_Peca", "Quantidade", "Valor_Unit", "Valor_Total",
    "Status_Orc", "Observacoes",
]
STATUS_ORC = ["Em Orçamento", "Aprovado", "Faturado", "Cancelado"]

TIPOS_PATIO  = ["Nova", "Usada", "Recal", "Feira", "Demonstração"]
STATUS_PATIO = ["Disponível", "Reservada", "Vendida", "Em Manutenção"]
STATUS_REV   = ["Na Revenda", "Retornou", "Vendida"]
STATUS_PROD  = ["Aguardando", "Em Produção", "Pronto", "Entregue", "Cancelado"]

MESES_PT = {
    1: "Janeiro",  2: "Fevereiro", 3: "Março",    4: "Abril",
    5: "Maio",     6: "Junho",     7: "Julho",     8: "Agosto",
    9: "Setembro", 10: "Outubro",  11: "Novembro", 12: "Dezembro",
}

# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def _norm(s: str) -> str:
    """Normaliza string: remove acentos, lowercase, strip."""
    return (
        unicodedata.normalize("NFD", str(s))
        .encode("ascii", "ignore").decode()
        .lower().strip()
    )


def _ler_csv(path: Path, cols: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=cols)
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            df = pd.read_csv(path, encoding=enc)
            if len(df.columns) >= 1:
                for c in cols:
                    if c not in df.columns:
                        df[c] = ""
                df = df[cols].copy()
                df = df.dropna(how="all")
                df = df[~df.apply(
                    lambda r: all(str(v).strip() in ("", "nan", "None") for v in r), axis=1
                )]
                return df.reset_index(drop=True)
        except Exception:
            continue
    return pd.DataFrame(columns=cols)


def _gravar(df: pd.DataFrame, csv_path: Path, xlsx_path: Path | None = None):
    tmp = csv_path.with_suffix(".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(csv_path)
    if xlsx_path:
        try:
            df.to_excel(xlsx_path, index=False, engine="openpyxl")
        except Exception:
            pass


def _para_xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════
# ESTOQUE PÁTIO (session_state)
# ══════════════════════════════════════════════════════════════

def _init_patio():
    if "estoque_patio" not in st.session_state:
        st.session_state.estoque_patio = []

def ler_patio() -> pd.DataFrame:
    _init_patio()
    return pd.DataFrame(st.session_state.estoque_patio)

def salvar_patio(df: pd.DataFrame):
    st.session_state.estoque_patio = df.to_dict(orient="records")

def adicionar_patio(registro: dict) -> bool:
    try:
        _init_patio()
        st.session_state.estoque_patio.append(registro)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

def atualizar_patio(idx: int, campo: str, valor) -> bool:
    try:
        _init_patio()
        if 0 <= idx < len(st.session_state.estoque_patio):
            st.session_state.estoque_patio[idx][campo] = valor
            return True
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")
    return False

def excluir_patio(idx: int) -> bool:
    try:
        _init_patio()
        if 0 <= idx < len(st.session_state.estoque_patio):
            del st.session_state.estoque_patio[idx]
            return True
    except Exception as e:
        st.error(f"Erro ao excluir: {e}")
    return False

def exportar_patio() -> bytes:
    return _para_xlsx_bytes(ler_patio())


# ══════════════════════════════════════════════════════════════
# ESTOQUE REVENDAS (session_state)
# ══════════════════════════════════════════════════════════════

def _init_revendas():
    if "estoque_revendas" not in st.session_state:
        st.session_state.estoque_revendas = []

def ler_revendas() -> pd.DataFrame:
    _init_revendas()
    return pd.DataFrame(st.session_state.estoque_revendas)

def salvar_revendas(df: pd.DataFrame):
    st.session_state.estoque_revendas = df.to_dict(orient="records")

def adicionar_revenda(registro: dict) -> bool:
    try:
        _init_revendas()
        st.session_state.estoque_revendas.append(registro)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

def atualizar_revenda(idx: int, campo: str, valor) -> bool:
    try:
        _init_revendas()
        if 0 <= idx < len(st.session_state.estoque_revendas):
            st.session_state.estoque_revendas[idx][campo] = valor
            return True
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")
    return False

def excluir_revenda(idx: int) -> bool:
    try:
        _init_revendas()
        if 0 <= idx < len(st.session_state.estoque_revendas):
            del st.session_state.estoque_revendas[idx]
            return True
    except Exception as e:
        st.error(f"Erro ao excluir: {e}")
    return False

def exportar_revendas() -> bytes:
    return _para_xlsx_bytes(ler_revendas())


# ══════════════════════════════════════════════════════════════
# FORECAST
# ══════════════════════════════════════════════════════════════

def ler_forecast() -> pd.DataFrame:
    return _ler_csv(CSV_FORECAST, COLS_FORECAST)


def salvar_forecast(df: pd.DataFrame):
    _gravar(df, CSV_FORECAST)


def upsert_forecast(ano: int, mes: int, meta: float):
    df = ler_forecast()
    mask = (
        (df["Ano"].astype(str) == str(ano)) &
        (df["Mes"].astype(str) == str(mes))
    )
    if mask.any():
        df.loc[mask, "Meta_Valor"] = meta
    else:
        df = pd.concat(
            [df, pd.DataFrame([{"Ano": ano, "Mes": mes, "Meta_Valor": meta}])],
            ignore_index=True,
        )
    df["Meta_Valor"] = pd.to_numeric(df["Meta_Valor"], errors="coerce").fillna(0)
    df = df.sort_values(["Ano", "Mes"]).reset_index(drop=True)
    salvar_forecast(df)


def excluir_forecast(ano: int, mes: int):
    df = ler_forecast()
    df = df[~(
        (df["Ano"].astype(str) == str(ano)) &
        (df["Mes"].astype(str) == str(mes))
    )].reset_index(drop=True)
    salvar_forecast(df)


# ══════════════════════════════════════════════════════════════
# PRODUÇÃO (ciclo + lead time)
# ══════════════════════════════════════════════════════════════

def ler_producao() -> pd.DataFrame:
    return _ler_csv(CSV_PRODUCAO, COLS_PRODUCAO)


def salvar_producao(df: pd.DataFrame):
    _gravar(df, CSV_PRODUCAO, CSV_PRODUCAO.with_suffix(".xlsx"))


def adicionar_producao(registro: dict) -> bool:
    try:
        df = ler_producao()
        df = pd.concat([df, pd.DataFrame([registro])], ignore_index=True)
        salvar_producao(df)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False


def atualizar_producao(idx: int, dados: dict) -> bool:
    try:
        df = ler_producao()
        if 0 <= idx < len(df):
            for k, v in dados.items():
                df.at[idx, k] = v
            salvar_producao(df)
            return True
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")
    return False


def excluir_producao(idx: int) -> bool:
    try:
        df = ler_producao()
        if 0 <= idx < len(df):
            df = df.drop(index=idx).reset_index(drop=True)
            salvar_producao(df)
            return True
    except Exception as e:
        st.error(f"Erro ao excluir: {e}")
    return False


def importar_producao(uploaded) -> tuple[int, str]:
    # (Mantido para compatibilidade com PCP, embora possa não ser mais usado)
    try:
        nome = uploaded.name.lower()
        if nome.endswith(".csv"):
            for enc in ("utf-8-sig", "utf-8", "latin-1"):
                try:
                    uploaded.seek(0)
                    df_up = pd.read_csv(uploaded, encoding=enc,
                                        sep=None, engine="python")
                    break
                except Exception:
                    continue
        else:
            uploaded.seek(0)
            df_up = pd.read_excel(uploaded, engine="openpyxl")
    except Exception:
        return 0, "Erro ao ler arquivo."

    for c in COLS_PRODUCAO:
        if c not in df_up.columns:
            df_up[c] = ""
    df_exist = ler_producao()
    df_final = pd.concat([df_exist, df_up], ignore_index=True).drop_duplicates()
    salvar_producao(df_final)
    return len(df_up), "OK"


def exportar_producao() -> bytes:
    return _para_xlsx_bytes(ler_producao())


def calcular_kpis_producao(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {
            "total": 0, "em_producao": 0, "prontos": 0,
            "entregues": 0, "ciclo_medio_dias": 0.0, "atrasados": 0,
        }
    total     = len(df)
    em_prod   = int((df["Status_Producao"] == "Em Produção").sum())
    prontos   = int((df["Status_Producao"] == "Pronto").sum())
    entregues = int((df["Status_Producao"] == "Entregue").sum())

    ciclo_medio = 0.0
    try:
        df2 = df[df["Data_Entrega_Real"].astype(str).str.strip() != ""].copy()
        df2["_ini"] = pd.to_datetime(
            df2["Data_Inicio_Producao"], errors="coerce", dayfirst=True)
        df2["_fim"] = pd.to_datetime(
            df2["Data_Entrega_Real"], errors="coerce", dayfirst=True)
        dias = (df2["_fim"] - df2["_ini"]).dt.days.dropna()
        ciclo_medio = float(dias.mean()) if not dias.empty else 0.0
    except Exception:
        pass

    atrasados = 0
    try:
        import datetime as _dt
        hoje = pd.Timestamp(_dt.date.today())
        df3 = df[~df["Status_Producao"].isin(["Entregue", "Cancelado"])].copy()
        df3["_prev"] = pd.to_datetime(
            df3["Data_Entrega_Prevista"], errors="coerce", dayfirst=True)
        atrasados = int((df3["_prev"] < hoje).sum())
    except Exception:
        pass

    return {
        "total":            total,
        "em_producao":      em_prod,
        "prontos":          prontos,
        "entregues":        entregues,
        "ciclo_medio_dias": round(ciclo_medio, 1),
        "atrasados":        atrasados,
    }


# ══════════════════════════════════════════════════════════════
# ORÇAMENTOS DE PEÇAS
# ══════════════════════════════════════════════════════════════

def ler_orcamentos() -> pd.DataFrame:
    return _ler_csv(CSV_ORCAMENTOS, COLS_ORCAMENTOS)


def salvar_orcamentos(df: pd.DataFrame):
    _gravar(df, CSV_ORCAMENTOS)


def adicionar_orcamento(registro: dict) -> bool:
    try:
        df = ler_orcamentos()
        if not registro.get("Valor_Total"):
            try:
                registro["Valor_Total"] = (
                    float(registro.get("Quantidade", 0)) *
                    float(registro.get("Valor_Unit", 0))
                )
            except Exception:
                registro["Valor_Total"] = 0.0
        df = pd.concat([df, pd.DataFrame([registro])], ignore_index=True)
        salvar_orcamentos(df)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar orçamento: {e}")
        return False


def atualizar_status_orcamento(idx: int, novo_status: str) -> bool:
    try:
        df = ler_orcamentos()
        if 0 <= idx < len(df):
            df.at[idx, "Status_Orc"] = novo_status
            salvar_orcamentos(df)
            return True
    except Exception as e:
        st.error(f"Erro ao atualizar orçamento: {e}")
    return False


def excluir_orcamento(idx: int) -> bool:
    try:
        df = ler_orcamentos()
        if 0 <= idx < len(df):
            df = df.drop(index=idx).reset_index(drop=True)
            salvar_orcamentos(df)
            return True
    except Exception as e:
        st.error(f"Erro ao excluir orçamento: {e}")
    return False


def calcular_kpis_orcamentos(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {"total": 0, "em_orcamento": 0, "aprovado": 0,
                "faturado": 0, "valor_aberto": 0.0, "valor_faturado": 0.0}
    total       = len(df)
    em_orc      = int((df["Status_Orc"] == "Em Orçamento").sum()) if "Status_Orc" in df.columns else 0
    aprovado    = int((df["Status_Orc"] == "Aprovado").sum())     if "Status_Orc" in df.columns else 0
    faturado    = int((df["Status_Orc"] == "Faturado").sum())     if "Status_Orc" in df.columns else 0
    valor_total_col = pd.to_numeric(df.get("Valor_Total", pd.Series(dtype=float)), errors="coerce").fillna(0)
    mask_aberto = df["Status_Orc"].isin(["Em Orçamento", "Aprovado"]) if "Status_Orc" in df.columns else pd.Series([False]*len(df))
    valor_aberto   = float(valor_total_col[mask_aberto].sum())
    valor_faturado = float(valor_total_col[df["Status_Orc"] == "Faturado"].sum()) if "Status_Orc" in df.columns else 0.0
    return {
        "total":          total,
        "em_orcamento":   em_orc,
        "aprovado":       aprovado,
        "faturado":       faturado,
        "valor_aberto":   valor_aberto,
        "valor_faturado": valor_faturado,
    }


# ── Aliases para compatibilidade com estoque.py ───────────────
ler_revendas_estoque        = ler_revendas
adicionar_revenda_estoque   = adicionar_revenda
excluir_revenda_estoque     = excluir_revenda
exportar_revendas_estoque   = exportar_revendas
