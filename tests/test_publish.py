"""
tests/test_publish.py — Unit tests for review/publish.py.

All HTTP calls are simulated; no real network traffic is made.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch, call

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from review.publish import (
    split_review,
    md_to_slack,
    chunk_text,
    publish,
    _build_score_line,
    SEPARATOR,
)

# ── helpers ──────────────────────────────────────────────────────────────────

SAMPLE_MAIN = """# Revue pipeline — 2026-11-18 — Atelier Nova

110 deals ouverts pour 2 484 500\u202f€ de pipeline.

## Priorités

**Deal A** (Acme) — Négociation — 51 500\u202f€
- Aucune activité depuis 43 jours"""

SAMPLE_DETAIL = """## Détail par AE

### Alice Moreau

**Deal A** (Acme) — Alice Moreau — Négociation — 51 500\u202f€
- Aucune activité depuis 43 jours

## Vus, pas inquiétants

- Deal B (Beta, Alice Moreau) — durée normale pour ce secteur"""

SAMPLE_REVIEW = SAMPLE_MAIN + "\n" + SEPARATOR + "\n\n" + SAMPLE_DETAIL

FAKE_TOKEN = "xoxb-fake-token-do-not-log"
FAKE_CHANNEL = "C0TEST123"


def _make_review_file(tmp_dir, content=None, name="review_hermes_2026-11-18.md"):
    path = os.path.join(tmp_dir, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content if content is not None else SAMPLE_REVIEW)
    return path


def _make_eval_file(tmp_dir, name="review_hermes_2026-11-18.md"):
    stem = os.path.splitext(name)[0]
    eval_path = os.path.join(tmp_dir, f"eval_{stem}.json")
    ev = {
        "recall": 1.0,
        "false_leurres": 0,
        "invented_numbers": 0,
        "length_words": 150,
        "pass": True,
    }
    with open(eval_path, "w", encoding="utf-8") as fh:
        json.dump(ev, fh)
    return eval_path


def _mock_post(ts="111.222"):
    """Return a mock _post_fn that always succeeds and records calls."""
    calls = []

    def _fn(token, payload):
        calls.append(payload.copy())
        return {"ok": True, "ts": ts}

    _fn.calls = calls
    return _fn


# ── split_review ─────────────────────────────────────────────────────────────

class TestSplitReview(unittest.TestCase):

    def test_normal_split(self):
        main, detail = split_review(SAMPLE_REVIEW)
        self.assertIn("Revue pipeline", main)
        self.assertIn("Détail par AE", detail)
        self.assertNotIn(SEPARATOR, main)
        self.assertNotIn(SEPARATOR, detail)

    def test_missing_separator_raises(self):
        with self.assertRaises(ValueError) as ctx:
            split_review("No separator here.")
        self.assertIn(SEPARATOR, str(ctx.exception))

    def test_multiple_separators_raises(self):
        bad = SAMPLE_REVIEW + "\n" + SEPARATOR + "\n extra"
        with self.assertRaises(ValueError) as ctx:
            split_review(bad)
        self.assertIn("2", str(ctx.exception))


# ── md_to_slack ───────────────────────────────────────────────────────────────

class TestMdToSlack(unittest.TestCase):

    def test_h1_becomes_bold(self):
        result = md_to_slack("# My Title")
        self.assertEqual(result, "*My Title*")

    def test_h2_becomes_bold(self):
        result = md_to_slack("## Section")
        self.assertEqual(result, "*Section*")

    def test_h3_becomes_bold(self):
        result = md_to_slack("### Sub")
        self.assertEqual(result, "*Sub*")

    def test_bold_double_star_converted(self):
        result = md_to_slack("**Deal A** (Acme)")
        self.assertEqual(result, "*Deal A* (Acme)")

    def test_italic_unchanged(self):
        result = md_to_slack("_some italic_")
        self.assertEqual(result, "_some italic_")

    def test_bullet_list_unchanged(self):
        result = md_to_slack("- item one\n- item two")
        self.assertEqual(result, "- item one\n- item two")

    def test_bullet_symbol_unchanged(self):
        result = md_to_slack("• item one")
        self.assertEqual(result, "• item one")

    def test_mixed_content(self):
        md = "# Title\n\n**Bold** text\n\n- list item"
        slack = md_to_slack(md)
        self.assertIn("*Title*", slack)
        self.assertIn("*Bold* text", slack)
        self.assertIn("- list item", slack)


# ── chunk_text ────────────────────────────────────────────────────────────────

class TestChunkText(unittest.TestCase):

    def test_short_text_not_chunked(self):
        text = "Short text."
        chunks = chunk_text(text, max_chars=100)
        self.assertEqual(chunks, ["Short text."])

    def test_exact_limit_not_chunked(self):
        text = "x" * 100
        chunks = chunk_text(text, max_chars=100)
        self.assertEqual(len(chunks), 1)

    def test_splits_on_paragraph_boundary(self):
        para_a = "A" * 60
        para_b = "B" * 60
        text = para_a + "\n\n" + para_b
        chunks = chunk_text(text, max_chars=80)
        self.assertEqual(len(chunks), 2)
        self.assertIn("A", chunks[0])
        self.assertIn("B", chunks[1])

    def test_each_chunk_within_limit(self):
        # Build a text that must be chunked
        lines = ["Line number " + str(i) + ": " + ("x" * 40) for i in range(50)]
        text = "\n\n".join(lines)
        chunks = chunk_text(text, max_chars=200)
        for i, c in enumerate(chunks):
            self.assertLessEqual(len(c), 200, f"Chunk {i} exceeds limit: {len(c)}")

    def test_all_content_preserved(self):
        paras = ["Para " + str(i) + ": " + "word " * 10 for i in range(20)]
        text = "\n\n".join(paras)
        chunks = chunk_text(text, max_chars=200)
        combined = "\n\n".join(chunks)
        for para in paras:
            self.assertIn(para.strip()[:20], combined)

    def test_heading_stays_with_next_paragraph(self):
        """An AE heading (*Name*) must not be isolated at chunk boundary."""
        # Build a text where without keep_headings_with_next, the heading
        # would end up alone at the end of a chunk
        big_intro = "A" * 60 + "\n\nB" * 60
        ae_heading = "*Alice Moreau*"
        ae_content = "**Deal X** (Acme) — Alice Moreau — Négociation — 51\u202f500\u202f€\n- Fait important"
        text = big_intro + "\n\n" + ae_heading + "\n\n" + ae_content
        chunks = chunk_text(text, max_chars=130, keep_headings_with_next=True)
        # The heading must not appear alone in any chunk
        for chunk in chunks:
            stripped = chunk.strip()
            if stripped == ae_heading:
                self.fail(f"AE heading was isolated in a chunk: {repr(chunk)}")


# ── publish: thread structure ─────────────────────────────────────────────────

class TestPublishThread(unittest.TestCase):

    def _run_publish(self, tmp_dir, mock_post, **kwargs):
        review_file = _make_review_file(tmp_dir)
        _make_eval_file(tmp_dir)
        with patch("review.publish._load_config", return_value=(FAKE_TOKEN, FAKE_CHANNEL)):
            publish(review_file, _post_fn=mock_post, **kwargs)
        return mock_post.calls

    def test_first_call_has_no_thread_ts(self):
        with tempfile.TemporaryDirectory() as tmp:
            mock_post = _mock_post(ts="1000.001")
            calls = self._run_publish(tmp, mock_post)
            self.assertNotIn("thread_ts", calls[0])
            self.assertEqual(calls[0]["channel"], FAKE_CHANNEL)

    def test_subsequent_calls_use_thread_ts(self):
        with tempfile.TemporaryDirectory() as tmp:
            mock_post = _mock_post(ts="1000.001")
            calls = self._run_publish(tmp, mock_post)
            for c in calls[1:]:
                self.assertEqual(c.get("thread_ts"), "1000.001",
                                 f"Expected thread_ts in call: {c}")

    def test_detail_posted_in_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            mock_post = _mock_post(ts="1000.001")
            calls = self._run_publish(tmp, mock_post)
            detail_calls = [c for c in calls[1:] if "Détail" in c.get("text", "")]
            self.assertGreater(len(detail_calls), 0, "Detail not found in thread calls")

    def test_score_posted_in_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            mock_post = _mock_post(ts="1000.001")
            calls = self._run_publish(tmp, mock_post)
            score_calls = [c for c in calls if "Score" in c.get("text", "")]
            self.assertEqual(len(score_calls), 1)
            self.assertEqual(score_calls[0].get("thread_ts"), "1000.001")

    def test_at_least_two_api_calls(self):
        """main + at least one detail chunk = minimum 2 calls."""
        with tempfile.TemporaryDirectory() as tmp:
            mock_post = _mock_post()
            calls = self._run_publish(tmp, mock_post)
            self.assertGreaterEqual(len(calls), 2)


# ── anti-duplicate ────────────────────────────────────────────────────────────

class TestAntiDuplicate(unittest.TestCase):

    def test_refuses_if_already_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            review_file = _make_review_file(tmp)
            # Write a fake published marker
            stem = os.path.splitext(os.path.basename(review_file))[0]
            marker = os.path.join(tmp, f"published_{stem}.json")
            with open(marker, "w") as fh:
                json.dump({"ts": "999.000", "channel": FAKE_CHANNEL,
                           "published_at": "2026-01-01T00:00:00Z"}, fh)

            mock_post = _mock_post()
            with patch("review.publish._load_config", return_value=(FAKE_TOKEN, FAKE_CHANNEL)):
                with self.assertRaises(RuntimeError) as ctx:
                    publish(review_file, _post_fn=mock_post)
            self.assertIn("already published", str(ctx.exception).lower())
            self.assertEqual(mock_post.calls, [], "HTTP call should not have been made")

    def test_force_allows_republish(self):
        with tempfile.TemporaryDirectory() as tmp:
            review_file = _make_review_file(tmp)
            stem = os.path.splitext(os.path.basename(review_file))[0]
            marker = os.path.join(tmp, f"published_{stem}.json")
            with open(marker, "w") as fh:
                json.dump({"ts": "999.000", "channel": FAKE_CHANNEL,
                           "published_at": "2026-01-01T00:00:00Z"}, fh)

            mock_post = _mock_post(ts="1001.000")
            with patch("review.publish._load_config", return_value=(FAKE_TOKEN, FAKE_CHANNEL)):
                result = publish(review_file, _post_fn=mock_post, force=True)
            self.assertGreater(len(mock_post.calls), 0, "Should have made HTTP calls")
            self.assertEqual(result["ts"], "1001.000")

    def test_published_marker_written_after_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            review_file = _make_review_file(tmp)
            stem = os.path.splitext(os.path.basename(review_file))[0]
            marker = os.path.join(tmp, f"published_{stem}.json")

            mock_post = _mock_post(ts="2000.001")
            with patch("review.publish._load_config", return_value=(FAKE_TOKEN, FAKE_CHANNEL)):
                publish(review_file, _post_fn=mock_post)

            self.assertTrue(os.path.exists(marker))
            with open(marker) as fh:
                data = json.load(fh)
            self.assertEqual(data["ts"], "2000.001")
            self.assertEqual(data["channel"], FAKE_CHANNEL)


# ── dry-run ───────────────────────────────────────────────────────────────────

class TestDryRun(unittest.TestCase):

    def test_dry_run_no_http_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            review_file = _make_review_file(tmp)
            mock_post = _mock_post()
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                result = publish(review_file, dry_run=True, _post_fn=mock_post)
            self.assertIsNone(result)
            self.assertEqual(mock_post.calls, [], "dry-run must not make HTTP calls")

    def test_dry_run_does_not_write_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            review_file = _make_review_file(tmp)
            stem = os.path.splitext(os.path.basename(review_file))[0]
            marker = os.path.join(tmp, f"published_{stem}.json")
            with patch("sys.stdout", io.StringIO()):
                publish(review_file, dry_run=True, _post_fn=_mock_post())
            self.assertFalse(os.path.exists(marker))

    def test_dry_run_prints_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            review_file = _make_review_file(tmp)
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                publish(review_file, dry_run=True, _post_fn=_mock_post())
            output = captured.getvalue()
            self.assertIn("DRY RUN", output)
            self.assertIn("chunk", output.lower())

    def test_dry_run_no_config_required(self):
        """dry-run must not fail when no Slack config is present."""
        with tempfile.TemporaryDirectory() as tmp:
            review_file = _make_review_file(tmp)
            # Ensure no env vars and no config file
            env_patch = {k: "" for k in ("SLACK_BOT_TOKEN", "SLACK_CHANNEL")}
            fake_home = tmp  # ~/.config/crm-fictif/slack.env won't exist here
            with patch.dict(os.environ, env_patch):
                with patch("os.path.expanduser", return_value=os.path.join(tmp, "no.env")):
                    with patch("sys.stdout", io.StringIO()):
                        try:
                            publish(review_file, dry_run=True, _post_fn=_mock_post())
                        except RuntimeError as exc:
                            self.fail(f"dry-run raised RuntimeError unexpectedly: {exc}")


# ── token security ────────────────────────────────────────────────────────────

class TestTokenSecurity(unittest.TestCase):

    def test_token_never_in_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            review_file = _make_review_file(tmp)
            captured = io.StringIO()
            with patch("review.publish._load_config",
                       return_value=(FAKE_TOKEN, FAKE_CHANNEL)):
                with patch("sys.stdout", captured):
                    publish(review_file, _post_fn=_mock_post())
            self.assertNotIn(FAKE_TOKEN, captured.getvalue(),
                             "Token must not appear in stdout")

    def test_token_never_in_error_messages(self):
        """Even when the API returns an error, the token must not appear."""
        with tempfile.TemporaryDirectory() as tmp:
            review_file = _make_review_file(tmp)

            def _failing_post(token, payload):
                # Intentionally raise with a generic message
                raise RuntimeError("Slack API returned error: invalid_auth")

            with patch("review.publish._load_config",
                       return_value=(FAKE_TOKEN, FAKE_CHANNEL)):
                try:
                    publish(review_file, _post_fn=_failing_post)
                except RuntimeError as exc:
                    self.assertNotIn(FAKE_TOKEN, str(exc),
                                     "Token must not appear in error message")

    def test_token_never_in_dry_run_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            review_file = _make_review_file(tmp)
            captured = io.StringIO()
            # Patch _load_config so it would return the token IF called
            with patch("review.publish._load_config",
                       return_value=(FAKE_TOKEN, FAKE_CHANNEL)):
                with patch("sys.stdout", captured):
                    publish(review_file, dry_run=True, _post_fn=_mock_post())
            self.assertNotIn(FAKE_TOKEN, captured.getvalue())


# ── score line builder ────────────────────────────────────────────────────────

class TestBuildScoreLine(unittest.TestCase):

    def test_returns_empty_when_no_eval_file(self):
        result = _build_score_line("/nonexistent/path/eval_x.json")
        self.assertEqual(result, "")

    def test_includes_pass_indicator(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
            json.dump({"pass": True, "recall": 1.0, "invented_numbers": 0,
                       "length_words": 150}, fh)
            path = fh.name
        try:
            result = _build_score_line(path)
            self.assertIn("OK", result)
            self.assertIn("100%", result)
        finally:
            os.unlink(path)

    def test_includes_fail_indicator_on_failure(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
            json.dump({"pass": False, "recall": 0.7, "invented_numbers": 2,
                       "length_words": 300}, fh)
            path = fh.name
        try:
            result = _build_score_line(path)
            self.assertIn("FAIL", result)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
