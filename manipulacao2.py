import pandas as pd

# --- Configurações do Arquivo de Entrada e Saída ---
ARQUIVO_ENTRADA = 'Tabelas/egressos-ceres.csv'
ARQUIVO_SAIDA = 'Tabelas/tempo_medio_curso.csv'

# 1. Carregar o arquivo CSV
try:
    df = pd.read_csv(ARQUIVO_ENTRADA)
    print(f"DataFrame '{ARQUIVO_ENTRADA}' carregado com sucesso.")
except FileNotFoundError:
    print(f"Erro: O arquivo '{ARQUIVO_ENTRADA}' não foi encontrado.")
    exit()

# --- Etapa 1: Filtragem e Tratamento de Tipos ---
cursos_a_remover = ["PEDAGOGIA - PROBÁSICA", "LETRAS", "GESTÃO PÚBLICA"]
df_filtrado = df[~df['nome_curso'].isin(cursos_a_remover)].copy()

colunas_para_int = [
    'ano_conclusao', 
    'ano_ingresso', 
    'periodo_conclusao', 
    'periodo_ingresso'
]
for col in colunas_para_int:
    df_filtrado[col] = df_filtrado[col].astype(int)

# --- Etapa 2: Criação de Colunas Cronológicas e Cálculo do Tempo de Curso ---

# Coluna Semestre em formato String (AAAA.P) para uso como Índice da Tabela
df_filtrado['semestre_conclusao'] = (
    df_filtrado['ano_conclusao'].astype(str) + 
    '.' + 
    df_filtrado['periodo_conclusao'].astype(str)
)

# Cálculo do tempo de curso em semestres
df_filtrado['anos_diff'] = df_filtrado['ano_conclusao'] - df_filtrado['ano_ingresso']
df_filtrado['periodos_diff'] = df_filtrado['periodo_conclusao'] - df_filtrado['periodo_ingresso']

# Fórmula: (Anos * 2) + Diferença de Períodos + 1 (para contar o semestre de conclusão)
df_filtrado['tempo_curso_semestres'] = (
    df_filtrado['anos_diff'] * 2
) + df_filtrado['periodos_diff'] + 1

# Conversão para Anos (Tempo de Curso em Anos = Tempo em Semestres / 2)
df_filtrado['tempo_curso_anos'] = df_filtrado['tempo_curso_semestres'] / 2

# --- Etapa 3: Agrupamento e Cálculo da Média ---

# 1. Criar o ID Único do Curso (ID - Nome)
df_filtrado['id_nome_curso'] = (
    df_filtrado['id_curso'].astype(str) + 
    ' - ' + 
    df_filtrado['nome_curso']
)

# 2. Agrupar pela chave única (ID Semestre) e chave do curso (ID - Nome) para calcular a média
media_por_curso_semestre = (
    df_filtrado
    .groupby(['id_nome_curso', 'semestre_conclusao'])
    ['tempo_curso_anos']
    .mean() # Calcula a MÉDIA do tempo em anos
    .reset_index(name='media_tempo_anos')
)

# --- Etapa 4: Geração da Tabela Semestre x Curso (Pivot Table) ---

# Gerar a Tabela Dinâmica
tabela_tempo_medio = media_por_curso_semestre.pivot_table(
    index='semestre_conclusao',      # Linhas: Semestres (ordenado cronologicamente)
    columns='id_nome_curso',         # Colunas: ID - Nome do Curso (Chave única)
    values='media_tempo_anos',       # Valores: Média de Tempo em Anos
    fill_value=0                     # Preenche semestres sem egressos com 0
)

# Arredondar os valores para duas casas decimais
tabela_tempo_medio = tabela_tempo_medio.round(2)

# --- Etapa FINAL: Salvamento do Arquivo CSV ---

tabela_tempo_medio.to_csv(ARQUIVO_SAIDA)

print("\n" + "="*80)
print(f"✅ SUCESSO! A tabela de tempo médio foi salva em '{ARQUIVO_SAIDA}'")
print("As linhas representam a evolução do tempo médio (em anos) por semestre de conclusão.")
print("="*80)