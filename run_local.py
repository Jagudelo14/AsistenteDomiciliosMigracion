from dotenv import load_dotenv

# cargar .env si existe
load_dotenv()


# simple "fake" request compatible con _process_message (solo necesita get_body)
class DummyReq:
    def __init__(self, body_bytes: bytes):
        self._body = body_bytes
        self.method = "POST"
        self._params = {}

    def get_body(self):
        return self._body

    @property
    def params(self):
        return self._params

def main():
    # carga sample.json (ruta relativa)
    with open("sample.json", "r", encoding="utf-8") as f:
        body = f.read()

    # crear request y llamar a la función
    from function_app import _process_message

    req = DummyReq(body.encode("utf-8"))
    resp = _process_message(req)

    # imprimir resultado
    try:
        body = resp.get_body().decode("utf-8")
    except Exception:
        body = str(resp)
    print("status:", getattr(resp, "status_code", "unknown"))
    print("body:", body)

if __name__ == "__main__":
    main()