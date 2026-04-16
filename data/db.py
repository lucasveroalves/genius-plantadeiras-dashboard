"""
data/db.py — Genius Plantadeiras
Camada de persistência via Supabase (PostgreSQL gratuito).
Substitui os CSVs locais que se perdem a cada reinicialização no Streamlit Cloud.

Tabelas utilizadas:
  • genius_producao
  • genius_orcamentos
  • genius_nf_demo
  • genius_revendas
  • genius_estoque_patio
  • genius_estoque_revendas
  • genius_usuarios         (senhas em hash — gerenciamento de acesso)
  • genius_pecas_cache      (planilha Senior importada)

CONFIGURAÇÃO (secrets.toml):
  [supabase]
  url    = "https://XXXX.supabase.co"
  key    = "eyJ..."          # chave anon/public
"""

from __future__ import annotations

import io
import json
import hashlib
import hmac
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

# ──────────────────────────────────────────────────────────────
# Cliente Supabase (lazy — só conecta quando necessário)
# ──────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _get_client():
    """Retorna cliente Supabase cacheado para toda a sessão."""
    try:
        from supabase import create_client
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Supabase não configurado: {e}")
        return None


def _sb():
    return _get_client()


# ──────────────────────────────────────────────────────────────
# Helpers genéricos
# ──────────────────────────────────────────────────────────────

def _to_df(rows: list[dict], cols: list[str]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    # Remove colunas internas do Supabase
    for c in ["id", "created_at"]:
        if c in df.columns and c not in cols:
            df = df.drop(columns=[c])
    return df[cols].reset_index(drop=True)


def _agora() -> str:
    return datetime.utcnow().isoformat()


# ══════════════════════════════════════════════════════════════
# PRODUÇÃO
# ══════════════════════════════════════════════════════════════

_COLS_PROD = [
    "Equipamento", "Cliente", "Representante", "Data_Pedido",
    "Data_Inicio_Producao", "Data_Entrega_Prevista", "Data_Entrega_Real",
    "Status_Producao", "Observacoes",
]

def ler_producao() -> pd.DataFrame:
    sb = _sb()
    if not sb:
        return pd.DataFrame(columns=_COLS_PROD)
    try:
        res = sb.table("genius_producao").select("*").order("id").execute()
        return _to_df(res.data or [], _COLS_PROD)
    except Exception as e:
        st.error(f"Erro ao ler produção: {e}")
        return pd.DataFrame(columns=_COLS_PROD)


def adicionar_producao(reg: dict) -> bool:
    sb = _sb()
    if not sb:
        return False
    try:
        payload = {k: str(v) if v is not None else "" for k, v in reg.items()
                   if k in _COLS_PROD}
        sb.table("genius_producao").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar produção: {e}")
        return False


def excluir_producao(row_id: int) -> bool:
    """row_id = id real do Supabase (coluna 'id')"""
    sb = _sb()
    if not sb:
        return False
    try:
        sb.table("genius_producao").delete().eq("id", row_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir: {e}")
        return False


def importar_producao(uploaded) -> tuple[int, str]:
    try:
        uploaded.seek(0)
        if uploaded.name.lower().endswith(".csv"):
            df = pd.read_csv(uploaded, encoding="utf-8-sig")
        else:
            df = pd.read_excel(uploaded, engine="openpyxl")
    except Exception:
        return 0, "Erro ao ler arquivo."
    count = 0
    for _, row in df.iterrows():
        reg = {c: str(row.get(c, "")) for c in _COLS_PROD}
        if adicionar_producao(reg):
            count += 1
    return count, "OK"


def exportar_producao() -> bytes:
    buf = io.BytesIO()
    ler_producao().to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def calcular_kpis_producao(df: pd.DataFrame) -> dict:
    from data.loader_estoque import calcular_kpis_producao as _kpi
    return _kpi(df)


# ══════════════════════════════════════════════════════════════
# ORÇAMENTOS DE PEÇAS
# ══════════════════════════════════════════════════════════════

_COLS_ORC = [
    "Nr_Pedido", "Data_Orcamento", "Cliente_Revenda",
    "Descricao_Peca", "Quantidade", "Valor_Unit", "Valor_Total",
    "Status_Orc", "Observacoes",
]

def ler_orcamentos() -> pd.DataFrame:
    sb = _sb()
    if not sb:
        return pd.DataFrame(columns=_COLS_ORC)
    try:
        res = sb.table("genius_orcamentos").select("*").order("id").execute()
        return _to_df(res.data or [], _COLS_ORC)
    except Exception as e:
        st.error(f"Erro ao ler orçamentos: {e}")
        return pd.DataFrame(columns=_COLS_ORC)


def adicionar_orcamento(reg: dict) -> bool:
    sb = _sb()
    if not sb:
        return False
    try:
        if not reg.get("Valor_Total"):
            try:
                reg["Valor_Total"] = float(reg.get("Quantidade", 0)) * float(reg.get("Valor_Unit", 0))
            except Exception:
                reg["Valor_Total"] = 0.0
        payload = {k: str(v) if v is not None else "" for k, v in reg.items()
                   if k in _COLS_ORC}
        sb.table("genius_orcamentos").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar orçamento: {e}")
        return False


def excluir_orcamento(row_id: int) -> bool:
    sb = _sb()
    if not sb:
        return False
    try:
        sb.table("genius_orcamentos").delete().eq("id", row_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir orçamento: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# NF EM DEMONSTRAÇÃO
# ══════════════════════════════════════════════════════════════

_COLS_NF = ["Data_Emissao", "Nr_NF", "Cliente", "Maquina", "Observacoes"]

def ler_nfs() -> list[dict]:
    sb = _sb()
    if not sb:
        return []
    try:
        res = sb.table("genius_nf_demo").select("*").order("id").execute()
        rows = res.data or []
        # Retorna lista de dicts incluindo 'id' para deleção
        return rows
    except Exception as e:
        st.error(f"Erro ao ler NFs: {e}")
        return []


def adicionar_nf(reg: dict) -> bool:
    sb = _sb()
    if not sb:
        return False
    try:
        payload = {k: reg.get(k, "") for k in _COLS_NF}
        sb.table("genius_nf_demo").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar NF: {e}")
        return False


def excluir_nf(row_id: int) -> bool:
    sb = _sb()
    if not sb:
        return False
    try:
        sb.table("genius_nf_demo").delete().eq("id", row_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir NF: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# CADASTRO DE REVENDAS
# ══════════════════════════════════════════════════════════════

_COLS_REV_CAD = [
    "Nome_Revenda", "CNPJ", "Endereco", "Cidade",
    "Estado", "Responsavel", "Regioes_Atuacao",
]

def ler_revendas_cadastro() -> list[dict]:
    sb = _sb()
    if not sb:
        return []
    try:
        res = sb.table("genius_revendas").select("*").order("id").execute()
        return res.data or []
    except Exception as e:
        st.error(f"Erro ao ler revendas: {e}")
        return []


def adicionar_revenda_cadastro(reg: dict) -> bool:
    sb = _sb()
    if not sb:
        return False
    try:
        payload = {k: reg.get(k, "") for k in _COLS_REV_CAD}
        sb.table("genius_revendas").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar revenda: {e}")
        return False


def excluir_revenda_cadastro(row_id: int) -> bool:
    sb = _sb()
    if not sb:
        return False
    try:
        sb.table("genius_revendas").delete().eq("id", row_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir revenda: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# ESTOQUE PÁTIO
# ══════════════════════════════════════════════════════════════

_COLS_PATIO = [
    "Codigo", "Modelo", "Tipo", "Ano", "Cor",
    "Numero_Serie", "Data_Entrada", "Status_Patio", "Observacoes",
]

def ler_patio() -> pd.DataFrame:
    sb = _sb()
    if not sb:
        return pd.DataFrame(columns=_COLS_PATIO)
    try:
        res = sb.table("genius_estoque_patio").select("*").order("id").execute()
        return _to_df(res.data or [], _COLS_PATIO)
    except Exception as e:
        st.error(f"Erro ao ler estoque pátio: {e}")
        return pd.DataFrame(columns=_COLS_PATIO)


def adicionar_patio(reg: dict) -> bool:
    sb = _sb()
    if not sb:
        return False
    try:
        payload = {k: str(reg.get(k, "")) for k in _COLS_PATIO}
        sb.table("genius_estoque_patio").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar pátio: {e}")
        return False


def excluir_patio(row_id: int) -> bool:
    sb = _sb()
    if not sb:
        return False
    try:
        sb.table("genius_estoque_patio").delete().eq("id", row_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir pátio: {e}")
        return False


def exportar_patio() -> bytes:
    buf = io.BytesIO()
    ler_patio().to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════
# ESTOQUE REVENDAS
# ══════════════════════════════════════════════════════════════

_COLS_EST_REV = [
    "Codigo", "Modelo", "Revenda", "Contato", "Cidade", "Estado",
    "Data_Envio", "Data_Retorno_Prevista", "Status_Revenda", "Observacoes",
]

def ler_revendas_estoque() -> pd.DataFrame:
    sb = _sb()
    if not sb:
        return pd.DataFrame(columns=_COLS_EST_REV)
    try:
        res = sb.table("genius_estoque_revendas").select("*").order("id").execute()
        return _to_df(res.data or [], _COLS_EST_REV)
    except Exception as e:
        st.error(f"Erro ao ler estoque revendas: {e}")
        return pd.DataFrame(columns=_COLS_EST_REV)


def adicionar_revenda_estoque(reg: dict) -> bool:
    sb = _sb()
    if not sb:
        return False
    try:
        payload = {k: str(reg.get(k, "")) for k in _COLS_EST_REV}
        sb.table("genius_estoque_revendas").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar revenda no estoque: {e}")
        return False


def excluir_revenda_estoque(row_id: int) -> bool:
    sb = _sb()
    if not sb:
        return False
    try:
        sb.table("genius_estoque_revendas").delete().eq("id", row_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir revenda do estoque: {e}")
        return False


def exportar_revendas_estoque() -> bytes:
    buf = io.BytesIO()
    ler_revendas_estoque().to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════
# CACHE DA PLANILHA DE PEÇAS (Senior ERP)
# ══════════════════════════════════════════════════════════════

def salvar_cache_pecas(df: pd.DataFrame, nome_arquivo: str) -> bool:
    """Serializa o DataFrame em JSON e salva no Supabase."""
    sb = _sb()
    if not sb:
        return False
    try:
        payload = {
            "chave": "pecas_senior",
            "nome_arquivo": nome_arquivo,
            "dados_json": df.to_json(orient="records", date_format="iso", force_ascii=False),
            "atualizado_em": _agora(),
        }
        # Upsert baseado na chave
        sb.table("genius_pecas_cache").upsert(payload, on_conflict="chave").execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar cache de peças: {e}")
        return False


def ler_cache_pecas() -> tuple[pd.DataFrame | None, str]:
    """Retorna (DataFrame, nome_arquivo) ou (None, '') se não há cache."""
    sb = _sb()
    if not sb:
        return None, ""
    try:
        res = sb.table("genius_pecas_cache").select("*").eq("chave", "pecas_senior").execute()
        if not res.data:
            return None, ""
        row = res.data[0]
        df = pd.read_json(io.StringIO(row["dados_json"]), orient="records")
        if "Data_Venda" in df.columns:
            df["Data_Venda"] = pd.to_datetime(df["Data_Venda"], errors="coerce")
        return df, row.get("nome_arquivo", "planilha")
    except Exception as e:
        st.error(f"Erro ao ler cache de peças: {e}")
        return None, ""


# ══════════════════════════════════════════════════════════════
# GERENCIAMENTO DE USUÁRIOS E SENHAS
# ══════════════════════════════════════════════════════════════

def _hash(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()


def _verificar(senha_digitada: str, hash_salvo: str) -> bool:
    return hmac.compare_digest(_hash(senha_digitada), hash_salvo)


def ler_usuarios() -> dict:
    """
    Retorna dict de usuários. Prioridade:
      1. Tabela genius_usuarios no Supabase (permite alteração em runtime)
      2. st.secrets["usuarios"] (fallback somente-leitura)
    """
    sb = _sb()
    if sb:
        try:
            res = sb.table("genius_usuarios").select("*").execute()
            if res.data:
                return {
                    row["login"]: {
                        "nome":       row["nome"],
                        "perfil":     row["perfil"],
                        "senha_hash": row["senha_hash"],
                        "is_admin":   row.get("is_admin", False),
                    }
                    for row in res.data
                }
        except Exception:
            pass
    # Fallback: secrets
    try:
        return {k: dict(v) for k, v in st.secrets["usuarios"].items()}
    except Exception:
        return {}


def alterar_senha(login: str, senha_nova: str) -> bool:
    """Altera a senha de um usuário na tabela genius_usuarios."""
    sb = _sb()
    if not sb:
        st.error("Supabase não configurado — não é possível alterar senha.")
        return False
    try:
        novo_hash = _hash(senha_nova)
        res = sb.table("genius_usuarios").select("id").eq("login", login).execute()
        if res.data:
            sb.table("genius_usuarios").update({"senha_hash": novo_hash}).eq("login", login).execute()
        else:
            # Cria o usuário se não existir na tabela ainda
            # (usuários podem vir apenas de secrets na primeira vez)
            usuarios_secrets = {}
            try:
                usuarios_secrets = {k: dict(v) for k, v in st.secrets["usuarios"].items()}
            except Exception:
                pass
            dados = usuarios_secrets.get(login, {})
            sb.table("genius_usuarios").insert({
                "login":      login,
                "nome":       dados.get("nome", login),
                "perfil":     dados.get("perfil", "comercial"),
                "senha_hash": novo_hash,
                "is_admin":   login == "lucas",
            }).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao alterar senha: {e}")
        return False


def criar_usuario(login: str, nome: str, perfil: str, senha: str, is_admin: bool = False) -> bool:
    """Cria um novo usuário na tabela genius_usuarios."""
    sb = _sb()
    if not sb:
        return False
    try:
        sb.table("genius_usuarios").insert({
            "login":      login.strip().lower(),
            "nome":       nome.strip(),
            "perfil":     perfil,
            "senha_hash": _hash(senha),
            "is_admin":   is_admin,
        }).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao criar usuário: {e}")
        return False


def excluir_usuario(login: str) -> bool:
    sb = _sb()
    if not sb:
        return False
    try:
        sb.table("genius_usuarios").delete().eq("login", login).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir usuário: {e}")
        return False
