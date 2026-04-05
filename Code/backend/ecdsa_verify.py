import base64
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature


def verify_signature(public_key_b64: str, message: str, signature_b64: str) -> bool:
    """Verify an ECDSA P-256 signature from the browser's WebCrypto API.

    WebCrypto produces signatures in IEEE P1363 format (raw r||s, 64 bytes),
    but Python's cryptography library expects DER format. We convert here.
    """
    try:
        # Decode the raw public key bytes from browser (65 bytes uncompressed point)
        pub_bytes = base64.b64decode(public_key_b64)
        public_key = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), pub_bytes
        )

        # Decode the raw r||s signature from WebCrypto (64 bytes for P-256)
        sig_bytes = base64.b64decode(signature_b64)

        # Convert IEEE P1363 (r||s) → DER format
        # Each of r and s is 32 bytes for P-256
        r = int.from_bytes(sig_bytes[:32], "big")
        s = int.from_bytes(sig_bytes[32:], "big")
        der_sig = utils.encode_dss_signature(r, s)

        # Verify using SHA-256
        public_key.verify(
            der_sig,
            message.encode("utf-8"),
            ec.ECDSA(hashes.SHA256()),
        )
        return True
    except (InvalidSignature, Exception) as e:
        print(f"ECDSA verify failed: {e}")
        return False
