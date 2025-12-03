import pandas as pd
import plotly.graph_objects as go
import dash
from dash import dcc, html
from dash.dependencies import Input, Output

# --- 1. Carregar os Dados de Previsão ---
# Verifique se os nomes dos arquivos correspondem aos gerados anteriormente.
ARQUIVO_PREVISAO_CONTAGEM = 'Tabelas/previsao_contagem_egressos.csv'
ARQUIVO_PREVISAO_TEMPO = 'Tabelas/previsao_tempo_medio_curso.csv'
ARQUIVO_PREVISAO_MEDIA = 'Tabelas/previsao_media_acumulada_ponderada.csv'

# --- Configurações de Arquivos ---
# Arquivos Originais (Série Histórica Completa)
ARQUIVO_HISTORICO_CONTAGEM = 'Tabelas/egressos_por_semestre.csv' 
ARQUIVO_HISTORICO_TEMPO = 'Tabelas/tempo_medio_curso_ffill.csv'
ARQUIVO_HISTORICO_MEDIA = 'Tabelas/media_acumulada_ponderada_ffill.csv'

# --- 1. Função de Carregamento e Mesclagem dos Dados (Inalterada) ---
def carregar_e_mesclar_dfs(arquivo_historico, arquivo_previsao):
    df_hist = pd.read_csv(arquivo_historico, index_col='semestre_conclusao')
    df_prev_completo = pd.read_csv(arquivo_previsao, index_col='semestre_conclusao')
    
    semestres_historicos = df_hist.index.tolist()
    semestres_previsao = [s for s in df_prev_completo.index.tolist() if s not in semestres_historicos]
    
    df_previsao_apenas = df_prev_completo.loc[semestres_previsao].copy()
    
    df_final = pd.concat([df_hist, df_previsao_apenas])
    df_final['indice_numerico'] = range(1, len(df_final) + 1)
    
    return df_final, semestres_previsao

try:
    df_contagem, semestres_contagem_prev = carregar_e_mesclar_dfs(ARQUIVO_HISTORICO_CONTAGEM, ARQUIVO_PREVISAO_CONTAGEM)
    df_tempo, semestres_tempo_prev = carregar_e_mesclar_dfs(ARQUIVO_HISTORICO_TEMPO, ARQUIVO_PREVISAO_TEMPO)
    df_media, semestres_media_prev = carregar_e_mesclar_dfs(ARQUIVO_HISTORICO_MEDIA, ARQUIVO_PREVISAO_MEDIA)
    
except FileNotFoundError as e:
    print(f"ERRO: Arquivo não encontrado - {e}. Certifique-se de que os nomes dos arquivos estão corretos.")
    exit()

# Extrair a lista de cursos (colunas)
cursos = [col for col in df_contagem.columns if col != 'indice_numerico']

# --- 2. Inicializar o Aplicativo Dash ---
app = dash.Dash(__name__)

# --- 3. Função de Geração de Gráfico ADAPTADA para MÚLTIPLOS CURSOS ---
def criar_grafico(df, cursos_selecionados, titulo_metrica, y_label, semestres_previsao):
    
    fig = go.Figure()
    
    # ⚠️ Iterar sobre todos os cursos selecionados
    for curso in cursos_selecionados:
        
        # Separa os dataframes para plotar com cores e estilos diferentes
        df_historico = df.loc[df.index.difference(semestres_previsao)].copy()
        df_previsao_plot = df.loc[df.index >= df_historico.index[-1]].copy()

        # 1. Histórico (Dados Conhecidos - Série Completa)
        fig.add_trace(go.Scatter(
            x=df_historico['indice_numerico'], 
            y=df_historico[curso], 
            mode='lines+markers',
            name=f'{curso} (Histórico)',
            line=dict(dash='solid'), # Cor será gerenciada automaticamente pelo Plotly
            legendgroup=curso, # Agrupa as duas traces (histórico e previsão) na legenda
            customdata=df_historico.index,
            hovertemplate='<b>%{customdata}</b><br>Curso: ' + curso + '<br>Valor: %{y}<extra></extra>'
        ))
        
        # 2. Previsão (Projeção SARIMAX - Conectada ao último ponto do histórico)
        fig.add_trace(go.Scatter(
            x=df_previsao_plot['indice_numerico'], 
            y=df_previsao_plot[curso], 
            mode='lines+markers',
            name=f'{curso} (Previsão)',
            line=dict(dash='dash'), # Linha tracejada para a previsão
            marker=dict(symbol='circle', size=8),
            showlegend=True, # Mostrar a previsão na legenda, se desejado
            legendgroup=curso,
            customdata=df_previsao_plot.index,
            hovertemplate='<b>%{customdata}</b><br>Curso: ' + curso + '<br>Valor: %{y}<extra></extra>'
        ))

    # Atualizar Layout: Usar os rótulos de semestre no eixo X
    fig.update_layout(
        title=f'{titulo_metrica}: Comparação de Cursos',
        xaxis_title="Semestre de Conclusão",
        yaxis_title=y_label,
        hovermode="x unified",
        legend_title_text='Série Temporal',
        # Definir os ticks do eixo X usando o índice numérico e os rótulos de semestre
        xaxis=dict(
            tickmode='array',
            tickvals=df['indice_numerico'],
            ticktext=df.index,
            tickangle=45
        )
    )
    
    return fig

# --- 4. Layout do Dashboard (HTML) ---
app.layout = html.Div(style={'backgroundColor': '#f8f8f8', 'padding': '20px'}, children=[
    html.H1("🎓 Dashboard de Previsão de Egressos - Comparativo", 
            style={'textAlign': 'center', 'color': '#333333'}),
    html.Hr(style={'borderTop': '2px solid #ccc'}),
    
    html.Div([
        html.Label("Selecione o(s) Curso(s):", style={'fontWeight': 'bold', 'marginRight': '10px'}),
        dcc.Dropdown(
            id='dropdown-curso',
            options=[{'label': i, 'value': i} for i in cursos],
            value=[cursos[0]],  # Valor padrão: lista com o primeiro curso
            multi=True, # 🔑 MUDANÇA CRUCIAL: Permite seleção múltipla
            clearable=True,
            style={'width': '95%'}
        ),
    ], style={'marginBottom': '20px'}),
    
    html.Div(id='conteudo-graficos', children=[
        dcc.Graph(id='grafico-contagem'),
        dcc.Graph(id='grafico-tempo-medio'),
        dcc.Graph(id='grafico-media-ponderada'),
    ])
])

# --- 5. Callbacks (Interatividade) ---
@app.callback(
    [Output('grafico-contagem', 'figure'),
     Output('grafico-tempo-medio', 'figure'),
     Output('grafico-media-ponderada', 'figure')],
    [Input('dropdown-curso', 'value')]
)
def atualizar_graficos(cursos_selecionados):
    # Se nada estiver selecionado, retornar gráficos vazios
    if not cursos_selecionados:
        return go.Figure(), go.Figure(), go.Figure()

    # Passamos a lista de cursos e a lista de semestres de previsão para a função criar_grafico
    fig_contagem = criar_grafico(df_contagem, cursos_selecionados, "Contagem de Egressos", "Número de Egressos", semestres_contagem_prev)
    fig_tempo = criar_grafico(df_tempo, cursos_selecionados, "Tempo Médio de Curso (Simples)", "Semestres", semestres_tempo_prev)
    fig_media = criar_grafico(df_media, cursos_selecionados, "Média Acumulada Ponderada", "Média", semestres_media_prev)

    return fig_contagem, fig_tempo, fig_media

# --- 6. Execução do Servidor ---
if __name__ == '__main__':
    print("\nExecutando o Dash app com seleção múltipla. Acesse http://127.0.0.1:8050/ no seu navegador.")
    app.run(debug=True)