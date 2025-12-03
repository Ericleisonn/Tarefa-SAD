import pandas as pd

# --- Configurações do Arquivo de Entrada e Saída ---
ARQUIVO_ENTRADA = 'Tabelas/egressos-ceres.csv'
ARQUIVO_SAIDA = 'Tabelas/media_acumulada_ponderada_ffill.csv'

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

# --- 3. Agrupamento Inicial e Cálculo do Tempo Ponderado ---

# Agrupamos pelo ID Único do Curso e Semestre para obter a média e a contagem de egressos por semestre.
df_agrupado = df_filtrado.groupby(['id_nome_curso', 'semestre_conclusao']).agg(
    media_tempo_semestre=('tempo_curso_anos', 'mean'), # Média do semestre
    total_egressos=('id_curso', 'size')              # Contagem do semestre
).reset_index()

# Calcular o tempo total (Tempo Médio * Nº de Alunos) para ser acumulado
df_agrupado['tempo_total_ponderado'] = (
    df_agrupado['media_tempo_semestre'] * df_agrupado['total_egressos']
)

# --- 4. Cálculo da Média Acumulada Ponderada (Ponto Central) ---

# Ordenar para garantir que o 'cumsum' seja cronológico
df_agrupado = df_agrupado.sort_values(by=['id_nome_curso', 'semestre_conclusao'])

# Calcular as somas acumuladas DENTRO de cada grupo de curso
df_agrupado['tempo_total_acumulado'] = df_agrupado.groupby('id_nome_curso')['tempo_total_ponderado'].cumsum()
df_agrupado['egressos_acumulados'] = df_agrupado.groupby('id_nome_curso')['total_egressos'].cumsum()

# Calcular a Média Acumulada Ponderada: Tempo Total Acumulado / Egressos Acumulados
df_agrupado['media_acumulada_ponderada'] = (
    df_agrupado['tempo_total_acumulado'] / 
    df_agrupado['egressos_acumulados']
)

# --- 5. Geração da Tabela Semestre x Curso (Pivot Table) ---

# Pivoteamento para o formato final solicitado
tabela_media_acumulada = df_agrupado.pivot_table(
    index='semestre_conclusao',         
    columns='id_nome_curso',            
    values='media_acumulada_ponderada', 
    # Não preenchemos com 0 aqui, permitindo que os valores faltantes sejam NA
)

# --- 6. APLICAÇÃO DO FORWARD FILL (FFILL) - Ponto Chave da Sua Solicitação ---

# Aplica o ffill: valores NA (sem egressos no semestre) são preenchidos pelo último valor válido (semestre anterior).
tabela_media_acumulada = tabela_media_acumulada.fillna(method='ffill')

# Preenche com 0 os valores NA remanescentes (antes do primeiro egresso de cada curso)
tabela_media_acumulada = tabela_media_acumulada.fillna(0)

# Arredondar os valores para duas casas decimais
tabela_media_acumulada = tabela_media_acumulada.round(2)

# --- 7. Salvamento do Arquivo CSV ---

tabela_media_acumulada.to_csv(ARQUIVO_SAIDA)

print("\n" + "="*80)
print(f"✅ SUCESSO! A tabela de média acumulada ponderada com FFILL foi salva em '{ARQUIVO_SAIDA}'")
print("Cada valor é a média histórica de tempo de curso (em anos) de todos os formandos do curso até aquele semestre.")
print("Semestres sem egressos foram preenchidos com o valor do último semestre conhecido.")
print("="*80)