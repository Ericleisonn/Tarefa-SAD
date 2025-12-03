import pandas as pd
import os

# --- Configurações do Arquivo de Entrada e Saída ---
ARQUIVO_ENTRADA = 'Tabelas/egressos-ceres.csv'
ARQUIVO_SAIDA = 'Tabelas/egressos_por_semestre.csv'

# 1. Carregar o arquivo CSV
try:
    df = pd.read_csv(ARQUIVO_ENTRADA)
    print(f"DataFrame '{ARQUIVO_ENTRADA}' carregado com sucesso.")
except FileNotFoundError:
    print(f"Erro: O arquivo '{ARQUIVO_ENTRADA}' não foi encontrado. Certifique-se de que ele está no mesmo diretório do script.")
    exit()

# --- Etapa 1: Filtragem e Remoção de Cursos ---
cursos_a_remover = ["PEDAGOGIA - PROBÁSICA", "LETRAS", "GESTÃO PÚBLICA"]

# Filtrar o DataFrame, mantendo apenas as linhas onde 'nome_curso' NÃO está na lista
df_filtrado = df[~df['nome_curso'].isin(cursos_a_remover)].copy()

print(f"Linhas removidas: {len(df) - len(df_filtrado)}")

# --- Etapa 2: Tratamento de Tipos de Dados ---
colunas_para_int = [
    'ano_conclusao', 
    'ano_ingresso', 
    'periodo_conclusao', 
    'periodo_ingresso'
]

# Converter colunas para inteiro (int)
for col in colunas_para_int:
    df_filtrado[col] = df_filtrado[col].astype(int)

# --- Etapa 3: Criação de Colunas Cronológicas (Conclusão) ---

# Coluna Semestre em formato String (AAAA.P) para uso como Índice da Tabela
df_filtrado['semestre_conclusao'] = (
    df_filtrado['ano_conclusao'].astype(str) + 
    '.' + 
    df_filtrado['periodo_conclusao'].astype(str)
)

# Coluna ID Semestre em formato Inteiro (AAAAP) (Opcional, mas útil para o cálculo interno)
df_filtrado['id_semestre_conclusao_inteiro'] = (
    df_filtrado['ano_conclusao'] * 10
) + df_filtrado['periodo_conclusao']

# --- Etapa 4: Agrupamento e Contagem de Egressos ---

# 1. Criar o ID Único do Curso (ID - Nome)
df_filtrado['id_nome_curso'] = (
    df_filtrado['id_curso'].astype(str) + 
    ' - ' + 
    df_filtrado['nome_curso']
)

# 2. Agrupar e Contar
contagem_por_conclusao = (
    df_filtrado
    .groupby(['id_nome_curso', 'semestre_conclusao'])
    .size() 
    .reset_index(name='total_egressos')
)

# --- Etapa 5: Geração da Tabela Semestre x Curso (Pivot Table) ---

# Gerar a Tabela Dinâmica com semestre nas linhas e ID do curso nas colunas
tabela_semestre_id_curso = contagem_por_conclusao.pivot_table(
    index='semestre_conclusao',  # Linhas: Semestres (ordenado cronologicamente)
    columns='id_nome_curso',     # Colunas: ID - Nome do Curso (Chave única)
    values='total_egressos',    # Valores: Contagem de Egressos
    fill_value=0                # Preenche semestres sem egressos com 0
)

# --- Etapa FINAL: Salvamento do Arquivo CSV ---

tabela_semestre_id_curso.to_csv(ARQUIVO_SAIDA)

print("\n" + "="*80)
print(f"✅ SUCESSO! A tabela final foi salva em '{ARQUIVO_SAIDA}'")
print("As linhas são os semestres cronológicos e as colunas são os cursos únicos (ID - Nome).")
print("="*80)