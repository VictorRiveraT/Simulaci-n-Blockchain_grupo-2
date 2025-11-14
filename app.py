import sys
from uuid import uuid4
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask import send_from_directory

from blockchain import Blockchain
from keys import Keys

app = Flask(__name__)
CORS(app) 
blockchain = Blockchain()

# --- Endpoint de Salud (sin cambios) ---
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK", "message": "Simulador de Blockchain Activo", "difficulty": 4}), 200

# --- Endpoint Raíz (sin cambios) ---
@app.route('/', methods=['GET'])
def get_index():
    return send_from_directory('.', 'index.html')

# --- ELIMINADO ---
# El endpoint '/keys/new' se elimina porque 
# 'indexvane.html' genera las llaves en el navegador (JavaScript).

# --- NUEVO ENDPOINT: /transactions/verify_only ---
@app.route('/transactions/verify_only', methods=['POST'])
def verify_transaction_only():
    """
    Verifica una transacción (fondos y firma) SIN agregarla al mempool.
    Usado por el botón "VERIFY" del Nodo Central.
    """
    values = request.get_json()
    if not values:
        return jsonify({'valid': False, 'error': 'Solicitud JSON inválida.'}), 400

    # CAMBIO: 'sender_pub' y 'amount' como entero
    required_fields = ['sender_pub', 'recipient', 'amount', 'signature']
    if not all(k in values for k in required_fields):
        return jsonify({'valid': False, 'error': 'Faltan campos (sender_pub, recipient, amount, signature)'}), 400

    try:
        # CAMBIO: Convertir a entero
        amount = int(values['amount'])
    except ValueError:
        return jsonify({'valid': False, 'error': 'El monto debe ser un número entero.'}), 400
        
    success, message = blockchain.verify_transaction(
        sender_pub=values['sender_pub'],
        recipient=values['recipient'],
        amount=amount,
        signature=values['signature']
    )

    if not success:
        return jsonify({'valid': False, 'error': message}), 400

    return jsonify({'valid': True, 'message': message}), 200

# --- ENDPOINT MODIFICADO: /transactions/new ---
@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    """
    Recibe una transacción (ya verificada por el frontend)
    y la añade al mempool.
    """
    values = request.get_json()
    if not values:
        return jsonify({'message': 'Error: Solicitud JSON inválida.'}), 400

    # CAMBIO: 'sender_pub' y 'amount' como entero. No se recibe 'message_hash'.
    required_fields = ['sender_pub', 'recipient', 'amount', 'signature']
    if not all(k in values for k in required_fields):
        return jsonify({'message': 'Error: Faltan campos (sender_pub, recipient, amount, signature)'}), 400

    try:
        amount = int(values['amount'])
    except ValueError:
        return jsonify({'message': 'Error: El monto debe ser un número entero.'}), 400
        
    # Llama a la nueva función de blockchain
    success, message = blockchain.new_transaction(
        sender_pub=values['sender_pub'],
        recipient=values['recipient'],
        amount=amount,
        signature=values['signature']
    )

    if not success:
        return jsonify({'message': f'Error al crear la transacción: {message}'}), 400

    response = {'message': message}
    return jsonify(response), 201

# --- ENDPOINT MODIFICADO: /mine ---
@app.route('/mine', methods=['POST'])
def mine():
    values = request.get_json()
    if not values:
        return jsonify({'message': 'Error: Solicitud JSON inválida.'}), 400
    
    # CAMBIO: Recibe 'miner_address' en lugar de 'miner_public_key'
    miner_address = values.get('miner_address')
    if not miner_address:
        return jsonify({'message': 'Error: Se requiere "miner_address".'}), 400

    blockchain.node_id = miner_address

    last_block = blockchain.last_block
    nonce = blockchain.proof_of_work(last_block)

    previous_hash = blockchain._hash(last_block)
    block = blockchain._new_block(previous_hash, nonce)

    # La respuesta es la misma, el nuevo JS la mostrará en el log
    response = {
        'message': "¡Nuevo bloque minado!",
        'index': block['index'],
        'transactions': block['transactions'],
        'nonce': block['nonce'],
        'previous_hash': block['previous_hash'],
        'hash': blockchain._hash(block) # Añadido para el panel 5
    }
    return jsonify(response), 200

# --- Endpoints de Consulta (Chain y Mempool sin cambios) ---

@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/mempool', methods=['GET'])
def get_mempool():
    # El nuevo JS espera una lista, no un diccionario
    return jsonify(blockchain.mempool), 200

# --- NUEVO ENDPOINT: /balances ---
@app.route('/balances', methods=['GET'])
def get_all_balances():
    """
    Retorna los saldos de todas las direcciones.
    """
    return jsonify(blockchain.get_all_balances()), 200

# --- NUEVO ENDPOINT: /leaders ---
@app.route('/leaders', methods=['GET'])
def get_leaders():
    """
    Retorna las recompensas acumuladas por los mineros.
    """
    return jsonify(blockchain.get_leaders()), 200

# --- NUEVO ENDPOINT: /validate ---
@app.route('/validate', methods=['GET'])
def validate_chain():
    """
    Verifica la integridad de la cadena.
    """
    is_valid = blockchain.is_chain_valid()
    if is_valid:
        return jsonify({'message': 'La cadena es válida.', 'valid': True}), 200
    else:
        return jsonify({'message': 'ERROR: La cadena NO es válida.', 'valid': False}), 500

# --- Endpoints de Nodos (sin cambios) ---
@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Por favor, proporcione una lista válida de nodos", 400
    for node in nodes:
        blockchain.register_node(node)
    response = {
        'message': 'Nuevos nodos han sido añadidos',
        'total_nodes': list(blockchain._nodes),
    }
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    return jsonify({'message': 'Consenso no implementado'}), 501

# --- Ejecutar Servidor (sin cambios) ---
if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    app.run(host='0.0.0.0', port=port, debug=True)
