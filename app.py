# -*- coding: utf-8 -*-
import sys
import os
from time import time
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit

from blockchain import Blockchain, FOUNDER_PRIVATE_KEY, FOUNDER_ADDRESS, MINING_REWARD
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
alias_registry = {
    'FOUNDER': FOUNDER_ADDRESS
}

# ==========================================
# RUTAS DE VISUALIZACIÓN Y ALIAS
# ==========================================

@app.route('/')
def get_index():
    """ Sirve el index.html usando Flask 'render_template' """
    return render_template('index.html')

@app.route('/aliases', methods=['GET'])
def get_aliases():
    """ Retorna el registro completo de alias (nombre -> Public Key) """
    return jsonify(alias_registry), 200

@app.route('/register_alias', methods=['POST'])
def register_alias():
    """ Registra un nuevo alias para una llave pública """
    values = request.get_json()
    alias = values.get('alias')
    public_key = values.get('public_key')

    if not alias or not public_key:
        return jsonify({'error': 'Se requiere alias y public_key.'}), 400
    
    if alias in alias_registry:
        return jsonify({'error': f'El alias "{alias}" ya está en uso.'}), 409
    
    # Simple check para que no se use la clave FOUNDER
    if public_key == FOUNDER_ADDRESS:
        return jsonify({'error': 'No puedes registrarte con la llave del Fundador.'}), 403
    
    alias_registry[alias] = public_key
    print(f"Alias registrado: {alias} -> {public_key[:10]}...")
    return jsonify({'message': f'Alias "{alias}" registrado con éxito.'}), 201


# ==========================================
# RUTAS DE TRANSACCIONES Y FAUCET
# ==========================================

def _get_transaction_data(values):
    """ Función utilitaria para extraer y validar datos de transacción """
    sender_pub = values.get('sender_pub')
    recipient = values.get('recipient')
    amount = values.get('amount')
    signature = values.get('signature')

    if not all([sender_pub, recipient, amount, signature]):
        return None, {'error': 'Faltan campos obligatorios: sender_pub, recipient, amount, signature.'}

    try:
        amount = int(amount)
        if amount <= 0:
             return None, {'error': 'El monto debe ser un número entero positivo.'}
    except ValueError:
        return None, {'error': 'El monto debe ser un número entero.'}
    
    payload = {
        'sender': sender_pub,
        'recipient': recipient,
        'amount': amount,
    }
    
    # Calcular el hash que se firmó para la verificación
    tx_hash = blockchain._hash(payload)
    
    return payload, tx_hash, signature

@app.route('/transactions/verify_only', methods=['POST'])
def verify_transaction():
    """ 
    Verifica la firma y los fondos antes de que el frontend intente enviar la transacción.
    """
    values = request.get_json()
    if not values:
        return jsonify({'error': 'Solicitud JSON inválida.'}), 400

    payload, tx_hash, signature = _get_transaction_data(values)
    if payload is None:
        return jsonify(tx_hash), 400 # tx_hash en este caso contiene el error

    # 1. Verificar Firma Criptográfica
    is_signature_valid = Keys.verify_signature(
        public_key_hex=payload['sender'], 
        signature_hex=signature, 
        message_hash_hex=tx_hash
    )

    if not is_signature_valid:
        return jsonify({'valid': False, 'error': 'Firma criptográfica inválida.'}), 401

    # 2. Verificar Fondos Suficientes
    sender_balance = blockchain.get_balance(payload['sender'])
    if sender_balance < payload['amount']:
        return jsonify({'valid': False, 'error': f'Fondos insuficientes. Saldo actual: {sender_balance}.'}), 402

    return jsonify({'valid': True, 'message': 'Firma y fondos verificados correctamente.'}), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    """
    Recibe una nueva transacción (firmada) y la añade al mempool.
    Se asume que el frontend ya verificó la firma y los fondos (o se re-verifica).
    """
    values = request.get_json()
    if not values:
        return jsonify({'error': 'Solicitud JSON inválida.'}), 400
    
    # Se extraen los datos y se asume que la estructura es correcta para el mempool
    sender = values.get('sender_pub')
    recipient = values.get('recipient')
    amount = values.get('amount')
    signature = values.get('signature')

    if not all([sender, recipient, amount, signature]):
        return jsonify({'error': 'Faltan datos en la transacción (sender_pub, recipient, amount, signature).'}), 400

    # Se añade al mempool
    success = blockchain.new_transaction(sender, recipient, amount, signature)
    
    if success:
        # Emitir evento WebSocket para actualizar el frontend
        socketio.emit('actualizacion_mempool', {'msg': 'Nueva transacción añadida'})
        return jsonify({
            'message': 'Transacción añadida al Mempool', 
            'tx_count': len(blockchain.mempool)
        }), 201
    else:
        return jsonify({'error': 'La transacción no pudo ser añadida.'}), 500

@app.route('/faucet', methods=['POST'])
def faucet_funds():
    """
    Permite al Fundador enviar 100 monedas a cualquier dirección.
    Requiere la llave privada fija del Fundador para autenticación.
    """
    values = request.get_json()
    if not values:
        return jsonify({'message': 'Error: Solicitud JSON inválida.'}), 400
    
    recipient_address = values.get('recipient_address')
    admin_private_key = values.get('admin_private_key')
    
    if not recipient_address or not admin_private_key:
        return jsonify({'message': 'Error: Se requiere "recipient_address" y "admin_private_key".'}), 400

    # **CRÍTICO: Verificación de la llave privada del administrador**
    if admin_private_key != FOUNDER_PRIVATE_KEY:
        return jsonify({'message': 'Error: Llave Privada del Fundador inválida. No eres el Admin!'}), 401

    # Crear el payload de la transacción
    payload = {
        'sender': FOUNDER_ADDRESS,
        'recipient': recipient_address,
        'amount': 100, # Monto fijo del Faucet
    }

    # Firmar el payload con la llave privada del Fundador
    tx_hash = blockchain._hash(payload)
    signature = Keys.sign_digest(FOUNDER_PRIVATE_KEY, tx_hash)

    # Añadir al mempool (asumimos que la firma es correcta y los fondos son suficientes)
    success = blockchain.new_transaction(
        FOUNDER_ADDRESS, 
        recipient_address, 
        100, 
        signature
    )

    if success:
        socketio.emit('actualizacion_mempool', {'msg': 'Transacción Faucet añadida'})
        return jsonify({'message': f'100 monedas enviadas a {recipient_address[:10]}... desde el Faucet.'}), 201
    else:
        return jsonify({'message': 'Error al añadir la transacción del Faucet.'}), 500

# ==========================================
# RUTAS DE MINADO Y CONSULTA
# ==========================================

@app.route('/mine', methods=['POST'])
def mine_block():
    """ Endpoint para iniciar el proceso de minado (Proof of Work) """
    values = request.get_json()
    if not values:
        return jsonify({'error': 'Solicitud JSON inválida.'}), 400

    miner_address = values.get('miner_address')
    if not miner_address:
        return jsonify({'error': 'Se requiere la dirección del minero (miner_address).'}), 400

    new_block = blockchain.mine(miner_address)
    
    # Emitir evento WebSocket para actualizar el frontend
    socketio.emit('bloque_minado', {'index': new_block['index'], 'msg': 'Nuevo bloque minado'})
    
    response = {
        'message': 'Nuevo Bloque Forjado',
        'index': new_block['index'],
        'transactions': new_block['transactions'],
        'nonce': new_block['nonce'],
        'previous_hash': new_block['previous_hash'],
        'hash': new_block['hash'],
    }
    return jsonify(response), 200

@app.route('/health', methods=['GET'])
def health_check():
    """ Endpoint de salud y dificultad de PoW """
    return jsonify({
        'status': 'OK', 
        'message': 'Simulador de Blockchain Activo', 
        'difficulty': 4,
        'chain_length': len(blockchain.chain),
        'mempool_size': len(blockchain.mempool)
    }), 200

@app.route('/chain', methods=['GET'])
def full_chain():
    """ Retorna la cadena completa """
    return jsonify({'chain': blockchain.chain, 'length': len(blockchain.chain)}), 200

@app.route('/mempool', methods=['GET'])
def get_mempool(): 
    """ Retorna las transacciones pendientes en el Mempool. """
    return jsonify(blockchain.mempool), 200

@app.route('/balances', methods=['GET'])
def get_all_balances(): 
    """ Retorna el estado actual de cuentas (saldos). """
    return jsonify(blockchain.get_all_balances()), 200

@app.route('/leaders', methods=['GET'])
def get_leaders(): 
    """ Retorna la tabla de clasificación de mineros por recompensas. """
    return jsonify(blockchain.get_leaders()), 200

@app.route('/validate', methods=['GET'])
def validate_chain():
    """ Verifica la integridad criptográfica de toda la cadena. """
    valid = blockchain.is_chain_valid()
    return jsonify({'valid': valid, 'message': 'Cadena válida' if valid else 'Cadena inválida'}), 200 if valid else 500


# ==========================================
# PUNTO DE ENTRADA CON SOCKETIO
# ==========================================

if __name__ == '__main__':
    # Configuración del puerto basada en variables de entorno (para Render)
    port = int(os.environ.get('PORT', 5000))
    print("="*50)
    print("Iniciando Servidor Blockchain con soporte WebSockets")
    print(f"Puerto de escucha: {port}")
    print(f"URL Local: http://127.0.0.1:{port}")
    print("="*50)
    
    # Usar socketio.run en lugar de app.run cuando se usa Flask-SocketIO
    socketio.run(app, host='0.0.0.0', port=port)
