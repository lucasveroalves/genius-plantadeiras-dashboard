# 🌾 Genius Plantadeiras — Dashboard de Performance Comercial

Dashboard executivo do pipeline de vendas com autenticação por usuário,
filtros interativos, gráficos responsivos e identidade visual Genius.

---

## 📁 Estrutura de Arquivos

```
genius_dashboard/
├── app.py                        ← Ponto de entrada (streamlit run app.py)
├── auth.py                       ← Autenticação / controle de sessão
├── gerar_senhas.py               ← Utilitário para gerar hashes de senha
├── requirements.txt              ← Dependências Python
│
├── data/
│   └── loader.py                 ← Carregamento, validação e limpeza
│
├── kpis/
│   └── calculators.py            ← Cálculo dos KPIs
│
├── charts/
│   └── plots.py                  ← Todos os gráficos Plotly
│
├── components/
│   └── ui.py                     ← Componentes de interface (CSS, cards, tabelas)
│
├── assets/
│   └── genius_logo.png           ← Logo Genius (identidade visual)
│
└── .streamlit/
    ├── config.toml               ← Tema escuro com cor primária Genius
    └── secrets.toml              ← Credenciais dos usuários (⚠️ não commitar!)
```

---

## 🚀 Instalação e Execução

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Configurar senhas dos usuários

```bash
python gerar_senhas.py
```

Cole os hashes gerados no arquivo `.streamlit/secrets.toml`.

> **Usuários padrão disponíveis:** `admin`, `gerente1`, `vendedor1`, `vendedor2`,
> `analista1`, `analista2`, `consultor`

### 3. Executar o dashboard

```bash
streamlit run app.py
```

Acesse: `http://localhost:8501`

---

## 🔐 Sistema de Login

| Usuário    | Role      | Permissões                              |
|------------|-----------|------------------------------------------|
| admin      | admin     | Tudo + configurações                    |
| gerente1   | gestor    | Todos os dados + alertas + exportação   |
| vendedor1  | vendedor  | Dashboard sem tabela de alertas         |
| vendedor2  | vendedor  | Dashboard sem tabela de alertas         |
| analista1  | analista  | Todos os dados + alertas                |
| analista2  | analista  | Todos os dados + alertas                |
| consultor  | readonly  | Somente visualização do dashboard       |

- Sessão expira após **8 horas** de inatividade
- Senhas armazenadas como **hash bcrypt** (nunca em texto puro)
- Credenciais em `.streamlit/secrets.toml` (**adicione ao `.gitignore`!**)

---

## 📊 Funcionalidades

### KPIs (6 cards)
- 💰 Faturamento Realizado
- 📥 Faturamento a Entrar (Em Aberto + Crédito)
- 🚜 Total do Pipeline
- 📋 Total de Pedidos
- 🎫 Ticket Médio
- 🚨 Pedidos em Alerta

### Gráficos
- **Barras verticais** — Volume financeiro por status
- **Barras horizontais** — Top 10 revendas por faturamento
- **Área temporal** — Evolução semanal do pipeline
- **Donut** — Distribuição proporcional do pipeline ativo

### Filtros (sidebar)
- Período (data inicial / final)
- Revendas (multi-seleção)
- Status (multi-seleção)

### Tabela de Alertas
- Pedidos `Atrasado` (fundo vermelho) e `Aguardando Checklist` (fundo amarelo)
- Visível apenas para roles: `admin`, `gestor`, `analista`

---

## 📂 Formato da Planilha

O dashboard aceita arquivos **CSV** ou **XLSX** com as colunas:

| Coluna       | Tipo     | Obrigatório | Descrição                        |
|--------------|----------|-------------|----------------------------------|
| Status       | texto    | ✅ Sim      | Ver status reconhecidos abaixo   |
| Revenda      | texto    | ✅ Sim      | Nome da revenda                  |
| Valor        | numérico | ✅ Sim      | Valor do pedido em R$            |
| Data_Pedido  | data     | ❌ Opcional | Habilita gráfico temporal        |
| Observacao   | texto    | ❌ Opcional | Exibido na tabela de alertas     |

**Status reconhecidos** (case-insensitive):
`Faturado` · `Em Aberto` · `Crédito` · `Pronto para Faturar` · `Atrasado` · `Aguardando Checklist`

---

## 🔒 Segurança

- ⚠️ Adicione `.streamlit/secrets.toml` ao seu `.gitignore`
- Nunca exponha o `secrets.toml` em repositórios públicos
- Para deploy em nuvem (Streamlit Cloud), configure os secrets pela interface web
- Para produção em servidor, use variáveis de ambiente ou cofre de segredos

---

## 🛠️ Bugs Corrigidos vs. Versão Anterior

| Bug | Descrição | Status |
|-----|-----------|--------|
| Case-sensitivity | `str.capitalize()` quebrava filtros de status multi-palavra | ✅ Corrigido |
| Cache incorreto | `@st.cache_data` em `UploadedFile` causava erros de hash | ✅ Corrigido |
| Tabela vazia | `"Aguardando Checklist"` nunca batia com `capitalize()` | ✅ Corrigido |
| Seed global | `np.random.seed(42)` não era thread-safe | ✅ Corrigido |
| Timezone | `strftime` falhava com datas timezone-aware | ✅ Corrigido |
| Sem login | Qualquer pessoa acessava todos os dados | ✅ Implementado |
| Sem filtros | Nenhum filtro interativo disponível | ✅ Implementado |
| Moeda BR | Separadores americanos em valores monetários | ✅ Corrigido |
| Tema escuro | Gráficos com fundo branco no tema escuro | ✅ Corrigido |
| Alertas visuais | Tabela sem coloração por criticidade | ✅ Implementado |

---

## 📦 Dependências

```
streamlit>=1.32.0
pandas>=2.0.0
plotly>=5.18.0
numpy>=1.26.0
openpyxl>=3.1.2
bcrypt>=4.1.0
```
