""" Reading and representation of Instapaper spec files. """

import sys

from saulify.clean import clean_content


class TestCase(object):
    """
    Test case for the article scraper.

    Attributes:
      url (str): URL of the page being tested
      fragments (list of str): Fragments of text that should be present in
        the output of the scraper.
    """

    def __init__(self, url):
        self.url = url
        self.fragments = []

    def add_contains(self, fragment):
        self.fragments.append(fragment)

    def run(self):
        try:
            output = clean_content(self.url)["plaintext"]
        except Exception as e:
            sys.stderr.write("Exception on " + self.url + " :\n")
            sys.stderr.write(str(e))
            return {
                "url": self.url,
                "status": "EXCEPTION",
                "message": "e.message"
            }
        else:
            return {
                "url": self.url,
                "status": "OK",
                "missing_fragments": self.missing_fragments(output),
            }

    def missing_fragments(self, text):
        missing = []
        for s in self.fragments:
            if s not in text:
                missing.append(s)
        return missing


def load_testcases(fpath):
    """
    Reads test cases from an Instapaper spec file.

    Scans file until it reaches a line labelled "test_url", then creates a
    new ``TestCase`` object. Subsequent lines populate the test case.
    Multiple test cases in a single file are supported.

    Args:
      fpath: Path to the spec file.

    Returns:
      A list of ``TestCase`` objects.
    """

    def parse_specline(line):
        parts = line.partition(':')
        label = parts[0]
        content = parts[2].strip()
        return (label, content)

    cases = []

    with open(fpath) as f:
        for line_str in f:
            line = line_str.decode("utf-8")
            (label, content) = parse_specline(line)
            if label == "test_url":
                url = content
                case = TestCase(url)
                cases.append(case)
            elif label == "test_contains":
                if not cases:
                    raise Exception("Invalid spec file: " + fpath)
                fragment = content
                cases[-1].add_contains(fragment)

    return cases
