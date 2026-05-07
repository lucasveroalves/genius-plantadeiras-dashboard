"""
auth.py — Genius Implementos Agrícolas v17

Alterações v17:
  [V17-1]  Removida aba "⚙️ PCP" de TODAS_ABAS e ABAS_PCP.
           ABAS_PCP mantido por compatibilidade mas sem PCP.
"""

from __future__ import annotations
from datetime import datetime, timedelta
import streamlit as st
from data.db import (
    ler_usuarios, alterar_senha, criar_usuario, excluir_usuario,
    atualizar_usuario, verificar_senha, _hash_senha,
)

# ── Configuração de sessão ────────────────────────────────────
SESSION_TTL_MINUTOS = 480   # 8 horas

# ── Abas disponíveis no sistema — PCP REMOVIDO [V17-1] ───────
TODAS_ABAS = [
    "📝 Orçamento de Peças",
    "🏬 Revendas",
    "🤝 Pipeline Máquinas",
    "📦 Estoque de Máquinas",
    "📄 NF em Demonstração",
    "🔧 Peças",
    "🗺️ Territórios",
]
ABAS_PCP = ["🔧 Peças"]   # mantido por compatibilidade — sem PCP


# ── Tela de Login ─────────────────────────────────────────────
def tela_login() -> bool:
    if st.session_state.get("autenticado"):
        login_time = st.session_state.get("login_time")
        if login_time:
            elapsed = (datetime.now() - login_time).total_seconds() / 60
            if elapsed > SESSION_TTL_MINUTOS:
                _limpar_sessao()
                st.warning("⏱️ Sessão expirada. Faça login novamente.")
                st.rerun()
        return True

    col_l, col_c, col_r = st.columns([1, 1.4, 1])
    with col_c:
        st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)

        import os, base64 as _b64
        def _logo_b64(rel):
            for p in [
                os.path.join(os.path.dirname(os.path.abspath(__file__)), rel),
                os.path.join(os.getcwd(), rel),
            ]:
                if os.path.exists(p):
                    with open(p, "rb") as f:
                        return _b64.b64encode(f.read()).decode()
            return None

        logo_data = _logo_b64("assets/genius_logo.png")
        if logo_data:
            st.markdown(
                f'<div style="text-align:center;margin-bottom:20px;">'
                f'<img src="data:image/png;base64,{logo_data}" style="max-width:220px;"></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='text-align:center;font-size:2rem;font-weight:800;"
                "color:#E36C2C;font-family:Barlow Condensed,sans-serif;'>"
                "🌾 Genius Implementos</div>",
                unsafe_allow_html=True,
            )

        st.markdown(
            "<div style='text-align:center;color:#6A7A8A;margin-bottom:30px;'>Sistema Comercial</div>",
            unsafe_allow_html=True,
        )

        with st.form("form_login", clear_on_submit=False):
            usuario = st.text_input("Usuário", placeholder="Seu login")
            senha   = st.text_input("Senha",   type="password", placeholder="Sua senha")
            login_btn = st.form_submit_button("🔐 Entrar", use_container_width=True, type="primary")

        if login_btn:
            if not usuario.strip() or not senha.strip():
                st.error("Preencha usuário e senha.")
                return False

            usuarios = ler_usuarios()
            dados = usuarios.get(usuario.strip())

            if not dados:
                st.error("Usuário não encontrado.")
                return False

            hash_salvo = dados.get("senha_hash") or dados.get("senha") or ""
            if not verificar_senha(senha, hash_salvo):
                st.error("Senha incorreta.")
                return False

            perfil = dados.get("perfil", "comercial")
            abas   = dados.get("abas_permitidas") or (TODAS_ABAS if perfil == "comercial" else ABAS_PCP)

            st.session_state.autenticado      = True
            st.session_state.usuario_atual    = usuario.strip()
            st.session_state.perfil_atual     = perfil
            st.session_state.nome_usuario     = dados.get("nome") or usuario.strip()
            st.session_state.is_admin         = bool(dados.get("is_admin", False))
            st.session_state.abas_permitidas  = abas
            st.session_state.login_time       = datetime.now()
            st.rerun()

    return False


def _limpar_sessao():
    for k in ["autenticado", "usuario_atual", "perfil_atual", "nome_usuario",
              "is_admin", "abas_permitidas", "login_time", "_sb_ok"]:
        st.session_state.pop(k, None)


def painel_usuario():
    usuario = st.session_state.get("nome_usuario", "")
    perfil  = st.session_state.get("perfil_atual", "")
    admin   = st.session_state.get("is_admin", False)

    badge = "★ Admin" if admin else ""
    label = "Comercial" if perfil == "comercial" else "PCP"

    st.sidebar.markdown(
        f'<div style="font-size:13px;color:#EEF2F8;font-weight:600;">Olá, {usuario} '
        f'<span style="color:#E36C2C;font-size:11px;">{badge}</span></div>'
        f'<div style="font-size:11px;color:#6A7A8A;">🟢 Perfil: {label}</div>',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("---")

    col1, col2 = st.sidebar.columns(2)

    with col1:
        if st.button("🔑\nSenha", use_container_width=True):
            st.session_state["_mostrar_troca_senha"] = not st.session_state.get("_mostrar_troca_senha", False)

    with col2:
        if st.button("Sair", use_container_width=True):
            _limpar_sessao()
            st.rerun()

    if st.session_state.get("_mostrar_troca_senha"):
        with st.sidebar.form("form_troca_senha", clear_on_submit=True):
            s_atual = st.text_input("Senha atual", type="password")
            s_nova  = st.text_input("Nova senha",  type="password")
            s_conf  = st.text_input("Confirmar",   type="password")
            ok = st.form_submit_button("Alterar", type="primary")
            if ok:
                if len(s_nova) < 8:
                    st.error("Mínimo 8 caracteres.")
                elif s_nova != s_conf:
                    st.error("Senhas não coincidem.")
                else:
                    usuarios = ler_usuarios()
                    u = usuarios.get(st.session_state.get("usuario_atual", ""))
                    if u and verificar_senha(s_atual, u.get("senha_hash") or u.get("senha", "")):
                        alterar_senha(st.session_state["usuario_atual"], s_nova)
                        st.success("✅ Senha alterada!")
                        st.session_state["_mostrar_troca_senha"] = False
                    else:
                        st.error("Senha atual incorreta.")


def is_admin() -> bool:
    return bool(st.session_state.get("is_admin", False))


def abas_permitidas() -> list[str]:
    abas = st.session_state.get("abas_permitidas")
    if abas is None:
        return []
    return abas


def render_painel_admin():
    st.markdown("""
<div style="display:flex;align-items:center;gap:14px;padding:10px 0 18px;
            border-bottom:1px solid #2D3748;margin-bottom:24px;">
  <div style="background:rgba(227,108,44,.14);border:1px solid rgba(227,108,44,.4);
              border-radius:10px;padding:10px 14px;font-size:22px;">⚙️</div>
  <div>
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:1.9rem;
                font-weight:700;color:#F0F4F8;line-height:1.1;">Painel Administrativo</div>
    <div style="font-size:12px;color:#6A7A8A;text-transform:uppercase;
                letter-spacing:.07em;margin-top:4px;">Gestão de Usuários</div>
  </div>
</div>""", unsafe_allow_html=True)

    usuarios = ler_usuarios()

    # ── Criar usuário ──────────────────────────────────────────
    with st.expander("➕ Criar Novo Usuário", expanded=False):
        with st.form("form_criar_usuario", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                nu_login = st.text_input("Login *")
                nu_nome  = st.text_input("Nome completo")
                nu_senha = st.text_input("Senha *", type="password")
            with c2:
                nu_perfil  = st.selectbox("Perfil base", ["comercial", "pcp"], key="nu_perfil")
                nu_admin   = st.checkbox("É administrador?")
                nu_abas    = st.multiselect("Abas permitidas", TODAS_ABAS,
                                             default=TODAS_ABAS if nu_perfil == "comercial" else ABAS_PCP)
            criar = st.form_submit_button("✅ Criar Usuário", type="primary")
            if criar:
                if not nu_login.strip() or len(nu_senha) < 8:
                    st.error("Login e senha (min. 8 chars) são obrigatórios.")
                elif nu_login.strip() in usuarios:
                    st.error("Login já existe.")
                else:
                    ok = criar_usuario(
                        login    = nu_login.strip(),
                        nome     = nu_nome.strip(),
                        perfil   = nu_perfil,
                        senha    = nu_senha,
                        is_admin = nu_admin,
                        abas     = nu_abas or TODAS_ABAS,
                    )
                    if ok:
                        st.success(f"✅ Usuário '{nu_login}' criado!")
                        ler_usuarios.clear()
                        st.rerun()

    # ── Lista de usuários ──────────────────────────────────────
    st.subheader(f"👥 Usuários Cadastrados ({len(usuarios)})")
    usuario_atual = st.session_state.get("usuario_atual", "")

    for login, d in usuarios.items():
        perfil_u = d.get("perfil", "comercial")
        admin_u  = d.get("is_admin", False)
        nome_u   = d.get("nome") or login

        with st.expander(f"**{nome_u}** ({login}) — {perfil_u}" + (" ★ Admin" if admin_u else ""), expanded=False):
            abas_u   = d.get("abas_permitidas", TODAS_ABAS if perfil_u == "comercial" else ABAS_PCP)

            with st.form(f"form_edit_{login}", clear_on_submit=False):
                c1, c2 = st.columns(2)
                with c1:
                    novo_nome   = st.text_input("Nome", value=nome_u, key=f"nome_{login}")
                    novo_perfil = st.selectbox("Perfil", ["comercial", "pcp"],
                                               index=0 if perfil_u == "comercial" else 1,
                                               key=f"perf_{login}")
                    novo_admin  = st.checkbox("Admin", value=bool(admin_u), key=f"adm_{login}")
                with c2:
                    novas_abas = st.multiselect("Abas", TODAS_ABAS,
                                                 default=[a for a in abas_u if a in TODAS_ABAS],
                                                 key=f"abas_{login}")
                    nova_senha = st.text_input("Nova senha (deixe em branco para não alterar)",
                                               type="password", key=f"pw_{login}")

                c_save, c_del = st.columns(2)
                salvar = c_save.form_submit_button("💾 Salvar", type="primary")
                excluir = c_del.form_submit_button("🗑 Excluir", type="secondary")

                if salvar:
                    upd = {
                        "nome":            novo_nome.strip(),
                        "perfil":          novo_perfil,
                        "is_admin":        novo_admin,
                        "abas_permitidas": novas_abas or TODAS_ABAS,
                    }
                    if nova_senha and len(nova_senha) >= 8:
                        upd["senha_hash"] = _hash_senha(nova_senha)
                    elif nova_senha:
                        st.error("Senha precisa ter ao menos 8 caracteres.")
                    atualizar_usuario(login, upd)
                    st.success(f"✅ {login} atualizado!")
                    ler_usuarios.clear()
                    st.rerun()

                if excluir:
                    if login == usuario_atual:
                        st.error("Não é possível excluir o próprio usuário.")
                    else:
                        excluir_usuario(login)
                        st.success(f"🗑 {login} removido.")
                        ler_usuarios.clear()
                        st.rerun()
