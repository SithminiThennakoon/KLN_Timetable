defmodule ElixirSnapshotVerifierTest do
  use ExUnit.Case

  test "valid snapshot passes hard checks" do
    snapshot = %{
      "selected_soft_constraints" => ["prefer_morning_theory"],
      "rooms" => [
        %{"id" => 1, "name" => "Hall A", "capacity" => 80, "room_type" => "lecture", "lab_type" => nil, "year_restriction" => nil}
      ],
      "attendance_groups" => [
        %{"id" => 1, "study_year" => 1, "student_hashes" => ["s1", "s2", "s3"]}
      ],
      "shared_sessions" => [
        %{
          "id" => 1,
          "name" => "CHEM 101 Lecture",
          "session_type" => "lecture",
          "occurrences_per_week" => 1,
          "required_room_type" => "lecture",
          "required_lab_type" => nil,
          "specific_room_id" => nil,
          "lecturer_ids" => [1],
          "attendance_group_ids" => [1]
        }
      ],
      "timetable_entries" => [
        %{
          "shared_session_id" => 1,
          "day" => "Monday",
          "start_minute" => 8 * 60,
          "duration_minutes" => 120,
          "occurrence_index" => 1,
          "room" => %{"id" => 1, "name" => "Hall A", "capacity" => 80, "room_type" => "lecture", "lab_type" => nil, "year_restriction" => nil},
          "lecturer_ids" => [1],
          "attendance_group_ids" => [1]
        }
      ]
    }

    result = ElixirSnapshotVerifier.verify_snapshot(snapshot)
    assert result["hard_valid"]
    assert result["hard_violations"] == []
  end

  test "capacity violation is reported" do
    snapshot = %{
      "selected_soft_constraints" => [],
      "rooms" => [
        %{"id" => 1, "name" => "Hall A", "capacity" => 1, "room_type" => "lecture", "lab_type" => nil, "year_restriction" => nil}
      ],
      "attendance_groups" => [
        %{"id" => 1, "study_year" => 1, "student_hashes" => ["s1", "s2", "s3"]}
      ],
      "shared_sessions" => [
        %{
          "id" => 1,
          "name" => "CHEM 101 Lecture",
          "session_type" => "lecture",
          "occurrences_per_week" => 1,
          "required_room_type" => "lecture",
          "required_lab_type" => nil,
          "specific_room_id" => nil,
          "lecturer_ids" => [1],
          "attendance_group_ids" => [1]
        }
      ],
      "timetable_entries" => [
        %{
          "shared_session_id" => 1,
          "day" => "Monday",
          "start_minute" => 8 * 60,
          "duration_minutes" => 120,
          "occurrence_index" => 1,
          "room" => %{"id" => 1, "name" => "Hall A", "capacity" => 1, "room_type" => "lecture", "lab_type" => nil, "year_restriction" => nil},
          "lecturer_ids" => [1],
          "attendance_group_ids" => [1]
        }
      ]
    }

    result = ElixirSnapshotVerifier.verify_snapshot(snapshot)
    refute result["hard_valid"]
    assert Enum.any?(result["hard_violations"], fn item ->
             item["constraint"] == "room_capacity_compatibility"
           end)
  end

  test "room year restriction violation is reported" do
    snapshot = %{
      "selected_soft_constraints" => [],
      "rooms" => [
        %{"id" => 1, "name" => "Hall A", "capacity" => 80, "room_type" => "lecture", "lab_type" => nil, "year_restriction" => 2}
      ],
      "attendance_groups" => [
        %{"id" => 1, "study_year" => 1, "student_hashes" => ["s1", "s2", "s3"]}
      ],
      "shared_sessions" => [
        %{
          "id" => 1,
          "name" => "CHEM 101 Lecture",
          "session_type" => "lecture",
          "occurrences_per_week" => 1,
          "required_room_type" => "lecture",
          "required_lab_type" => nil,
          "specific_room_id" => nil,
          "lecturer_ids" => [1],
          "attendance_group_ids" => [1]
        }
      ],
      "timetable_entries" => [
        %{
          "shared_session_id" => 1,
          "day" => "Monday",
          "start_minute" => 8 * 60,
          "duration_minutes" => 120,
          "occurrence_index" => 1,
          "room" => %{"id" => 1, "name" => "Hall A", "capacity" => 80, "room_type" => "lecture", "lab_type" => nil, "year_restriction" => 2},
          "lecturer_ids" => [1],
          "attendance_group_ids" => [1]
        }
      ]
    }

    result = ElixirSnapshotVerifier.verify_snapshot(snapshot)
    refute result["hard_valid"]
    assert Enum.any?(result["hard_violations"], fn item ->
             item["constraint"] == "room_year_restriction"
           end)
  end
end
