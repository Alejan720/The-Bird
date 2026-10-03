import asyncio
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from database import Database


class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.sqlite")
        self.db = Database()
        self.db.db_name = self.db_path
        await self.db.setup()

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_concurrent_transfers_cannot_overdraw(self):
        db = self.db.for_guild(11)
        await db.update_user_balance(1, 100)
        results = await asyncio.gather(
            db.transfer(1, 2, 80),
            db.transfer(1, 3, 80),
        )
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual((await db.get_user(1))["balance"], 20)
        self.assertEqual(
            (await db.get_user(2))["balance"] + (await db.get_user(3))["balance"],
            80,
        )

    async def test_purchase_is_atomic_and_adds_inventory(self):
        db = self.db.for_guild(12)
        await db.update_user_balance(1, 100)
        self.assertTrue(await db.purchase_item(1, "escudo", 80, "2030-01-01T00:00:00+00:00"))
        self.assertFalse(await db.purchase_item(1, "escudo", 80))
        self.assertEqual((await db.get_user(1))["balance"], 20)
        self.assertEqual(await db.get_item_count(1, "escudo"), 1)

    async def test_daily_claim_has_atomic_cooldown(self):
        db = self.db.for_guild(13)
        now = datetime.now(timezone.utc).isoformat()
        results = await asyncio.gather(*(
            db.claim_reward(1, "last_daily", 86400, 100, now)
            for _ in range(2)
        ))
        self.assertEqual(sum(result[0] for result in results), 1)
        self.assertEqual((await db.get_user(1))["balance"], 100)

    async def test_setup_migrates_existing_user_table_without_losing_balance(self):
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("DROP TABLE users")
            connection.execute("""
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    bank INTEGER DEFAULT 0,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    last_daily TEXT,
                    last_rob TEXT,
                    last_message_time REAL DEFAULT 0
                )
            """)
            connection.execute("INSERT INTO users (user_id, balance) VALUES (42, 275)")
            connection.commit()
        finally:
            connection.close()
        with patch("database.Config.LEGACY_ECONOMY_GUILD_ID", 42):
            await self.db.setup()
        target = self.db.for_guild(42)
        self.assertEqual((await target.get_user(42))["balance"], 275)
        async with self.db.connect() as connection:
            legacy = await (await connection.execute("SELECT balance FROM users WHERE user_id = 42")).fetchone()
        self.assertEqual(legacy[0], 275)

    async def test_setup_requires_legacy_migration_target(self):
        async with self.db.connect() as connection:
            await connection.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (44, 'cafe', 1)")
            await connection.commit()
        with patch("database.Config.LEGACY_ECONOMY_GUILD_ID", 0):
            with self.assertRaisesRegex(RuntimeError, "datos económicos globales"):
                await self.db.setup()

    async def test_legacy_naive_utc_cooldown_is_accepted(self):
        db = self.db.for_guild(14)
        await db.update_user_balance(1, 0)
        old_timestamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        async with db.connect() as connection:
            await connection.execute("UPDATE guild_users SET last_daily = ? WHERE guild_id = ? AND user_id = ?", (old_timestamp, 14, 1))
            await connection.commit()
        claimed, remaining, _ = await db.claim_reward(
            1, "last_daily", 86400, 100, datetime.now(timezone.utc).isoformat()
        )
        self.assertFalse(claimed)
        self.assertGreater(remaining, 0)

    async def test_xp_cooldown_is_atomic_and_levels_carry_over(self):
        db = self.db.for_guild(15)
        results = await asyncio.gather(
            db.update_user_xp_level(9, 350, 100, 1000.0, 60),
            db.update_user_xp_level(9, 350, 100, 1000.0, 60),
        )
        self.assertEqual(sorted(results), [-1, 2])
        user = await db.get_user(9)
        self.assertEqual(user["level"], 3)
        self.assertEqual(user["xp"], 50)

    async def test_market_buying_and_selling_pressure_changes_price_direction(self):
        db = self.db.for_guild(16)
        self.assertEqual(len(await self.db.get_market_assets()), 7)
        await db.update_user_balance(1, 100_000)
        bought, price, _, _ = await db.trade_asset(1, "AUR", 10, True)
        self.assertTrue(bought)
        initial_price = price
        now = datetime.now(timezone.utc) + timedelta(hours=1)
        with patch("database.random.uniform", return_value=0):
            self.assertEqual(await self.db.advance_market(now), 1)
        after_buy = (await self.db.get_market_assets())[0][2]
        self.assertGreater(after_buy, initial_price)

        sold, sell_price, proceeds, profit = await db.trade_asset(1, "AUR", 10, False)
        self.assertTrue(sold)
        self.assertEqual(proceeds, sell_price * 10)
        self.assertGreater(profit, 0)
        with patch("database.random.uniform", return_value=0):
            self.assertEqual(await self.db.advance_market(now + timedelta(hours=1)), 1)
        after_sell = (await self.db.get_market_assets())[0][2]
        self.assertLess(after_sell, sell_price)
        history = await db.get_market_trade_history(1)
        self.assertEqual([trade[1] for trade in history], ["sell", "buy"])

    async def test_market_position_limit_blocks_concentration(self):
        db = self.db.for_guild(17)
        await db.update_user_balance(2, 1_000_000)
        allowed, _, _, _ = await db.trade_asset(2, "NEX", 1000, True)
        self.assertTrue(allowed)
        rejected, _, _, _ = await db.trade_asset(2, "NEX", 1, True)
        self.assertFalse(rejected)

    async def test_properties_generate_bank_rent_and_cap_offline_accrual(self):
        db = self.db.for_guild(18)
        await db.update_user_balance(5, 10_000)
        bought, price = await db.buy_property(5, "casa", datetime.now(timezone.utc).isoformat())
        self.assertTrue(bought)
        self.assertEqual(price, 2500)
        async with db.connect() as connection:
            await connection.execute(
            "UPDATE guild_property_holdings SET last_collected_at = ? WHERE guild_id = ? AND user_id = ?",
            ((datetime.now(timezone.utc) - timedelta(hours=200)).isoformat(), 18, 5),
            )
            await connection.commit()
        payout = await db.collect_rent(5, datetime.now(timezone.utc))
        self.assertEqual(payout, 12 * 168)
        self.assertEqual((await db.get_user(5))["bank"], payout)
        sold, resale = await db.sell_property(5, "casa")
        self.assertTrue(sold)
        self.assertEqual(resale, 1875)
        sold_again, _ = await db.sell_property(5, "casa")
        self.assertFalse(sold_again)
        self.assertEqual(len(await db.get_properties(5)), 6)

    async def test_consumables_apply_bonus_once_and_open_crate_atomically(self):
        db = self.db.for_guild(19)
        await db.add_item(7, "cafe")
        self.assertTrue(await db.activate_work_boost(7, 50))
        self.assertFalse(await db.activate_work_boost(7, 50))
        now = datetime.now(timezone.utc).isoformat()
        claimed, reward, _ = await db.claim_reward(7, "last_work", 0, 100, now)
        self.assertTrue(claimed)
        self.assertEqual(reward, 150)
        self.assertEqual((await db.get_user(7))["balance"], 150)
        await db.add_item(7, "caja")
        self.assertTrue(await db.open_crate(7, 300))
        self.assertFalse(await db.open_crate(7, 300))
        self.assertEqual((await db.get_user(7))["balance"], 450)

    async def test_daily_coupon_doubles_next_daily_reward_once(self):
        db = self.db.for_guild(20)
        await db.add_item(10, "cupon_diario")
        self.assertTrue(await db.activate_daily_coupon(10, 100))
        self.assertFalse(await db.activate_daily_coupon(10, 100))
        now = datetime.now(timezone.utc).isoformat()
        claimed, reward, _ = await db.claim_reward(10, "last_daily", 86400, 100, now)
        self.assertTrue(claimed)
        self.assertEqual(reward, 200)
        self.assertEqual((await db.get_user(10))["balance"], 200)

    async def test_robbery_insurance_is_consumed_on_failure(self):
        db = self.db.for_guild(21)
        await db.update_user_balance(20, 1000)
        await db.update_user_balance(21, 1000)
        await db.add_item(20, "seguro")
        self.assertTrue(await db.activate_robbery_insurance(20))
        with patch("database.random.randint", return_value=100):
            result, amount, _ = await db.rob(
                20, 21, datetime.now(timezone.utc).isoformat(), 0, 0, 20, 20
            )
        self.assertEqual((result, amount), ("insured", 0))
        self.assertEqual((await db.get_user(20))["balance"], 1000)
        self.assertFalse(await db.activate_robbery_insurance(20))

    async def test_admin_adjustments_are_audited_and_cannot_overdraw(self):
        guild_db = self.db.for_guild(900)
        await guild_db.update_user_balance(30, 500)
        self.assertTrue(await guild_db.admin_adjust_balance(
            900, 1, 30, 125, "grant", "Premio del torneo", datetime.now(timezone.utc).isoformat()
        ))
        self.assertFalse(await guild_db.admin_adjust_balance(
            900, 1, 30, 1000, "remove", "Sanción", datetime.now(timezone.utc).isoformat()
        ))
        self.assertEqual((await guild_db.get_user(30))["balance"], 625)
        self.assertEqual((await self.db.for_guild(901).get_user(30))["balance"], 0)
        audit = await guild_db.get_economy_audit(900)
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0][2:5], (125, "grant", "Premio del torneo"))

    async def test_guild_settings_reminders_and_moderation_cases_persist(self):
        await self.db.set_guild_setting(77, "log_channel_id", 1234)
        self.assertEqual(await self.db.get_guild_settings(77), (None, 1234, None))
        due_at = datetime.now(timezone.utc).isoformat()
        reminder_id = await self.db.add_reminder(5, 77, 4567, "Prueba", due_at)
        due = await self.db.get_due_reminders(due_at)
        self.assertEqual(due[0], (reminder_id, 5, 4567, "Prueba"))
        await self.db.mark_reminder_delivered(reminder_id)
        self.assertEqual(await self.db.get_due_reminders(due_at), [])
        case_id = await self.db.create_moderation_case(77, 5, 6, "warning", "Reincidencia", due_at)
        cases = await self.db.get_moderation_cases(77, 5)
        self.assertEqual(cases[0][:4], (case_id, 6, "warning", "Reincidencia"))

    async def test_questionnaire_and_vote_survive_database_reopen(self):
        questionnaire_id = await self.db.create_questionnaire(
            77, 6, 4567, "Roles", "¿Cuál?", '["A", "B"]', '{"roles": [1, 2], "multiple": true}',
            datetime.now(timezone.utc).isoformat(),
        )
        await self.db.set_questionnaire_message(questionnaire_id, 9876)
        await self.db.save_questionnaire_vote(questionnaire_id, 5, "[0, 1]")
        active = await self.db.get_active_questionnaires()
        self.assertEqual(active[0][:2], (questionnaire_id, 9876))
        self.assertEqual(await self.db.get_questionnaire_vote(questionnaire_id, 5), "[0, 1]")

        from cogs.questionnaries import QuestionnairesCog
        restored = []
        bot = SimpleNamespace(db=self.db, add_view=lambda view, message_id: restored.append((view, message_id)))
        cog = QuestionnairesCog(bot)
        await cog.cog_load()
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0][1], 9876)
        self.assertIsNone(restored[0][0].timeout)

    async def test_sqlite_backup_is_readable(self):
        backup_file = os.path.join(self.temp_dir.name, "backup.sqlite")
        guild_db = self.db.for_guild(808)
        await guild_db.update_user_balance(8, 90)
        await self.db.backup(backup_file)
        backup = sqlite3.connect(backup_file)
        try:
            balance = backup.execute(
                "SELECT balance FROM guild_users WHERE guild_id = 808 AND user_id = 8"
            ).fetchone()[0]
        finally:
            backup.close()
        self.assertEqual(balance, 90)

    async def test_economy_is_isolated_between_guilds(self):
        first = self.db.for_guild(101)
        second = self.db.for_guild(202)
        await first.update_user_balance(50, 700)
        await first.add_item(50, "cafe")
        gained = await first.update_user_xp_level(50, 80, 100, 1000.0, 60)
        self.assertEqual(gained, 0)
        self.assertEqual((await first.get_user(50))["balance"], 700)
        self.assertEqual((await second.get_user(50))["balance"], 0)
        self.assertEqual((await first.get_user(50))["xp"], 80)
        self.assertEqual((await second.get_user(50))["xp"], 0)
        self.assertEqual(await first.get_item_count(50, "cafe"), 1)
        self.assertEqual(await second.get_item_count(50, "cafe"), 0)

    async def test_wealth_and_leaderboard_only_include_current_guild(self):
        first = self.db.for_guild(111)
        second = self.db.for_guild(222)
        await first.update_user_balance(60, 900)
        await second.update_user_balance(60, 100)
        self.assertEqual(await first.get_user_wealth(60), (900, 0, 0, 0))
        self.assertEqual(await second.get_user_wealth(60), (100, 0, 0, 0))
        self.assertEqual(await first.get_leaderboard(), [(60, 900)])

    async def test_legacy_economy_migrates_once_to_selected_guild_and_keeps_source(self):
        async with self.db.connect() as connection:
            await connection.execute("INSERT INTO users (user_id, balance, xp, level) VALUES (75, 1234, 80, 2)")
            await connection.execute(
                "INSERT INTO inventory (user_id, item_name, quantity) VALUES (75, 'seguro', 2)"
            )
            await connection.commit()
        target = self.db.for_guild(303)
        self.assertTrue(await target.migrate_legacy_economy(303))
        self.assertFalse(await target.migrate_legacy_economy(303))
        self.assertFalse(await self.db.for_guild(404).migrate_legacy_economy(404))
        self.assertEqual((await target.get_user(75))["balance"], 1234)
        self.assertEqual(await target.get_item_count(75, "seguro"), 2)
        self.assertEqual((await self.db.for_guild(404).get_user(75))["balance"], 0)
        async with self.db.connect() as connection:
            legacy_balance = await (await connection.execute(
                "SELECT balance FROM users WHERE user_id = 75"
            )).fetchone()
        self.assertEqual(legacy_balance[0], 1234)


if __name__ == "__main__":
    unittest.main()