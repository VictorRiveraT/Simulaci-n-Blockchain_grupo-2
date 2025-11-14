import hashlib
import json
from time import time
from uuid import uuid4
from urllib.parse import urlparse
from collections import OrderedDict

from keys import Keys

# --- CONSTANTES GLOBALES Y SECRETAS ---
# Genera un par de llaves permanente para el Fundador/Génesis (secreta)
_FOUNDER_KEYS = Keys.generate_key_pair()
FOUNDER_PRIVATE_KEY = _FOUNDER_KEYS[0]
FOUNDER_ADDRESS = _FOUNDER_KEYS[1] 
MINING_REWARD = 10

print("*"*50)
print(f"🔑 Llave PRIVADA Fundador (Admin): {FOUNDER_PRIVATE_KEY}")
print(f"   (Copia esta llave para usar el Faucet)")
print(f"🔑 Dirección del Fundador (Génesis): {FOUNDER_ADDRESS}")
print(f"💰 El Fundador tiene 5000 monedas para usar como Faucet.")
print("*"*50)
# --- FIN DE CONSTANTES ---


class Blockchain:
    """
    Clase que maneja la lógica de la cadena de bloques.
    """

    def __init__(self):
        self._chain = []
        self._current_transactions = [] 
        self._nodes = set()
        self.node_id = str(uuid4()).replace('-', '')

        # Se llama una sola vez para crear el bloque Génesis
        self._new_block(
            previous_hash='0' * 64,
            nonce=0,
            genesis=True
        )

    @staticmethod
    def _stable_hash_payload(payload: dict) -> str:
        """
        Crea un hash SHA-256 de un diccionario de payload, ordenando
        las claves para consistencia con el JS.
        """
        sorted_payload = OrderedDict(sorted(payload.items()))
        payload_string = json.dumps(sorted_payload, separators=(',', ':')).encode()
        return hashlib.sha256(payload_string).hexdigest()

    # --- FUNCIÓN CORREGIDA: Acepta el tiempo como argumento ---
    def _new_block(self, previous_hash: str, nonce: int, genesis: bool = False, current_time: float = None):
        """
        Crea un nuevo Bloque. Usa el tiempo pasado por el endpoint /mine.
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

        block = {
            'index': len(self._chain) + 1,
            'timestamp': current_time or time(), # Usa el tiempo fijo o el actual
            'transactions': transactions_in_block,
            'nonce': nonce,
            'previous_hash': previous_hash or self._hash(self.last_block),
        }

        self._current_transactions = []
        self._chain.append(block)
        return block
    # --- FIN DE MODIFICACIÓN ---

    def new_transaction(self, sender_pub: str, recipient: str, amount: int, signature: str) -> tuple[bool, str]:
        is_valid, message = self.verify_transaction(sender_pub, recipient, amount, signature)
        
        if not is_valid:
            return False, message
        
        self._current_transactions.append({
            'sender': sender_pub,
            'recipient': recipient,
            'amount': amount,
            'signature': signature
        })
        return True, "Transacción verificada y añadida al Mempool."
    
    def verify_transaction(self, sender_pub: str, recipient: str, amount: int, signature: str) -> tuple[bool, str]:
        """
        Verifica una transacción (fondos y firma) SIN agregarla al mempool.
        """
        current_balance = self.get_balance(sender_pub)
        if current_balance < amount:
            return False, f"Verificación de fondos fallida. El remitente solo tiene {current_balance}."

        payload = {
            'amount': amount,
            'recipient': recipient,
            'sender': sender_pub
        }
        message_hash_hex = self._stable_hash_payload(payload)
        
        if not Keys.verify_signature(sender_pub, signature, message_hash_hex):
            return False, "Verificación de firma fallida. La firma no es válida."

        return True, "Transacción verificada (firma y fondos OK)."

    def get_balance(self, public_key_address: str) -> int:
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
        El Fundador (dueño del nodo) firma y envía fondos a una dirección.
        """
        founder_balance = self.get_balance(FOUNDER_ADDRESS)
        if founder_balance < amount:
            return False, "El Faucet está vacío. El Fundador no tiene fondos."

        payload = {'amount': amount, 'recipient': recipient_address, 'sender': FOUNDER_ADDRESS}
        message_hash_hex = self._stable_hash_payload(payload)
        signature = Keys.sign_digest(FOUNDER_PRIVATE_KEY, message_hash_hex)
        
        if not signature:
            return False, "Error interno al firmar la transacción del Faucet."

        return self.new_transaction(
            sender_pub=FOUNDER_ADDRESS,
            recipient=recipient_address,
            amount=amount,
            signature=signature
        )

    # --- FUNCIÓN CORREGIDA: Ahora hashea el bloque completo con tiempo fijo ---
    def proof_of_work(self, last_block: dict, current_time: float = None) -> int:
        """
        Prueba de Trabajo: Busca el nonce hasheando el BLOQUE COMPLETO
        con un timestamp fijo hasta que el hash comience con 4 ceros.
        """
        nonce = 0
        
        # Preparamos las transacciones que irán en el bloque candidato (recompensa + mempool)
        transactions_in_block = []
        transactions_in_block.append({
            'sender': "SYSTEM",
            'recipient': self.node_id,
            'amount': MINING_REWARD,
            'signature': "SYSTEM_SIGNATURE"
        })
        transactions_in_block.extend(self._current_transactions)
        
        while True:
            # Creamos el bloque candidato TEMPORAL
            guess_block = {
                'index': len(self._chain) + 1,
                'timestamp': current_time or time(), # Usa el tiempo fijo
                'transactions': transactions_in_block,
                'nonce': nonce,
                'previous_hash': self._hash(last_block),
            }

            guess_hash = self._hash(guess_block)
            
            if guess_hash[:4] == "0000":
                return nonce
            
            nonce += 1
    # --- FIN DE MODIFICACIÓN ---
    
    @staticmethod
    def _hash(block: dict) -> str:
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    # ... (el resto de las funciones de consulta: get_all_balances, get_leaders, is_chain_valid, etc. van aquí) ...

    # El resto de las funciones son las que ya teníamos (omitidas por espacio)
    def get_all_balances(self) -> dict:
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
        leaders = {}
        for block in self.chain:
            for tx in block['transactions']:
                if tx['sender'] == "SYSTEM" and tx['recipient'] != FOUNDER_ADDRESS:
                    miner = tx['recipient']
                    amount = int(tx['amount'])
                    leaders[miner] = leaders.get(miner, 0) + amount
        return leaders

    def is_chain_valid(self) -> bool:
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
