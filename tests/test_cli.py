"""
Tests for mcp_core.core.cli.
"""

import logging
import os
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
        with patch.object(sys, "argv", ["prog", "--transport", "invalid"]):
            with pytest.raises(SystemExit):
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
        """safe_import of nonexistent module returns None."""
        with patch.object(cli.console, "print"), patch.object(
            logging.getLogger("mcp_core.core.cli"), "error"
        ):
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
        """run() with --list-tools displays tools and returns without starting server."""
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
    def test_run_stdio_skips_human_output_by_default(
        self,
        parse_mock,
        setup_mock,
        safe_import_mock,
        get_server_mock,
        start_server_mock,
    ):
        """run() with stdio transport does not emit Rich console output by default."""
        parse_mock.return_value = MagicMock(
            debug=False,
            transport="stdio",
            host="127.0.0.1",
            port=8000,
            list_tools=False,
        )
        with patch.object(cli.console, "print") as print_mock:
            cli.run()
        print_mock.assert_not_called()
        start_server_mock.assert_called_once_with(
            transport="stdio", host="127.0.0.1", port=8000
        )

    @patch("mcp_core.core.server.start_server")
    @patch("mcp_core.core.server.get_mcp_server")
    @patch(
        "mcp_core.core.config.MCP_SETTINGS",
        MagicMock(
            version="1.0",
            server_name="Test",
            tools=["generate_uml"],
            prompts=["uml_diagram"],
            resources=["uml://types"],
        ),
    )
    @patch("mcp_core.core.cli.safe_import", return_value=MagicMock())
    @patch("mcp_core.core.cli.setup_logging", return_value=MagicMock())
    @patch("mcp_core.core.cli.parse_args")
    def test_run_stdio_can_render_human_output_when_explicitly_enabled(
        self,
        parse_mock,
        setup_mock,
        safe_import_mock,
        get_server_mock,
        start_server_mock,
    ):
        """run() can render stderr UI in stdio mode only when explicitly enabled."""
        parse_mock.return_value = MagicMock(
            debug=False,
            transport="stdio",
            host="127.0.0.1",
            port=8000,
            list_tools=True,
        )
        with patch.dict(os.environ, {"UML_MCP_STDIO_UI": "true"}, clear=False):
            with patch.object(cli.console, "print") as print_mock:
                cli.run()
        assert print_mock.call_count >= 4
        start_server_mock.assert_not_called()
