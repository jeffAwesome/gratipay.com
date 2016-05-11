from __future__ import absolute_import, division, print_function, unicode_literals


class NoRoom(Exception):
    pass


class MembershipMixin(object):
    """This mixin provides membership management for
    :py:class:`~gratipay.models.team.Team` objects. It depends on API in the
    :py:class:`~gratipay.models.team.mixins.Takes` mixin.
    """

    @property
    def nmembers(self):
        return self.ndistributing_to


    def get_memberships(self, cursor=None):
        """Return a list of memberships for this team.
        """
        return (cursor or self.db).all("""

            SELECT cm.*
                 , (SELECT p.*::participants
                      FROM participants p
                     WHERE p.id=participant_id) AS participant
              FROM memberships cm
              JOIN teams t
                ON t.id = cm.team_id
             WHERE t.id = %s
               AND t.ntakes > 0

        """, (self.id,))


    def add_member(self, participant):
        """Add a participant to this team.

        :param Participant participant: the participant to add
        :raises NoRoom: if are no unclaimed takes for the participant to claim

        """
        ntakes = self.set_ntakes_for(participant, 1)
        if ntakes == 0:
            raise NoRoom


    def remove_member(self, participant):
        """Remove a participant from this team.

        :param Participant participant: the participant to remove

        """
        self.set_ntakes_for(participant, 0)
