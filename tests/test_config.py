# -*- coding: utf-8 -*-
"""Settings, state and backups."""

import json
import os

from app import backup, config, state

from .support import Base


class TestConfig(Base):

    def test_missing_keys_are_filled_from_defaults(self):
        with open(config.CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump({"port": 5050}, fh)
        cfg = config.load(force=True)
        self.assertEqual(cfg["port"], 5050)
        self.assertEqual(cfg["delay_choices"], config.DEFAULTS["delay_choices"])

    def test_broken_file_does_not_block_startup(self):
        # The remote must start even with a broken config: otherwise one
        # bad edit leaves the machine with no remote at all
        with open(config.CONFIG_FILE, "w", encoding="utf-8") as fh:
            fh.write("{not json at all")
        cfg = config.load(force=True)
        self.assertEqual(cfg["port"], config.DEFAULTS["port"])
        self.assertTrue(os.path.exists(config.CONFIG_FILE + ".broken"),
                        "the broken file is kept for inspection")

    def test_defaults_are_not_shared_between_loads(self):
        cfg = config.load(force=True)
        cfg["delay_choices"].append(999)
        config.save(cfg)
        self.assertNotIn(999, config.DEFAULTS["delay_choices"],
                         "editing settings must not mutate the defaults")

    def test_env_password_wins_over_file(self):
        os.environ["REMOTE_WIN11_PASSWORD"] = "from-env"
        try:
            self.assertEqual(config.password(), "from-env")
        finally:
            os.environ.pop("REMOTE_WIN11_PASSWORD")


class TestState(Base):

    def test_snapshot_expires_by_itself(self):
        state.set_pending("shutdown", "word.shutdown", -1)
        self.assertEqual(state.snapshot(), (None, None, 0))

    def test_restore_picks_up_running_timer(self):
        # The timer lives in Windows, not here: after a restart the
        # countdown must continue rather than vanish
        state.set_pending("shutdown", "word.shutdown", 300)
        state._pending = None
        left = state.restore()
        self.assertGreater(left, 290)
        self.assertEqual(state.snapshot()[0], "shutdown")

    def test_restore_ignores_expired_timer(self):
        state.set_pending("shutdown", "word.shutdown", -10)
        state._pending = None
        self.assertEqual(state.restore(), 0)


class TestBackup(Base):

    def test_snapshot_strips_secrets_by_default(self):
        cfg = config.load()
        cfg["mqtt"]["password"] = "broker-secret"
        cfg["backups"]["webhooks"] = [{"name": "n", "url": "http://x",
                                       "enabled": True, "auth_header": "Bearer x"}]
        config.save(cfg)

        snap = backup.snapshot()
        self.assertNotIn("password", snap["config"])
        self.assertEqual(snap["config"]["mqtt"]["password"], "")
        self.assertEqual(snap["config"]["backups"]["webhooks"][0]["auth_header"], "")
        self.assertFalse(snap["includes_secrets"])

    def test_snapshot_can_include_secrets_on_request(self):
        snap = backup.snapshot(include_secrets=True)
        self.assertEqual(snap["config"]["password"], "secret")
        self.assertTrue(snap["includes_secrets"])

    def test_restore_rejects_foreign_file(self):
        ok, text = backup.restore({"app": "something-else"})
        self.assertFalse(ok)
        self.assertIn("not a pc-remote", text)

    def test_restore_keeps_password_when_backup_has_none(self):
        snap = backup.snapshot()
        cfg = config.load()
        cfg["password"] = "new-one"
        config.save(cfg)
        backup.restore(snap)
        self.assertEqual(config.password(), "new-one")

    def test_restore_keeps_nested_secrets(self):
        # A stripped backup carries empty nested passwords; applying them
        # as-is would silently cut the broker connection
        cfg = config.load()
        cfg["mqtt"]["password"] = "broker-secret"
        config.save(cfg)
        snap = backup.snapshot()
        backup.restore(snap)
        self.assertEqual(config.load()["mqtt"]["password"], "broker-secret")

    def test_restore_applies_ordinary_settings(self):
        cfg = config.load()
        cfg["pc_name"] = "From backup"
        config.save(cfg)
        snap = backup.snapshot()

        cfg = config.load()
        cfg["pc_name"] = "Overwritten"
        config.save(cfg)

        ok, _ = backup.restore(snap)
        self.assertTrue(ok)
        self.assertEqual(config.load()["pc_name"], "From backup")

    def test_push_without_targets_is_not_an_error(self):
        results, summary = backup.push()
        self.assertEqual(results, [])
        self.assertIn("No targets", summary)

    def test_filename_has_host_and_timestamp(self):
        name = backup.filename()
        self.assertTrue(name.startswith("pc-remote-"))
        self.assertTrue(name.endswith(".json"))
