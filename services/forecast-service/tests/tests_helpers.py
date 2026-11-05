from pathlib import Path


class FakeSource:
    def __init__(self, export):
        self.export = export

    def fetch(self):
        return self.export


class NullWriter:
    def __init__(self, root):
        self.root = Path(root)

    def put(self, name, data):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p.as_uri()
