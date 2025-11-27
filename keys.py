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
        
        public_key_hex_uncompressed = '04' + public_key_hex 
        
        return private_key_hex, public_key_hex_uncompressed

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

    @staticmethod
    def verify_signature(public_key_hex: str, signature_hex: str, message_hash_hex: str) -> bool:
        """ 
        Verifica una firma contra un hash (digest). 
        """
        try:
            if public_key_hex.startswith('04'):
                public_key_hex = public_key_hex[2:]

            public_key_bytes = binascii.unhexlify(public_key_hex)
            public_key = ecdsa.VerifyingKey.from_string(public_key_bytes, curve=CURVE)
            signature_bytes = binascii.unhexlify(signature_hex)
            message_hash = binascii.unhexlify(message_hash_hex)
            
            return public_key.verify_digest(
                signature_bytes, 
                message_hash,
                sigdecode=ecdsa.util.sigdecode_der
            )
            
        except (ecdsa.BadSignatureError, binascii.Error, ValueError, ecdsa.keys.MalformedPointError):
            return False
