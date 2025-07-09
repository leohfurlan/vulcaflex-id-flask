# Primeiro, instale a biblioteca se ainda não tiver:
# pip install requests

import requests

# URL base da API
BASE_URL = "http://172.172.191.253"

# --- Exemplo 1: Consultar Informações de um Tambor ---
# Endpoint: /tambor_info
# Documentação: [cite: 11, 37]
# Exemplo CURL: [cite: 94]

def consultar_tambor(unidade, processo, transportador, tambor_id):
    """
    Busca informações de um tambor específico.
    """
    endpoint = f"{BASE_URL}/tambor_info"
    params = {
        'unidade': unidade,
        'processo': processo,
        'transportador': transportador,
        'ID': tambor_id
    }
    
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()  # Lança um erro para respostas com código de falha (4xx ou 5xx)
        
        print(f"Sucesso! Resposta para /tambor_info (Tambor: {tambor_id}):")
        print(response.json())
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Erro ao chamar a API: {e}")
        return None

# Como usar a função:
# consultar_tambor(unidade="LLK", processo="teste", transportador="BHTEC", tambor_id="CT0135")


# --- Exemplo 2: Obter a Última Medição de Espessura ---
# Endpoint: /tambor_agora
# Documentação: [cite: 14, 52]
# Exemplo CURL: [cite: 108]

def obter_medicao_agora(unidade, processo, transportador, tambor_id):
    """
    Busca a medição de espessura mais recente de um tambor.
    """
    endpoint = f"{BASE_URL}/tambor_agora"
    
    # ATENÇÃO: A documentação formal (XML) especifica nomes diferentes para os parâmetros.
    # Versão do Contrato: unidadeCliente, processoUnidade, transportadorCorreia [cite: 53]
    # Versão do Exemplo (CURL): unidade, processo, transportador
    # É mais seguro usar a versão dos exemplos que funcionaram.
    params = {
        'unidade': unidade,
        'processo': processo,
        'transportador': transportador,
        'ID': tambor_id
    }
    
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        
        print(f"Sucesso! Resposta para /tambor_agora (Tambor: {tambor_id}):")
        print(response.json())
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Erro ao chamar a API: {e}")
        return None

# Como usar a função:
# obter_medicao_agora(unidade="LLK", processo="teste", transportador="LS", tambor_id="CT0135")


# --- Exemplo 3: Obter Histórico de Medições ---
# Endpoint: /tambor_historico
# Documentação: [cite: 12]
# Exemplo CURL: [cite: 95]

def obter_historico_tambor(unidade, processo, transportador, tambor_id, data_inicio, data_fim):
    """
    Busca o histórico de medições de um tambor em um período.
    """
    endpoint = f"{BASE_URL}/tambor_historico"
    params = {
        'unidade': unidade,
        'processo': processo,
        'transportador': transportador,
        'ID': tambor_id,
        'dataInicio': data_inicio,
        'dataFim': data_fim
    }
    
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        
        print(f"Sucesso! Resposta para /tambor_historico (Tambor: {tambor_id}):")
        print(response.json())
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Erro ao chamar a API: {e}")
        return None

# Como usar a função:
# obter_historico_tambor("LLK", "teste", "LS", "CT0135", "2025-01-01", "2025-05-05")

consultar_tambor("LLK", "teste", "BHTEC", "CT0135")
#obter_medicao_agora("LLK", "teste", "LS", "CT0135")
#obter_historico_tambor("LLK", "teste", "LS", "CT0134", "2024-01-01", "2025-07-05")