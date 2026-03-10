import React from "react";

/**
 * Inline confirmation strip that replaces an instant delete button.
 *
 * Usage:
 *   <ConfirmDelete
 *     label="Remove Room"               // button text when idle
 *     confirmMessage="Delete Room 1?"   // text shown when pending
 *     cascadeNote="Also removes 2 sessions."  // optional extra line
 *     onConfirm={() => removeRecord(...)}
 *   />
 */
export function ConfirmDelete({ label = "Remove", confirmMessage, cascadeNote, onConfirm, className = "danger-btn" }) {
  const [pending, setPending] = React.useState(false);

  if (!pending) {
    return (
      <button
        type="button"
        className={className}
        onClick={() => setPending(true)}
      >
        {label}
      </button>
    );
  }

  return (
    <span className="confirm-strip">
      <span className="confirm-strip-msg">
        {confirmMessage || "Are you sure?"}
        {cascadeNote && <span className="confirm-strip-note"> {cascadeNote}</span>}
      </span>
      <button
        type="button"
        className="danger-btn confirm-strip-yes"
        onClick={() => { setPending(false); onConfirm(); }}
      >
        Delete
      </button>
      <button
        type="button"
        className="ghost-btn confirm-strip-cancel"
        onClick={() => setPending(false)}
      >
        Cancel
      </button>
    </span>
  );
}
