"""
auth.py — Genius Plantadeiras v13
Novidades:
  • Usuários buscados do Supabase (genius_usuarios) com fallback para secrets
  • Cada usuário pode redefinir a própria senha
  • Perfil admin (lucas) pode criar, editar e excluir qualquer usuário
  • Tela de login mantém o mesmo visual
"""

from __future__ import annotations

import hashlib
import hmac

import streamlit as st
from data.db import ler_usuarios, alterar_senha, criar_usuario, excluir_usuario


# ──────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────

def _hash(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()


def _verificar(senha_digitada: str, hash_salvo: str) -> bool:
    return hmac.compare_digest(_hash(senha_digitada), hash_salvo)


# ──────────────────────────────────────────────────────────────
# Tela de Login
# ──────────────────────────────────────────────────────────────

def tela_login() -> bool:
    if st.session_state.get("autenticado"):
        return True

    col_l, col_c, col_r = st.columns([1, 1.4, 1])
    with col_c:
        st.markdown("<div style='height:60px'></div>", unsafe_allow_html=True)

        st.markdown("""
<div style='text-align:center;margin-bottom:32px;'>
  <div style='font-size:2.6rem;font-weight:800;color:#E36C2C;
              font-family:Barlow Condensed,sans-serif;letter-spacing:.02em;'>
    🌾 Genius Plantadeiras
  </div>
  <div style='color:#6A7A8A;font-size:1rem;margin-top:4px;'>
    Performance Comercial e Gestão Integrada
  </div>
</div>
""", unsafe_allow_html=True)

        with st.form("form_login", clear_on_submit=False):
            usuario = st.text_input("Usuário", placeholder="seu.usuario", key="login_user")
            senha   = st.text_input("Senha",   placeholder="••••••••",   type="password", key="login_pass")
            entrar  = st.form_submit_button("Entrar", type="primary", use_container_width=True)

        if entrar:
            usuarios = ler_usuarios()
            user_lower = usuario.strip().lower()
            if user_lower in usuarios:
                dados = usuarios[user_lower]
                hash_salvo = dados.get("senha_hash", "") if isinstance(dados, dict) else ""
                if _verificar(senha, hash_salvo):
                    st.session_state.autenticado   = True
                    st.session_state.usuario_atual = user_lower
                    st.session_state.perfil_atual  = dados.get("perfil", "comercial")
                    st.session_state.nome_usuario  = dados.get("nome", usuario)
                    st.session_state.is_admin      = dados.get("is_admin", False) or user_lower == "lucas"
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
            else:
                st.error("Usuário não encontrado.")

        st.markdown("""
<div style='text-align:center;color:#3A4858;font-size:11px;margin-top:24px;'>
  Acesso restrito · Genius Plantadeiras © 2025
</div>
""", unsafe_allow_html=True)

    return False


# ──────────────────────────────────────────────────────────────
# Painel do usuário na sidebar
# ──────────────────────────────────────────────────────────────

def painel_usuario():
    nome   = st.session_state.get("nome_usuario", "Usuário")
    perfil = st.session_state.get("perfil_atual", "comercial")
    admin  = st.session_state.get("is_admin", False)

    icone = "💼" if perfil == "comercial" else "🏭"
    label = "Comercial" if perfil == "comercial" else "PCP"
    admin_badge = ' <span style="color:#E36C2C;font-size:10px;">★ Admin</span>' if admin else ""

    st.sidebar.markdown(f"""
<div style='padding:10px 0 8px;'>
  <div style='font-size:13px;color:#A8B8CC;'>
    Olá, <strong style='color:#EEF2F8;'>{nome}</strong>{admin_badge}
  </div>
  <div style='font-size:11px;color:#6A7A8A;margin-top:2px;'>{icone} Perfil: {label}</div>
</div>
""", unsafe_allow_html=True)

    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("🔑 Senha", use_container_width=True, key="btn_senha"):
            st.session_state["_modal_senha"] = True
    with col2:
        if st.button("Sair", use_container_width=True, key="btn_sair"):
            for k in ["autenticado", "usuario_atual", "perfil_atual", "nome_usuario", "is_admin"]:
                st.session_state.pop(k, None)
            st.rerun()

    # Modal de redefinição de senha (própria)
    if st.session_state.get("_modal_senha"):
        _modal_redefinir_senha()


# ──────────────────────────────────────────────────────────────
# Modal — Redefinir a própria senha
# ──────────────────────────────────────────────────────────────

def _modal_redefinir_senha():
    with st.sidebar.expander("🔑 Redefinir Minha Senha", expanded=True):
        login_atual = st.session_state.get("usuario_atual", "")

        with st.form("form_mudar_senha", clear_on_submit=True):
            senha_atual  = st.text_input("Senha atual",     type="password", key="sp_atual")
            senha_nova   = st.text_input("Nova senha",       type="password", key="sp_nova")
            senha_conf   = st.text_input("Confirmar senha",  type="password", key="sp_conf")
            salvar       = st.form_submit_button("Salvar nova senha", type="primary")

        if salvar:
            usuarios = ler_usuarios()
            dados = usuarios.get(login_atual, {})
            if not _verificar(senha_atual, dados.get("senha_hash", "")):
                st.sidebar.error("Senha atual incorreta.")
            elif len(senha_nova) < 6:
                st.sidebar.error("A nova senha deve ter pelo menos 6 caracteres.")
            elif senha_nova != senha_conf:
                st.sidebar.error("As senhas não coincidem.")
            else:
                if alterar_senha(login_atual, senha_nova):
                    st.sidebar.success("✅ Senha alterada com sucesso!")
                    st.session_state.pop("_modal_senha", None)
                    st.rerun()

        if st.sidebar.button("Cancelar", key="btn_cancel_senha"):
            st.session_state.pop("_modal_senha", None)
            st.rerun()


# ──────────────────────────────────────────────────────────────
# Painel Admin — Gerenciar Usuários
# ──────────────────────────────────────────────────────────────

def render_painel_admin():
    """
    Renderiza o painel completo de gerenciamento de usuários.
    Deve ser chamado dentro de uma aba exclusiva (ex: aba '⚙️ Admin').
    Só é exibido para usuários com is_admin=True.
    """
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
                font-weight:700;color:#F0F4F8;line-height:1.1;">Gerenciar Usuários</div>
    <div style="font-size:12px;color:#6A7A8A;text-transform:uppercase;
                letter-spacing:.07em;margin-top:4px;">
      Criar · Redefinir senhas · Excluir</div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Criar novo usuário ─────────────────────────────────────
    with st.expander("➕ Criar Novo Usuário", expanded=False):
        with st.form("form_criar_user", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                novo_login  = st.text_input("Login (usuário)", placeholder="ex: vendedor4", key="nu_login")
                novo_nome   = st.text_input("Nome completo",   placeholder="ex: Carlos Souza", key="nu_nome")
            with c2:
                novo_perfil = st.selectbox("Perfil", ["comercial", "pcp"], key="nu_perfil")
                novo_admin  = st.checkbox("É administrador?", key="nu_admin")
            nova_senha  = st.text_input("Senha inicial", type="password", key="nu_senha")
            nova_conf   = st.text_input("Confirmar senha", type="password", key="nu_conf")
            criar = st.form_submit_button("✅ Criar Usuário", type="primary")

        if criar:
            usuarios_existentes = ler_usuarios()
            if not novo_login.strip():
                st.error("Login é obrigatório.")
            elif novo_login.strip().lower() in usuarios_existentes:
                st.error(f"Login '{novo_login}' já existe.")
            elif len(nova_senha) < 6:
                st.error("Senha deve ter pelo menos 6 caracteres.")
            elif nova_senha != nova_conf:
                st.error("Senhas não coincidem.")
            else:
                if criar_usuario(novo_login.strip().lower(), novo_nome.strip(),
                                 novo_perfil, nova_senha, novo_admin):
                    st.success(f"✅ Usuário '{novo_login}' criado com sucesso!")
                    st.rerun()

    st.divider()

    # ── Lista de usuários com opções ──────────────────────────
    st.subheader("👥 Usuários Cadastrados")
    usuarios = ler_usuarios()

    if not usuarios:
        st.info("Nenhum usuário encontrado.")
        return

    for login, dados in usuarios.items():
        nome_u  = dados.get("nome", login)
        perfil_u = dados.get("perfil", "comercial")
        admin_u  = dados.get("is_admin", False) or login == "lucas"

        with st.expander(f"{'★ ' if admin_u else ''}{nome_u}  —  @{login}  [{perfil_u}]"):
            tab_senha, tab_excluir = st.tabs(["🔑 Redefinir Senha", "🗑 Excluir"])

            with tab_senha:
                with st.form(f"form_reset_{login}", clear_on_submit=True):
                    s1 = st.text_input("Nova senha",      type="password", key=f"rs1_{login}")
                    s2 = st.text_input("Confirmar senha", type="password", key=f"rs2_{login}")
                    ok = st.form_submit_button("Salvar", type="primary")
                if ok:
                    if len(s1) < 6:
                        st.error("Senha muito curta (mínimo 6 caracteres).")
                    elif s1 != s2:
                        st.error("Senhas não coincidem.")
                    else:
                        if alterar_senha(login, s1):
                            st.success(f"✅ Senha de '{nome_u}' redefinida!")

            with tab_excluir:
                login_eu = st.session_state.get("usuario_atual", "")
                if login == login_eu:
                    st.warning("Você não pode excluir sua própria conta.")
                else:
                    st.warning(f"⚠️ Isso removerá permanentemente o usuário **{nome_u}**.")
                    if st.button(f"🗑 Excluir {nome_u}", key=f"del_user_{login}", type="secondary"):
                        if excluir_usuario(login):
                            st.success(f"Usuário '{nome_u}' excluído.")
                            st.rerun()


# ──────────────────────────────────────────────────────────────
# Helpers de perfil
# ──────────────────────────────────────────────────────────────

def perfil_atual() -> str:
    return st.session_state.get("perfil_atual", "comercial")

def is_comercial() -> bool:
    return perfil_atual() == "comercial"

def is_pcp() -> bool:
    return perfil_atual() == "pcp"

def is_admin() -> bool:
    return st.session_state.get("is_admin", False)
