"""Reference developer backend — the executable spec for the HexaUI contract."""

import os

# Pin ADK to the legacy tool-schema field (`parameters`) that HexGate
# registration reads; google-adk >=2.x otherwise uses `parameters_json_schema`.
os.environ.setdefault("ADK_DISABLE_JSON_SCHEMA_FOR_FUNC_DECL", "1")
