import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from panels import _md_to_html, _convert_tables


class TestMdToHtml:
    # ── Headings ──
    def test_h1_heading(self):
        assert "<h2>Title</h2>" in _md_to_html("# Title")

    def test_h2_heading(self):
        assert "<h3>Section</h3>" in _md_to_html("## Section")

    def test_h3_heading(self):
        assert "<h4>Sub</h4>" in _md_to_html("### Sub")

    # ── Bold / Italic ──
    def test_bold(self):
        assert "<strong>hello</strong>" in _md_to_html("**hello**")

    def test_italic_single_word(self):
        assert "<em>word</em>" in _md_to_html("*word*")

    # ── Inline code ──
    def test_inline_code(self):
        assert "<code>fn()</code>" in _md_to_html("`fn()`")

    # ── Horizontal rules ──
    def test_hr(self):
        assert "<hr>" in _md_to_html("---")

    # ── Blockquotes ──
    def test_blockquote(self):
        assert "<blockquote>quote</blockquote>" in _md_to_html("> quote")

    # ── Inner thought ──
    def test_inner_thought(self):
        result = _md_to_html("*(thinking)*")
        assert '<span class="inner-thought">' in result
        assert "（thinking）" in result

    # ── Span preservation (teacher expresions) ──
    def test_preserves_teacher_span(self):
        html = _md_to_html('<span style="color: #999;">*action*</span>')
        assert '<span style="color: #999;">' in html
        assert '</span>' in html
        assert "&lt;span" not in html

    def test_preserves_span_with_inner_thought(self):
        html = _md_to_html('<span style="color: #999;">*(smile)*</span>')
        assert '<span style="color: #999;">' in html
        assert 'inner-thought' in html
        assert '（smile）' in html

    # ── Line breaks ──
    def test_double_newline_to_br(self):
        html = _md_to_html("line1\n\nline2")
        assert "<br>" in html

    # ── HTML escaping ──
    def test_escapes_script_tag(self):
        html = _md_to_html('<script>alert(1)</script>')
        assert '<script>' not in html
        assert '&lt;script&gt;' in html

    def test_escapes_img_onerror(self):
        html = _md_to_html('<img src=x onerror="alert(1)">')
        assert '<img' not in html
        assert '&lt;img' in html

    # ── Tables ──
    def test_converts_table(self):
        md = "| a | b |\n| --- | --- |\n| 1 | 2 |"
        html = _md_to_html(md)
        assert "<table>" in html
        assert "<th>a</th>" in html
        assert "<td>1</td>" in html


class TestConvertTables:
    def test_simple_table(self):
        result = _convert_tables("| Name | Age |\n| --- | --- |\n| John | 30 |")
        assert "<table>" in result
        assert "<th>Name</th>" in result
        assert "<td>John</td>" in result

    def test_table_with_alignment_markers(self):
        result = _convert_tables("| L | R |\n| :-- | --: |\n| a | b |")
        assert "<table>" in result

    def test_no_table_separator_no_conversion(self):
        result = _convert_tables("| just | a row |")
        assert "<table>" not in result

    def test_table_inside_full_markdown(self):
        md = "## Scores\n\n| Name | Score |\n| --- | --- |\n| A | 90 |\n\nDone."
        html = _md_to_html(md)
        assert "<h3>Scores</h3>" in html
        assert "<table>" in html
        assert "<td>A</td>" in html
        assert "<td>90</td>" in html
