import pytest
from pathlib import Path
from ollama_assistant.history import init_db, load_history, save_message, clear_history, get_sessions
import ollama_assistant.history

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    config_dir = tmp_path / ".config" / "ollama-assist"
    db_file = config_dir / "history.db"
    monkeypatch.setattr(ollama_assistant.history, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(ollama_assistant.history, "DB_FILE", db_file)
    return db_file

def test_init_db(temp_db):
    conn = init_db()
    assert temp_db.exists()
    conn.close()

def test_save_and_load_history(temp_db):
    save_message("user", "hello", "test_session")
    history = load_history("test_session")
    assert len(history) == 1
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "hello"

def test_clear_history(temp_db):
    save_message("user", "hello", "test_session")
    clear_history("test_session")
    history = load_history("test_session")
    assert len(history) == 0

def test_get_sessions(temp_db):
    save_message("user", "hello", "session1")
    save_message("user", "hi", "session2")
    sessions = get_sessions()
    assert set(sessions) == {"session1", "session2"}
