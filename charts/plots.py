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
    Gráfico de PIZZA (pie) para a Curva ABC de peças.
    Agrupa por classe A/B/C e mostra % do faturamento total.
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

    col_valor = next(
        (c for c in ["Valor_Total", "valor_total", "Quantidade", "quantidade"] if c in df.columns),
        df.columns[-1],
    )
    col_classe = next(
        (c for c in ["Curva", "curva", "Classe", "classe"] if c in df.columns),
        None,
    )

    df = df.copy()
    df[col_valor] = pd.to_numeric(df[col_valor], errors="coerce").fillna(0)
    df = df[df[col_valor] > 0]

    if df.empty:
        fig = go.Figure()
        _layout_base(fig)
        return fig

    # Calcula curva ABC completa e agrupa por CLASSE
    df[col_valor] = pd.to_numeric(df[col_valor], errors="coerce").fillna(0)
    total_geral = df[col_valor].sum()
    
    if col_classe and col_classe in df.columns:
        # Já tem coluna de classe — agrupa direto
        grp = df.groupby(col_classe)[col_valor].sum().reset_index()
        labels = grp[col_classe].tolist()
        values = grp[col_valor].tolist()
    else:
        # Calcula ABC pelo acumulado e agrupa por classe
        df_sorted = df.sort_values(col_valor, ascending=False).copy()
        df_sorted["pct_acum"] = df_sorted[col_valor].cumsum() / total_geral * 100
        df_sorted["Curva"] = df_sorted["pct_acum"].apply(
            lambda x: "A" if x <= 80 else ("B" if x <= 95 else "C")
        )
        grp = df_sorted.groupby("Curva")[col_valor].sum()
        # Garante ordem A, B, C
        labels = [c for c in ["A", "B", "C"] if c in grp.index]
        values = [grp[c] for c in labels]

    color_map = {
        "A": _LARANJA, "B": _VERDE, "C": _AZUL,
        "Outros": "#4A5568",
    }
    colors = [color_map.get(str(l), _AZUL) for l in labels]

    # Formata texto das fatias
    total = sum(values)
    text_labels = [
        f"{l}<br>{_fmt_brl_compacto(v)}<br>({v/total*100:.1f}%)"
        for l, v in zip(labels, values)
    ]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        text=text_labels,
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>%{value:,.0f}<br>%{percent}<extra></extra>",
        marker=dict(colors=colors, line=dict(color=_PAPER, width=2)),
        hole=0.35,
    ))

    fig.update_layout(
        paper_bgcolor=_PAPER,
        plot_bgcolor=_BG,
        font=dict(color=_TEXT, family="Inter, sans-serif", size=12),
        margin=dict(l=10, r=10, t=30, b=10),
        showlegend=True,
        legend=dict(
            orientation="v",
            font=dict(size=11, color=_TEXT),
            bgcolor="rgba(0,0,0,0)",
        ),
        height=380,
    )

    return fig



# ══════════════════════════════════════════════════════════════
# Top Produtos por Código (barras horizontais)
# ══════════════════════════════════════════════════════════════

def grafico_top_produtos(df: pd.DataFrame, top_n: int = 15) -> go.Figure:
    """
    Barras horizontais mostrando os top produtos por faturamento.
    Exibe: Código + Descrição, valor formatado, cor por classe A/B/C.
    """
    if df is None or df.empty:
        fig = go.Figure()
        _layout_base(fig)
        return fig

    col_cod   = next((c for c in ["Codigo","_cod","codigo"] if c in df.columns), None)
    col_desc  = next((c for c in ["Descricao_Peca","descricao_peca"] if c in df.columns), col_cod)
    col_valor = next((c for c in ["Valor_Total","valor_total"] if c in df.columns), None)
    col_curva = next((c for c in ["Curva","curva"] if c in df.columns), None)

    if not col_valor:
        fig = go.Figure()
        _layout_base(fig)
        return fig

    df = df.copy()
    df[col_valor] = pd.to_numeric(df[col_valor], errors="coerce").fillna(0)
    df = df[df[col_valor] > 0].sort_values(col_valor, ascending=False).head(top_n)
    df = df.sort_values(col_valor, ascending=True)  # maior no topo

    # Label: Código — Descrição (truncada)
    if col_cod and col_desc and col_cod != col_desc:
        df["_label"] = df[col_cod].astype(str) + " — " + df[col_desc].astype(str).str[:30]
    elif col_cod:
        df["_label"] = df[col_cod].astype(str)
    else:
        df["_label"] = df[col_desc].astype(str).str[:35]

    # Cor por classe
    color_map = {"A": _LARANJA, "B": _VERDE, "C": _AZUL}
    if col_curva:
        colors = [color_map.get(str(c), _AZUL) for c in df[col_curva]]
    else:
        colors = [_LARANJA] * len(df)

    def _fmt_brl_completo(v):
        try:
            return f"R$ {float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
        except:
            return "—"

    fig = go.Figure(go.Bar(
        x=df[col_valor],
        y=df["_label"],
        orientation="h",
        text=df[col_valor].apply(_fmt_brl_completo),
        textposition="outside",
        textfont=dict(size=10, color="#EEF2F8"),
        marker=dict(color=colors, line=dict(width=0)),
        cliponaxis=False,
    ))

    fig.update_layout(
        paper_bgcolor=_PAPER,
        plot_bgcolor=_BG,
        font=dict(color=_TEXT, family="Inter, sans-serif", size=10),
        margin=dict(l=10, r=80, t=20, b=10),
        showlegend=False,
        xaxis=dict(
            rangemode="tozero", showgrid=False, zeroline=False,
            tickfont=dict(color=_TEXT, size=9), title=None,
            tickformat=",.0f",
        ),
        yaxis=dict(showgrid=False, zeroline=False,
                   tickfont=dict(color="#EEF2F8", size=9), title=None, automargin=True),
        bargap=0.2,
        height=max(350, len(df) * 26 + 60),
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
