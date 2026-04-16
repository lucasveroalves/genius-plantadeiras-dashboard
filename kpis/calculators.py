"""
kpis/calculators.py — Cálculo dos KPIs
Genius Plantadeiras | Dashboard de Performance Comercial

AUDITORIA v2 — Correções aplicadas:
  1. Comparações agora usam as constantes *_LOWER de loader.py para garantir
     consistência — eliminado risco de divergência entre listas duplicadas.
  2. Adicionado safe-guard: se coluna 'Valor' ou 'Status' ausente, retorna
     zeros sem lançar exceção silenciosa.
  3. ticket_medio: calculado apenas sobre pedidos com Valor > 0 (exclui zeros
     gerados por erros de parse que passaram pelo dropna).
  4. Todos os retornos numéricos são explicitamente float para evitar problemas
     de serialização/formatação downstream.
"""

import pandas as pd
import streamlit as st
from data.loader import (
    STATUS_FATURADO_LOWER,
    STATUS_PIPELINE_LOWER,
    STATUS_ALERTA_LOWER,
)


def calcular_kpis(df: pd.DataFrame) -> dict:
    """
    Retorna dicionário com os 6 KPIs do dashboard.
    Nunca lança exceção — em caso de erro devolve zeros.
    """
    _zeros = {
        "faturado":       0.0,
        "a_entrar":       0.0,
        "total_pipeline": 0.0,
        "qtd_pedidos":    0,
        "ticket_medio":   0.0,
        "qtd_alertas":    0,
    }

    if df is None or df.empty:
        return _zeros

    # Colunas obrigatórias
    if "Status" not in df.columns or "Valor" not in df.columns:
        st.warning("⚠️ Colunas 'Status' ou 'Valor' ausentes — KPIs zerados.")
        return _zeros

    try:
        status_lower = df["Status"].str.lower().str.strip()

        # ── Faturado ──────────────────────────────────────────────
        faturado = float(
            df.loc[status_lower.isin(STATUS_FATURADO_LOWER), "Valor"].sum()
        )

        # ── A Entrar (Em Aberto + Crédito) ────────────────────────
        a_entrar_mask = status_lower.isin(["em aberto", "crédito"])
        a_entrar = float(df.loc[a_entrar_mask, "Valor"].sum())

        # ── Pipeline total ────────────────────────────────────────
        pipeline_mask = status_lower.isin(STATUS_PIPELINE_LOWER)
        total_pipeline = float(df.loc[pipeline_mask, "Valor"].sum())

        # ── Quantidade e ticket médio ─────────────────────────────
        qtd_pedidos = int(len(df))
        valores_validos = df.loc[df["Valor"] > 0, "Valor"]
        ticket_medio = float(valores_validos.mean()) if len(valores_validos) > 0 else 0.0

        # ── Alertas ───────────────────────────────────────────────
        qtd_alertas = int(status_lower.isin(STATUS_ALERTA_LOWER).sum())

        return {
            "faturado":       faturado,
            "a_entrar":       a_entrar,
            "total_pipeline": total_pipeline,
            "qtd_pedidos":    qtd_pedidos,
            "ticket_medio":   ticket_medio,
            "qtd_alertas":    qtd_alertas,
        }

    except Exception as e:
        st.error(f"Erro ao calcular KPIs: {e}")
        return _zeros
