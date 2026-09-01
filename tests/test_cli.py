"""
Tests for mcp_core.core.cli.
"""

import logging
import sys
from unittest.mock import MagicMock, patch

import pytest

from mcp_core.core import cli


class TestParseArgs:
    """Tests for parse_args()."""

    def test_defaults(self):
        """With no args, parse_args returns stdio transport and default host/port."""
        with patch.object(sys, "argv", ["prog"]):
            args = cli.parse_args()
        assert args.transport == "stdio"
        assert args.host == "127.0.0.1"
        assert args.port == 8000
        assert args.debug is False
        assert args.list_tools is False

    def test_debug_transport_http_host_port_list_tools(self):
        """parse_args parses --debug, --transport http, --host, --port, --list-tools."""
        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "--debug",
                "--transport",
                "http",
                "--host",
                "0.0.0.0",
                "--port",
                "9000",
                "--list-tools",
            ],
        ):
            args = cli.parse_args()
        assert args.debug is True
        assert args.transport == "http"
        assert args.host == "0.0.0.0"
        assert args.port == 9000
        assert args.list_tools is True

    def test_invalid_transport_raises(self):
        """Invalid --transport choice causes argparse to raise SystemExit."""
        with (
            patch.object(sys, "argv", ["prog", "--transport", "invalid"]),
            pytest.raises(SystemExit),
        ):
            cli.parse_args()


class TestSetupLogging:
    """Tests for setup_logging()."""

    @pytest.fixture(autouse=True)
    def _restore_root_logger(self):
        root = logging.getLogger()
        original_level = root.level
        original_handlers = root.handlers[:]
        yield
        root.handlers = original_handlers
        root.setLevel(original_level)

    @patch("mcp_core.core.cli.logging.FileHandler")
    @patch("mcp_core.core.cli.os.makedirs")
    @patch("mcp_core.core.cli.os.path.exists")
    def test_debug_sets_debug_level(
        self, exists_mock, makedirs_mock, file_handler_mock
    ):
        """setup_logging(debug=True) sets root logger to DEBUG."""
        exists_mock.return_value = False
        mock_handler = MagicMock()
        mock_handler.level = logging.NOTSET
        file_handler_mock.return_value = mock_handler
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.WARNING)
        cli.setup_logging(debug=True)
        assert root.level == logging.DEBUG

    @patch("mcp_core.core.cli.logging.FileHandler")
    @patch("mcp_core.core.cli.os.makedirs")
    @patch("mcp_core.core.cli.os.path.exists")
    def test_no_debug_sets_info_level(
        self, exists_mock, makedirs_mock, file_handler_mock
    ):
        """setup_logging(debug=False) sets root logger to INFO."""
        exists_mock.return_value = False
        mock_handler = MagicMock()
        mock_handler.level = logging.NOTSET
        file_handler_mock.return_value = mock_handler
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.WARNING)
        cli.setup_logging(debug=False)
        assert root.level == logging.INFO

    @patch("mcp_core.core.cli.logging.FileHandler")
    @patch("mcp_core.core.cli.os.makedirs")
    @patch("mcp_core.core.cli.os.path.exists")
    def test_adds_file_handler(self, exists_mock, makedirs_mock, file_handler_mock):
        """setup_logging creates log dir and adds a FileHandler."""
        exists_mock.return_value = False
        mock_handler = MagicMock()
        mock_handler.level = logging.NOTSET
        file_handler_mock.return_value = mock_handler
        cli.setup_logging(debug=False)
        makedirs_mock.assert_called_once_with("logs")
        file_handler_mock.assert_called_once()
        root = logging.getLogger()
        assert mock_handler in root.handlers


class TestSafeImport:
    """Tests for safe_import()."""

    def test_nonexistent_module_returns_none(self):
        """safe_import of nonexistent module returns None and logs error."""
        with patch("mcp_core.core.cli.logging") as log_mock:
            log_mock.getLogger.return_value = MagicMock()
            result = cli.safe_import("_nonexistent_module_xyz_123")
        assert result is None

    def test_real_module_returns_module(self):
        """safe_import of existing module returns the module."""
        result = cli.safe_import("json")
        assert result is not None
        import json as json_mod

        assert result is json_mod


class TestDisplayTools:
    """Tests for display_tools()."""

    def test_display_tools_no_exception(self):
        """display_tools(mcp_settings) runs without exception."""
        mcp_settings = MagicMock()
        mcp_settings.tools = ["generate_class_diagram"]
        with patch.object(cli.console, "print"):
            cli.display_tools(mcp_settings)


class TestDisplayPrompts:
    """Tests for display_prompts()."""

    def test_display_prompts_no_exception(self):
        """display_prompts(mcp_settings) runs without exception."""
        mcp_settings = MagicMock()
        mcp_settings.prompts = ["class_diagram"]
        with patch.object(cli.console, "print"):
            cli.display_prompts(mcp_settings)


class TestDisplayResources:
    """Tests for display_resources()."""

    def test_display_resources_no_exception(self):
        """display_resources(mcp_settings) runs without exception."""
        mcp_settings = MagicMock()
        mcp_settings.resources = ["uml://types"]
        with patch.object(cli.console, "print"):
            cli.display_resources(mcp_settings)


class TestRun:
    """Tests for run()."""

    @patch("mcp_core.core.server.start_server")
    @patch("mcp_core.core.server.get_mcp_server")
    @patch(
        "mcp_core.core.config.MCP_SETTINGS",
        MagicMock(
            version="1.0",
            server_name="Test",
            tools=[],
            prompts=[],
            resources=[],
        ),
    )
    @patch("mcp_core.core.cli.safe_import", return_value=MagicMock())
    @patch("mcp_core.core.cli.setup_logging", return_value=MagicMock())
    @patch("mcp_core.core.cli.parse_args")
    def test_list_tools_exits_without_starting_server(
        self,
        parse_mock,
        setup_mock,
        safe_import_mock,
        get_server_mock,
        start_server_mock,
    ):
        """run() with --list-tools on http transport displays tools and returns without starting server."""
        parse_mock.return_value = MagicMock(
            debug=False,
            transport="http",
            host="127.0.0.1",
            port=8000,
            list_tools=True,
        )
        with patch.object(cli.console, "print"):
            cli.run()
        start_server_mock.assert_not_called()

    @patch("mcp_core.core.server.start_server")
    @patch("mcp_core.core.server.get_mcp_server")
    @patch(
        "mcp_core.core.config.MCP_SETTINGS",
        MagicMock(
            version="1.0",
            server_name="Test",
            tools=["generate_uml", "validate_uml"],
            prompts=[],
            resources=[],
        ),
    )
    @patch("mcp_core.core.cli.safe_import", return_value=MagicMock())
    @patch("mcp_core.core.cli.setup_logging", return_value=MagicMock())
    @patch("mcp_core.core.cli.parse_args")
    def test_list_tools_stdio_exits_without_starting_server(
        self,
        parse_mock,
        setup_mock,
        safe_import_mock,
        get_server_mock,
        start_server_mock,
    ):
        """run() with --list-tools and default stdio transport prints tools and exits."""
        parse_mock.return_value = MagicMock(
            debug=False,
            transport="stdio",
            host="127.0.0.1",
            port=8000,
            list_tools=True,
        )
        with patch.object(cli.console, "print"):
            cli.run()
        start_server_mock.assert_not_called()

    @patch("mcp_core.core.server.start_server")
    @patch("mcp_core.core.server.get_mcp_server")
    @patch(
        "mcp_core.core.config.MCP_SETTINGS",
        MagicMock(
            version="1.0",
            server_name="Test",
            tools=[],
            prompts=[],
            resources=[],
            update_from_args=MagicMock(),
        ),
    )
    @patch("mcp_core.core.cli.safe_import", return_value=MagicMock())
    @patch("mcp_core.core.cli.setup_logging", return_value=MagicMock())
    @patch("mcp_core.core.cli.parse_args")
    def test_run_http_calls_start_server(
        self,
        parse_mock,
        setup_mock,
        safe_import_mock,
        get_server_mock,
        start_server_mock,
    ):
        """run() with transport http calls start_server with host and port."""
        parse_mock.return_value = MagicMock(
            debug=False,
            transport="http",
            host="0.0.0.0",
            port=9999,
            list_tools=False,
        )
        with patch.object(cli.console, "print"):
            cli.run()
        start_server_mock.assert_called_once_with(
            transport="http", host="0.0.0.0", port=9999
        )

    @patch("mcp_core.core.cli.safe_import", return_value=None)
    @patch("mcp_core.core.cli.setup_logging", return_value=MagicMock())
    @patch("mcp_core.core.cli.parse_args")
    def test_run_missing_modules_exits(self, parse_mock, setup_mock, safe_import_mock):
        """run() exits with code 1 when required modules are missing."""
        parse_mock.return_value = MagicMock(
            debug=False,
            transport="stdio",
            host="127.0.0.1",
            port=8000,
            list_tools=False,
        )
        with patch.object(cli.console, "print"), pytest.raises(SystemExit) as exc_info:
            cli.run()
        assert exc_info.value.code == 1

    @patch("mcp_core.core.server.start_server", side_effect=KeyboardInterrupt)
    @patch("mcp_core.core.server.get_mcp_server")
    @patch(
        "mcp_core.core.config.MCP_SETTINGS",
        MagicMock(
            version="1.0", server_name="Test", tools=[], prompts=[], resources=[]
        ),
    )
    @patch("mcp_core.core.cli.safe_import", return_value=MagicMock())
    @patch("mcp_core.core.cli.setup_logging", return_value=MagicMock())
    @patch("mcp_core.core.cli.parse_args")
    def test_run_handles_keyboard_interrupt(
        self, parse_mock, setup_mock, safe_import_mock, get_server_mock, start_mock
    ):
        """run() catches KeyboardInterrupt gracefully."""
        parse_mock.return_value = MagicMock(
            debug=False, transport="http", host="127.0.0.1", port=8000, list_tools=False
        )
        with patch.object(cli.console, "print"):
            cli.run()  # Should not raise

    @patch("mcp_core.core.server.start_server", side_effect=RuntimeError("boom"))
    @patch("mcp_core.core.server.get_mcp_server")
    @patch(
        "mcp_core.core.config.MCP_SETTINGS",
        MagicMock(
            version="1.0", server_name="Test", tools=[], prompts=[], resources=[]
        ),
    )
    @patch("mcp_core.core.cli.safe_import", return_value=MagicMock())
    @patch("mcp_core.core.cli.setup_logging", return_value=MagicMock())
    @patch("mcp_core.core.cli.parse_args")
    def test_run_handles_generic_exception(
        self, parse_mock, setup_mock, safe_import_mock, get_server_mock, start_mock
    ):
        """run() catches generic exceptions and logs them."""
        parse_mock.return_value = MagicMock(
            debug=False, transport="http", host="127.0.0.1", port=8000, list_tools=False
        )
        with patch.object(cli.console, "print"):
            cli.run()  # Should not raise


class TestStdioUI:
    """Tests for stdio UI rendering logic."""

    def test_stdio_ui_disabled_by_default(self):
        """_stdio_ui_enabled returns False when env var is unset."""
        with patch.dict("os.environ", {}, clear=True):
            assert cli._stdio_ui_enabled() is False

    def test_stdio_ui_enabled_with_env_var(self):
        """_stdio_ui_enabled returns True for truthy env values."""
        for val in ("true", "1", "yes"):
            with patch.dict("os.environ", {"UML_MCP_STDIO_UI": val}):
                assert cli._stdio_ui_enabled() is True

    def test_should_render_for_http(self):
        """_should_render_human_output always returns True for http transport."""
        assert cli._should_render_human_output("http") is True

    def test_should_not_render_for_stdio_by_default(self):
        """_should_render_human_output returns False for stdio without env var."""
        with patch.dict("os.environ", {}, clear=True):
            assert cli._should_render_human_output("stdio") is False

    def test_should_render_for_stdio_with_env(self):
        """_should_render_human_output returns True for stdio with UML_MCP_STDIO_UI=true."""
        with patch.dict("os.environ", {"UML_MCP_STDIO_UI": "true"}):
            assert cli._should_render_human_output("stdio") is True


class TestDisplayFallbacks:
    """Tests for display fallback methods."""

    def test_display_tools_fallback_with_tools(self):
        """_display_tools_fallback populates table with known tool names."""
        mcp_settings = MagicMock()
        mcp_settings.tools = ["generate_uml"]
        table = MagicMock()
        cli._display_tools_fallback(mcp_settings, table)
        table.add_row.assert_called()

    def test_display_tools_fallback_empty(self):
        """_display_tools_fallback shows 'No tools found' when empty."""
        mcp_settings = MagicMock()
        mcp_settings.tools = []
        table = MagicMock()
        cli._display_tools_fallback(mcp_settings, table)
        table.add_row.assert_called_once_with(
            "No tools found", "Check server configuration", ""
        )

    def test_display_prompts_fallback_with_prompts(self):
        """_display_prompts_fallback populates table with known prompts."""
        mcp_settings = MagicMock()
        mcp_settings.prompts = ["class_diagram"]
        table = MagicMock()
        cli._display_prompts_fallback(mcp_settings, table)
        table.add_row.assert_called()

    def test_display_prompts_fallback_empty(self):
        """_display_prompts_fallback shows 'No prompts found' when empty."""
        mcp_settings = MagicMock()
        mcp_settings.prompts = []
        table = MagicMock()
        cli._display_prompts_fallback(mcp_settings, table)
        table.add_row.assert_called_once_with(
            "No prompts found", "Check server configuration"
        )

    def test_display_resources_fallback_with_resources(self):
        """_display_resources_fallback populates table with known resources."""
        mcp_settings = MagicMock()
        mcp_settings.resources = ["uml://types"]
        table = MagicMock()
        cli._display_resources_fallback(mcp_settings, table)
        table.add_row.assert_called()

    def test_display_resources_fallback_empty(self):
        """_display_resources_fallback shows 'No resources found' when empty."""
        mcp_settings = MagicMock()
        mcp_settings.resources = []
        table = MagicMock()
        cli._display_resources_fallback(mcp_settings, table)
        table.add_row.assert_called_once_with(
            "No resources found", "Check server configuration"
        )
