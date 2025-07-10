import requests
import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash
from collections import defaultdict
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__)

# --- Configurações ---
app.secret_key = os.getenv('SECRET_KEY', 'uma-chave-padrao-para-desenvolvimento')
API_BASE_URL = "http://172.172.191.253"
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
ADMIN_USER = "administrador"
ADMIN_PASS = "5959"

# --- Funções Auxiliares ---

def flatten_if_nested(data_list):
    if not data_list or not isinstance(data_list, list): return []
    if data_list and isinstance(data_list[0], list): return [item[0] for item in data_list if item]
    return data_list

def get_plate_styles():
    return {
        10: {'text': 'text-green-600', 'border': 'border-green-600', 'label': '>10mm', 'color': '#16a34a'},
        8: {'text': 'text-yellow-500', 'border': 'border-yellow-500', 'label': '<10mm', 'color': '#eab308'},
        5: {'text': 'text-orange-400', 'border': 'border-orange-400', 'label': '<8mm', 'color': '#fb923c'},
        0: {'text': 'text-red-600', 'border': 'border-red-600', 'label': '<5mm', 'color': '#dc2626'},
        -1: {'text': 'text-gray-800', 'border': 'border-gray-800', 'label': 'Erro', 'color': '#1f2937'}
    }

def prepare_chart_data(plates_details, styles):
    chart_data = {}
    if not plates_details: return chart_data
    for plate in plates_details:
        plate_code = plate.get('codigo') or plate.get('placa')
        if not plate_code: continue
        tick_map = {10: 5, 8: 4, 5: 3, 0: 2, -1: 1}
        chart_data[plate_code] = {
            'labels': list(plate.get('secoes', {}).keys()),
            'values': [tick_map.get(v, 1) for v in plate.get('secoes', {}).values()],
            'colors': [styles.get(v, {}).get('color', '#000') for v in plate.get('secoes', {}).values()]
        }
    return chart_data

def get_summary_for_scope(selected_unity=None, selected_process=None, selected_transporter=None):
    summary = {'general_stats': defaultdict(int), 'thickness_counts': defaultdict(int), 'locations': []}
    try:
        unities_to_scan = [selected_unity] if selected_unity else flatten_if_nested(requests.get(f"{API_BASE_URL}/cliente_info", timeout=10).json().get('unidades', []))
        summary['general_stats']['unity_count'] = len(unities_to_scan)
        for unity in unities_to_scan:
            processes_to_scan = [selected_process] if selected_process else flatten_if_nested(requests.get(f"{API_BASE_URL}/cliente_info", params={'unidade': unity}, timeout=10).json().get('processos', []))
            if not selected_unity: summary['general_stats']['process_count'] += len(processes_to_scan)
            for process in processes_to_scan:
                transporters_to_scan = [selected_transporter] if selected_transporter else flatten_if_nested(requests.get(f"{API_BASE_URL}/cliente_info", params={'unidade': unity, 'processo': process}, timeout=10).json().get('transportadores', []))
                if not selected_process: summary['general_stats']['transporter_count'] += len(transporters_to_scan)
                for transporter in transporters_to_scan:
                    barrel_res = requests.get(f"{API_BASE_URL}/cliente_info", params={'unidade': unity, 'processo': process, 'transportador': transporter}, timeout=10)
                    barrels = flatten_if_nested(barrel_res.json().get('IDs', []))
                    if not selected_transporter: summary['general_stats']['barrel_count'] += len(barrels)
                    for barrel_id in barrels:
                        params = {'unidade': unity, 'processo': process, 'transportador': transporter, 'ID': barrel_id}
                        info_res = requests.get(f"{API_BASE_URL}/tambor_info", params=params, timeout=10)
                        if info_res.ok:
                            info_data = info_res.json()
                            lat, lng = info_data.get('latitude'), info_data.get('longitude')
                            if lat and lng:
                                # AJUSTE: A estrutura de 'locations' já contém todos os dados necessários
                                # para criar os links de filtro no mapa. Cada item da lista tem as
                                # informações de unidade, processo, transportador e tambor.
                                summary['locations'].append({
                                    'lat': float(lat), 'lng': float(lng), 'title': barrel_id,
                                    'unidade': unity, 'processo': process, 
                                    'transportador': transporter, 'tambor': barrel_id
                                })
                        agora_res = requests.get(f"{API_BASE_URL}/tambor_agora", params=params, timeout=10)
                        if agora_res.ok:
                            plates = agora_res.json().get('espessuraAtual', [])
                            for plate in plates:
                                section_values = [v for v in plate.get('secoes', {}).values() if isinstance(v, (int, float))]
                                if section_values: summary['thickness_counts'][min(section_values)] += 1
        if selected_process: summary['general_stats']['process_count'] = 1
        if selected_transporter: summary['general_stats']['transporter_count'] = 1
    except requests.exceptions.RequestException as e:
        print(f"ERRO durante a busca do resumo: {e}")
    return summary

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

    context = {
        'title': 'Dashboard de Monitoramento', 'subtitle': 'Visão geral do sistema de tambores',
        'unities': [], 'processes': [], 'transporters': [], 'barrels': [],
        'selected_values': {'unidade': selected_unity, 'processo': selected_process, 'transportador': selected_transporter, 'tambor': selected_barrel},
        'dashboard_data': {}, 'error': None, 'maps_api_key': GOOGLE_MAPS_API_KEY, 'plate_styles': get_plate_styles()
    }

    try:
        unities_response = requests.get(f"{API_BASE_URL}/cliente_info", timeout=5)
        context['unities'] = flatten_if_nested(unities_response.json().get('unidades', []))
        if selected_unity:
            process_response = requests.get(f"{API_BASE_URL}/cliente_info", params={'unidade': selected_unity}, timeout=5)
            context['processes'] = flatten_if_nested(process_response.json().get('processos', []))
        if selected_unity and selected_process:
            transporter_response = requests.get(f"{API_BASE_URL}/cliente_info", params={'unidade': selected_unity, 'processo': selected_process}, timeout=5)
            context['transporters'] = flatten_if_nested(transporter_response.json().get('transportadores', []))
        if selected_unity and selected_process and selected_transporter:
            barrel_response = requests.get(f"{API_BASE_URL}/cliente_info", params={'unidade': selected_unity, 'processo': selected_process, 'transportador': selected_transporter}, timeout=5)
            context['barrels'] = flatten_if_nested(barrel_response.json().get('IDs', []))

        if selected_barrel:
            params = {'unidade': selected_unity, 'processo': selected_process, 'transportador': selected_transporter, 'ID': selected_barrel}
            info_response = requests.get(f"{API_BASE_URL}/tambor_info", params=params, timeout=5)
            info_response.raise_for_status()
            tambor_info_data = info_response.json()
            agora_response = requests.get(f"{API_BASE_URL}/tambor_agora", params=params, timeout=5)
            agora_response.raise_for_status()
            plates_details = agora_response.json().get('espessuraAtual', [])
            thickness_counts = defaultdict(int)
            for plate in plates_details:
                section_values = [v for v in plate.get('secoes', {}).values() if isinstance(v, (int, float))]
                if section_values: thickness_counts[min(section_values)] += 1
            
            context['dashboard_data'] = {
                'info': tambor_info_data, 'plates_details': plates_details, 'thickness_counts': dict(thickness_counts),
                'location_data': json.dumps([{'lat': float(tambor_info_data.get('latitude', 0)), 'lng': float(tambor_info_data.get('longitude', 0)), 'title': selected_barrel}]),
                'chart_data': json.dumps(prepare_chart_data(plates_details, context['plate_styles'])),
                'general_stats': {
                    'unity_count': len(context['unities']), 'process_count': len(context['processes']),
                    'transporter_count': len(context['transporters']), 'barrel_count': len(context['barrels'])
                }
            }
        else:
            summary = get_summary_for_scope(selected_unity, selected_process, selected_transporter)
            context['dashboard_data'] = {
                'general_stats': summary['general_stats'], 'thickness_counts': summary['thickness_counts'],
                'location_data': json.dumps(summary['locations']), 'plates_details': None, 'chart_data': '{}'
            }
    except requests.exceptions.RequestException as e:
        context['error'] = f"Erro ao comunicar com a API: {e}"
    except Exception as e:
        context['error'] = f"Ocorreu um erro inesperado: {e}"
        import traceback
        traceback.print_exc()

    return render_template('status.html', **context)

@app.route('/remove_tambor', methods=['POST'])
def remove_barrel():
    unidade = request.form.get('unidade')
    processo = request.form.get('processo')
    transportador = request.form.get('transportador')
    barrel_id = request.form.get('tambor')
    params = {'acessousuario': ADMIN_USER, 'acessosenha': ADMIN_PASS, 'unidade': unidade, 'processo': processo, 'transportador': transportador, 'ID': barrel_id}
    try:
        response = requests.get(f"{API_BASE_URL}/remove_tambor", params=params, timeout=5)
        response.raise_for_status()
        flash(f"Tambor {barrel_id} removido com sucesso!", "success")
    except requests.exceptions.RequestException as e:
        flash(f"Erro ao remover o tambor: {e}", "error")
    return redirect(url_for('status_page', unidade=unidade, processo=processo, transportador=transportador))

@app.route('/relatorio/<unidade>/<processo>/<transportador>/<barrel_id>')
def relatorio_tambor(unidade, processo, transportador, barrel_id):
    drum_data = None
    error_message = None
    params = {'unidade': unidade, 'processo': processo, 'transportador': transportador, 'ID': barrel_id}
    
    try:
        response = requests.get(f"{API_BASE_URL}/tambor_info", params=params, timeout=5)
        response.raise_for_status()
        drum_data = response.json()
        if 'dataInstalacao' in drum_data:
            try:
                date_obj = datetime.strptime(drum_data['dataInstalacao'], '%a, %d %b %Y %H:%M:%S %Z')
                drum_data['dataInstalacaoFormatada'] = date_obj.strftime('%d/%m/%Y')
            except (ValueError, TypeError):
                drum_data['dataInstalacaoFormatada'] = drum_data['dataInstalacao']
    except requests.exceptions.RequestException as e:
        error_message = f"Erro ao buscar dados do tambor: {e}"
        
    return render_template(
        'relatorio.html', title=f"Relatório do Tambor {barrel_id}", drum_data=drum_data,
        error=error_message, maps_api_key=GOOGLE_MAPS_API_KEY, now=datetime.now(),
        unidade=unidade, processo=processo, transportador=transportador, barrel_id=barrel_id
    )

if __name__ == '__main__':
    app.run(debug=True, port=5001)
