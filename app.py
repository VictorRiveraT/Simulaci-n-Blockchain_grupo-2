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

# --- NUEVO: REGISTRO DE ALIAS ---
# Un simple diccionario en memoria para guardar: {'alias': 'public_key'}
alias_registry = {}

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK", "message": "Simulador de Blockchain Activo", "difficulty": 4}), 200

@app.route('/', methods=['GET'])
def get_index():
    return send_from_directory('.', 'index.html')

@app.route('/faucet', methods=['POST'])
def faucet_funds():
    """
    Reparte fondos del Fundador (Faucet) a una dirección.
    (Este endpoint no cambia, ya es seguro)
    """
    values = request.get_json()
    if not values:
        return jsonify({'message': 'Error: Solicitud JSON inválida.'}), 400
    
    recipient_address = values.get('recipient_address')
    if not recipient_address:
        return jsonify({'message': 'Error: Se requiere "recipient_address".'}), 400

    success, message = blockchain.issue_faucet_funds(recipient_address)
    
    if not success:
        return jsonify({'message': f'Error del Faucet: {message}'}), 500

    return jsonify({
        'message': f'¡Éxito! {message}. Se enviaron 100 monedas a tu dirección.',
        'note': 'Deberás minar un bloque para confirmar la transacción.'
    }), 200

# --- NUEVO ENDPOINT: /register_alias ---
@app.route('/register_alias', methods=['POST'])
def register_alias():
    """
    Registra un alias (nombre) para una llave pública.
    """
    values = request.get_json()
    if not values:
        return jsonify({'message': 'Error: Solicitud JSON inválida.'}), 400
        
    alias = values.get('alias')
    public_key = values.get('public_key')

    if not alias or not public_key:
        return jsonify({'message': 'Error: Se requiere "alias" y "public_key".'}), 400

    # Verificar si el alias ya está tomado
    if alias in alias_registry:
        return jsonify({'message': f'Error: El alias "{alias}" ya está tomado.'}), 400
        
    # Verificar si la llave ya tiene un alias
    if public_key in alias_registry.values():
         return jsonify({'message': 'Error: Esta Llave Pública ya tiene un alias registrado.'}), 400

    alias_registry[alias] = public_key
    print(f"Registro de Alias: {alias} -> {public_key}")
    return jsonify({'message': f'¡Éxito! Alias "{alias}" registrado.'}), 201

# --- NUEVO ENDPOINT: /aliases ---
@app.route('/aliases', methods=['GET'])
def get_aliases():
    """
    Retorna la lista completa de alias.
    """
    return jsonify(alias_registry), 200

@app.route('/transactions/verify_only', methods=['POST'])
def verify_transaction_only():
    values = request.get_json()
    if not values:
        return jsonify({'valid': False, 'error': 'Solicitud JSON inválida.'}), 400

    required_fields = ['sender_pub', 'recipient', 'amount', 'signature']
    if not all(k in values for k in required_fields):
        return jsonify({'valid': False, 'error': 'Faltan campos (sender_pub, recipient, amount, signature)'}), 400

    try:
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

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    if not values:
        return jsonify({'message': 'Error: Solicitud JSON inválida.'}), 400

    required_fields = ['sender_pub', 'recipient', 'amount', 'signature']
    if not all(k in values for k in required_fields):
        return jsonify({'message': 'Error: Faltan campos (sender_pub, recipient, amount, signature)'}), 400

    try:
        amount = int(values['amount'])
    except ValueError:
        return jsonify({'message': 'Error: El monto debe ser un número entero.'}), 400
        
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

@app.route('/mine', methods=['POST'])
def mine():
    values = request.get_json()
    if not values:
        return jsonify({'message': 'Error: Solicitud JSON inválida.'}), 400
    
    miner_address = values.get('miner_address')
    if not miner_address:
        return jsonify({'message': 'Error: Se requiere "miner_address".'}), 400

    blockchain.node_id = miner_address
    last_block = blockchain.last_block
    nonce = blockchain.proof_of_work(last_block)
    previous_hash = blockchain._hash(last_block)
    block = blockchain._new_block(previous_hash, nonce)

    response = {
        'message': "¡Nuevo bloque minado!",
        'index': block['index'],
        'transactions': block['transactions'],
        'nonce': block['nonce'],
        'previous_hash': block['previous_hash'],
        'hash': blockchain._hash(block)
    }
    return jsonify(response), 200

@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/mempool', methods=['GET'])
def get_mempool():
    return jsonify(blockchain.mempool), 200

@app.route('/balances', methods=['GET'])
def get_all_balances():
    return jsonify(blockchain.get_all_balances()), 200

@app.route('/leaders', methods=['GET'])
def get_leaders():
    return jsonify(blockchain.get_leaders()), 200

@app.route('/validate', methods=['GET'])
def validate_chain():
    is_valid = blockchain.is_chain_valid()
    if is_valid:
        return jsonify({'message': 'La cadena es válida.', 'valid': True}), 200
    else:
        return jsonify({'message': 'ERROR: La cadena NO es válida.', 'valid': False}), 500

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

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    app.run(host='0.0.0.0', port=port, debug=True)
