import pytest
from unittest.mock import patch, MagicMock
from ollama_assistant.commands import handle_slash_command
from ollama_assistant.state import state

@pytest.fixture
def mock_config():
    return {"user_name": "TestUser", "theme": "ansicyan"}

@pytest.fixture
def mock_handle_turn():
    return MagicMock()

def test_handle_slash_command_clear(mock_config, mock_handle_turn):
    messages = [{"role": "user", "content": "hello"}]
    
    with patch("ollama_assistant.commands.Confirm.ask", return_value=True):
        with patch("ollama_assistant.commands.clear_history") as mock_clear:
            handled, model = handle_slash_command("/clear", "", "llama3", messages, mock_config, mock_handle_turn)
            
            assert handled is True
            assert model == "llama3"
            assert len(messages) == 0
            mock_clear.assert_called_once_with(state.current_session)

def test_handle_slash_command_model(mock_config, mock_handle_turn):
    messages = []
    handled, model = handle_slash_command("/model", "mistral", "llama3", messages, mock_config, mock_handle_turn)
    
    assert handled is True
    assert model == "mistral"
    assert state.current_model_name == "mistral"

def test_handle_slash_command_new_workspace(mock_config, mock_handle_turn):
    messages = [{"role": "user", "content": "hi"}]
    with patch("ollama_assistant.commands.load_history", return_value=[]):
        handled, model = handle_slash_command("/new", "test_workspace", "llama3", messages, mock_config, mock_handle_turn)
        
        assert handled is True
        assert state.current_session == "test_workspace"
        assert len(messages) == 0
