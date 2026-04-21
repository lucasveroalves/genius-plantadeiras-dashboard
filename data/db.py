"""
data/db.py — Genius Implementos Agrícolas v15

Novas funções adicionadas:
  [DB-MIGR] importar_pecas_senior_para_supabase(df)
            Faz upsert em lotes de 1500 linhas usando a API Python do Supabase.
            Retorna (n_linhas_ok, "OK") em caso de sucesso ou (0, mensagem_erro).

Mantidas todas as funções existentes do v14.
"""

from __future__ import annotations
import math
import pandas as pd
import streamlit as st
from supabase import create_client, Client


# ══════════════════════════════════════════════════════════════
# Cliente Supabase (singleton cacheado — ttl=3600s)
# ══════════════════════════════════════════════════════════════

@st.cache_resource(ttl=3600)
def _get_client() -> Client:
    url  = st.secrets["supabase"]["url"]
    key  = st.secrets["supabase"]["key"]
    return create_client(url, key)


def _sb() -> Client:
    return _get_client()


# ══════════════════════════════════════════════════════════════
# Helpers internos
# ══════════════════════════════════════════════════════════════

def _safe_response(resp) -> list[dict]:
    """Extrai .data de uma resposta Supabase ou retorna lista vazia."""
    try:
        return resp.data or []
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════
# NFs em Demonstração
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def ler_nfs() -> list[dict]:
    return _safe_response(_sb().table("nf_demo").select("*").order("id").execute())


def adicionar_nf(registro: dict) -> bool:
    try:
        _sb().table("nf_demo").insert(registro).execute()
        ler_nfs.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar NF: {e}")
        return False


def excluir_nf(row_id: int) -> bool:
    try:
        _sb().table("nf_demo").delete().eq("id", row_id).execute()
        ler_nfs.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir NF: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# Produção / PCP
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def ler_producao() -> pd.DataFrame:
    data = _safe_response(_sb().table("producao").select("*").order("id").execute())
    return pd.DataFrame(data) if data else pd.DataFrame()


def adicionar_producao(registro: dict) -> bool:
    try:
        _sb().table("producao").insert(registro).execute()
        ler_producao.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar produção: {e}")
        return False


def excluir_producao(row_id: int) -> bool:
    try:
        _sb().table("producao").delete().eq("id", row_id).execute()
        ler_producao.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir produção: {e}")
        return False


def atualizar_producao_campo(row_id: int, campo: str, valor) -> bool:
    try:
        _sb().table("producao").update({campo: valor}).eq("id", row_id).execute()
        ler_producao.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar campo '{campo}': {e}")
        return False


def importar_producao(file) -> tuple[int, str]:
    try:
        if file.name.endswith(".csv"):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        registros = df.where(pd.notna(df), None).to_dict("records")
        if not registros:
            return 0, "Arquivo vazio."
        _sb().table("producao").insert(registros).execute()
        ler_producao.clear()
        return len(registros), "OK"
    except Exception as e:
        return 0, str(e)


def exportar_producao() -> bytes:
    df = ler_producao()
    from io import BytesIO
    buf = BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def calcular_kpis_producao(df: pd.DataFrame) -> dict:
    zeros = dict(total=0, em_producao=0, prontos=0, entregues=0,
                 atrasados=0, ciclo_medio_dias=0.0)
    if df is None or df.empty:
        return zeros
    hoje = pd.Timestamp("today").normalize()
    status = df.get("Status_Producao", pd.Series(dtype=str)).str.lower().str.strip()
    total        = len(df)
    em_producao  = int((status == "em produção").sum())
    prontos      = int((status == "pronto").sum())
    entregues    = int((status == "entregue").sum())
    prev_col     = pd.to_datetime(df.get("Data_Entrega_Prevista", pd.Series()), errors="coerce", dayfirst=True)
    atrasados    = int(
        ((prev_col < hoje) & ~status.isin(["entregue", "cancelado"])).sum()
    )
    if "Data_Inicio_Producao" in df.columns and "Data_Entrega_Real" in df.columns:
        ini  = pd.to_datetime(df["Data_Inicio_Producao"],  errors="coerce", dayfirst=True)
        real = pd.to_datetime(df["Data_Entrega_Real"],     errors="coerce", dayfirst=True)
        ciclos = (real - ini).dt.days.dropna()
        ciclo_medio = float(ciclos.mean()) if not ciclos.empty else 0.0
    else:
        ciclo_medio = 0.0
    return dict(total=total, em_producao=em_producao, prontos=prontos,
                entregues=entregues, atrasados=atrasados, ciclo_medio_dias=ciclo_medio)


# ══════════════════════════════════════════════════════════════
# Orçamentos
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def ler_orcamentos() -> pd.DataFrame:
    data = _safe_response(_sb().table("orcamentos").select("*").order("id").execute())
    return pd.DataFrame(data) if data else pd.DataFrame()


def adicionar_orcamento(registro: dict) -> bool:
    try:
        _sb().table("orcamentos").insert(registro).execute()
        ler_orcamentos.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar orçamento: {e}")
        return False


def excluir_orcamento(row_id: int) -> bool:
    try:
        _sb().table("orcamentos").delete().eq("id", row_id).execute()
        ler_orcamentos.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir orçamento: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# Usuários
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=60)
def ler_usuarios() -> dict:
    data = _safe_response(_sb().table("usuarios").select("*").execute())
    return {d["login"]: d for d in data} if data else {}


def criar_usuario(login: str, nome: str, perfil: str,
                  senha: str, is_admin: bool, abas: list) -> bool:
    import hashlib
    try:
        reg = {
            "login": login, "nome": nome, "perfil": perfil,
            "senha_hash": hashlib.sha256(senha.encode()).hexdigest(),
            "is_admin": is_admin, "abas_permitidas": abas,
        }
        _sb().table("usuarios").insert(reg).execute()
        ler_usuarios.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao criar usuário: {e}")
        return False


def alterar_senha(login: str, nova_senha: str) -> bool:
    import hashlib
    try:
        novo_hash = hashlib.sha256(nova_senha.encode()).hexdigest()
        _sb().table("usuarios").update({"senha_hash": novo_hash}).eq("login", login).execute()
        ler_usuarios.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao alterar senha: {e}")
        return False


def excluir_usuario(login: str) -> bool:
    try:
        _sb().table("usuarios").delete().eq("login", login).execute()
        ler_usuarios.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir usuário: {e}")
        return False


def atualizar_usuario(login: str, campos: dict) -> bool:
    try:
        _sb().table("usuarios").update(campos).eq("login", login).execute()
        ler_usuarios.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar usuário: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# Lead Time
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def ler_leadtime() -> pd.DataFrame:
    data = _safe_response(_sb().table("leadtime").select("*").order("id").execute())
    return pd.DataFrame(data) if data else pd.DataFrame()


def adicionar_leadtime(registro: dict) -> bool:
    try:
        _sb().table("leadtime").insert(registro).execute()
        ler_leadtime.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar lead time: {e}")
        return False


def excluir_leadtime(row_id: int) -> bool:
    try:
        _sb().table("leadtime").delete().eq("id", row_id).execute()
        ler_leadtime.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir lead time: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# Estoque
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def ler_estoque() -> pd.DataFrame:
    data = _safe_response(_sb().table("estoque").select("*").order("id").execute())
    return pd.DataFrame(data) if data else pd.DataFrame()


def adicionar_estoque(registro: dict) -> bool:
    try:
        _sb().table("estoque").insert(registro).execute()
        ler_estoque.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar estoque: {e}")
        return False


def excluir_estoque(row_id: int) -> bool:
    try:
        _sb().table("estoque").delete().eq("id", row_id).execute()
        ler_estoque.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir estoque: {e}")
        return False


def atualizar_estoque_campo(row_id: int, campo: str, valor) -> bool:
    try:
        _sb().table("estoque").update({campo: valor}).eq("id", row_id).execute()
        ler_estoque.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar estoque: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# [DB-MIGR]  importar_pecas_senior_para_supabase
# ══════════════════════════════════════════════════════════════

def importar_pecas_senior_para_supabase(
    df: pd.DataFrame,
    tabela: str = "pecas_senior",
    batch_size: int = 1500,
    conflict_column: str = "id_linha",
) -> tuple[int, str]:
    """
    Importa (upsert) o DataFrame da planilha Senior ERP para o Supabase
    em lotes (batches) para evitar timeouts com +170 mil linhas.

    Parâmetros
    ----------
    df              : DataFrame já processado por preparar_pecas()
    tabela          : nome da tabela no Supabase (default: "pecas_senior")
    batch_size      : tamanho de cada lote — 1500 linhas é seguro para a
                      maioria dos planos Supabase (payload < 5 MB por batch)
    conflict_column : coluna usada como chave de upsert; deve existir na tabela
                      como PRIMARY KEY ou UNIQUE. Se None, usa INSERT puro.

    Retorna
    -------
    (n_linhas_inseridas, "OK") em sucesso
    (0, mensagem_de_erro)      em falha
    """
    if df is None or df.empty:
        return 0, "DataFrame vazio — nada a importar."

    try:
        client = _sb()

        # ── 1. Limpeza/normalização mínima do DataFrame ───────
        df = df.copy()

        # Converte datas para string ISO (Supabase aceita date/timestamp como string)
        for col in df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
            df[col] = df[col].dt.strftime("%Y-%m-%d")

        # Substitui NaN/NaT/inf/-inf por None (JSON null)
        import numpy as np
        df = df.replace([np.inf, -np.inf], None)
        df = df.where(pd.notna(df), other=None)

        # Converte para lista de dicionários
        registros: list[dict] = df.to_dict("records")
        total     = len(registros)
        n_batches = math.ceil(total / batch_size)
        n_ok      = 0

        # ── 2. Loop de upsert por lote ─────────────────────────
        for i in range(n_batches):
            lote = registros[i * batch_size : (i + 1) * batch_size]

            if conflict_column and conflict_column in df.columns:
                # upsert: atualiza se a chave já existir, insere se não
                resp = (
                    client
                    .table(tabela)
                    .upsert(lote, on_conflict=conflict_column)
                    .execute()
                )
            else:
                # insert puro quando não há chave de conflito definida
                resp = client.table(tabela).insert(lote).execute()

            n_inseridos = len(resp.data) if resp.data else len(lote)
            n_ok += n_inseridos

        return n_ok, "OK"

    except Exception as exc:
        return 0, str(exc)


# ══════════════════════════════════════════════════════════════
# Revendas Cadastro (tabela: revendas_cadastro)
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def ler_revendas_cadastro() -> pd.DataFrame:
    data = _safe_response(_sb().table("revendas_cadastro").select("*").order("id").execute())
    return pd.DataFrame(data) if data else pd.DataFrame()

def adicionar_revenda_cadastro(registro: dict) -> bool:
    try:
        _sb().table("revendas_cadastro").insert(registro).execute()
        ler_revendas_cadastro.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar revenda: {e}")
        return False

def excluir_revenda_cadastro(row_id: int) -> bool:
    try:
        _sb().table("revendas_cadastro").delete().eq("id", row_id).execute()
        ler_revendas_cadastro.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir revenda: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# Funções complementares — Orçamentos
# ══════════════════════════════════════════════════════════════

def atualizar_orcamento(row_id: int, campos: dict) -> bool:
    try:
        _sb().table("orcamentos").update(campos).eq("id", row_id).execute()
        ler_orcamentos.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar orçamento: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# Funções complementares — Lead Time
# ══════════════════════════════════════════════════════════════

def atualizar_leadtime(row_id: int, campos: dict) -> bool:
    try:
        _sb().table("leadtime").update(campos).eq("id", row_id).execute()
        ler_leadtime.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar lead time: {e}")
        return False


def calcular_kpis_leadtime(df: pd.DataFrame) -> dict:
    zeros = dict(total_registros=0, aguardando_req=0, req_enviada=0,
                 nf_emitida=0, lead_medio_dias=None, lead_max_dias=None)
    if df is None or df.empty:
        return zeros
    total = len(df)
    status_col = df.get("Status_Lead", pd.Series(dtype=str)).astype(str)
    aguardando = int((status_col == "Orçamento Fechado").sum())
    req_env    = int((status_col == "Req. Enviada").sum())
    nf_emit    = int((status_col == "NF Emitida").sum())
    # Calcula lead time nos concluídos
    lead_med = None
    lead_max = None
    try:
        concluidos = df[status_col == "NF Emitida"].copy()
        if not concluidos.empty:
            from datetime import datetime as _dt
            def _calc(row):
                try:
                    d1 = _dt.strptime(str(row["Data_Orcamento_Fechado"]).strip(), "%d/%m/%Y")
                    d2 = _dt.strptime(str(row["Data_NF"]).strip(), "%d/%m/%Y")
                    return (d2 - d1).days
                except Exception:
                    return None
            concluidos["_dias"] = concluidos.apply(_calc, axis=1)
            dias_validos = concluidos["_dias"].dropna()
            if not dias_validos.empty:
                lead_med = round(float(dias_validos.mean()), 1)
                lead_max = int(dias_validos.max())
    except Exception:
        pass
    return dict(total_registros=total, aguardando_req=aguardando,
                req_enviada=req_env, nf_emitida=nf_emit,
                lead_medio_dias=lead_med, lead_max_dias=lead_max)


# ══════════════════════════════════════════════════════════════
# Pátio e Revendas Estoque (tabelas: patio / revendas_estoque)
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def ler_patio() -> pd.DataFrame:
    data = _safe_response(_sb().table("patio").select("*").order("id").execute())
    return pd.DataFrame(data) if data else pd.DataFrame()

def adicionar_patio(registro: dict) -> bool:
    try:
        _sb().table("patio").insert(registro).execute()
        ler_patio.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar ao pátio: {e}")
        return False

def excluir_patio(row_id: int) -> bool:
    try:
        _sb().table("patio").delete().eq("id", row_id).execute()
        ler_patio.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir do pátio: {e}")
        return False

def exportar_patio() -> bytes:
    from io import BytesIO
    buf = BytesIO()
    ler_patio().to_excel(buf, index=False)
    return buf.getvalue()

@st.cache_data(ttl=30)
def ler_revendas_estoque() -> pd.DataFrame:
    data = _safe_response(_sb().table("revendas_estoque").select("*").order("id").execute())
    return pd.DataFrame(data) if data else pd.DataFrame()

def adicionar_revenda_estoque(registro: dict) -> bool:
    try:
        _sb().table("revendas_estoque").insert(registro).execute()
        ler_revendas_estoque.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar revenda estoque: {e}")
        return False

def excluir_revenda_estoque(row_id: int) -> bool:
    try:
        _sb().table("revendas_estoque").delete().eq("id", row_id).execute()
        ler_revendas_estoque.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir revenda estoque: {e}")
        return False

def exportar_revendas_estoque() -> bytes:
    from io import BytesIO
    buf = BytesIO()
    ler_revendas_estoque().to_excel(buf, index=False)
    return buf.getvalue()
