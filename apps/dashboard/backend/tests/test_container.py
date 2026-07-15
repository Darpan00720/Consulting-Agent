def test_container_entrypoint_survives_a_root_owned_paas_volume():
    """A managed platform (Railway/Fly/Render) attaches its disk ROOT-OWNED,
    whatever the image says — so `mkdir + chown` at build time is not enough and
    the non-root app crashes with "unable to open database file" on startup.
    This is what took the first Railway deploy down.

    Two invariants the Dockerfile must keep:
      1. no `USER` directive — the entrypoint needs root to chown the mount,
         then drops privileges itself via gosu;
      2. the port comes from $PORT when the platform assigns one, else 8000.
         A hardcoded port makes a healthy container unreachable (502).
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / "Dockerfile").read_text()
    entrypoint = (root / "docker-entrypoint.sh").read_text()

    assert "gosu" in dockerfile, "gosu must be installed to drop root"
    assert "ENTRYPOINT" in dockerfile
    # A `USER app` line would strip the root needed to chown a PaaS volume.
    user_lines = [
        ln for ln in dockerfile.splitlines()
        if ln.strip().startswith("USER ")
    ]
    assert not user_lines, f"USER directive breaks the chown-then-drop flow: {user_lines}"

    assert "chown -R app" in entrypoint, "entrypoint must fix the volume ownership"
    assert 'exec gosu app' in entrypoint, "entrypoint must drop root before running"
    assert '${PORT:-8000}' in entrypoint, "must honour the platform's $PORT"
    assert 'STRATAGENT_DB' in entrypoint, "must derive the dir from the configured DB path"
