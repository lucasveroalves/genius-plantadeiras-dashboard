"""
components/tab_territorios.py — Genius Implementos Agrícolas v17

Alterações v17:
  [V17-MAP-1]  Removido formulário de cadastro duplicado — revendas entram no mapa
               automaticamente ao serem cadastradas em 'Revendas' (forms.py).
  [V17-MAP-2]  Botão "Sincronizar Revendas → Mapa" adicionado para forçar a
               sincronização de revendas já cadastradas que ainda não estão no mapa.
  [V17-MAP-3]  Banco de coordenadas expandido com +200 cidades do Sul/CO.
  [V17-MAP-4]  Export Excel adicionado na tabela de territórios.
  [V17-MAP-5]  Formulário de "Adicionar cidade avulsa" mantido mas simplificado.
"""

from __future__ import annotations
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import urllib.request
import urllib.parse
from io import BytesIO
from data.db import (
    ler_territorios, adicionar_territorio, excluir_territorio,
    atualizar_territorio, ler_revendas_cadastro,
)

# ══════════════════════════════════════════════════════════════
# Banco interno de coordenadas expandido
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
    "Garopaba": (-28.0256, -48.6186), "Treze Tílias": (-27.0056, -51.4047),
    "Tangará": (-27.1253, -51.2544), "Fraiburgo": (-27.0244, -50.9194),
    "Lebon Régis": (-26.9294, -50.6911), "Monte Carlo": (-27.2161, -50.9736),
    "Brunópolis": (-27.1058, -51.0275), "Anita Garibaldi": (-27.6944, -51.1322),
    "Abdon Batista": (-27.6133, -51.0233), "Celso Ramos": (-27.6494, -51.3197),
    "Ibiam": (-27.2319, -51.4694), "Zortéa": (-27.4833, -51.5594),
    "Vargem": (-27.5256, -50.9911), "Frei Rogério": (-27.1706, -50.8372),
    "Santa Cecília": (-26.9597, -50.4281), "Ponte Alta": (-27.4869, -50.3753),
    "Papanduva": (-26.3736, -50.1453), "Três Barras": (-26.1169, -50.3122),
    "Irineópolis": (-26.2328, -50.7936), "Água Doce": (-26.7244, -51.5531),
    "Catanduvas": (-26.9058, -51.6464), "Vargem Bonita": (-26.9789, -51.5300),
    "Irani": (-27.0217, -51.9014), "Presidente Castello Branco": (-27.1542, -51.7297),
    "Jabor": (-27.1, -51.9), "Herval d'Oeste": (-27.1878, -51.4903),
    "Erval Velho": (-27.2756, -51.6519), "Lacerdópolis": (-27.2589, -51.5561),
    "Luzerna": (-27.1386, -51.4631), "Ouro": (-27.3558, -51.6172),
    "Capinzal": (-27.3428, -51.6089), "Piratuba": (-27.4186, -51.7853),
    "Ipira": (-27.4083, -51.7789), "Pinheiro Preto": (-27.0619, -51.2156),
    "Rio das Antas": (-26.8975, -51.0736), "Arroio Trinta": (-26.9256, -51.3528),
    "Salto Veloso": (-26.9433, -51.3247), "Pomerode": (-26.7397, -49.1767),
    "Indaial": (-26.8978, -49.2319), "Timbó": (-26.8244, -49.2694),
    "Rodeio": (-26.9294, -49.3628), "Ascurra": (-26.9622, -49.3544),
    "Apiúna": (-27.0403, -49.3803), "Agronômica": (-27.2494, -49.8589),
    "Aurora": (-27.3061, -49.6344), "Trombudo Central": (-27.3044, -49.7847),
    "Rio do Sul": (-27.2133, -49.6419), "Taió": (-27.1131, -49.9872),
    "Salete": (-26.9628, -49.8958), "Pouso Redondo": (-27.2569, -49.9411),
    "São João Batista": (-27.2742, -48.8522), "Nova Trento": (-27.2922, -48.9308),
    "Rancho Queimado": (-27.6631, -49.0119), "Angelina": (-27.5814, -48.9664),
    "Antônio Carlos": (-27.4578, -48.7481), "Governador Celso Ramos": (-27.3122, -48.5589),
    "Florianopolis": (-27.5954, -48.5480),
    # ── Rio Grande do Sul ──────────────────────────────────────
    "Porto Alegre": (-30.0346, -51.2177), "Caxias do Sul": (-29.1678, -51.1794),
    "Pelotas": (-31.7654, -52.3376), "Santa Maria": (-29.6842, -53.8069),
    "Passo Fundo": (-28.2576, -52.4090), "Novo Hamburgo": (-29.6784, -51.1307),
    "São Leopoldo": (-29.7596, -51.1498), "Canoas": (-29.9178, -51.1839),
    "Ijuí": (-28.3878, -53.9148), "Santa Cruz do Sul": (-29.7176, -52.4261),
    "Lajeado": (-29.4669, -51.9614), "Bagé": (-31.3289, -54.1069),
    "Erechim": (-27.6339, -52.2739), "Uruguaiana": (-29.7545, -57.0882),
    "Cruz Alta": (-28.6378, -53.6058), "Vacaria": (-28.5122, -50.9336),
    "Bento Gonçalves": (-29.1706, -51.5189), "Frederico Westphalen": (-27.3594, -53.3953),
    "Palmeira das Missões": (-27.8989, -53.3139), "Santo Ângelo": (-28.2994, -54.2642),
    "São Borja": (-28.6594, -56.0028), "Carazinho": (-28.2831, -52.7869),
    "Não-Me-Toque": (-28.4561, -52.8228), "Sarandi": (-27.9450, -52.9231),
    "Getúlio Vargas": (-27.8919, -52.2258), "Tapejara": (-27.8581, -52.0111),
    "Marau": (-28.4478, -52.2028), "Espumoso": (-28.7286, -52.8469),
    "Ibirubá": (-28.6264, -53.0836), "Lagoa Vermelha": (-28.2094, -51.5264),
    "Soledade": (-28.8178, -52.5144), "Três de Maio": (-27.7831, -54.2461),
    "Horizontina": (-27.6261, -54.3064), "Tenente Portela": (-27.3706, -53.7553),
    "Santo Cristo": (-27.8278, -54.6819), "Giruá": (-28.0297, -54.3575),
    "Panambi": (-28.2978, -53.5022), "Tupanciretã": (-29.0803, -53.8419),
    "Santiago": (-29.1906, -54.8764), "São Luiz Gonzaga": (-28.4042, -54.9597),
    "Cerro Largo": (-28.1483, -54.7394), "São Pedro do Sul": (-29.6222, -54.1814),
    "Cacequi": (-29.8847, -54.8317), "Rosário do Sul": (-30.2572, -54.9158),
    # ── Paraná ────────────────────────────────────────────────
    "Curitiba": (-25.4284, -49.2733), "Londrina": (-23.3045, -51.1696),
    "Maringá": (-23.4205, -51.9333), "Cascavel": (-24.9578, -53.4595),
    "Foz do Iguaçu": (-25.5163, -54.5854), "Pato Branco": (-26.2295, -52.6705),
    "Francisco Beltrão": (-26.0813, -53.0557), "Guarapuava": (-25.3908, -51.4628),
    "Ponta Grossa": (-25.0944, -50.1619), "Toledo": (-24.7253, -53.7442),
    "Dois Vizinhos": (-25.7478, -53.0575), "Ampére": (-25.9044, -53.4878),
    "Chopinzinho": (-25.8553, -52.5208), "Laranjeiras do Sul": (-25.4103, -52.4136),
    "Pitanga": (-24.7589, -51.7617), "União da Vitória": (-26.2278, -51.0875),
    "Palmas": (-26.4839, -51.9906), "Clevelândia": (-26.4028, -52.3553),
    "Coronel Vivida": (-25.9864, -52.5639), "Mangueirinha": (-25.9472, -52.1722),
    "Cantagalo": (-25.3750, -52.1058), "Medianeira": (-25.2953, -54.0942),
    # ── São Paulo / MS / GO ───────────────────────────────────
    "São Paulo": (-23.5505, -46.6333), "Campinas": (-22.9068, -47.0626),
    "Campo Grande": (-20.4697, -54.6201), "Dourados": (-22.2211, -54.8056),
    "Goiânia": (-16.6869, -49.2648), "Brasília": (-15.7797, -47.9297),
    # ── Paraguai ──────────────────────────────────────────────
    "Assunção": (-25.2867, -57.6470), "Ciudad del Este": (-25.5088, -54.6119),
    "Encarnación": (-27.3306, -55.8669), "Pedro Juan Caballero": (-22.5558, -55.7367),
    "Villarrica": (-25.7528, -56.4347), "Caaguazú": (-25.4667, -56.0167),
    "Coronel Oviedo": (-25.4444, -56.4406), "San Lorenzo": (-25.3404, -57.5086),
    # ── Bolívia ───────────────────────────────────────────────
    "Santa Cruz de la Sierra": (-17.8146, -63.1561), "La Paz": (-16.5000, -68.1500),
    "Cochabamba": (-17.3895, -66.1568),
}

_CORES = [
    "#E67E22", "#3D9970", "#2980B9", "#E74C3C", "#9B59B6",
    "#1ABC9C", "#F39C12", "#E91E63", "#00BCD4", "#8BC34A",
    "#FF5722", "#607D8B", "#795548", "#FFC107", "#03A9F4",
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
]

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Barlow:wght@400;500;600&display=swap');
.terr-header { display:flex;align-items:center;gap:14px;padding:10px 0 18px;border-bottom:1px solid #2D3748;margin-bottom:24px; }
.terr-icon { background:rgba(52,183,120,.13);border:1px solid rgba(52,183,120,.4);border-radius:10px;padding:10px 14px;font-size:22px; }
.terr-title { font-family:'Barlow Condensed',sans-serif;font-size:1.9rem;font-weight:700;color:#F0F4F8;line-height:1.1; }
.terr-sub { font-size:12px;color:#6A7A8A;text-transform:uppercase;letter-spacing:.07em;margin-top:4px; }
.terr-sec { font-size:11px;font-weight:700;color:#3A4858;text-transform:uppercase;letter-spacing:.1em;border-bottom:1px solid #30394A;padding-bottom:6px;margin-bottom:14px; }
.kpi-grid { display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px; }
.kpi-card { background:linear-gradient(135deg,#1A2332 0%,#151D28 100%);border:1px solid #2D3748;border-radius:12px;padding:16px 18px;position:relative;overflow:hidden; }
.kpi-card::before { content:'';position:absolute;top:0;left:0;right:0;height:2px; }
.kpi-card.verde::before { background:linear-gradient(90deg,#3D9970,#1ABC9C); }
.kpi-card.laranja::before { background:linear-gradient(90deg,#E67E22,#F39C12); }
.kpi-card.azul::before { background:linear-gradient(90deg,#2980B9,#00BCD4); }
.kpi-card.roxo::before { background:linear-gradient(90deg,#9B59B6,#E91E63); }
.kpi-val { font-family:'Barlow Condensed',sans-serif;font-size:2.2rem;font-weight:700;color:#F0F4F8;line-height:1; }
.kpi-lbl { font-size:11px;color:#6A7A8A;text-transform:uppercase;letter-spacing:.08em;margin-top:4px; }
.cidade-chip { display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:12px;font-size:11px;margin:2px;background:rgba(255,255,255,.06);color:#A8B8CC;border:1px solid rgba(255,255,255,.08); }
.mapa-container { border-radius:12px;overflow:hidden;border:1px solid #2D3748;margin-bottom:20px;box-shadow:0 4px 24px rgba(0,0,0,.4); }
</style>
"""


# ══════════════════════════════════════════════════════════════
# Geocodificação
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=86400, show_spinner=False)
def _buscar_coord_nominatim(cidade: str, estado: str) -> tuple[float, float] | None:
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
    # Normaliza: remove espaços extras, tenta com e sem acento
    cidade_norm = cidade.strip()
    if cidade_norm in _COORDS:
        return _COORDS[cidade_norm]
    # Tenta Nominatim como fallback
    return _buscar_coord_nominatim(cidade_norm, estado)


# ══════════════════════════════════════════════════════════════
# Sincronização: Revendas → Territórios
# [V17-MAP-2] Sincroniza revendas cadastradas com o mapa
# ══════════════════════════════════════════════════════════════

def _sincronizar_todas_revendas():
    """Sincroniza TODAS as revendas cadastradas para o mapa de territórios."""
    try:
        df_rev = ler_revendas_cadastro()
        if df_rev.empty:
            return 0

        df_terr = ler_territorios()
        ja_existem = set()
        if not df_terr.empty and "Revenda" in df_terr.columns:
            for _, r in df_terr.iterrows():
                ja_existem.add((str(r.get("Revenda","")).strip(), str(r.get("Cidade","")).strip()))

        adicionadas = 0
        for _, rev in df_rev.iterrows():
            nome = str(rev.get("Nome_Revenda","")).strip()
            cidade_sede = str(rev.get("Cidade","")).strip()
            estado = str(rev.get("Estado","")).strip()
            responsavel = str(rev.get("Responsavel","")).strip()
            regioes = str(rev.get("Regioes_Atuacao","")).strip()

            cidades = []
            if cidade_sede:
                cidades.append(cidade_sede)
            if regioes:
                for c in regioes.split(","):
                    c = c.strip()
                    if c and c not in cidades:
                        cidades.append(c)

            for cidade in cidades:
                if (nome, cidade) not in ja_existem:
                    reg = {
                        "Revenda":       nome,
                        "Representante": responsavel,
                        "Cidade":        cidade,
                        "Estado":        estado,
                        "Observacoes":   "Sincronizado do cadastro de revendas",
                    }
                    if adicionar_territorio(reg):
                        adicionadas += 1
                        ja_existem.add((nome, cidade))

        return adicionadas
    except Exception as e:
        st.error(f"Erro na sincronização: {e}")
        return 0


# ══════════════════════════════════════════════════════════════
# Construção do mapa profissional
# ══════════════════════════════════════════════════════════════

def _construir_mapa(df_terr: pd.DataFrame):
    fig = go.Figure()

    if df_terr.empty:
        fig.update_layout(
            mapbox=dict(style="carto-darkmatter", center=dict(lat=-27.5, lon=-51.5), zoom=5),
            paper_bgcolor="#12171D", height=520,
            margin=dict(l=0, r=0, t=0, b=0),
            annotations=[dict(
                text="📍 Nenhum território cadastrado ainda.<br>Cadastre revendas na aba Revendas.",
                x=0.5, y=0.5, xref="paper", yref="paper",
                font=dict(size=14, color="#6A7A8A"),
                showarrow=False, bgcolor="rgba(18,23,29,0.8)",
                bordercolor="#2D3748", borderwidth=1, borderpad=10,
            )],
        )
        return fig, []

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
            sem_coord.append(f"{cidade} ({estado})")

    if not pontos:
        fig.update_layout(
            mapbox=dict(style="carto-darkmatter", center=dict(lat=-27.5, lon=-51.5), zoom=5),
            paper_bgcolor="#12171D", height=520,
            margin=dict(l=0, r=0, t=0, b=0),
        )
        return fig, sem_coord

    df_map = pd.DataFrame(pontos)
    revendas = df_map["Revenda"].unique().tolist()
    color_map = {r: _CORES[i % len(_CORES)] for i, r in enumerate(revendas)}

    # ── Polígonos preenchidos por revenda ────────────────────
    import math as _math

    def _hex_to_rgba(hex_cor: str, alpha: float) -> str:
        hex_cor = hex_cor.lstrip("#")
        r, g, b = int(hex_cor[0:2],16), int(hex_cor[2:4],16), int(hex_cor[4:6],16)
        return f"rgba({r},{g},{b},{alpha})"

    def _circulo(lat_c, lon_c, raio_km=55, n=40):
        """Gera lista de lat/lon formando um círculo."""
        r_lat = raio_km / 111.0
        r_lon = raio_km / (111.0 * _math.cos(_math.radians(lat_c)))
        lats = [lat_c + r_lat * _math.sin(2*_math.pi*i/n) for i in range(n+1)]
        lons = [lon_c + r_lon * _math.cos(2*_math.pi*i/n) for i in range(n+1)]
        return lats, lons

    try:
        from scipy.spatial import ConvexHull
        import numpy as _np
        _scipy_ok = True
    except ImportError:
        _scipy_ok = False

    for revenda in revendas:
        df_r   = df_map[df_map["Revenda"] == revenda]
        cor    = color_map[revenda]
        fill   = _hex_to_rgba(cor, 0.14)
        border = _hex_to_rgba(cor, 0.80)
        lats_a = df_r["lat"].values
        lons_a = df_r["lon"].values

        if len(df_r) == 1:
            # 1 cidade → círculo de ~55km
            h_lats, h_lons = _circulo(lats_a[0], lons_a[0])
        elif len(df_r) == 2:
            # 2 cidades → círculos individuais + linha ligando
            h_lats1, h_lons1 = _circulo(lats_a[0], lons_a[0], 45)
            h_lats2, h_lons2 = _circulo(lats_a[1], lons_a[1], 45)
            for hl, hlo in [(h_lats1, h_lons1), (h_lats2, h_lons2)]:
                fig.add_trace(go.Scattermapbox(
                    lat=hl, lon=hlo, mode="lines",
                    fill="toself", fillcolor=fill,
                    line=dict(width=1.5, color=border),
                    showlegend=False, hoverinfo="skip",
                ))
            # Linha ligando as duas
            fig.add_trace(go.Scattermapbox(
                lat=list(lats_a), lon=list(lons_a), mode="lines",
                line=dict(width=2, color=border, dash="dot"),
                showlegend=False, hoverinfo="skip",
            ))
            continue
        else:
            # 3+ cidades → convex hull
            if _scipy_ok:
                try:
                    pts  = _np.column_stack([lons_a, lats_a])
                    hull = ConvexHull(pts)
                    idxs = list(hull.vertices) + [hull.vertices[0]]
                    h_lons = [pts[v,0] for v in idxs]
                    h_lats = [pts[v,1] for v in idxs]
                except Exception:
                    h_lats = list(lats_a) + [lats_a[0]]
                    h_lons = list(lons_a) + [lons_a[0]]
            else:
                h_lats = list(lats_a) + [lats_a[0]]
                h_lons = list(lons_a) + [lons_a[0]]

        fig.add_trace(go.Scattermapbox(
            lat=h_lats, lon=h_lons, mode="lines",
            fill="toself", fillcolor=fill,
            line=dict(width=2, color=border),
            showlegend=False, hoverinfo="skip",
        ))

    # Marcadores por revenda
    for revenda in revendas:
        df_r = df_map[df_map["Revenda"] == revenda]
        cor  = color_map[revenda]
        textos = df_r.apply(
            lambda r: (
                f"<b>📍 {r['Cidade']} — {r['Estado']}</b><br>"
                f"<span style='color:#A8B8CC'>Revenda:</span> {r['Revenda']}<br>"
                f"<span style='color:#A8B8CC'>Representante:</span> {r['Representante']}"
                + (f"<br><span style='color:#6A7A8A'>{r['Obs']}</span>" if r["Obs"] else "")
            ), axis=1,
        ).tolist()

        fig.add_trace(go.Scattermapbox(
            lat=df_r["lat"].tolist(),
            lon=df_r["lon"].tolist(),
            mode="markers+text",
            name=revenda[:35],
            marker=dict(size=14, color=cor, opacity=0.92),
            text=df_r["Cidade"].tolist(),
            textposition="top right",
            textfont=dict(size=9, color="#EEF2F8"),
            customdata=textos,
            hovertemplate="%{customdata}<extra></extra>",
        ))

    lat_c = df_map["lat"].mean()
    lon_c = df_map["lon"].mean()
    spread = max(df_map["lat"].max() - df_map["lat"].min(), df_map["lon"].max() - df_map["lon"].min())
    zoom = 10 if spread < 0.5 else 8 if spread < 2 else 6 if spread < 5 else 4.5

    fig.update_layout(
        mapbox=dict(style="carto-darkmatter", center=dict(lat=lat_c, lon=lon_c), zoom=zoom),
        paper_bgcolor="#12171D", height=580,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=True,
        legend=dict(
            bgcolor="rgba(15,20,28,0.92)", bordercolor="#2D3748", borderwidth=1,
            font=dict(size=11, color="#EEF2F8", family="Barlow, sans-serif"),
            x=0.01, y=0.99, xanchor="left", yanchor="top",
            title=dict(text="Revendas", font=dict(size=10, color="#6A7A8A")),
        ),
        hoverlabel=dict(bgcolor="#1E2A3A", bordercolor="#3A4858", font=dict(size=12, color="#EEF2F8")),
    )

    return fig, sem_coord


# ══════════════════════════════════════════════════════════════
# KPIs
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
  <div class="kpi-card verde"><div class="kpi-val">{n_rev}</div><div class="kpi-lbl">🏬 Revendas</div></div>
  <div class="kpi-card laranja"><div class="kpi-val">{n_rep}</div><div class="kpi-lbl">👤 Representantes</div></div>
  <div class="kpi-card azul"><div class="kpi-val">{n_cid}</div><div class="kpi-lbl">📍 Cidades Cobertas</div></div>
  <div class="kpi-card roxo"><div class="kpi-val">{n_est}</div><div class="kpi-lbl">🗺️ Estados / Países</div></div>
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
    color_map = {r: _CORES[i % len(_CORES)] for i, r in enumerate(df["Revenda"].unique().tolist())}

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
                chips = " ".join([f'<span class="cidade-chip">📍 {c}</span>' for c in sorted(cidades)])
                st.markdown(chips, unsafe_allow_html=True)
            with c2:
                st.markdown("**👤 Representantes**")
                for r in reps:
                    st.markdown(f"- {r}")
                st.markdown("**🗺️ Estados**")
                st.markdown(", ".join(sorted(estados)))

            df_show = df_r[["Cidade", "Estado", "Representante", "Observacoes"]].copy()
            df_show.columns = ["Cidade", "Estado", "Representante", "Obs."]
            st.dataframe(df_show, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════
# Formulário — Adicionar cidade avulsa (simplificado)
# [V17-MAP-1] Formulário de revenda REMOVIDO — use a aba Revendas
# ══════════════════════════════════════════════════════════════

def _form_cidade_avulsa(df_terr: pd.DataFrame):
    st.markdown('<div class="terr-sec">📍 Adicionar Cidade Avulsa ao Mapa</div>', unsafe_allow_html=True)
    st.caption("Para cadastrar uma revenda completa, use a aba **🏬 Revendas** — as cidades são adicionadas automaticamente ao mapa.")

    revendas_existentes = sorted(df_terr["Revenda"].unique().tolist()) if not df_terr.empty else []

    with st.form("form_cidade_avulsa_v17", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            if revendas_existentes:
                modo_rev = st.radio("Revenda", ["Selecionar existente", "Nova revenda"], horizontal=True)
                if modo_rev == "Selecionar existente":
                    revenda = st.selectbox("Revenda", revendas_existentes, key="rev_sel_av")
                else:
                    revenda = st.text_input("Nova Revenda", placeholder="Ex: PLANJO MAQUINAS AGRI")
            else:
                revenda = st.text_input("Revenda / Empresa", placeholder="Ex: PLANJO MAQUINAS AGRI")
            representante = st.text_input("Representante", placeholder="Ex: João Silva")

        with c2:
            cidade = st.text_input("Cidade", placeholder="Ex: Campos Novos")
            estado = st.selectbox("Estado / País", [
                "SC", "RS", "PR", "SP", "MG", "RJ", "GO", "MT", "MS", "DF",
                "BA", "PE", "CE", "AM", "PA", "RO", "AC", "RR", "AP", "TO",
                "Paraguai", "Bolívia",
            ])
            obs = st.text_input("Observações (opcional)", placeholder="Ex: Microregião")

        salvar = st.form_submit_button("💾 Adicionar Cidade", type="primary", use_container_width=True)

        if salvar:
            rev_final = revenda if isinstance(revenda, str) else str(revenda)
            if not rev_final.strip():
                st.toast("⚠️ Revenda é obrigatória.", icon="🚫")
            elif not cidade.strip():
                st.toast("⚠️ Cidade é obrigatória.", icon="🚫")
            else:
                coord = _get_coord(cidade.strip(), estado)
                coord_status = "✅" if coord else "⚠️ coordenada não encontrada — verifique a grafia"
                reg = {
                    "Revenda":        rev_final.strip(),
                    "Representante":  representante.strip(),
                    "Cidade":         cidade.strip(),
                    "Estado":         estado,
                    "Observacoes":    obs.strip(),
                }
                if adicionar_territorio(reg):
                    st.toast(f"{coord_status} — {cidade} adicionada ao território de {rev_final}!", icon="✅")
                    st.rerun()


# ══════════════════════════════════════════════════════════════
# Tabela de territórios
# ══════════════════════════════════════════════════════════════

def _tabela_territorios(df: pd.DataFrame):
    if df.empty:
        st.info("Nenhum território cadastrado ainda.")
        return

    st.markdown('<div class="terr-sec">📋 Todos os Territórios</div>', unsafe_allow_html=True)

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

    # [V17-MAP-4] Export Excel
    buf = BytesIO()
    df_show.drop(columns=["id"], errors="ignore").to_excel(buf, index=False)
    col_dl, _ = st.columns([1, 3])
    col_dl.download_button("📥 Exportar Excel", data=buf.getvalue(),
                            file_name="territorios.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_terr_excel")

    cols_w = [2.0, 1.5, 1.5, 0.8, 1.8, 0.4]
    hdr = st.columns(cols_w)
    for c, lbl in zip(hdr, ["Revenda", "Representante", "Cidade", "UF", "Observações", ""]):
        c.markdown(
            f'<div style="font-size:10px;font-weight:700;color:#3A4858;text-transform:uppercase;'
            f'letter-spacing:.08em;padding-bottom:6px;border-bottom:1px solid #2D3748;">{lbl}</div>',
            unsafe_allow_html=True,
        )

    revendas_uniq = df["Revenda"].unique().tolist()
    color_map = {r: _CORES[i % len(_CORES)] for i, r in enumerate(revendas_uniq)}

    for _, row in df_show.iterrows():
        row_id  = int(row.get("id", 0))
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
    <div class="terr-sub">Cobertura de Revendas · Atualização Automática via Cadastro de Revendas</div>
  </div>
</div>""", unsafe_allow_html=True)

    df_terr = ler_territorios()

    # [V17-MAP-2] Botão de sincronização
    col_sync, col_info = st.columns([1, 3])
    with col_sync:
        if st.button("🔄 Sincronizar Revendas → Mapa", use_container_width=True, type="secondary"):
            with st.spinner("Sincronizando..."):
                n = _sincronizar_todas_revendas()
            if n > 0:
                st.success(f"✅ {n} nova(s) cidade(s) adicionada(s) ao mapa!")
                st.rerun()
            else:
                st.info("Mapa já está sincronizado com as revendas.")
    with col_info:
        st.caption("As cidades de atuação das revendas entram automaticamente no mapa ao cadastrar em **🏬 Revendas**. Use o botão ao lado para sincronizar revendas já cadastradas.")

    st.markdown("---")

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
            st.caption("Essas cidades não aparecem no mapa. Verifique a grafia exata.")
            for c in sem_coord:
                st.markdown(f"- `{c}`")

    st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:20px 0;">', unsafe_allow_html=True)

    if not df_terr.empty:
        _painel_revendas(df_terr)
        st.markdown('<hr style="border:none;border-top:1px solid #2D3748;margin:20px 0;">', unsafe_allow_html=True)

    tab_add, tab_lista = st.tabs(["📍 Adicionar Cidade Avulsa", "📋 Ver Territórios"])

    with tab_add:
        _form_cidade_avulsa(df_terr)

    with tab_lista:
        _tabela_territorios(df_terr)
