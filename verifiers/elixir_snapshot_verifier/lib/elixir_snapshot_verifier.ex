defmodule ElixirSnapshotVerifier do
  @moduledoc """
  Independent verifier for snapshot-based timetable outputs.
  """

  @start_minute 8 * 60
  @end_minute 18 * 60
  @lunch_start 12 * 60
  @lunch_end 13 * 60
  @day_order ~w(Monday Tuesday Wednesday Thursday Friday)
  @soft_labels %{
    "spread_sessions_across_days" => "Spread repeated sessions across different days",
    "prefer_morning_theory" => "Keep theory sessions in the morning",
    "prefer_afternoon_practicals" => "Keep practicals in the afternoon",
    "avoid_late_afternoon_starts" => "Avoid late-afternoon starts",
    "avoid_friday_sessions" => "Avoid Friday sessions",
    "prefer_standard_block_starts" => "Use standard block starts",
    "balance_teaching_load_across_week" => "Balance teaching load across the week",
    "avoid_monday_overload" => "Avoid Monday overload"
  }

  def main(args) do
    path = List.first(args) || "-"

    result =
      path
      |> read_snapshot!()
      |> verify_snapshot()

    IO.puts(Jason.encode!(result, pretty: true))
    System.halt(if(result["hard_valid"], do: 0, else: 1))
  end

  def verify_snapshot(snapshot) do
    hard_violations = verify_hard_constraints(snapshot)

    %{
      "verifier" => "elixir",
      "hard_valid" => hard_violations == [],
      "hard_violations" => hard_violations,
      "soft_summary" => summarize_soft_constraints(snapshot),
      "stats" => %{
        "entry_count" => length(snapshot["timetable_entries"] || []),
        "room_count" => length(snapshot["rooms"] || []),
        "attendance_group_count" => length(snapshot["attendance_groups"] || []),
        "shared_session_count" => length(snapshot["shared_sessions"] || [])
      }
    }
  end

  defp read_snapshot!("-") do
    {:ok, raw} = IO.read(:stdio, :eof) |> case do
      data when is_binary(data) -> {:ok, data}
      _ -> {:error, :invalid_input}
    end

    Jason.decode!(raw)
  end

  defp read_snapshot!(path) do
    path |> File.read!() |> Jason.decode!()
  end

  defp verify_hard_constraints(snapshot) do
    entries = build_entry_context(snapshot)

    base_violations =
      Enum.flat_map(entries, fn item ->
        room = item.entry["room"]
        session = item.session
        start_minute = integer(item.entry["start_minute"])
        duration_minutes = integer(item.entry["duration_minutes"])
        end_minute = start_minute + duration_minutes
        student_count = MapSet.size(item.student_hashes)
        room_capacity = integer(room["capacity"])

        []
        |> maybe_push(
          item.lecturer_ids == [],
          violation(
            "lecturer_assignment",
            "Session \"#{session["name"]}\" has no lecturer assigned."
          )
        )
        |> maybe_push(
          student_count > room_capacity,
          violation(
            "room_capacity_compatibility",
            "Session \"#{session["name"]}\" has #{student_count} students but room \"#{room["name"]}\" only holds #{room_capacity}."
          )
        )
        |> maybe_push(
          present?(session["required_room_type"]) and room["room_type"] != session["required_room_type"],
          violation(
            "room_capability_compatibility",
            "Session \"#{session["name"]}\" requires room type \"#{session["required_room_type"]}\" but was placed in \"#{room["room_type"]}\"."
          )
        )
      |> maybe_push(
        present?(session["required_lab_type"]) and room["lab_type"] != session["required_lab_type"],
        violation(
          "room_capability_compatibility",
          "Session \"#{session["name"]}\" requires lab type \"#{session["required_lab_type"]}\" but room \"#{room["name"]}\" is \"#{room["lab_type"]}\"."
        )
      )
      |> maybe_push(
        present?(room["year_restriction"]) and Enum.any?(item.study_years, &(&1 != integer(room["year_restriction"]))),
        violation(
          "room_year_restriction",
          "Session \"#{session["name"]}\" includes study years #{inspect(Enum.sort(item.study_years))} but room \"#{room["name"]}\" is restricted to year #{room["year_restriction"]}."
        )
      )
      |> maybe_push(
        present?(session["specific_room_id"]) and integer(room["id"]) != integer(session["specific_room_id"]),
        violation(
          "specific_room_restrictions",
          "Session \"#{session["name"]}\" must use room ##{session["specific_room_id"]} but was placed in room ##{room["id"]}."
          )
        )
        |> maybe_push(
          start_minute < @start_minute or end_minute > @end_minute,
          violation("working_hours_only", "Session \"#{session["name"]}\" falls outside working hours.")
        )
        |> maybe_push(
          overlap?(start_minute, end_minute, @lunch_start, @lunch_end),
          violation("lunch_break_protection", "Session \"#{session["name"]}\" overlaps the lunch window.")
        )
      end)

    room_violations =
      entries
      |> Enum.group_by(fn item -> {integer(item.entry["room"]["id"]), item.entry["day"]} end)
      |> Enum.flat_map(fn {{room_id, day}, grouped} ->
        pairwise_overlap_violations(
          grouped,
          "no_room_overlap",
          "Room ##{room_id} is double-booked on #{day}."
        )
      end)

    lecturer_violations =
      entries
      |> Enum.flat_map(fn item ->
        item.lecturer_ids
        |> Enum.map(fn lecturer_id -> {{lecturer_id, item.entry["day"]}, item} end)
      end)
      |> Enum.group_by(fn {key, _item} -> key end, fn {_key, item} -> item end)
      |> Enum.flat_map(fn {{lecturer_id, day}, grouped} ->
        pairwise_overlap_violations(
          grouped,
          "no_lecturer_overlap",
          "Lecturer ##{lecturer_id} is assigned to overlapping sessions on #{day}."
        )
      end)

    student_violations =
      entries
      |> Enum.flat_map(fn item ->
        item.student_hashes
        |> Enum.map(fn student_hash -> {{student_hash, item.entry["day"]}, item} end)
      end)
      |> Enum.group_by(fn {key, _item} -> key end, fn {_key, item} -> item end)
      |> Enum.flat_map(fn {{_student_hash, day}, grouped} ->
        pairwise_overlap_violations(
          grouped,
          "no_student_overlap",
          "Student membership overlaps on #{day}."
        )
      end)

    base_violations ++ room_violations ++ lecturer_violations ++ student_violations
  end

  defp summarize_soft_constraints(snapshot) do
    entries = build_entry_context(snapshot)

    sessions_by_id =
      Map.new(snapshot["shared_sessions"] || [], fn session ->
        {integer(session["id"]), session}
      end)

    occurrence_days =
      Enum.reduce(entries, %{}, fn item, acc ->
        update_in(
          acc,
          [Access.key(integer(item.entry["shared_session_id"]), %{})],
          &Map.put(&1, integer(item.entry["occurrence_index"]), item.entry["day"])
        )
      end)

    daily_minutes =
      Enum.reduce(@day_order, %{}, fn day, acc -> Map.put(acc, day, 0) end)
      |> then(fn initial ->
        Enum.reduce(entries, initial, fn item, acc ->
          Map.update!(acc, item.entry["day"], &(&1 + integer(item.entry["duration_minutes"])))
        end)
      end)

    Enum.map(snapshot["selected_soft_constraints"] || [], fn key ->
      build_soft_summary(key, entries, sessions_by_id, occurrence_days, daily_minutes)
    end)
  end

  defp build_soft_summary(
         "spread_sessions_across_days",
         _entries,
         sessions_by_id,
         occurrence_days,
         _daily_minutes
       ) do
    offenders =
      occurrence_days
      |> Enum.filter(fn {session_id, day_map} ->
        session = sessions_by_id[session_id] || %{}
        unique_day_count = day_map |> Map.values() |> MapSet.new() |> MapSet.size()

        integer(session["occurrences_per_week"] || 1) > 1 and
          map_size(day_map) != unique_day_count
      end)
      |> Enum.map(fn {session_id, _} -> (sessions_by_id[session_id] || %{})["name"] end)

    summary("spread_sessions_across_days", offenders == [], offenders, "Repeated sessions are on distinct days.")
  end

  defp build_soft_summary("prefer_morning_theory", entries, _sessions_by_id, _occurrence_days, _daily_minutes) do
    offenders =
      entries
      |> Enum.filter(fn item ->
        theory?(item.session["session_type"]) and
          integer(item.entry["start_minute"]) + integer(item.entry["duration_minutes"]) > @lunch_start
      end)
      |> Enum.map(fn item -> item.session["name"] end)

    summary("prefer_morning_theory", offenders == [], offenders, "All theory sessions finish before lunch.")
  end

  defp build_soft_summary("prefer_afternoon_practicals", entries, _sessions_by_id, _occurrence_days, _daily_minutes) do
    offenders =
      entries
      |> Enum.filter(fn item ->
        if practical?(item.session) do
          start_minute = integer(item.entry["start_minute"])
          duration_minutes = integer(item.entry["duration_minutes"])

          cond do
            duration_minutes >= 180 -> start_minute != @lunch_end
            duration_minutes >= 120 -> start_minute not in [@lunch_end, 14 * 60]
            true -> start_minute < @lunch_end
          end
        else
          false
        end
      end)
      |> Enum.map(fn item -> item.session["name"] end)

    summary(
      "prefer_afternoon_practicals",
      offenders == [],
      offenders,
      "All practical sessions start in the preferred afternoon window."
    )
  end

  defp build_soft_summary("avoid_late_afternoon_starts", entries, _sessions_by_id, _occurrence_days, _daily_minutes) do
    offenders =
      entries
      |> Enum.filter(fn item -> integer(item.entry["start_minute"]) > 14 * 60 end)
      |> Enum.map(fn item -> item.session["name"] end)

    summary("avoid_late_afternoon_starts", offenders == [], offenders, "No session starts after 2:00 PM.")
  end

  defp build_soft_summary("avoid_friday_sessions", entries, _sessions_by_id, _occurrence_days, _daily_minutes) do
    offenders =
      entries
      |> Enum.filter(fn item -> item.entry["day"] == "Friday" and theory?(item.session["session_type"]) end)
      |> Enum.map(fn item -> item.session["name"] end)

    summary("avoid_friday_sessions", offenders == [], offenders, "No theory sessions are scheduled on Friday.")
  end

  defp build_soft_summary("prefer_standard_block_starts", entries, _sessions_by_id, _occurrence_days, _daily_minutes) do
    offenders =
      entries
      |> Enum.filter(fn item ->
        not standard_start_allowed?(
          integer(item.entry["duration_minutes"]),
          integer(item.entry["start_minute"])
        )
      end)
      |> Enum.map(fn item -> item.session["name"] end)

    summary("prefer_standard_block_starts", offenders == [], offenders, "All sessions use standard block starts.")
  end

  defp build_soft_summary("balance_teaching_load_across_week", _entries, _sessions_by_id, _occurrence_days, daily_minutes) do
    values = Map.values(daily_minutes)
    peak = Enum.max(values, fn -> 0 end)
    trough = Enum.min(values, fn -> 0 end)

    %{
      "key" => "balance_teaching_load_across_week",
      "label" => @soft_labels["balance_teaching_load_across_week"],
      "satisfied" => peak - trough <= 180,
      "details" => "Daily load spread: #{inspect(daily_minutes)}."
    }
  end

  defp build_soft_summary("avoid_monday_overload", _entries, _sessions_by_id, _occurrence_days, daily_minutes) do
    monday = Map.get(daily_minutes, "Monday", 0)
    others = daily_minutes |> Map.delete("Monday") |> Map.values()
    satisfied = if others == [], do: true, else: monday <= Enum.min(others)

    %{
      "key" => "avoid_monday_overload",
      "label" => @soft_labels["avoid_monday_overload"],
      "satisfied" => satisfied,
      "details" => "Daily load spread: #{inspect(daily_minutes)}."
    }
  end

  defp build_soft_summary(key, _entries, _sessions_by_id, _occurrence_days, _daily_minutes) do
    %{
      "key" => key,
      "label" => Map.get(@soft_labels, key, key),
      "satisfied" => false,
      "details" => "Unknown soft constraint key."
    }
  end

  defp summary(key, true, _offenders, success_details) do
    %{
      "key" => key,
      "label" => @soft_labels[key],
      "satisfied" => true,
      "details" => success_details
    }
  end

  defp summary(key, false, offenders, _success_details) do
    %{
      "key" => key,
      "label" => @soft_labels[key],
      "satisfied" => false,
      "details" => "#{@soft_labels[key]} not satisfied: #{Enum.take(offenders, 5) |> Enum.join(", ")}"
    }
  end

  defp build_entry_context(snapshot) do
    groups_by_id =
      Map.new(snapshot["attendance_groups"] || [], fn group ->
        {integer(group["id"]), group}
      end)

    sessions_by_id =
      Map.new(snapshot["shared_sessions"] || [], fn session ->
        {integer(session["id"]), session}
      end)

    Enum.map(snapshot["timetable_entries"] || [], fn entry ->
      session = sessions_by_id[integer(entry["shared_session_id"])]
      attendance_group_ids = present_list(entry["attendance_group_ids"], session["attendance_group_ids"])
      lecturer_ids = present_list(entry["lecturer_ids"], session["lecturer_ids"])

      student_hashes =
        attendance_group_ids
        |> Enum.flat_map(fn group_id ->
          group = groups_by_id[integer(group_id)] || %{}
          group["student_hashes"] || []
        end)
        |> MapSet.new()

      study_years =
        attendance_group_ids
        |> Enum.reduce(MapSet.new(), fn group_id, acc ->
          case groups_by_id[integer(group_id)] do
            %{"study_year" => study_year} when not is_nil(study_year) ->
              MapSet.put(acc, integer(study_year))

            _ ->
              acc
          end
        end)

      %{
        entry: entry,
        session: session,
        lecturer_ids: Enum.map(lecturer_ids, &integer/1),
        student_hashes: student_hashes,
        study_years: study_years
      }
    end)
  end

  defp pairwise_overlap_violations(entries, constraint, message) do
    entries
    |> Enum.with_index()
    |> Enum.flat_map(fn {item, index} ->
      entries
      |> Enum.drop(index + 1)
      |> Enum.filter(fn other ->
        overlap?(
          integer(item.entry["start_minute"]),
          integer(item.entry["start_minute"]) + integer(item.entry["duration_minutes"]),
          integer(other.entry["start_minute"]),
          integer(other.entry["start_minute"]) + integer(other.entry["duration_minutes"])
        )
      end)
      |> Enum.map(fn _other -> violation(constraint, message) end)
    end)
  end

  defp violation(constraint, message), do: %{"constraint" => constraint, "message" => message}

  defp maybe_push(list, true, value), do: [value | list]
  defp maybe_push(list, false, _value), do: list

  defp overlap?(start_a, end_a, start_b, end_b), do: start_a < end_b and start_b < end_a

  defp theory?(session_type) do
    normalized = session_type |> to_string() |> String.downcase()
    normalized in ["lecture", "tutorial", "seminar"]
  end

  defp practical?(session) do
    normalized = session["session_type"] |> to_string() |> String.downcase()
    normalized in ["practical", "lab", "laboratory"] or
      present?(session["required_lab_type"]) or session["required_room_type"] == "lab"
  end

  defp standard_start_allowed?(duration_minutes, start_minute) when duration_minutes >= 180,
    do: start_minute in [9 * 60, 13 * 60]

  defp standard_start_allowed?(120, start_minute), do: start_minute in [8 * 60, 10 * 60, 13 * 60]
  defp standard_start_allowed?(90, start_minute), do: start_minute in [8 * 60, 13 * 60]
  defp standard_start_allowed?(60, start_minute), do: start_minute in [8 * 60, 10 * 60, 13 * 60, 15 * 60]
  defp standard_start_allowed?(_duration_minutes, _start_minute), do: true

  defp present?(value), do: not is_nil(value) and value != ""

  defp present_list(list, _fallback) when is_list(list) and list != [], do: list
  defp present_list(_list, fallback) when is_list(fallback), do: fallback
  defp present_list(_list, _fallback), do: []

  defp integer(value) when is_integer(value), do: value
  defp integer(value) when is_float(value), do: trunc(value)
  defp integer(value) when is_binary(value), do: String.to_integer(value)
  defp integer(value) when is_nil(value), do: 0
end
