__all__ = ["InstapaperScraper"]

import re

from lxml import html
from lxml.html.clean import clean_html


class InstapaperScraper(object):

    """ Scrapes articles based on a given set of Instapaper directives """

    def __init__(self, spec):
        """
        Args:
          spec (defaultdict of list): Dictionary of Instapaper directives.
              See `saulify.sitespec.load_rules` for details on the format.
        """
        self.spec = spec

    def clean_article(self, source):
        """ Extract article according to scraping spec.

        Args:
          source (str): The article page html.

        Returns:
            lxml.ElementTree of the cleaned article.
        """

        result = {}

        # Directives acting on the html source
        source = self._find_replace(source)
        source = self._maybe_clean(source)

        etree = html.fromstring(source)

        # Directives extracting content from the DOM

        for c in ["date", "title", "footnotes"]:
            n = self._extract_first(etree, c)
            if n is not None:
                result[c] = n.text_content().strip()

        authors = []
        for node in self._extract_all(etree, "author"):
            authors.append(node.text_content().strip())
        result["authors"] = ", ".join(authors)

        # Directives acting on the article body
        maybe_body = self._extract_first(etree, "body")
        body = maybe_body if maybe_body is not None else etree
        self._strip_nodes(body)
        self._strip_id_or_class(body)
        self._strip_image_src(body)
        self._maybe_prune(body)

        result["html"] = html.tostring(body)

        return result

    def _maybe_clean(self, source):
        if self.spec["lxml_clean"] is not False:
            return clean_html(source)
        return source

    def _find_replace(self, source):
        """ Implements the `find_string` and `replace_string` directives.

        Uses simple (non-regex) find and replace.
        """
        for find, replace in self.spec["find_replace"]:
            source = source.replace(find, replace)
        return source

    def _strip_nodes(self, etree):
        """ Implements the `strip` directive.

        Strips any elements matched by the configured xpaths.
        """
        for xpath in self.spec["strip"]:
            self._drop_by_xpath(etree, xpath)

    def _strip_image_src(self, etree):
        """ Implements the `strip_img_src` directive.

        Strips any `img` whose @src contains certain substrings.
        """
        for substr in self.spec["strip_image_src"]:
            # The value for this field is sometimes surrounded by quotes
            substr = substr.strip(" \"'")
            xpath = '//img[contains(@src,"{0}")]'.format(substr)
            self._drop_by_xpath(etree, xpath)

    def _maybe_prune(self, elem, special_limit=0.5):
        """ Implements the `prune` directive.

        Strips "elements within body that do not resemble content elements".
        Uses heuristic based on fraction of alphanumeric characters in tags.

        Args:
            elem (lxml.Element): The body element to be pruned

            special_limit (float): Elements which include more than this
                fraction of special characters (ignoring whitespace) are pruned.

        Returns:
            `None`; mutates `elem`
        """

        nonspecial = re.compile(r'[\w,\.]', re.UNICODE)
        whitespace = re.compile(r'\s', re.UNICODE)

        def prune_element(e):

            for child in e.xpath("*"):
                prune_element(child)

            # If a sub-element was kept, don't try to prune this element.
            if len(e) > 0:
                return

            content = e.text_content().strip()

            nsc = len(re.findall(nonspecial, content))
            wc = len(re.findall(whitespace, content))
            sc = len(content) - wc - nsc

            if e.tag not in ["br"]:
                if sc + nsc == 0 or float(sc) / (sc + nsc) > special_limit:
                    e.drop_tree()

        if self.spec["prune"] is not False:
            for e in elem.xpath("*"):
                prune_element(e)

    def _strip_id_or_class(self, etree):
        """ Implements the `strip_id_or_class` directive.

        Strips any elements whose @id or @class contains certain substrings.
        Functionality is defined by the fivefilters documentation and contains
        many potential problems (e.g. this will drop elements with class equal
        to "notclass1" when the supplied string is "class1", see the unit test).

        Fixes are possible but may break compatibility with some existing site
        configuration files.

        TODO : assess the extent to which existing configuration files would
        need to be adjusted if the semantics of this directive were changed to
        use set-wise logic on class selectors (hopefully this would be minimal)
        """
        for id_or_class in self.spec["strip_id_or_class"]:
            # The value for this field is sometimes surrounded by quotes
            id_or_class = id_or_class.strip(" \"'")
            xpath = '//*[contains(@class,"{0}")] | //*[contains(@id,"{0}")]' \
                    .format(id_or_class)
            self._drop_by_xpath(etree, xpath)

    def _drop_by_xpath(self, etree, xpath):
        """ Drop all elements matching `xpath` from `etree` """
        for elem in etree.xpath(xpath):
            elem.drop_tree()

    def _extract_all(self, etree, component):
        """ Find nodes in the DOM for all xpaths in a spec directive.

        Args:
            etree (lxml.ElementTree): DOM from which to extract data.

            component (str): A key in the spec (e.g. `"author"`),
                for which nodes will be extracted.

        Returns:
            A flat list of the matching nodes for every configured xpath.
        """
        for xpath in self.spec[component]:
            for node in etree.xpath(xpath):
                yield node

    def _extract_first(self, etree, component):
        """ Find first DOM node matching an xpath in a spec directive.

        Args:
            etree (lxml.ElementTree): DOM from which to extract node.

            component (str): Key in the spec (e.g. `"author"`).

        Returns:
            An `lxml.Element` if any nodes were matched, otherwise `None`.
        """
        g = self._extract_all(etree, component)
        return next(g, None)
