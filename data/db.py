"""
data/db.py — Genius Plantadeiras v14
Persistência completa via Supabase.
Novidades v14:
  • genius_usuarios tem coluna abas_permitidas (JSON TEXT)
  • atualizar_usuario() para edição de perfil/abas/admin
  • enviar_email_nf() para alertas de NF via SMTP (configurado nos secrets)
"""

from __future__ import annotations
import io, json, hashlib, hmac
from datetime import datetime
import pandas as pd
import streamlit as st


# ── Cliente Supabase ──────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _get_client():
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
                        "is_admin":        r.get("is_admin", False),
                        "abas_permitidas": abas,
                    }
                return out
        except Exception:
            pass
    try:
        return {k: dict(v) for k, v in st.secrets["usuarios"].items()}
    except Exception:
        return {}

def alterar_senha(login: str, nova: str) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        h = _hash(nova)
        res = sb.table("genius_usuarios").select("id").eq("login", login).execute()
        if res.data:
            sb.table("genius_usuarios").update({"senha_hash": h}).eq("login", login).execute()
        else:
            # Cria a partir do fallback de secrets
            dados = {}
            try: dados = dict(st.secrets["usuarios"].get(login, {}))
            except Exception: pass
            sb.table("genius_usuarios").insert({
                "login": login, "nome": dados.get("nome", login),
                "perfil": dados.get("perfil", "comercial"),
                "senha_hash": h, "is_admin": login == "lucas",
            }).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao alterar senha: {e}"); return False

def criar_usuario(login: str, nome: str, perfil: str, senha: str,
                  is_admin: bool = False, abas: list | None = None) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_usuarios").insert({
            "login": login.strip().lower(), "nome": nome.strip(),
            "perfil": perfil, "senha_hash": _hash(senha),
            "is_admin": is_admin,
            "abas_permitidas": json.dumps(abas) if abas else None,
        }).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao criar usuário: {e}"); return False

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
        st.error(f"Erro ao excluir: {e}"); return False


# ══════════════════════════════════════════════════════════════
# PRODUÇÃO
# ══════════════════════════════════════════════════════════════

_COLS_PROD = [
    "Equipamento","Cliente","Representante","Data_Pedido",
    "Data_Inicio_Producao","Data_Entrega_Prevista","Data_Entrega_Real",
    "Status_Producao","Observacoes",
]

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
        # mantém coluna id para deleção
        return df[["id"] + _COLS_PROD].reset_index(drop=True)
    except Exception as e:
        st.error(f"Erro ao ler produção: {e}"); return pd.DataFrame(columns=_COLS_PROD)

def adicionar_producao(reg: dict) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        payload = {k: str(v) if v is not None else "" for k, v in reg.items() if k in _COLS_PROD}
        sb.table("genius_producao").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar produção: {e}"); return False

def atualizar_producao_campo(row_id: int, campo: str, valor: str) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_producao").update({campo: str(valor)}).eq("id", row_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}"); return False

def excluir_producao(row_id: int) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_producao").delete().eq("id", row_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir: {e}"); return False

def importar_producao(uploaded) -> tuple[int, str]:
    try:
        uploaded.seek(0)
        df = pd.read_csv(uploaded, encoding="utf-8-sig") if uploaded.name.lower().endswith(".csv") \
             else pd.read_excel(uploaded, engine="openpyxl")
    except Exception:
        return 0, "Erro ao ler arquivo."
    count = 0
    for _, row in df.iterrows():
        if adicionar_producao({c: str(row.get(c,"")) for c in _COLS_PROD}):
            count += 1
    return count, "OK"

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
    except Exception as e:
        st.error(f"Erro ao ler orçamentos: {e}"); return pd.DataFrame(columns=_COLS_ORC)

def adicionar_orcamento(reg: dict) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        if not reg.get("Valor_Total"):
            try: reg["Valor_Total"] = float(reg.get("Quantidade",0)) * float(reg.get("Valor_Unit",0))
            except Exception: reg["Valor_Total"] = 0.0
        payload = {k: str(v) if v is not None else "" for k, v in reg.items() if k in _COLS_ORC}
        sb.table("genius_orcamentos").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar orçamento: {e}"); return False

def atualizar_orcamento(row_id: int, dados: dict) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        payload = {k: str(v) for k, v in dados.items() if k in _COLS_ORC}
        sb.table("genius_orcamentos").update(payload).eq("id", row_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar orçamento: {e}"); return False

def excluir_orcamento(row_id: int) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_orcamentos").delete().eq("id", row_id).execute()
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
    except Exception as e:
        st.error(f"Erro ao ler NFs: {e}"); return []

def adicionar_nf(reg: dict) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_nf_demo").insert({k: reg.get(k,"") for k in _COLS_NF}).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar NF: {e}"); return False

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
    except Exception as e:
        st.error(f"Erro ao ler revendas: {e}"); return []

def adicionar_revenda_cadastro(reg: dict) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_revendas").insert({k: reg.get(k,"") for k in _COLS_REV}).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar revenda: {e}"); return False

def excluir_revenda_cadastro(row_id: int) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_revendas").delete().eq("id", row_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir revenda: {e}"); return False


# ══════════════════════════════════════════════════════════════
# ESTOQUE PÁTIO / REVENDAS
# ══════════════════════════════════════════════════════════════

_COLS_PATIO = ["Codigo","Modelo","Tipo","Ano","Cor","Numero_Serie","Data_Entrada","Status_Patio","Observacoes"]
_COLS_EST_REV = ["Codigo","Modelo","Revenda","Contato","Cidade","Estado","Data_Envio","Data_Retorno_Prevista","Status_Revenda","Observacoes"]

def ler_patio() -> pd.DataFrame:
    sb = _sb()
    if not sb: return pd.DataFrame(columns=_COLS_PATIO)
    try:
        res = sb.table("genius_estoque_patio").select("*").order("id").execute()
        return _to_df(res.data or [], _COLS_PATIO)
    except Exception as e:
        st.error(f"Erro pátio: {e}"); return pd.DataFrame(columns=_COLS_PATIO)

def adicionar_patio(reg: dict) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_estoque_patio").insert({k: str(reg.get(k,"")) for k in _COLS_PATIO}).execute()
        return True
    except Exception as e:
        st.error(f"Erro: {e}"); return False

def excluir_patio(row_id: int) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_estoque_patio").delete().eq("id", row_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro: {e}"); return False

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
    except Exception as e:
        st.error(f"Erro: {e}"); return pd.DataFrame(columns=_COLS_EST_REV)

def adicionar_revenda_estoque(reg: dict) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_estoque_revendas").insert({k: str(reg.get(k,"")) for k in _COLS_EST_REV}).execute()
        return True
    except Exception as e:
        st.error(f"Erro: {e}"); return False

def excluir_revenda_estoque(row_id: int) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_estoque_revendas").delete().eq("id", row_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro: {e}"); return False

def exportar_revendas_estoque() -> bytes:
    buf = io.BytesIO()
    ler_revendas_estoque().to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════
# CACHE PLANILHA PEÇAS
# ══════════════════════════════════════════════════════════════

def salvar_cache_pecas(df: pd.DataFrame, nome: str) -> bool:
    sb = _sb()
    if not sb: return False
    try:
        sb.table("genius_pecas_cache").upsert({
            "chave": "pecas_senior", "nome_arquivo": nome,
            "dados_json": df.to_json(orient="records", date_format="iso", force_ascii=False),
            "atualizado_em": _agora(),
        }, on_conflict="chave").execute()
        return True
    except Exception as e:
        st.error(f"Erro cache peças: {e}"); return False

def ler_cache_pecas() -> tuple[pd.DataFrame | None, str]:
    sb = _sb()
    if not sb: return None, ""
    try:
        res = sb.table("genius_pecas_cache").select("*").eq("chave","pecas_senior").execute()
        if not res.data: return None, ""
        row = res.data[0]
        df  = pd.read_json(io.StringIO(row["dados_json"]), orient="records")
        if "Data_Venda" in df.columns:
            df["Data_Venda"] = pd.to_datetime(df["Data_Venda"], errors="coerce")
        return df, row.get("nome_arquivo","planilha")
    except Exception as e:
        st.error(f"Erro leitura cache: {e}"); return None, ""


# ══════════════════════════════════════════════════════════════
# E-MAIL — notificações de NF
# ══════════════════════════════════════════════════════════════

def enviar_email_nf(para: str, assunto: str, corpo: str) -> bool:
    """
    Envia e-mail via SMTP configurado nos secrets:
      [email]
      smtp_host    = "smtp.gmail.com"
      smtp_port    = 587
      smtp_user    = "seu@email.com"
      smtp_pass    = "app_password"
      remetente    = "Genius Plantadeiras <seu@email.com>"
    """
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

        with smtplib.SMTP(host, port) as s:
            s.ehlo()
            s.starttls()
            s.login(user, pwd)
            s.sendmail(user, [para], msg.as_string())
        return True
    except Exception as e:
        st.error(f"Erro ao enviar e-mail: {e}")
        return False
