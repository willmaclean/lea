from __future__ import annotations

import pathlib
import shutil

import duckdb
from typer.testing import CliRunner

from lea.app import make_app
from lea.clients import make_client

runner = CliRunner()


def test_jaffle_shop():
    app = make_app(make_client=make_client)
    here = pathlib.Path(__file__).parent
    env_path = str((here.parent / "examples" / "jaffle_shop" / ".env").absolute())
    views_path = str((here.parent / "examples" / "jaffle_shop" / "views").absolute())

    # Write .env file
    with open(env_path, "w") as f:
        f.write(
            "LEA_USERNAME=max\n" "LEA_WAREHOUSE=duckdb\n" "LEA_DUCKDB_PATH=tests/jaffle_shop.db\n"
        )

    # Prepare
    result = runner.invoke(app, ["prepare", views_path, "--env", env_path])
    assert result.exit_code == 0

    # Run
    result = runner.invoke(app, ["run", views_path, "--env", env_path, "--fresh"])
    assert result.exit_code == 0

    # Check number of tables created
    con = duckdb.connect("tests/jaffle_shop_max.db")
    tables = con.sql("SELECT table_schema, table_name FROM information_schema.tables").df()
    assert tables.shape[0] == 7

    # Check number of rows in core__customers
    customers = con.sql("SELECT * FROM core.customers").df()
    assert customers.shape[0] == 100

    # Check number of rows in core__orders
    orders = con.sql("SELECT * FROM core.orders").df()
    assert orders.shape[0] == 99

    # Run unit tests
    result = runner.invoke(app, ["test", views_path, "--env", env_path])
    assert result.exit_code == 0
    assert "Found 1 singular tests" in result.stdout
    assert "Found 1 assertion tests" in result.stdout
    assert "SUCCESS" in result.stdout

    # Build docs
    docs_path = here.parent / "examples" / "jaffle_shop" / "docs"
    shutil.rmtree(docs_path, ignore_errors=True)
    result = runner.invoke(
        app,
        [
            "docs",
            views_path,
            "--env",
            env_path,
            "--output-dir",
            str(docs_path.absolute()),
        ],
    )
    assert result.exit_code == 0
    assert docs_path.exists()
    assert (docs_path / "README.md").exists()
    assert (docs_path / "core" / "README.md").exists()
    assert (docs_path / "staging" / "README.md").exists()
    assert (docs_path / "analytics" / "README.md").exists()


def test_diff():
    app = make_app(make_client=make_client)
    here = pathlib.Path(__file__).parent
    env_path = str((here.parent / "examples" / "diff" / ".env").absolute())
    prod_views_path = str((here.parent / "examples" / "diff" / "views" / "prod").absolute())
    dev_views_path = str((here.parent / "examples" / "diff" / "views" / "dev").absolute())

    prod_args = [prod_views_path, "--env", env_path, "--production"]
    dev_args = [dev_views_path, "--env", env_path]

    # Write .env file
    with open(env_path, "w") as f:
        f.write("LEA_USERNAME=max\n" "LEA_WAREHOUSE=duckdb\n" "LEA_DUCKDB_PATH=tests/diff.db\n")

    # Prepare
    assert runner.invoke(app, ["prepare", *prod_args]).exit_code == 0
    assert runner.invoke(app, ["prepare", *dev_args]).exit_code == 0

    # Run
    assert runner.invoke(app, ["run", *prod_args]).exit_code == 0
    assert runner.invoke(app, ["run", *dev_args]).exit_code == 0

    prod_con = duckdb.connect("tests/diff.db")
    dev_con = duckdb.connect("tests/diff_max.db")

    # Check number of tables created
    prod_tables = prod_con.sql(
        "SELECT table_schema, table_name FROM information_schema.tables"
    ).df()
    assert prod_tables.shape[0] == 5
    assert prod_tables.table_schema.nunique() == 2

    dev_tables = prod_con.sql("SELECT table_schema, table_name FROM information_schema.tables").df()
    assert dev_tables.shape[0] == 5
    assert dev_tables.table_schema.nunique() == 2

    # Check number of rows in core__customers
    assert prod_con.sql("SELECT * FROM core.orders").df().shape[0] == 99
    assert dev_con.sql("SELECT * FROM core.orders").df().shape[0] == 70
