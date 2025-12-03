import pandas as pd
import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX

# --- Configurações Iniciais ---
ARQUIVO_ENTRADA = 'Tabelas/tempo_medio_curso_ffill.csv' 
SEMESTRES_FUTUROS = 3
ARQUIVO_SAIDA = 'Tabelas/previsao_tempo_medio_curso_SARIMAX.csv'

# Parâmetros SARIMAX (os mesmos usados para a contagem)
SARIMAX_ORDER = (1, 1, 0)
SARIMAX_SEASONAL_ORDER = (1, 0, 0, 2) 

# Funções auxiliares (inalteradas)
def semestre_to_date(semestre_str):
    """Converte 'AAAA.P' para o índice de data inicial do semestre (YYYY-MM-01)."""
    try:
        ano, periodo = map(int, semestre_str.split('.'))
        mes = 1 if periodo == 1 else 7
        return pd.to_datetime(f'{ano}-{mes:02d}-01')
    except:
        return pd.NaT

def date_to_semestre(date):
    """Converte datetime de volta para AAAA.P."""
    if isinstance(date, pd.Timestamp):
        ano = date.year
        periodo = 1 if date.month <= 6 else 2
        return f'{ano}.{periodo}'
    return str(date)

def rodar_previsao_sarimax_tempo(df_tabela, order, seasonal_order):
    """Aplica o SARIMAX coluna por coluna para séries contínuas (Tempo Médio)."""
    
    tabela = df_tabela.copy()
    
    # 1. Limpeza e Conversão de Índice para DatetimeIndex
    tabela.index.name = 'semestre_conclusao'
    tabela = tabela.reset_index() 
    tabela['semestre_conclusao'] = tabela['semestre_conclusao'].astype(str).str.strip() 
    
    tabela['ds'] = tabela['semestre_conclusao'].map(semestre_to_date)
    tabela = tabela.dropna(subset=['ds'])
    tabela_data_only = tabela.drop(columns=['semestre_conclusao']).set_index('ds').sort_index()
    
    tabela_data_only = tabela_data_only.asfreq('6MS') 
    
    previsoes_finais_df = []
    
    # 2. Rodar o SARIMAX para cada coluna (curso)
    for curso_id in tabela_data_only.columns:
        serie = tabela_data_only[curso_id]
        
        # Converte para numérico e trata NaN (FFILL já foi feito, mas garante a numeração)
        serie = pd.to_numeric(serie, errors='coerce')
        
        # Filtra períodos iniciais de zeros/NaNs se existirem (para Tempo Médio, NaNs devem ser FFILL)
        # Encontra o primeiro valor não-NaN/não-zero
        primeiro_valor_valido = serie[serie.notna() & (serie != 0)].index.min()
        
        if pd.isna(primeiro_valor_valido):
            print(f"Aviso: O curso {curso_id} não possui dados válidos para previsão de Tempo Médio.")
            continue
            
        serie_train = serie.loc[primeiro_valor_valido:].copy()
        
        if serie_train.empty or len(serie_train.dropna()) < 10:
            print(f"Aviso: O curso {curso_id} não possui dados suficientes para previsão SARIMAX.")
            continue
            
        try:
            # Fit do Modelo SARIMAX
            modelo = SARIMAX(
                serie_train,
                order=order,
                seasonal_order=seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False
            )
            resultados = modelo.fit(disp=False) 

            # Define os índices de previsão (3 períodos futuros)
            last_date = serie_train.index[-1] 
            start_date_forecast = last_date + pd.offsets.MonthBegin(6)
            end_date_forecast = start_date_forecast + pd.offsets.MonthBegin(6 * (SEMESTRES_FUTUROS - 1))
            
            predicao_sarimax = resultados.get_prediction(
                start=start_date_forecast,
                end=end_date_forecast
            )
            
            yhat = predicao_sarimax.predicted_mean
            
            # Não aplicamos restrição a zero, mas limitamos a 2 casas decimais
            yhat = yhat.round(2)
            
            df_forecast = yhat.to_frame(name=curso_id)
            previsoes_finais_df.append(df_forecast)
            
        except Exception as e:
            print(f"Erro ao prever para o curso {curso_id}: {e}")
            
    # 3. Consolidar Previsões e Dados Originais (Correção de Visualização)
    if not previsoes_finais_df:
        return pd.DataFrame()
        
    df_prev = pd.concat(previsoes_finais_df, axis=1)
    
    # 3.1 Prepara o índice string para o resultado final
    df_prev_string_index = df_prev.index.to_series().apply(date_to_semestre)
    df_prev_string_index.index = df_prev_string_index.values
    
    df_original = df_tabela.copy()
    df_original.index.name = 'semestre_conclusao'
    semestres_originais_str = df_original.index.unique().tolist()
    
    # 3.2 Obtém os 3 semestres futuros do forecast
    semestres_futuros_str = df_prev_string_index.index.tolist()
    
    # 3.3 Mesclagem: Apenas os últimos 5 originais + 3 previstos
    df_original_subset = df_original.loc[semestres_originais_str[-10:]].copy()
    
    df_previsoes_finais = df_prev.loc[df_prev.index.map(lambda x: date_to_semestre(x)).isin(semestres_futuros_str)]
    df_previsoes_finais.index = semestres_futuros_str
    df_previsoes_finais.index.name = 'semestre_conclusao'
    
    df_final = pd.concat([df_original_subset, df_previsoes_finais])
    
    # Formatação Final: Valores contínuos com 2 casas decimais
    df_final = df_final.fillna(0).round(2)

    # 4. Salvar e Exibir
    df_final.to_csv(ARQUIVO_SAIDA)
    print("\n" + "="*90)
    print(f"✅ SUCESSO! Previsão de Tempo Médio Simples com SARIMAX salva em '{ARQUIVO_SAIDA}'")
    print("Previsão (Últimos 5 períodos conhecidos + 3 previstos):")
    print(df_final.tail(SEMESTRES_FUTUROS + 5).to_markdown())
    print("="*90)
    
    return df_final

# --- Execução ---
try:
    df_input = pd.read_csv(ARQUIVO_ENTRADA, index_col=0) 
    rodar_previsao_sarimax_tempo(df_input, SARIMAX_ORDER, SARIMAX_SEASONAL_ORDER)

except FileNotFoundError:
    print(f"Erro: O arquivo '{ARQUIVO_ENTRADA}' não foi encontrado.")
except Exception as e:
    print(f"Erro inesperado durante a execução do script: {e}")