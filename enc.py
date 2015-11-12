import base64
from cryptography.fernet import Fernet
from secretsharing import PlaintextToHexSecretSharer as shamir


def encrypt(data):
    """
    Encrypt the data with a symmetric encryption scheme using a random key.
    Return the encrypted data along with the key.
    """
    key = Fernet.generate_key()         # base64-encoded 32-byte key
    f = Fernet(key)
    token = base64.urlsafe_b64decode(f.encrypt(data))

    return (key, token)


def decrypt(data, key):
    f = Fernet(key)
    token = f.decrypt(base64.urlsafe_b64encode(data))
    return token


def encrypt_and_split(data, threshold_number, total):
    """
    Encrypt the data with a symmetric encryption scheme using a random
    key. Then split the key using Shamir's secret sharing scheme into
    total number of subkeys. The key can be recreated using
    threshold_number of the subkeys generated.

    Return the subkeys along with the encrypted data.
    """
    key, encrypted_data = encrypt(data)
    shares = shamir.split_secret(key.decode(), threshold_number, total)

    return (shares, encrypted_data)


def combine_and_decrypt(data, subkeys):
    """
    Decrypt the data by recreating the original key with threshold number
    of subkeys.

    Return the decrypted data.
    """
    key = shamir.recover_secret(subkeys)
    decrypted_data = decrypt(data, key.encode())

    return decrypted_data
