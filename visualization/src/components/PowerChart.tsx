import { useState } from "react";
import type {
  PowerDistributionUnified,
  RoleNodeUnified,
} from "../types/unified";
import { powerColor } from "../utils/exploration";

interface PowerChartProps {
  data: PowerDistributionUnified[];
  roles: RoleNodeUnified[];
  onRoleClick: (id: string) => void;
}

export function PowerChart({ data, roles, onRoleClick }: PowerChartProps) {
  const [power, setPower] = useState<string | null>(null);
  const selected = data.find((item) => item.power === power) ?? data[0];
  const members = roles
    .filter((role) => selected?.roles.includes(role.id))
    .sort((a, b) => b.appearances - a.appearances);
  const maximum = data[0]?.count ?? 1;
  return (
    <section className="surface power-view">
      <div className="section-heading">
        <div>
          <p className="eyebrow">从人物看诸国</p>
          <h2>势力与人物</h2>
        </div>
        <span className="count-label">{data.length} 个势力</span>
      </div>
      <p className="context-note">
        按当前关系网中已知归属的人物统计，不代表国力、人口或疆域。点击势力查看人物，再点姓名阅读详情。
      </p>
      {!selected ? (
        <div className="empty-state">
          <h3>当前范围没有可统计的人物</h3>
          <p>试试扩大范围或返回前五卷。</p>
        </div>
      ) : (
        <div className="power-layout">
          <div className="power-list" aria-label="选择势力">
            {data.map((item) => (
              <button
                key={item.power}
                className="power-row"
                aria-pressed={selected.power === item.power}
                onClick={() => setPower(item.power)}
              >
                <span>{item.power}</span>
                <span className="power-track">
                  <span
                    style={{
                      width: `${(100 * item.count) / maximum}%`,
                      background: powerColor(item.power),
                    }}
                  />
                </span>
                <strong>{item.count}</strong>
              </button>
            ))}
          </div>
          <div className="power-members">
            <div className="event-list-heading">
              <h3>{selected.power}</h3>
              <span>{selected.count} 人</span>
            </div>
            <div className="person-grid">
              {members.map((role) => (
                <button key={role.id} onClick={() => onRoleClick(role.id)}>
                  <strong>{role.name}</strong>
                  <span>提及 {role.appearances} 次 ↗</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
