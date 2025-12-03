import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html

# ============================================
# Carregamento do dataset
# ============================================

df_egressos = pd.read_csv("Tabelas/egressos-ceres.csv")      # <- arquivo egressos
df_cursos = pd.read_csv("Tabelas/cursos-ufrn.csv", sep=";")  # <- arquivo cursos UFRN


# ============================================
# FUNÇÕES PARA TRATAMENTO DE DADOS
# ============================================

def adicionar_grau_academico(df_egressos, df_cursos):
    """
    Pega o id_curso dos egressos, busca no dataset de cursos
    e adiciona a coluna 'grau_academico' ao dataframe final.
    """
    df_cursos_reduzido = df_cursos[['id_curso', 'grau_academico','unidade_responsavel']]
    df_final = df_egressos.merge(
        df_cursos_reduzido,
        on="id_curso",
        how="left"
    )
    print(df_final)
    return df_final


def obter_grau_academico_por_curso(df_egressos, df_cursos):
    """
    Retorna cada id_curso único dos egressos
    e seus respectivos graus acadêmicos encontrados no dataset de cursos.
    """
    ids_unicos = df_egressos["id_curso"].dropna().unique()
    df_filtrado = df_cursos[df_cursos["id_curso"].isin(ids_unicos)]
    df_filtrado = df_filtrado[["nome", "id_curso", "grau_academico"]]

    df_filtrado_cursoid = (
        df_filtrado
        .groupby("id_curso")
        .head(2)
        .reset_index(drop=True)
    )
    return df_filtrado_cursoid


def processar_dados():
    """
    Processa os dados e retorna df_egressos incluindo o grau acadêmico.
    """
    return adicionar_grau_academico(df_egressos, df_cursos)

# Processa os dados 1 vez
df_final = processar_dados()




# ============================================
# GRÁFICOS
# ============================================

# 1. Egressos por ano de conclusão
fig_ano = px.histogram(
    df_final,
    x="ano_conclusao",
    title="Egressos por Ano de Conclusão",
    nbins=30,
)

# 2. Egressos por curso
fig_curso = px.histogram(
    df_final,
    x="nome_curso",
    title="Egressos por Curso",
).update_xaxes(categoryorder="total descending")

# 3. Distribuição por sexo
fig_sexo = px.pie(
    df_final,
    names="sexo",
    title="Distribuição por Sexo",
)

# 4. Formas de ingresso
fig_forma = px.histogram(
    df_final,
    x="forma_ingresso",
    title="Formas de Ingresso"
).update_xaxes(categoryorder="total descending")

# 5. Tempo de conclusão
df_final["tempo_conclusao"] = (
    df_final["ano_conclusao"] - df_final["ano_ingresso"]
)

fig_tempo = px.histogram(
    df_final,
    x="tempo_conclusao",
    title="Tempo de Conclusão (Ano de Conclusão - Ano de Ingresso)",
)

# 6. Tempo de conclusão por curso
fig_tempo_curso = px.box(
    df_final,
    x="nome_curso",
    y="tempo_conclusao",
    title="Tempo de Conclusão por Curso"
)

# 7. Conclusão por semestre
df_final["conclusao_semestre"] = (
    df_final["ano_conclusao"].astype(str)
    + "."
    + df_final["periodo_conclusao"].astype(int).astype(str)
)

fig_conclusao_semestre = px.histogram(
    df_final,
    x="conclusao_semestre",
    title="Conclusões por Semestre"
).update_xaxes(categoryorder="total descending")

# 8. Ingressos por ano e curso
fig_ingresso_ano_curso = px.histogram(
    df_final,
    x="ano_ingresso",
    color="nome_curso",
    barmode="group",
    title="Ingressos por Ano e Curso"
)

# 9. Relação ingresso x conclusão
fig_ingresso_conclusao = px.scatter(
    df_final,
    x="ano_ingresso",
    y="ano_conclusao",
    color="nome_curso",
    title="Relação entre Ano de Ingresso e Ano de Conclusão"
)

# 10. Grau acadêmico
fig_grau = px.histogram(
    df_final,
    x="grau_academico",
    title="Quantidade de Egressos por Grau Acadêmico"
).update_xaxes(categoryorder="total descending")


# ============================================
# Dashboard em Dash
# ============================================

app = Dash(__name__)

app.layout = html.Div([
    html.H1("Dashboard de Egressos – CERES", style={"textAlign": "center"}),

    dcc.Graph(figure=fig_ano),
    dcc.Graph(figure=fig_curso),
    dcc.Graph(figure=fig_sexo),
    dcc.Graph(figure=fig_forma),
    dcc.Graph(figure=fig_tempo),
    dcc.Graph(figure=fig_tempo_curso),
    dcc.Graph(figure=fig_conclusao_semestre),
    dcc.Graph(figure=fig_ingresso_ano_curso),
    dcc.Graph(figure=fig_ingresso_conclusao),
    dcc.Graph(figure=fig_grau),
])

# ============================================
# Execução
# ============================================

df_graus = obter_grau_academico_por_curso(df_egressos, df_cursos)


if __name__ == "__main__":
    app.run(debug=True)
