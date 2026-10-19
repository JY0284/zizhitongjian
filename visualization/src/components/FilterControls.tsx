import { useState } from "react";
import { readFilterDraft } from "../utils/exploration";

interface FilterControlsProps {
  juanRange: [number, number];
  timeRange: [number | null, number | null];
  maxJuan: number;
  onApply: (
    juans: [number, number],
    years: [number | null, number | null],
  ) => void;
  onPreset: (
    juans: [number, number],
    years: [number | null, number | null],
  ) => void;
  syncJuanYear: boolean;
  syncAvailable: boolean;
  onSyncJuanYearChange: (enabled: boolean) => void;
}

export function FilterControls({
  juanRange,
  timeRange,
  maxJuan,
  onApply,
  onPreset,
  syncJuanYear,
  syncAvailable,
  onSyncJuanYearChange,
}: FilterControlsProps) {
  const [juans, setJuans] = useState<[string, string]>([
    String(juanRange[0]),
    String(juanRange[1]),
  ]);
  const [years, setYears] = useState<[string, string]>(
    timeRange.map((value) => (value === null ? "" : String(value))) as [
      string,
      string,
    ],
  );
  const [error, setError] = useState("");
  const preset = (range: [number, number]) => {
    setJuans([String(range[0]), String(range[1])]);
    setYears(["", ""]);
    setError("");
    onPreset(range, [null, null]);
  };
  return (
    <form
      className="surface filter-panel"
      onSubmit={(event) => {
        event.preventDefault();
        const result = readFilterDraft(juans, years, maxJuan);
        if (result.error !== undefined) {
          setError(result.error);
          return;
        }
        setError("");
        onApply(result.juans, result.years);
      }}
    >
      <div className="section-heading">
        <h2>阅读范围</h2>
        <span className="count-label">已收录前五卷</span>
      </div>
      <div className="preset-buttons">
        <button type="button" onClick={() => preset([1, 1])}>
          第一卷
        </button>
        <button type="button" onClick={() => preset([1, 5])}>
          前五卷
        </button>
      </div>
      <fieldset>
        <legend>按卷选择</legend>
        <div className="input-pair">
          {(["起始卷", "结束卷"] as const).map((label, i) => (
            <label key={label}>
              {label}
              <input
                inputMode="numeric"
                value={juans[i]}
                onChange={(e) =>
                  setJuans(
                    i === 0
                      ? [e.target.value, juans[1]]
                      : [juans[0], e.target.value],
                  )
                }
              />
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend>按年代细选</legend>
        <p className="field-hint">公元前用负数，如 −403；留空不限。</p>
        <div className="input-pair">
          {(["起始年", "结束年"] as const).map((label, i) => (
            <label key={label}>
              {label}
              <input
                inputMode="text"
                placeholder="不限"
                value={years[i]}
                onChange={(e) =>
                  setYears(
                    i === 0
                      ? [e.target.value, years[1]]
                      : [years[0], e.target.value],
                  )
                }
              />
            </label>
          ))}
        </div>
      </fieldset>
      <label className="check-label">
        <input
          type="checkbox"
          checked={syncJuanYear}
          disabled={!syncAvailable}
          onChange={(e) => onSyncJuanYearChange(e.target.checked)}
        />
        卷数与年代联动
      </label>
      <p className="field-hint">
        只修改卷数或年代时，自动匹配另一项。限定年份后不包含年份待考的记载。
      </p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="filter-actions">
        <button className="primary-button" type="submit">
          应用范围
        </button>
        <button
          type="button"
          className="quiet-button"
          onClick={() => preset([1, 5])}
        >
          重置
        </button>
      </div>
    </form>
  );
}
