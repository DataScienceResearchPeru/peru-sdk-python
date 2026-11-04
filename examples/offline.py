"""Run after installing sdk-python; uses synthetic data and makes no network calls."""
from peru_sdk.reniec import Identity, IdentityQuery, MockIdentityService
from peru_sdk.sunat import parse_validity_response

service = MockIdentityService([Identity("00000001", "PERSONA", "PRUEBA", "SINTETICA")])
print("Identidad sintética:", service.lookup(IdentityQuery("00000001")))
result = parse_validity_response(
    b'{"success":true,"data":{"estadoCp":1,"estadoRuc":"00","condDomiRuc":"00"}}'
)
print("Estado de comprobante simulado:", result.document_status)
