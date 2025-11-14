import hashlib
import json
from time import time
from uuid import uuid4
from urllib.parse import urlparse

from keys import Keys

FOUNDER_ADDRESS = "0000_GENESIS_0000"
MINING_REWARD = 10

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
        """
        Agrega un nuevo nodo a la lista de nodos
        :param address: (str) Dirección del nodo. Ej. 'http://192.168.0.5:5000'
        """
        parsed_url = urlparse(address)
        if parsed_url.netloc:
            self._nodes.add(parsed_url.netloc)
        elif parsed_url.path:
            self._nodes.add(parsed_url.path)
        else:
            raise ValueError('URL inválida')

    def _new_block(self, previous_hash: str, nonce: int, genesis: bool = False):
        """
        Crea un nuevo Bloque en la Cadena
        :param previous_hash: (str) Hash del Bloque anterior
        :param nonce: (int) El nonce encontrado por la Prueba de Trabajo
        :param genesis: (bool) True si es el bloque génesis
        """

        transactions_in_block = []

        if genesis:
            transactions_in_block.append({
                'sender_public_key': "SYSTEM",
                'recipient': FOUNDER_ADDRESS,
                'amount': 5000.0,
                'signature': "SYSTEM_SIGNATURE"
            })
        else:
            transactions_in_block.append({
                'sender_public_key': "SYSTEM",
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

    def new_transaction(self, sender_public_key: str, recipient: str, amount: float, signature: str, message_hash: str) -> tuple[bool, str]:
        """
        Agrega una nueva transacción al 'mempool' después de una doble verificación.
        
        :param sender_public_key: (str) Llave Pública (Dirección) del remitente
        :param recipient: (str) Llave Pública (Dirección) del destinatario
        :param amount: (float) Monto
        :param signature: (str) Firma de la transacción
        :param message_hash: (str) Hash SHA-256 del mensaje en hexadecimal
        
        :return: (bool, str) (True/False si fue exitosa, Mensaje de estado)
        """

        current_balance = self.get_balance(sender_public_key)
        if current_balance < amount:
            return False, f"Verificación de fondos fallida. El remitente solo tiene {current_balance}."
        
        amount_str = str(int(amount)) if amount == int(amount) else str(amount)
        expected_message = f"{sender_public_key}{recipient}{amount_str}"
        expected_hash = hashlib.sha256(expected_message.encode('utf-8')).hexdigest()
        
        if message_hash != expected_hash:
            return False, f"Verificación de hash fallida. El hash del mensaje no coincide. Esperado: {expected_hash}, Recibido: {message_hash}"
        
        if not Keys.verify_signature(sender_public_key, signature, message_hash):
            return False, "Verificación de firma fallida. La firma no es válida."

        self._current_transactions.append({
            'sender_public_key': sender_public_key,
            'recipient': recipient,
            'amount': amount,
            'signature': signature
        })

        return True, "Transacción verificada y añadida al Mempool."

    def get_balance(self, public_key_address: str) -> float:
        """
        Calcula el saldo de una dirección (public_key) recorriendo toda la blockchain
        y el mempool.
        """
        balance = 0.0
        
        for block in self._chain:
            for tx in block['transactions']:
                if tx['recipient'] == public_key_address:
                    balance += float(tx['amount'])
                
                if tx['sender_public_key'] == public_key_address:
                    balance -= float(tx['amount'])
        
        for tx in self._current_transactions:
            if tx['sender_public_key'] == public_key_address:
                balance -= float(tx['amount'])
                
        return balance

    @staticmethod
    def _hash(block: dict) -> str:
        """
        Crea un hash SHA-256 de un Bloque
        :param block: (dict) Bloque
        :return: (str) Hash
        """
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

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

    def proof_of_work(self, last_block: dict) -> int:
        """
        Prueba de Trabajo simple:
         - Encontrar un número 'p' (nonce) tal que hash(hash_anterior + nonce) tenga 4 ceros al inicio
        """
        last_hash = self._hash(last_block)
        nonce = 0
        while not self._valid_proof(last_hash, nonce):
            nonce += 1
        return nonce

    @staticmethod
    def _valid_proof(last_hash: str, nonce: int, difficulty: int = 4) -> bool:
        """
        Valida la Prueba: ¿El hash(last_hash, nonce) contiene {difficulty} ceros al inicio?
        """
        guess = f'{last_hash}{nonce}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:difficulty] == "0" * difficulty
