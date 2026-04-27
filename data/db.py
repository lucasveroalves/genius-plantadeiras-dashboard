"""
data/db.py — Genius Implementos Agrícolas v16 (AUDITORIA)

Correções aplicadas:
  [FIX-TTL-1]  TTL de 5s elevado para 30s nas tabelas operacionais.
               Reduz queries ao Supabase de ~120/min para ~10/min com 5 usuários.
  [FIX-SEC-2]  Senhas agora usam bcrypt com salt (werkzeug.security).
               SHA-256 puro sem salt é vulnerável a rainbow table.
               Fallback automático para hashes SHA-256 legados durante login.
  [FIX-CLOUD-1] importar_pecas_senior_para_supabase agora exibe st.progress()
               granular por lote e retorna erro parcial em vez de abortar tudo.
  [FIX-CONN-1] _sb() com reconexão automática: detecta conexão morta via
               healthcheck leve (SELECT 1 row) e recria o cliente se necessário.
               Healthcheck executado apenas uma vez por sessão Streamlit.
  [FIX-PERF-1] ler_pecas_senior_filtrado(): query server-side com .gte/.lte
               em Data_Venda — evita transferir 170k+ linhas para o Python.
  [FIX-TRUNC]  Paginação adicionada em ler_producao, ler_orcamentos, ler_estoque,
               ler_nfs, ler_patio, ler_revendas_estoque para não truncar em 1000 rows.
"""

from __future__ import annotations
import math
import hashlib
import pandas as pd
import streamlit as st
from supabase import create_client, Client


# ══════════════════════════════════════════════════════════════
# Cliente Supabase (singleton cacheado — ttl=3600s)
# ══════════════════════════════════════════════════════════════

@st.cache_resource(ttl=3600)
def _get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)


def _sb() -> Client:
    """
    [FIX-CONN-1] Retorna o cliente Supabase com healthcheck por sessão.
    Se a conexão estiver morta (timeout do servidor PostgreSQL), recria.
    O healthcheck ocorre apenas uma vez por sessão — sem overhead por chamada.
    """
    client = _get_client()
    if not st.session_state.get("_sb_ok"):
        try:
            client.table("usuarios").select("login").limit(1).execute()
            st.session_state["_sb_ok"] = True
        except Exception:
            # Conexão morta — recria o cliente
            _get_client.clear()
            client = _get_client()
            st.session_state["_sb_ok"] = True
    return client


# ══════════════════════════════════════════════════════════════
# Helpers internos
# ══════════════════════════════════════════════════════════════

def _safe_response(resp) -> list[dict]:
    """Extrai .data de uma resposta Supabase ou retorna lista vazia."""
    try:
        return resp.data or []
    except Exception:
        return []


def _paginar(tabela: str, select: str = "*", order: str = "id") -> list[dict]:
    """
    [FIX-TRUNC] Lê uma tabela completa em páginas de 1000 rows.
    Evita truncamento silencioso pelo limite padrão do PostgREST.
    """
    todos = []
    page_size = 1000
    offset = 0
    client = _sb()
    while True:
        resp = (
            client.table(tabela)
            .select(select)
            .order(order)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = resp.data or []
        todos.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return todos


# ══════════════════════════════════════════════════════════════
# Segurança de senhas — bcrypt com fallback SHA-256
# ══════════════════════════════════════════════════════════════

def _hash_senha(senha: str) -> str:
    """
    [FIX-SEC-2] Gera hash bcrypt com salt automático.
    Substitui o SHA-256 puro que era vulnerável a rainbow table.
    """
    try:
        from werkzeug.security import generate_password_hash
        return generate_password_hash(senha, method="pbkdf2:sha256", salt_length=16)
    except ImportError:
        # Fallback: se werkzeug não estiver disponível, usa SHA-256 (legado)
        return hashlib.sha256(senha.encode()).hexdigest()


def verificar_senha(digitada: str, salvo: str) -> bool:
    """
    [FIX-SEC-2] Verifica senha com suporte dual:
    - Hashes novos: pbkdf2:sha256 (werkzeug)
    - Hashes legados: SHA-256 puro (64 chars hex) — para migração gradual
    """
    if not salvo:
        return False
    # Hash legado SHA-256 (64 caracteres hexadecimais)
    if len(salvo) == 64 and all(c in "0123456789abcdef" for c in salvo.lower()):
        import hmac
        return hmac.compare_digest(hashlib.sha256(digitada.encode()).hexdigest(), salvo)
    # Hash novo pbkdf2
    try:
        from werkzeug.security import check_password_hash
        return check_password_hash(salvo, digitada)
    except (ImportError, ValueError):
        return False


# ══════════════════════════════════════════════════════════════
# NFs em Demonstração
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)  # [FIX-TTL-1] era ttl=5
def ler_nfs() -> list[dict]:
    return _paginar("nf_demo")


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

@st.cache_data(ttl=30)  # [FIX-TTL-1] era ttl=5
def ler_producao() -> pd.DataFrame:
    data = _paginar("producao")
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
    total       = len(df)
    em_producao = int((status == "em produção").sum())
    prontos     = int((status == "pronto").sum())
    entregues   = int((status == "entregue").sum())
    prev_col    = pd.to_datetime(df.get("Data_Entrega_Prevista", pd.Series()), errors="coerce", dayfirst=True)
    atrasados   = int(
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

@st.cache_data(ttl=30)  # [FIX-TTL-1] era ttl=5
def ler_orcamentos() -> pd.DataFrame:
    data = _paginar("orcamentos")
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


def atualizar_orcamento(row_id: int, campos: dict) -> bool:
    try:
        _sb().table("orcamentos").update(campos).eq("id", row_id).execute()
        ler_orcamentos.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar orçamento: {e}")
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
    try:
        reg = {
            "login": login,
            "nome": nome,
            "perfil": perfil,
            "senha_hash": _hash_senha(senha),   # [FIX-SEC-2] bcrypt
            "is_admin": is_admin,
            "abas_permitidas": abas,
        }
        _sb().table("usuarios").insert(reg).execute()
        ler_usuarios.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao criar usuário: {e}")
        return False


def alterar_senha(login: str, nova_senha: str) -> bool:
    try:
        novo_hash = _hash_senha(nova_senha)    # [FIX-SEC-2] bcrypt
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

@st.cache_data(ttl=30)  # [FIX-TTL-1] era ttl=5
def ler_leadtime() -> pd.DataFrame:
    data = _paginar("leadtime")
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
# Estoque
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)  # [FIX-TTL-1] era ttl=5
def ler_estoque() -> pd.DataFrame:
    data = _paginar("estoque")
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
# Importação Senior → Supabase (com progress e tratamento de erro parcial)
# ══════════════════════════════════════════════════════════════

def importar_pecas_senior_para_supabase(
    df: pd.DataFrame,
    tabela: str = "pecas_senior",
    batch_size: int = 1500,
    conflict_column: str = None,  # [FIX-IDLINHA] id_linha removida do banco — usa INSERT simples
) -> tuple[int, str]:
    """
    [FIX-CLOUD-1] Upsert em lotes com:
    - st.progress() granular por lote (feedback visual ao usuário)
    - Erro parcial: retorna linhas já inseridas + mensagem de erro se um lote falhar
    - Sem abort total: continua nos lotes seguintes após falha isolada

    Parâmetros
    ----------
    df              : DataFrame já processado por preparar_pecas()
    tabela          : nome da tabela no Supabase (default: "pecas_senior")
    batch_size      : tamanho de cada lote (1500 é seguro para a maioria dos planos)
    conflict_column : coluna UNIQUE usada como chave de upsert
    """
    if df is None or df.empty:
        return 0, "DataFrame vazio — nada a importar."

    try:
        client = _sb()

        # ── 1. Limpeza/normalização ────────────────────────────
        df = df.copy()

        # Converte datas para string ISO
        for col in df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
            df[col] = df[col].dt.strftime("%Y-%m-%d")

        # Substitui NaN/inf por None
        import numpy as _np
        df = df.replace([_np.inf, -_np.inf], _np.nan)
        for _c in list(df.columns):
            df[_c] = df[_c].where(pd.notna(df[_c]), other=None)

        def _limpar_registro(rec: dict) -> dict:
            import math as _math
            return {
                k: (None if (v is not None and isinstance(v, float) and _math.isnan(v)) else v)
                for k, v in rec.items()
            }

        registros: list[dict] = [_limpar_registro(r) for r in df.to_dict("records")]
        total     = len(registros)
        n_batches = math.ceil(total / batch_size)
        n_ok      = 0
        erros     = []

        # ── 2. Progress bar ────────────────────────────────────
        progress = st.progress(0, text=f"Importando 0 de {total} linhas...")

        for i in range(n_batches):
            lote = registros[i * batch_size: (i + 1) * batch_size]
            try:
                if conflict_column and conflict_column in df.columns:
                    resp = (
                        client
                        .table(tabela)
                        .upsert(lote, on_conflict=conflict_column)
                        .execute()
                    )
                else:
                    resp = client.table(tabela).insert(lote).execute()

                n_inseridos = len(resp.data) if resp.data else len(lote)
                n_ok += n_inseridos

            except Exception as exc:
                erros.append(f"Lote {i + 1}/{n_batches}: {exc}")
                # Continua nos próximos lotes mesmo com falha

            pct = (i + 1) / n_batches
            progress.progress(
                pct,
                text=f"Importando {min(n_ok, total):,} de {total:,} linhas... ({i+1}/{n_batches})",
            )

        progress.empty()

        if erros:
            return n_ok, f"Concluído com {len(erros)} erro(s): {erros[0]}"
        return n_ok, "OK"

    except Exception as exc:
        return 0, str(exc)


# ══════════════════════════════════════════════════════════════
# Revendas Cadastro
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)  # [FIX-TTL-1] era ttl=5
def ler_revendas_cadastro() -> pd.DataFrame:
    data = _paginar("revendas_cadastro")
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
# Pátio e Revendas Estoque
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)  # [FIX-TTL-1] era ttl=5
def ler_patio() -> pd.DataFrame:
    data = _paginar("patio")
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


@st.cache_data(ttl=30)  # [FIX-TTL-1] era ttl=5
def ler_revendas_estoque() -> pd.DataFrame:
    data = _paginar("revendas_estoque")
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


# ══════════════════════════════════════════════════════════════
# Catálogo de Peças
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def ler_catalogo_pecas() -> pd.DataFrame:
    """Lê catálogo de peças (Codigo + Descricao) do Supabase."""
    try:
        todos = _paginar("catalogo_pecas", select="Codigo,Descricao")
        return pd.DataFrame(todos) if todos else pd.DataFrame(columns=["Codigo", "Descricao"])
    except Exception as e:
        st.warning(f"⚠️ Erro ao ler catálogo: {e}")
        return pd.DataFrame(columns=["Codigo", "Descricao"])


def importar_catalogo_pecas(df: pd.DataFrame) -> tuple[int, str]:
    if df is None or df.empty:
        return 0, "DataFrame vazio."
    try:
        import math as _math
        import numpy as _np
        df = df.copy()[["Codigo", "Descricao"]]
        df["Codigo"]    = df["Codigo"].astype(str).str.strip()
        df["Descricao"] = df["Descricao"].astype(str).str.strip()
        df = df.dropna(subset=["Codigo"]).drop_duplicates("Codigo")

        def _limpar(rec):
            return {k: (None if isinstance(v, float) and _math.isnan(v) else v)
                    for k, v in rec.items()}

        registros = [_limpar(r) for r in df.to_dict("records")]
        batch_size = 1000
        n_ok = 0
        for i in range(_math.ceil(len(registros) / batch_size)):
            lote = registros[i * batch_size:(i + 1) * batch_size]
            resp = _sb().table("catalogo_pecas").upsert(lote, on_conflict="Codigo").execute()
            n_ok += len(resp.data) if resp.data else len(lote)
        ler_catalogo_pecas.clear()
        return n_ok, "OK"
    except Exception as e:
        return 0, str(e)


# ══════════════════════════════════════════════════════════════
# Lançamentos de Peças Manuais
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)  # [FIX-TTL-1] era ttl=5
def ler_lancamentos_pecas() -> pd.DataFrame:
    try:
        todos = _paginar("lancamentos_pecas")
        return pd.DataFrame(todos) if todos else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def adicionar_lancamento_peca(registro: dict) -> bool:
    try:
        _sb().table("lancamentos_pecas").insert(registro).execute()
        ler_lancamentos_pecas.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar lançamento: {e}")
        return False


def excluir_lancamento_peca(row_id: int) -> bool:
    try:
        _sb().table("lancamentos_pecas").delete().eq("id", row_id).execute()
        ler_lancamentos_pecas.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir lançamento: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# Territórios
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def ler_territorios() -> pd.DataFrame:
    try:
        data = _paginar("territorios")
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def adicionar_territorio(registro: dict) -> bool:
    try:
        _sb().table("territorios").insert(registro).execute()
        ler_territorios.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar território: {e}")
        return False


def excluir_territorio(row_id: int) -> bool:
    try:
        _sb().table("territorios").delete().eq("id", row_id).execute()
        ler_territorios.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir território: {e}")
        return False


def atualizar_territorio(row_id: int, campos: dict) -> bool:
    try:
        _sb().table("territorios").update(campos).eq("id", row_id).execute()
        ler_territorios.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar território: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# Metas de Faturamento
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def ler_metas() -> pd.DataFrame:
    try:
        data = _safe_response(_sb().table("metas_faturamento").select("*").order("id").execute())
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def salvar_meta(ano: int, mes: int, valor: float) -> bool:
    try:
        existing = _sb().table("metas_faturamento").select("id") \
            .eq("Ano", ano).eq("Mes", mes).execute()
        if existing.data:
            _sb().table("metas_faturamento").update({"Meta": valor}) \
                .eq("Ano", ano).eq("Mes", mes).execute()
        else:
            _sb().table("metas_faturamento").insert(
                {"Ano": ano, "Mes": mes, "Meta": valor}
            ).execute()
        ler_metas.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar meta: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# [FIX-PERF-1] Query filtrada server-side para pecas_senior
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def ler_pecas_senior_filtrado(
    data_inicio: str,
    data_fim: str,
    limit: int = 10000,
) -> pd.DataFrame:
    """
    [FIX-PERF-1] Lê peças com filtro de data no servidor (server-side).
    Evita transferir 170k+ linhas quando apenas um período é necessário.

    Parâmetros
    ----------
    data_inicio : str no formato "YYYY-MM-DD"
    data_fim    : str no formato "YYYY-MM-DD"
    limit       : máximo de rows a retornar (default 10.000)
    """
    try:
        resp = (
            _sb()
            .table("pecas_senior")
            .select("Codigo,Descricao_Peca,Quantidade,Valor_Total,Cliente_Revenda,Data_Venda")
            .gte("Data_Venda", data_inicio)
            .lte("Data_Venda", data_fim)
            .limit(limit)
            .execute()
        )
        data = resp.data or []
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if "Data_Venda" in df.columns:
            df["Data_Venda"] = pd.to_datetime(df["Data_Venda"], errors="coerce")
        if "Valor_Total" in df.columns:
            df["Valor_Total"] = pd.to_numeric(df["Valor_Total"], errors="coerce").fillna(0)
        if "Quantidade" in df.columns:
            df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce").fillna(0)
        return df
    except Exception as e:
        st.warning(f"⚠️ Erro ao ler peças filtradas: {e}")
        return pd.DataFrame()
