"""
Unit tests for parsers — no network required.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ais_mcp.parsers import (
    clean_page_text,
    parse_grades_table,
    parse_person,
    text_of,
)
from bs4 import BeautifulSoup


GRADES_HTML = """
<html><body>
<table>
<tr><th>Code</th><th>Course</th><th>Com.</th><th>Attempt</th><th>Result</th><th>Credits</th><th>Type</th></tr>
<tr><td>B-MAT2</td><td>Mathematics 2</td><td>Exm</td><td>1</td><td>A</td><td>6</td><td>compulsory</td></tr>
<tr><td>B-PRS</td><td>Access Networks</td><td>Exm</td><td></td><td></td><td>6</td><td>compulsory</td></tr>
</table>
</body></html>
"""

PERSON_HTML = """
<html><body>
<ul class="breadcrumb"><li class="breadcrumb-item active"><span>John Doe</span></li></ul>
<div>Identification number: 123456</div>
<div>E-mail in the information system: john [at] is.stuba.sk</div>
<div>University e-mail: john.doe [at] stuba.sk</div>
</body></html>
"""


def test_grades_table():
    courses = parse_grades_table(GRADES_HTML)
    assert len(courses) == 2
    mat2 = next(c for c in courses if c["code"] == "B-MAT2")
    assert mat2["result"] == "A"
    assert mat2["credits"] == "6"
    prs = next(c for c in courses if c["code"] == "B-PRS")
    assert prs["result"] == ""


def test_parse_person():
    person = parse_person("https://is.stuba.sk/auth/lide/clovek.pl?id=1", PERSON_HTML)
    assert person["name"] == "John Doe"
    assert person["id"] == "123456"
    assert person["is_email"] == "john@is.stuba.sk"
    assert person["university_email"] == "john.doe@stuba.sk"


def test_clean_page_text():
    html = "<html><body><script>var x=1</script><p>Hello</p><p>  World  </p></body></html>"
    soup = BeautifulSoup(html, "lxml")
    text = clean_page_text(soup)
    assert "Hello" in text
    assert "World" in text
    assert "var x" not in text


def test_text_of_none():
    assert text_of(None) == ""
