import { useState, useMemo } from "react";

export default function SearchableMultiSelect({
  options,
  selectedIds,
  onChange,
  getLabel,
  placeholder = "Search...",
}) {
  const [search, setSearch] = useState("");

  const filteredOptions = useMemo(() => {
    if (!search.trim()) {
      return options;
    }
    const query = search.toLowerCase();
    return options.filter((opt) => getLabel(opt).toLowerCase().includes(query));
  }, [options, search, getLabel]);

  const selectedOptions = useMemo(
    () => options.filter((opt) => selectedIds.includes(opt.id)),
    [options, selectedIds]
  );

  const handleToggle = (id) => {
    if (selectedIds.includes(id)) {
      onChange(selectedIds.filter((sid) => sid !== id));
    } else {
      onChange([...selectedIds, id]);
    }
  };

  const handleRemove = (id) => {
    onChange(selectedIds.filter((sid) => sid !== id));
  };

  return (
    <div className="searchable-multi-select">
      {selectedOptions.length > 0 && (
        <div className="sms-chips">
          {selectedOptions.map((opt) => (
            <span key={opt.id} className="sms-chip">
              {getLabel(opt)}
              <button
                type="button"
                className="sms-chip-remove"
                onClick={() => handleRemove(opt.id)}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <input
        type="text"
        className="sms-search"
        placeholder={placeholder}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <div className="sms-dropdown">
        {filteredOptions.length === 0 ? (
          <div className="sms-empty">No options found</div>
        ) : (
          filteredOptions.map((opt) => (
            <label key={opt.id} className="sms-option">
              <input
                type="checkbox"
                checked={selectedIds.includes(opt.id)}
                onChange={() => handleToggle(opt.id)}
              />
              <span>{getLabel(opt)}</span>
            </label>
          ))
        )}
      </div>
    </div>
  );
}
