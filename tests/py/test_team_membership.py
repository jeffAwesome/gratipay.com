from __future__ import absolute_import, division, print_function, unicode_literals

from test_team_takes import TeamTakesHarness
from gratipay.models.team import mixins


class Tests(TeamTakesHarness):

    def setUp(self):
        TeamTakesHarness.setUp(self)
        self.enterprise.set_ntakes(1000)

    def assert_memberships(self, *expected):
        actual = self.enterprise.get_memberships()
        assert [(m.participant.username, m.ntakes) for m in actual] == list(expected)


    def test_team_object_subclasses_takes_mixin(self):
        assert isinstance(self.enterprise, mixins.Membership)


    # gm - get_memberships

    def test_gm_returns_an_empty_list_when_there_are_no_members(self):
        assert self.enterprise.get_memberships() == []

    def test_gm_returns_memberships_when_there_are_members(self):
        self.enterprise.add_member(self.crusher)
        assert len(self.enterprise.get_memberships()) == 1

    def test_gm_returns_more_memberships_when_there_are_more_members(self):
        self.enterprise.add_member(self.crusher)
        self.enterprise.add_member(self.bruiser)
        assert len(self.enterprise.get_memberships()) == 2


    # am - add_member

    def test_am_adds_a_member(self):
        self.enterprise.add_member(self.crusher)
        self.assert_memberships(('crusher', 1))

    def test_am_adds_another_member(self):
        self.enterprise.add_member(self.crusher)
        self.enterprise.add_member(self.bruiser)
        self.assert_memberships(('crusher', 1), ('bruiser', 1))

    def test_am_affects_cacheroonies_as_expected(self):
        self.enterprise.add_member(self.crusher)
        self.enterprise.add_member(self.bruiser)
        assert self.enterprise.nmembers == 2
        assert self.enterprise.ntakes_claimed == 2
        assert self.enterprise.ntakes_unclaimed == 998


    # rm - remove_member

    def test_rm_removes_a_member(self):
        self.enterprise.add_member(self.crusher)
        self.enterprise.add_member(self.bruiser)
        self.enterprise.remove_member(self.crusher)
        self.assert_memberships(('bruiser', 1))

    def test_rm_removes_another_member(self):
        self.enterprise.add_member(self.crusher)
        self.enterprise.add_member(self.bruiser)
        self.enterprise.remove_member(self.crusher)
        self.enterprise.remove_member(self.bruiser)
        self.assert_memberships()

    def test_rm_affects_cacheroonies_as_expected(self):
        self.enterprise.add_member(self.crusher)
        self.enterprise.add_member(self.bruiser)
        self.enterprise.remove_member(self.crusher)
        assert self.enterprise.nmembers == 1
        assert self.enterprise.ntakes_claimed == 1
        assert self.enterprise.ntakes_unclaimed == 999
