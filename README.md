# CovPass-Scanner

Python script for scanning, decoding, and verifying the EU Covid-19 vaccine certificate, as [specified by the EU](https://ec.europa.eu/health/ehealth/covid-19_en).

CovPass-Scanner scans the QR code of a vaccine certificate using a webcam. 
Certificate validity and name of the owner are displayed on-screen. 
This allows for quickly verifying the certificates of visitors.

The script is heavily based on [hannob/vacdec](https://github.com/hannob/vacdec) (data extraction) and [HQJaTu/vacdec](https://github.com/HQJaTu/vacdec/tree/signature-verification) (signature verification).
Check out these repositories for more information on the innner workings.


## Setup

You will need:
* pillow for image handling
* pyzbar for reading QR-code
* base45, cbor2 and cose packages for [RFC-8152 data structure](https://datatracker.ietf.org/doc/html/rfc8152) reading
* Additionally, you need zbar
  * For Mac OS X, it can be installed via `brew install zbar`
  * Debian systems via `apt install libzbar0`. [Source](https://pypi.org/project/pyzbar/)
  * Fedora / Red Hat `dnf install zbar`
* opencv for webcam mode 
* pygame for playing sound

Install them via your distribution or via pip:

```
pip install -r requirements.txt
```

## usage

Run:

```bash
./covpass-scanner --image-file <image>
```

or

```bash
./covpass-scanner --camera <camera device, e.g. /dev/video0>
```

``image`` can be an image in any format pillow supports, including of
course PNG and JPG.

## Example run:
```bash
$ ./vacdec --image-file samples/Sweden-2.png
2021-08-05 19:33:39,927 [INFO ]  COVID certificate signed with X.509 certificate.
2021-08-05 19:33:39,927 [INFO ]  X.509 in DER form has SHA-256 beginning with: 5f74910195c5cecb
2021-08-05 19:36:24,800 [INFO ]  Found the key from DB!
2021-08-05 19:36:24,820 [INFO ]  Signature verified ok
2021-08-05 19:33:39,928 [INFO ]  Certificate as JSON: {
  "1": "SE",
  "4": 1625305802,
  "6": 1623750603,
  "-260": {
    "1": {
      "t": [
        {
          "ci": "URN:UVCI:01:SE:EHM/TARN89875439877",
          "co": "SE",
          "is": "Swedish eHealth Agency",
          "nm": "Roche LightCycler qPCR",
          "sc": "2021-06-15 09:24:02+00:00",
          "tc": "Arlanda Airport Covid Center 1",
          "tg": "840539006",
          "tr": "260415000",
          "tt": "LP6464-4"
        }
      ],
      "dob": "1958-11-11",
      "nam": {
        "fn": "Lövström",
        "gn": "Oscar",
        "fnt": "LOEVSTROEM",
        "gnt": "OSCAR"
      },
      "ver": "1.3.0"
    }
  }
}
```

# More information on the EU Digital COVID Certificate
(Note: formerly known as Digital Green Certificate)

## Specifications
What's in a EU Digital COVID/Green Certificate?
* Value Sets for Digital Green Certificates https://ec.europa.eu/health/sites/default/files/ehealth/docs/digital-green-certificates_dt-specifications_en.pdf
* JSON schema: https://github.com/ehn-dcc-development/ehn-dcc-schema

## Sample data
Digital Green Certificate Gateway (DGCG) samples for all participating countries:
https://github.com/eu-digital-green-certificates/dgc-testdata

## Digital Signature X.509 Certificates
* Digital Green Certificate Gateway (DGCG) Swagger: https://eu-digital-green-certificates.github.io/dgc-gateway/
  * API-key needed. Get it from ???
* French solution to gather a list of all:
  * https://github.com/lovasoa/sanipasse
  * JSON-list: https://raw.githubusercontent.com/lovasoa/sanipasse/master/src/assets/Digital_Green_Certificate_Signing_Keys.json
* Swedish list of all certificates: https://dgcg.covidbevis.se/tp/

# Authors

Written by [Hanno Böck](https://hboeck.de/).
Signature verification by [Jari Turkia](https://blog.hqcodeshop.fi/).
Minor fixes, decoding of Digital Green Certificate Values Sets, and webcam mode by [Raphael Wimmer](https://www.winterwind.org) and Thomas Fischer.
