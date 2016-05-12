-- https://github.com/gratipay/gratipay.com/pull/4009

BEGIN;
    -- Farewell, old takes table!
    DROP VIEW current_takes;
    DROP TABLE takes;

    -- Be gone, payroll! I never knew you.
    DROP VIEW current_payroll;
    DROP TABLE payroll;
END;


-- https://github.com/gratipay/gratipay.com/pull/4023

BEGIN;

    -- takes - how participants express membership in teams
    CREATE TABLE takes
    ( id                bigserial                   PRIMARY KEY
    , ctime             timestamp with time zone    NOT NULL
    , mtime             timestamp with time zone    NOT NULL DEFAULT now()
    , participant_id    bigint                      NOT NULL REFERENCES participants(id)
    , team_id           bigint                      NOT NULL REFERENCES teams(id)
    , ntakes            bigint                      NOT NULL
    , recorder_id       bigint                      NOT NULL REFERENCES participants(id)
    , CONSTRAINT not_negative CHECK (ntakes >= 0)
     );

    CREATE VIEW memberships AS
        SELECT * FROM (
             SELECT DISTINCT ON (participant_id, team_id) t.*
               FROM takes t
               JOIN participants p ON p.id = t.participant_id
              WHERE p.is_suspicious IS NOT TRUE
           ORDER BY participant_id
                  , team_id
                  , mtime DESC
        ) AS anon WHERE ntakes > 0;

    ALTER TABLE teams ADD COLUMN ntakes bigint default 0;
    ALTER TABLE teams ADD COLUMN ntakes_unclaimed bigint default 0;
    ALTER TABLE teams ADD COLUMN ntakes_claimed bigint default 0;
    ALTER TABLE teams ADD CONSTRAINT ntakes_sign CHECK (ntakes >= 0);
    ALTER TABLE teams ADD CONSTRAINT ntakes_sum CHECK (ntakes = ntakes_claimed + ntakes_unclaimed);

END;


CREATE FUNCTION propagate_takes_insert()
RETURNS trigger AS $$
DECLARE
    is_new_member   bool;
    team_ntakes     bigint;
    team_receiving  numeric(35,2);

    delta_n         int;
    delta_amount    numeric(35,2);

    old_taking      numeric(35,2);
    old_ntaking_from int;
    old_ntakes      bigint;
    old_amount      numeric(35,2);

    new_amount      numeric(35,2);
BEGIN
    is_new_member := ( SELECT id
                         FROM memberships
                        WHERE participant_id=NEW.participant_id
                          AND team_id=NEW.team_id
                      ) IS NULL;

    team_ntakes := (SELECT ntakes FROM teams WHERE id=NEW.team_id);
    team_receiving := (SELECT receiving FROM teams WHERE id=NEW.team_id);
    new_amount := (NEW.ntakes::numeric / team_ntakes::numeric) * team_receiving;
    new_amount := round(new_amount, 2);

    IF is_new_member THEN

        -- They're being added to a team.

        IF NEW.ntakes = 0 THEN
            RAISE 'How did you get here?'; -- They are leaving a team they're not on!
        ELSE
            delta_n := 1;
            delta_amount := new_amount;
        END IF;
    ELSE

        -- They're leaving a team or changing their take.

        old_ntaking_from := (SELECT ntaking_from FROM participants WHERE id=NEW.participant_id);
        old_taking := (SELECT taking FROM participants WHERE id=NEW.participant_id);
        old_ntakes := ( SELECT ntakes
                          FROM memberships
                         WHERE team_id=NEW.team_id
                           AND participant_id=NEW.participant_id
                       );
        old_amount := (old_ntakes / team_ntakes) * team_receiving;
        old_amount := round(old_amount, 2);

        IF NEW.ntakes = 0 THEN

            -- They're leaving a team.

            delta_n := -1;

            IF old_ntaking_from = 1 THEN

                -- They're leaving their *last* team; use their entire old
                -- taking amount as the delta to avoid rounding errors.

                delta_amount := -old_taking;

            ELSE

                -- They're leaving a team, but it's not their last; use an
                -- estimate of the value of their take.

                delta_amount := -old_amount;

            END IF;
        ELSE

            -- They're changing their takes.

            delta_n := 0;
            delta_amount := new_amount - old_amount;

        END IF;
    END IF;

    UPDATE participants
       SET ntaking_from = ntaking_from + delta_n
         , taking = taking + delta_amount
     WHERE id = NEW.participant_id;

    UPDATE teams
       SET ndistributing_to = ndistributing_to + delta_n
         , distributing = distributing + delta_amount
     WHERE id = NEW.team_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER propagate_takes_insert
    BEFORE INSERT ON takes
    FOR EACH ROW EXECUTE PROCEDURE propagate_takes_insert();
