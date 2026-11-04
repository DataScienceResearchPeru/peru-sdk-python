# Peru SDK para Python

SDK nativo Python 3.11+, licencia MIT y cero dependencias de runtime de terceros. Cliente HTTP de Consulta Integrada SUNAT y proveedor de identidad sintético. No implementa emisión ni un cliente oficial RENIEC; las consultas institucionales reales todavía no están verificadas.

## Instalar y probar

```bash
python3 -m pip install .
python3 examples/offline.py
python3 -m unittest discover -s tests -v
```

El ejemplo y los tests usan datos sintéticos, sin secretos ni consultas externas. El corpus está incluido en `tests/data/conformance.json`, incluso en la distribución fuente. La suite funciona sin otros repositorios del ecosistema.

```python
from peru_sdk.sunat import StaticToken, ValidityClient, ValidityQuery

# La aplicación proporciona el RUC consultante y un token autorizado.
client = ValidityClient(requester_ruc, StaticToken(access_token))
query = ValidityQuery(issuer_ruc, "01", "F001", 123, "2026-11-02", "118.00")
result = client.check(query)  # Esta llamada sí realiza una consulta HTTP.
```

`OAuth2TokenProvider(client_id, client_secret)` implementa la obtención y caché del token mediante client_credentials. No es el flujo de emisión con Clave SOL. Entrada inválida produce `ValueError`; errores institucionales y de protocolo producen `SDKError` con categoría y operación. Un estado de comprobante negativo no equivale a un error de transporte.

## Modelos y conformidad

`upstream.lock.json` fija por commit y SHA-256 el generador, los contratos y el corpus. Regeneración explícita: `python3 .ci/sync_upstream.py`; comprobación sin modificar archivos: `python3 .ci/sync_upstream.py --check`. El backend Python no requiere Go. El SDK instalado no descarga ni ejecuta el generador.

## Empaquetado independiente

```bash
python3 -m pip install -r .ci/requirements.txt
stage=$(mktemp -d /var/tmp/peru-python-dist.XXXXXXXX)
python3 .ci/check_package.py --output "$stage"
```

Se construyen wheel y sdist desde una copia aislada, se comprueban sus archivos y dependencias, se instala la wheel en un destino nuevo y se ejecuta la suite incluida en el sdist. `dist/` contiene exclusivamente los dos archivos publicables a PyPI; hashes y procedencia van en `manifest/`.

## Publicar en PyPI

El workflow Release produce artefactos en PR y ejecución manual. Publicar requiere una etiqueta que coincida exactamente con la versión de pyproject.toml: para 0.1.0a1, `v0.1.0a1`. Una ejecución manual tiene `publish=false` por defecto; para publicar manualmente, seleccionar la etiqueta y `publish=true`.

Configurar una sola vez un Trusted Publisher en PyPI para el proyecto `peru-sdk` (sujeto a disponibilidad del nombre): owner `DataScienceResearchPeru`, repository `peru-sdk-python`, workflow `release.yml`, environment `pypi`. El job de publicación usa OIDC y solo recibe los dos archivos de `dist/`, después de verificar sus hashes. No requiere un token de PyPI permanente.

No hay una publicación en PyPI completada por esta implementación. La configuración de cuenta y la publicación externa requieren ese alta. Las credenciales de otros SDKs no se usan en este repositorio.
