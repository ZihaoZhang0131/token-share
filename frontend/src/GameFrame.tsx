import type { CSSProperties, ReactNode } from "react";
import { Button } from "./components";
import { PixelIcon } from "./PixelIcon";

const skyClouds = [
  { top: 9, size: 160, duration: 260, phase: 0.17, position: 6, opacity: 0.88 },
  { top: 13, size: 102, duration: 310, phase: 0.77, position: 84, opacity: 0.68 },
  { top: 27, size: 108, duration: 300, phase: 0.23, position: 14, opacity: 0.72 },
  { top: 31, size: 208, duration: 250, phase: 0.73, position: 80, opacity: 0.86 },
  { top: 45, size: 184, duration: 290, phase: 0.15, position: 3, opacity: 0.78 },
  { top: 48, size: 122, duration: 335, phase: 0.82, position: 90, opacity: 0.65 },
  { top: 63, size: 94, duration: 320, phase: 0.25, position: 17, opacity: 0.66 },
  { top: 65, size: 170, duration: 280, phase: 0.75, position: 83, opacity: 0.82 },
  { top: 80, size: 212, duration: 270, phase: 0.19, position: 9, opacity: 0.84 },
  { top: 81, size: 100, duration: 340, phase: 0.81, position: 89, opacity: 0.7 },
  { top: 95, size: 136, duration: 305, phase: 0.16, position: 5, opacity: 0.74 },
  { top: 94, size: 194, duration: 285, phase: 0.72, position: 79, opacity: 0.8 },
];

export default function GameFrame({
  name,
  role,
  action,
  onAction,
  children,
}: {
  name: string;
  role: string;
  action: string;
  onAction: () => void;
  children: ReactNode;
}) {
  return (
    <div className="game-scene">
      <div className="sky-clouds" aria-hidden="true">
        {skyClouds.map((cloud, index) => (
          <span
            className="sky-cloud"
            key={index}
            style={
              {
                "--cloud-top": `${cloud.top}vh`,
                "--cloud-size": `${cloud.size}px`,
                "--cloud-duration": `${cloud.duration}s`,
                "--cloud-delay": `${-cloud.duration * cloud.phase}s`,
                "--rest-position": `${cloud.position}vw`,
                opacity: cloud.opacity,
              } as CSSProperties
            }
          />
        ))}
      </div>
      <div className="app-shell">
        <header className="window-header">
          <div className="window-brand">
            <span className="brand-tile">
              <PixelIcon name="sprout" size={32} />
            </span>
            <div>
              <strong>Token Station</strong>
            </div>
          </div>
          <div className="window-user">
            <span className="role-badge">{role}</span>
            <span className="user-name" title={name}>
              {name}
            </span>
            <Button variant="secondary" onClick={onAction}>
              {action}
            </Button>
          </div>
        </header>
        {children}
        <footer className="window-footer">
          <span>
            <PixelIcon name="shield" size={16} />
            不保存对话内容
          </span>
          <span>1 M = 1,000,000 Token</span>
        </footer>
      </div>
    </div>
  );
}
