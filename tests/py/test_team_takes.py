from __future__ import absolute_import, division, print_function, unicode_literals

from decimal import Decimal as D

from gratipay.testing import Harness
from gratipay.models.participant import Participant
from gratipay.models.team.mixins.takes import BadMember
from pytest import raises


class TeamTakesHarness(Harness):
    # Factored out to share with membership tests ...

    def setUp(self):
        self.enterprise = self.make_team('The Enterprise')

        self.TT = self.db.one("SELECT id FROM countries WHERE code='TT'")

        self.picard = Participant.from_username(self.enterprise.owner)

        self.crusher = self.make_participant( 'crusher'
                                            , email_address='crusher@example.com'
                                            , claimed_time='now'
                                            , last_paypal_result=''
                                             )
        self.crusher.store_identity_info(self.TT, 'nothing-enforced', {'name': 'Crusher'})
        self.crusher.set_identity_verification(self.TT, True)

        self.bruiser = self.make_participant( 'bruiser'
                                            , email_address='bruiser@example.com'
                                            , claimed_time='now'
                                            , last_paypal_result=''
                                             )
        self.bruiser.store_identity_info(self.TT, 'nothing-enforced', {'name': 'Bruiser'})
        self.bruiser.set_identity_verification(self.TT, True)

        self.bob = self.make_participant('bob', claimed_time='now', last_bill_result='')
        self.bob.set_payment_instruction(self.enterprise, '99.00')

    @property
    def last_event(self):
        return self.db.one("SELECT * FROM events ORDER BY ts DESC LIMIT 1")

    @property
    def last_take(self):
        return self.db.one("SELECT * FROM takes ORDER BY mtime DESC LIMIT 1")


class TestSetNtakes(TeamTakesHarness):

    def test_sn_sets_ntakes(self):
        assert self.enterprise.set_ntakes(1024, self.picard) == 1024

    def test_sn_actually_sets_ntakes(self):
        self.enterprise.set_ntakes(1024, self.picard)
        assert self.db.one("SELECT ntakes FROM teams") == self.enterprise.ntakes == 1024

    def test_sn_wont_set_ntakes_below_zero(self):
        assert self.enterprise.set_ntakes(-1, self.picard) == 0

    def test_sn_wont_set_ntakes_below_nclaimed(self):
        self.enterprise.set_ntakes(1024, self.picard)
        self.enterprise.set_ntakes_for(self.crusher, 128)
        assert self.enterprise.set_ntakes(-1024, self.picard) == 128

    def test_sn_affects_cacheroonies_as_expected(self):
        assert self.enterprise.ntakes == 0
        assert self.enterprise.ntakes_claimed == 0
        assert self.enterprise.ntakes_unclaimed == 0

        self.enterprise.set_ntakes(1024, self.picard)
        assert self.enterprise.ntakes == 1024
        assert self.enterprise.ntakes_claimed == 0
        assert self.enterprise.ntakes_unclaimed == 1024

        self.enterprise.set_ntakes_for(self.crusher, 128)

        self.enterprise.set_ntakes(-1024, self.picard)
        assert self.enterprise.ntakes == 128
        assert self.enterprise.ntakes_claimed == 128
        assert self.enterprise.ntakes_unclaimed == 0

    def test_sn_logs_recorder(self):
        self.enterprise.set_ntakes(1023, self.picard)
        assert self.last_event.payload['recorder_id'] == self.picard.id


class TestSetNtakesFor(TeamTakesHarness):

    def setUp(self):
        super(TestSetNtakesFor, self).setUp()
        self.enterprise.set_ntakes(1000, self.picard)


    def test_snf_sets_ntakes_for(self):
        assert self.enterprise.set_ntakes_for(self.crusher, 537) == 537

    def test_snf_actually_sets_ntakes_for(self):
        self.enterprise.set_ntakes_for(self.crusher, 537)
        assert self.db.one("SELECT ntakes FROM takes") == 537

    def test_snf_takes_as_much_as_is_available(self):
        assert self.enterprise.set_ntakes_for(self.crusher, 1000) == 1000

    def test_snf_caps_ntakes_to_the_number_available(self):
        assert self.enterprise.set_ntakes_for(self.crusher, 1024) == 1000

    def test_snf_works_with_another_member_present(self):
        assert self.enterprise.set_ntakes_for(self.bruiser, 537) == 537
        assert self.enterprise.set_ntakes_for(self.crusher, 537) == 463

    def test_snf_affects_cacheroonies_as_expected(self):
        self.enterprise.set_ntakes_for(self.bruiser, 537)
        self.enterprise.set_ntakes_for(self.crusher, 128)
        assert self.enterprise.ndistributing_to == 2
        assert self.enterprise.ntakes_claimed == 665
        assert self.enterprise.ntakes_unclaimed == 335

    def test_snf_sets_ntakes_properly_for_an_existing_member(self):
        assert self.enterprise.set_ntakes_for(self.crusher, 537) == 537
        assert self.enterprise.set_ntakes_for(self.bruiser, 537) == 463
        assert self.enterprise.set_ntakes_for(self.crusher, 128) == 128
        assert self.enterprise.ndistributing_to == 2
        assert self.enterprise.ntakes_claimed   ==  463 + 128 == 591
        assert self.enterprise.ntakes_unclaimed == 1000 - 591 == 409

    def test_snf_records_recorder(self):
        self.enterprise.set_ntakes_for(self.crusher, 537)
        assert self.last_take.recorder_id == self.crusher.id

    def test_snf_lets_someone_else_be_the_recorder(self):
        assert self.enterprise.set_ntakes_for(self.crusher, 537, self.picard) == 537
        assert self.last_take.recorder_id == self.picard.id

    def test_snf_updates_taking_on_member(self):
        self.crusher.ntaking_from == 0
        self.enterprise.set_ntakes_for(self.crusher, 537)
        assert self.crusher.taking == D('53.16')
        assert self.crusher.ntaking_from == 1


    def assert_bad_member(self, member, reason):
        err = raises(BadMember, self.enterprise.set_ntakes_for, member, 867).value
        assert err.reason == reason
        assert self.enterprise.set_ntakes_for(member, 0) == 0

    def test_snf_requires_that_member_is_claimed_even_when_setting_to_zero(self):
        alice = self.make_participant('alice')
        err = raises(BadMember, self.enterprise.set_ntakes_for, alice, 867).value
        assert err.reason == 'unclaimed'
        err = raises(BadMember, self.enterprise.set_ntakes_for, alice, 0).value
        assert err.reason == 'unclaimed'

    def test_snf_requires_that_member_is_not_suspicious_except_when_setting_to_zero(self):
        alice = self.make_participant('alice', claimed_time='now', is_suspicious=True)
        self.assert_bad_member(alice, 'suspicious')

    def test_snf_requires_that_member_has_an_email_except_when_setting_to_zero(self):
        alice = self.make_participant('alice', claimed_time='now')
        self.assert_bad_member(alice, 'missing an email')

    def test_snf_requires_that_member_has_an_identity_except_when_setting_to_zero(self):
        alice = self.make_participant('alice', claimed_time='now', email_address='foo@example.com')
        self.assert_bad_member(alice, 'missing an identity')

    def test_snf_requires_that_member_has_a_payout_route_except_when_setting_to_zero(self):
        alice = self.make_participant('alice', claimed_time='now', email_address='foo@example.com')
        alice.store_identity_info(self.TT, 'nothing-enforced', {'name': 'Alice'})
        alice.set_identity_verification(self.TT, True)
        self.assert_bad_member(alice, 'missing a payout route')
