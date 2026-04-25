"""
auth.py — Genius Implementos Agrícolas v14 (CORRIGIDO)

Correções aplicadas:
  [FIX-SEC-1] Removido hardcode "lucas" como admin em todas as verificações
  [FIX-SEC-6] Fallback seguro de abas_permitidas: lista vazia ao invés de TODAS_ABAS
              quando session_state não tem o campo (evita exposição por sessão parcial)
  [FIX-SEC-7] is_admin lido exclusivamente do banco via session_state,
              sem comparação de string de login
"""

from __future__ import annotations
import hashlib, hmac
import streamlit as st
from data.db import ler_usuarios, alterar_senha, criar_usuario, excluir_usuario, atualizar_usuario

# ── Abas disponíveis no sistema ───────────────────────────────
TODAS_ABAS = [
    "🏬 Revendas",
    "🤝 Pipeline Máquinas",
    "⚙️ PCP",
    "📦 Estoque de Máquinas",
    "📄 NF em Demonstração",
    "🔧 Peças",
    "🗺️ Territórios",
]
ABAS_COMERCIAL = TODAS_ABAS
ABAS_PCP       = ["⚙️ PCP", "🔧 Peças"]


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

def _verificar(digitada: str, salvo: str) -> bool:
    # Bloco seguro: salvo vazio nunca autentica
    if not salvo:
        return False
    return hmac.compare_digest(_hash(digitada), salvo)


# ── Tela de Login ─────────────────────────────────────────────
def tela_login() -> bool:
    if st.session_state.get("autenticado"):
        return True

    col_l, col_c, col_r = st.columns([1, 1.4, 1])
    with col_c:
        st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)

        import os, base64 as _b64
        def _logo_b64(rel):
            for p in [
                os.path.join(os.path.dirname(os.path.abspath(__file__)), rel),
                os.path.join(os.getcwd(), rel),
                rel,
            ]:
                if os.path.exists(p):
                    with open(p, 'rb') as _f:
                        return _b64.b64encode(_f.read()).decode()
            return None

        logo_data = _logo_b64('assets/genius_logo.png')
        if logo_data:
            st.markdown(
                '<div style="display:flex;justify-content:center;margin-bottom:12px;">'
                f'<img src="data:image/png;base64,{logo_data}" '
                'style="max-width:220px;width:100%;"></div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                "<div style='text-align:center;margin-bottom:8px;'>"
                "<span style='font-size:2.2rem;font-weight:800;color:#E36C2C;'>"
                "Genius Implementos Agrícolas</span></div>",
                unsafe_allow_html=True
            )

        st.markdown("""
<div style='text-align:center;color:#6A7A8A;font-size:.95rem;margin-bottom:28px;'>
  Performance Comercial e Gestão Integrada
</div>
""", unsafe_allow_html=True)

        with st.form("form_login", clear_on_submit=False):
            usuario = st.text_input("Usuário", placeholder="seu.usuario")
            senha   = st.text_input("Senha",   placeholder="••••••••", type="password")
            entrar  = st.form_submit_button("Entrar", type="primary", use_container_width=True)

        if entrar:
            with st.spinner("🔐 Verificando credenciais..."):
                usuarios   = ler_usuarios()
            user_lower = usuario.strip().lower()
            if user_lower in usuarios:
                d = usuarios[user_lower]
                if _verificar(senha, d.get("senha_hash", "")):
                    st.session_state.autenticado   = True
                    st.session_state.usuario_atual = user_lower
                    st.session_state.perfil_atual  = d.get("perfil", "comercial")
                    st.session_state.nome_usuario  = d.get("nome", usuario)
                    # [FIX-SEC-1] is_admin vem APENAS do banco, sem hardcode de login
                    st.session_state.is_admin      = bool(d.get("is_admin", False))

                    # Abas permitidas: custom > perfil > padrão seguro
                    abas_custom = d.get("abas_permitidas")
                    if abas_custom:
                        st.session_state.abas_permitidas = abas_custom
                    elif d.get("perfil") == "pcp":
                        st.session_state.abas_permitidas = ABAS_PCP
                    else:
                        st.session_state.abas_permitidas = TODAS_ABAS
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
            else:
                st.error("Usuário não encontrado.")

        st.markdown("""
<div style='text-align:center;color:#3A4858;font-size:11px;margin-top:20px;'>
  Acesso Restrito · Genius Implementos Agrícolas 2026
</div>""", unsafe_allow_html=True)

    return False


# ── Sidebar do usuário ────────────────────────────────────────
def painel_usuario():
    nome   = st.session_state.get("nome_usuario", "Usuário")
    perfil = st.session_state.get("perfil_atual", "comercial")
    admin  = st.session_state.get("is_admin", False)

    icone = "💼" if perfil == "comercial" else "🏭"
    label = "Comercial" if perfil == "comercial" else "PCP"
    adm_badge = ' <span style="color:#E36C2C;font-size:10px;">★ Admin</span>' if admin else ""

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"""
<div style='padding:6px 0 8px;'>
  <div style='font-size:13px;color:#A8B8CC;'>
    Olá, <strong style='color:#EEF2F8;'>{nome}</strong>{adm_badge}
  </div>
  <div style='font-size:11px;color:#6A7A8A;margin-top:2px;'>{icone} Perfil: {label}</div>
</div>""", unsafe_allow_html=True)

    c1, c2 = st.sidebar.columns(2)
    with c1:
        if st.button("🔑 Senha", use_container_width=True, key="btn_senha_side"):
            st.session_state["_modal_senha"] = True
    with c2:
        if st.button("Sair", use_container_width=True, key="btn_sair"):
            for k in ["autenticado","usuario_atual","perfil_atual","nome_usuario","is_admin","abas_permitidas"]:
                st.session_state.pop(k, None)
            st.rerun()

    if st.session_state.get("_modal_senha"):
        _modal_senha()


def _modal_senha():
    with st.sidebar.expander("🔑 Redefinir Minha Senha", expanded=True):
        login = st.session_state.get("usuario_atual", "")
        with st.form("form_minha_senha", clear_on_submit=True):
            atual = st.text_input("Senha atual",    type="password", key="mp_atual")
            nova  = st.text_input("Nova senha",     type="password", key="mp_nova")
            conf  = st.text_input("Confirmar",      type="password", key="mp_conf")
            ok    = st.form_submit_button("Salvar", type="primary")
        if ok:
            usuarios = ler_usuarios()
            d = usuarios.get(login, {})
            if not _verificar(atual, d.get("senha_hash", "")):
                st.sidebar.error("Senha atual incorreta.")
            elif len(nova) < 6:
                st.sidebar.error("Mínimo 6 caracteres.")
            elif nova != conf:
                st.sidebar.error("As senhas não coincidem.")
            else:
                if alterar_senha(login, nova):
                    st.sidebar.success("✅ Senha alterada!")
                    st.session_state.pop("_modal_senha", None)
                    st.rerun()
        if st.sidebar.button("Cancelar", key="btn_cancel_mp"):
            st.session_state.pop("_modal_senha", None)
            st.rerun()


# ── Painel Admin ──────────────────────────────────────────────
def render_painel_admin():
    if not st.session_state.get("is_admin"):
        st.warning("⛔ Acesso restrito a administradores.")
        return

    st.markdown("""
<div style="display:flex;align-items:center;gap:14px;padding:10px 0 18px;
            border-bottom:1px solid #2D3748;margin-bottom:24px;">
  <div style="background:rgba(227,108,44,.14);border:1px solid rgba(227,108,44,.4);
              border-radius:10px;padding:10px 14px;font-size:22px;">⚙️</div>
  <div>
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:1.9rem;
                font-weight:700;color:#F0F4F8;">Gerenciar Usuários</div>
    <div style="font-size:12px;color:#6A7A8A;text-transform:uppercase;letter-spacing:.07em;margin-top:4px;">
      Criar · Permissões · Senhas · Excluir</div>
  </div>
</div>""", unsafe_allow_html=True)

    # ── Criar usuário ─────────────────────────────────────────
    with st.expander("➕ Criar Novo Usuário", expanded=False):
        with st.form("form_criar_user", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                nu_login  = st.text_input("Login", placeholder="ex: vendedor4", key="nu_login")
                nu_nome   = st.text_input("Nome",  placeholder="ex: Carlos Souza", key="nu_nome")
            with c2:
                nu_perfil = st.selectbox("Perfil base", ["comercial", "pcp"], key="nu_perfil")
                nu_admin  = st.checkbox("Administrador?", key="nu_admin")
            nu_abas = st.multiselect(
                "Abas permitidas (deixe vazio = padrão do perfil)",
                TODAS_ABAS, key="nu_abas",
            )
            nu_senha = st.text_input("Senha inicial", type="password", key="nu_senha")
            nu_conf  = st.text_input("Confirmar senha", type="password", key="nu_conf")
            criar_btn = st.form_submit_button("✅ Criar Usuário", type="primary")

        if criar_btn:
            existentes = ler_usuarios()
            if not nu_login.strip():
                st.error("Login é obrigatório.")
            elif nu_login.strip().lower() in existentes:
                st.error(f"Login '{nu_login}' já existe.")
            elif len(nu_senha) < 6:
                st.error("Mínimo 6 caracteres na senha.")
            elif nu_senha != nu_conf:
                st.error("Senhas não coincidem.")
            else:
                abas_salvar = nu_abas if nu_abas else (
                    ABAS_PCP if nu_perfil == "pcp" else TODAS_ABAS
                )
                if criar_usuario(nu_login.strip().lower(), nu_nome.strip(),
                                 nu_perfil, nu_senha, nu_admin, abas_salvar):
                    st.success(f"✅ Usuário '{nu_login}' criado!")
                    st.rerun()

    st.divider()
    st.subheader("👥 Usuários Cadastrados")
    usuarios = ler_usuarios()

    for login, d in usuarios.items():
        nome_u   = d.get("nome", login)
        perfil_u = d.get("perfil", "comercial")
        # [FIX-SEC-1] admin_u vem apenas do banco
        admin_u  = bool(d.get("is_admin", False))
        abas_u   = d.get("abas_permitidas", TODAS_ABAS if perfil_u == "comercial" else ABAS_PCP)

        with st.expander(f"{'★ ' if admin_u else ''}{nome_u}  —  @{login}  [{perfil_u}]"):
            tab_perm, tab_senha, tab_excluir = st.tabs(["🔐 Permissões", "🔑 Senha", "🗑 Excluir"])

            with tab_perm:
                with st.form(f"form_perm_{login}", clear_on_submit=False):
                    novo_perfil = st.selectbox("Perfil", ["comercial","pcp"],
                                               index=0 if perfil_u=="comercial" else 1,
                                               key=f"pf_{login}")
                    # Filtra abas_u para só incluir valores que existem em TODAS_ABAS
                    abas_u_validas = [a for a in (abas_u or []) if a in TODAS_ABAS]
                    novas_abas  = st.multiselect("Abas com acesso", TODAS_ABAS,
                                                  default=abas_u_validas, key=f"ab_{login}")
                    novo_admin  = st.checkbox("Administrador", value=admin_u, key=f"adm_{login}")
                    salvar_perm = st.form_submit_button("💾 Salvar Permissões", type="primary")
                if salvar_perm:
                    abas_final = novas_abas if novas_abas else (
                        ABAS_PCP if novo_perfil == "pcp" else TODAS_ABAS
                    )
                    if atualizar_usuario(login, {"perfil": novo_perfil,
                                                  "abas_permitidas": abas_final,
                                                  "is_admin": novo_admin}):
                        st.success("✅ Permissões atualizadas!")

            with tab_senha:
                with st.form(f"form_reset_{login}", clear_on_submit=True):
                    s1 = st.text_input("Nova senha",     type="password", key=f"rs1_{login}")
                    s2 = st.text_input("Confirmar",      type="password", key=f"rs2_{login}")
                    ok = st.form_submit_button("Salvar", type="primary")
                if ok:
                    if len(s1) < 6:
                        st.error("Mínimo 6 caracteres.")
                    elif s1 != s2:
                        st.error("Senhas não coincidem.")
                    else:
                        if alterar_senha(login, s1):
                            st.success(f"✅ Senha de '{nome_u}' redefinida!")

            with tab_excluir:
                eu = st.session_state.get("usuario_atual", "")
                if login == eu:
                    st.warning("Você não pode excluir sua própria conta.")
                else:
                    st.warning(f"Remove permanentemente **{nome_u}**.")
                    if st.button(f"🗑 Excluir {nome_u}", key=f"del_u_{login}"):
                        if excluir_usuario(login):
                            st.success(f"'{nome_u}' excluído.")
                            st.rerun()


def abas_permitidas() -> list[str]:
    # [FIX-SEC-6] Fallback seguro: lista vazia se sessão parcial — app exibe aviso
    abas = st.session_state.get("abas_permitidas")
    if abas is None:
        return []
    return abas

def perfil_atual() -> str:
    return st.session_state.get("perfil_atual", "comercial")

def is_admin() -> bool:
    # [FIX-SEC-1] Apenas lê do session_state — sem hardcode de login
    return bool(st.session_state.get("is_admin", False))
