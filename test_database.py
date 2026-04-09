# test_database_safe.py
from database import SurveyDatabase
import os
import glob


TEST_DB = "test_survey_data.db"


def cleanup_test_artifacts():
    """Remove test database and any backup CSVs created during testing."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    for pattern in [
        "participants_backup_*.csv",
        "responses_backup_*.csv",
    ]:
        for file in glob.glob(pattern):
            try:
                os.remove(file)
            except OSError:
                pass


def test_database():
    """Test the main functionality of the SurveyDatabase using a separate test DB."""
    print("🧪 Testing AI Survey Database (SAFE TEST MODE)")
    print("=" * 60)
    print(f"Using isolated test database: {TEST_DB}")

    # Start clean
    cleanup_test_artifacts()

    # Create isolated database instance
    db = SurveyDatabase(db_name=TEST_DB)

    # Test 1: Database creation
    print("\n📁 Test 1: Database Creation")
    assert os.path.exists(TEST_DB), "Test database file was not created."
    print("   ✅ Test database created successfully")

    # Test 2: Initial target setting
    print("\n📋 Test 2: Check Initial Target Setting")
    initial_target = db.get_target_participants()
    expected_target = 20
    assert initial_target == expected_target, f"Expected {expected_target}, got {initial_target}"
    print(f"   ✅ Initial target is set correctly at {initial_target}")

    # Test 3: Update target
    print("\n🎯 Test 3: Increase Participant Target")
    new_target = 20
    db.set_target_participants(new_target)
    updated_target = db.get_target_participants()
    assert updated_target == new_target, f"Expected {new_target}, got {updated_target}"
    print(f"   ✅ Participant target updated to {updated_target}")

    # Test 4: Participant allocation
    print("\n👥 Test 4: Participant Allocation")
    condition1, participant_id1 = db.get_next_condition()
    condition2, participant_id2 = db.get_next_condition()

    valid_conditions = ["Control", "Group A - Warning Label"]
    assert participant_id1 is not None
    assert participant_id2 is not None
    assert condition1 in valid_conditions
    assert condition2 in valid_conditions

    print(f"   ✅ Participant {participant_id1} assigned to {condition1}")
    print(f"   ✅ Participant {participant_id2} assigned to {condition2}")

    # Test 5: Update participant info
    print("\n📝 Test 5: Update Participant Info")
    db.update_participant_info(
        participant_id1,
        age=30,
        profession="Resident",
        sex="Female",
        race="Asian"
    )
    participants_df = db.export_participants()
    updated_row = participants_df[participants_df["id"] == participant_id1].iloc[0]

    assert updated_row["age"] == 30
    assert updated_row["profession"] == "Resident"
    assert updated_row["sex"] == "Female"
    assert updated_row["race"] == "Asian"
    print(f"   ✅ Participant {participant_id1} info updated successfully")

    # Test 6: Save response
    print("\n💬 Test 6: Save Survey Response")
    response_data = {
        "case_id": 1,
        "response_number": 1,
        "group": condition1,
        "user_age": 30,
        "user_profession": "Resident",
        "user_sex": "Female",
        "user_race": "Asian",
        "agree": "4 Agree",
        "trust": "Yes",
        "comment": "Looks reasonable."
    }
    db.save_response(participant_id1, response_data)

    responses_df = db.export_responses()
    assert not responses_df.empty, "Responses table should not be empty after saving a response."
    print(f"   ✅ Response saved successfully for participant {participant_id1}")

    # Test 7: Joined data export
    print("\n🔗 Test 7: Export Joined Data")
    joined_df = db.export_joined_data()
    assert not joined_df.empty, "Joined data should not be empty."
    print(f"   ✅ Joined data exported successfully: {len(joined_df)} rows")

    # Test 8: Delete one participant
    print("\n🗑️ Test 8: Delete One Participant")
    db.delete_participant(participant_id2)
    participants_after_delete = db.export_participants()
    assert participant_id2 not in participants_after_delete["id"].values
    print(f"   ✅ Participant {participant_id2} deleted successfully")

    # Test 9: Backup all data
    print("\n💾 Test 9: Backup All Data")
    participants_backup, responses_backup = db.backup_all_data()
    assert os.path.exists(participants_backup), f"Missing backup file: {participants_backup}"
    assert os.path.exists(responses_backup), f"Missing backup file: {responses_backup}"
    print(f"   ✅ Participants backup created: {participants_backup}")
    print(f"   ✅ Responses backup created: {responses_backup}")

    # Test 10: Delete all data
    print("\n🚨 Test 10: Delete All Data")
    participants_backup2, responses_backup2 = db.delete_all_data()
    assert os.path.exists(participants_backup2), f"Missing backup file: {participants_backup2}"
    assert os.path.exists(responses_backup2), f"Missing backup file: {responses_backup2}"

    final_participants = db.export_participants()
    final_responses = db.export_responses()

    assert final_participants.empty, "Participants table should be empty after delete_all_data()."
    assert final_responses.empty, "Responses table should be empty after delete_all_data()."
    print("   ✅ All data deleted successfully after backup")

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")

    # Final cleanup
    cleanup_test_artifacts()
    print("🧹 Test artifacts cleaned up")


if __name__ == "__main__":
    try:
        test_database()
    finally:
        cleanup_test_artifacts()