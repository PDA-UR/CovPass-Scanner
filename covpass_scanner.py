import sys
import zlib
import logging
from typing import Dict, Tuple, Optional
from datetime import datetime
import pyzbar.pyzbar
import json
import base45
import base64
import cbor2
from cose.headers import Algorithm, KID
from cose.messages import CoseMessage
from cose.keys import cosekey, ec2, keyops, curves

from cryptography import x509
from cryptography import hazmat
from pyasn1.codec.ber import decoder as asn1_decoder
from cryptojwt import jwk as cjwtk
from cryptojwt import utils as cjwt_utils


DEFAULT_CERTIFICATE_DB_JSON = 'certs/Digital_Green_Certificate_Signing_Keys.json'


class CovpassScanner:

    def __init__(self, certs=DEFAULT_CERTIFICATE_DB_JSON):

        self.certs = certs

        self.log = logging.getLogger(__name__)
        self.__setup_logger()

    def __setup_logger(self) -> None:
        log_formatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s]  %(message)s")
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(log_formatter)
        console_handler.propagate = False
        logging.getLogger().addHandler(console_handler)
        self.log.setLevel(logging.DEBUG)
        # log.setLevel(logging.INFO)

    def process_frame(self, frame):
        barcodes = pyzbar.pyzbar.decode(frame)
        found_certificate = len(barcodes) == 1

        if found_certificate:
            data = barcodes[0].data.decode()
            if data.startswith("HC1:"):
                # try:
                parsed_covid_cert_data = self.output_covid_cert_data(data, self.certs)
                is_valid = parsed_covid_cert_data['verified'][1]

                return found_certificate, is_valid, parsed_covid_cert_data
            # except:
            #    log.info("no certificate in QR code")

        return found_certificate, False, None

    def output_covid_cert_data(self, cert: str, keys_file: str) -> dict:
        # Code adapted from:
        # https://alphalist.com/blog/the-use-of-blockchain-for-verification-eu-vaccines-passport-program-and-more
        signature_verified = False

        # Strip the first characters to form valid Base45-encoded data
        b45data = cert[4:]

        # Decode the data
        zlibdata = base45.b45decode(b45data)

        # Uncompress the data
        decompressed = zlib.decompress(zlibdata)

        self.log.debug(decompressed)

        # decode COSE message (no signature verification done yet)
        cose_msg = CoseMessage.decode(decompressed)

        # decode the CBOR encoded payload and print as json
        # for some reason, some certificates store the KID in the protected header, some in the unprotected header
        # (e.g., current German vaccination passports)
        if KID in cose_msg.phdr:
            key_header = cose_msg.phdr[KID]
            self.log.debug("KID in cose_msg.phdr: " + str(cose_msg.phdr))
        elif KID in cose_msg.uhdr:
            key_header = cose_msg.uhdr[KID]
            self.log.debug("KID in cose_msg.uhdr: " + str(cose_msg.uhdr))
        else:
            key_header = None
        if key_header:
            self.log.info("COVID certificate signed with X.509 certificate.")
            self.log.info("X.509 in DER form has SHA-256 beginning with: {0}".format(
                key_header.hex()))
            key = self.find_key(key_header, keys_file)
            if key:
                signature_verified = self.verify_signature(cose_msg, key)
            else:
                self.log.info("Skip verify as no key found from database")
        else:
            self.log.debug("KID not in cose_msg.phdr or cose_msg.uhdr: " + str(KID))
            self.log.info("Certificate is not signed")
        self.log.debug(cose_msg.key)
        cbor = cbor2.loads(cose_msg.payload)
        cbor['verified'] = True if signature_verified else False
        # Note: Some countries have hour:minute:second for sc-field (Date/Time of Sample Collection).
        # If used, this will decode as a datetime. A datetime cannot be JSON-serialized without hints (use str as default).
        # Note 2: Names may contain non-ASCII characters in UTF-8
        self.log.info("Certificate as JSON: {0}".format(json.dumps(cbor, indent=2, default=str, ensure_ascii=False)))
        return self.print_cert_data(cbor)

    def find_key(self, key: Algorithm, keys_file: str) -> Optional[cosekey.CoseKey]:
        if False:
            # Test read a PEM-key
            jwt_key = read_cosekey_from_pem_file("certs/Finland.pem")
            # pprint(jwt_key)
            # pprint(jwt_key.kid.decode())

        # Read the JSON-database of all known keys
        with open(keys_file, encoding='utf-8') as f:
            known_keys = json.load(f)

        jwt_key = None
        for key_id, key_data in known_keys.items():
            key_id_binary = base64.b64decode(key_id)
            if key_id_binary == key:
                self.log.info("Found the key from DB!")
                # check if the point is uncompressed rather than compressed
                x, y = self.public_ec_key_points(base64.b64decode(key_data['publicKeyPem']))
                key_dict = {'crv': key_data['publicKeyAlgorithm']['namedCurve'],  # 'P-256'
                            'kid': key_id_binary.hex(),
                            'kty': key_data['publicKeyAlgorithm']['name'][:2],  # 'EC'
                            'x': x,  # 'eIBWXSaUgLcxfjhChSkV_TwNNIhddCs2Rlo3tdD671I'
                            'y': y,  # 'R1XB4U5j_IxRgIOTBUJ7exgz0bhen4adlbHkrktojjo'
                            }
                jwt_key = self.cosekey_from_jwk_dict(key_dict)
                break

        if not jwt_key:
            return None

        if jwt_key.kid.decode() != key.hex():
            raise RuntimeError("Internal: No key for {0}!".format(key.hex()))

        return jwt_key

    def verify_signature(self, cose_msg: CoseMessage, key: cosekey.CoseKey) -> bool:
        cose_msg.key = key
        if not cose_msg.verify_signature():
            self.log.warning("Signature does not verify with key ID {0}!".format(key.kid.decode()))
            return False
        self.log.info("Signature verified ok")
        return cose_msg.verify_signature()

    def print_cert_data(self, d) -> dict:
        print(f"Issuer: {d[1]}")
        print(f"Issue Date: {datetime.fromtimestamp(int(d[6]))}")
        print(f"Expiration Date: {datetime.fromtimestamp(int(d[4]))}")
        data = d[-260][1]
        data = self.flatten(data)
        data['verified'] = d['verified']
        data['issuer'] = d[1]
        data['issue date'] = datetime.fromtimestamp(int(d[6]))
        data['expiration date'] = datetime.fromtimestamp(int(d[4]))

        translated = {}
        for k in data.keys():
            translated[k] = (self.translate(k), self.translate(data[k]))
            self.log.info(f"{self.translate(k)}: {self.translate(data[k])}")
        return translated

    def flatten(self, dic):
        items = {}
        for item in dic.keys():
            if type(dic[item]) == dict:
                for k, v in self.flatten(dic[item]).items():
                    items[k] = v
            elif type(dic[item]) == list:
                for d in dic[item]:
                    for k, v in self.flatten(d).items():
                        items[k] = v
            else:
                items[item] = dic[item]
        return items

    def translate(self, abbreviation):
        abbr_dict = json.load(open("Digital_Green_Certificate_Value_Sets.json"))
        abbreviations = self.flatten(abbr_dict)
        if abbreviation in abbreviations.keys():
            return abbreviations[abbreviation]
        else:
            return abbreviation

    def public_ec_key_points(self, public_key: bytes) -> Tuple[str, str]:
        # This code adapted from: https://stackoverflow.com/a/59537764/1548275
        public_key_asn1, _remainder = asn1_decoder.decode(public_key)
        public_key_bytes = public_key_asn1[1].asOctets()

        off = 0
        if public_key_bytes[off] != 0x04:
            raise ValueError("EC public key is not an uncompressed point")
        off += 1

        size_bytes = (len(public_key_bytes) - 1) // 2

        x_bin = public_key_bytes[off:off + size_bytes]
        x = int.from_bytes(x_bin, 'big', signed=False)
        off += size_bytes

        y_bin = public_key_bytes[off:off + size_bytes]
        y = int.from_bytes(y_bin, 'big', signed=False)
        off += size_bytes

        bl = (x.bit_length() + 7) // 8
        bytes_val = x.to_bytes(bl, 'big')
        x_str = base64.b64encode(bytes_val, altchars='-_'.encode()).decode()

        bl = (y.bit_length() + 7) // 8
        bytes_val = y.to_bytes(bl, 'big')
        y_str = base64.b64encode(bytes_val, altchars='-_'.encode()).decode()

        return x_str, y_str

    # Create CoseKey from JWK
    def cosekey_from_jwk_dict(self, jwk_dict: Dict) -> cosekey.CoseKey:
        # Read key and return CoseKey
        if jwk_dict["kty"] != "EC":
            raise ValueError("Only EC keys supported")
        if jwk_dict["crv"] != "P-256":
            raise ValueError("Only P-256 supported")

        key = ec2.EC2(
            crv=curves.P256,
            x=cjwt_utils.b64d(jwk_dict["x"].encode()),
            y=cjwt_utils.b64d(jwk_dict["y"].encode()),
        )
        key.key_ops = [keyops.VerifyOp]
        if "kid" in jwk_dict:
            key.kid = bytes(jwk_dict["kid"], "UTF-8")

        return key

    # Create JWK and calculate KID from Public Signing Certificate
    def read_cosekey_from_pem_file(self, cert_file: str) -> cosekey.CoseKey:
        # Read certificate, calculate kid and return EC CoseKey
        if not cert_file.endswith(".pem"):
            raise ValueError("Unknown key format. Use .pem keyfile")

        with open(cert_file, 'rb') as f:
            cert_data = f.read()
            # Calculate Hash from the DER format of the Certificate
            cert = x509.load_pem_x509_certificate(cert_data, hazmat.backends.default_backend())
            keyidentifier = cert.fingerprint(hazmat.primitives.hashes.SHA256())
        f.close()
        key = cert.public_key()

        jwk = cjwtk.ec.ECKey()
        jwk.load_key(key)
        # Use first 8 bytes of the hash as Key Identifier (Hex as UTF-8)
        jwk.kid = keyidentifier[:8].hex()
        jwk_dict = jwk.serialize(private=False)

        return self.cosekey_from_jwk_dict(jwk_dict)
