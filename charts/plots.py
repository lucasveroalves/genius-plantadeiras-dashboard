"""
charts/plots.py — Genius Implementos Agrícolas v15

Correções aplicadas:
  [FIX-ABC]  grafico_curva_abc reconstruído com plotly.express:
             - Barras horizontais (orientation='h')
             - Ordena maior → topo (sort_values + category_orders)
             - xaxis rangemode="tozero" — eixo X SEMPRE começa do zero
             - Rótulos na ponta das barras: formato compacto R$ 1.5M / R$ 800k
             - Grid de fundo removido; tema dark consistente
"""

from __future__ import annotations
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# ── Paleta compartilhada ──────────────────────────────────────
_BG    = "#12171D"
_PAPER = "#1E262E"
_GRID  = "#2D3748"
_TEXT  = "#A8B8CC"
_LARANJA = "#E67E22"
_VERDE   = "#3D9970"
_AZUL    = "#2A5A8A"


def _fmt_brl_compacto(v: float) -> str:
    """Formata valor em BRL compacto: R$ 1.5M, R$ 800k, R$ 250."""
    try:
        v = float(v)
        if v >= 1_000_000:
            return f"R$ {v/1_000_000:.1f}M"
        if v >= 1_000:
            return f"R$ {v/1_000:.0f}k"
        return f"R$ {v:,.0f}"
    except Exception:
        return "—"


def _layout_base(fig: go.Figure, title: str = "") -> go.Figure:
    """Aplica tema dark padrão ao layout."""
    fig.update_layout(
        title=dict(text=title, font=dict(color="#EEF2F8", size=14)) if title else None,
        paper_bgcolor=_PAPER,
        plot_bgcolor=_BG,
        font=dict(color=_TEXT, family="Inter, sans-serif"),
        margin=dict(l=10, r=10, t=30 if title else 10, b=10),
        showlegend=False,
    )
    return fig


# ══════════════════════════════════════════════════════════════
# [FIX-ABC]  Curva ABC — Peças mais vendidas
# ══════════════════════════════════════════════════════════════

def grafico_curva_abc(df: pd.DataFrame) -> go.Figure:
    """
    Gráfico de barras horizontais para a Curva ABC de peças.

    Parâmetros esperados no df:
        - 'Codigo_Peca' ou 'Descricao'  → label do eixo Y
        - 'Valor_Total' ou 'Quantidade' → magnitude das barras (eixo X)
        - 'Classe' (opcional)           → cor A/B/C

    Regras de exibição:
        - Ordena descrescente → maior barra no TOPO
        - Eixo X começa ESTRITAMENTE do zero (rangemode="tozero")
        - Rótulos compactos no final de cada barra
        - Sem grid de fundo
    """
    if df is None or df.empty:
        fig = go.Figure()
        _layout_base(fig)
        fig.add_annotation(
            text="Sem dados", xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(color=_TEXT, size=14),
        )
        return fig

    # ── Decide coluna de label e de valor ─────────────────────
    col_label = next(
        (c for c in ["Descricao", "Codigo_Peca", "descricao", "codigo_peca"] if c in df.columns),
        df.columns[0],
    )
    col_valor = next(
        (c for c in ["Valor_Total", "valor_total", "Quantidade", "quantidade"] if c in df.columns),
        df.columns[-1],
    )
    col_classe = next(
        (c for c in ["Classe", "classe", "Curva", "curva"] if c in df.columns),
        None,
    )

    df = df.copy()
    df[col_valor] = pd.to_numeric(df[col_valor], errors="coerce").fillna(0)
    df = df[df[col_valor] > 0]

    if df.empty:
        fig = go.Figure()
        _layout_base(fig)
        return fig

    # Ordena crescente para que maior fique no TOPO no px (eixo y invertido)
    df = df.sort_values(col_valor, ascending=True).tail(25)

    # ── Mapa de cores por classe A/B/C ─────────────────────────
    color_map = {"A": _LARANJA, "B": _VERDE, "C": _AZUL}
    if col_classe and col_classe in df.columns:
        color_col = col_classe
    else:
        # Atribui classe pelo percentil se não existir
        df["_classe_calc"] = pd.cut(
            df[col_valor].rank(pct=True),
            bins=[0, 0.2, 0.5, 1.0],
            labels=["C", "B", "A"],
        ).astype(str)
        color_col = "_classe_calc"
        color_map = {"A": _LARANJA, "B": _VERDE, "C": _AZUL}

    # ── Plotly Express: barras horizontais ────────────────────
    fig = px.bar(
        df,
        x=col_valor,
        y=col_label,
        orientation="h",
        color=color_col,
        color_discrete_map=color_map,
        text=df[col_valor].apply(_fmt_brl_compacto),
    )

    # ── Estilização das barras ─────────────────────────────────
    fig.update_traces(
        textposition="outside",
        textfont=dict(size=11, color="#EEF2F8"),
        marker_line_width=0,
        cliponaxis=False,
    )

    # ── Layout ─────────────────────────────────────────────────
    fig.update_layout(
        paper_bgcolor=_PAPER,
        plot_bgcolor=_BG,
        font=dict(color=_TEXT, family="Inter, sans-serif", size=11),
        margin=dict(l=10, r=80, t=20, b=10),
        showlegend=bool(col_classe),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="left", x=0,
            font=dict(size=10, color=_TEXT),
        ),
        # ── [FIX-ABC] Eixo X SEMPRE começa do zero ────────────
        xaxis=dict(
            rangemode="tozero",        # NUNCA corta abaixo de 0
            showgrid=False,            # Remove grid vertical
            zeroline=False,
            tickfont=dict(color=_TEXT, size=10),
            title=None,
        ),
        yaxis=dict(
            showgrid=False,            # Remove grid horizontal
            zeroline=False,
            tickfont=dict(color="#EEF2F8", size=10),
            title=None,
            automargin=True,
        ),
        bargap=0.25,
        height=max(300, len(df) * 28 + 60),
    )

    return fig


# ══════════════════════════════════════════════════════════════
# Ranking Top-10 Revendas
# ══════════════════════════════════════════════════════════════

def grafico_ranking_revendas_pecas(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """
    Barras horizontais — Top-N revendas por valor faturado.
    Mesmas regras de eixo: rangemode=tozero, sem grid.
    """
    if df is None or df.empty:
        fig = go.Figure()
        _layout_base(fig)
        return fig

    col_rev = next(
        (c for c in ["Revenda", "revenda", "Cliente", "cliente"] if c in df.columns),
        df.columns[0],
    )
    col_val = next(
        (c for c in ["Valor_Total", "valor_total", "Valor", "valor"] if c in df.columns),
        df.columns[-1],
    )

    df = df.copy()
    df[col_val] = pd.to_numeric(df[col_val], errors="coerce").fillna(0)
    df = (
        df.groupby(col_rev, as_index=False)[col_val]
        .sum()
        .nlargest(top_n, col_val)
        .sort_values(col_val, ascending=True)  # topo = maior
    )

    fig = px.bar(
        df,
        x=col_val,
        y=col_rev,
        orientation="h",
        text=df[col_val].apply(_fmt_brl_compacto),
        color_discrete_sequence=[_AZUL],
    )

    fig.update_traces(
        textposition="outside",
        textfont=dict(size=11, color="#EEF2F8"),
        marker_color=_AZUL,
        marker_line_width=0,
        cliponaxis=False,
    )

    fig.update_layout(
        paper_bgcolor=_PAPER,
        plot_bgcolor=_BG,
        font=dict(color=_TEXT, family="Inter, sans-serif", size=11),
        margin=dict(l=10, r=80, t=20, b=10),
        showlegend=False,
        xaxis=dict(
            rangemode="tozero",
            showgrid=False,
            zeroline=False,
            tickfont=dict(color=_TEXT, size=10),
            title=None,
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            tickfont=dict(color="#EEF2F8", size=10),
            title=None,
            automargin=True,
        ),
        bargap=0.25,
        height=max(300, len(df) * 28 + 60),
    )

    return fig


# ══════════════════════════════════════════════════════════════
# Gráfico genérico de linha (para lead time / evolução)
# ══════════════════════════════════════════════════════════════

def grafico_linha_serie(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    color: str = _LARANJA,
) -> go.Figure:
    """Linha temporal simples com tema dark."""
    fig = px.line(df, x=x, y=y, title=title, color_discrete_sequence=[color])
    fig.update_traces(line_width=2)
    fig.update_layout(
        paper_bgcolor=_PAPER,
        plot_bgcolor=_BG,
        font=dict(color=_TEXT, size=11),
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(color=_TEXT)),
        yaxis=dict(
            showgrid=True,
            gridcolor=_GRID,
            zeroline=False,
            tickfont=dict(color=_TEXT),
            rangemode="tozero",
        ),
    )
    return fig
