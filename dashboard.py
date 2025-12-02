import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html

# ============================================
# Carregamento do dataset
# ============================================
df = pd.read_csv("Tabelas/egressos-ceres.csv")

# ============================================
# Gráficos
# ============================================

# 1. Egressos por ano de conclusão
fig_ano = px.histogram(
    df,
    x="ano_conclusao",
    title="Egressos por Ano de Conclusão",
    nbins=30,
)

# 2. Egressos por curso
fig_curso = px.histogram(
    df,
    x="nome_curso",
    title="Egressos por Curso",
).update_xaxes(categoryorder="total descending")

# 3. Distribuição por sexo
fig_sexo = px.pie(
    df,
    names="sexo",
    title="Distribuição por Sexo",
)

# 4. Formas de ingresso
fig_forma = px.histogram(
    df,
    x="forma_ingresso",
    title="Formas de Ingresso"
).update_xaxes(categoryorder="total descending")

# 5. Tempo de conclusão (anos)
df["tempo_conclusao"] = df["ano_conclusao"] - df["ano_ingresso"]

fig_tempo = px.histogram(
    df,
    x="tempo_conclusao",
    title="Tempo de Conclusão (Ano de Conclusão - Ano de Ingresso)",
)

# 6. Tempo de conclusão por curso
fig_tempo_curso = px.box(
    df,
    x="nome_curso",
    y="tempo_conclusao",
    title="Tempo de Conclusão por Curso"
)

# Criando coluna de conclusão por semestre (ex: 2009.1)
df["conclusao_semestre"] = (
    df["ano_conclusao"].astype(str) + "." + df["periodo_conclusao"].astype(int).astype(str)
)

# 7. Conclusões por semestre
fig_conclusao_semestre = px.histogram(
    df,
    x="conclusao_semestre",
    title="Conclusões por Semestre"
).update_xaxes(categoryorder="total descending")

# 8. Ingressos por ano e curso
fig_ingresso_ano_curso = px.histogram(
    df,
    x="ano_ingresso",
    color="nome_curso",
    barmode="group",
    title="Ingressos por Ano e Curso"
)

# 9. Relação ingresso x conclusão (dispersão)
fig_ingresso_conclusao = px.scatter(
    df,
    x="ano_ingresso",
    y="ano_conclusao",
    color="nome_curso",
    title="Relação entre Ano de Ingresso e Ano de Conclusão"
)



# ============================================
# DASHBOARD EM DASH
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
    
])

if __name__ == "__main__":
    app.run(debug=True)
