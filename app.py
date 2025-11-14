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

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de salud para verificar que el servidor está activo."""
    return jsonify({"status": "OK", "message": "Simulador de Blockchain Activo"}), 200

@app.route('/', methods=['GET'])
def get_index():
    """
    Sirve el archivo principal (index.html) cuando
    alguien visita la URL raíz.
    """
    return send_from_directory('.', 'index.html')

@app.route('/keys/new', methods=['GET'])
def new_key_pair():
    """
    Genera un nuevo par de llaves (privada y pública).
    El frontend usará esto para el botón "RANDOM".
    """
    private_key, public_key = Keys.generate_key_pair()
    response = {
        'message': 'Nuevo par de llaves generado.',
        'private_key': private_key,
        'public_key': public_key
    }
    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    """
    Recibe una nueva transacción (firmada) y la añade al mempool
    después de la doble verificación.
    """
    values = request.get_json()
    
    if not values:
        return jsonify({'message': 'Error: Solicitud JSON inválida o vacía.'}), 400

    required_fields = ['sender_public_key', 'recipient', 'amount', 'signature', 'message_hash']
    if not all(k in values for k in required_fields):
        return jsonify({'message': 'Error: Faltan campos en la transacción (se requiere: sender_public_key, recipient, amount, signature, message_hash)'}), 400

    try:
        amount = float(values['amount'])
    except ValueError:
        return jsonify({'message': 'Error: El monto debe ser un número.'}), 400
        
    success, message = blockchain.new_transaction(
        sender_public_key=values['sender_public_key'],
        recipient=values['recipient'],
        amount=amount,
        signature=values['signature'],
        message_hash=values['message_hash']
    )

    if not success:
        return jsonify({'message': f'Error al crear la transacción: {message}'}), 400

    response = {
        'message': message,
        'transaction': values
    }
    return jsonify(response), 201

@app.route('/mine', methods=['POST'])
def mine():
    """
    Mina un nuevo bloque, añade las transacciones del mempool
    y entrega la recompensa al minero.
    """
    values = request.get_json()
    
    if not values:
        return jsonify({'message': 'Error: Solicitud JSON inválida o vacía.'}), 400
    
    miner_public_key = values.get('miner_public_key')
    if not miner_public_key:
        return jsonify({'message': 'Error: Se requiere "miner_public_key" para asignar la recompensa.'}), 400

    blockchain.node_id = miner_public_key

    last_block = blockchain.last_block
    nonce = blockchain.proof_of_work(last_block)

    previous_hash = blockchain._hash(last_block)
    block = blockchain._new_block(previous_hash, nonce)

    response = {
        'message': "¡Nuevo bloque minado exitosamente!",
        'index': block['index'],
        'transactions': block['transactions'],
        'nonce': block['nonce'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200

@app.route('/chain', methods=['GET'])
def full_chain():
    """Retorna la cadena de bloques completa."""
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/mempool', methods=['GET'])
def get_mempool():
    """Retorna las transacciones pendientes (mempool)."""
    response = {
        'mempool': blockchain.mempool,
        'count': len(blockchain.mempool),
    }
    return jsonify(response), 200

@app.route('/balances', methods=['GET'])
def get_all_balances():
    """
    Calcula y retorna los saldos de todas las direcciones
    que han participado en la blockchain.
    """
    all_addresses = set()
    for block in blockchain.chain:
        for tx in block['transactions']:
            if tx['sender_public_key'] != "SYSTEM":
                all_addresses.add(tx['sender_public_key'])
            all_addresses.add(tx['recipient'])
    
    balances = {}
    for address in all_addresses:
        balances[address] = blockchain.get_balance(address)
    
    return jsonify(balances), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    
    if not values:
        return jsonify({'message': 'Error: Solicitud JSON inválida o vacía.'}), 400
    
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
    return jsonify({'message': 'Consenso no implementado en este simulador'}), 501

if __name__ == '__main__':
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    
    app.run(host='0.0.0.0', port=port, debug=True)
