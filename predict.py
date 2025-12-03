import pandas as pd
import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX

# --- Configurações Iniciais ---
ARQUIVO_ENTRADA = 'Tabelas/egressos_por_semestre.csv'
SEMESTRES_FUTUROS = 3
ARQUIVO_SAIDA = 'Tabelas/previsao_contagem_egressos_prophet.csv'

# Parâmetros SARIMAX robustos
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

def rodar_previsao_sarimax(df_tabela, order, seasonal_order):
    """Aplica o SARIMAX coluna por coluna com restrição zero."""
    
    tabela = df_tabela.copy()
    
    # 1. Limpeza e Conversão de Índice para DatetimeIndex
    tabela.index.name = 'semestre_conclusao'
    tabela = tabela.reset_index() 
    tabela['semestre_conclusao'] = tabela['semestre_conclusao'].astype(str).str.strip() 
    
    tabela['ds'] = tabela['semestre_conclusao'].map(semestre_to_date)
    tabela = tabela.dropna(subset=['ds'])
    tabela_data_only = tabela.drop(columns=['semestre_conclusao']).set_index('ds').sort_index()
    
    tabela_data_only = tabela_data_only.asfreq('6MS') 
    tabela_data_only = tabela_data_only.fillna(0)
    
    previsoes_finais_df = []
    
    # 2. Rodar o SARIMAX para cada coluna (curso)
    for curso_id in tabela_data_only.columns:
        serie = tabela_data_only[curso_id]
        serie = pd.to_numeric(serie, errors='coerce').fillna(0)
        
        primeiro_valor = (serie > 0).idxmax()
        serie_train = serie.loc[primeiro_valor:].copy()
        
        if serie_train.empty or len(serie_train) < 10:
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

            # *** CORREÇÃO AQUI: Forçar o início da previsão para o próximo período ***
            
            # Último ponto de dado conhecido
            last_date = serie.index[-1] 
            
            # Ponto de início da previsão (2025.1)
            start_date_forecast = last_date + pd.offsets.MonthBegin(6)
            
            # Ponto final da previsão (3 períodos depois, 2026.1)
            end_date_forecast = start_date_forecast + pd.offsets.MonthBegin(6 * (SEMESTRES_FUTUROS - 1))
            
            predicao_sarimax = resultados.get_prediction(
                start=start_date_forecast, # Começa a previsão no próximo período
                end=end_date_forecast      # Termina a previsão no terceiro período futuro (2026.1)
            )
            
            yhat = predicao_sarimax.predicted_mean
            
            # Restrição a Zero (Corrigindo valores negativos)
            yhat = np.maximum(0, yhat).round(0) 
            
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
    
    # 3.2 Obtém os 3 semestres futuros do forecast, garantindo que não há duplicação
    semestres_futuros_str = df_prev_string_index.index.tolist()
    
    # 3.3 Mesclagem: Apenas os últimos 5 originais + 3 previstos
    df_original_subset = df_original.loc[semestres_originais_str[-10:]].copy()
    
    # Filtra apenas as 3 linhas de previsão
    df_previsoes_finais = df_prev.loc[df_prev.index.map(lambda x: date_to_semestre(x)).isin(semestres_futuros_str)]
    df_previsoes_finais.index = semestres_futuros_str
    df_previsoes_finais.index.name = 'semestre_conclusao'
    
    df_final = pd.concat([df_original_subset, df_previsoes_finais])
    
    # Formatação Final: Contagem deve ser inteira
    df_final = df_final.round(0).astype('Int64').fillna(0)

    # 4. Salvar e Exibir
    df_final.to_csv(ARQUIVO_SAIDA)
    print("\n" + "="*90)
    print(f"✅ SUCESSO! Previsão de Contagem de Egressos com SARIMAX salva em '{ARQUIVO_SAIDA}'")
    print("Previsão (Últimos 5 períodos conhecidos + 3 previstos):")
    print(df_final.tail(SEMESTRES_FUTUROS + 5).to_markdown())
    print("="*90)
    
    return df_final

# --- Execução ---
try:
    df_input = pd.read_csv(ARQUIVO_ENTRADA, index_col=0) 
    rodar_previsao_sarimax(df_input, SARIMAX_ORDER, SARIMAX_SEASONAL_ORDER)

except FileNotFoundError:
    print(f"Erro: O arquivo '{ARQUIVO_ENTRADA}' não foi encontrado.")
except Exception as e:
    print(f"Erro inesperado durante a execução do script: {e}")