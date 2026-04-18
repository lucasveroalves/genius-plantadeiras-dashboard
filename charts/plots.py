"""
charts/plots.py v10 — Genius Plantadeiras

v10:
  • grafico_donut_pipeline: textinfo="percent" fora das fatias (textposition="outside"),
    automargin=True elimina sobreposição, legenda compacta à direita,
    altura 500 px para dar espaço aos labels externos
  • Todos os outros gráficos sem alteração funcional
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
# STATUS_PIPELINE definido localmente (não existe em data.loader na v11)
STATUS_PIPELINE = [
    "Em Negociação", "Em Aberto", "Crédito",
    "Pronto para Faturar", "Aguardando Checklist",
]

# ── Paleta ────────────────────────────────────────────────────
CARD = "#252B35"
ORG  = "#D4651E"
ORG2 = "#E8813E"
BLU  = "#1E3A5F"
BLU2 = "#2A5A8A"
BLU3 = "#4A7A9C"
GRN  = "#3D9970"
GRN2 = "#52B788"
TEL  = "#2A6A7A"
PUR  = "#5A4A8A"
YEL  = "#E8A020"
T1   = "#EEF2F8"
T2   = "#A8B8CC"
T3   = "#6A7A8A"
GRD  = "#2A3448"

SCALE_MAIN = [[0.0, BLU], [0.65, BLU2], [1.0, ORG]]
PIE_COLORS = [ORG, BLU2, BLU3, GRN, TEL, PUR, ORG2, GRN2]
ABC_COLORS = {"A": ORG, "B": BLU2, "C": T3}

_ABREV = {
    "Pronto para Faturar":  "Pronto p/ Fat.",
    "Aguardando Checklist": "Ag. Checklist",
    "Em Negociação":        "Em Negoc.",
}


def _brl(v: float) -> str:
    try:
        i, d = f"{abs(float(v)):,.2f}".split(".")
        return f"R$ {i.replace(',','.')},{d}"
    except Exception:
        return "R$ 0,00"


def _abrev_nome(s: str, max_len: int = 18) -> str:
    s = _ABREV.get(s, s)
    return s if len(s) <= max_len else s[:max_len - 1] + "…"


def _base(fig, title: str = "", h: int = 490, margin_b: int = 60):
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=17, color=T1,
                      family="'Barlow Condensed','DM Sans',sans-serif"),
            x=0.02, xanchor="left", y=0.97,
        ),
        plot_bgcolor=CARD,
        paper_bgcolor=CARD,
        font=dict(family="'DM Sans',sans-serif", size=13, color=T2),
        height=h,
        margin=dict(l=54, r=54, t=76, b=margin_b),
        legend=dict(
            bgcolor="rgba(0,0,0,0)", bordercolor=GRD, borderwidth=1,
            font=dict(size=13, color=T2),
        ),
        hoverlabel=dict(
            bgcolor="#1A2A3A", font_size=13,
            font_family="'DM Sans',sans-serif", bordercolor=ORG,
        ),
        separators=",.",
    )
    fig.update_xaxes(
        showgrid=False, zeroline=False,
        tickfont=dict(color=T2, size=13), linecolor=GRD,
    )
    fig.update_yaxes(
        showgrid=True, gridwidth=1, gridcolor=GRD,
        zeroline=False, tickfont=dict(color=T3, size=12),
        linecolor="rgba(0,0,0,0)",
    )
    return fig


# ════════════════════════════════════════════════════════════
# MÁQUINAS
# ════════════════════════════════════════════════════════════

def grafico_status_barras(df: pd.DataFrame):
    """Preservado mas não chamado no layout atual do dashboard."""
    try:
        ss = (df.groupby("Status")["Valor"].sum()
              .reset_index().sort_values("Valor", ascending=False))
        x_labels = [_abrev_nome(s) for s in ss["Status"]]
        max_val  = ss["Valor"].max()
        cores    = [ORG if v == max_val else BLU2 for v in ss["Valor"]]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=x_labels, y=ss["Valor"],
            marker=dict(color=cores, line=dict(color="rgba(0,0,0,0)")),
            text=[_brl(v) for v in ss["Valor"]],
            textposition="outside", cliponaxis=False,
            textfont=dict(color=T1, size=18,
                          family="'Barlow Condensed','DM Sans',sans-serif"),
            hovertemplate="<b>%{x}</b><br>%{customdata}<extra></extra>",
            customdata=[_brl(v) for v in ss["Valor"]],
        ))
        fig = _base(fig, "Volume Financeiro por Status", h=560, margin_b=80)
        fig.update_yaxes(tickformat=",.0f", tickprefix="R$ ", showgrid=False)
        fig.update_xaxes(tickangle=-25, showgrid=False)
        fig.update_layout(yaxis=dict(range=[0, max_val * 1.32]), bargap=0.35)
        return fig
    except Exception as e:
        st.error(f"Erro barras status: {e}")
        return go.Figure()


def grafico_top_revendas(df: pd.DataFrame, top_n: int = 10):
    try:
        rs = (df.groupby("Revenda")["Valor"].sum()
              .reset_index().sort_values("Valor", ascending=True).tail(top_n))
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=rs["Revenda"], x=rs["Valor"], orientation="h",
            marker=dict(
                color=rs["Valor"], colorscale=SCALE_MAIN,
                showscale=False, line=dict(color="rgba(0,0,0,0)"),
            ),
            text=[_brl(v) for v in rs["Valor"]],
            textposition="outside", cliponaxis=False,
            textfont=dict(color=T1, size=14,
                          family="'Barlow Condensed','DM Sans',sans-serif"),
            hovertemplate="<b>%{y}</b><br>%{customdata}<extra></extra>",
            customdata=[_brl(v) for v in rs["Valor"]],
        ))
        fig = _base(fig, f"Top {top_n} Revendas por Faturamento", 500)
        fig.update_xaxes(showgrid=True, gridcolor=GRD,
                         tickformat=",.0f", tickprefix="R$ ")
        fig.update_yaxes(showgrid=False, autorange="reversed",
                         tickfont=dict(size=12))
        mx = rs["Valor"].max()
        fig.update_layout(xaxis=dict(range=[0, mx * 1.28]))
        return fig
    except Exception as e:
        st.error(f"Erro top revendas: {e}")
        return go.Figure()


def grafico_evolucao_temporal(df: pd.DataFrame):
    try:
        if "Data_Pedido" not in df.columns:
            return None
        dt = df.copy()
        dt["Data_Pedido"] = pd.to_datetime(dt["Data_Pedido"], errors="coerce")
        dt = dt.dropna(subset=["Data_Pedido"])
        if dt.empty:
            return None
        if dt["Data_Pedido"].dt.tz is not None:
            dt["Data_Pedido"] = dt["Data_Pedido"].dt.tz_localize(None)
        dt["Semana"] = dt["Data_Pedido"].dt.to_period("W").dt.start_time
        ev = dt.groupby("Semana")["Valor"].sum().reset_index()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=ev["Semana"], y=ev["Valor"],
            mode="lines+markers",
            line=dict(color=ORG, width=2.5, shape="spline"),
            marker=dict(size=7, color=ORG, line=dict(color=CARD, width=1.5)),
            fill="tozeroy", fillcolor="rgba(212,101,30,.10)",
            name="Pipeline",
            hovertemplate="<b>%{x|%d/%m/%Y}</b><br>%{customdata}<extra></extra>",
            customdata=[_brl(v) for v in ev["Valor"]],
        ))
        fig = _base(fig, "Evolução Semanal do Pipeline", 440)
        fig.update_xaxes(tickformat="%d/%m")
        fig.update_yaxes(tickformat=",.0f", tickprefix="R$ ")
        return fig
    except Exception as e:
        st.error(f"Erro temporal: {e}")
        return None


def grafico_donut_pipeline(df: pd.DataFrame):
    """
    Donut do pipeline ativo — v11.
    • textinfo="percent+label" dentro das fatias (radial) → sem sobreposição
    • Sem legenda externa → donut ocupa todo o espaço disponível
    • Margem mínima → gráfico maior e mais dinâmico
    • Hover mostra valor R$ completo
    """
    try:
        pf = df[df["Status"].isin(STATUS_PIPELINE)]
        if pf.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="Sem dados no pipeline ativo",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color=T3),
            )
            return _base(fig, "Distribuição do Pipeline Ativo", 440)

        ss = (pf.groupby("Status")["Valor"].sum()
              .reset_index().sort_values("Valor", ascending=False))
        n     = len(ss)
        cores = (PIE_COLORS * 4)[:n]

        total = ss["Valor"].sum()
        # Pull suave nas fatias menores para respirar
        pull = [0.04 if (v / total) < 0.10 else 0.0 for v in ss["Valor"]]

        fig = go.Figure()
        fig.add_trace(go.Pie(
            labels=ss["Status"],
            values=ss["Valor"],
            hole=0.50,
            marker=dict(colors=cores, line=dict(color=CARD, width=2)),
            # % + nome curto dentro, radial para não sobrepor
            textinfo="percent+label",
            textposition="inside",
            insidetextorientation="radial",
            textfont=dict(
                size=12, color="#FFFFFF",
                family="'Barlow Condensed','DM Sans',sans-serif",
            ),
            automargin=True,
            pull=pull,
            hovertemplate=(
                "<b>%{label}</b><br>"
                "%{customdata}<br>"
                "%{percent:.1%}<extra></extra>"
            ),
            customdata=[_brl(v) for v in ss["Valor"]],
            showlegend=False,       # sem legenda = mais espaço pro donut
            direction="clockwise",
            sort=False,
        ))

        # Valor total no centro do furo
        fig.add_annotation(
            text=f"<b>{_brl(total)}</b><br><span style='font-size:10px'>Pipeline</span>",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=13, color=T1,
                      family="'Barlow Condensed','DM Sans',sans-serif"),
            align="center",
        )

        fig.update_layout(
            title=dict(
                text="Distribuição do Pipeline Ativo",
                font=dict(size=17, color=T1,
                          family="'Barlow Condensed','DM Sans',sans-serif"),
                x=0.02, xanchor="left",
            ),
            plot_bgcolor=CARD,
            paper_bgcolor=CARD,
            font=dict(family="'DM Sans',sans-serif", size=13, color=T2),
            height=440,
            # Margens mínimas = donut ocupa todo o espaço
            margin=dict(l=10, r=10, t=60, b=10),
            separators=",.",
            hoverlabel=dict(
                bgcolor="#1A2A3A", font_size=13,
                font_family="'DM Sans',sans-serif", bordercolor=ORG,
            ),
        )
        return fig
    except Exception as e:
        st.error(f"Erro donut: {e}")
        return go.Figure()


# ════════════════════════════════════════════════════════════
# PEÇAS
# ════════════════════════════════════════════════════════════

def grafico_curva_abc(df_abc: pd.DataFrame, top_n: int = 20):
    """
    Curva ABC — barras horizontais, estilo IDENTICO ao grafico_ranking_revendas_pecas.
    Cores: A=laranja, B=azul escalonado, C=cinza.
    Exige colunas: Codigo, Descricao_Peca, Valor_Total, Pct, Pct_Acum, Curva.
    """
    try:
        if df_abc is None or df_abc.empty:
            fig = go.Figure()
            fig.add_annotation(text="Sem dados para Curva ABC", x=0.5, y=0.5,
                               showarrow=False, font=dict(color=T3, size=14))
            return _base(fig, f"Curva ABC — Top {top_n} Peças Mais Vendidas", 480)

        df_abc = df_abc.copy()
        for col in ["Valor_Total", "Pct", "Pct_Acum"]:
            if col in df_abc.columns:
                df_abc[col] = pd.to_numeric(df_abc[col], errors="coerce").fillna(0)
            else:
                df_abc[col] = 0.0

        if "Curva" not in df_abc.columns:
            df_abc["Curva"] = "A"

        df_abc = (df_abc[df_abc["Valor_Total"] > 0]
                  .sort_values("Valor_Total", ascending=False)
                  .head(top_n)
                  .sort_values("Valor_Total", ascending=True)   # plotly: menor embaixo, maior em cima
                  .reset_index(drop=True))

        if df_abc.empty:
            fig = go.Figure()
            fig.add_annotation(text="Sem dados para Curva ABC", x=0.5, y=0.5,
                               showarrow=False, font=dict(color=T3, size=14))
            return _base(fig, f"Curva ABC — Top {top_n} Peças Mais Vendidas", 480)

        # Label eixo Y: código + descrição curta
        def _ylabel(row):
            cod  = str(row.get("Codigo", "")).strip()
            desc = str(row.get("Descricao_Peca", "")).strip()
            if desc and desc not in ("", "nan", cod):
                short = desc[:26] + "…" if len(desc) > 26 else desc
                return f"{cod} · {short}"
            return cod

        ylabels = [_ylabel(r) for _, r in df_abc.iterrows()]
        curvas  = df_abc["Curva"].tolist()
        mx      = float(df_abc["Valor_Total"].max())

        # Cor por curva — A=laranja, B=azul gradiente, C=cinza
        COR_MAP = {"A": ORG, "B": BLU2, "C": T3}
        cores = [COR_MAP.get(c, BLU2) for c in curvas]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=ylabels,
            x=df_abc["Valor_Total"],
            orientation="h",
            marker=dict(
                color=cores,
                line=dict(color="rgba(0,0,0,0)"),
            ),
            text=[_brl(v) for v in df_abc["Valor_Total"]],
            textposition="outside",
            cliponaxis=False,
            textfont=dict(color=T1, size=14,
                          family="'Barlow Condensed','DM Sans',sans-serif"),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Valor: %{customdata[0]}<br>"
                "Curva <b>%{customdata[1]}</b>  ·  %{customdata[2]:.1f}%  "
                "(acum. %{customdata[3]:.1f}%)<extra></extra>"
            ),
            customdata=list(zip(
                [_brl(v) for v in df_abc["Valor_Total"]],
                curvas,
                df_abc["Pct"],
                df_abc["Pct_Acum"],
            )),
        ))

        # Usa _base() — mesma função do ranking de revendas
        n_items = len(df_abc)
        altura  = max(480, 80 + n_items * 36)
        fig = _base(fig, f"Curva ABC — Top {top_n} Peças Mais Vendidas", altura)

        # Eixo X: igual ao ranking (começa em 0, sem grid vertical, prefixo R$)
        fig.update_xaxes(
            showgrid=False,
            zeroline=False,
            tickformat=",.0f",
            tickprefix="R$ ",
            range=[0, mx * 1.30],
        )

        # Eixo Y: nomes não cortados, ordem preservada
        fig.update_yaxes(
            showgrid=False,
            categoryorder="array",
            categoryarray=ylabels,
            tickfont=dict(size=12),
            automargin=True,
        )

        # Legenda de curvas A/B/C presentes nos dados
        badges = [
            ("A", ORG,  "Curva A  ≤80%"),
            ("B", BLU2, "Curva B  80–95%"),
            ("C", T3,   "Curva C  >95%"),
        ]
        for k, cor, lbl in badges:
            if k in curvas:
                fig.add_trace(go.Scatter(
                    x=[None], y=[None], mode="markers", name=lbl,
                    marker=dict(color=cor, size=10, symbol="square"),
                    showlegend=True,
                ))

        return fig
    except Exception as e:
        st.error(f"Erro curva ABC: {e}")
        return go.Figure()

def grafico_ranking_revendas_pecas(df: pd.DataFrame, top_n: int = 10):
    try:
        fat = (df[df["Status_Peca"] == "Faturado"]
               if "Status_Peca" in df.columns else df)
        if "Cliente_Revenda" not in fat.columns or fat.empty:
            fig = go.Figure()
            fig.add_annotation(text="Sem dados de revendas", x=0.5, y=0.5,
                               showarrow=False, font=dict(color=T3, size=14))
            return _base(fig, f"Top {top_n} Revendas — Consumo de Peças", 480)
        rs = (fat.groupby("Cliente_Revenda")["Valor_Total"].sum()
              .reset_index().sort_values("Valor_Total", ascending=True).tail(top_n))
        # Garante que os nomes são string (evita eixo numérico)
        rs["Cliente_Revenda"] = rs["Cliente_Revenda"].astype(str).str.strip()

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=rs["Cliente_Revenda"], x=rs["Valor_Total"],
            orientation="h",
            marker=dict(
                color=rs["Valor_Total"], colorscale=SCALE_MAIN,
                showscale=False, line=dict(color="rgba(0,0,0,0)"),
            ),
            text=[_brl(v) for v in rs["Valor_Total"]],
            textposition="outside", cliponaxis=False,
            textfont=dict(color=T1, size=14,
                          family="'Barlow Condensed','DM Sans',sans-serif"),
            hovertemplate="<b>%{y}</b><br>%{customdata}<extra></extra>",
            customdata=[_brl(v) for v in rs["Valor_Total"]],
        ))
        fig = _base(fig, f"Top {top_n} Revendas — Consumo de Peças", 480)
        fig.update_xaxes(showgrid=True, gridcolor=GRD,
                         tickformat=",.0f", tickprefix="R$ ")
        # categoryorder garante ordenação correta sem autorange=reversed
        fig.update_yaxes(showgrid=False,
                         categoryorder="total ascending",
                         tickfont=dict(size=12))
        mx = float(rs["Valor_Total"].max()) if not rs.empty else 1
        fig.update_layout(xaxis=dict(range=[0, mx * 1.28]))
        return fig
    except Exception as e:
        st.error(f"Erro ranking revendas peças: {e}")
        return go.Figure()


def grafico_evolucao_pecas(df: pd.DataFrame):
    try:
        if "Data_Venda" not in df.columns:
            return None
        dt = df.copy()
        dt["Data_Venda"] = pd.to_datetime(dt["Data_Venda"], errors="coerce")
        dt = dt.dropna(subset=["Data_Venda"])
        if dt.empty:
            return None
        if dt["Data_Venda"].dt.tz is not None:
            dt["Data_Venda"] = dt["Data_Venda"].dt.tz_localize(None)
        dt["Mes"] = dt["Data_Venda"].dt.to_period("M").dt.start_time

        fat  = (dt[dt["Status_Peca"] == "Faturado"]
                .groupby("Mes")["Valor_Total"].sum().reset_index())
        orca = (dt[dt["Status_Peca"] == "Orçamento"]
                .groupby("Mes")["Valor_Total"].sum().reset_index())

        fig = go.Figure()
        if not fat.empty:
            fig.add_trace(go.Scatter(
                x=fat["Mes"], y=fat["Valor_Total"],
                name="Faturado", mode="lines+markers",
                line=dict(color=GRN, width=2.5, shape="spline"),
                marker=dict(size=6, color=GRN),
                fill="tozeroy", fillcolor="rgba(61,153,112,.10)",
                hovertemplate="Faturado %{x|%b/%Y}<br>%{customdata}<extra></extra>",
                customdata=[_brl(v) for v in fat["Valor_Total"]],
            ))
        if not orca.empty:
            fig.add_trace(go.Scatter(
                x=orca["Mes"], y=orca["Valor_Total"],
                name="Orçamento", mode="lines+markers",
                line=dict(color=YEL, width=2, dash="dot"),
                marker=dict(size=6, color=YEL),
                hovertemplate="Orçamento %{x|%b/%Y}<br>%{customdata}<extra></extra>",
                customdata=[_brl(v) for v in orca["Valor_Total"]],
            ))
        fig = _base(fig, "Evolução Mensal — Peças Faturadas vs. Orçadas", 420)
        fig.update_xaxes(tickformat="%b/%y")
        fig.update_yaxes(tickformat=",.0f", tickprefix="R$ ")
        return fig
    except Exception as e:
        st.error(f"Erro evolução peças: {e}")
        return None
