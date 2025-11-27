import ecdsa
import ecdsa.util
import hashlib
import binascii

CURVE = ecdsa.SECP256k1
HASH_ALGORITHM = hashlib.sha256

class Keys:
    """
    Clase utilitaria para la gestión de criptografía de curva elíptica (ECDSA).
    Proporciona métodos estáticos para la generación de pares de claves,
    firma de mensajes y verificación de firmas digitales.
    """

    @staticmethod
    def generate_key_pair() -> tuple[str, str]:
        """
        Genera un nuevo par de claves (privada y pública) utilizando la curva SECP256k1.
        
        Retorna:
            tuple[str, str]: Una tupla conteniendo (llave_privada_hex, llave_publica_hex).
        """
        private_key = ecdsa.SigningKey.generate(curve=CURVE)
        public_key = private_key.get_verifying_key()
        
        private_key_hex = binascii.hexlify(private_key.to_string()).decode('utf-8')
        public_key_hex = binascii.hexlify(public_key.to_string()).decode('utf-8')
        
        return private_key_hex, public_key_hex

    @staticmethod
    def sign_message(private_key_hex: str, message: str) -> str:
        """
        Firma un mensaje de texto plano.
        Calcula el hash del mensaje internamente antes de firmarlo.
        
        Parámetros:
            private_key_hex (str): La llave privada en formato hexadecimal.
            message (str): El mensaje a firmar.
            
        Retorna:
            str: La firma digital en formato hexadecimal (codificación DER).
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
        Verifica la validez de una firma digital contra un hash de mensaje dado.
        
        Parámetros:
            public_key_hex (str): La llave pública del firmante en hexadecimal.
            signature_hex (str): La firma digital a verificar en hexadecimal.
            message_hash_hex (str): El hash del mensaje original en hexadecimal.
            
        Retorna:
            bool: True si la firma es válida y corresponde a la llave pública, False en caso contrario.
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

    @staticmethod
    def sign_digest(private_key_hex: str, digest_hex: str) -> str:
        """
        Firma un hash (digest) pre-calculado.
        Utilizado cuando el payload ya ha sido hasheado externamente (ej: transacciones).
        
        Parámetros:
            private_key_hex (str): La llave privada en formato hexadecimal.
            digest_hex (str): El hash del mensaje a firmar en hexadecimal.
            
        Retorna:
            str: La firma digital en formato hexadecimal, o cadena vacía en caso de error.
        """
        try:
            private_key_bytes = binascii.unhexlify(private_key_hex)
            private_key = ecdsa.SigningKey.from_string(private_key_bytes, curve=CURVE)
            message_hash = binascii.unhexlify(digest_hex)
            
            signature = private_key.sign_digest(
                message_hash,
                sigencode=ecdsa.util.sigencode_der
            )
            
            return binascii.hexlify(signature).decode('utf-8')
            
        except (binascii.Error, ValueError):
            return ""
