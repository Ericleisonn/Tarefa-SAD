import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import dash
from dash import dcc, html
from dash.dependencies import Input, Output

# --- Configurações de Arquivos ---
# Arquivos Históricos/Brutos
ARQUIVO_EGRESSOS_BRUTOS = 'Tabelas/egressos-ceres.csv'
ARQUIVO_CURSOS_UFRN = 'Tabelas/cursos-ufrn.csv'

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

# Lista de cursos a serem excluídos (IDs ou Nomes parciais, a depender da coluna usada)
CURSOS_EXCLUIDOS = ["PEDAGOGIA - PROBÁSICA", "LETRAS", "GESTÃO PÚBLICA"]

# --- 1. FUNÇÃO PRINCIPAL DE PREPARAÇÃO DOS DADOS BRUTOS (Descritivos) ---
def processar_dados_brutos():
    """Carrega, limpa, mescla e filtra os dados brutos de egressos e cursos."""
    
    try:
        df_egressos = pd.read_csv(ARQUIVO_EGRESSOS_BRUTOS)
        df_cursos = pd.read_csv(ARQUIVO_CURSOS_UFRN, sep=";")
    except FileNotFoundError as e:
        print(f"ERRO: Arquivo de dados brutos não encontrado: {e}.")
        return None
    except pd.errors.ParserError as e:
        print(f"ERRO: Erro de parsing nos arquivos CSV: {e}.")
        return None
    
    df_cursos_reduzido = df_cursos[['id_curso', 'grau_academico', 'unidade_responsavel']]
    df_final = df_egressos.merge(
        df_cursos_reduzido,
        on="id_curso",
        how="left"
    )
    
    if 'nome_curso' in df_final.columns:
        for curso_excluir in CURSOS_EXCLUIDOS:
            df_final = df_final[~df_final['nome_curso'].str.contains(curso_excluir, case=False, na=False)]

    df_final["tempo_conclusao"] = df_final["ano_conclusao"] - df_final["ano_ingresso"]
    df_final["conclusao_semestre"] = (
        df_final["ano_conclusao"].astype(str)
        + "."
        + df_final["periodo_conclusao"].fillna(0).astype(int).astype(str)
    )
    
    df_final['ordem_semestre'] = df_final['ano_conclusao'] + df_final['periodo_conclusao'].fillna(0) / 10
    df_final = df_final.sort_values(by='ordem_semestre').drop(columns=['ordem_semestre'])
    
    return df_final

df_dados_brutos = processar_dados_brutos()

if df_dados_brutos is None:
    print("Falha ao processar dados brutos. Saindo do script.")
    exit()

CURSOS_DISPONIVEIS = sorted(df_dados_brutos['nome_curso'].unique().tolist())


# --- 2. FUNÇÃO DE PREPARAÇÃO DOS DADOS SARIMAX (Previsão) ---

def get_column_mapping(df_sarimax):
    """Cria um mapeamento de Nome Curto (Dropdown) para Coluna Longa (DataFrame)."""
    mapping = {}
    for col in df_sarimax.columns:
        parts = col.split(' - ', 1)
        if len(parts) == 2:
            nome_curso = parts[1].strip()
            mapping[nome_curso] = col
    return mapping

def carregar_e_mesclar_dfs_sarimax(arquivo_historico, arquivo_previsao):
    """Carrega histórico completo e previsão, mesclando e aplicando o filtro de cursos."""
    
    try:
        df_hist = pd.read_csv(arquivo_historico, index_col='semestre_conclusao')
        df_prev_completo = pd.read_csv(arquivo_previsao, index_col='semestre_conclusao')
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Arquivo de previsão SARIMAX não encontrado: {e}")

    for curso_excluir in CURSOS_EXCLUIDOS:
        cols_drop = [col for col in df_hist.columns if curso_excluir.upper() in col.upper()]
        df_hist = df_hist.drop(columns=cols_drop, errors='ignore')
        df_prev_completo = df_prev_completo.drop(columns=cols_drop, errors='ignore')

    semestres_historicos = df_hist.index.tolist()
    semestres_previsao = [s for s in df_prev_completo.index.tolist() if s not in semestres_historicos]
    
    df_previsao_apenas = df_prev_completo.loc[semestres_previsao].copy()
    df_final = pd.concat([df_hist, df_previsao_apenas])
    
    df_final['indice_numerico'] = range(1, len(df_final) + 1)
    
    return df_final, semestres_previsao

try:
    df_contagem, semestres_contagem_prev = carregar_e_mesclar_dfs_sarimax(ARQUIVO_HISTORICO_CONTAGEM, ARQUIVO_PREVISAO_CONTAGEM)
    MAPPING_CONTAGEM = get_column_mapping(df_contagem)

    df_tempo, semestres_tempo_prev = carregar_e_mesclar_dfs_sarimax(ARQUIVO_HISTORICO_TEMPO, ARQUIVO_PREVISAO_TEMPO)
    MAPPING_TEMPO = get_column_mapping(df_tempo)

    df_media, semestres_media_prev = carregar_e_mesclar_dfs_sarimax(ARQUIVO_HISTORICO_MEDIA, ARQUIVO_PREVISAO_MEDIA)
    MAPPING_MEDIA = get_column_mapping(df_media)
    
except FileNotFoundError as e:
    print(f"ERRO CRÍTICO: {e}. Verifique se os arquivos de previsão SARIMAX estão corretos.")
    exit()


# --- 3. FUNÇÃO DE PLOTAGEM SARIMAX ---
def criar_grafico_sarimax(df, cursos_selecionados, titulo_metrica, y_label, semestres_previsao, mapping):
    
    fig = go.Figure()
    if not cursos_selecionados or df.empty:
         fig.update_layout(title=f'{titulo_metrica}: Selecione um curso ou dado indisponível.', yaxis_title=y_label)
         return fig
    
    for curso_nome_curto in cursos_selecionados:
        curso_coluna = mapping.get(curso_nome_curto)
        
        if not curso_coluna or curso_coluna not in df.columns:
            continue
            
        df_historico = df.loc[df.index.difference(semestres_previsao)].copy()
        df_previsao_plot = df.loc[df.index >= df_historico.index[-1]].copy()

        # 1. Histórico
        fig.add_trace(go.Scatter(
            x=df_historico['indice_numerico'], y=df_historico[curso_coluna], mode='lines+markers',
            name=f'{curso_nome_curto} (Histórico)', line=dict(dash='solid'), legendgroup=curso_nome_curto,
            customdata=df_historico.index, hovertemplate=f'<b>Semestre: %{{customdata}}</b><br>Curso: {curso_nome_curto}<br>Valor: %{{y}}<extra></extra>'
        ))
        
        # 2. Previsão
        fig.add_trace(go.Scatter(
            x=df_previsao_plot['indice_numerico'], y=df_previsao_plot[curso_coluna], mode='lines+markers',
            name=f'{curso_nome_curto} (Previsão)', line=dict(dash='dash'), marker=dict(symbol='circle', size=8),
            legendgroup=curso_nome_curto, customdata=df_previsao_plot.index, showlegend=True,
            hovertemplate=f'<b>Semestre: %{{customdata}}</b><br>Curso: {curso_nome_curto}<br>Valor: %{{y}}<extra></extra>'
        ))

    fig.update_layout(
        title=f'{titulo_metrica}: Comparação de Cursos', xaxis_title="Semestre de Conclusão",
        yaxis_title=y_label, hovermode="x unified", legend_title_text='Série Temporal',
        xaxis=dict(
            tickmode='array', tickvals=df['indice_numerico'], ticktext=df.index, tickangle=45
        )
    )
    return fig

# --- 4. FUNÇÃO DE PLOTAGEM DESCRITIVA (Com correção robusta de label 'Quantidade') ---
def criar_grafico_descritivo(df, cursos_selecionados, tipo_grafico, coluna_x, coluna_cor=None, titulo=None, y_label=None, padronizar_y=True):
    df_filtrado = df[df['nome_curso'].isin(cursos_selecionados)]
    
    # Determina os rótulos
    labels = {coluna_x: coluna_x.replace('_', ' ').title()}
    if y_label:
         # Define o label Y para gráficos que usam coluna Y (Boxplot, Scatter)
        labels[y_label] = y_label.replace('_', ' ').title()

    if tipo_grafico == 'histogram':
        # Tentativa de usar 'count' para Plotly Express (fallback para a correção abaixo)
        labels['count'] = 'Quantidade' 
        
        fig = px.histogram(
            df_filtrado, x=coluna_x, color=coluna_cor, 
            barmode='group' if coluna_cor else 'relative',
            title=titulo, nbins=30 if coluna_x == 'ano_conclusao' else None,
            labels=labels
        )
        
        # 🔑 CORREÇÃO ROBUSTA: Forçar o rótulo Y para "Quantidade" após a criação do gráfico
        if padronizar_y:
            fig.update_yaxes(title='Quantidade') 
            
        if coluna_x in ['nome_curso', 'forma_ingresso', 'grau_academico']:
            fig.update_xaxes(categoryorder="total descending")
        
    elif tipo_grafico == 'pie':
        fig = px.pie(df_filtrado, names=coluna_x, title=titulo)
        
    elif tipo_grafico == 'box':
        fig = px.box(df_filtrado, x=coluna_x, y=y_label, color=coluna_cor, title=titulo)
        # Padroniza o rótulo Y do Boxplot
        if y_label == 'tempo_conclusao':
            fig.update_yaxes(title='Tempo de Conclusão (Anos)')
        
    elif tipo_grafico == 'scatter':
        fig = px.scatter(df_filtrado, x=coluna_x, y=y_label, color=coluna_cor, title=titulo)
    
    else:
        fig = go.Figure()

    return fig

# --- 5. LAYOUT DO DASHBOARD UNIFICADO ---
app = dash.Dash(__name__)

app.layout = html.Div(style={'backgroundColor': '#f8f8f8', 'padding': '20px'}, children=[
    html.H1("🎓 Dashboard Egressos CERES: Análise Descritiva e Previsão SARIMAX", 
            style={'textAlign': 'center', 'color': '#333333'}),
    html.Hr(style={'borderTop': '4px solid #aaa'}),
    
    # 🎯 SEÇÃO DE CONTROLE DE FILTRO
    html.Div([
        html.H2("Selecione o(s) Curso(s) para Análise:", style={'fontSize': '1.5em', 'marginTop': '10px'}),
        dcc.Dropdown(
            id='dropdown-curso',
            options=[{'label': i, 'value': i} for i in CURSOS_DISPONIVEIS],
            value=[CURSOS_DISPONIVEIS[0]] if CURSOS_DISPONIVEIS else None,
            multi=True, 
            clearable=True,
            style={'width': '95%', 'minHeight': '40px'}
        ),
    ], style={'padding': '15px', 'backgroundColor': '#e0e0e0', 'borderRadius': '8px', 'marginBottom': '30px'}),

    # --- SEÇÃO 1: GRÁFICOS DE PREVISÃO SARIMAX (SÉRIE TEMPORAL) ---
    html.H2("📈 Previsão de Série Temporal (SARIMAX)", style={'borderLeft': '5px solid blue', 'paddingLeft': '10px'}),
    html.Div([
        dcc.Graph(id='grafico-contagem', className='six columns'),
        dcc.Graph(id='grafico-tempo-medio', className='six columns'),
    ], className='row'),
    dcc.Graph(id='grafico-media-ponderada'),
    html.Hr(),

    # --- SEÇÃO 2: GRÁFICOS DESCRITIVOS (DADOS BRUTOS) ---
    html.H2("🔬 Análise Descritiva Histórica", style={'borderLeft': '5px solid green', 'paddingLeft': '10px', 'marginTop': '30px'}),
    
    html.Div([
        dcc.Graph(id='fig-ano', className='six columns'),
        dcc.Graph(id='fig-sexo', className='six columns'),
    ], className='row'),
    
    html.Div([
        dcc.Graph(id='fig-forma', className='six columns'),
        dcc.Graph(id='fig-grau', className='six columns'),
    ], className='row'),

    html.Div([
        dcc.Graph(id='fig-tempo', className='six columns'), 
        dcc.Graph(id='fig-tempo-curso', className='six columns'),
    ], className='row'),

    html.Div([
        dcc.Graph(id='fig-conclusao-anual'), 
    ]),
    
])

# --- 6. CALLBACKS (Interatividade) ---

@app.callback(
    [Output('grafico-contagem', 'figure'),
     Output('grafico-tempo-medio', 'figure'),
     Output('grafico-media-ponderada', 'figure'),
     Output('fig-ano', 'figure'),
     Output('fig-sexo', 'figure'),
     Output('fig-forma', 'figure'),
     Output('fig-tempo', 'figure'),
     Output('fig-tempo-curso', 'figure'),
     Output('fig-conclusao-anual', 'figure'), 
     Output('fig-grau', 'figure'),
     ],
    [Input('dropdown-curso', 'value')]
)
def atualizar_graficos(cursos_selecionados):
    if not cursos_selecionados:
        return [go.Figure() for _ in range(10)]

    # 1. Gráficos SARIMAX (Previsão)
    fig_contagem = criar_grafico_sarimax(df_contagem, cursos_selecionados, "Contagem de Egressos", "Número de Egressos", semestres_contagem_prev, MAPPING_CONTAGEM)
    fig_tempo = criar_grafico_sarimax(df_tempo, cursos_selecionados, "Tempo Médio de Curso (Simples)", "Semestres", semestres_tempo_prev, MAPPING_TEMPO)
    fig_media = criar_grafico_sarimax(df_media, cursos_selecionados, "Média Acumulada Ponderada", "Média", semestres_media_prev, MAPPING_MEDIA)

    # 2. Gráficos Descritivos

    # 2.1. Egressos por Ano de Conclusão (Gráfico de Linhas)
    df_ano_contagem_linha = (
        df_dados_brutos[df_dados_brutos['nome_curso'].isin(cursos_selecionados)]
        .groupby(['ano_conclusao', 'nome_curso'])
        .size()
        .reset_index(name='Quantidade') 
    )

    fig_ano = px.line(
        df_ano_contagem_linha, 
        x="ano_conclusao", 
        y="Quantidade", 
        color="nome_curso",
        title="Egressos por Ano de Conclusão (Série Temporal)",
        markers=True,
        labels={'ano_conclusao': 'Ano de Conclusão', 'nome_curso': 'Curso'}
    ).update_xaxes(dtick=1, tickangle=45)

    # 2.2. Distribuição por sexo (Pie)
    fig_sexo = criar_grafico_descritivo(df_dados_brutos, cursos_selecionados, 'pie', coluna_x="sexo", titulo="Distribuição por Sexo", padronizar_y=False) 

    # 2.3. Formas de ingresso (Histograma - Label Y corrigido para 'Quantidade')
    fig_forma = criar_grafico_descritivo(df_dados_brutos, cursos_selecionados, 'histogram', coluna_x="forma_ingresso", coluna_cor="nome_curso", titulo="Formas de Ingresso", padronizar_y=True)
    
    # 2.4. Tempo de conclusão (Histograma - Label Y corrigido para 'Quantidade')
    fig_tempo_hist = criar_grafico_descritivo(df_dados_brutos, cursos_selecionados, 'histogram', coluna_x="tempo_conclusao", coluna_cor="nome_curso", titulo="Tempo de Conclusão (Anos)", padronizar_y=True)

    # 2.5. Tempo de conclusão por curso (Boxplot - Label Y corrigido para 'Tempo de Conclusão (Anos)')
    fig_tempo_curso = criar_grafico_descritivo(df_dados_brutos, cursos_selecionados, 'box', coluna_x="nome_curso", y_label="tempo_conclusao", titulo="Tempo de Conclusão por Curso", padronizar_y=False)
    
    # 2.6. Conclusões por Ano (Gráfico de Colunas)
    df_conclusao_anual = (
        df_dados_brutos[df_dados_brutos['nome_curso'].isin(cursos_selecionados)]
        .groupby(['ano_conclusao', 'nome_curso'])
        .size()
        .reset_index(name='Quantidade') 
    )
    
    fig_conclusao_anual = px.bar(
        df_conclusao_anual, 
        x="ano_conclusao", 
        y="Quantidade", 
        color="nome_curso", 
        barmode='group',
        title="Total de Conclusões por Ano",
        labels={'ano_conclusao': 'Ano de Conclusão', 'nome_curso': 'Curso'}
    ).update_xaxes(dtick=1, tickangle=45)
    
    # 2.7. Grau acadêmico (Histograma - Label Y corrigido para 'Quantidade')
    fig_grau = criar_grafico_descritivo(df_dados_brutos, cursos_selecionados, 'histogram', coluna_x="grau_academico", coluna_cor="nome_curso", titulo="Egressos por Grau Acadêmico", padronizar_y=True)
    
    return (fig_contagem, fig_tempo, fig_media, 
            fig_ano, fig_sexo, fig_forma, fig_tempo_hist, fig_tempo_curso, fig_conclusao_anual, fig_grau)

# --- 7. Execução ---
if __name__ == '__main__':
    print("\nAcesse http://127.0.0.1:8050/ no seu navegador.")
    app.run(debug=True)