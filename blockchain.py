import hashlib
import json
import sqlite3
from time import time
from uuid import uuid4
from urllib.parse import urlparse
from collections import OrderedDict

from keys import Keys

FOUNDER_PRIVATE_KEY = "84a1dad2fa1c17c90d67c28a7f2dc49634ee15bf0e22c02ced1209cebbbb8d7d"
FOUNDER_ADDRESS = "04ce3540cbdc33541362e8715c279fa62c941fc34f7385dbd7244eb00cbe8f4f57dc000441801ec521f0063c51fed1e95a20b4943f3ebcf3af4c5716f95e2235d9"
MINING_REWARD = 10

print("*"*50)
print(f"Llave PRIVADA Fundador (Admin): {FOUNDER_PRIVATE_KEY}")
print(f"Direccion del Fundador (Genesis): {FOUNDER_ADDRESS}")
print("*"*50)

DB_NAME = 'Blockchain.db'

class Blockchain:
    """
    Clase principal que gestiona la estructura de datos de la blockchain,
    la persistencia en base de datos SQLite y la lógica de consenso (PoW).
    """

    def __init__(self):
        self.conn = self._connect_db()
        self._create_tables()
        self._chain = []
        self._current_transactions = [] 
        self._nodes = set()
        self.node_id = str(uuid4()).replace('-', '')

        self._load_chain_from_db()
        self._load_mempool_from_db()

    def _connect_db(self):
        """
        Establece la conexión con la base de datos SQLite.
        Configura el row_factory para acceder a columnas por nombre.
        """
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_tables(self):
        """
        Inicializa el esquema de base de datos si no existe.
        Crea tablas para almacenar bloques confirmados y el mempool.
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blocks (
                "index" INTEGER PRIMARY KEY,
                block_data TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mempool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_data TEXT NOT NULL
            )
        ''')
        self.conn.commit()

    def _load_chain_from_db(self):
        """
        Recupera la cadena de bloques completa desde la base de datos.
        Si la base de datos está vacía, inicializa el Bloque Génesis.
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT block_data FROM blocks ORDER BY "index" ASC')
        rows = cursor.fetchall()
        
        if not rows:
            print("Base de datos vacia. Inicializando Bloque Genesis...")
            self._new_block(previous_hash='0' * 64, nonce=0, genesis=True)
        else:
            print(f"Cargando {len(rows)} bloques desde la base de datos...")
            self._chain = [json.loads(row['block_data']) for row in rows]

    def _load_mempool_from_db(self):
        """
        Recupera las transacciones pendientes (Mempool) desde la base de datos.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT tx_data FROM mempool")
        rows = cursor.fetchall()
        self._current_transactions = [json.loads(row['tx_data']) for row in rows]

    @staticmethod
    def _stable_hash_payload(payload: dict) -> str:
        """
        Genera un hash SHA-256 determinista de un diccionario.
        Ordena las claves para garantizar consistencia en la firma digital.
        """
        sorted_payload = OrderedDict(sorted(payload.items()))
        payload_string = json.dumps(sorted_payload, separators=(',', ':')).encode()
        return hashlib.sha256(payload_string).hexdigest()

    def _build_block_struct(self, index, timestamp, transactions, nonce, previous_hash):
        """
        Método auxiliar para estandarizar la estructura de datos del bloque.
        Garantiza que el objeto bloque sea idéntico durante el minado y el guardado.
        """
        return {
            'index': index,
            'timestamp': timestamp,
            'transactions': transactions,
            'nonce': nonce,
            'previous_hash': previous_hash,
        }

    def _new_block(self, previous_hash: str, nonce: int, genesis: bool = False, current_time: float = None):
        """
        Crea un nuevo bloque, lo añade a la cadena y persiste el estado en la BD.
        """
        transactions_in_block = []
        
        if genesis:
            transactions_in_block.append({
                'sender': "SYSTEM", 
                'recipient': FOUNDER_ADDRESS, 
                'amount': 5000, 
                'signature': "SYSTEM_SIGNATURE"
            })
        else:
            transactions_in_block.append({
                'sender': "SYSTEM", 
                'recipient': self.node_id,
                'amount': MINING_REWARD, 
                'signature': "SYSTEM_SIGNATURE"
            })
            transactions_in_block.extend(self._current_transactions)

        block = self._build_block_struct(
            index=len(self._chain) + 1,
            timestamp=current_time or time(),
            transactions=transactions_in_block,
            nonce=nonce,
            previous_hash=previous_hash or self._hash(self.last_block)
        )

        block_string = json.dumps(block, sort_keys=True)
        cursor = self.conn.cursor()
        try:
            cursor.execute('INSERT INTO blocks ("index", block_data) VALUES (?, ?)',
                           (block['index'], block_string))
            
            if not genesis:
                cursor.execute("DELETE FROM mempool")
            
            self.conn.commit()
            
            self._current_transactions = []
            self._chain.append(block)
            return block
            
        except sqlite3.IntegrityError:
            print("Error de integridad: El bloque ya existe en la BD.")
            return None

    def new_transaction(self, sender_pub: str, recipient: str, amount: int, signature: str) -> tuple[bool, str]:
        """
        Crea una nueva transacción, la valida y la añade al Mempool.
        """
        is_valid, message = self.verify_transaction(sender_pub, recipient, amount, signature)
        
        if not is_valid:
            return False, message
        
        tx_payload = {
            'sender': sender_pub, 
            'recipient': recipient,
            'amount': amount, 
            'signature': signature,
            'timestamp': time()
        }
        
        tx_string = json.dumps(tx_payload)
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO mempool (tx_data) VALUES (?)", (tx_string,))
        self.conn.commit()

        self._current_transactions.append(tx_payload)
        return True, "Transaccion verificada y anadida al Mempool."
    
    def proof_of_work(self, last_block: dict, current_time: float = None) -> int:
        """
        Algoritmo de Consenso (PoW): Encuentra un número 'nonce' tal que el hash del bloque
        comience con 4 ceros.
        """
        nonce = 0
        
        transactions_in_block = []
        transactions_in_block.append({
            'sender': "SYSTEM", 
            'recipient': self.node_id,
            'amount': MINING_REWARD, 
            'signature': "SYSTEM_SIGNATURE"
        })
        transactions_in_block.extend(self._current_transactions)
        
        previous_hash = self._hash(last_block)
        
        while True:
            guess_block = self._build_block_struct(
                index=len(self._chain) + 1,
                timestamp=current_time or time(),
                transactions=transactions_in_block,
                nonce=nonce,
                previous_hash=previous_hash
            )

            guess_hash = self._hash(guess_block)
            
            if guess_hash[:4] == "0000":
                return nonce
            
            nonce += 1
    
    @staticmethod
    def _hash(block: dict) -> str:
        """
        Genera el hash SHA-256 de un bloque.
        """
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def verify_transaction(self, sender_pub: str, recipient: str, amount: int, signature: str) -> tuple[bool, str]:
        """
        Verifica la validez criptográfica y financiera de una transacción.
        """
        current_balance = self.get_balance(sender_pub)
        if current_balance < amount:
            return False, f"Fondos insuficientes. Saldo actual: {current_balance}."

        payload = {
            'amount': amount, 
            'recipient': recipient, 
            'sender': sender_pub
        }
        message_hash_hex = self._stable_hash_payload(payload)
        
        if not Keys.verify_signature(sender_pub, signature, message_hash_hex):
            return False, "Verificacion de firma fallida. Firma invalida."

        return True, "Transaccion valida."

    def get_balance(self, public_key_address: str) -> int:
        """
        Calcula el saldo de una dirección recorriendo todo el historial de transacciones (UTXO simplificado).
        """
        balance = 0
        for block in self._chain:
            for tx in block['transactions']:
                if tx['recipient'] == public_key_address:
                    balance += int(tx['amount'])
                if tx['sender'] == public_key_address:
                    balance -= int(tx['amount'])
        
        for tx in self._current_transactions:
            if tx['sender'] == public_key_address:
                balance -= int(tx['amount'])
        return balance

    def issue_faucet_funds(self, recipient_address: str, amount: int = 100) -> tuple[bool, str]:
        """
        Genera una transacción especial firmada por el Fundador para distribuir fondos.
        """
        founder_balance = self.get_balance(FOUNDER_ADDRESS)
        if founder_balance < amount:
            return False, "El Faucet no tiene fondos suficientes."

        payload = {'amount': amount, 'recipient': recipient_address, 'sender': FOUNDER_ADDRESS}
        message_hash_hex = self._stable_hash_payload(payload)
        signature = Keys.sign_digest(FOUNDER_PRIVATE_KEY, message_hash_hex)
        
        if not signature:
            return False, "Error critico en la firma del Faucet."

        return self.new_transaction(
            sender_pub=FOUNDER_ADDRESS,
            recipient=recipient_address,
            amount=amount,
            signature=signature
        )

    def get_all_balances(self) -> dict:
        """
        Retorna un diccionario con los saldos de todas las direcciones conocidas.
        """
        all_addresses = set()
        for block in self.chain:
            for tx in block['transactions']:
                if tx['sender'] != "SYSTEM":
                    all_addresses.add(tx['sender'])
                all_addresses.add(tx['recipient'])
        
        balances = {}
        for address in all_addresses:
            balances[address] = self.get_balance(address)
        return balances

    def get_leaders(self) -> dict:
        """
        Calcula el ranking de mineros basado en las recompensas acumuladas.
        """
        leaders = {}
        for block in self.chain:
            for tx in block['transactions']:
                if tx['sender'] == "SYSTEM" and tx['recipient'] != FOUNDER_ADDRESS:
                    miner = tx['recipient']
                    amount = int(tx['amount'])
                    leaders[miner] = leaders.get(miner, 0) + amount
        return leaders

    def is_chain_valid(self) -> bool:
        """
        Verifica la integridad completa de la cadena de bloques.
        Comprueba enlaces de hash y pruebas de trabajo.
        """
        last_block = self._chain[0]
        current_index = 1
        while current_index < len(self._chain):
            block = self._chain[current_index]
            
            if block['previous_hash'] != self._hash(last_block):
                return False
            
            if not self._valid_proof(self._hash(last_block), block['nonce']):
                return False
            
            last_block = block
            current_index += 1
        return True

    @staticmethod
    def _valid_proof(last_hash: str, nonce: int, difficulty: int = 4) -> bool:
        """
        Valida si un nonce cumple con la dificultad objetivo.
        """
        guess = f'{last_hash}{nonce}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:difficulty] == "0" * difficulty
    
    @property
    def last_block(self) -> dict:
        return self._chain[-1]
    @property
    def chain(self) -> list:
        return list(self._chain)
    @property
    def mempool(self) -> list:
        return list(self._current_transactions)
