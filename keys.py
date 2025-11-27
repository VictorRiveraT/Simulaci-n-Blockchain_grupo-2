import ecdsa
import ecdsa.util
import hashlib
import binascii

CURVE = ecdsa.SECP256k1
HASH_ALGORITHM = hashlib.sha256

class Keys:

    @staticmethod
    def generate_key_pair() -> tuple[str, str]:
        private_key = ecdsa.SigningKey.generate(curve=CURVE)
        public_key = private_key.get_verifying_key()
        
        private_key_hex = binascii.hexlify(private_key.to_string()).decode('utf-8')
        public_key_hex = binascii.hexlify(public_key.to_string()).decode('utf-8')
        
        return private_key_hex, public_key_hex

    @staticmethod
    def sign_message(private_key_hex: str, message: str) -> str:
        private_key_bytes = binascii.unhexlify(private_key_hex)
        private_key = ecdsa.SigningKey.from_string(private_key_bytes, curve=CURVE)
        
        message_bytes = message.encode('utf-8')
        message_hash = HASH_ALGORITHM(message_bytes).digest()
        
        signature = private_key.sign(message_hash)
        return binascii.hexlify(signature).decode('utf-8')

    @staticmethod
    def verify_signature(public_key_hex: str, signature_hex: str, message_hash_hex: str) -> bool:
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
