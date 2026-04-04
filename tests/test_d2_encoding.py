"""
Tests for D2 encoding/decoding and URL generation.
"""

from tools.kroki.d2 import Layout, Theme, decode, encode, generate_d2graphviz_url


class TestD2Encoding:
    """Tests for D2 encode/decode functions."""

    def test_encode_decode_roundtrip(self):
        """encode then decode returns the original string."""
        original = "a -> b: hello"
        encoded = encode(original)
        decoded = decode(encoded)
        assert decoded == original

    def test_encode_decode_multiline(self):
        """Roundtrip works for multiline D2 code."""
        original = "a -> b\nb -> c\nc -> a"
        assert decode(encode(original)) == original

    def test_encode_decode_unicode(self):
        """Roundtrip works for unicode characters."""
        original = 'node: "Hello World \u2192 \u00e9\u00e8\u00ea"'
        assert decode(encode(original)) == original

    def test_encode_returns_base64_string(self):
        """encode() returns a valid base64 string."""
        encoded = encode("a -> b")
        assert isinstance(encoded, str)
        assert len(encoded) > 0

    def test_encode_empty_string(self):
        """encode() handles empty string."""
        encoded = encode("")
        decoded = decode(encoded)
        assert decoded == ""

    def test_encode_long_input(self):
        """encode() handles long input."""
        original = "a -> b\n" * 500
        assert decode(encode(original)) == original


class TestD2URLGeneration:
    """Tests for generate_d2graphviz_url."""

    def test_default_layout_and_theme(self):
        """Default layout is dagre and theme is 0."""
        url = generate_d2graphviz_url("a -> b")
        assert "layout=dagre" in url
        assert "theme=0" in url
        assert url.startswith("https://play.d2lang.com/")

    def test_custom_layout(self):
        """Custom layout is reflected in URL."""
        url = generate_d2graphviz_url("a -> b", layout=Layout.ELK)
        assert "layout=elk" in url

    def test_custom_theme(self):
        """Custom theme is reflected in URL."""
        url = generate_d2graphviz_url("a -> b", theme=Theme.DARK)
        assert "theme=103" in url

    def test_url_contains_script_param(self):
        """URL contains script= parameter with encoded data."""
        url = generate_d2graphviz_url("hello -> world")
        assert "script=" in url


class TestD2Enums:
    """Tests for Layout and Theme enums."""

    def test_layout_values(self):
        assert Layout.DAGRE.value == "dagre"
        assert Layout.ELK.value == "elk"
        assert Layout.TALA.value == "tala"

    def test_theme_values(self):
        assert Theme.DEFAULT.value == "0"
        assert Theme.DARK.value == "103"
