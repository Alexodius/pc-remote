# -*- coding: utf-8 -*-
"""Action catalog: which commands get built and what comes back.

Nothing is executed here — the border with the system is stubbed in
support.Base.stub_system.
"""

import os
from unittest import mock

from app import actions, config, state

from .support import Base


class TestPowerActions(Base):

    def test_shutdown_builds_expected_command(self):
        rec = self.stub_system()
        ok, text, _ = actions.execute(actions.get("shutdown"), 30)
        self.assertTrue(ok)
        self.assertEqual(rec.last, ["shutdown", "/s", "/t", "30", "/f"])
        self.assertIn("30", text)

    def test_reboot_uses_r_flag(self):
        rec = self.stub_system()
        actions.execute(actions.get("reboot"), 45)
        self.assertEqual(rec.last, ["shutdown", "/r", "/t", "45", "/f"])

    def test_zero_delay_forces_apps_closed(self):
        # Windows implies /f above zero, but at zero a single unsaved
        # document would stall the shutdown
        rec = self.stub_system()
        ok, text, _ = actions.execute(actions.get("shutdown"), 0)
        self.assertTrue(ok)
        self.assertIn("/f", rec.last)
        self.assertEqual(state.snapshot()[2], 0, "no countdown at zero delay")

    def test_pending_state_is_set_and_counted(self):
        self.stub_system()
        actions.execute(actions.get("shutdown"), 60)
        act, _, left = state.snapshot()
        self.assertEqual(act, "shutdown")
        self.assertGreater(left, 55)

    def test_cancel_clears_pending(self):
        self.stub_system()
        actions.execute(actions.get("shutdown"), 60)
        actions.execute(actions.get("cancel"), 0)
        self.assertEqual(state.snapshot(), (None, None, 0))

    def test_cancel_without_timer_is_not_an_error(self):
        # 1116 means no shutdown was scheduled. An early version
        # returned 500 for it and showed a scary red error.
        self.stub_system(returncode=1116)
        ok, text, _ = actions.execute(actions.get("cancel"), 0)
        self.assertTrue(ok)
        self.assertIn("No timer", text)

    def test_failure_is_reported_not_swallowed(self):
        self.stub_system(returncode=1, stderr="access denied")
        ok, text, rc = actions.execute(actions.get("shutdown"), 30)
        self.assertFalse(ok)
        self.assertIn("access denied", text)
        self.assertEqual(rc, 1)


class TestSuspendActions(Base):
    """Sleep, hibernation and sign-out take the machine down along with
    the calling process, so they must not wait for a result."""

    def test_sleep_is_detached(self):
        rec = self.stub_system()
        ok, _, _ = actions.execute(actions.get("sleep"), 0)
        self.assertTrue(ok)
        self.assertEqual(rec.last, ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])

    def test_hibernate_and_logoff_are_detached(self):
        rec = self.stub_system()
        actions.execute(actions.get("hibernate"), 0)
        self.assertEqual(rec.last, ["shutdown", "/h"])
        actions.execute(actions.get("logoff"), 0)
        self.assertEqual(rec.last, ["shutdown", "/l"])

    def test_suspend_actions_do_not_use_waiting_runner(self):
        # Checks the implementation itself: run_cmd waits for a result
        # and on a real machine would hang until the timeout, then
        # report failure where everything worked.
        for action_id in ("sleep", "hibernate", "logoff"):
            src = actions.get(action_id).run.__code__.co_names \
                + actions.get(action_id).run.__code__.co_freevars
            self.assertNotIn("run_cmd", src, f"{action_id} must not wait for a result")


class TestCatalogRules(Base):

    def test_locked_actions_cannot_be_disabled(self):
        cfg_off = {"shutdown": {"enabled": False},
                   "reboot": {"enabled": False},
                   "cancel": {"enabled": False}}
        from app import config
        cfg = config.load()
        cfg["actions"] = cfg_off
        config.save(cfg)
        for action_id in ("shutdown", "reboot", "cancel"):
            self.assertTrue(actions.is_enabled(actions.get(action_id)),
                            f"{action_id} is locked and must stay enabled")

    def test_optional_actions_respect_defaults(self):
        self.assertFalse(actions.is_enabled(actions.get("hibernate")))
        self.assertFalse(actions.is_enabled(actions.get("logoff")))
        self.assertTrue(actions.is_enabled(actions.get("lock")))

    def test_unknown_action_is_none(self):
        self.assertIsNone(actions.get("no-such-action"))

    def test_every_action_has_icon_and_group(self):
        for a in actions.CATALOG:
            self.assertIn(a.group, actions.GROUPS, a.id)
            self.assertTrue(a.icon, a.id)

    def test_every_action_is_translated(self):
        # A missing translation shows up as the key itself: quiet but
        # visible, so both languages are checked at once
        for a in actions.CATALOG:
            for lang in ("ru", "en"):
                self.assertNotIn(".label", a.label(lang), f"{a.id}/{lang}")
                self.assertNotIn(".hint", a.hint(lang), f"{a.id}/{lang}")

    def test_groups_are_translated(self):
        titles_ru = [g["title"] for g in actions.groups("ru")]
        titles_en = [g["title"] for g in actions.groups("en")]
        self.assertNotIn("group.power", titles_ru + titles_en)
        self.assertNotEqual(titles_ru, titles_en)

    def test_answers_come_in_requested_language(self):
        self.stub_system(returncode=1116)
        _, ru, _ = actions.execute(actions.get("cancel"), 0, "ru")
        _, en, _ = actions.execute(actions.get("cancel"), 0, "en")
        self.assertNotEqual(ru, en)
        self.assertIn("timer", en.lower())

    def test_launchers_get_namespaced_ids(self):
        from app import config
        cfg = config.load()
        cfg["launchers"] = [{"name": "My Player", "target": "C:/player.exe"},
                            {"name": "my player", "target": "C:/other.exe"}]
        config.save(cfg)
        ids = [a.id for a in actions.all_actions()]
        self.assertIn("launch:my_player", ids)
        # Identical names must not collapse onto one id
        self.assertIn("launch:my_player_2", ids)

    def test_launcher_keeps_its_own_name_in_both_languages(self):
        from app import config
        cfg = config.load()
        cfg["launchers"] = [{"name": "My Player", "target": "C:/player.exe"}]
        config.save(cfg)
        a = actions.get("launch:my_player")
        self.assertEqual(a.label("en"), "My Player",
                         "a person chose the name, nothing to translate")

    def test_exception_inside_action_does_not_escape(self):
        def explode(_delay, _lang=None):
            raise RuntimeError("boom")

        broken = actions.Action("broken", "app", "apps", explode)
        ok, text, rc = actions.execute(broken, 0)
        self.assertFalse(ok)
        self.assertIn("boom", text)
        self.assertEqual(rc, -1)


class TestLaunchers(Base):
    """Custom buttons run programs, and where they run from matters."""

    def launcher(self, name, target):
        cfg = config.load()
        cfg["launchers"] = [{"name": name, "target": target}]
        config.save(cfg)
        return next(a for a in actions.all_actions()
                    if a.id.startswith("launch:"))

    def test_a_program_starts_in_its_own_folder(self):
        # A launcher sitting next to the files it loads finds nothing when
        # it inherits the remote's working directory
        target = os.path.join(self._tmp.name, "launcher.exe")
        open(target, "wb").close()
        action = self.launcher("Game", target)
        with mock.patch("os.startfile") as started:
            actions.execute(action, 0)
        self.assertEqual(started.call_args.kwargs.get("cwd"), self._tmp.name)

    def test_a_uri_is_handed_over_as_is(self):
        action = self.launcher("Big Picture", "steam://open/bigpicture")
        with mock.patch("os.startfile") as started:
            actions.execute(action, 0)
        self.assertEqual(started.call_args.args[0], "steam://open/bigpicture")
        self.assertNotIn("cwd", started.call_args.kwargs)

    def test_ids_never_collide(self):
        cfg = config.load()
        cfg["launchers"] = [{"name": "Game", "target": "a.exe"},
                            {"name": "Game", "target": "b.exe"}]
        config.save(cfg)
        ids = [a.id for a in actions.all_actions() if a.id.startswith("launch:")]
        self.assertEqual(len(ids), len(set(ids)), ids)
