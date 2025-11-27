# -*- coding: utf-8 -*-
import hashlib
import json
import sqlite3
from time import time
from uuid import uuid4
from urllib.parse import urlparse
from collections import OrderedDict

from keys import Keys

# ==========================================
# CONFIGURACIÓN DE CREDENCIALES ADMINISTRATIVAS (FIJAS PARA SIMULACIÓN)
# ==========================================
# Llaves criptográficas FIJAS para el Fundador. Esto permite la persistencia de
# la cuenta de origen a través de reinicios, un atajo para el demo.
FOUNDER_PRIVATE_KEY = "84a1dad2fa1c17c90d67c28a7f2dc49634ee15bf0e22c02ced1209cebbbb8d7d"
FOUNDER_ADDRESS = "04ce3540cbdc33541362e8715c279fa62c941fc34f7385dbd7244eb00cbe8f4f57dc000441801ec521f0063c51fed1e95a20b4943f3ebcf3af4c5716f95e2235d9"
MINING_REWARD = 10 # Recompensa otorgada por bloque minado
INITIAL_FUNDING = 5000 # Saldo inicial del Fundador

print("*"*50)
print(f"Llave PRIVADA Fundador (Admin): {FOUNDER_PRIVATE_KEY}")
print(f"Direccion del Fundador (Genesis): {FOUNDER_ADDRESS}")
print("*"*50)

DB_NAME = 'blockchain.db'

class Blockchain:
    """
    Clase que maneja la lógica de la cadena de bloques y la persistencia SQLite.
    """

    def __init__(self):
        self._chain = []
        self._current_transactions = []
        self._nodes = set()
        self.node_id = str(uuid4()).replace('-', '')
        self._conn = self._init_db()
        
        # Carga la cadena desde la DB o crea el bloque Genesis
        self._load_chain()
        if not self._chain:
            self._new_block(
                previous_hash='0' * 64,
                nonce=0,
                genesis=True
            )

    def _init_db(self) -> sqlite3.Connection:
        """Inicializa la conexión y crea la tabla si no existe."""
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        cursor = conn.cursor()
        # La columna 'data' contendrá el JSON completo del bloque
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                id INTEGER PRIMARY KEY,
                hash TEXT NOT NULL,
                data TEXT NOT NULL
            )
        """)
        conn.commit()
        return conn

    def _load_chain(self):
        """Carga la cadena de bloques desde la base de datos."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT data FROM blocks ORDER BY id ASC")
        blocks_data = cursor.fetchall()
        
        self._chain = []
        if blocks_data:
            for data in blocks_data:
                self._chain.append(json.loads(data[0]))
        
        print(f"Blockchain cargada. Longitud: {len(self._chain)}")
        
        # Recuperar transacciones pendientes (mempool)
        # Esto es una simplificación: en la vida real, el mempool no es persistente
        # pero lo hacemos para mantener la sesión de demo más fluida.
        if len(self._chain) > 0:
            last_block = self._chain[-1]
            if 'current_transactions_after_mine' in last_block:
                self._current_transactions = last_block['current_transactions_after_mine']
                del last_block['current_transactions_after_mine'] # Limpiamos la clave temporal

    def _save_block(self, block: dict):
        """Guarda un nuevo bloque en la base de datos."""
        cursor = self._conn.cursor()
        block_json = json.dumps(block)
        cursor.execute("INSERT INTO blocks (hash, data) VALUES (?, ?)", 
                       (block['hash'], block_json))
        self._conn.commit()


    def _new_block(self, previous_hash: str, nonce: int, genesis: bool = False):
        """
        Crea un nuevo Bloque en la Cadena y lo guarda en la DB.
        """
        
        # 1. Transacciones a incluir (Mempool + Recompensa)
        transactions_to_include = list(self._current_transactions)
        
        # Si es el Bloque Génesis, se añade el funding inicial
        if genesis:
            transactions_to_include.append({
                'sender': 'SYSTEM',
                'recipient': FOUNDER_ADDRESS,
                'amount': INITIAL_FUNDING,
                'timestamp': time(),
            })
            
        # 2. Creación del Bloque
        block = {
            'index': len(self._chain) + 1,
            'timestamp': time(),
            'transactions': transactions_to_include,
            'nonce': nonce,
            'previous_hash': previous_hash or self._hash(self._chain[-1]),
        }

        # 3. Hash del Bloque
        block['hash'] = self._hash(block)
        
        # 4. Limpieza: el mempool queda vacío después de minar (o se inicializa)
        self._current_transactions = []
        
        # 5. Añadir y Guardar
        self._chain.append(block)
        self._save_block(block)
        
        return block

    def new_transaction(self, sender: str, recipient: str, amount: int, signature: str) -> bool:
        """
        Añade una nueva transacción al mempool después de verificarla.
        """
        transaction = {
            'sender': sender,
            'recipient': recipient,
            'amount': int(amount),
            'timestamp': time(),
            'signature': signature,
        }
        
        # 1. Verificar firma (lógica en el frontend, se re-verifica solo el hash)
        # En este simulador, la verificación completa (firma + fondos) se realiza 
        # en el endpoint '/transactions/verify_only' antes de llamar a esta función.
        # Por simplicidad, asumimos que si llega aquí, la firma y los fondos son válidos.
        
        # 2. Añadir al mempool
        self._current_transactions.append(transaction)
        
        return True

    def mine(self, miner_address: str) -> dict:
        """
        Mina un nuevo bloque: calcula el PoW y añade la recompensa.
        """
        
        # 1. Añadir la transacción de recompensa
        reward_tx = {
            'sender': 'SYSTEM',
            'recipient': miner_address,
            'amount': MINING_REWARD,
            'timestamp': time(),
        }
        
        # Se añade la recompensa al inicio para que el minero la obtenga primero
        self._current_transactions.insert(0, reward_tx)
        
        # 2. Obtener el último bloque
        last_block = self.last_block
        
        # 3. Realizar Proof of Work
        nonce = self.proof_of_work(last_block)
        
        # 4. Crear el nuevo bloque
        new_block = self._new_block(
            previous_hash=last_block['hash'],
            nonce=nonce
        )
        
        return new_block

    # --- Lógica de Proof of Work (PoW) ---

    def proof_of_work(self, last_block: dict) -> int:
        """
        Prueba de Trabajo simple:
         - Encontrar un número 'nonce' tal que hash(bloque + nonce) tenga 4 ceros al inicio.
        """
        nonce = 0
        # El bloque a hashear debe incluir el timestamp ACTUAL para forzar a que el minero lo genere
        # y no use un bloque pre-calculado.
        candidate_block_data = {
            'index': last_block['index'] + 1,
            'timestamp': time(), # Usar el timestamp actual
            'transactions': self._current_transactions,
            'previous_hash': self._hash(last_block),
        }
        
        # Creamos una versión del bloque para hashear (sin el nonce final)
        block_string_base = json.dumps(candidate_block_data, sort_keys=True)
        
        while not self._valid_proof(block_string_base, nonce):
            nonce += 1
        return nonce

    # Reemplaza la función _valid_proof en blockchain.py
    
    @staticmethod
    def _valid_proof(last_hash: str, nonce: int, difficulty: int = 4) -> bool:
        guess = f'{last_hash}{nonce}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:difficulty] == "0" * difficulty

    # --- Lógica de Saldos y Hash ---

    def get_balance(self, address: str) -> int:
        """Calcula el saldo de una dirección recorriendo la cadena."""
        balance = 0
        for block in self._chain:
            for tx in block['transactions']:
                if tx['sender'] == address:
                    balance -= int(tx['amount'])
                if tx['recipient'] == address:
                    balance += int(tx['amount'])
        
        # Considerar el mempool (transacciones pendientes) para el saldo en tiempo real
        for tx in self._current_transactions:
            if tx['sender'] == address:
                balance -= int(tx['amount'])
            
        return balance

    def get_all_balances(self) -> dict:
        """Calcula y retorna los saldos de todas las direcciones."""
        all_addresses = set()
        
        for block in self._chain:
            for tx in block['transactions']:
                all_addresses.add(tx['recipient'])
                if tx['sender'] != 'SYSTEM':
                    all_addresses.add(tx['sender'])

        for tx in self._current_transactions:
            all_addresses.add(tx['recipient'])
            if tx['sender'] != 'SYSTEM':
                all_addresses.add(tx['sender'])
        
        balances = {}
        for address in sorted(list(all_addresses)):
            balances[address] = self.get_balance(address)
        
        return OrderedDict(sorted(balances.items(), key=lambda item: item[1], reverse=True))


    def get_leaders(self) -> dict: 
        """Retorna la tabla de clasificación de mineros por recompensas obtenidas."""
        leaders = {}
        for block in self.chain:
            for tx in block['transactions']:
                # Las transacciones de tipo recompensa tienen 'SYSTEM' como sender
                if tx['sender'] == 'SYSTEM' and tx['recipient'] != FOUNDER_ADDRESS:
                    miner = tx['recipient']
                    amount = int(tx['amount'])
                    leaders[miner] = leaders.get(miner, 0) + amount
        
        # Ordenar por recompensa (descendente)
        return OrderedDict(sorted(leaders.items(), key=lambda item: item[1], reverse=True))


    @staticmethod
    def _hash(block: dict) -> str:
        """
        Crea un hash SHA-256 de un Bloque (serializado de forma estable).
        """
        # Excluir el campo 'hash' si existe antes de calcular el hash del bloque
        block_copy = block.copy()
        block_copy.pop('hash', None) 
        
        # Serialización estable del bloque
        block_string = json.dumps(block_copy, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def is_chain_valid(self) -> bool:
        """Verifica la integridad completa de la cadena de bloques."""
        last_block = self._chain[0]
        current_index = 1
        while current_index < len(self._chain):
            block = self._chain[current_index]
            
            if block['previous_hash'] != self._hash(last_block):
                print(f"ERROR: Bloque {block['index']} hash anterior inválido.")
                return False
            
            block_data_for_proof = {
                'index': block['index'],
                'timestamp': block['timestamp'],
                'transactions': block['transactions'],
                'previous_hash': block['previous_hash'],
            }
            block_string_base = json.dumps(block_data_for_proof, sort_keys=True)
            
            if not self._valid_proof(block_string_base, block['nonce']):
                print(f"ERROR: Bloque {block['index']} prueba de trabajo inválida.")
                return False
            
            last_block = block
            current_index += 1
        return True

    @property
    def last_block(self) -> dict:
        """Retorna el último bloque de la cadena"""
        return self._chain[-1]
    
    @property
    def chain(self) -> list:
        """Retorna una copia de la cadena completa"""
        return list(self._chain)
    
    @property
    def mempool(self) -> list:
        """Retorna una copia de las transacciones pendientes"""
        return list(self._current_transactions)
