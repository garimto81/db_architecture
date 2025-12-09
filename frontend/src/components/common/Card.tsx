/**
 * Card Component - 재사용 가능한 카드 컴포넌트
 * BLOCK_FRONTEND / FrontendAgent
 */

import type { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  title?: string;
  className?: string;
  action?: ReactNode;
}

export function Card({ children, title, className = '', action }: CardProps) {
  return (
    <div className={`card ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between mb-4">
          {title && <h3 className="text-lg font-semibold text-gray-900">{title}</h3>}
          {action && <div>{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}
