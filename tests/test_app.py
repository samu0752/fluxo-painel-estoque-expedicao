import csv
import io
import tempfile
import unittest
from pathlib import Path

from app import create_app, get_db


class InventoryAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.database = str(Path(self.temp_dir.name) / "test.db")
        self.app = create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE": self.database})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_demo_data_is_seeded_and_home_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Vis\xc3\xa3o geral", response.data)
        self.assertIn(b"Cabo de rede CAT6", response.data)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM products").fetchone()[0], 6)

    def test_stock_out_updates_product_and_creates_movement(self):
        with self.app.app_context():
            product = get_db().execute("SELECT id, quantity FROM products WHERE sku = 'CAB-001'").fetchone()
            product_id, initial = product["id"], product["quantity"]
        response = self.client.post("/movimentacoes", data={
            "product_id": product_id, "movement_type": "saida", "quantity": "3", "note": "Pedido de demonstração"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            db = get_db()
            self.assertEqual(db.execute("SELECT quantity FROM products WHERE id = ?", (product_id,)).fetchone()[0], initial - 3)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM movements WHERE product_id = ? AND movement_type = 'saida'", (product_id,)).fetchone()[0], 1)

    def test_cannot_ship_more_than_available(self):
        with self.app.app_context():
            product = get_db().execute("SELECT id, quantity FROM products WHERE sku = 'CAB-001'").fetchone()
            product_id, initial = product["id"], product["quantity"]
        response = self.client.post("/movimentacoes", data={
            "product_id": product_id, "movement_type": "saida", "quantity": str(initial + 1)
        }, follow_redirects=True)
        self.assertIn("Saída não registrada", response.get_data(as_text=True))
        with self.app.app_context():
            db = get_db()
            self.assertEqual(db.execute("SELECT quantity FROM products WHERE id = ?", (product_id,)).fetchone()[0], initial)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM movements WHERE product_id = ? AND movement_type = 'saida'", (product_id,)).fetchone()[0], 0)

    def test_duplicate_sku_is_rejected(self):
        response = self.client.post("/produtos", data={
            "sku": "cab-001", "name": "Produto repetido", "category": "Teste", "quantity": "1", "minimum_quantity": "0", "unit": "un."
        }, follow_redirects=True)
        self.assertIn("Esse código SKU já existe", response.get_data(as_text=True))

    def test_product_with_initial_stock_creates_matching_entry(self):
        response = self.client.post("/produtos", data={
            "sku": "novo-001", "name": "Adaptador USB", "category": "Acessórios",
            "quantity": "4", "minimum_quantity": "1", "unit": "un."
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            db = get_db()
            product = db.execute("SELECT id, quantity FROM products WHERE sku = 'NOVO-001'").fetchone()
            movement = db.execute(
                "SELECT movement_type, quantity FROM movements WHERE product_id = ? ORDER BY id DESC LIMIT 1",
                (product["id"],),
            ).fetchone()
            self.assertEqual(product["quantity"], 4)
            self.assertEqual((movement["movement_type"], movement["quantity"]), ("entrada", 4))

    def test_unrepresentable_integer_is_rejected_without_server_error(self):
        response = self.client.post("/produtos", data={
            "sku": "BIG-001", "name": "Quantidade inválida", "category": "Teste",
            "quantity": "999999999999999999999999999999", "minimum_quantity": "0", "unit": "un."
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("quantidades inteiras não negativas", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertIsNone(get_db().execute("SELECT id FROM products WHERE sku = 'BIG-001'").fetchone())

    def test_public_demo_is_read_only_and_hides_edit_forms(self):
        read_only_db = str(Path(self.temp_dir.name) / "read-only.db")
        read_only_app = create_app({
            "TESTING": True, "SECRET_KEY": "test", "DATABASE": read_only_db, "READ_ONLY_DEMO": True
        })
        client = read_only_app.test_client()
        page = client.get("/").get_data(as_text=True)
        self.assertIn("Demonstração pública", page)
        self.assertNotIn('action="/produtos"', page)
        self.assertNotIn('action="/movimentacoes"', page)
        with read_only_app.app_context():
            before = get_db().execute("SELECT quantity FROM products WHERE sku = 'CAB-001'").fetchone()[0]
        response = client.post("/movimentacoes", data={
            "product_id": "1", "movement_type": "entrada", "quantity": "5"
        }, follow_redirects=True)
        self.assertIn("somente para consulta", response.get_data(as_text=True))
        with read_only_app.app_context():
            db = get_db()
            after = db.execute("SELECT quantity FROM products WHERE sku = 'CAB-001'").fetchone()[0]
            self.assertEqual(db.execute("SELECT COUNT(*) FROM movements WHERE movement_type = 'entrada'").fetchone()[0], 6)
        self.assertEqual(after, before)

    def test_csv_export_includes_headers_and_utf8_bom(self):
        response = self.client.get("/exportar/movimentacoes.csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)
        self.assertTrue(response.data.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"), newline=""), delimiter=";"))
        self.assertEqual(rows[0][0], "Data e hora")
        self.assertGreater(len(rows), 1)

    def test_csv_export_neutralizes_formula_after_leading_whitespace(self):
        with self.app.app_context():
            product_id = get_db().execute("SELECT id FROM products WHERE sku = 'CAB-001'").fetchone()["id"]
            get_db().execute(
                "INSERT INTO movements (product_id, movement_type, quantity, note, created_at) VALUES (?, 'entrada', 1, ?, '2026-01-01T10:00:00-03:00')",
                (product_id, "  =1+1"),
            )
            get_db().commit()
        response = self.client.get("/exportar/movimentacoes.csv")
        rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"), newline=""), delimiter=";"))
        exported_note = next(row[-1] for row in rows[1:] if row[-1].endswith("=1+1"))
        self.assertEqual(exported_note, "'  =1+1")


if __name__ == "__main__":
    unittest.main()
