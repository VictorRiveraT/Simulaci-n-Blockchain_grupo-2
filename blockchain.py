import hashlib
import json
from time import time
from uuid import uuid4
from urllib.parse import urlparse
from collections import OrderedDict

from keys import Keys

# --- CONSTANTES MODIFICADAS ---
# 1. Generar un par de llaves permanente para el Fundador/Génesis
_FOUNDER_KEYS = Keys.generate_key_pair()
FOUNDER_PRIVATE_KEY = _FOUNDER_KEYS[0]
FOUNDER_ADDRESS = _FOUNDER_KEYS[1] # Esta es ahora la dirección pública
MINING_REWARD = 10

print("*"*50)
print(f"🔑 Dirección del Fundador (Génesis): {FOUNDER_ADDRESS}")
print(f"💰 El Fundador tiene 5000 monedas para usar como Faucet.")
print("*"*50)
# --- FIN DE MODIFICACIÓN ---


class Blockchain:
    """
    Clase que maneja la lógica de la cadena de bloques.
    """

    def __init__(self):
        self._chain = []
        self._current_transactions = [] 
        self._nodes = set()

        self.node_id = str(uuid4()).replace('-', '')

        self._new_block(
            previous_hash='0' * 64,
            nonce=0,
            genesis=True
        )

    def register_node(self, address: str):
        parsed_url = urlparse(address)
        if parsed_url.netloc:
            self._nodes.add(parsed_url.netloc)
        elif parsed_url.path:
            self._nodes.add(parsed_url.path)
        else:
            raise ValueError('URL inválida')

    @staticmethod
    def _stable_hash_payload(payload: dict) -> str:
        """
        Crea un hash SHA-256 de un diccionario de payload, ordenando
        las claves para consistencia.
        """
        sorted_payload = OrderedDict(sorted(payload.items()))
        payload_string = json.dumps(sorted_payload, separators=(',', ':')).encode()
        return hashlib.sha256(payload_string).hexdigest()

    def _new_block(self, previous_hash: str, nonce: int, genesis: bool = False):
        transactions_in_block = []

        if genesis:
            transactions_in_block.append({
                'sender': "SYSTEM",
                'recipient': FOUNDER_ADDRESS, # Ahora usa la llave pública generada
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
            'timestamp': time(),
            'transactions': transactions_in_block,
            'nonce': nonce,
            'previous_hash': previous_hash or self._hash(self.last_block),
        }

        self._current_transactions = []
        self._chain.append(block)
        return block

    def new_transaction(self, sender_pub: str, recipient: str, amount: int, signature: str) -> tuple[bool, str]:
        """
        Verifica y luego agrega una nueva transacción al 'mempool'.
        """
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
        """
        Calcula el saldo (entero) de una dirección.
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

    def get_all_balances(self) -> dict:
        """
        Retorna un diccionario con los saldos de todas las direcciones.
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
        Calcula y retorna las recompensas totales por minero.
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
        Verifica si la cadena de bloques es válida (hashes y PoW).
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

    # --- NUEVA FUNCIÓN AÑADIDA ---
    def issue_faucet_funds(self, recipient_address: str, amount: int = 100) -> tuple[bool, str]:
        """
        El Fundador (dueño del nodo) firma y envía fondos
        a una dirección como un 'Faucet'.
        """
        
        # 1. Verificar que el fundador tenga fondos
        founder_balance = self.get_balance(FOUNDER_ADDRESS)
        if founder_balance < amount:
            return False, "El Faucet está vacío. El Fundador no tiene fondos."

        # 2. Crear el payload de la transacción
        payload = {
            'amount': amount,
            'recipient': recipient_address,
            'sender': FOUNDER_ADDRESS
        }
        
        # 3. Hashear el payload
        message_hash_hex = self._stable_hash_payload(payload)
        
        # 4. Firmar el hash con la LLAVE PRIVADA del Fundador
        signature = Keys.sign_digest(FOUNDER_PRIVATE_KEY, message_hash_hex)
        
        if not signature:
            return False, "Error interno al firmar la transacción del Faucet."

        # 5. Enviar la transacción a la red (al mempool)
        return self.new_transaction(
            sender_pub=FOUNDER_ADDRESS,
            recipient=recipient_address,
            amount=amount,
            signature=signature
        )

    @staticmethod
    def _hash(block: dict) -> str:
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self) -> dict:
        return self._chain[-1]
    
    @property
    def chain(self) -> list:
        return list(self._chain)
    
    @property
    def mempool(self) -> list:
        return list(self._current_transactions)

    def proof_of_work(self, last_block: dict) -> int:
        last_hash = self._hash(last_block)
        nonce = 0
        while not self._valid_proof(last_hash, nonce):
            nonce += 1
        return nonce

    @staticmethod
    def _valid_proof(last_hash: str, nonce: int, difficulty: int = 4) -> bool:
        guess = f'{last_hash}{nonce}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:difficulty] == "0" * difficulty
