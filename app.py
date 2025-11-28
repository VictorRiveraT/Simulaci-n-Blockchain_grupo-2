import hashlib
import json
import time
from uuid import uuid4

import eventlet  # Importar eventlet para usar workers asíncronos con Gunicorn/Render

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# Asegúrate de importar tu clase Blockchain desde donde la tengas
# Asumo que tienes una estructura como: from blockchain_module import Blockchain
# Si tu clase Blockchain está en el mismo archivo (app.py), simplemente ignora o ajusta esta línea.
from blockchain import Blockchain, InvalidTransactionError 

# --- Inicialización de Flask y SocketIO ---
app = Flask(__name__)
# Permitir CORS para cualquier origen (necesario para el despliegue en Render)
CORS(app) 
# Inicializar SocketIO, el driver asíncrono debe ser eventlet
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Instanciar la Blockchain
# Reemplaza '4' con el nivel de dificultad que desees
blockchain = Blockchain(difficulty=4)

# Generar una dirección de nodo única
node_identifier = str(uuid4()).replace('-', '')

# --- Lógica del Bloque Génesis ---
# Inicializar el bloque Génesis si la cadena está vacía (asumo que 'chain' es la lista de bloques)
if len(blockchain.chain) == 0:
    print("Base de datos vacia. Inicializando Bloque Genesis...")
    # Asegúrate de que esta lógica está en tu clase Blockchain o la inicializas correctamente aquí.
    # Si la inicialización del Bloque Génesis ya está manejada por el constructor de Blockchain, 
    # puedes eliminar o comentar esta sección si el constructor ya la maneja.
    # Aquí asumo que lo manejas en la clase.

# --- Endpoints de la API ---

@app.route('/')
def index():
    """Sirve el archivo HTML principal."""
    return render_template('index.html')

@app.route('/mine', methods=['POST'])
def mine():
    """Endpoint para minar un nuevo bloque."""
    # 1. Obtener la Prueba (Proof) del request
    values = request.get_json()
    if not values or 'proof' not in values:
        return 'Falta la Prueba (Proof)', 400

    proof = values['proof']

    # 2. Agregar la transacción de recompensa de minería (si aplica)
    # (Asegúrate de que esta lógica sea correcta en tu clase Blockchain)
    # blockchain.new_transaction(sender="0", recipient=node_identifier, amount=1)

    # 3. Minar el nuevo bloque
    block = blockchain.mine_block(proof)

    # *** CORRECCIÓN DEL ERROR 'NoneType' ***
    # El error 'NoneType' object is not subscriptable ocurre cuando 'block' es None.
    # Esto pasa, según tus logs, cuando 'El bloque ya existe en la BD.'
    if block is None:
        response = {
            'message': 'Error al minar: El bloque ya existe o la prueba es inválida.',
        }
        # Código de estado 400 (Bad Request) o 409 (Conflict)
        return jsonify(response), 400 

    # 4. Construir la respuesta (si el bloque se minó correctamente)
    response = {
        'message': 'Nuevo bloque minado',
        # *** LÍNEA CORREGIDA (ya no fallará si 'block' no es None) ***
        'index': block['index'], 
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    
    # Emitir evento a todos los clientes conectados a través de SocketIO
    socketio.emit('new_block', response) 
    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    """Endpoint para crear una nueva transacción."""
    values = request.get_json()
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Faltan valores en el cuerpo de la petición', 400

    try:
        # Crea la nueva transacción.
        index = blockchain.new_transaction(
            values['sender'], 
            values['recipient'], 
            values['amount']
        )
    except InvalidTransactionError as e:
        return jsonify({'message': str(e)}), 400
        
    response = {'message': f'La transacción se agregará al Bloque {index}'}
    return jsonify(response), 201

# --- Otros Endpoints (dejados como referencia) ---

@app.route('/chain', methods=['GET'])
def full_chain():
    """Retorna la cadena completa."""
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/balances', methods=['GET'])
def get_balances():
    """Retorna los balances de todas las direcciones."""
    balances = blockchain.get_balances()
    return jsonify(balances), 200

@app.route('/register_node', methods=['POST'])
def register_node():
    """Registra nuevos nodos (direcciones de otros servidores de la red)."""
    values = request.get_json()
    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Por favor, proporciona una lista de nodos válida", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'Nuevos nodos han sido añadidos',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201

@app.route('/resolve', methods=['GET'])
def consensus():
    """Resuelve conflictos, reemplazando la cadena si se encuentra una más larga."""
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Nuestra cadena fue reemplazada',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Nuestra cadena es autoritativa',
            'chain': blockchain.chain
        }

    # Emitir evento si la cadena fue reemplazada
    if replaced:
        socketio.emit('chain_update', response) 

    return jsonify(response), 200

# --- SocketIO Events (Si tienes lógica de SocketIO) ---
@socketio.on('connect')
def test_connect():
    print('Cliente conectado a SocketIO')
    emit('my response', {'data': 'Conectado'}, broadcast=False)

# Si usas Gunicorn, NO uses app.run() o socketio.run()
# Gunicorn manejará la ejecución.

# if __name__ == '__main__':
#     # Este bloque sólo se usa para desarrollo local (no en Render con Gunicorn)
#     # Si quieres correr localmente con eventlet:
#     # socketio.run(app, host='0.0.0.0', port=5000)
#     pass # Se deja vacío para que Gunicorn tome el control
