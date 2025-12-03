import pandas as pd

# --- Configurações do Arquivo de Entrada e Saída ---
ARQUIVO_ENTRADA = 'Tabelas/egressos-ceres.csv'
ARQUIVO_SAIDA = 'Tabelas/tempo_medio_curso_ffill.csv'

# 1. Carregar e Filtrar o Arquivo CSV
try:
    df = pd.read_csv(ARQUIVO_ENTRADA)
    print(f"DataFrame '{ARQUIVO_ENTRADA}' carregado com sucesso.")
except FileNotFoundError:
    print(f"Erro: O arquivo '{ARQUIVO_ENTRADA}' não foi encontrado.")
    exit()

cursos_a_remover = ["PEDAGOGIA - PROBÁSICA", "LETRAS", "GESTÃO PÚBLICA"]
df_filtrado = df[~df['nome_curso'].isin(cursos_a_remover)].copy()

# --- 2. Tratamento de Tipos e Cálculo do Tempo de Curso em Anos ---

colunas_para_int = [
    'ano_conclusao', 
    'ano_ingresso', 
    'periodo_conclusao', 
    'periodo_ingresso'
]
for col in colunas_para_int:
    df_filtrado[col] = df_filtrado[col].astype(int)

# Criar identificadores
df_filtrado['semestre_conclusao'] = (
    df_filtrado['ano_conclusao'].astype(str) + 
    '.' + 
    df_filtrado['periodo_conclusao'].astype(str)
)
df_filtrado['id_nome_curso'] = (
    df_filtrado['id_curso'].astype(str) + 
    ' - ' + 
    df_filtrado['nome_curso']
)

# Cálculo do tempo de curso em anos (preciso)
df_filtrado['anos_diff'] = df_filtrado['ano_conclusao'] - df_filtrado['ano_ingresso']
df_filtrado['periodos_diff'] = df_filtrado['periodo_conclusao'] - df_filtrado['periodo_ingresso']
df_filtrado['tempo_curso_semestres'] = (df_filtrado['anos_diff'] * 2) + df_filtrado['periodos_diff'] + 1
df_filtrado['tempo_curso_anos'] = df_filtrado['tempo_curso_semestres'] / 2

# --- 3. Agrupamento e Cálculo da Média Simples ---

# Agrupar e calcular a MÉDIA SIMPLES do tempo em anos por curso e semestre
media_por_curso_semestre = (
    df_filtrado
    .groupby(['id_nome_curso', 'semestre_conclusao'])
    ['tempo_curso_anos']
    .mean()
    .reset_index(name='media_tempo_anos')
)

# --- 4. Geração da Tabela Semestre x Curso (Pivot Table) ---

# Gera a Tabela Dinâmica. Semestres sem egressos resultam em valores NA.
tabela_tempo_medio = media_por_curso_semestre.pivot_table(
    index='semestre_conclusao',      
    columns='id_nome_curso',         
    values='media_tempo_anos',       
    # Não usamos fill_value aqui, permitindo que os valores faltantes sejam NA
)

# --- 5. APLICAÇÃO DO FORWARD FILL (FFILL) - Ponto Chave ---

# Aplica o ffill: valores NA são preenchidos pelo último valor válido (semestre anterior).
# Isso mantém o valor do último semestre com formandos nos semestres sem formandos.
tabela_tempo_medio = tabela_tempo_medio.fillna(method='ffill')

# Os valores NA que SOBRAREM são aqueles no início da série, antes do primeiro egresso de cada curso.
# Estes devem ser preenchidos com 0, conforme solicitado.
tabela_tempo_medio = tabela_tempo_medio.fillna(0)

# Arredondar os valores para duas casas decimais
tabela_tempo_medio = tabela_tempo_medio.round(2)

# --- 6. Salvamento do Arquivo CSV ---

tabela_tempo_medio.to_csv(ARQUIVO_SAIDA)

print("\n" + "="*80)
print(f"✅ SUCESSO! A tabela de tempo médio com FFILL foi salva em '{ARQUIVO_SAIDA}'")
print("Semestres sem egressos foram preenchidos com a média do semestre anterior com formandos.")
print("="*80)