# -*- coding: utf-8 -*-
import sys
import os
from time import time
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# Importación de módulos locales para la lógica de blockchain y criptografía
from blockchain import Blockchain, FOUNDER_PRIVATE_KEY, FOUNDER_ADDRESS
from keys import Keys

# ==========================================
# CONFIGURACIÓN DE LA APLICACIÓN FLASK
# ==========================================
# Se definen las rutas para archivos estáticos y plantillas HTML
app = Flask(__name__, 
            static_folder='static',
            static_url_path='/static',
            template_folder='templates')

app.config['SECRET_KEY'] = 'secreto_seguro_blockchain' # Clave requerida para la gestión de sesiones y websockets
CORS(app) 

# Inicialización de SocketIO para habilitar la comunicación bidireccional en tiempo real
socketio = SocketIO(app, cors_allowed_origins="*")

# Instancia de la Blockchain (gestiona la base de datos y la lógica de cadena)
blockchain = Blockchain()

# Registro de Alias: Mapeo de nombres legibles a direcciones públicas
# Se inicializa con la dirección del fundador pre-cargada
alias_registry = {
    'FOUNDER': FOUNDER_ADDRESS
}

# ==========================================
# RUTAS DEL SISTEMA
# ==========================================

@app.route('/health', methods=['GET'])
def health_check():
    """
    Endpoint para verificar el estado del servicio.
    Retorna el estado operativo y la dificultad actual de minado.
    """
    return jsonify({"status": "OK", "message": "Simulador Activo", "difficulty": 4}), 200

@app.route('/')
def get_index():
    """
    Ruta principal que sirve la interfaz de usuario (SPA).
    """
    return render_template('index.html')

# ==========================================
# RUTAS TRANSACCIONALES
# ==========================================

@app.route('/faucet', methods=['POST'])
def faucet_funds():
    """
    Distribuye fondos desde la cuenta del Fundador a una dirección destino.
    Requiere autenticación mediante la llave privada del administrador.
    """
    values = request.get_json()
    if not values: return jsonify({'message': 'Error: Solicitud JSON inválida.'}), 400
    
    recipient = values.get('recipient_address')
    key = values.get('admin_private_key')
    
    if not recipient or not key: return jsonify({'message': 'Error: Faltan datos requeridos.'}), 400
    
    # Verificación simple de credenciales administrativas
    if key != FOUNDER_PRIVATE_KEY: return jsonify({'message': 'Error: Llave privada inválida.'}), 401

    success, msg = blockchain.issue_faucet_funds(recipient)
    if not success: return jsonify({'message': msg}), 500

    # Emisión de evento WebSocket: Notificar a los clientes para actualizar el mempool
    socketio.emit('actualizacion_mempool', {'msg': 'Faucet utilizado'})
    
    return jsonify({'message': 'Exito: ' + str(msg)}), 200

@app.route('/register_alias', methods=['POST'])
def register_alias():
    """
    Registra un alias legible para una clave pública específica.
    """
    values = request.get_json()
    alias = values.get('alias')
    pub = values.get('public_key')
    if not alias or not pub: return jsonify({'message': 'Error: Faltan datos requeridos.'}), 400
    
    alias_registry[alias] = pub
    return jsonify({'message': 'Alias registrado correctamente.'}), 201

@app.route('/aliases', methods=['GET'])
def get_aliases():
    """
    Retorna el registro completo de alias para su resolución en el frontend.
    """
    return jsonify(alias_registry), 200

@app.route('/transactions/verify_only', methods=['POST'])
def verify_transaction_only():
    """
    Verifica la validez de una transacción (firma y fondos) sin procesarla.
    Utilizado por el nodo para validación previa.
    """
    v = request.get_json()
    try: amt = int(v['amount'])
    except: return jsonify({'valid': False, 'error': 'Error: Monto inválido.'}), 400
        
    success, msg = blockchain.verify_transaction(v['sender_pub'], v['recipient'], amt, v['signature'])
    if not success: return jsonify({'valid': False, 'error': msg}), 400
    return jsonify({'valid': True, 'message': msg}), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    """
    Crea una nueva transacción y la añade al Mempool.
    Emite un evento WebSocket para actualizar la interfaz de los clientes conectados.
    """
    v = request.get_json()
    try: amt = int(v['amount'])
    except: return jsonify({'message': 'Error: Monto inválido.'}), 400
        
    success, msg = blockchain.new_transaction(v['sender_pub'], v['recipient'], amt, v['signature'])
    if not success: return jsonify({'message': msg}), 400

    # Emisión de evento WebSocket: Notificar nueva transacción pendiente
    socketio.emit('actualizacion_mempool', {'msg': 'Nueva transacción pendiente'})

    return jsonify({'message': msg}), 201

@app.route('/mine', methods=['POST'])
def mine():
    """
    Ejecuta el algoritmo de Prueba de Trabajo (PoW) para minar un nuevo bloque.
    Sincroniza el tiempo de minado y creación del bloque para asegurar la consistencia del hash.
    """
    v = request.get_json()
    miner = v.get('miner_address')
    if not miner: return jsonify({'message': 'Error: Se requiere dirección del minero.'}), 400

    blockchain.node_id = miner
    last_block = blockchain.last_block
    
    # Captura del tiempo actual para asegurar consistencia entre el cálculo del nonce y el bloque final
    timestamp_fijo = time()
    
    # Ejecución de PoW con tiempo congelado
    nonce = blockchain.proof_of_work(last_block, current_time=timestamp_fijo)
    
    # Creación y persistencia del bloque con el nonce encontrado
    block = blockchain._new_block(
        previous_hash=blockchain._hash(last_block), 
        nonce=nonce, 
        current_time=timestamp_fijo
    )

    # Construcción de la respuesta con detalles técnicos para el frontend
    response = {
        'message': "Nuevo bloque minado exitosamente.",
        'index': block['index'],
        'nonce': block['nonce'],
        'previous_hash': block['previous_hash'],
        'transactions': block['transactions'],
        'hash': blockchain._hash(block)
    }
    
    # Emisión de evento WebSocket: Notificar a todos los nodos sobre el nuevo bloque
    socketio.emit('bloque_minado', {'index': block['index'], 'miner': miner})
    
    return jsonify(response), 200

# ==========================================
# RUTAS DE CONSULTA E INFORMACIÓN
# ==========================================

@app.route('/chain', methods=['GET'])
def full_chain(): 
    """ Retorna la cadena de bloques completa y su longitud. """
    return jsonify({'chain': blockchain.chain, 'length': len(blockchain.chain)}), 200

@app.route('/mempool', methods=['GET'])
def get_mempool(): 
    """ Retorna las transacciones pendientes en el Mempool. """
    return jsonify(blockchain.mempool), 200

@app.route('/balances', methods=['GET'])
def get_all_balances(): 
    """ Retorna el estado actual de cuentas (UTXO abstraído). """
    return jsonify(blockchain.get_all_balances()), 200

@app.route('/leaders', methods=['GET'])
def get_leaders(): 
    """ Retorna la tabla de clasificación de mineros por recompensas obtenidas. """
    return jsonify(blockchain.get_leaders()), 200

@app.route('/validate', methods=['GET'])
def validate_chain():
    """ Verifica la integridad criptográfica de toda la cadena. """
    valid = blockchain.is_chain_valid()
    return jsonify({'valid': valid, 'message': 'Cadena válida' if valid else 'Cadena inválida'}), 200 if valid else 500

# ==========================================
# PUNTO DE ENTRADA
# ==========================================

if __name__ == '__main__':
    # Configuración del puerto basada en variables de entorno
    port = int(os.environ.get('PORT', 5000))
    print("="*50)
    print(f"Iniciando Servidor Blockchain con soporte WebSockets")
    print(f"Puerto de escucha: {port}")
    print(f"URL Local: http://127.0.0.1:{port}")
    print("="*50)
    
    # Ejecución del servidor utilizando SocketIO
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)
