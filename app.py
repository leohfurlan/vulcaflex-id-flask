import requests
import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
from collections import defaultdict
from dotenv import load_dotenv
from datetime import datetime, date
#print("--- [DEBUG] 1: Imports feitos", flush=True)
load_dotenv()

app = Flask(__name__)

# --- Configurações ---
app.secret_key = os.getenv('SECRET_KEY', 'uma-chave-padrao-para-desenvolvimento')
API_BASE_URL = "http://172.172.191.253"
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
ADMIN_USER = "administrador"
ADMIN_PASS = "5959"
#print("--- [DEBUG] 2: variaveis carregadas", flush=True)

# --- Estrutura de Usuários (Em memória para este exemplo) ---
# Em produção, isso seria um banco de dados
USERS = {
    'administrador': {"password": "5959", "level": "administrador", "email": "teste", "unidade": "TODAS"},
    "llk": {"password": "123", "level": "usuario", "email": "teste1", "unidade": "BHTEC"},
}
#print("--- [DEBUG] 2: variaveis carregadas", flush=True)


# --- Decorators de Autenticação ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash("Você precisa estar logado para ver esta página.", "warning")
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash("Você precisa estar logado para ver esta página.", "warning")
            return redirect(url_for('login_page'))
        if session.get('level') != 'administrador':
            flash("Você não tem permissão para acessar esta página.", "error")
            return redirect(url_for('status_page'))
        return f(*args, **kwargs)
    return decorated_function

# --- Funções Auxiliares ---

# Decorator para garantir que o usuário esteja logado
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login_page', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def flatten_if_nested(data_list):
    if not data_list or not isinstance(data_list, list): return []
    if data_list and isinstance(data_list[0], list): return [item[0] for item in data_list if item]
    return data_list

def get_plate_styles():
    return {
        10: {'text': 'text-green-800', 'border': 'border-green-300', 'bg': 'bg-green-100', 'label': '>10mm', 'color': '#16a34a'},
        8: {'text': 'text-yellow-800', 'border': 'border-yellow-300', 'bg': 'bg-yellow-100', 'label': '<10mm', 'color': '#eab308'},
        5: {'text': 'text-orange-800', 'border': 'border-orange-300', 'bg': 'bg-orange-100', 'label': '<8mm', 'color': '#fb923c'},
        0: {'text': 'text-red-800', 'border': 'border-red-300', 'bg': 'bg-red-100', 'label': '<5mm', 'color': '#dc2626'},
        -1: {'text': 'text-gray-800', 'border': 'border-gray-400', 'bg': 'bg-gray-200', 'label': 'Erro', 'color': '#1f2937'}
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
        # ==================================================================
        # INÍCIO DA LÓGICA DE CORREÇÃO
        # ==================================================================

        # 1. Busca TODAS as unidades válidas da API primeiro.
        all_unities_res = requests.get(f"{API_BASE_URL}/cliente_info", timeout=10)
        all_unities_res.raise_for_status()
        valid_unities = flatten_if_nested(all_unities_res.json().get('unidades', []))

        unities_to_scan = []
        # 2. Determina quais unidades realmente processar.
        if selected_unity:
            # Se uma unidade foi selecionada, só a processe se ela for válida.
            if selected_unity in valid_unities:
                unities_to_scan = [selected_unity]
        else:
            # Se nenhuma foi selecionada, processa todas as unidades válidas.
            unities_to_scan = valid_unities
        
        # 3. A contagem de unidades AGORA reflete a realidade.
        summary['general_stats']['unity_count'] = len(unities_to_scan)

        # ==================================================================
        # FIM DA LÓGICA DE CORREÇÃO
        # ==================================================================

        # O resto da função agora opera sobre a lista 'unities_to_scan', que é garantidamente válida.
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


def prepare_history_chart_data(history_data, plate_code):
    """
    Filtra e processa os dados do histórico de uma placa para exibição no gráfico.
    - Seleciona o último registro de cada dia.
    - Mapeia os valores de espessura para o gráfico.
    """
    if not history_data or not plate_code:
        return {}

    # Equivalente ao tickMap no JS
    tick_map = {-1: 1, 0: 2, 5: 3, 8: 4, 10: 5}

    history_map = {}
    
    # 1. Filtra por código da placa e obtém o último registro de cada dia
    for record in history_data:
        if record.get('codigo') == plate_code or record.get('placa') == plate_code:
            # Converte a string da data para um objeto datetime
            record_date = datetime.strptime(record['data'], '%a, %d %b %Y %H:%M:%S %Z')
            day_key = record_date.strftime('%Y-%m-%d')

            # Se o dia ainda não está no mapa, ou se o registro atual é mais recente, armazena
            if day_key not in history_map or record_date > history_map[day_key]['date_obj']:
                history_map[day_key] = {
                    'date_obj': record_date,
                    'secoes': record['secoes']
                }
    
    # Ordena os registros pela data
    sorted_history = sorted(history_map.values(), key=lambda x: x['date_obj'])

    # 2. Prepara os dados para o Chart.js
    labels = []
    section1_data = []
    section2_data = []
    section3_data = []

    for record in sorted_history:
        labels.append(record['date_obj'].strftime('%d/%m'))
        secoes = record['secoes']
        
        # O nome das seções pode variar ('1', 'secao1'), então tratamos ambos
        s1_key = 'secao1' if 'secao1' in secoes else '1'
        s2_key = 'secao2' if 'secao2' in secoes else '2'
        s3_key = 'secao3' if 'secao3' in secoes else '3'

        section1_data.append(tick_map.get(secoes.get(s1_key), 1))
        section2_data.append(tick_map.get(secoes.get(s2_key), 1))
        section3_data.append(tick_map.get(secoes.get(s3_key), 1))

    return {
        'labels': labels,
        'datasets': [
            {'label': 'Seção 1', 'data': section1_data, 'borderColor': '#8884d8', 'tension': 0.3},
            {'label': 'Seção 2', 'data': section2_data, 'borderColor': '#82ca9d', 'tension': 0.3},
            {'label': 'Seção 3', 'data': section3_data, 'borderColor': '#ff7300', 'tension': 0.3},
        ]
    }

# --- Rotas da Aplicação ---
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = USERS.get(username)

        if user and user['password'] == password:
            session['logged_in'] = True
            session['username'] = username
            session['level'] = user['level']
            session['unidade'] = user['unidade']
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('status_page'))
        else:
            flash('Credenciais inválidas. Tente novamente.', 'error')
    return render_template('login.html', title="Login")

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login_page'))

@app.route('/')
def home():
    #print("--- [DEBUG] 3: carregou app flask", flush=True)
    return redirect(url_for('login_page'))

# --- Rotas de Gerenciamento de Usuário ---
@app.route('/admin/users')
@admin_required
def manage_users_page():
    # Passa a lista de unidades para o template, para usar no formulário de adição
    unities = []
    try:
        res = requests.get(f"{API_BASE_URL}/cliente_info", timeout=5)
        unities = flatten_if_nested(res.json().get('unidades', []))
    except requests.exceptions.RequestException as e:
        flash(f"Não foi possível carregar as unidades da API: {e}", "error")
    return render_template('manage_users.html', users=USERS, unities=unities, title="Gerenciar Usuários")

@app.route('/admin/add_user', methods=['POST'])
@admin_required
def add_user():
    username = request.form.get('username')
    password = request.form.get('password')
    level = request.form.get('level')
    email = request.form.get('email')
    unidade = request.form.get('unidade') # Novo campo
    
    if username in USERS:
        flash(f"Usuário '{username}' já existe.", "error")
    else:
        USERS[username] = {"password": password, "level": level, "email": email, "unidade": unidade}
        flash(f"Usuário '{username}' criado com sucesso.", "success")
    return redirect(url_for('manage_users_page'))

@app.route('/admin/edit_user/<username>', methods=['GET', 'POST'])
@admin_required
def edit_user_page(username):
    user_to_edit = USERS.get(username)
    if not user_to_edit:
        flash("Usuário não encontrado.", "error")
        return redirect(url_for('manage_users_page'))

    if request.method == 'POST':
        # Atualiza os dados
        new_password = request.form.get('password')
        user_to_edit['level'] = request.form.get('level')
        user_to_edit['email'] = request.form.get('email')
        user_to_edit['unidade'] = request.form.get('unidade')
        
        if new_password: # Só atualiza a senha se uma nova for fornecida
            user_to_edit['password'] = new_password
        
        flash(f"Usuário '{username}' atualizado com sucesso.", "success")
        return redirect(url_for('manage_users_page'))
    
    # Busca unidades para o dropdown do formulário de edição
    unities = []
    try:
        res = requests.get(f"{API_BASE_URL}/cliente_info", timeout=5)
        unities = flatten_if_nested(res.json().get('unidades', []))
    except requests.exceptions.RequestException as e:
        flash(f"Não foi possível carregar as unidades da API: {e}", "error")
    
    return render_template('edit_user.html', user=user_to_edit, username=username, unities=unities, title=f"Editar Usuário {username}")


@app.route('/admin/delete_user', methods=['POST'])
@admin_required
def delete_user():
    username = request.form.get('username')
    
    if username == session.get('username'):
        flash("Você não pode remover seu próprio usuário.", "error")
        return redirect(url_for('manage_users_page'))

    if username in USERS:
        del USERS[username]
        flash(f"Usuário '{username}' removido com sucesso.", "success")
    else:
        flash(f"Usuário '{username}' não encontrado.", "error")
        
    return redirect(url_for('manage_users_page'))

# --- Rotas de Consulta Protegidas ---

@app.route('/status')
@login_required
def status_page():
    # Inicializa o contexto com valores padrão
    context = {
        'title': 'Dashboard de Monitoramento', 'subtitle': 'Visão geral do sistema de tambores',
        'unities': [], 'processes': [], 'transporters': [], 'barrels': [],
        'selected_values': {},
        'dashboard_data': {
            'general_stats': {'unity_count': 0, 'process_count': 0, 'transporter_count': 0, 'barrel_count': 0},
            'thickness_counts': {}, 'location_data': '[]', 'chart_data': '{}'
        },
        'error': None, 'maps_api_key': GOOGLE_MAPS_API_KEY, 'plate_styles': get_plate_styles()
    }

    # Parâmetros da URL
    selected_unity = request.args.get('unidade')
    selected_process = request.args.get('processo')
    selected_transporter = request.args.get('transportador')
    selected_barrel = request.args.get('tambor')

    # Permissões do usuário da sessão
    user_level = session.get('level')
    user_unidade_permitida = session.get('unidade')

    # ==================================================================
    # INÍCIO DA LÓGICA DE VALIDAÇÃO E PRÉ-SELEÇÃO
    # ==================================================================
    
    # Se o usuário é comum (não admin)...
    if user_level != 'administrador' and user_unidade_permitida != 'TODAS':
        # E tentou acessar uma unidade pela URL que não é a sua...
        if selected_unity and selected_unity != user_unidade_permitida:
            flash("Você não tem permissão para acessar a unidade/processo/transportador ou tambor selecionado.", "error")
            return render_template('status.html', **context)
        
        # **A CORREÇÃO PRINCIPAL ESTÁ AQUI**
        # Força a seleção para a unidade permitida, tratando o caso em que o usuário acessa /status sem parâmetros.
        selected_unity = user_unidade_permitida

    # Atualiza o dicionário de valores selecionados que será usado no template
    context['selected_values'].update({
        'unidade': selected_unity,
        'processo': selected_process,
        'transportador': selected_transporter,
        'tambor': selected_barrel
    })
    
    # ==================================================================
    # FIM DA VALIDAÇÃO E PRÉ-SELEÇÃO
    # ==================================================================

    try:
        # A busca de dados agora usa a 'selected_unity' que foi previamente validada e definida
        all_unities_response = requests.get(f"{API_BASE_URL}/cliente_info", timeout=5)
        all_unities = flatten_if_nested(all_unities_response.json().get('unidades', []))

        # Popula o dropdown de unidades com base na permissão
        if user_level == 'administrador' or user_unidade_permitida == 'TODAS':
            context['unities'] = all_unities
        elif user_unidade_permitida in all_unities:
            context['unities'] = [user_unidade_permitida]
    
    # A busca de dados detalhados prossegue normalmente, agora com a certeza
    # de que a 'selected_unity' é permitida para o usuário.
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
            # Esta função agora só é chamada com parâmetros validados
            summary = get_summary_for_scope(selected_unity, selected_process, selected_transporter)
            context['dashboard_data'].update({
                'general_stats': summary['general_stats'],
                'thickness_counts': summary['thickness_counts'],
                'location_data': json.dumps(summary['locations']),
            })
    except requests.exceptions.RequestException as e:
        context['error'] = f"Erro ao comunicar com a API: {e}"
    except Exception as e:
        context['error'] = f"Ocorreu um erro inesperado: {e}"
        import traceback
        traceback.print_exc()

    return render_template('status.html', **context)

@app.route('/remove_tambor', methods=['POST'])
@login_required
def remove_barrel():
    #print("--- [DEBUG] 5: carregou/remove_tambor", flush=True)
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
@login_required
def relatorio_tambor(unidade, processo, transportador, barrel_id):
    #print("--- [DEBUG] 6: carregou/relatorio_tambor", flush=True)
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

@app.route('/historico')
@login_required
def historico_page():
    #print("--- [DEBUG] 7: carregou/historico", flush=True)
    # Captura todos os valores do formulário
    selected_unity = request.args.get('unidade')
    selected_process = request.args.get('processo')
    selected_transporter = request.args.get('transportador')
    selected_barrel = request.args.get('tambor')
    selected_plate = request.args.get('placa')
    data_inicio = request.args.get('dataInicio')
    data_fim = request.args.get('dataFim')

    # --- NOVA LÓGICA: Define datas padrão se não forem fornecidas ---
    dates_provided = bool(data_inicio and data_fim)
    if not dates_provided:
        data_inicio = '2024-01-01'
        data_fim = date.today().strftime('%Y-%m-%d')
    # -----------------------------------------------------------------

    context = {
        'title': 'Histórico de Desgaste', 'subtitle': 'Acompanhamento detalhado das placas',
        'unities': [], 'processes': [], 'transporters': [], 'barrels': [], 'plates': [],
        'selected_values': {
            'unidade': selected_unity, 'processo': selected_process,
            'transportador': selected_transporter, 'tambor': selected_barrel,
            'placa': selected_plate,
            'dataInicio': data_inicio, # Sempre terá um valor (padrão ou do usuário)
            'dataFim': data_fim        # Sempre terá um valor (padrão ou do usuário)
        },
        'chart_data': {}, 'error': None, 'history_data': []
    }

    try:
        # Lógica para popular os dropdowns de filtro (sem alterações)
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

        # Busca o histórico se um tambor for selecionado (agora sempre terá datas)
        if selected_barrel:
            # --- LÓGICA ATUALIZADA PARA BUSCAR PLACAS E HISTÓRICO ---
            # Busca as placas disponíveis no tambor
            agora_params = {'unidade': selected_unity, 'processo': selected_process, 'transportador': selected_transporter, 'ID': selected_barrel}
            agora_response = requests.get(f"{API_BASE_URL}/tambor_agora", params=agora_params, timeout=10)
            if agora_response.ok:
                espessura_atual = agora_response.json().get('espessuraAtual', [])
                if espessura_atual:
                    context['plates'] = sorted([p.get('placa') for p in espessura_atual if p.get('placa')])

            # Se a placa não foi selecionada pelo usuário, define a primeira como padrão
            if not selected_plate and context['plates']:
                selected_plate = context['plates'][0]
                context['selected_values']['placa'] = selected_plate

            # Prepara e executa a chamada para o histórico
            history_params = {
                'unidade': selected_unity, 'processo': selected_process,
                'transportador': selected_transporter, 'ID': selected_barrel,
                'dataInicio': f"{data_inicio} 00:00:00",
                'dataFim': f"{data_fim} 23:59:59"
            }
            historico_response = requests.get(f"{API_BASE_URL}/tambor_historico", params=history_params, timeout=10)
            historico_response.raise_for_status()
            history_data = historico_response.json().get('historico', [])
            context['history_data'] = history_data
            
            # Prepara os dados do gráfico se houver histórico e uma placa selecionada
            if history_data and selected_plate:
                chart_data = prepare_history_chart_data(history_data, selected_plate)
                context['chart_data'] = json.dumps(chart_data)

    except requests.exceptions.RequestException as e:
        context['error'] = f"Erro ao comunicar com a API: {e}"
    except Exception as e:
        context['error'] = f"Ocorreu um erro inesperado: {e}"

    return render_template('historico.html', **context)


if __name__ == '__main__':
    app.run(debug=True, port=5001)
