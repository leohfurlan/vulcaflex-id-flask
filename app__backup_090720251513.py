import requests
import os
import json
from flask import Flask, render_template, request, redirect, url_for
from collections import defaultdict

app = Flask(__name__)

# --- Configurações ---
API_BASE_URL = "http://172.172.191.253"
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "SUA_CHAVE_API_AQUI")

# --- Funções Auxiliares ---

def flatten_if_nested(data_list):
    """Garante que a lista de dados para os dropdowns seja sempre plana."""
    if not data_list or not isinstance(data_list, list):
        return []
    if data_list and isinstance(data_list[0], list):
        return [item[0] for item in data_list if item]
    return data_list

def get_plate_styles():
    """Retorna um dicionário com as classes de estilo para cada estado de espessura."""
    return {
        10: {'text': 'text-green-600', 'border': 'border-green-600', 'label': '>10mm', 'color': '#16a34a'},
        8: {'text': 'text-yellow-500', 'border': 'border-yellow-500', 'label': '<10mm', 'color': '#eab308'},
        5: {'text': 'text-orange-400', 'border': 'border-orange-400', 'label': '<8mm', 'color': '#fb923c'},
        0: {'text': 'text-red-600', 'border': 'border-red-600', 'label': '<5mm', 'color': '#dc2626'},
        -1: {'text': 'text-gray-800', 'border': 'border-gray-800', 'label': 'Erro', 'color': '#1f2937'}
    }

def prepare_chart_data(plates_details, styles):
    """Prepara os dados de todas as placas para o gráfico JavaScript."""
    chart_data = {}
    if not plates_details:
        return chart_data
    
    for plate in plates_details:
        # A API retorna 'placa' no /tambor_agora e 'codigo' em outras rotas. Normalizamos para 'codigo'.
        plate_code = plate.get('codigo') or plate.get('placa')
        if not plate_code:
            continue

        tick_map = {10: 5, 8: 4, 5: 3, 0: 2, -1: 1}
        
        chart_data[plate_code] = {
            'labels': list(plate['secoes'].keys()),
            'values': [tick_map.get(v, 1) for v in plate['secoes'].values()],
            'colors': [styles.get(v, {}).get('color', '#000') for v in plate['secoes'].values()]
        }
    return chart_data

from collections import defaultdict

def calculate_dashboard_metrics(api_response, plates_details):
    """Calcula as métricas para o dashboard."""
    
    # --- Passo 1: Inspecionar os dados de entrada ---
    print("--- 🔍 Início da execução de calculate_dashboard_metrics ---")
    print("\n[DEBUG] Conteúdo de 'api_response':")
    print(api_response)
    print("\n[DEBUG] Conteúdo de 'plates_details':")
    print(plates_details)
    
    if not api_response:
        print("\n[INFO] 'api_response' está vazio. Retornando None.")
        return None

    dashboard = {
        'process_count': api_response.get('qnt_processos', 0),
        'transporter_count': api_response.get('qnt_transportadores', 0),
        'barrel_count': api_response.get('qnt_tambores', 0),
        'plate_count': api_response.get('qnt_placas', 0),
        'plates_details': plates_details
    }
    
    # --- Passo 2: Verificar o dicionário inicial ---
    print("\n[DEBUG] Dashboard após a criação inicial:")
    print(dashboard)

    thickness_counts = defaultdict(int)
    for plate in plates_details:
        if 'secoes' in plate and isinstance(plate['secoes'], dict):
            section_values = [v for v in plate['secoes'].values() if isinstance(v, (int, float))]
            if section_values:
                min_thickness = min(section_values)
                thickness_counts[min_thickness] += 1
    
    dashboard['thickness_counts'] = dict(thickness_counts)
    
    # --- Passo 3: Inspecionar o resultado final ---
    print("\n[DEBUG] Conteúdo final do Dashboard antes de retornar:")
    print(dashboard)
    print("\n--- ✅ Fim da execução ---")
    
    return dashboard

# --- Rotas da Aplicação ---

@app.route('/')
def home():
    return redirect(url_for('status_page'))

@app.route('/status')
def status_page():
    selected_unity = request.args.get('unidade')
    selected_process = request.args.get('processo')
    selected_transporter = request.args.get('transportador')
    selected_barrel = request.args.get('tambor')

    unities_data, processes_data, transporters_data, barrels_data = [], [], [], []
    dashboard_data = None
    location_data = None
    chart_data_json = '{}'
    error_message = None
    plate_styles = get_plate_styles()

    try:
        # --- PASSO 1: Obter dados para os dropdowns e contagens gerais ---
        info_params = {
            'unidade': selected_unity or '',
            'processo': selected_process or '',
            'transportador': selected_transporter or '',
            'ID': selected_barrel or '' # ID aqui ajuda a obter a lista correta de tambores
        }
        info_response = requests.get(f"{API_BASE_URL}/tambor_info", params=info_params, timeout=5)
        info_response.raise_for_status()
        info_data = info_response.json()

        # Preencher dropdowns com base na resposta de /tambor_info
        unities_data = flatten_if_nested(info_data.get('unidades', []))
        processes_data = flatten_if_nested(info_data.get('processos', []))
        transporters_data = flatten_if_nested(info_data.get('transportadores', []))
        barrels_data = flatten_if_nested(info_data.get('lista', []))
        
        # Extrair localização
        if 'localizacao' in info_data and info_data['localizacao']:
            loc = info_data['localizacao']
            if loc.get('lat') and loc.get('lng'):
                location_data = {'lat': loc['lat'], 'lng': loc['lng']}

        # --- PASSO 2: Obter detalhes das placas com /tambor_agora ---
        plates_details = []
        # Só chamamos /tambor_agora se todos os filtros estiverem preenchidos
        if all([selected_unity, selected_process, selected_transporter, selected_barrel]):
            agora_params = {
                'unidade': selected_unity,
                'processo': selected_process,
                'transportador': selected_transporter,
                'ID': selected_barrel
            }
            agora_response = requests.get(f"{API_BASE_URL}/tambor_agora", params=agora_params, timeout=5)
            agora_response.raise_for_status()
            plates_details = agora_response.json().get('espessuraAtual', [])
        else:
            # Se não houver filtro completo, usamos os detalhes de placas de /tambor_info, se existirem
            plates_details = info_data.get('espessuraAtual', [])

        # --- PASSO 3: Calcular métricas e preparar dados para o template ---
        dashboard_data = calculate_dashboard_metrics(info_data, plates_details)
        if dashboard_data and 'plates_details' in dashboard_data:
            chart_data_json = json.dumps(prepare_chart_data(dashboard_data['plates_details'], plate_styles))

    except requests.exceptions.RequestException as e:
        error_message = f"Erro ao comunicar com a API: {e}"
        print(error_message)

    return render_template(
        'status.html',
        title='Dashboard',
        subtitle='Visão geral do sistema',
        unities=unities_data,
        processes=processes_data,
        transporters=transporters_data,
        barrels=barrels_data,
        selected_values={
            'unidade': selected_unity,
            'processo': selected_process,
            'transportador': selected_transporter,
            'tambor': selected_barrel
        },
        dashboard_data=dashboard_data,
        location_data=json.dumps(location_data),
        maps_api_key=GOOGLE_MAPS_API_KEY,
        plate_styles=plate_styles,
        chart_data=chart_data_json,
        error=error_message
    )

@app.route('/logout')
def logout():
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
