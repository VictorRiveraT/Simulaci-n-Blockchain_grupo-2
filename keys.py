import ecdsa
import ecdsa.util
import hashlib
import binascii

CURVE = ecdsa.SECP256k1
HASH_ALGORITHM = hashlib.sha256

class Keys:
    """
    Clase para manejar la generación de llaves ECDSA, firmas y verificación.
    """

    @staticmethod
    def generate_key_pair() -> tuple[str, str]:
        """
        Genera un par de llaves (privada y pública) usando ECDSA.
        
        Retorna:
            (str, str): Clave privada (hex) y Clave pública (hex).
        """
        private_key = ecdsa.SigningKey.generate(curve=CURVE)
        
        public_key = private_key.get_verifying_key()
        
        private_key_hex = binascii.hexlify(private_key.to_string()).decode('utf-8')
        public_key_hex = binascii.hexlify(public_key.to_string()).decode('utf-8')
        
        return private_key_hex, public_key_hex

    @staticmethod
    def sign_message(private_key_hex: str, message: str) -> str:
        """
        Firma un mensaje usando la llave privada.
        
        Args:
            private_key_hex (str): La llave privada en formato hexadecimal.
            message (str): El mensaje a firmar (usualmente el hash de la transacción).
        
        Retorna:
            str: La firma en formato hexadecimal.
        """
        private_key_bytes = binascii.unhexlify(private_key_hex)
        private_key = ecdsa.SigningKey.from_string(private_key_bytes, curve=CURVE)
        
        message_bytes = message.encode('utf-8')
        message_hash = HASH_ALGORITHM(message_bytes).digest()
        
        signature = private_key.sign(message_hash)
        
        return binascii.hexlify(signature).decode('utf-8')

    @staticmethod
    def verify_signature(public_key_hex: str, signature_hex: str, message_hash_hex: str) -> bool:
        """
        Verifica una firma usando la llave pública.
        
        Args:
            public_key_hex (str): La llave pública en formato hexadecimal.
            signature_hex (str): La firma DER-encoded en formato hexadecimal.
            message_hash_hex (str): El hash SHA-256 del mensaje en formato hexadecimal.
        
        Retorna:
            bool: True si la firma es válida, False en caso contrario.
        """
        try:
            public_key_bytes = binascii.unhexlify(public_key_hex)
            public_key = ecdsa.VerifyingKey.from_string(public_key_bytes, curve=CURVE)
            
            signature_bytes = binascii.unhexlify(signature_hex)
            
            message_hash = binascii.unhexlify(message_hash_hex)
            
            return public_key.verify_digest(
                signature_bytes, 
                message_hash,
                sigdecode=ecdsa.util.sigdecode_der
            )
            
        except (ecdsa.BadSignatureError, binascii.Error, ValueError):
            return False
