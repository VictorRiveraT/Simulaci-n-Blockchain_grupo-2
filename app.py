# -*- coding: utf-8 -*-
import sys
from time import time
from uuid import uuid4
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

from blockchain import Blockchain, FOUNDER_PRIVATE_KEY
from keys import Keys

# ===== CONFIGURACION CORRECTA DE FLASK =====
app = Flask(__name__, 
            static_folder='static',
            static_url_path='/static',
            template_folder='templates')

CORS(app) 
blockchain = Blockchain()
alias_registry = {}

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK", "message": "Simulador de Blockchain Activo", "difficulty": 4}), 200

@app.route('/')
def get_index():
    return render_template('index.html')

@app.route('/faucet', methods=['POST'])
def faucet_funds():
    values = request.get_json()
    if not values:
        return jsonify({'message': 'Error: Solicitud JSON invalida.'}), 400
    
    recipient_address = values.get('recipient_address')
    admin_private_key = values.get('admin_private_key')
    
    if not recipient_address or not admin_private_key:
        return jsonify({'message': 'Error: Se requiere "recipient_address" y "admin_private_key".'}), 400

    if admin_private_key != FOUNDER_PRIVATE_KEY:
        return jsonify({'message': 'Error: Llave Privada del Fundador invalida. No eres el Admin!'}), 401

    success, message = blockchain.issue_faucet_funds(recipient_address)
    
    if not success:
        return jsonify({'message': 'Error del Faucet: ' + str(message)}), 500

    return jsonify({
        'message': 'Exito! ' + str(message) + '. Se enviaron 100 monedas a tu direccion.',
        'note': 'Deberas minar un bloque para confirmar la transaccion.'
    }), 200

@app.route('/register_alias', methods=['POST'])
def register_alias():
    values = request.get_json()
    if not values:
        return jsonify({'message': 'Error: Solicitud JSON invalida.'}), 400
        
    alias = values.get('alias')
    public_key = values.get('public_key')

    if not alias or not public_key:
        return jsonify({'message': 'Error: Se requiere "alias" y "public_key".'}), 400

    if alias in alias_registry:
        return jsonify({'message': 'Error: El alias "' + alias + '" ya esta tomado.'}), 400
        
    if public_key in alias_registry.values():
         return jsonify({'message': 'Error: Esta Llave Publica ya tiene un alias registrado.'}), 400

    alias_registry[alias] = public_key
    print("Registro de Alias: " + alias + " -> " + public_key)
    return jsonify({'message': 'Exito! Alias "' + alias + '" registrado.'}), 201

@app.route('/aliases', methods=['GET'])
def get_aliases():
    return jsonify(alias_registry), 200

@app.route('/transactions/verify_only', methods=['POST'])
def verify_transaction_only():
    values = request.get_json()
    if not values:
        return jsonify({'valid': False, 'error': 'Solicitud JSON invalida.'}), 400

    required_fields = ['sender_pub', 'recipient', 'amount', 'signature']
    if not all(k in values for k in required_fields):
        return jsonify({'valid': False, 'error': 'Faltan campos (sender_pub, recipient, amount, signature)'}), 400

    try:
        amount = int(values['amount'])
    except ValueError:
        return jsonify({'valid': False, 'error': 'El monto debe ser un numero entero.'}), 400
        
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
        return jsonify({'message': 'Error: Solicitud JSON invalida.'}), 400

    required_fields = ['sender_pub', 'recipient', 'amount', 'signature']
    if not all(k in values for k in required_fields):
        return jsonify({'message': 'Error: Faltan campos (sender_pub, recipient, amount, signature)'}), 400

    try:
        amount = int(values['amount'])
    except ValueError:
        return jsonify({'message': 'Error: El monto debe ser un numero entero.'}), 400
        
    success, message = blockchain.new_transaction(
        sender_pub=values['sender_pub'],
        recipient=values['recipient'],
        amount=amount,
        signature=values['signature']
    )

    if not success:
        return jsonify({'message': 'Error al crear la transaccion: ' + str(message)}), 400

    response = {'message': message}
    return jsonify(response), 201

@app.route('/mine', methods=['POST'])
def mine():
    values = request.get_json()
    if not values:
        return jsonify({'message': 'Error: Solicitud JSON invalida.'}), 400
    
    miner_address = values.get('miner_address')
    if not miner_address:
        return jsonify({'message': 'Error: Se requiere "miner_address".'}), 400

    blockchain.node_id = miner_address
    last_block = blockchain.last_block
    
    current_time = time()
    nonce = blockchain.proof_of_work(last_block, current_time)
    previous_hash = blockchain._hash(last_block)
    block = blockchain._new_block(previous_hash, nonce, current_time=current_time)

    response = {
        'message': "Nuevo bloque minado!",
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
        return jsonify({'message': 'La cadena es valida.', 'valid': True}), 200
    else:
        return jsonify({'message': 'ERROR: La cadena NO es valida.', 'valid': False}), 500

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Por favor, proporcione una lista valida de nodos", 400
    for node in nodes:
        blockchain.register_node(node)
    response = {
        'message': 'Nuevos nodos han sido anadidos',
        'total_nodes': list(blockchain._nodes),
    }
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    return jsonify({'message': 'Consenso no implementado'}), 501

if __name__ == '__main__':
    import os
    try:
        port = int(os.environ.get('PORT', 5000))
        print("="*50)
        print("Iniciando servidor en puerto " + str(port) + "...")
        print("Abre tu navegador en: http://127.0.0.1:" + str(port))
        print("="*50)
        app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
    except Exception as e:
        print("ERROR AL INICIAR SERVIDOR:")
        print(str(e))
        import traceback
        traceback.print_exc()
        input("Presiona Enter para salir...")