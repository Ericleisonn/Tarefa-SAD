import pandas as pd
from dash import Dash, dcc, html, Input, Output
import plotly.express as px

# -----------------------------
# CONFIG / LEITURA
# -----------------------------
CSV_FILE = "Tabelas/egressos-ceres.csv"

# Certifique-se de que o arquivo existe antes de rodar
try:
    df = pd.read_csv(CSV_FILE)
except FileNotFoundError:
    print(f"Erro: Arquivo não encontrado em {CSV_FILE}")
    exit()

lista = ["PEDAGOGIA - PROBÁSICA","LETRAS","GESTÃO PÚBLICA"]
df = df[~df["nome_curso"].isin(lista)]

# renomear colunas para nomes usados no script
df = df.rename(columns={
    "id_curso": "id_curso",
    "nome_curso": "curso",
    "ano_conclusao": "ano",
    "periodo_conclusao": "periodo",
    "ano_ingresso": "ano_ingresso",
    "periodo_ingresso": "periodo_ingresso"
})

# garantir tipos numéricos
df["ano"] = pd.to_numeric(df["ano"], errors="coerce")
df["periodo"] = pd.to_numeric(df["periodo"], errors="coerce")
df["ano_ingresso"] = pd.to_numeric(df["ano_ingresso"], errors="coerce")
df["periodo_ingresso"] = pd.to_numeric(df["periodo_ingresso"], errors="coerce")

# remover linhas sem ano ou periodo de conclusão
df = df[df["ano"].notna() & df["periodo"].notna()]
df["ano"] = df["ano"].astype(int)
df["periodo"] = df["periodo"].astype(int)

# criar rótulo legível para eixo x
df["periodo_label"] = df["ano"].astype(str) + "." + df["periodo"].astype(str)

# -----------------------------
# CALCULAR TEMPO DE CURSO
# -----------------------------
df["tempo_curso"] = (df["ano"] + df["periodo"] / 2) - (df["ano_ingresso"] + df["periodo_ingresso"] / 2)

# -----------------------------
# AGREGAÇÕES POR CURSO x PERÍODO
# -----------------------------

# 1) quantidade de concluintes
df_cnt = (
    df.groupby(["id_curso", "curso", "ano", "periodo", "periodo_label"])
      .size()
      .rename("quantidade")
      .reset_index()
)

# 2) média simples do tempo e soma do tempo (para ponderar)
df_media = (
    df.groupby(["id_curso", "curso", "ano", "periodo", "periodo_label"], as_index=False)
      .agg(tempo_medio=("tempo_curso", "mean"), soma_tempo=("tempo_curso", "sum"))
)

# -----------------------------
# CRIAR LISTA GLOBAL ORDENADA DE PERIODOS
# -----------------------------
periodos_ordenados = (
    df_cnt[["ano", "periodo", "periodo_label"]]
    .drop_duplicates()
    .sort_values(["ano", "periodo"])
    .reset_index(drop=True)
)
category_periodos = periodos_ordenados["periodo_label"].tolist()

# -----------------------------
# GERAR BASE COMPLETA (todos cursos x todos periodos)
# -----------------------------
cursos = df_cnt[["id_curso", "curso"]].drop_duplicates().reset_index(drop=True)

# criar DataFrame produto cartesiano (id_curso x periodos)
base = pd.MultiIndex.from_product(
    [cursos["id_curso"].unique(), periodos_ordenados["periodo_label"]],
    names=["id_curso", "periodo_label"]
).to_frame(index=False)

# juntar nome do curso
base = base.merge(cursos, on="id_curso", how="left")

# recuperar ano/periodo numericos no base
base[["ano", "periodo"]] = base["periodo_label"].str.split(".", expand=True).astype(int)

# --- Merge de Quantidade (para grafico_quantidade) ---
df_cnt_full = base.merge(df_cnt, on=["id_curso", "curso", "ano", "periodo", "periodo_label"], how="left")
df_cnt_full["quantidade"] = df_cnt_full["quantidade"].fillna(0).astype(int)


# --- Merge de Média (para graficos_media) ---
df_media_full = base.merge(df_media, on=["id_curso", "curso", "ano", "periodo", "periodo_label"], how="left")

# Garante que 'soma_tempo' exista e preenche NaNs com 0 para o cumsum ser seguro
df_media_full["soma_tempo"] = df_media_full["soma_tempo"].fillna(0)

# Recupera a coluna de quantidade da df_cnt_full
df_media_full = df_media_full.merge(df_cnt_full[['id_curso', 'periodo_label', 'quantidade']], 
                                    on=['id_curso', 'periodo_label'], 
                                    how='left', 
                                    suffixes=('_drop', ''))
df_media_full = df_media_full.drop(columns=['quantidade_drop'], errors='ignore')


# -----------------------------
# CALCULAR MÉDIA ACUMULADA PONDERADA E PREENCHER BRECHAS
# -----------------------------
df_media_full = df_media_full.sort_values(["id_curso", "ano", "periodo"]).reset_index(drop=True)

# calcular cumsums por curso
df_media_full["soma_tempo_cum"] = df_media_full.groupby("id_curso")["soma_tempo"].cumsum()
df_media_full["qtd_cum"] = df_media_full.groupby("id_curso")["quantidade"].cumsum()

# média acumulada ponderada: NaN quando qtd_cum == 0
df_media_full["media_acumulada_ponderada"] = df_media_full["soma_tempo_cum"] / df_media_full["qtd_cum"]
df_media_full.loc[df_media_full["qtd_cum"] == 0, "media_acumulada_ponderada"] = pd.NA

# *** NOVO: PREENCHE OS VALORES NaN/NA (antes do 1º concluinte) COM ZERO ***
df_media_full["media_acumulada_ponderada"] = df_media_full["media_acumulada_ponderada"].fillna(0)
# *************************************************************************


# -----------------------------
# PREENCHER BRECHAS EM tempo_medio (FFILL e depois 0)
# -----------------------------
# 1. Aplicar FFILL (Forward Fill) por curso, para pegar o valor do período anterior.
df_media_full["tempo_medio_preenchido"] = (
    df_media_full.groupby("id_curso")["tempo_medio"]
    .ffill() 
)

# 2. Preencher os NaNs remanescentes (casos onde não há dado anterior no curso) com 0.
df_media_full["tempo_medio_preenchido"] = df_media_full["tempo_medio_preenchido"].fillna(0)


# -----------------------------
# DASH APP
# -----------------------------
app = Dash(__name__)

app.layout = html.Div([
    html.H1("Dashboard de Egressos – CERES", style={"textAlign": "center"}),

    html.Label("Selecione cursos para comparar:", style={"fontWeight": "bold"}),
    dcc.Dropdown(
        id="dropdown_cursos",
        options=[
            {"label": f"{row['curso']} (ID {row['id_curso']})", "value": row["id_curso"]}
            for _, row in cursos.iterrows()
        ],
        multi=True,
        placeholder="Escolha um ou mais cursos..."
    ),

    dcc.Tabs([
        dcc.Tab(label="Quantidade por Período", children=[
            dcc.Graph(id="grafico_quantidade")
        ]),
        dcc.Tab(label="Tempo Médio por Período (Preenchido)", children=[
            dcc.Graph(id="grafico_media")
        ]),
        dcc.Tab(label="Média Acumulada Ponderada (Preenchida)", children=[
            dcc.Graph(id="grafico_media_acumulada")
        ])
    ])
])

# -----------------------------
# CALLBACKS
# -----------------------------
@app.callback(
    Output("grafico_quantidade", "figure"),
    Input("dropdown_cursos", "value")
)
def atualizar_grafico_quantidade(ids_cursos):
    if not ids_cursos:
        return px.line(title="Selecione um curso para visualizar os dados")

    dff = df_cnt_full[df_cnt_full["id_curso"].isin(ids_cursos)].copy()
    dff = dff.sort_values(["ano", "periodo"])

    fig = px.line(
        dff,
        x="periodo_label",
        y="quantidade",
        color="curso",
        markers=True,
        labels={
            "quantidade": "Quantidade de Concludentes",
            "periodo_label": "Ano.Período",
            "curso": "Curso"
        },
        title="Quantidade de Concludentes por Período"
    )

    fig.update_xaxes(categoryorder="array", categoryarray=category_periodos, tickangle=-45)
    fig.update_layout(plot_bgcolor="white", title_x=0.5)

    return fig


@app.callback(
    Output("grafico_media", "figure"),
    Input("dropdown_cursos", "value")
)
def atualizar_grafico_media(ids_cursos):
    if not ids_cursos:
        return px.line(title="Selecione um curso para visualizar os dados")

    dff = df_media_full[df_media_full["id_curso"].isin(ids_cursos)].copy()
    dff = dff.sort_values(["ano", "periodo"])

    fig = px.line(
        dff,
        x="periodo_label",
        y="tempo_medio_preenchido", 
        color="curso",
        markers=True,
        labels={
            "tempo_medio_preenchido": "Tempo Médio (anos)",
            "periodo_label": "Ano.Período",
            "curso": "Curso"
        },
        title="Tempo Médio de Curso por Período (Brechas Preenchidas)"
    )

    fig.update_xaxes(categoryorder="array", categoryarray=category_periodos, tickangle=-45)
    fig.update_layout(plot_bgcolor="white", title_x=0.5)

    return fig


@app.callback(
    Output("grafico_media_acumulada", "figure"),
    Input("dropdown_cursos", "value")
)
def atualizar_grafico_media_acumulada(ids_cursos):
    if not ids_cursos:
        return px.line(title="Selecione um curso para visualizar os dados")

    dff = df_media_full[df_media_full["id_curso"].isin(ids_cursos)].copy()
    dff = dff.sort_values(["id_curso", "ano", "periodo"])

    fig = px.line(
        dff,
        x="periodo_label",
        y="media_acumulada_ponderada",
        color="curso",
        markers=True,
        labels={
            "media_acumulada_ponderada": "Média Acumulada Ponderada (anos)",
            "periodo_label": "Ano.Período",
            "curso": "Curso"
        },
        title="Tempo Médio Acumulado Ponderado (Preenchido)"
    )

    fig.update_xaxes(categoryorder="array", categoryarray=category_periodos, tickangle=-45)
    fig.update_layout(plot_bgcolor="white", title_x=0.5)

    return fig

# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)