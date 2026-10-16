"""Painel de estoque e expedição — aplicação demonstrativa em Flask."""

from __future__ import annotations

import csv
import io
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, current_app, flash, g, redirect, render_template, request, url_for


SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    minimum_quantity INTEGER NOT NULL DEFAULT 0 CHECK (minimum_quantity >= 0),
    unit TEXT NOT NULL DEFAULT 'un.',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    movement_type TEXT NOT NULL CHECK (movement_type IN ('entrada', 'saida')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_movements_created_at ON movements(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_movements_product_id ON movements(product_id);
"""

DEMO_PRODUCTS = [
    ("CAB-001", "Cabo de rede CAT6", "Acessórios", 28, 10, "un."),
    ("MOU-002", "Mouse óptico USB", "Periféricos", 7, 8, "un."),
    ("TEC-003", "Teclado USB ABNT2", "Periféricos", 16, 6, "un."),
    ("SSD-004", "SSD 480 GB", "Armazenamento", 5, 4, "un."),
    ("MON-005", "Monitor 24 polegadas", "Monitores", 3, 3, "un."),
    ("FON-006", "Fonte ATX 500 W", "Componentes", 2, 5, "un."),
]


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "local-demo-key-change-before-deployment"),
        DATABASE=os.environ.get("DATABASE_PATH", str(Path(app.instance_path) / "estoque.db")),
    )
    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(close_db)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    with app.app_context():
        init_db()
        seed_demo_data()

    @app.get("/")
    def index():
        query = request.args.get("q", "").strip()
        category = request.args.get("categoria", "").strip()
        db = get_db()

        where = []
        params: list[str] = []
        if query:
            where.append("(sku LIKE ? OR name LIKE ? OR category LIKE ?)")
            term = f"%{query}%"
            params.extend([term, term, term])
        if category:
            where.append("category = ?")
            params.append(category)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        products = db.execute(
            f"""SELECT *, CASE WHEN quantity <= minimum_quantity THEN 1 ELSE 0 END AS is_low
                FROM products {where_sql} ORDER BY name COLLATE NOCASE""",
            params,
        ).fetchall()
        all_products = db.execute("SELECT id, sku, name, quantity, unit FROM products ORDER BY name COLLATE NOCASE").fetchall()
        metrics = db.execute(
            """SELECT COUNT(*) AS product_count,
                      COALESCE(SUM(quantity), 0) AS unit_count,
                      COALESCE(SUM(CASE WHEN quantity <= minimum_quantity THEN 1 ELSE 0 END), 0) AS low_count
               FROM products"""
        ).fetchone()
        movement_count = db.execute("SELECT COUNT(*) AS total FROM movements").fetchone()["total"]
        categories = db.execute("SELECT DISTINCT category FROM products ORDER BY category COLLATE NOCASE").fetchall()
        recent = db.execute(
            """SELECT m.*, p.sku, p.name AS product_name
               FROM movements m JOIN products p ON p.id = m.product_id
               ORDER BY m.created_at DESC, m.id DESC LIMIT 7"""
        ).fetchall()

        category_totals = db.execute(
            """SELECT category, SUM(quantity) AS units
               FROM products GROUP BY category ORDER BY units DESC, category COLLATE NOCASE LIMIT 5"""
        ).fetchall()
        largest = max((row["units"] for row in category_totals), default=0)
        return render_template(
            "index.html",
            products=products,
            all_products=all_products,
            metrics=metrics,
            movement_count=movement_count,
            categories=categories,
            recent=recent,
            category_totals=category_totals,
            largest_category=largest,
            query=query,
            selected_category=category,
            now=datetime.now().astimezone(),
        )

    @app.post("/produtos")
    def add_product():
        sku = request.form.get("sku", "").strip().upper()
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        unit = request.form.get("unit", "un.").strip() or "un."
        quantity = parse_nonnegative_int(request.form.get("quantity"))
        minimum = parse_nonnegative_int(request.form.get("minimum_quantity"))

        if not sku or not name or not category or quantity is None or minimum is None:
            flash("Confira os campos obrigatórios e informe quantidades inteiras não negativas.", "error")
            return redirect(url_for("index"))
        if len(sku) > 32 or len(name) > 100 or len(category) > 60 or len(unit) > 12:
            flash("Algum campo ultrapassou o tamanho permitido. Revise os dados e tente novamente.", "error")
            return redirect(url_for("index"))

        db = get_db()
        try:
            cursor = db.execute(
                """INSERT INTO products (sku, name, category, quantity, minimum_quantity, unit, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sku, name, category, quantity, minimum, unit, timestamp_now()),
            )
            product_id = cursor.lastrowid
            if quantity:
                db.execute(
                    """INSERT INTO movements (product_id, movement_type, quantity, note, created_at)
                       VALUES (?, 'entrada', ?, 'Saldo inicial cadastrado', ?)""",
                    (product_id, quantity, timestamp_now()),
                )
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            flash("Esse código SKU já existe. Use um código diferente.", "error")
            return redirect(url_for("index"))
        flash(f"Produto {sku} cadastrado com sucesso.", "success")
        return redirect(url_for("index"))

    @app.post("/movimentacoes")
    def add_movement():
        product_id = parse_positive_int(request.form.get("product_id"))
        quantity = parse_positive_int(request.form.get("quantity"))
        movement_type = request.form.get("movement_type", "").strip().lower()
        note = request.form.get("note", "").strip()

        if product_id is None or quantity is None or movement_type not in {"entrada", "saida"}:
            flash("Informe um produto, uma quantidade inteira positiva e o tipo de movimentação.", "error")
            return redirect(url_for("index"))
        if len(note) > 180:
            flash("A observação deve ter no máximo 180 caracteres.", "error")
            return redirect(url_for("index"))

        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
            if product is None:
                db.rollback()
                flash("O produto selecionado não foi encontrado.", "error")
                return redirect(url_for("index"))
            if movement_type == "saida" and quantity > product["quantity"]:
                db.rollback()
                flash(f"Saída não registrada: há somente {product['quantity']} {product['unit']} em estoque.", "error")
                return redirect(url_for("index"))

            delta = quantity if movement_type == "entrada" else -quantity
            db.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?", (delta, product_id))
            db.execute(
                """INSERT INTO movements (product_id, movement_type, quantity, note, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (product_id, movement_type, quantity, note, timestamp_now()),
            )
            db.commit()
        except sqlite3.Error:
            db.rollback()
            current_app.logger.exception("Falha ao registrar movimentação")
            flash("Não foi possível registrar a movimentação. Tente novamente.", "error")
            return redirect(url_for("index"))

        label = "Entrada" if movement_type == "entrada" else "Saída"
        flash(f"{label} de {quantity} {product['unit']} registrada para {product['name']}.", "success")
        return redirect(url_for("index"))

    @app.get("/exportar/movimentacoes.csv")
    def export_movements():
        rows = get_db().execute(
            """SELECT m.created_at, m.movement_type, p.sku, p.name, p.category,
                      m.quantity, p.unit, m.note
               FROM movements m JOIN products p ON p.id = m.product_id
               ORDER BY m.created_at DESC, m.id DESC"""
        ).fetchall()
        output = io.StringIO(newline="")
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["Data e hora", "Tipo", "SKU", "Produto", "Categoria", "Quantidade", "Unidade", "Observação"])
        for row in rows:
            writer.writerow([safe_csv_value(value) for value in row])
        content = "\ufeff" + output.getvalue()
        return Response(
            content,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=relatorio-movimentacoes.csv"},
        )

    @app.get("/saude")
    def health():
        return {"status": "ok", "service": "painel-estoque-expedicao"}

    return app


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db_path = current_app.config["DATABASE"]
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    get_db().executescript(SCHEMA)
    get_db().commit()


def seed_demo_data() -> None:
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM products").fetchone()[0]:
        return
    now = timestamp_now()
    for sku, name, category, quantity, minimum, unit in DEMO_PRODUCTS:
        cursor = db.execute(
            """INSERT INTO products (sku, name, category, quantity, minimum_quantity, unit, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sku, name, category, quantity, minimum, unit, now),
        )
        if quantity:
            db.execute(
                """INSERT INTO movements (product_id, movement_type, quantity, note, created_at)
                   VALUES (?, 'entrada', ?, 'Carga inicial de demonstração', ?)""",
                (cursor.lastrowid, quantity, now),
            )
    db.commit()


def timestamp_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_nonnegative_int(raw: str | None) -> int | None:
    try:
        value = int(raw or "")
        # SQLite INTEGER usa inteiros com sinal de 64 bits.
        return value if 0 <= value <= 9_223_372_036_854_775_807 else None
    except (TypeError, ValueError):
        return None


def parse_positive_int(raw: str | None) -> int | None:
    value = parse_nonnegative_int(raw)
    return value if value and value > 0 else None


def safe_csv_value(value: object) -> object:
    """Neutraliza marcadores de fórmula após espaços e caracteres de controle iniciais."""
    if isinstance(value, str) and value.lstrip(" \t\r\n")[:1] in {"=", "+", "-", "@"}:
        return "'" + value
    return value


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
