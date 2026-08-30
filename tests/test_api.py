# -*- coding: utf-8 -*-
"""The HTTP contract, through Flask's test client and no live server.

The frozen part — the /api path, the password/action/delay fields, the
status codes and the "no delay means 30 seconds" rule — is covered in
more detail than the rest, because integrations depend on it and they
break silently.
"""

import json

from app import actions, config, server

from .support import Base


class ApiBase(Base):

    def setUp(self):
        super().setUp()
        self.rec = self.stub_system()
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()

    def post(self, path, payload, headers=None):
        resp = self.client.post(path, data=json.dumps(payload),
                                content_type="application/json",
                                headers=headers or {},
                                environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
        body = resp.get_json(silent=True) or {}
        return resp.status_code, body

    def get(self, path):
        resp = self.client.get(path, environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
        return resp.status_code, resp

    def api(self, **payload):
        payload.setdefault("password", "secret")
        return self.post("/api", payload)


class TestFrozenContract(ApiBase):

    def test_missing_delay_means_thirty_seconds(self):
        # Exactly what integrations configured before `delay` existed send
        status, body = self.api(action="shutdown")
        self.assertEqual(status, 200)
        self.assertEqual(self.rec.last, ["shutdown", "/s", "/t", "30", "/f"])
        self.assertIn(body["pending_left"], (29, 30))

    def test_explicit_delay_is_used(self):
        self.api(action="shutdown", delay=120)
        self.assertEqual(self.rec.last, ["shutdown", "/s", "/t", "120", "/f"])

    def test_garbage_delay_falls_back_to_default(self):
        self.api(action="shutdown", delay="not-a-number")
        self.assertEqual(self.rec.last, ["shutdown", "/s", "/t", "30", "/f"])

    def test_delay_is_clamped(self):
        self.api(action="shutdown", delay=99999)
        self.assertEqual(self.rec.last, ["shutdown", "/s", "/t", "600", "/f"])
        self.api(action="shutdown", delay=-5)
        self.assertEqual(self.rec.last, ["shutdown", "/s", "/t", "0", "/f"])

    def test_status_codes(self):
        self.assertEqual(self.post("/api", {"password": "wrong", "action": "cancel"})[0], 403)
        self.assertEqual(self.api(action="no-such-action")[0], 400)

    def test_form_and_query_are_accepted(self):
        resp = self.client.post("/api", data={"password": "secret", "action": "cancel"},
                                environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(resp.status_code, 200)

    def test_system_failure_returns_500(self):
        self.rec.returncode, self.rec.stderr = 5, "access denied"
        status, body = self.api(action="shutdown")
        self.assertEqual(status, 500)
        self.assertIn("access denied", body["error"])


class TestAuth(ApiBase):

    def test_token_works_like_password(self):
        from app import security
        token = security.issue_token("test")
        self.assertEqual(self.api(action="cancel", password=token)[0], 200)

    def test_token_works_as_bearer_header(self):
        from app import security
        token = security.issue_token("test")
        status, _ = self.post("/api", {"action": "cancel"},
                              headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(status, 200)

    def test_revoked_token_is_rejected(self):
        from app import security
        token = security.issue_token("test")
        tid = security.list_tokens()[0]["id"]
        security.revoke_token(tid)
        self.assertEqual(self.api(action="cancel", password=token)[0], 403)

    def test_token_value_is_never_returned(self):
        from app import security
        security.issue_token("test")
        listed = json.dumps(security.list_tokens(), ensure_ascii=False)
        self.assertNotIn(config.load()["api_tokens"][0]["token"], listed)

    def test_lockout_after_repeated_failures(self):
        cfg = config.load()
        cfg["max_fails"], cfg["lockout_sec"] = 3, 300
        config.save(cfg)
        for _ in range(3):
            self.post("/api", {"password": "wrong", "action": "cancel"})
        status, body = self.api(action="cancel")
        self.assertEqual(status, 429)
        self.assertIn("Locked out", body["error"])

    def test_foreign_network_is_refused(self):
        resp = self.client.get("/healthz", environ_overrides={"REMOTE_ADDR": "8.8.8.8"})
        self.assertEqual(resp.status_code, 403)


class TestDisabledActions(ApiBase):

    def test_disabled_action_is_refused(self):
        cfg = config.load()
        cfg["actions"] = {"lock": {"enabled": False}}
        config.save(cfg)
        status, body = self.api(action="lock")
        self.assertEqual(status, 403)
        self.assertIn("disabled", body["error"])
        self.assertEqual(self.rec.calls, [], "a disabled action must not run")

    def test_disabled_action_disappears_from_catalog(self):
        cfg = config.load()
        cfg["actions"] = {"lock": {"enabled": False}}
        config.save(cfg)
        _, resp = self.get("/actions")
        ids = [a["id"] for a in resp.get_json()["actions"]]
        self.assertNotIn("lock", ids)


class TestPublicEndpoints(ApiBase):

    def test_healthz_needs_no_password(self):
        status, resp = self.get("/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(resp.get_json()["status"], "ok")

    def test_healthz_shows_pending(self):
        self.api(action="shutdown", delay=90)
        _, resp = self.get("/healthz")
        data = resp.get_json()
        self.assertEqual(data["pending"], "shutdown")
        self.assertGreater(data["pending_left"], 80)

    def test_actions_catalog_shape(self):
        _, resp = self.get("/actions")
        data = resp.get_json()
        self.assertTrue(data["groups"])
        for item in data["actions"]:
            self.assertLessEqual({"id", "label", "icon", "group", "tone"}, set(item))

    def test_pages_render(self):
        for path in ("/", "/admin", "/manifest.webmanifest"):
            status, resp = self.get(path)
            self.assertEqual(status, 200, path)
            self.assertNotIn(b"{{", resp.data, f"{path}: unrendered template")

    def test_catalog_hides_where_a_custom_button_points(self):
        # /actions asks for no password, and the target is a path on this
        # disk — the button's name is all an unauthenticated caller gets
        cfg = config.load()
        cfg["launchers"] = [{"name": "Notes", "target": r"C:\secret\diary.exe"}]
        config.save(cfg)
        _, resp = self.get("/actions")
        item = next(a for a in resp.get_json()["actions"]
                    if a["id"].startswith("launch:"))
        self.assertEqual(item["label"], "Notes")
        self.assertNotIn("diary", item["hint"])


class TestAdminApi(ApiBase):

    def admin(self, op, **extra):
        return self.post("/admin/api", dict(op=op, password="secret", **extra))

    def test_get_hides_secrets(self):
        status, body = self.admin("get")
        self.assertEqual(status, 200)
        self.assertNotIn("password", body["config"])
        self.assertEqual(body["config"]["mqtt"]["password"], "")

    def test_save_ignores_unknown_keys(self):
        self.admin("save", config={"pc_name": "Test", "not-a-setting": 1})
        cfg = config.load()
        self.assertEqual(cfg["pc_name"], "Test")
        self.assertNotIn("not-a-setting", cfg)

    def test_save_cannot_change_password(self):
        self.admin("save", config={"password": "hijacked"})
        self.assertEqual(config.password(), "secret")

    def test_password_change_requires_length(self):
        status, _ = self.admin("password", new_password="123")
        self.assertEqual(status, 400)

    def test_settings_page_still_sees_the_target(self):
        # The settings page asked for a password, so it gets the path it
        # needs to show — the catalog is trimmed only where it is open
        cfg = config.load()
        cfg["launchers"] = [{"name": "Notes", "target": r"C:\secret\diary.exe"}]
        config.save(cfg)
        _, body = self.admin("get")
        item = next(a for a in body["catalog"] if a["id"].startswith("launch:"))
        self.assertIn("diary", item["hint"])

    def test_log_survives_nonsense_line_counts(self):
        for value in ("abc", None, -5, 10 ** 9):
            status, body = self.admin("log", lines=value)
            self.assertEqual(status, 200, value)
            self.assertLessEqual(len(body["lines"]), 2000, value)

    def test_unknown_op(self):
        self.assertEqual(self.admin("no-such-op")[0], 400)


class TestFirstRun(ApiBase):
    """No password in the settings means the remote has never been claimed."""

    def unclaimed(self, value=""):
        cfg = config.load()
        cfg["password"] = value
        config.save(cfg)

    def test_nothing_runs_before_a_password_exists(self):
        self.unclaimed()
        for secret in ("", "anything", None):
            status, _ = self.post("/api", {"password": secret, "action": "lock"})
            self.assertEqual(status, 403, secret)
        self.assertEqual(self.rec.calls, [], "a command ran on an unclaimed remote")

    def test_the_old_shipped_placeholder_does_not_count(self):
        # It was printed in the README of every published copy, so it is a
        # published string rather than a password
        self.unclaimed("changeme")
        self.assertTrue(config.needs_setup())
        status, _ = self.post("/api", {"password": "changeme", "action": "lock"})
        self.assertEqual(status, 403)

    def test_setup_claims_the_remote_once(self):
        self.unclaimed()
        status, body = self.post("/setup", {"password": "chosen-by-me"})
        self.assertEqual(status, 200, body)
        self.assertFalse(config.needs_setup())

        status, _ = self.post("/api", {"password": "chosen-by-me", "action": "lock"})
        self.assertEqual(status, 200)

        # A second call is a closed door, not a password reset
        status, _ = self.post("/setup", {"password": "someone-else"})
        self.assertEqual(status, 409)
        self.assertEqual(config.password(), "chosen-by-me")

    def test_setup_refuses_a_short_password(self):
        self.unclaimed()
        status, _ = self.post("/setup", {"password": "abc"})
        self.assertEqual(status, 400)
        self.assertTrue(config.needs_setup())

    def test_the_gate_shows_on_both_pages(self):
        self.unclaimed()
        for path in ("/", "/admin"):
            _, resp = self.get(path)
            self.assertIn(b'data-setup="1"', resp.data, path)
        self.post("/setup", {"password": "chosen-by-me"})
        for path in ("/", "/admin"):
            _, resp = self.get(path)
            self.assertIn(b'data-setup="0"', resp.data, path)
