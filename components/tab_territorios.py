"""
components/tab_territorios.py — Mapa de Territórios v1

Funcionalidades:
  - Mapa interativo do Brasil, Paraguai e Bolívia
  - Cadastro de revendas/representantes com suas cidades
  - Visualização de cobertura por território
  - Edição inline de cidades por revenda
  - Geocodificação via API IBGE + coordenadas fixas PY/BO
"""

from __future__ import annotations
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import urllib.request
import urllib.parse
from data.db import ler_territorios, adicionar_territorio, excluir_territorio, atualizar_territorio

# ── Coordenadas de cidades do Paraguai e Bolívia ─────────────
CIDADES_PY_BO = {
    # Paraguai
    "Assunção": (-25.2867, -57.647),
    "Ciudad del Este": (-25.5088, -54.6119),
    "Encarnación": (-27.3306, -55.8669),
    "Pedro Juan Caballero": (-22.5558, -55.7367),
    "Concepción": (-23.4067, -57.4325),
    "Villarrica": (-25.7528, -56.4347),
    "Caaguazú": (-25.4667, -56.0167),
    "Coronel Oviedo": (-25.4444, -56.4406),
    "San Lorenzo": (-25.3404, -57.5086),
    "Luque": (-25.2667, -57.4833),
    # Bolívia
    "Santa Cruz de la Sierra": (-17.8146, -63.1561),
    "La Paz": (-16.5, -68.15),
    "Cochabamba": (-17.3895, -66.1568),
    "Sucre": (-19.0431, -65.2592),
    "Oruro": (-17.9833, -67.15),
    "Trinidad": (-14.8333, -64.9),
    "Tarija": (-21.5333, -64.7333),
    "Potosí": (-19.5836, -65.7531),
}

# Paleta de cores para territórios
CORES = [
    "#E67E22", "#3D9970", "#2A5A8A", "#E84040", "#9B59B6",
    "#1ABC9C", "#F39C12", "#E91E63", "#00BCD4", "#8BC34A",
    "#FF5722", "#607D8B", "#795548", "#FFC107", "#03A9F4",
]

_CSS = """
<style>
.terr-sec{font-size:11px;font-weight:700;color:#3A4858;text-transform:uppercase;
  letter-spacing:.1em;border-bottom:1px solid #30394A;padding-bottom:6px;margin-bottom:14px;}
</style>
"""


@st.cache_data(ttl=3600)
def _buscar_cidades_ibge(estado_sigla: str) -> dict[str, tuple[float, float]]:
    """Busca municípios de um estado via API IBGE com coordenadas."""
    try:
        url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{estado_sigla}/municipios"
        with urllib.request.urlopen(url, timeout=5) as r:
            municipios = json.loads(r.read().decode())
        # Retorna apenas nomes (coordenadas buscadas separadamente)
        return {m["nome"]: None for m in municipios}
    except Exception:
        return {}


@st.cache_data(ttl=86400)
def _coordenadas_cidades_br() -> dict[str, tuple[float, float]]:
    """
    Coordenadas aproximadas das principais cidades brasileiras.
    Dataset estático para evitar dependência de API externa.
    """
    return {
        # Sul
        "Campos Novos": (-27.4017, -51.2244),
        "Florianópolis": (-27.5954, -48.5480),
        "Joinville": (-26.3044, -48.8487),
        "Blumenau": (-26.9194, -49.0661),
        "Chapecó": (-27.1005, -52.6156),
        "Lages": (-27.8153, -50.3253),
        "Criciúma": (-28.6773, -49.3700),
        "Itajaí": (-26.9078, -48.6619),
        "Curitiba": (-25.4284, -49.2733),
        "Londrina": (-23.3045, -51.1696),
        "Maringá": (-23.4205, -51.9333),
        "Cascavel": (-24.9578, -53.4595),
        "Foz do Iguaçu": (-25.5163, -54.5854),
        "Pato Branco": (-26.2295, -52.6705),
        "Francisco Beltrão": (-26.0813, -53.0557),
        "Guarapuava": (-25.3908, -51.4628),
        "Porto Alegre": (-30.0346, -51.2177),
        "Caxias do Sul": (-29.1678, -51.1794),
        "Pelotas": (-31.7654, -52.3376),
        "Santa Maria": (-29.6842, -53.8069),
        "Passo Fundo": (-28.2576, -52.4090),
        "Novo Hamburgo": (-29.6784, -51.1307),
        "São Leopoldo": (-29.7596, -51.1498),
        "Canoas": (-29.9178, -51.1839),
        "Gravataí": (-29.9440, -50.9915),
        "Ijuí": (-28.3878, -53.9148),
        "Santa Cruz do Sul": (-29.7176, -52.4261),
        "Lajeado": (-29.4669, -51.9614),
        "Bagé": (-31.3289, -54.1069),
        "Erechim": (-27.6339, -52.2739),
        "Uruguaiana": (-29.7545, -57.0882),
        "Rio Grande": (-32.0350, -52.0986),
        # Sudeste
        "São Paulo": (-23.5505, -46.6333),
        "Campinas": (-22.9068, -47.0626),
        "Ribeirão Preto": (-21.1699, -47.8100),
        "Santos": (-23.9608, -46.3331),
        "São José dos Campos": (-23.1896, -45.8841),
        "Sorocaba": (-23.5015, -47.4526),
        "Osasco": (-23.5323, -46.7917),
        "Rio de Janeiro": (-22.9068, -43.1729),
        "Niterói": (-22.8838, -43.1044),
        "Duque de Caxias": (-22.7856, -43.3117),
        "Nova Iguaçu": (-22.7592, -43.4511),
        "Belford Roxo": (-22.7642, -43.3994),
        "Belo Horizonte": (-19.9167, -43.9345),
        "Uberlândia": (-18.9186, -48.2772),
        "Contagem": (-19.9319, -44.0536),
        "Juiz de Fora": (-21.7643, -43.3503),
        "Betim": (-19.9678, -44.1986),
        "Montes Claros": (-16.7281, -43.8613),
        "Vitória": (-20.3155, -40.3128),
        "Vila Velha": (-20.3297, -40.2922),
        "Serra": (-20.1219, -40.3086),
        # Centro-Oeste
        "Brasília": (-15.7797, -47.9297),
        "Goiânia": (-16.6869, -49.2648),
        "Campo Grande": (-20.4697, -54.6201),
        "Cuiabá": (-15.6014, -56.0979),
        "Anápolis": (-16.3281, -48.9528),
        "Aparecida de Goiânia": (-16.8231, -49.2464),
        "Dourados": (-22.2211, -54.8056),
        "Rondonópolis": (-16.4714, -54.6381),
        "Sinop": (-11.8642, -55.5054),
        # Nordeste
        "Salvador": (-12.9714, -38.5014),
        "Fortaleza": (-3.7319, -38.5267),
        "Recife": (-8.0476, -34.8770),
        "Maceió": (-9.6658, -35.7350),
        "Natal": (-5.7945, -35.2110),
        "Teresina": (-5.0892, -42.8019),
        "São Luís": (-2.5297, -44.3028),
        "Feira de Santana": (-12.2664, -38.9663),
        "Caruaru": (-8.2760, -35.9761),
        # Norte
        "Manaus": (-3.1190, -60.0217),
        "Belém": (-1.4558, -48.5044),
        "Porto Velho": (-8.7612, -63.9004),
        "Macapá": (0.0356, -51.0705),
        "Boa Vista": (2.8235, -60.6758),
        "Rio Branco": (-9.9754, -67.8249),
        "Palmas": (-10.2491, -48.3243),
        "Araguaína": (-7.1920, -48.2046),
    }


@st.cache_data(ttl=86400, show_spinner=False)
def _buscar_coord_ibge(cidade: str, estado: str) -> tuple[float, float] | None:
    """Busca coordenadas de município via API IBGE + Nominatim como fallback."""
    try:
        import urllib.request as _req, json as _json, time as _time

        # Tenta Nominatim (OpenStreetMap) — mais preciso para municípios
        cidade_enc = urllib.parse.quote(f"{cidade}, {estado}, Brasil")
        url = f"https://nominatim.openstreetmap.org/search?q={cidade_enc}&format=json&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "GeniusDashboard/1.0"})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = _json.loads(r.read().decode())
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None


def _get_coordenadas(cidade: str, estado: str = "") -> tuple[float, float] | None:
    """Retorna coordenadas: dicionário estático → API IBGE → None."""
    # 1. Dicionário estático BR
    cidades_br = _coordenadas_cidades_br()
    if cidade in cidades_br and cidades_br[cidade]:
        return cidades_br[cidade]
    # 2. Dicionário PY/BO
    if cidade in CIDADES_PY_BO:
        return CIDADES_PY_BO[cidade]
    # 3. API Nominatim (para cidades não catalogadas)
    if estado and estado not in ("Paraguai", "Bolívia"):
        coord = _buscar_coord_ibge(cidade, estado)
        if coord:
            return coord
    return None


def _construir_mapa(df_terr: pd.DataFrame) -> go.Figure:
    """Constrói mapa interativo com os territórios usando plotly graph_objects."""

    # Monta lista de pontos
    rows_map = []

    if df_terr.empty:
        # Pontos dos 3 países para mostrar o mapa mesmo vazio
        rows_map = [
            {"lat": -15.0, "lon": -53.0, "Revenda": "🇧🇷 Brasil",
             "Cidade": "Brasil", "Estado": "BR", "Representante": ""},
            {"lat": -23.4, "lon": -58.4, "Revenda": "🇵🇾 Paraguai",
             "Cidade": "Paraguai", "Estado": "PY", "Representante": ""},
            {"lat": -16.5, "lon": -64.5, "Revenda": "🇧🇴 Bolívia",
             "Cidade": "Bolívia", "Estado": "BO", "Representante": ""},
        ]
    else:
        for _, row in df_terr.iterrows():
            cidade = str(row.get("Cidade", "")).strip()
            estado = str(row.get("Estado", "")).strip()
            coords = _get_coordenadas(cidade, estado)
            if coords:
                rows_map.append({
                    "lat": coords[0],
                    "lon": coords[1],
                    "Revenda": str(row.get("Revenda", "—")),
                    "Cidade": cidade,
                    "Estado": estado,
                    "Representante": str(row.get("Representante", "")),
                })

    if not rows_map:
        # Nenhuma coordenada encontrada — mostra aviso
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor="#12171D",
            plot_bgcolor="#12171D",
            height=300,
            annotations=[dict(
                text="⚠️ Nenhuma coordenada encontrada para as cidades cadastradas.<br>"
                     "Verifique se os nomes das cidades estão corretos.",
                x=0.5, y=0.5, xref="paper", yref="paper",
                font=dict(size=13, color="#E8A020"),
                showarrow=False,
            )]
        )
        return fig

    import pandas as _pd
    df_map = _pd.DataFrame(rows_map)

    # Mapa de cores por revenda
    revendas_unicas = df_map["Revenda"].unique().tolist()
    color_map = {r: CORES[i % len(CORES)] for i, r in enumerate(revendas_unicas)}
    df_map["cor"] = df_map["Revenda"].map(color_map)
    df_map["texto"] = df_map.apply(
        lambda r: f"<b>{r['Cidade']}</b><br>Revenda: {r['Revenda']}<br>"
                  f"Representante: {r['Representante']}<br>Estado: {r['Estado']}",
        axis=1
    )

    fig = go.Figure()

    for revenda in revendas_unicas:
        df_r = df_map[df_map["Revenda"] == revenda]
        cor  = color_map[revenda]
        fig.add_trace(go.Scattergeo(
            lat=df_r["lat"].tolist(),
            lon=df_r["lon"].tolist(),
            mode="markers",
            name=revenda[:30],
            marker=dict(size=11, color=cor, opacity=0.9,
                        line=dict(width=1, color="#12171D")),
            text=df_r["texto"].tolist(),
            hovertemplate="%{text}<extra></extra>",
        ))

    fig.update_layout(
        geo=dict(
            scope="south america",
            showland=True,      landcolor="#1E2A3A",
            showocean=True,     oceancolor="#0D1520",
            showcountries=True, countrycolor="#5A6A7A",
            showcoastlines=True,coastlinecolor="#5A6A7A",
            showsubunits=True,  subunitcolor="#3A4858",
            showlakes=False,
            bgcolor="#12171D",
            center=dict(lat=-25, lon=-52),
            projection_scale=3.5,
            lataxis=dict(range=[-34, -8]),
            lonaxis=dict(range=[-62, -42]),
        ),
        paper_bgcolor="#12171D",
        plot_bgcolor="#12171D",
        font=dict(color="#EEF2F8", family="Inter, sans-serif", size=11),
        margin=dict(l=0, r=0, t=10, b=0),
        height=580,
        showlegend=True,
        legend=dict(
            bgcolor="rgba(20,30,40,0.95)",
            bordercolor="#3A4858",
            borderwidth=1,
            font=dict(size=11, color="#EEF2F8"),
            x=0.01, y=0.99,
        ),
    )
    return fig


def _form_cadastro():
    """Formulário para cadastrar cidades de uma revenda."""
    st.markdown('<div class="terr-sec">➕ Cadastrar Cidade / Território</div>', unsafe_allow_html=True)

    with st.form("form_territorio", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            revenda = st.text_input("Revenda / Empresa", placeholder="Ex: PLANJO MAQUINAS AGRI")
            representante = st.text_input("Representante", placeholder="Ex: João Silva")
        with c2:
            cidade = st.text_input("Cidade", placeholder="Ex: Campos Novos")
            estado = st.selectbox("Estado / País", [
                "SC","RS","PR","SP","MG","RJ","ES","GO","MT","MS","DF",
                "BA","PE","CE","RN","PB","AL","SE","MA","PI",
                "PA","AM","RO","AC","RR","AP","TO",
                "Paraguai","Bolívia"
            ])
        obs = st.text_input("Observações (opcional)", placeholder="Ex: Microregião Campos Novos")

        salvar = st.form_submit_button("💾 Salvar", type="primary", use_container_width=True)

        if salvar:
            if not revenda.strip():
                st.toast("⚠️ Revenda é obrigatória.", icon="🚫")
            elif not cidade.strip():
                st.toast("⚠️ Cidade é obrigatória.", icon="🚫")
            else:
                reg = {
                    "Revenda": revenda.strip(),
                    "Representante": representante.strip(),
                    "Cidade": cidade.strip(),
                    "Estado": estado,
                    "Observacoes": obs.strip(),
                }
                if adicionar_territorio(reg):
                    st.toast(f"✅ {cidade} adicionada ao território de {revenda}!", icon="✅")
                    st.rerun()


def _tabela_territorios(df: pd.DataFrame):
    """Exibe e gerencia os territórios cadastrados."""
    if df.empty:
        st.info("Nenhum território cadastrado ainda.")
        return

    st.markdown('<div class="terr-sec">📋 Territórios Cadastrados</div>', unsafe_allow_html=True)

    # Filtro por revenda
    revendas = ["Todas"] + sorted(df["Revenda"].unique().tolist())
    filtro = st.selectbox("Filtrar por revenda", revendas, key="filtro_revenda_terr")
    if filtro != "Todas":
        df = df[df["Revenda"] == filtro]

    # Métricas
    c1, c2, c3 = st.columns(3)
    c1.metric("🏬 Revendas", df["Revenda"].nunique() if "Revenda" in df.columns else 0)
    c2.metric("👤 Representantes", df["Representante"].nunique() if "Representante" in df.columns else 0)
    c3.metric("📍 Cidades", len(df))

    st.divider()

    # Tabela com delete
    cols_w = [2.0, 1.5, 1.5, 0.8, 2.0, 0.4]
    hdr = st.columns(cols_w)
    for c, lbl in zip(hdr, ["Revenda", "Representante", "Cidade", "Estado", "Observações", ""]):
        c.markdown(f'<div style="font-size:10px;font-weight:700;color:#3A4858;text-transform:uppercase;">{lbl}</div>', unsafe_allow_html=True)

    for _, row in df.iterrows():
        row_id = int(row.get("id", 0))
        cols = st.columns(cols_w)
        cols[0].markdown(f'<div style="font-size:12px;color:#EEF2F8;padding-top:8px;font-weight:500;">{row.get("Revenda","—")}</div>', unsafe_allow_html=True)
        cols[1].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Representante","—")}</div>', unsafe_allow_html=True)
        cols[2].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Cidade","—")}</div>', unsafe_allow_html=True)
        cols[3].markdown(f'<div style="font-size:12px;color:#6A7A8A;padding-top:8px;">{row.get("Estado","—")}</div>', unsafe_allow_html=True)
        cols[4].markdown(f'<div style="font-size:11px;color:#6A7A8A;padding-top:8px;">{row.get("Observacoes","") or "—"}</div>', unsafe_allow_html=True)
        if cols[5].button("🗑", key=f"del_terr_{row_id}"):
            if excluir_territorio(row_id):
                st.toast("Removido.", icon="🗑")
                st.rerun()
        st.markdown('<div style="border-bottom:1px solid rgba(45,55,72,.5);margin:2px 0;"></div>', unsafe_allow_html=True)

    # Exportar
    csv = df.drop(columns=["id"], errors="ignore").to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button("📥 Exportar territórios (.csv)", data=csv,
                       file_name="territorios.csv", mime="text/csv", key="dl_terr")


def render_aba_territorios():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown("""
<div style="display:flex;align-items:center;gap:14px;padding:10px 0 18px;
            border-bottom:1px solid #2D3748;margin-bottom:24px;">
  <div style="background:rgba(52,183,120,.13);border:1px solid rgba(52,183,120,.4);
              border-radius:10px;padding:10px 14px;font-size:22px;">🗺️</div>
  <div>
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:1.9rem;
                font-weight:700;color:#F0F4F8;line-height:1.1;">
      Mapa de Territórios</div>
    <div style="font-size:12px;color:#6A7A8A;text-transform:uppercase;
                letter-spacing:.07em;margin-top:4px;">
      Cobertura de Revendas e Representantes · Brasil · Paraguai · Bolívia</div>
  </div>
</div>""", unsafe_allow_html=True)

    df_terr = ler_territorios()

    # Mapa
    st.plotly_chart(_construir_mapa(df_terr), use_container_width=True)

    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:18px 0;">', unsafe_allow_html=True)

    # Tabs: cadastro e lista
    tab_cad, tab_lista = st.tabs(["➕ Cadastrar Cidades", "📋 Ver Territórios"])

    with tab_cad:
        _form_cadastro()

        # Upload em lote
        st.markdown("---")
        st.markdown("**📤 Importar em lote (CSV)**")
        st.caption("CSV com colunas: Revenda, Representante, Cidade, Estado, Observacoes")
        up = st.file_uploader("Arquivo CSV", type=["csv"], key="up_terr", label_visibility="collapsed")
        if up:
            try:
                df_up = pd.read_csv(up, sep=None, engine="python")
                df_up.columns = [c.strip() for c in df_up.columns]
                n_ok = 0
                for _, row in df_up.iterrows():
                    reg = {
                        "Revenda":        str(row.get("Revenda","")).strip(),
                        "Representante":  str(row.get("Representante","")).strip(),
                        "Cidade":         str(row.get("Cidade","")).strip(),
                        "Estado":         str(row.get("Estado","")).strip(),
                        "Observacoes":    str(row.get("Observacoes","")).strip(),
                    }
                    if reg["Revenda"] and reg["Cidade"]:
                        if adicionar_territorio(reg):
                            n_ok += 1
                st.success(f"✅ {n_ok} cidades importadas!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")

    with tab_lista:
        _tabela_territorios(df_terr)
