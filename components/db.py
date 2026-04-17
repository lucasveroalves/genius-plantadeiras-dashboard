"""
data/db.py — Genius Implementos Agrícolas v14 (CORRIGIDO)

Correções aplicadas:
  [FIX-SEC-1] Removido hardcode "lucas" como admin — is_admin vem exclusivamente do banco
  [FIX-SEC-2] alterar_senha() não cria mais usuários fantasma; retorna False se login inexistente
  [FIX-SEC-3] Cache de peças usa chave por usuário (evita vazamento entre usuários)
  [FIX-SEC-4] SMTP usa ssl.create_default_context() para validar certificado TLS
  [FIX-SEC-5] Fallback de secrets para ler_usuarios() garante que senha_hash esteja presente
  [FIX-PERF-1] @st.cache_resource com ttl=3600 para recriar cliente Supabase se expirar
  [FIX-PERF-2] ler_orcamentos() e ler_producao() com @st.cache_data(ttl=30)
  [FIX-PERF-3] importar_producao() usa batch insert e limita a 500 linhas por chamada
  [FIX-ROBUST-1] _exec_safe() agora envolve TODAS as operações de escrita em patio/revendas
"""

from __future__ import annotations
import io, json, hashlib, hmac, ssl
from datetime import datetime
import pandas as pd
import streamlit as st


# ── Cliente Supabase ──────────────────────────────────────────
# ttl=3600 garante recriação periódica — evita conexão expirada silenciosa
@st.cache_resource(show_spinner=False, ttl=3600)
def _get_client():
    try:
        from supabase import create_client
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception:
        return None

def _sb():
    return _get_client()

def _exec_safe(operation, write: bool = False):
    """
    Executa uma operação Supabase (.execute()) com tratamento de erros de rede.
    - write=True: mostra st.error() com mensagem amigável (ação do usuário)
    - write=False: falha silenciosa (leitura automática)
    Retorna o resultado ou None em caso de erro.
    """
    try:
        return operation.execute()
    except Exception as e:
        err = str(e)
        if write:
            if "Errno -2" in err or "Name or service" in err or "network" in err.lower():
                st.error("❌ Sem conexão com o banco de dados. Verifique a configuração do Supabase nos secrets do app.")
            else:
                st.error(f"❌ Erro ao salvar: {e}")
        return None

def _agora() -> str:
    return datetime.utcnow().isoformat()

def _to_df(rows: list[dict], cols: list[str]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    extras = [c for c in ["id","created_at"] if c in df.columns and c not in cols]
    if extras:
        df = df.drop(columns=extras)
    return df[cols].reset_index(drop=True)


# ══════════════════════════════════════════════════════════════
# USUÁRIOS
# ══════════════════════════════════════════════════════════════

def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

def ler_usuarios() -> dict:
    sb = _sb()
    if sb:
        try:
            res = sb.table("genius_usuarios").select("*").execute()
            if res.data:
                out = {}
                for r in res.data:
                    abas = r.get("abas_permitidas")
                    if isinstance(abas, str):
                        try: abas = json.loads(abas)
                        except Exception: abas = None
                    out[r["login"]] = {
                        "nome":            r["nome"],
                        "perfil":          r["perfil"],
                        "senha_hash":      r["senha_hash"],
                        # [FIX-SEC-1] is_admin vem apenas do banco, sem hardcode
                        "is_admin":        bool(r.get("is_admin", False)),
                        "abas_permitidas": abas,
                    }
                return out
        except Exception:
            pass

    # Fallback para secrets (modo offline / desenvolvimento)
    try:
        out = {}
        for k, v in st.secrets["usuarios"].items():
            d = dict(v)
            # [FIX-SEC-5] Só inclui usuário se senha_hash estiver presente e não vazia
            if not d.get("senha_hash", "").strip():
                continue
            out[k] = d
        return out
    except Exception:
        return {}

def alterar_senha(login: str, nova: str) -> bool:
    """
    [FIX-SEC-2] Altera senha APENAS se o usuário já existir no Supabase.
    Não cria registros — isso previne usuários fantasma sem permissões corretas.
    """
    sb = _sb()
    if not sb:
        return False
    try:
        h = _hash(nova)
        res = sb.table("genius_usuarios").select("id").eq("login", login).execute()
        if not res.data:
            st.error("❌ Usuário não encontrado no banco. Solicite ao administrador que crie o usuário primeiro.")
            return False
        sb.table("genius_usuarios").update({"senha_hash": h}).eq("login", login).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao alterar senha: {e}")
        return False

def criar_usuario(login: str, nome: str, perfil: str, senha: str,
                  is_admin: bool = False, abas: list | None = None) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        res = _exec_safe(sb.table("genius_usuarios").insert({
            "login": login.strip().lower(), "nome": nome.strip(),
            "perfil": perfil, "senha_hash": _hash(senha),
            "is_admin": is_admin,
            "abas_permitidas": json.dumps(abas) if abas else None,
        }), write=True)
        return res is not None
    except Exception as e:
        st.error(f"❌ Erro ao criar usuário: {e}"); return False

def atualizar_usuario(login: str, dados: dict) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        payload = {}
        if "perfil"          in dados: payload["perfil"]    = dados["perfil"]
        if "is_admin"        in dados: payload["is_admin"]  = dados["is_admin"]
        if "abas_permitidas" in dados:
            v = dados["abas_permitidas"]
            payload["abas_permitidas"] = json.dumps(v) if isinstance(v, list) else v
        sb.table("genius_usuarios").update(payload).eq("login", login).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar usuário: {e}"); return False

def excluir_usuario(login: str) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_usuarios").delete().eq("login", login).execute()
        return True
    except Exception as e:
        st.warning(f"⚠️ Erro ao excluir: {e}"); return False


# ══════════════════════════════════════════════════════════════
# PRODUÇÃO
# ══════════════════════════════════════════════════════════════

_COLS_PROD = [
    "Equipamento","Cliente","Representante","Data_Pedido",
    "Data_Inicio_Producao","Data_Entrega_Prevista","Data_Entrega_Real",
    "Status_Producao","Observacoes",
]

# [FIX-PERF-2] Cache com TTL de 30s — evita chamada ao Supabase a cada render
@st.cache_data(show_spinner=False, ttl=30)
def ler_producao() -> pd.DataFrame:
    sb = _sb()
    if not sb: return pd.DataFrame(columns=_COLS_PROD)
    try:
        res = sb.table("genius_producao").select("*").order("id").execute()
        rows = res.data or []
        if not rows: return pd.DataFrame(columns=_COLS_PROD)
        df = pd.DataFrame(rows)
        for c in _COLS_PROD:
            if c not in df.columns: df[c] = ""
        return df[["id"] + _COLS_PROD].reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=_COLS_PROD)

def adicionar_producao(reg: dict) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        payload = {k: str(v) if v is not None else "" for k, v in reg.items() if k in _COLS_PROD}
        res = _exec_safe(sb.table("genius_producao").insert(payload), write=True)
        if res is not None:
            # Invalida o cache para que próxima leitura busque dados atualizados
            ler_producao.clear()
            return True
        return False
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {e}"); return False

def atualizar_producao_campo(row_id: int, campo: str, valor: str) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_producao").update({campo: str(valor)}).eq("id", row_id).execute()
        ler_producao.clear()
        return True
    except Exception as e:
        st.warning(f"⚠️ Erro ao atualizar: {e}"); return False

def excluir_producao(row_id: int) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_producao").delete().eq("id", row_id).execute()
        ler_producao.clear()
        return True
    except Exception as e:
        st.warning(f"⚠️ Erro ao excluir: {e}"); return False

def importar_producao(uploaded) -> tuple[int, str]:
    """
    [FIX-PERF-3] Usa batch insert (único POST) em vez de INSERT por linha.
    Limita a 500 linhas por importação para evitar DoS / rate limit.
    """
    LIMITE_LINHAS = 500
    try:
        uploaded.seek(0)
        df = pd.read_csv(uploaded, encoding="utf-8-sig") if uploaded.name.lower().endswith(".csv") \
             else pd.read_excel(uploaded, engine="openpyxl")
    except Exception:
        return 0, "Erro ao ler arquivo."

    if len(df) > LIMITE_LINHAS:
        return 0, f"Arquivo excede o limite de {LIMITE_LINHAS} linhas por importação."

    sb = _sb()
    if not sb:
        return 0, "Sem conexão com o banco de dados."

    # Prepara lista de dicts para batch insert
    rows = []
    for _, row in df.iterrows():
        rows.append({c: str(row.get(c, "")) for c in _COLS_PROD})

    try:
        res = _exec_safe(sb.table("genius_producao").insert(rows), write=True)
        if res is not None:
            ler_producao.clear()
            return len(rows), "OK"
        return 0, "Erro ao inserir no banco."
    except Exception as e:
        return 0, f"Erro: {e}"

def exportar_producao() -> bytes:
    buf = io.BytesIO()
    ler_producao().drop(columns=["id"], errors="ignore").to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()

def calcular_kpis_producao(df: pd.DataFrame) -> dict:
    from data.loader_estoque import calcular_kpis_producao as _k
    return _k(df)


# ══════════════════════════════════════════════════════════════
# ORÇAMENTOS DE PEÇAS
# ══════════════════════════════════════════════════════════════

_COLS_ORC = [
    "Nr_Pedido","Data_Orcamento","Cliente_Revenda",
    "Descricao_Peca","Quantidade","Valor_Unit","Valor_Total",
    "Status_Orc","Observacoes",
]

# [FIX-PERF-2] Cache com TTL de 30s
@st.cache_data(show_spinner=False, ttl=30)
def ler_orcamentos() -> pd.DataFrame:
    sb = _sb()
    if not sb: return pd.DataFrame(columns=_COLS_ORC)
    try:
        res = sb.table("genius_orcamentos").select("*").order("id").execute()
        rows = res.data or []
        if not rows: return pd.DataFrame(columns=_COLS_ORC)
        df = pd.DataFrame(rows)
        for c in _COLS_ORC:
            if c not in df.columns: df[c] = ""
        return df[["id"] + _COLS_ORC].reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=_COLS_ORC)

def adicionar_orcamento(reg: dict) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        if not reg.get("Valor_Total"):
            try: reg["Valor_Total"] = float(reg.get("Quantidade",0)) * float(reg.get("Valor_Unit",0))
            except Exception: reg["Valor_Total"] = 0.0
        payload = {k: str(v) if v is not None else "" for k, v in reg.items() if k in _COLS_ORC}
        res = _exec_safe(sb.table("genius_orcamentos").insert(payload), write=True)
        if res is not None:
            ler_orcamentos.clear()
            return True
        return False
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {e}"); return False

def atualizar_orcamento(row_id: int, dados: dict) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        payload = {k: str(v) for k, v in dados.items() if k in _COLS_ORC}
        sb.table("genius_orcamentos").update(payload).eq("id", row_id).execute()
        ler_orcamentos.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar orçamento: {e}"); return False

def excluir_orcamento(row_id: int) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_orcamentos").delete().eq("id", row_id).execute()
        ler_orcamentos.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir orçamento: {e}"); return False


# ══════════════════════════════════════════════════════════════
# NF EM DEMONSTRAÇÃO
# ══════════════════════════════════════════════════════════════

_COLS_NF = ["Data_Emissao","Nr_NF","Cliente","Maquina","Observacoes"]

def ler_nfs() -> list[dict]:
    sb = _sb()
    if not sb: return []
    try:
        res = sb.table("genius_nf_demo").select("*").order("id").execute()
        return res.data or []
    except Exception:
        return []

def adicionar_nf(reg: dict) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        res = _exec_safe(sb.table("genius_nf_demo").insert({k: reg.get(k,"") for k in _COLS_NF}), write=True)
        return res is not None
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {e}"); return False

def excluir_nf(row_id: int) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_nf_demo").delete().eq("id", row_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir NF: {e}"); return False


# ══════════════════════════════════════════════════════════════
# REVENDAS CADASTRO
# ══════════════════════════════════════════════════════════════

_COLS_REV = ["Nome_Revenda","CNPJ","Cidade","Estado","Responsavel","Regioes_Atuacao"]

def ler_revendas_cadastro() -> list[dict]:
    sb = _sb()
    if not sb: return []
    try:
        res = sb.table("genius_revendas").select("*").order("id").execute()
        return res.data or []
    except Exception:
        return []

def adicionar_revenda_cadastro(reg: dict) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        res = _exec_safe(sb.table("genius_revendas").insert({k: reg.get(k,"") for k in _COLS_REV}), write=True)
        return res is not None
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {e}"); return False

def excluir_revenda_cadastro(row_id: int) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        res = _exec_safe(sb.table("genius_revendas").delete().eq("id", row_id), write=True)
        return res is not None
    except Exception as e:
        st.error(f"Erro ao excluir revenda: {e}"); return False


# ══════════════════════════════════════════════════════════════
# ESTOQUE PÁTIO / REVENDAS
# [FIX-ROBUST-1] Todas operações de escrita agora usam _exec_safe()
# ══════════════════════════════════════════════════════════════

_COLS_PATIO    = ["Codigo","Modelo","Tipo","Ano","Cor","Numero_Serie","Data_Entrada","Status_Patio","Observacoes"]
_COLS_EST_REV  = ["Codigo","Modelo","Revenda","Contato","Cidade","Estado","Data_Envio","Data_Retorno_Prevista","Status_Revenda","Observacoes"]

def ler_patio() -> pd.DataFrame:
    sb = _sb()
    if not sb: return pd.DataFrame(columns=_COLS_PATIO)
    try:
        res = sb.table("genius_estoque_patio").select("*").order("id").execute()
        return _to_df(res.data or [], _COLS_PATIO)
    except Exception:
        return pd.DataFrame(columns=_COLS_PATIO)

def adicionar_patio(reg: dict) -> bool:
    sb = _sb()
    if not sb: return False
    res = _exec_safe(
        sb.table("genius_estoque_patio").insert({k: str(reg.get(k,"")) for k in _COLS_PATIO}),
        write=True
    )
    return res is not None

def excluir_patio(row_id: int) -> bool:
    sb = _sb()
    if not sb: return False
    res = _exec_safe(
        sb.table("genius_estoque_patio").delete().eq("id", row_id),
        write=True
    )
    return res is not None

def exportar_patio() -> bytes:
    buf = io.BytesIO()
    ler_patio().to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()

def ler_revendas_estoque() -> pd.DataFrame:
    sb = _sb()
    if not sb: return pd.DataFrame(columns=_COLS_EST_REV)
    try:
        res = sb.table("genius_estoque_revendas").select("*").order("id").execute()
        return _to_df(res.data or [], _COLS_EST_REV)
    except Exception:
        return pd.DataFrame(columns=_COLS_EST_REV)

def adicionar_revenda_estoque(reg: dict) -> bool:
    sb = _sb()
    if not sb: return False
    res = _exec_safe(
        sb.table("genius_estoque_revendas").insert({k: str(reg.get(k,"")) for k in _COLS_EST_REV}),
        write=True
    )
    return res is not None

def excluir_revenda_estoque(row_id: int) -> bool:
    sb = _sb()
    if not sb: return False
    res = _exec_safe(
        sb.table("genius_estoque_revendas").delete().eq("id", row_id),
        write=True
    )
    return res is not None

def exportar_revendas_estoque() -> bytes:
    buf = io.BytesIO()
    ler_revendas_estoque().to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════
# CACHE PLANILHA PEÇAS
# [FIX-SEC-3] Chave de cache inclui login do usuário — evita vazamento entre usuários
# ══════════════════════════════════════════════════════════════

def _cache_key() -> str:
    """Gera chave de cache por usuário logado."""
    usuario = st.session_state.get("usuario_atual", "anonimo")
    return f"pecas_senior_{usuario}"

def salvar_cache_pecas(df: pd.DataFrame, nome: str) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        chave = _cache_key()
        sb.table("genius_pecas_cache").upsert({
            "chave": chave, "nome_arquivo": nome,
            "dados_json": df.to_json(orient="records", date_format="iso", force_ascii=False),
            "atualizado_em": _agora(),
        }, on_conflict="chave").execute()
        return True
    except Exception:
        return False

def ler_cache_pecas() -> tuple[pd.DataFrame | None, str]:
    sb = _sb()
    if not sb: return None, ""
    try:
        chave = _cache_key()
        res = sb.table("genius_pecas_cache").select("*").eq("chave", chave).execute()
        if not res.data: return None, ""
        row = res.data[0]
        df  = pd.read_json(io.StringIO(row["dados_json"]), orient="records")
        if "Data_Venda" in df.columns:
            df["Data_Venda"] = pd.to_datetime(df["Data_Venda"], errors="coerce")
        return df, row.get("nome_arquivo","planilha")
    except Exception:
        return None, ""


# ══════════════════════════════════════════════════════════════
# LEAD TIME
# ══════════════════════════════════════════════════════════════

_COLS_LEAD = [
    "Nr_Orcamento","Cliente_Revenda","Valor_Total",
    "Data_Orcamento_Fechado","Nr_Requisicao","Data_Requisicao",
    "Nr_NF","Data_NF","Status_Lead","Observacoes",
]

@st.cache_data(show_spinner=False, ttl=30)
def ler_leadtime() -> pd.DataFrame:
    sb = _sb()
    if not sb: return pd.DataFrame(columns=_COLS_LEAD)
    try:
        res = sb.table("genius_leadtime_pecas").select("*").order("id").execute()
        rows = res.data or []
        if not rows: return pd.DataFrame(columns=_COLS_LEAD)
        df = pd.DataFrame(rows)
        for c in _COLS_LEAD:
            if c not in df.columns: df[c] = ""
        return df[["id"] + _COLS_LEAD].reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=_COLS_LEAD)

def adicionar_leadtime(reg: dict) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        payload = {k: str(v) if v is not None else "" for k, v in reg.items() if k in _COLS_LEAD}
        res = _exec_safe(sb.table("genius_leadtime_pecas").insert(payload), write=True)
        if res is not None:
            ler_leadtime.clear()
            return True
        return False
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {e}"); return False

def atualizar_leadtime(row_id: int, dados: dict) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        payload = {k: str(v) for k, v in dados.items() if k in _COLS_LEAD}
        sb.table("genius_leadtime_pecas").update(payload).eq("id", row_id).execute()
        ler_leadtime.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}"); return False

def excluir_leadtime(row_id: int) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_leadtime_pecas").delete().eq("id", row_id).execute()
        ler_leadtime.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir: {e}"); return False

def calcular_kpis_leadtime(df: pd.DataFrame) -> dict:
    zeros = {"total": 0, "orc_fechado": 0, "req_enviada": 0,
             "nf_emitida": 0, "lead_medio_req": 0.0, "lead_medio_nf": 0.0}
    if df is None or df.empty:
        return zeros
    try:
        total       = len(df)
        orc_fechado = int((df["Status_Lead"] == "Orçamento Fechado").sum())
        req_enviada = int((df["Status_Lead"] == "Req. Enviada").sum())
        nf_emitida  = int((df["Status_Lead"] == "NF Emitida").sum())

        def _lead(col_ini, col_fim):
            try:
                d1 = pd.to_datetime(df[col_ini], errors="coerce", dayfirst=True)
                d2 = pd.to_datetime(df[col_fim],  errors="coerce", dayfirst=True)
                dias = (d2 - d1).dt.days.dropna()
                dias = dias[dias >= 0]
                return round(float(dias.mean()), 1) if not dias.empty else 0.0
            except Exception:
                return 0.0

        return {
            "total":           total,
            "orc_fechado":     orc_fechado,
            "req_enviada":     req_enviada,
            "nf_emitida":      nf_emitida,
            "lead_medio_req":  _lead("Data_Orcamento_Fechado", "Data_Requisicao"),
            "lead_medio_nf":   _lead("Data_Orcamento_Fechado", "Data_NF"),
        }
    except Exception:
        return zeros


# ══════════════════════════════════════════════════════════════
# E-MAIL — notificações de NF
# [FIX-SEC-4] SMTP com validação explícita de certificado TLS
# ══════════════════════════════════════════════════════════════

def enviar_email_nf(para: str, assunto: str, corpo: str) -> bool:
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        cfg  = st.secrets.get("email", {})
        host = cfg.get("smtp_host", "smtp.gmail.com")
        port = int(cfg.get("smtp_port", 587))
        user = cfg.get("smtp_user", "")
        pwd  = cfg.get("smtp_pass", "")
        rem  = cfg.get("remetente", user)

        if not user or not pwd:
            st.warning("⚠️ E-mail não configurado nos secrets.")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"]    = rem
        msg["To"]      = para
        msg.attach(MIMEText(corpo, "html", "utf-8"))

        # [FIX-SEC-4] Contexto SSL explícito valida certificado do servidor SMTP
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port) as s:
            s.ehlo()
            s.starttls(context=context)
            s.login(user, pwd)
            s.sendmail(user, [para], msg.as_string())
        return True
    except Exception as e:
        st.error(f"Erro ao enviar e-mail: {e}")
        return False
