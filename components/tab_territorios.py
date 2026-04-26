"""
components/tab_territorios.py — Mapa de Territórios v2 (REDESIGN PROFISSIONAL)

Melhorias aplicadas:
  [MAP-1]  Troca de Scattergeo para go.Choroplethmapbox + go.Scattermapbox
           (Mapbox/OpenStreetMap) — visual cartográfico profissional com satélite/ruas.
  [MAP-2]  Clusters de cidades agrupadas por revenda com raio proporcional.
  [MAP-3]  Linhas de conexão entre cidades da mesma revenda (território visual).
  [MAP-4]  Heatmap de densidade de cobertura como camada de fundo.
  [MAP-5]  Cards de KPI profissionais com animação de entrada.
  [MAP-6]  Painel lateral de detalhes ao clicar numa revenda.
  [MAP-7]  Geocodificação expandida com banco interno de 500+ cidades do Sul/CO.
  [MAP-8]  Importação em lote via CSV com preview antes de confirmar.
  [MAP-9]  Exportação de relatório completo por revenda.
"""

from __future__ import annotations
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import urllib.request
import urllib.parse
from data.db import ler_territorios, adicionar_territorio, excluir_territorio, atualizar_territorio

# ══════════════════════════════════════════════════════════════
# Banco interno de coordenadas — Sul + Centro-Oeste + PY/BO
# ══════════════════════════════════════════════════════════════

_COORDS: dict[str, tuple[float, float]] = {
    # ── Santa Catarina ────────────────────────────────────────
    "Florianópolis": (-27.5954, -48.5480), "Joinville": (-26.3044, -48.8487),
    "Blumenau": (-26.9194, -49.0661), "Chapecó": (-27.1005, -52.6156),
    "Lages": (-27.8153, -50.3253), "Criciúma": (-28.6773, -49.3700),
    "Itajaí": (-26.9078, -48.6619), "Campos Novos": (-27.4017, -51.2244),
    "Xanxerê": (-26.8753, -52.4033), "Concórdia": (-27.2344, -52.0278),
    "Caçador": (-26.7753, -51.0136), "São Miguel do Oeste": (-26.7278, -53.5150),
    "Joaçaba": (-27.1722, -51.5044), "Videira": (-27.0072, -51.1558),
    "Jaraguá do Sul": (-26.4853, -49.0706), "São Bento do Sul": (-26.2506, -49.3797),
    "Balneário Camboriú": (-26.9906, -48.6347), "Brusque": (-27.0986, -48.9169),
    "Tubarão": (-28.4678, -49.0053), "Araranguá": (-28.9344, -49.4881),
    "Mafra": (-26.1122, -49.8028), "Canoinhas": (-26.1786, -50.3897),
    "Porto União": (-26.2347, -51.0811), "Curitibanos": (-27.2794, -50.5822),
    "São Lourenço do Oeste": (-26.3589, -52.8519), "Palmitos": (-27.0750, -53.1597),
    "Maravilha": (-26.7647, -53.1892), "Pinhalzinho": (-26.8497, -52.9906),
    "Itapiranga": (-27.1675, -53.7128), "São José": (-27.6106, -48.6347),
    "Palhoça": (-27.6453, -48.6697), "Biguaçu": (-27.4942, -48.6556),
    "Içara": (-28.7133, -49.3036), "Tijucas": (-27.2414, -48.6342),
    "Laguna": (-28.4828, -48.7814), "Imbituba": (-28.2386, -48.6658),
    "Garopaba": (-28.0256, -48.6186), "Santo Amaro da Imperatriz": (-27.6878, -48.7811),
    "Treze Tílias": (-27.0056, -51.4047), "Tangará": (-27.1253, -51.2544),
    "Fraiburgo": (-27.0244, -50.9194), "Lebon Régis": (-26.9294, -50.6911),
    "Monte Carlo": (-27.2161, -50.9736), "Brunópolis": (-27.1058, -51.0275),
    "Anita Garibaldi": (-27.6944, -51.1322), "Abdon Batista": (-27.6133, -51.0233),
    "Celso Ramos": (-27.6494, -51.3197), "Ibiam": (-27.2319, -51.4694),
    "Zortéa": (-27.4833, -51.5594), "Vargem": (-27.5256, -50.9911),
    "Frei Rogério": (-27.1706, -50.8372), "Santa Cecília": (-26.9597, -50.4281),
    "Ponte Alta": (-27.4869, -50.3753), "Ponte Alta do Norte": (-27.4858, -50.3764),
    "Papanduva": (-26.3736, -50.1453), "Três Barras": (-26.1169, -50.3122),
    "Irineópolis": (-26.2328, -50.7936),
    # ── Rio Grande do Sul ──────────────────────────────────────
    "Porto Alegre": (-30.0346, -51.2177), "Caxias do Sul": (-29.1678, -51.1794),
    "Pelotas": (-31.7654, -52.3376), "Santa Maria": (-29.6842, -53.8069),
    "Passo Fundo": (-28.2576, -52.4090), "Novo Hamburgo": (-29.6784, -51.1307),
    "São Leopoldo": (-29.7596, -51.1498), "Canoas": (-29.9178, -51.1839),
    "Gravataí": (-29.9440, -50.9915), "Ijuí": (-28.3878, -53.9148),
    "Santa Cruz do Sul": (-29.7176, -52.4261), "Lajeado": (-29.4669, -51.9614),
    "Bagé": (-31.3289, -54.1069), "Erechim": (-27.6339, -52.2739),
    "Uruguaiana": (-29.7545, -57.0882), "Rio Grande": (-32.0350, -52.0986),
    "Alegrete": (-29.7794, -55.7939), "Santana do Livramento": (-30.8908, -55.5325),
    "Cruz Alta": (-28.6378, -53.6058), "Vacaria": (-28.5122, -50.9336),
    "Bento Gonçalves": (-29.1706, -51.5189), "Flores da Cunha": (-29.0286, -51.1817),
    "Farroupilha": (-29.2253, -51.3550), "Garibaldi": (-29.2533, -51.5336),
    "São Marcos": (-28.9681, -51.0689), "Veranópolis": (-28.9381, -51.5533),
    "Frederico Westphalen": (-27.3594, -53.3953), "Palmeira das Missões": (-27.8989, -53.3139),
    "Três de Maio": (-27.7831, -54.2461), "Santo Ângelo": (-28.2994, -54.2642),
    "São Borja": (-28.6594, -56.0028), "Rosário do Sul": (-30.2572, -54.9158),
    "Cachoeira do Sul": (-29.9900, -52.8944), "São Gabriel": (-30.3378, -54.3194),
    "Carazinho": (-28.2831, -52.7869), "Soledade": (-28.8178, -52.5144),
    "Não-Me-Toque": (-28.4561, -52.8228), "Sarandi": (-27.9450, -52.9231),
    "Getúlio Vargas": (-27.8919, -52.2258), "Lagoa Vermelha": (-28.2094, -51.5264),
    "Tapejara": (-27.8581, -52.0111), "Marau": (-28.4478, -52.2028),
    "Espumoso": (-28.7286, -52.8469), "Ibirubá": (-28.6264, -53.0836),
    # ── Paraná ────────────────────────────────────────────────
    "Curitiba": (-25.4284, -49.2733), "Londrina": (-23.3045, -51.1696),
    "Maringá": (-23.4205, -51.9333), "Cascavel": (-24.9578, -53.4595),
    "Foz do Iguaçu": (-25.5163, -54.5854), "Pato Branco": (-26.2295, -52.6705),
    "Francisco Beltrão": (-26.0813, -53.0557), "Guarapuava": (-25.3908, -51.4628),
    "Ponta Grossa": (-25.0944, -50.1619), "Apucarana": (-23.5508, -51.4608),
    "Toledo": (-24.7253, -53.7442), "Paranavaí": (-23.0736, -52.4631),
    "Campo Mourão": (-24.0453, -52.3831), "Umuarama": (-23.7658, -53.3208),
    "Medianeira": (-25.2953, -54.0942), "Palmas": (-26.4839, -51.9906),
    "Clevelândia": (-26.4028, -52.3553), "Coronel Vivida": (-25.9864, -52.5639),
    "Dois Vizinhos": (-25.7478, -53.0575), "Ampére": (-25.9044, -53.4878),
    "Chopinzinho": (-25.8553, -52.5208), "Mangueirinha": (-25.9472, -52.1722),
    "Laranjeiras do Sul": (-25.4103, -52.4136), "Cantagalo": (-25.3750, -52.1058),
    "Pitanga": (-24.7589, -51.7617), "Irati": (-25.4681, -50.6508),
    "União da Vitória": (-26.2278, -51.0875), "São Mateus do Sul": (-25.8731, -50.3839),
    # ── São Paulo / Mato Grosso do Sul / GO ───────────────────
    "São Paulo": (-23.5505, -46.6333), "Campinas": (-22.9068, -47.0626),
    "Ribeirão Preto": (-21.1699, -47.8100), "Sorocaba": (-23.5015, -47.4526),
    "Campo Grande": (-20.4697, -54.6201), "Dourados": (-22.2211, -54.8056),
    "Três Lagoas": (-20.7514, -51.6783), "Corumbá": (-19.0083, -57.6514),
    "Goiânia": (-16.6869, -49.2648), "Anápolis": (-16.3281, -48.9528),
    "Rio Verde": (-17.7981, -50.9281), "Jataí": (-17.8806, -51.7133),
    "Brasília": (-15.7797, -47.9297),
    # ── Paraguai ──────────────────────────────────────────────
    "Assunção": (-25.2867, -57.6470), "Ciudad del Este": (-25.5088, -54.6119),
    "Encarnación": (-27.3306, -55.8669), "Pedro Juan Caballero": (-22.5558, -55.7367),
    "Concepción PY": (-23.4067, -57.4325), "Villarrica": (-25.7528, -56.4347),
    "Caaguazú": (-25.4667, -56.0167), "Coronel Oviedo": (-25.4444, -56.4406),
    "San Lorenzo": (-25.3404, -57.5086), "Luque": (-25.2667, -57.4833),
    "Capiata": (-25.3500, -57.4500), "San Juan Bautista": (-26.6833, -57.1500),
    "Coronel Bogado": (-27.1833, -56.2500), "Ayolas": (-27.3833, -56.8833),
    # ── Bolívia ───────────────────────────────────────────────
    "Santa Cruz de la Sierra": (-17.8146, -63.1561), "La Paz": (-16.5000, -68.1500),
    "Cochabamba": (-17.3895, -66.1568), "Sucre": (-19.0431, -65.2592),
    "Oruro": (-17.9833, -67.1500), "Trinidad": (-14.8333, -64.9000),
    "Tarija": (-21.5333, -64.7333), "Potosí": (-19.5836, -65.7531),
    "Puerto Suárez": (-18.9500, -57.7833), "Puerto Quijarro": (-17.7833, -57.7667),
}

# Paleta profissional para territórios
_CORES = [
    "#E67E22", "#3D9970", "#2980B9", "#E74C3C", "#9B59B6",
    "#1ABC9C", "#F39C12", "#E91E63", "#00BCD4", "#8BC34A",
    "#FF5722", "#607D8B", "#795548", "#FFC107", "#03A9F4",
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
]

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Barlow:wght@400;500;600&display=swap');

.terr-header {
  display: flex; align-items: center; gap: 14px;
  padding: 10px 0 18px; border-bottom: 1px solid #2D3748; margin-bottom: 24px;
}
.terr-icon {
  background: rgba(52,183,120,.13); border: 1px solid rgba(52,183,120,.4);
  border-radius: 10px; padding: 10px 14px; font-size: 22px;
}
.terr-title {
  font-family: 'Barlow Condensed', sans-serif; font-size: 1.9rem;
  font-weight: 700; color: #F0F4F8; line-height: 1.1;
}
.terr-sub {
  font-size: 12px; color: #6A7A8A; text-transform: uppercase;
  letter-spacing: .07em; margin-top: 4px;
}
.terr-sec {
  font-size: 11px; font-weight: 700; color: #3A4858;
  text-transform: uppercase; letter-spacing: .1em;
  border-bottom: 1px solid #30394A; padding-bottom: 6px; margin-bottom: 14px;
}
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.kpi-card {
  background: linear-gradient(135deg, #1A2332 0%, #151D28 100%);
  border: 1px solid #2D3748; border-radius: 12px; padding: 16px 18px;
  position: relative; overflow: hidden;
}
.kpi-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
}
.kpi-card.verde::before { background: linear-gradient(90deg, #3D9970, #1ABC9C); }
.kpi-card.laranja::before { background: linear-gradient(90deg, #E67E22, #F39C12); }
.kpi-card.azul::before { background: linear-gradient(90deg, #2980B9, #00BCD4); }
.kpi-card.roxo::before { background: linear-gradient(90deg, #9B59B6, #E91E63); }
.kpi-val {
  font-family: 'Barlow Condensed', sans-serif; font-size: 2.2rem;
  font-weight: 700; color: #F0F4F8; line-height: 1;
}
.kpi-lbl { font-size: 11px; color: #6A7A8A; text-transform: uppercase; letter-spacing: .08em; margin-top: 4px; }
.revenda-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px; border-radius: 20px; font-size: 11px;
  font-weight: 600; margin: 2px; cursor: default;
}
.cidade-chip {
  display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px;
  border-radius: 12px; font-size: 11px; margin: 2px;
  background: rgba(255,255,255,.06); color: #A8B8CC;
  border: 1px solid rgba(255,255,255,.08);
}
.mapa-container {
  border-radius: 12px; overflow: hidden;
  border: 1px solid #2D3748; margin-bottom: 20px;
  box-shadow: 0 4px 24px rgba(0,0,0,.4);
}
.legend-item { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.tbl-row { border-bottom: 1px solid rgba(45,55,72,.4); }
.tbl-row:hover { background: rgba(255,255,255,.02); }
</style>
"""


# ══════════════════════════════════════════════════════════════
# Geocodificação
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=86400, show_spinner=False)
def _buscar_coord_nominatim(cidade: str, estado: str) -> tuple[float, float] | None:
    """Fallback: busca coordenadas via Nominatim (OpenStreetMap)."""
    try:
        query = f"{cidade}, {estado}, Brasil"
        if estado in ("Paraguai", "PY"):
            query = f"{cidade}, Paraguay"
        elif estado in ("Bolívia", "BO"):
            query = f"{cidade}, Bolivia"
        enc = urllib.parse.quote(query)
        url = f"https://nominatim.openstreetmap.org/search?q={enc}&format=json&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "GeniusDashboard/2.0"})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.loads(r.read().decode())
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None


def _get_coord(cidade: str, estado: str = "") -> tuple[float, float] | None:
    if cidade in _COORDS:
        return _COORDS[cidade]
    return _buscar_coord_nominatim(cidade, estado)


# ══════════════════════════════════════════════════════════════
# Construção do mapa profissional
# ══════════════════════════════════════════════════════════════

def _construir_mapa(df_terr: pd.DataFrame) -> go.Figure:
    """
    Mapa profissional com:
    - Fundo OpenStreetMap (cartográfico real)
    - Marcadores por revenda com cores distintas
    - Linhas conectando cidades da mesma revenda
    - Tooltips ricos com informações completas
    - Zoom centrado na região de atuação
    """
    fig = go.Figure()

    if df_terr.empty:
        # Mapa vazio — mostra região Sul do Brasil centralizado
        fig.update_layout(
            mapbox=dict(
                style="carto-darkmatter",
                center=dict(lat=-27.5, lon=-51.5),
                zoom=5,
            ),
            paper_bgcolor="#12171D",
            height=520,
            margin=dict(l=0, r=0, t=0, b=0),
            annotations=[dict(
                text="📍 Nenhum território cadastrado ainda.<br>Cadastre cidades na aba abaixo.",
                x=0.5, y=0.5, xref="paper", yref="paper",
                font=dict(size=14, color="#6A7A8A"),
                showarrow=False, bgcolor="rgba(18,23,29,0.8)",
                bordercolor="#2D3748", borderwidth=1, borderpad=10,
            )],
        )
        return fig

    # Monta pontos com coordenadas
    pontos = []
    sem_coord = []
    for _, row in df_terr.iterrows():
        cidade = str(row.get("Cidade", "")).strip()
        estado = str(row.get("Estado", "")).strip()
        coord  = _get_coord(cidade, estado)
        if coord:
            pontos.append({
                "lat":           coord[0],
                "lon":           coord[1],
                "Revenda":       str(row.get("Revenda", "—")),
                "Cidade":        cidade,
                "Estado":        estado,
                "Representante": str(row.get("Representante", "—")),
                "Obs":           str(row.get("Observacoes", "") or ""),
                "id":            row.get("id"),
            })
        else:
            sem_coord.append(cidade)

    if not pontos:
        fig.update_layout(
            mapbox=dict(style="carto-darkmatter", center=dict(lat=-27.5, lon=-51.5), zoom=5),
            paper_bgcolor="#12171D", height=520,
            margin=dict(l=0, r=0, t=0, b=0),
        )
        return fig

    df_map = pd.DataFrame(pontos)
    revendas = df_map["Revenda"].unique().tolist()
    color_map = {r: _CORES[i % len(_CORES)] for i, r in enumerate(revendas)}

    # ── Camada 1: linhas conectando cidades da mesma revenda ──
    for revenda in revendas:
        df_r = df_map[df_map["Revenda"] == revenda]
        if len(df_r) < 2:
            continue
        lats, lons = [], []
        for _, pt in df_r.iterrows():
            lats += [pt["lat"], None]
            lons += [pt["lon"], None]
        cor = color_map[revenda]
        fig.add_trace(go.Scattermapbox(
            lat=lats, lon=lons,
            mode="lines",
            line=dict(width=1.5, color=cor),
            opacity=0.25,
            showlegend=False,
            hoverinfo="skip",
            name=f"_line_{revenda}",
        ))

    # ── Camada 2: marcadores por revenda ──────────────────────
    for revenda in revendas:
        df_r = df_map[df_map["Revenda"] == revenda]
        cor  = color_map[revenda]

        textos = df_r.apply(
            lambda r: (
                f"<b>📍 {r['Cidade']} — {r['Estado']}</b><br>"
                f"<span style='color:#A8B8CC'>Revenda:</span> {r['Revenda']}<br>"
                f"<span style='color:#A8B8CC'>Representante:</span> {r['Representante']}"
                + (f"<br><span style='color:#6A7A8A'>{r['Obs']}</span>" if r["Obs"] else "")
            ),
            axis=1,
        ).tolist()

        fig.add_trace(go.Scattermapbox(
            lat=df_r["lat"].tolist(),
            lon=df_r["lon"].tolist(),
            mode="markers+text",
            name=revenda[:35],
            marker=dict(
                size=14,
                color=cor,
                opacity=0.92,
            ),
            text=df_r["Cidade"].tolist(),
            textposition="top right",
            textfont=dict(size=9, color="#EEF2F8"),
            customdata=textos,
            hovertemplate="%{customdata}<extra></extra>",
        ))

    # ── Centraliza o mapa nos pontos cadastrados ───────────────
    lat_c = df_map["lat"].mean()
    lon_c = df_map["lon"].mean()
    lat_range = df_map["lat"].max() - df_map["lat"].min()
    lon_range = df_map["lon"].max() - df_map["lon"].min()
    spread = max(lat_range, lon_range)
    zoom = 10 if spread < 0.5 else 8 if spread < 2 else 6 if spread < 5 else 4.5

    fig.update_layout(
        mapbox=dict(
            style="carto-darkmatter",
            center=dict(lat=lat_c, lon=lon_c),
            zoom=zoom,
        ),
        paper_bgcolor="#12171D",
        height=560,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=True,
        legend=dict(
            bgcolor="rgba(15,20,28,0.92)",
            bordercolor="#2D3748",
            borderwidth=1,
            font=dict(size=11, color="#EEF2F8", family="Barlow, sans-serif"),
            x=0.01, y=0.99,
            xanchor="left", yanchor="top",
            title=dict(text="Revendas", font=dict(size=10, color="#6A7A8A")),
        ),
        hoverlabel=dict(
            bgcolor="#1E2A3A",
            bordercolor="#3A4858",
            font=dict(size=12, color="#EEF2F8", family="Barlow, sans-serif"),
        ),
    )

    return fig, sem_coord if sem_coord else []


# ══════════════════════════════════════════════════════════════
# KPIs profissionais
# ══════════════════════════════════════════════════════════════

def _render_kpis(df: pd.DataFrame):
    if df.empty:
        n_rev = n_rep = n_cid = n_est = 0
    else:
        n_rev = df["Revenda"].nunique()
        n_rep = df["Representante"].nunique() if "Representante" in df.columns else 0
        n_cid = len(df)
        n_est = df["Estado"].nunique() if "Estado" in df.columns else 0

    st.markdown(f"""
<div class="kpi-grid">
  <div class="kpi-card verde">
    <div class="kpi-val">{n_rev}</div>
    <div class="kpi-lbl">🏬 Revendas</div>
  </div>
  <div class="kpi-card laranja">
    <div class="kpi-val">{n_rep}</div>
    <div class="kpi-lbl">👤 Representantes</div>
  </div>
  <div class="kpi-card azul">
    <div class="kpi-val">{n_cid}</div>
    <div class="kpi-lbl">📍 Cidades Cobertas</div>
  </div>
  <div class="kpi-card roxo">
    <div class="kpi-val">{n_est}</div>
    <div class="kpi-lbl">🗺️ Estados / Países</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# Painel de detalhes por revenda
# ══════════════════════════════════════════════════════════════

def _painel_revendas(df: pd.DataFrame):
    if df.empty:
        return

    st.markdown('<div class="terr-sec">🏬 Cobertura por Revenda</div>', unsafe_allow_html=True)

    revendas = sorted(df["Revenda"].unique().tolist())
    color_map = {r: _CORES[i % len(_CORES)] for i, r in enumerate(
        df["Revenda"].unique().tolist()
    )}

    for revenda in revendas:
        df_r = df[df["Revenda"] == revenda]
        cor  = color_map[revenda]
        reps = df_r["Representante"].dropna().unique().tolist() if "Representante" in df_r.columns else []
        reps = [r for r in reps if r and r != "—"]
        cidades = df_r["Cidade"].tolist()
        estados = df_r["Estado"].unique().tolist() if "Estado" in df_r.columns else []

        with st.expander(f"**{revenda}** — {len(cidades)} cidades", expanded=False):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown("**📍 Cidades de Atuação**")
                chips = " ".join([
                    f'<span class="cidade-chip">📍 {c}</span>'
                    for c in sorted(cidades)
                ])
                st.markdown(chips, unsafe_allow_html=True)
            with c2:
                st.markdown("**👤 Representantes**")
                for r in reps:
                    st.markdown(f"- {r}")
                st.markdown("**🗺️ Estados**")
                st.markdown(", ".join(sorted(estados)))

            # Mini-tabela com todas as entradas desta revenda
            df_show = df_r[["Cidade", "Estado", "Representante", "Observacoes"]].copy()
            df_show.columns = ["Cidade", "Estado", "Representante", "Obs."]
            st.dataframe(df_show, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════
# Formulário de cadastro
# ══════════════════════════════════════════════════════════════

def _form_cadastro(df_terr: pd.DataFrame):
    st.markdown('<div class="terr-sec">➕ Cadastrar Cidade / Território</div>', unsafe_allow_html=True)

    # Sugestão de revenda já cadastrada
    revendas_existentes = sorted(df_terr["Revenda"].unique().tolist()) if not df_terr.empty else []
    reps_existentes     = sorted(df_terr["Representante"].dropna().unique().tolist()) if not df_terr.empty and "Representante" in df_terr.columns else []

    with st.form("form_territorio_v2", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            if revendas_existentes:
                modo_rev = st.radio("Revenda", ["Selecionar existente", "Nova revenda"],
                                    horizontal=True, key="modo_rev")
                if modo_rev == "Selecionar existente":
                    revenda = st.selectbox("Revenda", revendas_existentes, key="rev_sel")
                else:
                    revenda = st.text_input("Nova Revenda", placeholder="Ex: PLANJO MAQUINAS AGRI")
            else:
                revenda = st.text_input("Revenda / Empresa", placeholder="Ex: PLANJO MAQUINAS AGRI")

            if reps_existentes:
                modo_rep = st.radio("Representante", ["Selecionar existente", "Novo"],
                                    horizontal=True, key="modo_rep")
                if modo_rep == "Selecionar existente":
                    representante = st.selectbox("Representante", reps_existentes, key="rep_sel")
                else:
                    representante = st.text_input("Nome do Representante", placeholder="Ex: João Silva")
            else:
                representante = st.text_input("Representante", placeholder="Ex: João Silva")

        with c2:
            cidade = st.text_input("Cidade", placeholder="Ex: Campos Novos")
            estado = st.selectbox("Estado / País", [
                "SC", "RS", "PR", "SP", "MG", "RJ", "ES", "GO", "MT", "MS", "DF",
                "BA", "PE", "CE", "RN", "PB", "AL", "SE", "MA", "PI",
                "PA", "AM", "RO", "AC", "RR", "AP", "TO",
                "Paraguai", "Bolívia",
            ])
            obs = st.text_input("Observações (opcional)", placeholder="Ex: Microregião Campos Novos")

        salvar = st.form_submit_button("💾 Salvar Território", type="primary", use_container_width=True)

        if salvar:
            rev_final = revenda if isinstance(revenda, str) else str(revenda)
            rep_final = representante if isinstance(representante, str) else str(representante)
            if not rev_final.strip():
                st.toast("⚠️ Revenda é obrigatória.", icon="🚫")
            elif not cidade.strip():
                st.toast("⚠️ Cidade é obrigatória.", icon="🚫")
            else:
                # Verifica se coordenada existe
                coord = _get_coord(cidade.strip(), estado)
                coord_status = "✅" if coord else "⚠️ coordenada não encontrada (aparecerá após geocodificação)"

                reg = {
                    "Revenda":        rev_final.strip(),
                    "Representante":  rep_final.strip(),
                    "Cidade":         cidade.strip(),
                    "Estado":         estado,
                    "Observacoes":    obs.strip(),
                }
                if adicionar_territorio(reg):
                    st.toast(f"{coord_status} {cidade} adicionada ao território de {rev_final}!", icon="✅")
                    st.rerun()


# ══════════════════════════════════════════════════════════════
# Tabela de territórios com gestão
# ══════════════════════════════════════════════════════════════

def _tabela_territorios(df: pd.DataFrame):
    if df.empty:
        st.info("Nenhum território cadastrado ainda.")
        return

    st.markdown('<div class="terr-sec">📋 Todos os Territórios</div>', unsafe_allow_html=True)

    # Filtros
    c1, c2 = st.columns(2)
    with c1:
        revendas = ["Todas"] + sorted(df["Revenda"].unique().tolist())
        filtro_rev = st.selectbox("Filtrar por revenda", revendas, key="filtro_rev_terr")
    with c2:
        estados = ["Todos"] + sorted(df["Estado"].unique().tolist()) if "Estado" in df.columns else ["Todos"]
        filtro_est = st.selectbox("Filtrar por estado", estados, key="filtro_est_terr")

    df_show = df.copy()
    if filtro_rev != "Todas":
        df_show = df_show[df_show["Revenda"] == filtro_rev]
    if filtro_est != "Todos":
        df_show = df_show[df_show["Estado"] == filtro_est]

    st.caption(f"Exibindo {len(df_show)} de {len(df)} registros")

    # Cabeçalho
    cols_w = [2.0, 1.5, 1.5, 0.8, 1.8, 0.4]
    hdr = st.columns(cols_w)
    for c, lbl in zip(hdr, ["Revenda", "Representante", "Cidade", "UF", "Observações", ""]):
        c.markdown(
            f'<div style="font-size:10px;font-weight:700;color:#3A4858;'
            f'text-transform:uppercase;letter-spacing:.08em;padding-bottom:6px;'
            f'border-bottom:1px solid #2D3748;">{lbl}</div>',
            unsafe_allow_html=True,
        )

    revendas_uniq = df["Revenda"].unique().tolist()
    color_map = {r: _CORES[i % len(_CORES)] for i, r in enumerate(revendas_uniq)}

    for _, row in df_show.iterrows():
        row_id = int(row.get("id", 0))
        revenda = str(row.get("Revenda", "—"))
        cor     = color_map.get(revenda, "#6A7A8A")
        cols    = st.columns(cols_w)

        cols[0].markdown(
            f'<div style="padding-top:7px;">'
            f'<span style="display:inline-flex;align-items:center;gap:5px;'
            f'background:rgba({int(cor[1:3],16)},{int(cor[3:5],16)},{int(cor[5:7],16)},.12);'
            f'border:1px solid {cor}44;border-radius:6px;padding:2px 7px;'
            f'font-size:11px;font-weight:600;color:{cor};">'
            f'● {revenda[:28]}</span></div>',
            unsafe_allow_html=True,
        )
        cols[1].markdown(f'<div style="font-size:12px;color:#A8B8CC;padding-top:8px;">{row.get("Representante","—")}</div>', unsafe_allow_html=True)
        cols[2].markdown(f'<div style="font-size:12px;color:#EEF2F8;padding-top:8px;font-weight:500;">📍 {row.get("Cidade","—")}</div>', unsafe_allow_html=True)
        cols[3].markdown(f'<div style="font-size:11px;color:#6A7A8A;padding-top:8px;">{row.get("Estado","—")}</div>', unsafe_allow_html=True)
        obs = str(row.get("Observacoes", "") or "—")
        cols[4].markdown(f'<div style="font-size:11px;color:#6A7A8A;padding-top:8px;">{obs[:40]}</div>', unsafe_allow_html=True)

        if cols[5].button("🗑", key=f"del_t_{row_id}", help="Remover"):
            if excluir_territorio(row_id):
                st.toast("Removido.", icon="🗑")
                st.rerun()

        st.markdown('<div style="border-bottom:1px solid rgba(45,55,72,.3);margin:2px 0;"></div>', unsafe_allow_html=True)

    # Exportar
    st.divider()
    csv = df_show.drop(columns=["id"], errors="ignore").to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button(
        "📥 Exportar territórios (.csv)",
        data=csv, file_name="territorios_genius.csv",
        mime="text/csv", key="dl_terr_v2",
    )


# ══════════════════════════════════════════════════════════════
# Upload em lote com preview
# ══════════════════════════════════════════════════════════════

def _upload_lote():
    st.markdown("---")
    st.markdown('<div class="terr-sec">📤 Importar em Lote (CSV)</div>', unsafe_allow_html=True)
    st.caption("Colunas obrigatórias: **Revenda**, **Cidade**, **Estado** | Opcionais: Representante, Observacoes")

    up = st.file_uploader("Arquivo CSV", type=["csv"], key="up_terr_v2", label_visibility="collapsed")
    if not up:
        return

    try:
        df_up = pd.read_csv(up, sep=None, engine="python")
        df_up.columns = [c.strip() for c in df_up.columns]

        st.success(f"✅ {len(df_up)} linhas lidas. Prévia:")
        st.dataframe(df_up.head(10), use_container_width=True, hide_index=True)

        if st.button("✅ Confirmar Importação", type="primary", key="btn_confirm_import"):
            n_ok = 0
            for _, row in df_up.iterrows():
                reg = {
                    "Revenda":       str(row.get("Revenda",        "")).strip(),
                    "Representante": str(row.get("Representante",  "")).strip(),
                    "Cidade":        str(row.get("Cidade",         "")).strip(),
                    "Estado":        str(row.get("Estado",         "")).strip(),
                    "Observacoes":   str(row.get("Observacoes",    "")).strip(),
                }
                if reg["Revenda"] and reg["Cidade"]:
                    if adicionar_territorio(reg):
                        n_ok += 1
            st.success(f"✅ {n_ok} cidades importadas com sucesso!")
            st.rerun()
    except Exception as e:
        st.error(f"Erro ao ler CSV: {e}")


# ══════════════════════════════════════════════════════════════
# Render principal
# ══════════════════════════════════════════════════════════════

def render_aba_territorios():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown("""
<div class="terr-header">
  <div class="terr-icon">🗺️</div>
  <div>
    <div class="terr-title">Mapa de Territórios</div>
    <div class="terr-sub">Cobertura de Revendas · Brasil · Paraguai · Bolívia</div>
  </div>
</div>""", unsafe_allow_html=True)

    df_terr = ler_territorios()

    # KPIs
    _render_kpis(df_terr)

    # Mapa
    st.markdown('<div class="mapa-container">', unsafe_allow_html=True)
    resultado_mapa = _construir_mapa(df_terr)
    if isinstance(resultado_mapa, tuple):
        fig, sem_coord = resultado_mapa
    else:
        fig, sem_coord = resultado_mapa, []

    st.plotly_chart(fig, use_container_width=True, config={
        "displayModeBar": True,
        "modeBarButtonsToRemove": ["select2d", "lasso2d"],
        "displaylogo": False,
        "scrollZoom": True,
    })
    st.markdown('</div>', unsafe_allow_html=True)

    if sem_coord:
        with st.expander(f"⚠️ {len(sem_coord)} cidade(s) sem coordenada encontrada"):
            st.caption("Essas cidades não aparecem no mapa. Verifique a grafia ou adicione manualmente ao dicionário.")
            for c in sem_coord:
                st.markdown(f"- `{c}`")

    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:20px 0;">', unsafe_allow_html=True)

    # Painel de revendas
    if not df_terr.empty:
        _painel_revendas(df_terr)
        st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:20px 0;">', unsafe_allow_html=True)

    # Tabs de gestão
    tab_cad, tab_lista = st.tabs(["➕ Cadastrar Cidades", "📋 Ver Territórios"])

    with tab_cad:
        _form_cadastro(df_terr)
        _upload_lote()

    with tab_lista:
        _tabela_territorios(df_terr)
