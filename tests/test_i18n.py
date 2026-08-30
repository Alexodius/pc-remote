# -*- coding: utf-8 -*-
"""Translations: nothing may stay untranslated silently.

A missing translation breaks nothing — the string simply stays English in the
middle of a translated interface. That is exactly why it is easy to miss, and
exactly why this check is automatic.

The markup is parsed the way the page walker sees it: every chunk of text
between tags is a separate node. A paragraph containing <code> splits into
several strings, each of which must be in the dictionary on its own.
"""

import os
import re

from app import actions, i18n

from .support import Base

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")

# Punctuation, numbers and separators carry no language
NOT_TEXT = re.compile(r"^[\W\d_]*$")

# Product names, endpoints, headers and other literals read the same in
# every language. Listing them explicitly is clearer than guessing by shape.
NEVER_TRANSLATED = {
    "pc-remote", "HTTP API",
    "POST /api", "GET /actions", "GET /healthz",
    "Authorization: Bearer …", "REMOTE_WIN11_PASSWORD",
    "steam://open/bigpicture", "https://…",
    '{"password": "…", "action": "shutdown", "delay": 30}',
}


def flat(text):
    return re.sub(r"\s+", " ", text).strip()


def translatable(text):
    return bool(text) and not NOT_TEXT.match(text) and text not in NEVER_TRANSLATED


def dictionary():
    src = open(os.path.join(APP, "static", "i18n.js"), encoding="utf-8").read()
    start = src.index("const RU = {")
    body = src[start:src.index("\n  };", start)]
    return {flat(m.group(1)) for m in re.finditer(r"'((?:[^'\\]|\\.)*)'\s*:", body)}


def visible_strings(path):
    src = open(path, encoding="utf-8").read()
    src = re.sub(r"<script\b.*?</script>", "", src, flags=re.S)
    src = re.sub(r"<style\b.*?</style>", "", src, flags=re.S)
    src = re.sub(r"<!--.*?-->", "", src, flags=re.S)
    # <code> holds literals: paths, headers, endpoints — never translated
    src = re.sub(r"<code.*?</code>", "", src, flags=re.S)
    src = re.sub(r"\{[%{].*?[%}]\}", "", src, flags=re.S)  # template tags

    out = []
    for attr in ("placeholder", "title"):
        out += [flat(m.group(1)) for m in re.finditer(attr + r'="([^"]+)"', src)]
    out += [flat(m.group(1)) for m in re.finditer(r">([^<>]+)<", src)]
    return [s for s in out if translatable(s)]


QUOTED = r"'((?:[^'\\]|\\.)*)'"

# Every position a visible string can occupy in the scripts. Dialog specs are
# listed because the token confirmation once carried the token name inside the
# key itself, and no dictionary can ever match a key like that.
SCRIPT_PATTERNS = (
    r"I18n\.s\(\s*" + QUOTED,
    r"toast\(\s*" + QUOTED,
    r"\bt\(\s*" + QUOTED,                  # the shorthand inside dialog.js
    r"(?:title|body|ok):\s*" + QUOTED,     # Dialog specs
    r"\.title\s*=\s*" + QUOTED,            # tooltips
)


def script_strings(path):
    src = open(path, encoding="utf-8").read()
    out = []
    for pattern in SCRIPT_PATTERNS:
        out += [flat(m.group(1)) for m in re.finditer(pattern, src)]
    return [s for s in out if translatable(s)]


def entries():
    """Dictionary keys, in the order they appear in the file."""
    src = open(os.path.join(APP, "static", "i18n.js"), encoding="utf-8").read()
    start = src.index("const RU = {")
    body = src[start:src.index("\n  };", start)]
    return [m.group(1) for m in re.finditer(r"\n    " + QUOTED + r"\s*:", body)]


class TestInterfaceTranslations(Base):

    def setUp(self):
        super().setUp()
        self.keys = dictionary()

    def _check(self, strings, where):
        missing = sorted({s for s in strings if s not in self.keys})
        self.assertEqual(missing, [], f"untranslated in {where}: {missing[:5]}")

    def test_remote_page_is_translated(self):
        self._check(visible_strings(os.path.join(APP, "templates", "remote.html")),
                    "remote.html")

    def test_settings_page_is_translated(self):
        self._check(visible_strings(os.path.join(APP, "templates", "admin.html")),
                    "admin.html")

    def test_scripts_are_translated(self):
        for name in ("remote.js", "admin.js", "dialog.js"):
            self._check(script_strings(os.path.join(APP, "static", name)), name)

    def test_dictionary_is_sorted(self):
        # Out of order it stops being readable by eye, and a duplicate key
        # silently shadows the one above it
        keys = entries()
        self.assertEqual(keys, sorted(keys), "the dictionary is out of order")

    def test_no_duplicate_keys(self):
        keys = entries()
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        self.assertEqual(dupes, [], f"duplicate keys: {dupes}")

    def test_placeholder_counts_match(self):
        # A translation that lost its %s drops the value silently, and only
        # in one of the languages
        src = open(os.path.join(APP, "static", "i18n.js"), encoding="utf-8").read()
        start = src.index("const RU = {")
        body = src[start:src.index("\n  };", start)]
        pairs = re.findall(r"\n    " + QUOTED + r"\s*:\s*\n?\s*" + QUOTED, body)
        checked = 0
        for key, value in pairs:
            if "%s" in key or "%s" in value:
                self.assertEqual(key.count("%s"), value.count("%s"), key)
                checked += 1
        self.assertGreater(checked, 0, "the %s check found nothing to check")

    def test_dictionary_has_no_empty_values(self):
        src = open(os.path.join(APP, "static", "i18n.js"), encoding="utf-8").read()
        self.assertNotIn(": '',", src, "an empty placeholder is left in the dictionary")


class TestServerTranslations(Base):

    def test_every_string_exists_in_both_languages(self):
        for key, pair in i18n.STRINGS.items():
            self.assertEqual(len(pair), len(i18n.SUPPORTED), key)
            for value in pair:
                self.assertTrue(value.strip(), f"empty translation: {key}")

    def test_placeholders_match_between_languages(self):
        # A mismatched set of {braces} is a KeyError out of nowhere,
        # and only in one of the languages
        for key, (ru, en) in i18n.STRINGS.items():
            self.assertEqual(set(re.findall(r"\{(\w+)\}", ru)),
                             set(re.findall(r"\{(\w+)\}", en)), key)

    def test_unknown_key_returns_itself(self):
        self.assertEqual(i18n.t("no.such.key"), "no.such.key")

    def test_language_normalisation(self):
        self.assertEqual(i18n.normalize("en-US"), "en")
        self.assertEqual(i18n.normalize("ru_RU"), "ru")
        self.assertEqual(i18n.normalize("de"), i18n.DEFAULT)
        self.assertEqual(i18n.normalize(None), i18n.DEFAULT)

    def test_action_texts_differ_between_languages(self):
        same = [a.id for a in actions.CATALOG
                if a.label("ru") == a.label("en") and a.id != "bigpicture"]
        self.assertEqual(same, [], f"looks untranslated: {same}")
