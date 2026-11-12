"""Unit tests for study and protocol registries and protocol immutability."""

from pathlib import Path

import pytest

from voxneuro.study.consent import record_consent
from voxneuro.study.database import get_connection, run_migrations
from voxneuro.study.participant import register_participant
from voxneuro.study.registry import (
    create_protocol,
    create_study,
    get_protocol,
    get_study,
    list_protocols,
    update_study_protocol,
    update_study_status,
)
from voxneuro.study.schema import (
    ConsentRecord,
    Participant,
    ProtocolDefinition,
    ResearchSession,
    Study,
)
from voxneuro.study.session import create_session


@pytest.fixture
def db_conn(tmp_path: Path):
    db_file = tmp_path / "test_registry.db"
    run_migrations(db_file)
    conn = get_connection(db_file)
    yield conn
    conn.close()


def test_protocol_lifecycle(db_conn):
    proto = ProtocolDefinition(
        protocol_id="proto_multitask_v1",
        protocol_version="1.0.0",
        tasks=["sustained_vowel", "ddk"],
        visits_expected=2,
        minimum_interval_days=30,
        instructions="Complete tasks in quiet room",
    )
    create_protocol(db_conn, proto)

    retrieved = get_protocol(db_conn, "proto_multitask_v1", "1.0.0")
    assert retrieved.protocol_id == "proto_multitask_v1"
    assert retrieved.tasks == ["sustained_vowel", "ddk"]
    assert retrieved.visits_expected == 2

    all_p = list_protocols(db_conn)
    assert len(all_p) >= 1


def test_study_lifecycle(db_conn):
    proto = ProtocolDefinition(
        protocol_id="proto_voice_v1",
        protocol_version="1.0.0",
    )
    create_protocol(db_conn, proto)

    study = Study(
        study_id="study_pd_obs_01",
        study_name="Observational Parkinson Voice Study",
        study_description="Longitudinal speech monitoring",
        protocol_id="proto_voice_v1",
        protocol_version="1.0.0",
        study_status="active",
    )
    create_study(db_conn, study)

    retrieved = get_study(db_conn, "study_pd_obs_01")
    assert retrieved.study_name == "Observational Parkinson Voice Study"
    assert retrieved.study_status == "active"

    update_study_status(db_conn, "study_pd_obs_01", "paused")
    assert get_study(db_conn, "study_pd_obs_01").study_status == "paused"


def test_protocol_version_immutability_enforced(db_conn):
    # Setup Protocol v1, Protocol v2, Study, Participant, Session under v1
    proto1 = ProtocolDefinition(protocol_id="proto_immut_test", protocol_version="1.0.0")
    proto2 = ProtocolDefinition(protocol_id="proto_immut_test", protocol_version="2.0.0")
    create_protocol(db_conn, proto1)
    create_protocol(db_conn, proto2)

    study = Study(
        study_id="study_immut_test",
        study_name="Immutability Test",
        study_description="Testing immutable protocol versioning",
        protocol_id="proto_immut_test",
        protocol_version="1.0.0",
        study_status="active",
    )
    create_study(db_conn, study)

    # Before sessions exist, updating protocol is allowed
    update_study_protocol(db_conn, "study_immut_test", "proto_immut_test", "2.0.0")
    assert get_study(db_conn, "study_immut_test").protocol_version == "2.0.0"

    # Switch back to 1.0.0
    update_study_protocol(db_conn, "study_immut_test", "proto_immut_test", "1.0.0")

    # Enroll participant and create a session under v1.0.0
    p = Participant(
        participant_id="PT-IMMUT-01",
        study_id="study_immut_test",
        enrollment_status="enrolled",
    )
    register_participant(db_conn, p)
    c = ConsentRecord(
        consent_record_id="CONSENT-IMMUT-01",
        participant_id="PT-IMMUT-01",
        study_id="study_immut_test",
        consent_form_version="1.0.0",
        consent_date="2026-01-01T00:00:00Z",
        scope_of_permission=["voice_recording"],
    )
    record_consent(db_conn, c)

    sess = ResearchSession(
        session_id="sess-immut-01",
        study_id="study_immut_test",
        protocol_version="1.0.0",
        participant_id="PT-IMMUT-01",
        visit_index=1,
        consent_reference="CONSENT-IMMUT-01",
    )
    create_session(db_conn, sess)

    # Now that a session exists under 1.0.0, protocol update must be rejected
    with pytest.raises(ValueError, match="Cannot modify protocol for study"):
        update_study_protocol(db_conn, "study_immut_test", "proto_immut_test", "2.0.0")
